"""Base classes, functions and types for entities."""

# region #-- imports --#
import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.util import slugify
from pyvelop.mesh import MeshSnapshot
from pyvelop.mesh_entity import DeviceEntity, NodeAdapterInfo, NodeEntity, NodeType

from .const import (
    CONF_UI_PLACEHOLDER_DEVICE_ID,
    DOMAIN,
    PYVELOP_AUTHOR,
    PYVELOP_NAME,
    PYVELOP_VERSION,
    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
)
from .coordinator import (
    LinksysVelopDataUpdateCoordinatorMultiUse,
)
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))

TargetEntityType = MeshSnapshot | DeviceEntity | NodeEntity | None


class EntityType(StrEnum):
    """Possible entity types."""

    DEVICE = auto()
    MESH = auto()
    NODE = auto()


@dataclass(frozen=True, kw_only=True)
class LinksysVelopEntityContext:
    """Representation of details for the context of the entity type."""

    data: dict[str, Any] = field(default_factory=dict)
    unique_id: str


@dataclass(frozen=True, kw_only=True)
class LinksysVelopEntityDescription(EntityDescription):
    """Describes Velop switch entity."""

    target_type: EntityType


class LinksysVelopMultiUseEntity(
    CoordinatorEntity[LinksysVelopDataUpdateCoordinatorMultiUse]
):
    """Representation of a Linksys Velop entity that uses the multi use DataUpdateCoordinator."""

    entity_description: LinksysVelopEntityDescription
    _attr_has_entity_name: bool = True
    _entity_domain: str

    def __init__(
        self,
        *,
        coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
        description: LinksysVelopEntityDescription,
        entity_context: LinksysVelopEntityContext,
    ) -> None:
        """Initialise entity."""

        super().__init__(coordinator)

        # region #-- custom attributes --#
        self.entity_context: LinksysVelopEntityContext = entity_context
        # endregion

        # region #-- standard attributes --#
        if description is not None:
            self.entity_description = description

        self._attr_unique_id = (
            f"{self.entity_context.unique_id}::"
            f"{self._entity_domain.lower()}::"
            f"{slugify(str(self.entity_description.name))}"
        )
        # endregion

        # region #-- setup device info --#
        target_type: EntityType = self.entity_description.target_type
        if target_type in (EntityType.DEVICE, EntityType.NODE):
            target: TargetEntityType = self._get_target()
            if isinstance(target, DeviceEntity) or target is None:
                is_placeholder_device: bool = (
                    self.entity_context.unique_id
                    == self.coordinator.config_entry.data.get(
                        CONF_UI_PLACEHOLDER_DEVICE_ID
                    )
                )
                self._attr_device_info = DeviceInfo(
                    identifiers={(DOMAIN, str(self.entity_context.unique_id))},
                    manufacturer=(
                        str(target.manufacturer)
                        if target is not None and not is_placeholder_device
                        else ""
                    ),
                    model=(
                        str(target.model)
                        if target is not None and not is_placeholder_device
                        else ""
                    ),
                    name=(
                        str(target.name)
                        if target is not None
                        and self.entity_context.unique_id
                        != self.coordinator.config_entry.data.get(
                            CONF_UI_PLACEHOLDER_DEVICE_ID
                        )
                        else "Placeholder Device"
                    ),
                )
            elif isinstance(target, NodeEntity) and target.serial is not None:
                self._attr_device_info = DeviceInfo(
                    hw_version=str(target.hardware_version),
                    identifiers={(DOMAIN, str(target.serial))},
                    model=str(target.model),
                    name=str(target.name),
                    manufacturer=str(target.manufacturer),
                    serial_number=str(target.serial),
                    sw_version=target.firmware.get("version", ""),
                )

                if target.type == NodeType.SECONDARY and target.adapter_info:
                    adapter_main: NodeAdapterInfo | None = next(
                        (adi for adi in target.adapter_info if adi.primary),
                        None,
                    )
                    if adapter_main is not None and adapter_main.ip is not None:
                        self._attr_device_info["configuration_url"] = (
                            f"http://{adapter_main.ip}/ca"
                        )
                elif target.type == NodeType.PRIMARY:
                    self._attr_device_info["configuration_url"] = (
                        f"http://{self.coordinator.api.connected_node}"
                    )
        elif self.entity_description.target_type == EntityType.MESH:
            self._attr_device_info = DeviceInfo(
                configuration_url=f"http://{self.coordinator.api.connected_node}",
                entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, self.entity_context.unique_id)},
                manufacturer=PYVELOP_AUTHOR,
                model=f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
                name="Mesh",
                sw_version="",
            )
        # endregion

    def __repr__(self) -> str:

        return f"{self.__class__.__name__}: {self.entity_context.unique_id} : { self.entity_description.name }"

    def _get_target(self) -> TargetEntityType:
        """Retrieve the target mesh entity for the current entity.

        :returns:
        """

        mesh: MeshSnapshot | None = self.coordinator.data.mesh
        if mesh is None:
            return None

        target_type = self.entity_description.target_type
        context_data = self.entity_context.data
        velop_id = context_data.get("velop", {}).get("id")

        if target_type in (EntityType.DEVICE, EntityType.NODE):
            placeholder_id = self.coordinator.config_entry.data.get(
                CONF_UI_PLACEHOLDER_DEVICE_ID
            )
            unique_id = (
                self.entity_context.unique_id
                if self.entity_context.unique_id != placeholder_id
                else velop_id
            )

            if unique_id is None:
                return None

            target = next(
                (
                    device
                    for device in mesh.devices
                    if device.unique_id.value == unique_id
                ),
                None,
            )

            if target is not None:
                return target

            return next(
                (node for node in mesh.nodes if node.unique_id.value == unique_id),
                None,
            )

        if target_type == EntityType.MESH:
            if velop_id is None:
                return mesh

            return next(
                (
                    device
                    for device in self.coordinator.data.device_tracker
                    if device.unique_id.value == velop_id
                ),
                None,
            )

        return None

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # region #-- create signal for updating the placeholder device --#
        if self.entity_context.unique_id == self.coordinator.config_entry.data.get(
            CONF_UI_PLACEHOLDER_DEVICE_ID
        ):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
                    self._handle_placeholder_device_update,
                )
            )
        # endregion

    def _handle_placeholder_device_update(self, velop_id: str | None) -> None:
        """Update the placeholder device context data.

        :param velop_id: unique ID of the device as provided by the mesh.
        """

        self.entity_context.data.update({"velop": {"id": velop_id}})
