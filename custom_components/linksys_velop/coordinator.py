"""Update Coordinators."""

# region #-- imports --#
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
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh, SpeedtestResult, SpeedtestStatus
from pyvelop.mesh_entity import DeviceEntity, NodeEntity, NodeType

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_DEVICE_TRACKERS,
    CONF_EVENTS_OPTIONS,
    CONF_EVENTS_WAIT_IP,
    CONF_UI_DEVICES,
    CONF_UI_PLACEHOLDER_DEVICE_ID,
    DEF_API_REQUEST_TIMEOUT,
    DEF_CHANNEL_SCAN_PROGRESS_INTERVAL_SECS,
    DEF_EVENTS_OPTIONS,
    DEF_EVENTS_WAIT_IP,
    DEF_SPEEDTEST_PROGRESS_INTERVAL_SECS,
    DOMAIN,
    ISSUE_MISSING_DEVICE_TRACKER,
    ISSUE_MISSING_UI_DEVICE,
    ChannelScanInfo,
    DataCoordinatorFormattedData,
    EventSubTypes,
    IntensiveTask,
)
from .exceptions import (
    CoordinatorMeshTimeout,
    DeviceTrackerMeshTimeout,
    GeneralException,
    IntensiveTaskRunning,
)
from .helpers import get_mesh_parent_node
from .logger import Logger

# endregion


_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass
class LinksysVelopRuntimeData:
    """Runtime data for the ConfigEntry."""

    mesh: Mesh
    coordinators: dict[CoordinatorTypes, DataUpdateCoordinator[Any]] = field(
        default_factory=dict
    )
    intensive_running_tasks: list[str] = field(default_factory=list)
    mesh_is_rebooting: bool = False


type LinksysVelopConfigEntry = ConfigEntry[LinksysVelopRuntimeData]


class CoordinatorTimers(StrEnum):
    """The timer types available to a DataCoordinator."""

    DEVICE_TRACKER = auto()
    MESH = auto()
    SPEEDTEST = auto()


class CoordinatorTypes(StrEnum):
    """The type of coordinator."""

    CHANNEL_SCAN = "coordinator_channel_scan"
    DEVICE_TRACKER = "coordinator_device_tracker"
    MESH = "coordinator_mesh"
    SPEEDTEST = "coordinator_speedtest"


class DataItems(StrEnum):
    """The data items available to a DataCoordinator."""

    CHANNEL_SCAN = auto()
    DEVICE_TRACKER = auto()
    MESH = auto()
    SPEEDTEST = auto()


class LinksyVelopDataUpdateCoordinator(DataUpdateCoordinator):
    """Base class for the update coordinators."""

    config_entry: LinksysVelopConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        config_entry: LinksysVelopConfigEntry,
        name: str,
        update_interval_secs: float,
    ) -> None:
        """Initialise."""

        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(seconds=update_interval_secs),
        )

    async def _debounce(self) -> bool:
        """Return True if the request to the mesh should be delayed."""

        # region #-- intensive task running so back off --#
        if len(self.config_entry.runtime_data.intensive_running_tasks) > 0:
            exc: IntensiveTaskRunning = IntensiveTaskRunning(
                translation_domain=DOMAIN,
                translation_key="intensive_task",
                translation_placeholders={
                    "coordinator_name": self.__class__.__name__,
                    "tasks": ",".join(
                        self.config_entry.runtime_data.intensive_running_tasks
                    ),
                },
            )
            _LOGGER.warning(exc)
            return True
        # endregion

        # region #-- check if we're rebooting --#
        if self.config_entry.runtime_data.mesh_is_rebooting:
            return True
        # endregion

        return False


