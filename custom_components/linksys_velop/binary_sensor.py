"""Binary sensors for the mesh, nodes and devices"""

# region #-- imports --#
# TODO: Fix up the try/except block when setting the minimum HASS version to 2021.12
# HASS 2021.12 introduces StrEnum for DEVICE_CLASS_* constants
try:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    DEVICE_CLASS_CONNECTIVITY = BinarySensorDeviceClass.CONNECTIVITY
    DEVICE_CLASS_UPDATE = BinarySensorDeviceClass.UPDATE
except ImportError:
    BinarySensorDeviceClass = None
    from homeassistant.components.binary_sensor import (
        DEVICE_CLASS_CONNECTIVITY,
        DEVICE_CLASS_UPDATE
    )

# TODO: Remove the try/except block when setting the minimum HASS version to 2021.12
try:
    from homeassistant.helpers.entity import EntityCategory
except ImportError:
    EntityCategory = None
    # TODO: Remove the try/except block when setting the minimum HASS version to 2021.11
    try:
        from homeassistant.const import (
            ENTITY_CATEGORY_CONFIG,
            ENTITY_CATEGORY_DIAGNOSTIC,
        )
    except ImportError:
        ENTITY_CATEGORY_CONFIG: str = "config"
        ENTITY_CATEGORY_DIAGNOSTIC: str = "diagnostic"

import asyncio
import dataclasses
import logging
from datetime import timedelta, datetime
from typing import (
    Any,
    Callable,
    List,
    Mapping,
    Optional,
    Union,
)

