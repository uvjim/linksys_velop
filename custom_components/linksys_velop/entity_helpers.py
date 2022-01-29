"""Base classes for managing entities in the integration"""

from typing import List, Union, Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
)
from .data_update_coordinator import LinksysVelopDataUpdateCoordinator
from pyvelop.mesh import Mesh
from pyvelop.node import Node
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR


class LinksysVelopMeshEntity(Entity):
    """Represents an entity belonging to the mesh"""

    _attribute: str
    _identity: str
    _mesh: Mesh

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device information to that of the mesh"""

        # noinspection HttpUrlsUsage
        ret = DeviceInfo(**{
            "configuration_url": f"http://{self._mesh.connected_node}",
            "identifiers": {(DOMAIN, self._identity)},
            "manufacturer": PYVELOP_AUTHOR,
            "model": f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            "name": "Mesh",
            "sw_version": "",
        })
        return ret

    @property
    def name(self) -> str:
        """Returns the name of the entity"""

        return f"{ENTITY_SLUG} Mesh: {self._attribute}"


class LinksysVelopNodeEntity(Entity):
    """"""

    _attribute: str
    _identity: str
    _mesh: Mesh

    def _get_node(self) -> Union[Node, None]:
        """Return the node from the list of nodes in the mesh"""
        ret = None
        node = [n for n in self._mesh.nodes if n.unique_id == self._identity]
        if node:
            ret = node[0]

        return ret

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device information to that of the node"""

        node = self._get_node()
        ret = DeviceInfo(**{
            "hw_version": node.hardware_version,
            "identifiers": {(DOMAIN, node.serial)},
            "model": node.model,
            "name": node.name,
            "manufacturer": node.manufacturer,
            "sw_version": node.firmware.get("version", ""),
        })
        return ret

    @property
    def name(self) -> str:
        """Returns the name of the sensor"""

        node = self._get_node()
        return f"{ENTITY_SLUG} {node.name}: {self._attribute}"


class LinksysVelopDeviceTracker(ScannerEntity, LinksysVelopMeshEntity):
    """Representation of a device tracker"""

    _attribute: str
    _config: ConfigEntry

    def __init__(self, identity: str) -> None:
        """Constructor"""
        super().__init__()
        self._identity = identity

    @property
    def is_connected(self) -> bool:
        """Returns True if connected, False otherwise"""

        return False

    @property
    def mac_address(self) -> Union[str, None]:
        """Returns the MAC address for the tracker"""

        return

    @property
    def should_poll(self) -> bool:
        """Do not poll for status"""

        return False

    @property
    def source_type(self) -> str:
        """Return the type as a router"""

        return SOURCE_TYPE_ROUTER


class LinksysVelopBinarySensor(BinarySensorEntity):
    """Representation of an unpolled binary sensor"""

    _attribute: str

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity: str = identity

    @property
    def should_poll(self) -> bool:
        """Do not poll for status"""

        return False

    @property
    def unique_id(self) -> str:
        """Returns the unique ID for the binary sensor"""

        ret = f"{self._identity}::binary_sensor::{slugify(self._attribute).lower()}"
        return ret


# noinspection PyAbstractClass
class LinksysVelopMeshSwitch(LinksysVelopMeshEntity, SwitchEntity):
    """Representation of a polled Switch"""

    _attribute: str
    coordinator: LinksysVelopDataUpdateCoordinator

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        super().__init__()
        self._mesh: Mesh = coordinator.data
        self._identity = identity

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch"""

        return

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch"""

        return

    @property
    def is_on(self) -> bool:
        """"""

        return False

    @property
    def should_poll(self) -> bool:
        """True if this is a polling entity, False otherwise"""

        return False

    @property
    def unique_id(self) -> str:
        """Returns the unique ID of the switch"""

        ret = f"{self._identity}::switch::{slugify(self._attribute).lower()}"
        return ret


class LinksysVelopPolledBinarySensor(CoordinatorEntity, LinksysVelopNodeEntity, BinarySensorEntity):
    """Representation of a polled Binary Sensor"""

    _attribute: str
    coordinator: LinksysVelopDataUpdateCoordinator

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        super().__init__(coordinator)
        self._mesh: Mesh = coordinator.data
        self._identity = identity

    @property
    def unique_id(self) -> str:
        """Returns the unique ID for the binary sensor"""

        ret = f"{self._identity}::binary_sensor::{slugify(self._attribute).lower()}"
        return ret


class LinksysVelopPolledSensor(CoordinatorEntity, LinksysVelopNodeEntity, SensorEntity):
    """Representation of a polled Sensor"""

    _attribute: str
    coordinator: LinksysVelopDataUpdateCoordinator

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        super().__init__(coordinator)
        self._mesh: Mesh = coordinator.data
        self._identity = identity

    @property
    def unique_id(self) -> str:
        """Returns the unique ID of the sensor"""

        ret = f"{self._identity}::sensor::{slugify(self._attribute).lower()}"
        return ret


class LinksysVelopNodePolledSensor(LinksysVelopPolledSensor):
    """Representation of a polled Sensor"""


class LinksysVelopNodePolledBinarySensor(LinksysVelopPolledBinarySensor):
    """Representation of a polled binary sensor"""


class LinksysVelopMeshBinarySensor(LinksysVelopMeshEntity, LinksysVelopBinarySensor):
    """Representation of an unpolled binary sensor"""


class LinksysVelopMeshPolledBinarySensor(LinksysVelopMeshEntity, LinksysVelopPolledBinarySensor):
    """Representation of a polled binary sensor"""


class LinksysVelopMeshPolledSensor(LinksysVelopMeshEntity, LinksysVelopPolledSensor):
    """Representation of a polled sensor"""

    def _get_devices(self, status: bool) -> List:
        """Get the devices that match the specified state

        :param status: True if looking for online devices, False otherwise
        :return: a list of devices matching the state
        """

        return [device for device in self._mesh.devices if device.status == status]


def entity_setup(
    hass: HomeAssistant,
    entity_classes: List,
    async_add_entities: AddEntitiesCallback,
    config: ConfigEntry
) -> None:
    """Set up the given entities


    :param hass: HomeAssistant object
    :param entity_classes: list of entity classes that should be created
    :param async_add_entities: callback
    :param config: configuration entry used to create the entities
    :return: None
    """

    coordinator: LinksysVelopDataUpdateCoordinator = hass.data[DOMAIN][config.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    entities = []

    for cls in entity_classes:
        if cls.__name__.startswith("LinksysVelopMesh"):
            entities.append(
                cls(
                    coordinator=coordinator,
                    identity=config.entry_id,
                )
            )
        else:
            for node in mesh.nodes:
                entities.append(
                    cls(
                        coordinator=coordinator,
                        identity=node.unique_id,
                    )
                )

    async_add_entities(entities)
