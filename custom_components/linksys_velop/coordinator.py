"""Update Coordinators"""

# region #-- imports --#
import asyncio
import copy
import logging
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum, auto
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify
from pyvelop.device import Device
from pyvelop.exceptions import MeshNeedsGatherDetails, MeshTimeoutError
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_EVENTS_OPTIONS,
    CONF_UI_DEVICES,
    DEF_API_REQUEST_TIMEOUT,
    DEF_CHANNEL_SCAN_PROGRESS_INTERVAL_SECS,
    DEF_EVENTS_OPTIONS,
    DEF_SPEEDTEST_PROGRESS_INTERVAL_SECS,
    DEF_UI_PLACEHOLDER_DEVICE_ID,
    DOMAIN,
    ISSUE_MISSING_NODE,
    ISSUE_MISSING_UI_DEVICE,
    IntensiveTask,
)
from .exceptions import CoordinatorMeshTimeout, GeneralException
from .logger import Logger
from .types import EventSubTypes, LinksysVelopConfigEntry

# endregion


_LOGGER: logging.Logger = logging.getLogger(__name__)


class SpeedtestStatus(StrEnum):
    """"""

    CHECKING_DOWNLOAD_SPEED = auto()
    CHECKING_LATENCY = auto()
    CHECKING_UPLOAD_SPEED = auto()
    DETECTING_SERVER = auto()
    FINISHED = auto()
    UNKNOWN = auto()


@dataclass
class DataCoordinatorFormattedData:
    """"""

    connected_node: str


@dataclass
class ChannelScanInfo(DataCoordinatorFormattedData):
    """Representation of Channel Scan information."""

    is_running: bool
    selected_channels: dict[str, list[dict[str, int | str]]] | None = None


@dataclass
class SpeedtestResults(DataCoordinatorFormattedData):
    """Representation of Speedtest results."""

    download_bandwidth: int
    exit_code: str
    friendly_status: str
    latency: float
    result_id: int
    timestamp: str
    upload_bandwidth: int