class LinksysVelopDataUpdateCoordinatorMultiUse(LinksyVelopDataUpdateCoordinator):
    """Retrieve the data from the Velop mesh."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
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
        for _, value in kwargs.items():
            update_intervals.add(value)

        base_update_interval_secs: float = min(update_intervals)

        super().__init__(
            hass,
            logger,
            name=name,
            config_entry=config_entry,
            update_interval_secs=base_update_interval_secs,
        )

        self.data: dict[str, Any] = {}
        self.data.update({CoordinatorTimers.MESH: config_entry.runtime_data.mesh})

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
                    except:
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

    async def _async_get_device_tracker_data(self) -> list[DeviceEntity]:
        """Get the device tracker information from the mesh."""

        if await self._debounce():
            return self.data.get(CoordinatorTimers.DEVICE_TRACKER, [])

        devices: list[DeviceEntity] = []
        try:
            tracked_devices: tuple[str] = self.config_entry.options.get(
                CONF_DEVICE_TRACKERS, []
            )
            devices = await self.config_entry.runtime_data.mesh.async_get_devices(
                tracked_devices,
                force_refresh=True,
            )
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
        except (MeshConnectionError, MeshTimeoutError) as err:
            exc_timeout: DeviceTrackerMeshTimeout = DeviceTrackerMeshTimeout(
                translation_domain=DOMAIN,
                translation_key="device_tracker_timeout",
            )
            _LOGGER.warning(exc_timeout)
            raise UpdateFailed(err) from err
        except MeshInvalidCredentials as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="failed_login",
            )
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

        return devices

    async def _async_get_mesh_data(self) -> Mesh:
        """Get all data from the mesh."""

        current_devices: set[str] = set()
        current_nodes_serials: set[str] = set()
        dr_ui_device: DeviceEntry | None = None
        previous_devices: set[str] = set()
        previous_nodes: list[NodeEntity] = []
        previous_nodes_serials: set[str] = set()
        device_registry: DeviceRegistry

        # region #-- debounce? --#
        if await self._debounce():
            return self.config_entry.runtime_data.mesh
        # endregion

        # region #-- set the previous details before getting mesh details --#
        previous_nodes = self.config_entry.runtime_data.mesh.nodes
        previous_nodes_serials = {
            node.serial.value
            for node in previous_nodes
            if node.serial.value is not None
        }
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            previous_devices = {
                device.unique_id.value
                for device in self.config_entry.runtime_data.mesh.devices
                if device.unique_id.value is not None
            }
        # endregion

        # region #-- get the details from the mesh --#
        try:
            await self.config_entry.runtime_data.mesh.async_gather_details()
        except (MeshConnectionError, MeshTimeoutError) as err:
            if not self.config_entry.runtime_data.mesh_is_rebooting:
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
        except MeshInvalidCredentials as err:
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
            for node in self.config_entry.runtime_data.mesh.nodes
            if node.serial.value is not None
        }
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            current_devices = {
                device.unique_id.value
                for device in self.config_entry.runtime_data.mesh.devices
                if device.unique_id.value is not None
            }
        # endregion

        # region #-- update node `device` attributes if we need to --#
        attr_to_check: set[str] = {"ip", "name", "parent_id"}
        device_registry = dr.async_get(self.hass)
        prev_node: NodeEntity
        cur_node: NodeEntity | None
        for prev_node in previous_nodes:
            if prev_node.serial.value is not None:
                if (
                    dr_node := device_registry.async_get_device(
                        identifiers={(DOMAIN, prev_node.serial.value)}
                    )
                ) is not None and (
                    cur_node := next(
                        (
                            n
                            for n in self.config_entry.runtime_data.mesh.nodes
                            if n.serial.value == prev_node.serial.value
                        ),
                        None,
                    )
                ) is not None:
                    attr_to_update: dict[str, Any] = {}
                    for attr in attr_to_check:
                        if attr == "ip":
                            # region #-- update the configuration_url --#
                            if cur_node.type == NodeType.SECONDARY:
                                cur_ip: str | None = next(
                                    filter(
                                        lambda adi: adi.primary,
                                        cur_node.adapter_info,
                                    ),
                                ).ip

                                prev_ip: str | None = next(
                                    filter(
                                        lambda adi: adi.primary,
                                        prev_node.adapter_info,
                                    ),
                                ).ip

                                if cur_ip != prev_ip:
                                    attr_to_update["configuration_url"] = (
                                        f"http://{cur_ip}/ca"
                                        if cur_ip is not None
                                        else None
                                    )
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
                                    cur_node, self.config_entry.runtime_data.mesh
                                )
                                if (
                                    parent_node is not None
                                    and parent_node.serial.value is not None
                                ):
                                    parent_dr_node: DeviceEntry | None = (
                                        device_registry.async_get_device(
                                            identifiers={
                                                (DOMAIN, parent_node.serial.value)
                                            }
                                        )
                                    )
                                    if (
                                        parent_dr_node is not None
                                        and dr_node.via_device_id != parent_dr_node.id
                                    ):
                                        attr_to_update["via_device_id"] = (
                                            parent_dr_node.id
                                        )
                            # endregion
                    if len(attr_to_update) > 0:
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
                dr_ui_device = device_registry.async_get_device(
                    identifiers={(DOMAIN, ui_device)}
                )
                cur_ui_device: DeviceEntity | None = next(
                    (
                        device
                        for device in self.config_entry.runtime_data.mesh.devices
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
                    dr_ui_device: DeviceEntry | None = device_registry.async_get_device(
                        identifiers={(DOMAIN, ui_device)}
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
                dr_device: DeviceEntry | None = device_registry.async_get_device(
                    identifiers={(DOMAIN, node_serial)}
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
                        (
                            n
                            for n in self.config_entry.runtime_data.mesh.nodes
                            if n.serial.value == node
                        ),
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
                    (
                        d
                        for d in self.config_entry.runtime_data.mesh.devices
                        if d.unique_id.value == device
                    ),
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

        return self.config_entry.runtime_data.mesh

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        # region #-- carry out relevant checks --#
        # test the credentials for the mesh.
        # raise the appropriate error depending on what happens.
        # if all is well there's no need to do anything.
        try:
            valid_auth: bool = (
                await self.config_entry.runtime_data.mesh.async_test_credentials()
            )
            if not valid_auth:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="failed_login",
                )

            await self.config_entry.runtime_data.mesh.async_initialise()
        except MeshTimeoutError as exc:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="init_mesh_timeout",
                translation_placeholders={
                    "current_timeout": str(self.config_entry.runtime_data.mesh.timeout),
                },
            ) from exc
        except MeshConnectionError as exc:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="init_connection_error",
                translation_placeholders={
                    "exc_msg": str(exc),
                    "primary_ip": self.config_entry.runtime_data.mesh.connected_node,
                },
            ) from exc
        # endregion

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh the mesh data."""

        # set when we're running for later comparison
        now: float = time.monotonic()
        _data: dict[str, Any] = copy.copy(self.data)

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
            _data.update({timer.value: res[idx]})
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