from homeassistant.components.binary_sensor import (
    DOMAIN as ENTITY_DOMAIN,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from pyvelop.mesh import Mesh
from pyvelop.node import Node

from . import (
    entity_cleanup,
    LinksysVelopMeshEntity,
    LinksysVelopNodeEntity,
)
from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- binary sensor entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the binary sensor description."""

    extra_attributes: Optional[Callable] = None
    state_value: Optional[Callable] = None


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the binary sensor description."""


@dataclasses.dataclass
class LinksysVelopBinarySensorDescription(
    OptionalLinksysVelopDescription,
    BinarySensorEntityDescription,
    RequiredLinksysVelopDescription
):
    """Describes binary sensor entity"""
# endregion


BINARY_SENSOR_DESCRIPTIONS: tuple[LinksysVelopBinarySensorDescription, ...] = (
    LinksysVelopBinarySensorDescription(
        device_class=DEVICE_CLASS_CONNECTIVITY,
        extra_attributes=lambda m: {"ip": m.wan_ip, "dns": m.wan_dns or None, "mac": m.wan_mac},
        key="wan_status",
        name="WAN Status",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the binary sensors from a config entry"""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data

    binary_sensors: List[Union[
        LinksysVelopMeshBinarySensor,
        LinksysVelopNodeBinarySensor,
        LinksysVelopMeshSpeedtestStatusBinarySensor
    ]] = [
        LinksysVelopMeshBinarySensor(
            config_entry=config_entry,
            coordinator=coordinator,
            description=binary_sensor_description,
        )
        for binary_sensor_description in BINARY_SENSOR_DESCRIPTIONS
    ]

    binary_sensors.append(
        LinksysVelopMeshSpeedtestStatusBinarySensor(
            config_entry=config_entry,
            coordinator=coordinator,
            description=LinksysVelopBinarySensorDescription(
                key="",
                name="Speedtest Status",
            )
        )
    )

    for node in mesh.nodes:
        binary_sensors.extend([
            LinksysVelopNodeBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopBinarySensorDescription(
                    device_class=DEVICE_CLASS_CONNECTIVITY,
                    extra_attributes=lambda n: n.connected_adapters[0] if n.connected_adapters else {},
                    key="status",
                    name="Status",
                )
            ),
            LinksysVelopNodeBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopBinarySensorDescription(
                    device_class=DEVICE_CLASS_UPDATE,
                    key="update_available",
                    name="Update Available",
                    state_value=lambda n: n.firmware.get("version") != n.firmware.get("latest_version")
                )
            ),
        ])

    async_add_entities(binary_sensors)

    binary_sensors_to_remove: List = [
        LinksysVelopMeshBinarySensor(
            config_entry=config_entry,
            coordinator=coordinator,
            description=LinksysVelopBinarySensorDescription(
                key="",
                name="Check for Updates Status",
            )
        )
    ]
    if binary_sensors_to_remove:
        entity_cleanup(config_entry=config_entry, entities=binary_sensors_to_remove, hass=hass)


class LinksysVelopMeshBinarySensor(LinksysVelopMeshEntity, BinarySensorEntity):
    """Representation of a binary sensor for the mesh"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopBinarySensorDescription
    ) -> None:
        """Constructor"""

        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC if EntityCategory is None else EntityCategory.DIAGNOSTIC

        self.entity_description: LinksysVelopBinarySensorDescription = description

        self._attr_name = f"{ENTITY_SLUG} Mesh: {self.entity_description.name}"
        self._attr_unique_id = f"{config_entry.entry_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Additional attributes for the binary sensor"""

        if (
            self.entity_description.extra_attributes
            and isinstance(self.entity_description.extra_attributes, Callable)
        ):
            return self.entity_description.extra_attributes(self._mesh)

    @property
    def is_on(self) -> Optional[bool]:
        """Get the state of the binary sensor"""

        if self.entity_description.state_value:
            return self.entity_description.state_value(self._mesh)
        else:
            return getattr(self._mesh, self.entity_description.key, None)


class LinksysVelopNodeBinarySensor(LinksysVelopNodeEntity, BinarySensorEntity):
    """Representaion of a binary sensor related to a node"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: LinksysVelopBinarySensorDescription
    ) -> None:
        """Constructor"""

        self._node_id: str = node.unique_id
        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC if EntityCategory is None else EntityCategory.DIAGNOSTIC

        self.entity_description: LinksysVelopBinarySensorDescription = description

        self._attr_name = f"{ENTITY_SLUG} {self._node.name}: {self.entity_description.name}"
        self._attr_unique_id = f"{self._node.unique_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Additional attributes for the binary sensor"""

        if (
            self.entity_description.extra_attributes
            and isinstance(self.entity_description.extra_attributes, Callable)
        ):
            return self.entity_description.extra_attributes(self._node)

    @property
    def is_on(self) -> Optional[bool]:
        """Get the state of the binary sensor"""

        if self.entity_description.state_value:
            return self.entity_description.state_value(self._node)
        else:
            return getattr(self._node, self.entity_description.key, None)


class LinksysVelopMeshSpeedtestStatusBinarySensor(LinksysVelopMeshBinarySensor):
    """Representation of the Speedtest status binary sensor"""

    _status_text: str = ""
    _status_update_interval: int = 1
    _remove_time_interval: Optional[Callable] = None

    async def _async_get_speedtest_state(self, _: Union[datetime, None] = None):
        """Update the state of the binary sensor

        Triggers a time interval to ensure that data is checked for more regularly when the state
        is on.
        """

        self._status_text = await self._mesh.async_get_speedtest_state()
        if self._status_text:
            if not self._remove_time_interval:
                self._remove_time_interval = async_track_time_interval(
                    self.hass,
                    self._async_get_speedtest_state,
                    timedelta(seconds=self._status_update_interval)
                )
        else:
            if self._remove_time_interval:
                self._remove_time_interval()
                self._remove_time_interval = None
                async_dispatcher_send(self.hass, SIGNAL_UPDATE_SPEEDTEST_RESULTS)

        self.async_schedule_update_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Update the speedtest status information when the coordinator updates"""

        asyncio.run_coroutine_threadsafe(coro=self._async_get_speedtest_state(), loop=self.hass.loop)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Do stuff when entity is added to registry"""

        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_SPEEDTEST_STATUS,
                target=self._async_get_speedtest_state,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Tidy up when removed"""

        if self._remove_time_interval:
            self._remove_time_interval()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set the current stage of the test as an attribute"""

        return {
            "status": self._status_text
        }

    @property
    def is_on(self) -> bool:
        """Return True if the mesh is currently running a Speedtest, False otherwise"""

        return self._status_text != ""
