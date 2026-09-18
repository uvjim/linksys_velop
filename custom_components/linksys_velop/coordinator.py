"""Update Coordinators."""

# region #-- imports --#
from __future__ import annotations

import asyncio
import copy
import logging
import math
import time
from collections.abc import Callable
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
from pyvelop.mesh_entity import DeviceEntity, NodeAdapterInfo, NodeEntity, NodeType

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
    CoordinatorMeshTimeout,
    DeviceTrackerMeshTimeout,
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

    async def _delay_run(self) -> bool:
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

    def add_listener_for_timer_type(
        self, timer_type: CoordinatorTimers, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Add a listener for a particular timer type."""

        self._timers.get(timer_type, {}).get("listeners", []).append(listener)

        def _unsub() -> None:
            if listener in self._timers.get(timer_type, {}).get("listeners", []):
                self._timers.get(timer_type, {}).get("listeners", []).remove(listener)

        return _unsub

    async def _async_get_device_tracker_data(self) -> tuple[DeviceEntity, ...]:
        """Get the device tracker information from the mesh."""

        if await self._delay_run():
            return self.data.device_tracker

        devices: tuple[DeviceEntity, ...] = ()
        try:
            tracked_devices: tuple[str] = self.config_entry.options.get(
                CONF_DEVICE_TRACKERS, []
            )
            devices = await self.api.async_get_devices(tracked_devices)
        except MeshDeviceNotFoundResponse as err:
            for tracker_missing in err.devices:
                entity_registry: er.EntityRegistry = er.async_get(self.hass)
                config_entities: list[er.RegistryEntry] = (
                    er.async_entries_for_config_entry(
                        entity_registry, self.config_entry.entry_id
                    )
                )
                tracker_entity: er.RegistryEntry | None
                if (
                    tracker_entity := next(
                        (
                            e
                            for e in config_entities
                            if e.unique_id
                            == f"{self.config_entry.entry_id}::{Platform.DEVICE_TRACKER}::{tracker_missing}"
                        ),
                        None,
                    )
                ) is not None:
                    # region #-- raise an issue --#
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        ISSUE_MISSING_DEVICE_TRACKER,
                        data={
                            "config_entry": self.config_entry.entry_id,
                            "device_id": tracker_entity.entity_id,
                            "device_name": tracker_entity.name
                            or tracker_entity.original_name,
                            "velop_id": tracker_missing,
                        },
                        is_fixable=True,
                        is_persistent=False,
                        severity=IssueSeverity.ERROR,
                        translation_key=ISSUE_MISSING_DEVICE_TRACKER,
                        translation_placeholders={
                            "device_name": tracker_entity.name
                            or tracker_entity.original_name
                            or ""
                        },
                    )
                    # endregion
                else:
                    # region #-- cleanup the config entry --#
                    new_options = copy.deepcopy(dict(self.config_entry.options))
                    if tracker_missing in new_options.get(CONF_DEVICE_TRACKERS, []):
                        new_options.get(CONF_DEVICE_TRACKERS, []).remove(
                            tracker_missing
                        )
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            options=new_options,
                        )
                    # endregion
        except (MeshConnectionError, MeshTimeoutError) as exc:
            exc_timeout: DeviceTrackerMeshTimeout = DeviceTrackerMeshTimeout(
                translation_domain=DOMAIN,
                translation_key="device_tracker_timeout",
            )
            _LOGGER.warning(exc_timeout)
            raise UpdateFailed(exc) from exc
        except MeshInvalidCredentials:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="failed_login",
            )
        except Exception as exc:
            exc_general: GeneralException = GeneralException(
                translation_domain=DOMAIN,
                translation_key="general",
                translation_placeholders={
                    "exc_type": type(exc).__name__,
                    "exc_msg": str(exc),
                },
            )
            _LOGGER.warning(exc_general)
            raise UpdateFailed(exc) from exc

        return devices

    async def _async_get_mesh_data(self) -> MeshSnapshot | None:
        """Get all data from the mesh."""

        current_devices: set[str] = set()
        current_nodes_serials: set[str] = set()
        dr_ui_device: DeviceEntry | None = None
        previous_devices: set[str] = set()
        previous_nodes: tuple[NodeEntity, ...] = ()
        previous_nodes_serials: set[str] = set()
        device_registry: DeviceRegistry

        # region #-- should we run? --#
        if await self._delay_run():
            return self.data.mesh
        # endregion

        # region #-- set the previous details before getting mesh details --#
        if isinstance(self.data.mesh, MeshSnapshot):
            previous_nodes = self.data.mesh.nodes
            previous_nodes_serials = {
                node.serial.value
                for node in previous_nodes
                if node.serial.value is not None
            }
            if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
                previous_devices = {
                    device.unique_id.value
                    for device in self.data.mesh.devices
                    if device.unique_id.value is not None
                }
        # endregion

        # region #-- get the details from the mesh --#
        try:
            mesh_data = await self.api.async_refresh()
        except (MeshConnectionError, MeshTimeoutError) as err:
            exc_mesh_timeout: CoordinatorMeshTimeout = CoordinatorMeshTimeout(
                translation_domain=DOMAIN,
                translation_key="coordinator_mesh_timeout",
                translation_placeholders={
                    "current_timeout": self.config_entry.options.get(
                        CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
                    )
                },
            )
            _LOGGER.warning(exc_mesh_timeout)
            raise UpdateFailed(err) from err
        except MeshInvalidCredentials:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="failed_login",
            )
        except MeshException as err:
            raise UpdateFailed(type(err).__name__) from err
        except Exception as err:
            exc_general: GeneralException = GeneralException(
                translation_domain=DOMAIN,
                translation_key="general",
                translation_placeholders={
                    "exc_type": type(err).__name__,
                    "exc_msg": str(err),
                },
            )
            _LOGGER.warning(exc_general)
            raise UpdateFailed(err) from err
        # endregion

        # region #-- get the current details for comparison --#
        current_nodes_serials = {
            node.serial.value
            for node in mesh_data.nodes
            if node.serial.value is not None
        }
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            current_devices = {
                device.unique_id.value
                for device in mesh_data.devices
                if device.unique_id.value is not None
            }
        # endregion

        # region #-- update node `device` attributes if we need to --#
        attr_to_check: set[str] = {"ip", "name", "parent_id"}
        device_registry = dr.async_get(self.hass)
        prev_node: NodeEntity
        cur_node: NodeEntity | None
        for prev_node in previous_nodes:
            serial = prev_node.serial.value

            if serial is None:
                continue

            dr_node: DeviceEntry | None = get_registry_device(
                self.hass, serial, self.config_entry.entry_id
            )
            if dr_node is None:
                continue

            cur_node = next(
                (node for node in mesh_data.nodes if node.serial.value == serial),
                None,
            )
            if cur_node is None:
                continue

            attr_to_update: dict[str, Any] = {}
            for attr in attr_to_check:
                if attr == "ip":
                    # region #-- update the configuration_url --#
                    cur_ip: str | None = None
                    prev_ip: str | None = None
                    if cur_node.type.value == NodeType.SECONDARY:
                        cur_adi: NodeAdapterInfo | None = next(
                            (adi for adi in cur_node.adapter_info if adi.primary),
                            None,
                        )
                        if cur_adi is not None:
                            cur_ip = cur_adi.ip

                        prev_adi: NodeAdapterInfo | None = next(
                            (adi for adi in prev_node.adapter_info if adi.primary),
                            None,
                        )
                        if prev_adi is not None:
                            prev_ip = prev_adi.ip

                        if cur_ip is not None and cur_ip != prev_ip:
                            attr_to_update["configuration_url"] = f"http://{cur_ip}/ca"
                    # endregion
                elif attr == "name":
                    # region #-- update the name --#
                    # this doesn't change the visible name in Home Assistant if that was set by the user.
                    if cur_node.name.value != prev_node.name.value:
                        attr_to_update["name"] = cur_node.name.value
                    # endregion
                elif attr == "parent_id":
                    # region #-- update the via_device --#
                    # this reflects the parent/child relationship on the mesh and only affects secondary nodes.
                    if cur_node.type.value == NodeType.SECONDARY:
                        parent_node: NodeEntity | None = get_mesh_parent_node(
                            cur_node, mesh_data
                        )
                        if (
                            parent_node is not None
                            and parent_node.serial.value is not None
                        ):
                            parent_dr_node: DeviceEntry | None = get_registry_device(
                                self.hass,
                                parent_node.serial.value,
                                self.config_entry.entry_id,
                            )
                            if (
                                parent_dr_node is not None
                                and dr_node.via_device_id != parent_dr_node.id
                            ):
                                attr_to_update["via_device_id"] = parent_dr_node.id
                    # endregion

            if attr_to_update:
                _LOGGER.debug(
                    "updating the following attributes for %s: %s",
                    prev_node.name,
                    attr_to_update,
                )
                device_registry.async_update_device(
                    dr_node.id,
                    **attr_to_update,
                )
        # endregion

        # region #-- update UI device names if we need to --#
        for ui_device in self.config_entry.options.get(CONF_UI_DEVICES, []):
            if ui_device != self.config_entry.data.get(CONF_UI_PLACEHOLDER_DEVICE_ID):
                dr_ui_device: DeviceEntry | None = get_registry_device(
                    self.hass,
                    ui_device,
                    self.config_entry.entry_id,
                )
                cur_ui_device: DeviceEntity | None = next(
                    (
                        device
                        for device in mesh_data.devices
                        if device.unique_id.value == ui_device
                    ),
                    None,
                )
                if (
                    cur_ui_device is not None
                    and dr_ui_device is not None
                    and cur_ui_device.name.value != dr_ui_device.name
                ):
                    device_registry.async_update_device(
                        dr_ui_device.id,
                        name=cur_ui_device.name.value,
                    )
        # endregion

        # region #-- missing UI devices --#
        if len(self.config_entry.options.get(CONF_UI_DEVICES, [])) > 0:
            missing_ui_devices: set[str] = set(
                self.config_entry.options.get(CONF_UI_DEVICES, [])
            ).difference(current_devices)
            missing_ui_devices.discard(
                self.config_entry.data.get(CONF_UI_PLACEHOLDER_DEVICE_ID)
            )
            if missing_ui_devices:
                for ui_device in missing_ui_devices:
                    dr_ui_device: DeviceEntry | None = get_registry_device(
                        self.hass,
                        ui_device,
                        self.config_entry.entry_id,
                    )
                    if dr_ui_device is not None:
                        ir.async_create_issue(
                            self.hass,
                            DOMAIN,
                            f"{ISSUE_MISSING_UI_DEVICE}::{ui_device}",
                            data={
                                "config_entry": self.config_entry.entry_id,
                                "device_name": dr_ui_device.name_by_user
                                or dr_ui_device.name,
                                "velop_id": ui_device,
                            },
                            is_fixable=True,
                            is_persistent=False,
                            severity=IssueSeverity.WARNING,
                            translation_key=ISSUE_MISSING_UI_DEVICE,
                            translation_placeholders={
                                "device_name": str(
                                    dr_ui_device.name_by_user or dr_ui_device.name
                                )
                            },
                        )
                    else:  # device not found in the registry so just remove it
                        new_options = copy.deepcopy(dict(**self.config_entry.options))
                        if ui_device in new_options.get(CONF_UI_DEVICES, []):
                            new_options.get(CONF_UI_DEVICES, {}).remove(ui_device)
                            self.hass.config_entries.async_update_entry(
                                self.config_entry, options=new_options
                            )
        # endregion

        # region #-- missing nodes --#
        if stale_nodes := previous_nodes_serials - current_nodes_serials:
            for node_serial in stale_nodes:
                dr_device: DeviceEntry | None = get_registry_device(
                    self.hass, node_serial, self.config_entry.entry_id
                )
                if dr_device is not None:
                    device_registry.async_update_device(
                        device_id=dr_device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
        # endregion

        # region #-- check for new nodes --#
        if EventSubTypes.NEW_NODE_FOUND.value in self._configured_events:
            new_nodes_serials: set[str] = current_nodes_serials.difference(
                previous_nodes_serials
            )
            node_info: NodeEntity | None
            for node in new_nodes_serials:
                if (
                    node_info := next(
                        (n for n in mesh_data.nodes if n.serial.value == node),
                        None,
                    )
                ) is not None:
                    async_dispatcher_send(
                        self.hass,
                        f"{DOMAIN}_{EventSubTypes.NEW_NODE_FOUND.value}",
                        node_info,
                    )
        # endregion

        # region #-- new device found --#
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            new_devices: set[str] = current_devices.difference(previous_devices)
            all_new_devices: set[str] = new_devices.union(self._waiting_for_ip)
            device_info: DeviceEntity | None
            for device in all_new_devices:
                if device_info := next(
                    (d for d in mesh_data.devices if d.unique_id.value == device),
                    None,
                ):
                    dev_ip = next(
                        (
                            adi
                            for adi in device_info.adapter_info
                            if adi.ip is not None or adi.ipv6 is not None
                        ),
                        None,
                    )
                    if (
                        self.config_entry.options.get(
                            CONF_EVENTS_WAIT_IP, DEF_EVENTS_WAIT_IP
                        )
                        and dev_ip is None
                    ):
                        self._waiting_for_ip.add(device)
                    else:
                        self._waiting_for_ip.discard(device)
                        async_dispatcher_send(
                            self.hass,
                            f"{DOMAIN}_{EventSubTypes.NEW_DEVICE_FOUND.value}",
                            device_info,
                        )
        # endregion

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
        """Refresh the mesh data."""

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
    """Retrieve the Mesh device from the registry."""

    return get_registry_device(hass, config_entry.entry_id, config_entry.entry_id)
