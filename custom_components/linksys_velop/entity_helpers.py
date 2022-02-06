"""Base classes for managing entities in the integration"""
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
        ENTITY_CATEGORY_CONFIG: str = ""
        ENTITY_CATEGORY_DIAGNOSTIC: str = ""

# TODO: Remove the try/except block when setting the minimum HASS version to 2021.12
try:
    from homeassistant.components.button import ButtonEntity
except ImportError:
    class ButtonEntity:
        """Dummy Button Entity"""

import logging
from abc import ABC
from typing import List, Union

import homeassistant.helpers.entity_registry as er
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.device import Device
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
)
from .data_update_coordinator import LinksysVelopDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class LinksysVelopConfigurationEntity(Entity):

    @property
    def entity_category(self) -> Union[EntityCategory, str, None]:
        if EntityCategory is not None:
            return EntityCategory.CONFIG
        else:
            return ENTITY_CATEGORY_CONFIG


class LinksysVelopDiagnosticEntity(Entity):

    @property
    def entity_category(self) -> Union[EntityCategory, str, None]:
        if EntityCategory is not None:
            return EntityCategory.DIAGNOSTIC
        else:
            return ENTITY_CATEGORY_DIAGNOSTIC


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
    _node: Node

    def _get_node(self):
        node = [n for n in self._mesh.nodes if n.unique_id == self._identity]
        if node:
            self._node = node[0]

    @property
    def device_info(self) -> DeviceInfo:
        """Set the device information to that of the node"""

        ret = DeviceInfo(**{
            "hw_version": self._node.hardware_version,
            "identifiers": {(DOMAIN, self._node.serial)},
            "model": self._node.model,
            "name": self._node.name,
            "manufacturer": self._node.manufacturer,
            "sw_version": self._node.firmware.get("version", ""),
        })
        return ret

    @property
    def name(self) -> str:
        """Returns the name of the sensor"""

        return f"{ENTITY_SLUG} {self._node.name}: {self._attribute}"


class LinksysVelopBinarySensor(BinarySensorEntity):
    """Representation of an unpolled binary sensor"""

    _attribute: str
    _identity: str

    @property
    def unique_id(self) -> str:
        """Returns the unique ID for the binary sensor"""

        ret = f"{self._identity}::binary_sensor::{slugify(self._attribute).lower()}"
        return ret


class LinksysVelopBinarySensorPolled(CoordinatorEntity, LinksysVelopBinarySensor):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator):
        """"""

        CoordinatorEntity.__init__(self, coordinator)


class LinksysVelopButton(ButtonEntity, ABC):
    """Representation of a button"""

    _attribute: str
    _identity: str

    @property
    def unique_id(self) -> str:
        """Returns the unique ID for the button"""

        ret = f"{self._identity}::button::{slugify(self._attribute).lower()}"
        return ret


class LinksysVelopDeviceTracker(ScannerEntity, ABC):
    """Representation of a device tracker"""

    _device: Device
    _identity: str

    @property
    def source_type(self) -> str:
        """Return the type as a router"""

        return SOURCE_TYPE_ROUTER

    @property
    def unique_id(self) -> str:
        """Returns the unique ID of the device tracker"""

        ret = f"{self._identity}::device_tracker::{self._device.unique_id}"
        return ret


class LinksysVelopSensor(SensorEntity):
    """Representation of a sensor"""

    _attribute: str
    _identity: str

    @property
    def unique_id(self) -> str:
        """Returns the unique ID of the sensor"""

        ret = f"{self._identity}::sensor::{slugify(self._attribute).lower()}"
        return ret


class LinksysVelopSensorPolled(CoordinatorEntity, LinksysVelopSensor):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator):
        """"""

        CoordinatorEntity.__init__(self, coordinator)


class LinksysVelopSwitch(SwitchEntity, ABC):
    """Representation of a Switch"""

    _attribute: str
    _identity: str

    @property
    def unique_id(self) -> str:
        """Returns the unique ID of the switch"""

        ret = f"{self._identity}::switch::{slugify(self._attribute).lower()}"
        return ret


class LinksysVelopMeshBinarySensor(LinksysVelopBinarySensor, LinksysVelopMeshEntity):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity


class LinksysVelopMeshBinarySensorPolled(LinksysVelopBinarySensorPolled, LinksysVelopMeshEntity):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity

        LinksysVelopBinarySensorPolled.__init__(self, coordinator)


class LinksysVelopMeshButton(LinksysVelopButton, LinksysVelopMeshEntity, ABC):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity


class LinksysVelopMeshSensorPolled(LinksysVelopSensorPolled, LinksysVelopMeshEntity):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity

        LinksysVelopSensorPolled.__init__(self, coordinator)

    def _get_devices(self, status: bool) -> List:
        """Get the devices that match the specified state

        :param status: True if looking for online devices, False otherwise
        :return: a list of devices matching the state
        """

        return [device for device in self._mesh.devices if device.status == status]


class LinksysVelopMeshSwitch(LinksysVelopSwitch, LinksysVelopMeshEntity, ABC):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity


class LinksysVelopNodeBinarySensorPolled(LinksysVelopBinarySensorPolled, LinksysVelopNodeEntity):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity
        self._get_node()

        LinksysVelopBinarySensorPolled.__init__(self, coordinator)
        coordinator.async_add_listener(update_callback=self._get_node)


class LinksysVelopNodeButton(LinksysVelopButton, LinksysVelopNodeEntity, ABC):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity
        self._get_node()

        coordinator.async_add_listener(update_callback=self._get_node)


class LinksysVelopNodeSensorPolled(LinksysVelopSensorPolled, LinksysVelopNodeEntity):
    """"""

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str) -> None:
        """Constructor"""

        self._mesh: Mesh = coordinator.data
        self._identity = identity
        self._get_node()

        LinksysVelopSensorPolled.__init__(self, coordinator)
        coordinator.async_add_listener(update_callback=self._get_node)


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
            node: Node
            for node in mesh.nodes:

                # do not create a reboot button for the primary node
                if cls.__name__ == "LinksysVelopNodeRebootButton" and node.type.lower() == "primary":
                    continue

                entities.append(
                    cls(
                        coordinator=coordinator,
                        identity=node.unique_id,
                    )
                )

    async_add_entities(entities)


def entity_remove(
    hass: HomeAssistant,
    entity_classes: List,
    config: ConfigEntry
) -> None:
    """"""

    coordinator: LinksysVelopDataUpdateCoordinator = hass.data[DOMAIN][config.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    entities: list[Entity] = []

    for cls in entity_classes:
        if cls.__name__.startswith("LinksysVelopMesh"):
            entities.append(
                cls(
                    coordinator=coordinator,
                    identity=config.entry_id,
                )
            )
        else:
            node: Node
            for node in mesh.nodes:
                entities.append(
                    cls(
                        coordinator=coordinator,
                        identity=node.unique_id,
                    )
                )

    entity_registry = er.async_get(hass)
    for entity in entities:
        entity_id = entity_registry.async_get_entity_id(
            domain=entity.unique_id.split("::")[1],
            platform=DOMAIN,
            unique_id=entity.unique_id,
        )
        if entity_id:
            _LOGGER.debug("Removing entity_id: %s", entity_id)
            entity_registry.async_remove(entity_id=entity_id)
