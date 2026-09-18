"""Update Coordinators."""

# region #-- imports --#
from __future__ import annotations

import asyncio
import copy
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum, auto
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyvelop.exceptions import (
    MeshConnectionError,
    MeshDeviceNotFoundResponse,
    MeshException,
    MeshInvalidCredentials,
    MeshNodeNotPrimary,
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh, MeshSnapshot, SpeedtestResult
from pyvelop.mesh_entity import DeviceEntity, NodeEntity, NodeType

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_EVENTS_OPTIONS,
    CONF_EVENTS_WAIT_IP,
    CONF_UI_DEVICES,
    CONF_UI_PLACEHOLDER_DEVICE_ID,
    DEF_API_REQUEST_TIMEOUT,
    DEF_EVENTS_OPTIONS,
    DEF_EVENTS_WAIT_IP,
    DOMAIN,
    ISSUE_MISSING_DEVICE_TRACKER,
    ISSUE_MISSING_UI_DEVICE,
    EventSubTypes,
)
from .exceptions import (
    BlockingTaskRunning,
    CoordinatorTimeout,
    GeneralException,
)
from .helpers import get_mesh_parent_node, get_registry_device
from .logger import Logger

# endregion


_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass
class DataUpdateCoordinatorData:
    """Representation of the data available to the update coordinator."""

    mesh: MeshSnapshot | None = field(kw_only=True, default=None)
    device_tracker: tuple[DeviceEntity, ...] = field(
        default_factory=tuple, kw_only=True
    )


@dataclass
class LinksysVelopRuntimeData:
    """Runtime data for the ConfigEntry."""

    api: Mesh
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse
    blocking_tasks: set[str] = field(default_factory=set)
    speedtest_data: SpeedtestResult | None = None


type LinksysVelopConfigEntry = ConfigEntry[LinksysVelopRuntimeData]


class BlockingTasks(StrEnum):
    """Representation of tasks that could cause a delay in response from the Mesh."""

    CHANNEL_SCAN = "Channel Scan"
    REBOOT = "Reboot"
    SPEEDTEST = "Speedtest"


class CoordinatorTimers(StrEnum):
    """The timer types available to a DataCoordinator."""

    DEVICE_TRACKER = auto()
    MESH = auto()


class LinksysVelopDataUpdateCoordinator(DataUpdateCoordinator):
    """Base class for the update coordinators."""

    config_entry: LinksysVelopConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        config_entry: LinksysVelopConfigEntry,
        mesh: Mesh,
        name: str,
        update_interval_secs: float,
    ) -> None:
        """Initialise."""

        self.api: Mesh = mesh

        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(seconds=update_interval_secs),
        )

    def _delay_run(self) -> bool:
        """Return True if the request to the mesh should be delayed."""

        # region #-- intensive task running so back off --#
        if self.config_entry.runtime_data.blocking_tasks:
            exc: BlockingTaskRunning = BlockingTaskRunning(
                translation_domain=DOMAIN,
                translation_key="intensive_task",
                translation_placeholders={
                    "coordinator_name": self.__class__.__name__,
                    "tasks": ",".join(self.config_entry.runtime_data.blocking_tasks),
                },
            )
            _LOGGER.warning(exc)
            return True
        # endregion

        return False


