"""Update Coordinators."""

# region #-- imports --#
import asyncio
import copy
import logging
import math
from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify
from pyvelop.exceptions import (
    MeshConnectionError,
    MeshException,
    MeshInvalidCredentials,
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import DeviceEntity, NodeEntity

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_EVENTS_OPTIONS,
    CONF_UI_DEVICES,
    DEF_API_REQUEST_TIMEOUT,
    DEF_CHANNEL_SCAN_PROGRESS_INTERVAL_SECS,
    DEF_EVENTS_OPTIONS,
    DEF_REBOOT_BACKOFF,
    DEF_SPEEDTEST_PROGRESS_INTERVAL_SECS,
    DEF_UI_PLACEHOLDER_DEVICE_ID,
    DOMAIN,
    ISSUE_MISSING_UI_DEVICE,
    ChannelScanInfo,
    IntensiveTask,
    SpeedtestResults,
    SpeedtestStatus,
)
from .exceptions import CoordinatorMeshTimeout, GeneralException
from .types import EventSubTypes, LinksysVelopConfigEntry

# endregion


_LOGGER: logging.Logger = logging.getLogger(__name__)


class LinksyVelopBaseUpdateCoordinator(DataUpdateCoordinator):
    """"""

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
        """Iniitlaise."""

        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(seconds=update_interval_secs),
        )

        self._mesh: Mesh = self.config_entry.runtime_data.mesh

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        # region #-- carry out relevant checks --#
        # test the credentials for the mesh.
        # raise the appropriate error depending on what happens.
        # if all is well there's no need to do anything.
        try:
            valid_auth: bool = await self._mesh.async_test_credentials()
            if not valid_auth:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="failed_login",
                )
        except MeshTimeoutError as exc:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="init_mesh_timeout",
                translation_placeholders={
                    "current_timeout": str(self._mesh.timeout),
                },
            ) from exc
        except MeshConnectionError as exc:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="init_connection_error",
                translation_placeholders={
                    "exc_msg": str(exc),
                    "primary_ip": self._mesh.connected_node,
                },
            ) from exc
        # endregion


