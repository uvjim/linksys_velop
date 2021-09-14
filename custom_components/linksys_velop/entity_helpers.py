"""Base classes for managing entities in the integration"""

from typing import List, Union

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
)
from .data_update_coordinator import LinksysVelopDataUpdateCoordinator
from .pyvelop.mesh import Mesh
from .pyvelop.node import Node


class LinksysVelopDeviceTracker(ScannerEntity):
    """Representation of a device tracker"""

    _attribute: str
    _config: ConfigEntry

    def __init__(self, identity: str) -> None:
        """Constructor"""
        super().__init__()
        self._identity = identity

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device information for the mesh"""

        ret = DeviceInfo(**{
            "name": "Mesh",
            "manufacturer": "Linksys",
            "identifiers": {(DOMAIN, self._config.entry_id)},
        })
        return ret

    @property
    def is_connected(self) -> bool:
        """Returns True if connected, False otherwise"""

        return False

    @property
    def mac_address(self) -> Union[str, None]:
        """Returns the MAC address for the tracker"""

        return

    @property
    def name(self) -> str:
        """Returns the name of the tracker"""

        return f"{ENTITY_SLUG} Mesh: {self._attribute}"

    @property
    def should_poll(self) -> bool:
        """Do not poll for status"""

        return False

    @property
    def source_type(self) -> str:
        """Return the type as a router"""

        return SOURCE_TYPE_ROUTER

    @property
    def unique_id(self) -> str:
        """Return the unique ID for the tracker"""

        ret = f"{self._identity}::device_tracker::{slugify(self._attribute).lower()}"
        return ret


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


class LinksysVelopPolledBinarySensor(CoordinatorEntity, BinarySensorEntity):
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


class LinksysVelopPolledSensor(CoordinatorEntity, SensorEntity):
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


# noinspection Duplicates
class LinksysVelopNodePolledSensor(LinksysVelopPolledSensor):
    """Representation of a polled Sensor"""

    def _get_node(self) -> Union[Node, None]:
        """Return the node from the list of nodes in the mesh"""

        return [n for n in self._mesh.nodes if n.unique_id == self._identity][0]

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device information to that of the node"""

        node = self._get_node()
        ret = DeviceInfo(**{
            "name": node.name,
            "manufacturer": node.manufacturer,
            "sw_version": node.firmware.get("version", ""),
            "model": node.model,
            "identifiers": {(DOMAIN, node.serial)}
        })
        return ret

    @property
    def name(self) -> str:
        """Returns the name of the sensor"""

        node = self._get_node()
        return f"{ENTITY_SLUG} {node.name}: {self._attribute}"


# noinspection Duplicates
class LinksysVelopNodePolledBinarySensor(LinksysVelopPolledBinarySensor):
    """Representation of a polled binary sensor"""

    def _get_node(self) -> Union[Node, None]:
        """Return the node from the list of nodes in the mesh"""

        return [n for n in self._mesh.nodes if n.unique_id == self._identity][0]

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device information to that of the node"""

        node = self._get_node()
        ret = DeviceInfo(**{
            "name": node.name,
            "manufacturer": node.manufacturer,
            "sw_version": node.firmware.get("version", ""),
            "model": node.model,
            "identifiers": {(DOMAIN, node.serial)}
        })
        return ret

    @property
    def name(self) -> str:
        """Set the name of the binary sensor"""

        node = self._get_node()
        return f"{ENTITY_SLUG} {node.name}: {self._attribute}"


class LinksysVelopMeshBinarySensor(LinksysVelopBinarySensor):
    """Representation of an unpolled binary sensor"""

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device information to that of the mesh"""

        ret = DeviceInfo(**{
            "name": "Mesh",
            "manufacturer": "Linksys",
            "identifiers": {(DOMAIN, self._identity)},
        })
        return ret

    @property
    def name(self) -> str:
        """Returns the name of the binary sensor"""

        return f"{ENTITY_SLUG} Mesh: {self._attribute}"


# noinspection Duplicates
class LinksysVelopMeshPolledBinarySensor(LinksysVelopPolledBinarySensor):
    """Representation of a polled binary sensor"""

    # def _get_devices(self, status: bool) -> List:
    #     return [device for device in self._mesh.devices if device.status == status]

    @property
    def device_info(self) -> DeviceInfo:
        """Sets the device info to that of the mesh"""

        ret = DeviceInfo(**{
            "name": "Mesh",
            "manufacturer": "Linksys",
            "identifiers": {(DOMAIN, self._identity)},
        })
        return ret

    @property
    def name(self) -> str:
        """Returns the name of the binary sensor"""

        return f"{ENTITY_SLUG} Mesh: {self._attribute}"


# noinspection Duplicates
class LinksysVelopMeshPolledSensor(LinksysVelopPolledSensor):
    """Representation of a polled sensor"""

    def _get_devices(self, status: bool) -> List:
        """Get the devices that match the specified state

        :param status: True if looking for online devices, False otherwise
        :return: a list of devices matching the state
        """

        return [device for device in self._mesh.devices if device.status == status]

    @property
    def device_info(self) -> DeviceInfo:
        """Sets the device info to that of the mesh"""

        ret = DeviceInfo(**{
            "name": "Mesh",
            "manufacturer": "Linksys",
            "identifiers": {(DOMAIN, self._identity)},
        })
        return ret

    @property
    def name(self) -> str:
        """Returns the name of the sensor"""

        return f"{ENTITY_SLUG} Mesh: {self._attribute}"


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