class LinksysVelopUpdateCoordinator(DataUpdateCoordinator):
    """Retrieve the data from the Velop mesh."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        mesh: Mesh,
        name: str,
        *,
        update_interval_secs: float,
    ) -> None:
        """Initialise."""

        self.config_entry: LinksysVelopConfigEntry
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=timedelta(seconds=update_interval_secs),
        )

        self.log_formatter = Logger(self.config_entry.unique_id)
        self._mesh: Mesh = mesh

    async def _async_update_data(self):
        """Refresh the mesh data."""

        current_devices: list[str] = []
        previous_devices: list[str] = []
        previous_nodes: list[str] = []
        previous_nodes_details: list[Node] = []

        configured_events: list[str] = self.config_entry.options.get(
            CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
        )

        try:
            previous_nodes_details = list(self._mesh.nodes)
            if EventSubTypes.NEW_NODE_FOUND.value in configured_events:
                previous_nodes = [node.unique_id for node in self._mesh.nodes]
            if EventSubTypes.NEW_DEVICE_FOUND.value in configured_events:
                previous_devices = [device.unique_id for device in self._mesh.devices]
        except MeshNeedsGatherDetails:
            pass

        try:
            await self._mesh.async_gather_details()
        except MeshTimeoutError as err:
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
        except Exception as err:
            exc_general: GeneralException = GeneralException(
                translation_domain=DOMAIN,
                translation_key="general",
                translation_placeholders={
                    "exc_type": type(err),
                    "exc_msg": err,
                },
            )
            _LOGGER.warning(exc_general)
            raise UpdateFailed(err) from err
        else:
            # region #-- issue management --#
            # region #-- missing ui devices --#
            if len(self.config_entry.options.get(CONF_UI_DEVICES, [])) > 0:
                current_devices = [device.unique_id for device in self._mesh.devices]
                missing_ui_devices: set[str] = set(
                    self.config_entry.options.get(CONF_UI_DEVICES, [])
                ).difference(current_devices)
                missing_ui_devices.discard(DEF_UI_PLACEHOLDER_DEVICE_ID)
                device_registry: DeviceRegistry = dr.async_get(self.hass)
                for ui_device in missing_ui_devices:
                    found_device: DeviceEntry | None = device_registry.async_get_device(
                        {(DOMAIN, ui_device)}
                    )
                    if found_device is not None:
                        ir.async_create_issue(
                            self.hass,
                            DOMAIN,
                            f"{ISSUE_MISSING_UI_DEVICE}::{ui_device}",
                            data={
                                "config_entry": self.config_entry,
                                "device_id": ui_device,
                                "device_name": found_device.name_by_user
                                or found_device.name,
                            },
                            is_fixable=True,
                            is_persistent=False,
                            severity=IssueSeverity.WARNING,
                            translation_key=ISSUE_MISSING_UI_DEVICE,
                            translation_placeholders={
                                "device_name": found_device.name_by_user
                                or found_device.name
                            },
                        )
                    else:
                        new_options = copy.deepcopy(dict(**self.config_entry.options))
                        if ui_device in new_options.get(CONF_UI_DEVICES, []):
                            new_options.get(CONF_UI_DEVICES).remove(ui_device)
                            self.hass.config_entries.async_update_entry(
                                self.config_entry, options=new_options
                            )
            # endregion
            # region #-- missing nodes --#
            current_nodes: list[str] = [node.unique_id for node in self._mesh.nodes]
            removed_nodes: set[str] = set(previous_nodes).difference(set(current_nodes))
            device_registry: DeviceRegistry = dr.async_get(self.hass)
            for node in removed_nodes:
                node_info: list[Node]
                if node_info := [
                    n for n in previous_nodes_details if n.unique_id == node
                ]:
                    found_device: DeviceEntry | None = device_registry.async_get_device(
                        {(DOMAIN, node_info[0].serial)}
                    )
                    if found_device is not None:
                        ir.async_create_issue(
                            self.hass,
                            DOMAIN,
                            f"{ISSUE_MISSING_NODE}::{node_info[0].serial}",
                            data={
                                "config_entry": self.config_entry,
                                "device_id": node_info[0].serial,
                                "device_name": found_device.name_by_user
                                or found_device.name,
                            },
                            is_fixable=True,
                            is_persistent=False,
                            severity=IssueSeverity.WARNING,
                            translation_key=ISSUE_MISSING_NODE,
                            translation_placeholders={
                                "device_name": found_device.name_by_user
                                or found_device.name
                            },
                        )
            # endregion
            # endregion

            # region #-- event management --#
            # region #-- check for new devices --#
            if EventSubTypes.NEW_DEVICE_FOUND.value in configured_events:
                if len(current_devices) == 0:
                    current_devices = [
                        device.unique_id for device in self._mesh.devices
                    ]
                new_devices: set[str] = set(current_devices).difference(
                    set(previous_devices)
                )
                device_info: list[Device] | Device
                for device in new_devices:
                    if (
                        device_info := [
                            d for d in self._mesh.devices if d.unique_id == device
                        ]
                    ) != []:
                        device_info = device_info[0]
                        async_dispatcher_send(
                            self.hass,
                            f"{DOMAIN}_{EventSubTypes.NEW_DEVICE_FOUND.value}",
                            device_info,
                        )
            # endregion

            # region #-- check for new nodes --#
            if EventSubTypes.NEW_NODE_FOUND.value in configured_events:
                if len(previous_nodes) > 0:
                    current_nodes: list[str] = [
                        node.unique_id for node in self._mesh.nodes
                    ]
                    new_nodes: set[str] = set(current_nodes).difference(
                        set(previous_nodes)
                    )
                    node_info: list[Node]
                    for node in new_nodes:
                        if node_info := [
                            n for n in self._mesh.nodes if n.unique_id == node
                        ]:
                            async_dispatcher_send(
                                self.hass,
                                f"{DOMAIN}_{EventSubTypes.NEW_NODE_FOUND.value}",
                                node_info[0],
                            )
            # endregion
            # endregion

        return self._mesh


class UpdateCoordinatorChangeableInterval(DataUpdateCoordinator):
    """"""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        mesh: Mesh,
        name: str,
        update_interval_secs: float,
        progress_update_interval_secs: float,
    ) -> None:
        """Initialise."""

        self._mesh: Mesh = mesh
        self.normal_update_interval: timedelta = timedelta(seconds=update_interval_secs)
        self.progress_update_interval: timedelta = timedelta(
            seconds=progress_update_interval_secs
        )

        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=self.normal_update_interval,
        )


class LinksysVelopUpdateCoordinatorSpeedtest(UpdateCoordinatorChangeableInterval):
    """Retrieve the Speedtest data from the Velop mesh."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        mesh: Mesh,
        name: str,
        update_interval_secs: float,
        progress_update_interval_secs: float = DEF_SPEEDTEST_PROGRESS_INTERVAL_SECS,
    ) -> None:
        """Initialise."""

        super().__init__(
            hass,
            logger,
            mesh,
            name,
            update_interval_secs,
            progress_update_interval_secs,
        )

    async def _async_update_data(self):
        """Refresh the Speedtest data."""

        ret: SpeedtestResults | None = None
        api_calls: list = [
            self._mesh.async_get_speedtest_results(only_latest=True),
            self._mesh.async_get_speedtest_state(),
        ]
        try:
            responses = await asyncio.gather(*api_calls)
            result: dict[str, Any] = responses[0][0]
            slug_friendly_status: str = slugify(responses[1])
            friendly_status: str
            try:
                friendly_status = (
                    SpeedtestStatus.FINISHED
                    if slug_friendly_status == ""
                    else SpeedtestStatus(slug_friendly_status)
                )
            except ValueError:
                friendly_status = SpeedtestStatus.UNKNOWN

            ret = SpeedtestResults(
                connected_node=self._mesh.connected_node,
                friendly_status=friendly_status,
                **result,
            )

            if friendly_status not in (
                SpeedtestStatus.FINISHED,
                SpeedtestStatus.UNKNOWN,
            ):
                self.update_interval = self.progress_update_interval
            else:
                self.update_interval = self.normal_update_interval
        except MeshTimeoutError as err:
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
        except Exception as err:
            exc_general: GeneralException = GeneralException(
                translation_domain=DOMAIN,
                translation_key="general",
                translation_placeholders={
                    "exc_type": type(err),
                    "exc_msg": err,
                },
            )
            _LOGGER.warning(exc_general)
            raise UpdateFailed(err) from err

        return ret


