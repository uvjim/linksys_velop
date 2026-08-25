"""Base classes, functions and types for entities."""

# region #-- imports --#
import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, cast, override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.util import slugify
from pyvelop.mesh import Mesh
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
    CoordinatorTimers,
    LinksysVelopDataUpdateCoordinatorMultiUse,
    LinksysVelopDataUpdateCoordinatorSpeedtest,
)
from .helpers import get_mesh_parent_node
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))


class EntityType(StrEnum):
    """Possible entity types."""

    DEVICE = auto()
    MESH = auto()
    NODE = auto()


@dataclass(frozen=True, kw_only=True)
class LinksysVelopEntityContext:
    """"""

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
        if self.entity_description.target_type == EntityType.DEVICE:
            device_info: DeviceEntity | None = self._get_target()
            if (
                device_info is not None
                or self.entity_context.unique_id
                == self.coordinator.config_entry.data.get(CONF_UI_PLACEHOLDER_DEVICE_ID)
            ):
                self._attr_device_info = DeviceInfo(
                    identifiers={(DOMAIN, str(self.entity_context.unique_id))},
                    manufacturer=(
                        str(device_info.manufacturer)
                        if device_info is not None
                        and self.entity_context.unique_id
                        != self.coordinator.config_entry.data.get(
                            CONF_UI_PLACEHOLDER_DEVICE_ID
                        )
                        else ""
                    ),
                    model=(
                        str(device_info.model)
                        if device_info is not None
                        and self.entity_context.unique_id
                        != self.coordinator.config_entry.data.get(
                            CONF_UI_PLACEHOLDER_DEVICE_ID
                        )
                        else ""
                    ),
                    name=(
                        str(device_info.name)
                        if device_info is not None
                        and self.entity_context.unique_id
                        != self.coordinator.config_entry.data.get(
                            CONF_UI_PLACEHOLDER_DEVICE_ID
                        )
                        else "Placeholder Device"
                    ),
                )
        elif self.entity_description.target_type == EntityType.MESH:
            self._attr_device_info = DeviceInfo(
                configuration_url=f"http://{self.coordinator.config_entry.runtime_data.mesh.connected_node}",
                entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, self.entity_context.unique_id)},
                manufacturer=PYVELOP_AUTHOR,
                model=f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
                name="Mesh",
                sw_version="",
            )
        elif self.entity_description.target_type in EntityType.NODE:
            node_info: NodeEntity | None = self._get_target()
            if node_info is not None and node_info.serial is not None:
                self._attr_device_info = DeviceInfo(
                    hw_version=str(node_info.hardware_version),
                    identifiers={(DOMAIN, str(node_info.serial))},
                    model=str(node_info.model),
                    name=str(node_info.name),
                    manufacturer=str(node_info.manufacturer),
                    serial_number=str(node_info.serial),
                    sw_version=node_info.firmware.get("version", ""),
                )

                # region #-- calculate additional attributes --#
                # additional device attributes that are conditional or need more calculation.
                # region #-- calculate the configuration url --#
                if node_info.type == NodeType.SECONDARY and node_info.adapter_info:
                    adapter_main: NodeAdapterInfo | None = next(
                        (adi for adi in node_info.adapter_info if adi.primary),
                        None,
                    )
                    if adapter_main is not None and adapter_main.ip is not None:
                        self._attr_device_info["configuration_url"] = (
                            f"http://{adapter_main.ip}/ca"
                        )
                elif node_info.type == NodeType.PRIMARY:
                    self._attr_device_info["configuration_url"] = (
                        f"http://{self.coordinator.config_entry.runtime_data.mesh.connected_node}"
                    )
                # endregion
                # endregion

        # endregion

    def __repr__(self) -> str:

        return f"{self.__class__.__name__}: {self.entity_context.unique_id} : { self.entity_description.name }"

    def _get_target(self) -> Any:
        """Retrieve the target mesh entity for the current entity."""

        ret: Any = None

        if self.entity_description.target_type == EntityType.DEVICE:
            unique_id: str | None = (
                self.entity_context.unique_id
                if self.entity_context.unique_id
                != self.coordinator.config_entry.data.get(CONF_UI_PLACEHOLDER_DEVICE_ID)
                else self.entity_context.data.get("velop", {}).get("id")
            )

            if unique_id is not None:
                ret = next(
                    (
                        d
                        for d in cast(
                            Mesh, self.coordinator.data.get(CoordinatorTimers.MESH)
                        ).devices
                        if d.unique_id.value == unique_id
                    ),
                    None,
                )
        elif self.entity_description.target_type == EntityType.MESH:
            if self.entity_context.data.get("velop", {}).get("id") is not None:
                ret = next(
                    (
                        d
                        for d in cast(
                            list[DeviceEntity],
                            self.coordinator.data.get(
                                CoordinatorTimers.DEVICE_TRACKER, []
                            ),
                        )
                        if d.unique_id.value
                        == self.entity_context.data.get("velop", {}).get("id")
                    ),
                    None,
                )
            else:
                ret = self.coordinator.data.get(CoordinatorTimers.MESH)
        elif self.entity_description.target_type == EntityType.NODE:
            ret = next(
                (
                    n
                    for n in cast(
                        Mesh, self.coordinator.data.get(CoordinatorTimers.MESH)
                    ).nodes
                    if n.unique_id.value == self.entity_context.unique_id
                ),
                None,
            )

        return ret

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
        """"""

        self.entity_context.data.update({"velop": {"id": velop_id}})


class LinksysVelopSpeedtestEntity(
    CoordinatorEntity[LinksysVelopDataUpdateCoordinatorSpeedtest]
):
    """Representation of and entity that uses the Speedtest DataUpdatCoordinator."""

    entity_description: LinksysVelopEntityDescription
    _attr_has_entity_name: bool = True
    _entity_domain: str

    def __init__(
        self,
        *,
        coordinator: LinksysVelopDataUpdateCoordinatorSpeedtest,
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
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{self.coordinator.config_entry.runtime_data.mesh.connected_node}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.entity_context.unique_id)},
            manufacturer=PYVELOP_AUTHOR,
            model=f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            name="Mesh",
            sw_version="",
        )
        # endregion