class LinksysVelopDataUpdateCoordinatorMultiUse(LinksysVelopDataUpdateCoordinator):
    """Retrieve the data from the Velop mesh."""

    data: DataUpdateCoordinatorData

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        api: Mesh,
        name: str,
        config_entry: LinksysVelopConfigEntry,
        update_interval_secs: float,
        **kwargs: float,
    ) -> None:
        """Initialise.

        Possible values kwargs are: -

        tracker_update_interval_secs
        """

        update_intervals: set[float] = set()
        update_intervals.add(update_interval_secs)
        for value in kwargs.values():
            update_intervals.add(value)

        base_update_interval_secs: float = min(update_intervals)

        super().__init__(
            hass,
            logger,
            mesh=api,
            name=name,
            config_entry=config_entry,
            update_interval_secs=base_update_interval_secs,
        )

        self.data = DataUpdateCoordinatorData(mesh=api.latest_snapshot)

        # region #-- custom instance variables --#
        self._configured_events: list[str] = self.config_entry.options.get(
            CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
        )
        self._timers: dict[CoordinatorTimers, Any] = {
            CoordinatorTimers.MESH: {
                "interval": update_interval_secs,
                "is_running": False,
                "last_success": None,
                "listeners": [],
            },
        }
        if kwargs.get("tracker_update_interval_secs") is not None:
            self._timers.update(
                {
                    CoordinatorTimers.DEVICE_TRACKER: {
                        "interval": kwargs.get("tracker_update_interval_secs"),
                        "is_running": False,
                        "last_success": None,
                        "listeners": [],
                    }
                }
            )
        self._waiting_for_ip: set[str] = set()
        # endregion

        # region #-- add a listener --#
        config_entry.async_on_unload(self.async_add_listener(self._process_listeners))
        # endregion

    def _create_missing_ui_issue(self, device: DeviceEntry, ui_id: str) -> None:
        """Create a Home Assistant issue for a missing UI device.

        :param device: `DeviceEntry` from the HA registry.
        :param ui_id: ID of the device from the mesh.
        """
        name = device.name_by_user or device.name
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{ISSUE_MISSING_UI_DEVICE}::{ui_id}",
            data={
                "config_entry": self.config_entry.entry_id,
                "device_name": name,
                "velop_id": ui_id,
            },
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key=ISSUE_MISSING_UI_DEVICE,
            translation_placeholders={"device_name": str(name)},
        )

    def _create_tracker_issue(self, entity: er.RegistryEntry, tracker_id: str):
        """Create a Home Assistant issue for a missing device tracker."""
        name = entity.name or entity.original_name or ""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_MISSING_DEVICE_TRACKER,
            data={
                "config_entry": self.config_entry.entry_id,
                "device_id": entity.entity_id,
                "device_name": name,
                "velop_id": tracker_id,
            },
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.ERROR,
            translation_key=ISSUE_MISSING_DEVICE_TRACKER,
            translation_placeholders={"device_name": name},
        )

    def _dispatch_new_entities(
        self,
        mesh_data: MeshSnapshot,
        prev_node_serials: set[str],
        cur_node_serials: set[str],
        prev_device_ids: set[str],
        cur_device_ids: set[str],
    ) -> None:
        """Dispatch events for newly discovered nodes and devices.

        :param mesh_data: recently polled and current data.
        :param prev_node_serials: previously gathered node serial numbers.
        :param cur_node_serials: current nodes serial numbers
        :param prev_device_ids: previously gathered device unique IDs.
        :param cur_device_ids: current device unique IDs.
        """

        # new nodes
        if EventSubTypes.NEW_NODE_FOUND.value in self._configured_events:
            for serial in cur_node_serials - prev_node_serials:
                if node_info := next(
                    (node for node in mesh_data.nodes if node.serial.value == serial),
                    None,
                ):
                    async_dispatcher_send(
                        self.hass,
                        f"{DOMAIN}_{EventSubTypes.NEW_NODE_FOUND.value}",
                        node_info,
                    )

        # new devices
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            new_ids = (cur_device_ids - prev_device_ids).union(self._waiting_for_ip)
            for dev_id in new_ids:
                if device_info := next(
                    (
                        device
                        for device in mesh_data.devices
                        if device.unique_id.value == dev_id
                    ),
                    None,
                ):
                    has_ip = any(adi.ip or adi.ipv6 for adi in device_info.adapter_info)
                    wait_for_ip_enabled = self.config_entry.options.get(
                        CONF_EVENTS_WAIT_IP, DEF_EVENTS_WAIT_IP
                    )

                    if wait_for_ip_enabled and not has_ip:
                        self._waiting_for_ip.add(dev_id)
                    else:
                        self._waiting_for_ip.discard(dev_id)
                        async_dispatcher_send(
                            self.hass,
                            f"{DOMAIN}_{EventSubTypes.NEW_DEVICE_FOUND.value}",
                            device_info,
                        )

    def _handle_missing_nodes(
        self,
        prev_serials: set[str],
        cur_serials: set[str],
        device_registry: DeviceRegistry,
    ) -> None:
        """Clean up registry entries for nodes that have disappeared from the mesh.

        :param prev_serials: serial numbers from the previous data.
        :param cur_serials: serial numbers from the current data.
        :param device_registry: `DeviceRegistry` object that should be updated.
        """
        for serial in prev_serials - cur_serials:
            dr_device = get_registry_device(
                self.hass, serial, self.config_entry.entry_id
            )
            if dr_device:
                device_registry.async_update_device(
                    device_id=dr_device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

    def _handle_missing_trackers(self, missing_ids: list[str]) -> None:
        """Process devices that were not found by the API.

        :param missing_ids: Mesh IDs of the devices that are missing from the mesh.
        """
        entity_registry = er.async_get(self.hass)
        config_entities = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        for tracker_id in missing_ids:
            # construct the unique ID for the tracker entity
            unique_id = (
                f"{self.config_entry.entry_id}::{Platform.DEVICE_TRACKER}::{tracker_id}"
            )
            entity = next(
                (e for e in config_entities if e.unique_id == unique_id), None
            )

            if entity:
                self._create_tracker_issue(entity, tracker_id)
            else:
                remove_tracker_from_options(self.hass, self.config_entry, tracker_id)

    def _process_listeners(self) -> None:
        """Process the listeners for any timers that were executing."""

        for timer_type, timer_data in self._timers.items():
            if timer_data.get("is_running", False):
                for listener in timer_data.get("listeners", []):
                    try:
                        timer_data["is_running"] = False
                        listener()
                    except Exception:  # noqa: BLE001
                        _LOGGER.error(
                            "unexpected error executing listener for %s", timer_type
                        )

    async def _safe_api_call[T](
        self, api_func: Callable[[], Awaitable[T]], timeout_key: tuple[str, float]
    ) -> T:
        """Wraps API calls to provide centralized exception handling and Home Assistant error translation.

        :param api_func: Callable to execute against the mesh.
        :param timeout_key:
        :returns: Response from the mesh.
        :raises:
        """

        try:
            return await api_func()
        except (MeshConnectionError, MeshTimeoutError) as err:
            _LOGGER.warning(
                CoordinatorTimeout(
                    translation_domain=DOMAIN,
                    translation_key="coordinator_timeout",
                    translation_placeholders={
                        "current_timeout": self.config_entry.options.get(
                            timeout_key[0], timeout_key[1]
                        )
                    },
                )
            )
            raise UpdateFailed(err) from err
        except MeshInvalidCredentials:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="failed_login"
            )
        except MeshException as err:
            raise UpdateFailed(type(err).__name__) from err
        except Exception as err:
            _LOGGER.warning(
                GeneralException(
                    translation_domain=DOMAIN,
                    translation_key="general",
                    translation_placeholders={
                        "exc_type": type(err).__name__,
                        "exc_msg": str(err),
                    },
                )
            )
            raise UpdateFailed(err) from err

    def _sync_node_attributes(
        self,
        prev_nodes: tuple[NodeEntity, ...],
        mesh_data: MeshSnapshot,
        device_registry: DeviceRegistry,
    ):
        """Update attributes for existing nodes.

        :param prev_nodes: `NodeEntity` objects from the previous data.
        :param mesh_data: the current data.
        :param device_regiastry: `DeviceRegistry` object that should be updated.
        """
        for prev_node in prev_nodes:
            serial = prev_node.serial.value
            if not serial:
                continue

            dr_node = get_registry_device(self.hass, serial, self.config_entry.entry_id)
            curr_node = next(
                (n for n in mesh_data.nodes if n.serial.value == serial), None
            )
            if not dr_node or not curr_node:
                continue

            updates = {}

            # IP -> config_url
            if curr_node.type.value == NodeType.SECONDARY:
                cur_ip = next(
                    (adi.ip for adi in curr_node.adapter_info if adi.primary), None
                )
                prev_ip = next(
                    (adi.ip for adi in prev_node.adapter_info if adi.primary), None
                )
                if cur_ip and cur_ip != prev_ip:
                    updates["configuration_url"] = f"http://{cur_ip}/ca"

            # name
            if curr_node.name.value != prev_node.name.value:
                updates["name"] = curr_node.name.value

            # via device (parent)
            if curr_node.type.value == NodeType.SECONDARY:
                parent = get_mesh_parent_node(curr_node, mesh_data)
                if parent and parent.serial.value:
                    parent_dr = get_registry_device(
                        self.hass, parent.serial.value, self.config_entry.entry_id
                    )
                    if parent_dr and dr_node.via_device_id != parent_dr.id:
                        updates["via_device_id"] = parent_dr.id

            if updates:
                _LOGGER.debug("Updating attributes for %s: %s", prev_node.name, updates)
                device_registry.async_update_device(dr_node.id, **updates)

    def _sync_ui_devices(
        self,
        mesh_data: MeshSnapshot,
        device_registry: DeviceRegistry,
        current_devices: set[str],
    ) -> None:
        """Synchronize device names and handle missing UI devices.

        :param mesh_data: current data from the mesh.
        :param device_registry: `DeviceRegistry` object that should be updated.
        :param current_devices: Device unique IDs
        """
        ui_devices = self.config_entry.options.get(CONF_UI_DEVICES, [])
        placeholder_id = self.config_entry.data.get(CONF_UI_PLACEHOLDER_DEVICE_ID)

        for ui_id in ui_devices:
            if ui_id == placeholder_id:
                continue

            dr_ui_device = get_registry_device(
                self.hass, ui_id, self.config_entry.entry_id
            )
            cur_ui_entity = next(
                (d for d in mesh_data.devices if d.unique_id.value == ui_id), None
            )

            # device exists in mesh and registry -> update name if changed
            if cur_ui_entity and dr_ui_device:
                if cur_ui_entity.name.value != dr_ui_device.name:
                    device_registry.async_update_device(
                        dr_ui_device.id, name=cur_ui_entity.name.value
                    )

            # device is missing from current mesh data
            elif ui_id not in current_devices:
                if dr_ui_device:
                    self._create_missing_ui_issue(dr_ui_device, ui_id)
                else:
                    remove_ui_device_from_options(self.hass, self.config_entry, ui_id)

    def add_listener_for_timer_type(
        self, timer_type: CoordinatorTimers, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Add a listener for a particular timer type.

        :param timer_type: Type of timer the listener should be associated with.
        :param listener: Callable that should be called when the timer has completed processing.
        :returns: Callable that can be used to unregister the listener.
        """

        self._timers.get(timer_type, {}).get("listeners", []).append(listener)

        def _unsub() -> None:
            if listener in self._timers.get(timer_type, {}).get("listeners", []):
                self._timers.get(timer_type, {}).get("listeners", []).remove(listener)

        return _unsub

    async def _async_get_device_tracker_data(self) -> tuple[DeviceEntity, ...]:
        """Get the device tracker information from the mesh.

        :returns: Device details from the mesh for the configured devices.
        """

        if self._delay_run():
            return self.data.device_tracker

        tracked_ids = self.config_entry.options.get(CONF_DEVICE_TRACKERS, [])

        try:
            return await self._safe_api_call(
                lambda: self.api.async_get_devices(tracked_ids),
                (CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT),
            )
        except MeshDeviceNotFoundResponse as err:
            self._handle_missing_trackers(err.devices)
            return ()  # return empty tuple as devices were not found

    async def _async_get_mesh_data(self) -> MeshSnapshot | None:
        """Get all data from the mesh and sync states with Home Assistant.

        :returns: Snapshot of the current mesh data. `None` if it hasn't been initialised yet.
        """

        if self._delay_run():
            return self.data.mesh

        # index previous details for comparison
        prev_mesh: MeshSnapshot | None = (
            self.data.mesh if isinstance(self.data.mesh, MeshSnapshot) else None
        )
        prev_nodes = prev_mesh.nodes if prev_mesh else ()
        prev_node_serials = {n.serial.value for n in prev_nodes if n.serial.value}
        prev_device_ids = (
            {d.unique_id.value for d in prev_mesh.devices if d.unique_id.value}
            if prev_mesh
            and EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events
            else set()
        )

        # get the details from the mesh
        mesh_data: MeshSnapshot = await self._safe_api_call(
            self.api.async_refresh, (CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT)
        )

        # index the current details for comparison
        cur_node_serials = {n.serial.value for n in mesh_data.nodes if n.serial.value}
        cur_device_ids = set()
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            cur_device_ids = {
                d.unique_id.value for d in mesh_data.devices if d.unique_id.value
            }

        # sync the data
        device_registry = dr.async_get(self.hass)
        self._sync_node_attributes(prev_nodes, mesh_data, device_registry)
        self._sync_ui_devices(mesh_data, device_registry, cur_device_ids)
        self._handle_missing_nodes(prev_node_serials, cur_node_serials, device_registry)
        self._dispatch_new_entities(
            mesh_data,
            prev_node_serials,
            cur_node_serials,
            prev_device_ids,
            cur_device_ids,
        )

        return mesh_data

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        try:
            await self.api.async_authenticate_and_refresh()
        except MeshInvalidCredentials as exc:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="failed_login",
            ) from exc
        except MeshNodeNotPrimary as exc:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="node_not_primary",
            ) from exc
        except MeshTimeoutError as exc:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="init_mesh_timeout",
                translation_placeholders={
                    "current_timeout": str(self.api.timeout),
                },
            ) from exc
        except MeshConnectionError as exc:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="init_connection_error",
                translation_placeholders={
                    "exc_msg": str(exc),
                    "primary_ip": self.api.connected_node,
                },
            ) from exc

    async def _async_update_data(self) -> DataUpdateCoordinatorData:
        """Refresh the mesh data.

        :returns: Updated data from the coordinator update.
        """

        # set when we're running for later comparison
        now: float = time.monotonic()
        _data: DataUpdateCoordinatorData = copy.copy(self.data)

        # region #-- establish the functions that need to run--#
        timers_running: list[CoordinatorTimers] = []
        coro_running: list = []
        for timer_type, timer_data in self._timers.items():
            last_success: float | None = timer_data.get("last_success")
            interval: float = timer_data.get("interval", 0)
            run_update: bool = (
                last_success is None or math.ceil(now - last_success) >= interval
            )
            if run_update:
                timer_data["is_running"] = True
                timers_running.append(timer_type)

                if timer_type == CoordinatorTimers.DEVICE_TRACKER:
                    coro_running.append(self._async_get_device_tracker_data())
                elif timer_type == CoordinatorTimers.MESH:
                    coro_running.append(self._async_get_mesh_data())
                else:
                    raise UpdateFailed(
                        f"unknown timer type: {timer_type} - cannot update data"
                    )

        _LOGGER.debug(
            "retrieving data for the multi use coordinator, %s",
            list(map(str, timers_running)),
        )
        # endregion

        # run the tasks
        res: list = await asyncio.gather(*coro_running)

        # region #-- set the results and appropriate attributes --#
        for idx, timer in enumerate(timers_running):
            setattr(_data, timer.value, res[idx])
            self._timers.get(timer, {}).update({"last_success": now})
        # endregion

        return _data

    async def async_force_refresh(
        self, timer: CoordinatorTimers | list[CoordinatorTimers]
    ) -> None:
        """Force a refresh of the coordinator data."""

        timers_to_force: list[CoordinatorTimers] = (
            timer if isinstance(timer, list) else [timer]
        )

        # region #-- cahce the timers --#
        timer_cache: dict[CoordinatorTimers, float | None] = {}
        for t in timers_to_force:
            timer_cache.update({t: self._timers.get(t, {}).get("last_success")})
            self._timers.get(t, {}).update({"last_success": None})
        # endregion

        # region #-- refresh --#
        await self.async_refresh()
        # endregion

        # region #-- restore the cache --#
        for t in timer_cache:
            self._timers.get(t, {}).update({"last_success": timer_cache.get(t)})
        # endregion


def get_mesh_device_for_config_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> DeviceEntry | None:
    """Retrieve the Mesh device from the registry.

    :param hass: Home Assistant root object.
    :param config_entry: Config entry to look-up the mesh for.
    :returns: `DeviceEntry` from the Home Assistant registry if one exists. `None` otherwise.
    """

    return get_registry_device(hass, config_entry.entry_id, config_entry.entry_id)


def remove_tracker_from_options(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry, tracker_id: str
) -> None:
    """Remove a missing tracker from the config entry options.

    :param hass: Home Assistant root object.
    :param config_entry: Config entry to remove the UI device from.
    :param tracker_id: ID of the tracker to remove.
    """
    options = copy.deepcopy(config_entry.options)
    trackers = options.get(CONF_DEVICE_TRACKERS, [])

    if tracker_id in trackers:
        trackers.remove(tracker_id)
        hass.config_entries.async_update_entry(config_entry, options=options)


def remove_ui_device_from_options(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry, ui_id: str
) -> None:
    """Remove a device from the config options if it no longer exists in the registry.

    :param hass: Home Assistant root object.
    :param config_entry: Config entry to remove the UI device from.
    :param ui_id: ID of the device to remove.
    """
    options = copy.deepcopy(config_entry.options)
    ui_list = options.get(CONF_UI_DEVICES, [])
    if ui_id in ui_list:
        ui_list.remove(ui_id)
        hass.config_entries.async_update_entry(config_entry, options=options)