class LinksysVelopUpdateCoordinatorChannelScan(UpdateCoordinatorChangeableInterval):
    """Retrieve the Channel Scan data from the Velop mesh."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        mesh: Mesh,
        name: str,
        update_interval_secs: float,
        progress_update_interval_secs: float = DEF_CHANNEL_SCAN_PROGRESS_INTERVAL_SECS,
    ) -> None:
        """Initialise."""

        super().__init__(
            hass,
            logger,
            mesh,
            name,
            update_interval_secs,
            progress_update_interval_secs,
        )

    async def _async_update_data(self):
        """Refresh the Speedtest data."""

        api_calls: list = [
            self._mesh.async_get_channel_scan_info(),
        ]
        try:
            responses = await asyncio.gather(*api_calls)
            result: dict[str, Any] = responses[0]
            ret: ChannelScanInfo = ChannelScanInfo(
                connected_node=self._mesh.connected_node,
                is_running=result.get("isRunning"),
            )
            if not ret.is_running:
                if (
                    IntensiveTask.CHANNEL_SCAN
                    in self.config_entry.runtime_data.intensive_running_tasks
                ):
                    self.config_entry.runtime_data.intensive_running_tasks.remove(
                        IntensiveTask.CHANNEL_SCAN
                    )
                self.update_interval = self.normal_update_interval
            else:
                self.update_interval = self.progress_update_interval
        except MeshTimeoutError as err:
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
        except Exception as err:
            exc_general: GeneralException = GeneralException(
                translation_domain=DOMAIN,
                translation_key="general",
                translation_placeholders={
                    "exc_type": type(err),
                    "exc_msg": err,
                },
            )
            _LOGGER.warning(exc_general)
            raise UpdateFailed(err) from err

        return ret
