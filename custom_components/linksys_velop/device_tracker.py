"""Device tracker entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Any, cast, override

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
)
from homeassistant.components.device_tracker import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.device_tracker import (
    ScannerEntity,
    ScannerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import AdapterInfo, DeviceEntity

from .const import (
    CONF_DEVICE_TRACKERS,
    DEF_CONSIDER_HOME,
)
from .coordinator import (
    CoordinatorTypes,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
    get_mesh_device_for_config_entry,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
)

# endregion

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinksysVelopDeviceTrackerEntityDescription(
    LinksysVelopEntityDescription, ScannerEntityDescription
):
    """Describes Velop device tracker entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create entities for device trackers."""

    adapter: list[AdapterInfo]
    device: DeviceEntity | None
    device_trackers: list[LinksysVelopDeviceTrackerCoordinatorEntity] = []
    connections: set[tuple[str, str]] = set()
    mesh: Mesh = config_entry.runtime_data.mesh
    for tracked_device in config_entry.options.get(CONF_DEVICE_TRACKERS, []):
        if (
            device := next(
                (d for d in mesh.devices if d.unique_id == tracked_device), None
            )
        ) is not None:
            device_trackers.append(
                LinksysVelopDeviceTrackerMultiUseEntity(
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorMultiUse,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.MESH
                        ),
                    ),
                    description=LinksysVelopDeviceTrackerEntityDescription(
                        name=device.name,
                        key="",
                        target_type=EntityType.MESH,
                    ),
                    entity_context=LinksysVelopEntityContext(
                        data={"velop": {"id": tracked_device}},
                        unique_id=config_entry.entry_id,
                    ),
                )
            )

            # region #-- add the connection details to the connection set --#
            #
            # these will be used to ensure the device tracker entities are displayed as part
            # of the Mesh device.
            if adapter := list(device.adapter_info):
                adi: AdapterInfo | None = next(iter(adapter), None)
                if adi is not None:
                    connections.add(
                        (
                            dr.CONNECTION_NETWORK_MAC,
                            dr.format_mac(adi.mac),
                        )
                    )
            # endregion

    # region #-- merge the connection information in to the Mesh device --#
    device_registry: DeviceRegistry = dr.async_get(hass)
    mesh_device: DeviceEntry | None = get_mesh_device_for_config_entry(
        hass, config_entry
    )
    if mesh_device is not None:
        device_registry.async_update_device(
            mesh_device.id, merge_connections=connections
        )
    # endregion

    async_add_entities(device_trackers)


class LinksysVelopDeviceTrackerEntity(ScannerEntity):
    """Base class representing a device tracker entity."""

    entity_description: LinksysVelopDeviceTrackerEntityDescription
    _entity_domain: str = ENTITY_DOMAIN


class LinksysVelopDeviceTrackerMultiUseEntity(
    LinksysVelopDeviceTrackerEntity, LinksysVelopMultiUseEntity
):
    """Representation of a device tracker."""

    _is_connected: bool | None = None
    _offline_first_seen: int | None = None

    def _process_device_update(self) -> None:
        """Establish device state or attribute changes."""

        device: DeviceEntity | None = self._get_target()
        if device is not None:
            if device.status != self._is_connected:
                if device.status:
                    _LOGGER.debug(self.log_formatter("%s: back online"), self.name)
                    self._is_connected = True
                else:
                    if device.results_time is not None:
                        if self._offline_first_seen is None:
                            # TODO: change this when pyvelop returns the results_time as int
                            self._offline_first_seen = int(device.results_time)
                            _LOGGER.debug(
                                self.log_formatter(
                                    "%s: waiting for consider_home period %s"
                                ),
                                self.name,
                                self.coordinator.config_entry.options.get(
                                    CONF_CONSIDER_HOME, DEF_CONSIDER_HOME
                                ),
                            )
                        else:
                            if int(
                                device.results_time
                            ) - self._offline_first_seen >= self.coordinator.config_entry.options.get(
                                CONF_CONSIDER_HOME, DEF_CONSIDER_HOME
                            ):
                                _LOGGER.debug(
                                    self.log_formatter(
                                        "%s: consider_home period expired"
                                    ),
                                    self.name,
                                )
                                self._is_connected = False
                                self._offline_first_seen = None
            else:
                if self._offline_first_seen is not None:
                    _LOGGER.debug(
                        self.log_formatter("%s: back online in consider_home period"),
                        self.name,
                    )
                    self._offline_first_seen = None

    @property
    @override
    def ip_address(self) -> str | None:

        ret: str | None = None

        device: DeviceEntity | None = self._get_target()
        if device is not None:
            adapter_info: list[AdapterInfo] | None = device.adapter_info
            ret = next(iter(adapter_info)).ip

        return ret

    @property
    @override
    def is_connected(self) -> bool | None:

        self._process_device_update()
        return self._is_connected

    @cached_property
    @override
    def mac_address(self) -> str | None:

        ret: str | None = None

        device: DeviceEntity | None = self._get_target()
        if device is not None:
            adapter_info: list[AdapterInfo] | None = device.adapter_info
            ret = next(iter(adapter_info)).mac

        return ret

    @property
    @override
    def unique_id(self) -> str | None:

        return (
            f"{self.entity_context.unique_id}::"
            f"{self._entity_domain.lower()}::"
            f"{str(self.entity_context.data.get("velop", {}).get("id"))}"
        )


type LinksysVelopDeviceTrackerCoordinatorEntity = LinksysVelopDeviceTrackerMultiUseEntity
