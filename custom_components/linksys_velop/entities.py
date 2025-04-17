"""Base classes, functions and types for entities."""

# region #-- imports --#
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import IntFlag, auto
from typing import Any, Callable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from pyvelop.const import DEF_EMPTY_NAME
from pyvelop.mesh import Mesh
from pyvelop.mesh_entity import DeviceEntity, NodeEntity
from pyvelop.types import NodeType

from .const import (
    CONF_UI_DEVICES,
    DEF_UI_PLACEHOLDER_DEVICE_ID,
    DOMAIN,
    PYVELOP_AUTHOR,
    PYVELOP_NAME,
    PYVELOP_VERSION,
    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
)
from .types import CoordinatorTypes, LinksysVelopConfigEntry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


EsaValueType = Callable[[DeviceEntity | Mesh | NodeEntity], dict[str, Any]] | None
PicValueType = Callable[[DeviceEntity | Mesh | NodeEntity], str] | None
StateValueType = (
    Callable[
        [DeviceEntity | Mesh | NodeEntity], StateType | bool | date | datetime | Decimal
    ]
    | None
)


class EntityType(IntFlag):
    """Possible entity types."""

    DEVICE = auto()
    MESH = auto()
    PLACEHOLDER_DEVICE = auto()
    PRIMARY_NODE = auto()
    SECONDARY_NODE = auto()
    WIRED_NODE = auto()
    WIFI_NODE = auto()
    NODE = PRIMARY_NODE | SECONDARY_NODE | WIFI_NODE | WIRED_NODE


@dataclass
class EntityContext:
    """The context used by entities."""

    unique_id: str


@dataclass
class EntityDetails:
    """Base details for an entity."""

    description: Any
    entity_type: EntityType
    coordinator_type: CoordinatorTypes = CoordinatorTypes.MESH
    esa_value_func: EsaValueType = None
    pic_value_func: PicValueType = None
    state_value_func: StateValueType = None


def build_entities(
    entity_details: list[EntityDetails],
    config_entry: LinksysVelopConfigEntry,
    entity_domain: str,
) -> list[dict[str, EntityContext | LinksysVelopConfigEntry | str | EntityDetails]]:
    """Create a list of information required for creating entities."""

    ret: list[
        dict[str, EntityContext | LinksysVelopConfigEntry | str | EntityDetails]
    ] = []

    for entity in entity_details:
        if entity.entity_type in (EntityType.DEVICE, EntityType.PLACEHOLDER_DEVICE):
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                if entity.entity_type == EntityType.DEVICE or (
                    entity.entity_type == EntityType.PLACEHOLDER_DEVICE
                    and ui_device == DEF_UI_PLACEHOLDER_DEVICE_ID
                ):
                    ret.append(
                        {
                            "config_entry": config_entry,
                            "context": EntityContext(unique_id=ui_device),
                            "entity_details": entity,
                            "entity_domain": entity_domain,
                        }
                    )
        elif entity.entity_type == EntityType.MESH:
            ret.append(
                {
                    "config_entry": config_entry,
                    "context": EntityContext(unique_id=config_entry.entry_id),
                    "entity_details": entity,
                    "entity_domain": entity_domain,
                }
            )
        elif (
            entity.entity_type == EntityType.NODE
            or entity.entity_type in EntityType.NODE
        ):
            for node in config_entry.runtime_data.coordinators.get(
                CoordinatorTypes.MESH
            ).data.nodes:
                wifi_node: bool = (
                    node.backhaul.get("connection", "").lower() == "wireless"
                )
                if (
                    entity.entity_type == EntityType.NODE
                    or (
                        entity.entity_type == EntityType.PRIMARY_NODE
                        and node.type == NodeType.PRIMARY
                    )
                    or (
                        entity.entity_type == EntityType.SECONDARY_NODE
                        and node.type == NodeType.SECONDARY
                    )
                    or (entity.entity_type == EntityType.WIFI_NODE and wifi_node)
                    or (entity.entity_type == EntityType.WIRED_NODE and not wifi_node)
                ):
                    ret.append(
                        {
                            "config_entry": config_entry,
                            "context": EntityContext(unique_id=node.unique_id),
                            "entity_details": entity,
                            "entity_domain": entity_domain,
                        }
                    )

    return ret