class LinksysVelopUpdateCoordinator(LinksyVelopBaseUpdateCoordinator):
    """Retrieve the data from the Velop mesh."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        *,
        config_entry: LinksysVelopConfigEntry,
        update_interval_secs: float,
    ) -> None:
        """Initialise."""

        super().__init__(
            hass,
            logger,
            name=name,
            config_entry=config_entry,
            update_interval_secs=update_interval_secs,
        )

        self._configured_events: list[str] = self.config_entry.options.get(
            CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
        )
        self._rebooting_skip_count: int = 0
        self._max_rebooting_skip_count: int = math.ceil(
            DEF_REBOOT_BACKOFF / update_interval_secs
        )

    async def _async_update_data(self) -> Mesh:
        """Refresh the mesh data."""

        current_devices: set[str] = set()
        current_nodes: set[str] = set()
        previous_devices: set[str] = set()
        previous_nodes: set[str] = set()

        try:
            # region #-- rebooting so just return the previous details --#
            if (
                self.config_entry.runtime_data.mesh_is_rebooting
                and self._rebooting_skip_count != self._max_rebooting_skip_count
            ):
                self._rebooting_skip_count += 1
                return self._mesh
            # endregion

            # region #-- reset the skip flag --#
            if self._rebooting_skip_count != 0:
                self._rebooting_skip_count = 0
            # endregion

            # region #-- set the previous details before getting mesh details --#
            previous_nodes = {
                node.serial for node in self._mesh.nodes if node.serial is not None
            }
            if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
                previous_devices = {
                    device.unique_id
                    for device in self._mesh.devices
                    if device.unique_id is not None
                }
            # endregion

            # get details from the mesh
            await self._mesh.async_gather_details()
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

        # region #-- signal that the mesh has rebooted --#
        if (
            self.config_entry.runtime_data.mesh_is_rebooting
            and self._rebooting_skip_count == 0
        ):
            self.config_entry.runtime_data.mesh_is_rebooting = False
            if EventSubTypes.MESH_REBOOTED.value in self.config_entry.options.get(
                CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
            ):
                async_dispatcher_send(
                    self.hass,
                    f"{DOMAIN}_{EventSubTypes.MESH_REBOOTED.value}",
                )
        # endregion

        # region #-- get the current details for comparison --#
        current_nodes = {
            node.serial for node in self._mesh.nodes if node.serial is not None
        }
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            current_devices = {
                device.unique_id
                for device in self._mesh.devices
                if device.unique_id is not None
            }
        # endregion

        # region #-- missing UI devices --#
        if len(self.config_entry.options.get(CONF_UI_DEVICES, [])) > 0:
            missing_ui_devices: set[str] = set(
                self.config_entry.options.get(CONF_UI_DEVICES, [])
            ).difference(current_devices)
            missing_ui_devices.discard(DEF_UI_PLACEHOLDER_DEVICE_ID)
            if missing_ui_devices:
                device_registry: DeviceRegistry = dr.async_get(self.hass)
                for ui_device in missing_ui_devices:
                    found_device: DeviceEntry | None = device_registry.async_get_device(
                        identifiers={(DOMAIN, ui_device)}
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
                                "device_name": str(
                                    found_device.name_by_user or found_device.name
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
        if stale_nodes := previous_nodes - current_nodes:
            device_registry: DeviceRegistry = dr.async_get(self.hass)
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

        # region #-- new device found --#
        if EventSubTypes.NEW_DEVICE_FOUND.value in self._configured_events:
            new_devices: set[str] = current_devices.difference(previous_devices)
            device_info: list[DeviceEntity] | DeviceEntity
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
        if (
            EventSubTypes.NEW_NODE_FOUND.value in self._configured_events
            and len(previous_nodes) > 0
        ):
            new_nodes: set[str] = current_nodes.difference(previous_nodes)
            if len(new_nodes) > 0:
                node_info: list[NodeEntity]
                for node in new_nodes:
                    if node_info := [
                        n for n in self._mesh.nodes if n.unique_id == node
                    ]:
                        async_dispatcher_send(
                            self.hass,
                            f"{DOMAIN}_{EventSubTypes.NEW_NODE_FOUND.value}",
                            node_info[0],
                        )
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
        # endregion

        return self._mesh


class UpdateCoordinatorChangeableInterval(LinksyVelopBaseUpdateCoordinator):
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


class LinksysVelopUpdateCoordinatorSpeedtest(UpdateCoordinatorChangeableInterval):
    """Retrieve the Speedtest data from the Velop mesh."""

    data: SpeedtestResults

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

    async def _async_update_data(self) -> SpeedtestResults:
        """Refresh the Speedtest data."""

        try:
            if self.config_entry.runtime_data.mesh_is_rebooting:
                return self.data

            api_calls: list = [
                self._mesh.async_get_speedtest_results(only_latest=True),
                self._mesh.async_get_speedtest_state(),
            ]
            responses = await asyncio.gather(*api_calls)
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

        result: dict[str, Any]
        result = responses[0][0] if len(responses[0]) else {}

        friendly_status: str | None = responses[1] if result else None
        slug_friendly_status: str = slugify(responses[1])
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

        if friendly_status in (
            None,
            SpeedtestStatus.FINISHED,
            SpeedtestStatus.UNKNOWN,
        ):
            self.update_interval = self.normal_update_interval
        else:
            self.update_interval = self.progress_update_interval

        return ret


class LinksysVelopUpdateCoordinatorChannelScan(UpdateCoordinatorChangeableInterval):
    """Retrieve the Channel Scan data from the Velop mesh."""

    data: ChannelScanInfo

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        *,
        config_entry: LinksysVelopConfigEntry,
        update_interval_secs: float,
        progress_update_interval_secs: float = DEF_CHANNEL_SCAN_PROGRESS_INTERVAL_SECS,
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

    async def _async_update_data(self) -> ChannelScanInfo:
        """Refresh the Speedtest data."""

        try:
            if self.config_entry.runtime_data.mesh_is_rebooting:
                return self.data

            api_calls: list = [
                self._mesh.async_get_channel_scan_info(),
            ]
            responses = await asyncio.gather(*api_calls)
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

        result: dict[str, Any] = responses[0]
        ret: ChannelScanInfo = ChannelScanInfo(
            connected_node=self._mesh.connected_node,
            is_running=result.get("isRunning", False),
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
        return ret
