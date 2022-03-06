"""Base classes for managing entities in the integration"""

import logging
from abc import ABC

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.helpers.entity import DeviceInfo, Entity
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.device import Device
from pyvelop.mesh import Mesh

from .const import (
    DOMAIN,
    ENTITY_SLUG,
)

_LOGGER = logging.getLogger(__name__)


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