class LinksysVelopEntity(CoordinatorEntity):
    """Representation of a Linksys Velop entity."""

    def __init__(
        self,
        context: EntityContext,
        config_entry: LinksysVelopConfigEntry,
        entity_details: EntityDetails,
        entity_domain: str,
    ) -> None:
        """Initialise entity."""
        self.coordinator_context: EntityContext

        self._config_entry: LinksysVelopConfigEntry = config_entry

        self._entity_details: EntityDetails = entity_details

        coordinator = self._config_entry.runtime_data.coordinators.get(
            self._entity_details.coordinator_type
        )

        super().__init__(coordinator, context)
        self.entity_description = self._entity_details.description

        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"{self.coordinator_context.unique_id}::"
            f"{entity_domain.lower()}::"
            f"{slugify(self.entity_description.name)}"
        )

        self._context_data: DeviceEntity | Mesh | NodeEntity | None = None
        self._ui_placeholder_device_id: str | None = None
        self._set_context_data()
        self._update_values()

        if self._entity_details.entity_type in (
            EntityType.DEVICE,
            EntityType.PLACEHOLDER_DEVICE,
        ):
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.coordinator_context.unique_id)},
                manufacturer=(
                    self._context_data.manufacturer or ""
                    if self.coordinator_context.unique_id
                    != DEF_UI_PLACEHOLDER_DEVICE_ID
                    else ""
                ),
                model=(
                    self._context_data.model or ""
                    if self.coordinator_context.unique_id
                    != DEF_UI_PLACEHOLDER_DEVICE_ID
                    else ""
                ),
                name=(
                    self._context_data.name
                    if self.coordinator_context.unique_id
                    != DEF_UI_PLACEHOLDER_DEVICE_ID
                    else "Placeholder Device"
                ),
            )
        elif self._entity_details.entity_type == EntityType.MESH:
            self._attr_device_info = DeviceInfo(
                configuration_url=f"http://{self.coordinator.data.connected_node}",
                entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, self.coordinator_context.unique_id)},
                manufacturer=PYVELOP_AUTHOR,
                model=f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
                name="Mesh",
                sw_version="",
            )
        elif self._entity_details.entity_type in EntityType.NODE:
            self._attr_device_info = DeviceInfo(
                hw_version=self._context_data.hardware_version,
                identifiers={(DOMAIN, self._context_data.serial)},
                model=self._context_data.model,
                name=self._context_data.name,
                manufacturer=self._context_data.manufacturer,
                serial_number=self._context_data.serial,
                sw_version=self._context_data.firmware.get("version", ""),
            )
            if self._context_data.adapter_info:
                self._attr_device_info["configuration_url"] = (
                    f"http://{self._context_data.adapter_info[0].get('ip')}"
                    f"{'/ca' if self._context_data.type is NodeType.SECONDARY else ''}"
                )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_context_data()
        self._update_values()
        super()._handle_coordinator_update()

    def _set_ui_placeholder_device_id(self, device_name: str | None) -> None:

        if device_name is not None:
            _mesh: Mesh = self._config_entry.runtime_data.mesh
            match_on: str = (
                device_name
                if not device_name.startswith(f"{DEF_EMPTY_NAME} (")
                else device_name.split("(")[1].strip(")")
            )
            for dev in _mesh.devices:
                match_against: list[str] = [dev.name.lower(), dev.unique_id]
                if device_name.startswith(f"{DEF_EMPTY_NAME} (") and dev.status:
                    match_against.append(dev.connected_adapters[0].get("ip"))
                if device_name and (match_on.lower() in match_against):
                    device_id = dev.unique_id
                    break
            self._ui_placeholder_device_id = device_id
        else:
            self._ui_placeholder_device_id = None
        self._set_context_data()

    def _set_context_data(self) -> None:
        """Ensure the context data is that of the necessary Device, Mesh or Node."""
        if self._entity_details.entity_type in (
            EntityType.DEVICE,
            EntityType.PLACEHOLDER_DEVICE,
        ):
            device_id: str | None = (
                self.coordinator_context.unique_id
                if self.coordinator_context.unique_id != DEF_UI_PLACEHOLDER_DEVICE_ID
                else self._ui_placeholder_device_id
            )
            if device_id is not None:
                devices: list[DeviceEntity] = [
                    d for d in self.coordinator.data.devices if d.unique_id == device_id
                ]
                if len(devices) > 0:
                    self._context_data: DeviceEntity = devices[0]
            else:
                self._context_data = None
        elif self._entity_details.entity_type == EntityType.MESH:
            self._context_data: Mesh = self.coordinator.data
        elif self._entity_details.entity_type in EntityType.NODE:
            nodes: list[NodeEntity] = [
                n
                for n in self.coordinator.data.nodes
                if n.unique_id == self.coordinator_context.unique_id
            ]
            if len(nodes) > 0:
                self._context_data: NodeEntity = nodes[0]

    def _update_attr_value(self) -> None:
        """Update the attribute value for the entity."""

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        if self.coordinator_context.unique_id == DEF_UI_PLACEHOLDER_DEVICE_ID:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
                    self._set_ui_placeholder_device_id,
                )
            )

    @callback
    def _update_esa_value(self) -> None:
        """Update the extra state attributes for the entity."""

        if self._context_data is None:
            self._attr_extra_state_attributes = None
            return

        if self._entity_details.esa_value_func is not None:
            self._attr_extra_state_attributes = self._entity_details.esa_value_func(
                self._context_data
            )
        else:
            self._attr_extra_state_attributes = None

    @callback
    def _update_pic_value(self) -> None:
        """Update the entity picture attribute for the entity."""

        if self._context_data is None:
            self._attr_entity_picture = None
            return

        if self._entity_details.pic_value_func is not None:
            self._attr_entity_picture = self._entity_details.pic_value_func(
                self._context_data, self._config_entry
            )
        else:
            self._attr_entity_picture = None

    def _update_values(self) -> None:
        self._update_attr_value()
        self._update_esa_value()
        self._update_pic_value()