class UpdateCoordinatorChangeableInterval(LinksyVelopDataUpdateCoordinator):
    """DataUpdateCoordinator that allows for the interval being changed."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        *,
        config_entry: LinksysVelopConfigEntry,
        update_interval_secs: float,
        progress_update_interval_secs: float,
    ) -> None:
        """Initialise."""

        self.normal_update_interval: timedelta = timedelta(seconds=update_interval_secs)
        self.progress_update_interval: timedelta = timedelta(
            seconds=progress_update_interval_secs
        )

        super().__init__(
            hass,
            logger,
            name=name,
            config_entry=config_entry,
            update_interval_secs=update_interval_secs,
        )


class LinksysVelopDataUpdateCoordinatorSpeedtest(UpdateCoordinatorChangeableInterval):
    """Retrieve the Speedtest data from the Velop mesh."""

    data: SpeedtestResult | None

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        *,
        config_entry: LinksysVelopConfigEntry,
        update_interval_secs: float,
        progress_update_interval_secs: float = DEF_SPEEDTEST_PROGRESS_INTERVAL_SECS,
    ) -> None:
        """Initialise."""

        super().__init__(
            hass,
            logger,
            name,
            config_entry=config_entry,
            update_interval_secs=update_interval_secs,
            progress_update_interval_secs=progress_update_interval_secs,
        )

    async def _async_update_data(self) -> SpeedtestResult | None:
        """Refresh the Speedtest data."""

        _result: SpeedtestResult | list[SpeedtestResult] | None
        result: SpeedtestResult | None = None
        ret: SpeedtestResult | None
        try:
            if await self._debounce():
                return self.data

            _LOGGER.debug("retrieving data for the Speedtest coordinator")

            if self.update_interval == self.progress_update_interval:
                _result = (
                    await self.config_entry.runtime_data.mesh.async_get_speedtest_state()
                )
            else:
                _result = await self.config_entry.runtime_data.mesh.async_get_speedtest_results(
                    only_latest=True,
                )
        except (MeshConnectionError, MeshTimeoutError) as err:
            if not self.config_entry.runtime_data.mesh_is_rebooting:
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
        except MeshInvalidCredentials as err:
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

        if _result:
            result = _result[0] if isinstance(_result, list) else _result
            if result.friendly_status in (
                SpeedtestStatus.NOT_RUNNING,
                SpeedtestStatus.UNKNOWN,
            ):
                if self.update_interval == self.progress_update_interval:
                    self.update_interval = self.normal_update_interval
                    _result = await self.config_entry.runtime_data.mesh.async_get_speedtest_results(
                        only_latest=True,
                        only_completed=True,
                    )
                    result = (
                        _result[0] if isinstance(_result, list) and result else None
                    )
            else:
                if self.update_interval == self.normal_update_interval:
                    self.update_interval = self.progress_update_interval

        ret = result
        return ret


def get_mesh_device_for_config_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> DeviceEntry | None:
    """Retrieve the Mesh device from the registry."""
    device_registry: DeviceRegistry = dr.async_get(hass)
    found_mesh: DeviceEntry | None = device_registry.async_get_device(
        {(DOMAIN, config_entry.entry_id)}
    )
    return found_mesh
