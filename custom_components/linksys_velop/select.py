"""Select entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, override

from homeassistant.components.select import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from pyvelop.mesh import MeshSnapshot, ScheduledRebootInterval
from pyvelop.mesh_entity import EMPTY_NAME, AdapterInfo, DeviceEntity, UiType

from .const import (
    CONF_NODE_IMAGES,
    CONF_UI_DEVICES,
    CONF_UI_PLACEHOLDER_DEVICE_ID,
    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
)
from .coordinator import (
    CoordinatorTimers,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
    TargetEntityType,
)
from .helpers import remove_velop_entity_from_registry
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass(frozen=True, kw_only=True)
class LinksysVelopSelectEntityDescription(
    LinksysVelopEntityDescription, SelectEntityDescription
):
    """Describes Velop select entity."""

    options_fn: Callable[[MeshSnapshot], Iterable[str]] | None = None
    pic_fn: (
        Callable[
            [LinksysVelopDataUpdateCoordinatorMultiUse, TargetEntityType], str | None
        ]
        | None
    ) = None
    set_fn: (
        Callable[
            [LinksysVelopDataUpdateCoordinatorMultiUse, TargetEntityType, str],
            Awaitable[None],
        ]
        | None
    ) = None
    value_fn: Callable[[MeshSnapshot, str], str | None] | None = None


def get_current_reboot_schedule(mesh: MeshSnapshot, *args) -> str | None:
    """Retrieve the current reboot schedule for display in the select entity."""

    if mesh.scheduled_reboot_enabled:
        ret = (
            mesh.scheduled_reboot_interval.value.lower()
            if mesh.scheduled_reboot_interval.value is not None
            else None
        )
    else:
        ret = "off"

    return ret


def get_placeholder_device_options(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> Mapping[str, str]:
    """Retrieve the list of device options available for the placeholder device.

    :param: mesh: Current `MeshSnapshot` for determining available devices.
    :returns: Mapping containing the unique IDs and display names.
    """

    mesh_data: MeshSnapshot | None = coordinator.data.mesh
    if mesh_data is None:
        return {}

    ret: dict[str, str] = {}

    for device in mesh_data.devices:
        adi: AdapterInfo | None = next(iter(device.adapter_info), None)
        name: str = (
            device.name.value
            if device.name != EMPTY_NAME
            else f"{device.name} ({adi.ip if adi is not None and device.status else device.unique_id})"
        )
        if device.unique_id.value is not None:
            ret[device.unique_id.value] = name

    return ret


def get_device_icon(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    target: TargetEntityType,
) -> str | None:
    """Retrieve the path to the icon to show for target.

    :param coordinator: The data update coordinator used to refresh the mesh state.
    :param target: The mesh entity to retrieve the icon for.
    :returns: Path to the icon.
    """

    if not isinstance(target, DeviceEntity):
        return

    prefix: str = coordinator.config_entry.options.get(CONF_NODE_IMAGES, "")
    if not prefix:
        return

    return f"{prefix.rstrip('/').strip()}/{target.ui_type}.png"


async def async_update_device_icon(
    _: LinksysVelopDataUpdateCoordinatorMultiUse,
    target: TargetEntityType,
    option: str,
) -> None:
    """Set the new UI type/icon for the device.

    :param _: Unused data update coordinator used to refresh the mesh state.
    :param target: Device to update the icon for.
    :param option: the currently selected reboot option.
    """

    if not isinstance(target, DeviceEntity):
        return

    ui_type: UiType = UiType(option)
    await target.async_set_icon(ui_type)


async def async_update_reboot_schedule(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    _: TargetEntityType,
    option: str,
) -> None:
    """Set the reboot schedule on the mesh.

    :param coordinator: The data update coordinator used to refresh the mesh state.
    :param _: Unused target.
    :param option: the currently selected reboot option.
    """

    if option == "off":
        await coordinator.api.async_set_scheduled_reboot_state(False)
    else:
        await coordinator.api.async_set_scheduled_reboot_interval(
            ScheduledRebootInterval(option.title())
        )


async def async_update_placeholder_device(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    target: TargetEntityType,
    option: str,
) -> None:
    """Calculate the new placeholder device ID and send the signal.

    :param coordinator: The data update coordinator used to refresh the mesh state.
    :param _: Unused `DeviceEntity` currently in use by the placeholder.
    :param option: Currently selected option.
    """

    if not coordinator.data.mesh:
        return

    # extract the actual name/ID from the option string
    match_on = (
        option.split("(")[1].strip(")")
        if option.startswith(f"{EMPTY_NAME} (")
        else option
    )
    match_on_lower = match_on.lower()

    # find the first device that matches the search criteria
    velop_id = None
    for dev in coordinator.data.mesh.devices:
        match_against = [dev.name.lower(), str(dev.unique_id)]

        # append IP if we are in "Empty Name" mode and device has an IP
        if option.startswith(f"{EMPTY_NAME} (") and dev.status:
            adi = next(iter(dev.adapter_info), None)
            if adi and adi.ip:
                match_against.append(adi.ip)

        if match_on_lower in match_against:
            velop_id = dev.unique_id.value
            break

    if velop_id:
        async_dispatcher_send(
            coordinator.hass, SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE, velop_id
        )


ENTITIES: Mapping[str, tuple[LinksysVelopSelectEntityDescription, ...]] = (
    MappingProxyType(
        {
            "scheduled_reboot_interval": (
                LinksysVelopSelectEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="",
                    name="Scheduled Reboot",
                    options_fn=lambda _: list(
                        map(
                            str.lower,
                            ["off"] + list(map(str, ScheduledRebootInterval)),
                        )
                    ),
                    set_fn=async_update_reboot_schedule,
                    target_type=EntityType.MESH,
                    translation_key="mesh_scheduled_reboot",
                    value_fn=get_current_reboot_schedule,
                ),
            ),
            "ui_type": (
                LinksysVelopSelectEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="ui_type",
                    name="Icon",
                    options_fn=lambda _: sorted(map(str.lower, UiType)),
                    pic_fn=get_device_icon,
                    set_fn=async_update_device_icon,
                    target_type=EntityType.DEVICE,
                    translation_key="ui_type",
                ),
            ),
        }
    )
)


class LinksysVelopSelectEntity(LinksysVelopMultiUseEntity, SelectEntity):
    """Linksys Velop select entity."""

    entity_description: LinksysVelopSelectEntityDescription
    _entity_domain: str = ENTITY_DOMAIN

    @property
    @override
    def current_option(self) -> str | None:

        mesh_data = self.coordinator.data.mesh
        if mesh_data is None:
            return

        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(
                mesh_data,
                self.entity_context.data.get("velop", {}).get("id"),
            )
        elif self.entity_description.key:
            ret: Any | None = getattr(
                self._get_target(), self.entity_description.key, None
            )
            if ret is not None:
                ret = str(ret)

            return ret

        return self._attr_current_option

    @property
    @override
    def entity_picture(self) -> str | None:

        ret: str | None = None
        if callable(self.entity_description.pic_fn):
            ret = self.entity_description.pic_fn(self.coordinator, self._get_target())

        return ret

    @property
    @override
    def options(self) -> list[str]:

        ret: list[str] = []
        mesh_data = self.coordinator.data.mesh
        if mesh_data is None:
            return ret

        if callable(self.entity_description.options_fn):
            ret = list(self.entity_description.options_fn(mesh_data))
        elif self.entity_description.options is not None:
            ret = self.entity_description.options

        return ret

    @override
    async def async_select_option(self, option: str) -> None:

        # set the current option - redundant in most cases
        self._attr_current_option = option

        # call the appropriate function or the default if none provided
        if callable(self.entity_description.set_fn):
            await self.entity_description.set_fn(
                self.coordinator,
                self._get_target(),
                option,
            )
            # refresh the data
            await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)
        else:
            await super().async_select_option(option)


def _init_device_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopSelectEntity, ...]:
    """Initialise the entities that target devices.

    :param coordinator: The data update coordinator.
    :return: A tuple of initialised device entities.
    """
    config_entry = coordinator.config_entry
    mesh_data = coordinator.data.mesh
    if mesh_data is None:
        return ()

    descriptions = tuple(
        entity
        for attr, entities in ENTITIES.items()
        if hasattr(DeviceEntity, attr)
        for entity in entities
        if entity.target_type is EntityType.DEVICE
    )

    entities: list[LinksysVelopSelectEntity] = []
    placeholder_device_id = config_entry.data.get(CONF_UI_PLACEHOLDER_DEVICE_ID)

    for device_id in config_entry.options.get(CONF_UI_DEVICES, []):
        device_descriptions = descriptions

        if device_id == placeholder_device_id:
            device_descriptions += (
                LinksysVelopSelectEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="",
                    name="Devices",
                    options_fn=lambda mesh: list(
                        get_placeholder_device_options(coordinator).values()
                    ),
                    set_fn=async_update_placeholder_device,
                    target_type=EntityType.DEVICE,
                    translation_key="mesh_devices",
                    value_fn=lambda mesh, uid: get_placeholder_device_options(
                        coordinator
                    ).get(uid),
                ),
            )

        context = LinksysVelopEntityContext(unique_id=device_id)
        entities.extend(
            LinksysVelopSelectEntity(
                entity_context=context,
                coordinator=coordinator,
                description=description,
            )
            for description in device_descriptions
        )

    return tuple(entities)


def _init_mesh_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> tuple[LinksysVelopSelectEntity, ...]:
    """Initialise the entities that target the mesh.

    :param coordinator: The data update coordinator.
    :return: A tuple of initialised mesh entities.
    """
    config_entry = coordinator.config_entry
    mesh_data = coordinator.data.mesh
    if mesh_data is None:
        return ()

    descriptions = tuple(
        entity
        for attr, entities in ENTITIES.items()
        if hasattr(mesh_data, attr)
        for entity in entities
        if entity.target_type is EntityType.MESH
    )

    context = LinksysVelopEntityContext(unique_id=config_entry.entry_id)

    return tuple(
        LinksysVelopSelectEntity(
            entity_context=context,
            coordinator=coordinator,
            description=description,
        )
        for description in descriptions
    )


def _init_node_entities() -> tuple[LinksysVelopSelectEntity, ...]:
    """Initialise the entities that target nodes.

    :return: A tuple of initialised node entities.
    """
    return ()


def _remove_stale_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> None:
    """Remove entities if they are no longer required.

    :param coordinator: The data update coordinator.
    """
    hass = coordinator.hass
    config_entry = coordinator.config_entry
    mesh_data = coordinator.data.mesh
    if mesh_data is None:
        return

    entities_to_remove: set[str] = set()

    # region #-- add mesh entities if they no longer exist --#
    mesh_entities: tuple[str, ...] = tuple(
        attr if len(entities) == 1 else slugify(str(entity.name))
        for attr, entities in ENTITIES.items()
        if not hasattr(mesh_data, attr)
        for entity in entities
        if entity.target_type == EntityType.MESH
    )
    for me in mesh_entities:
        entities_to_remove.add(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::{me}")
    # endregion

    for entity_unique_id in entities_to_remove:
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            entity_unique_id,
        )


def create_node_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the node entities.

    This is handled separately as new nodes may be added to the mesh whilst the integration is running.

    :param coordinator: The data update coordinator.
    :param async_add_entities: Callback to add entities to Home Assistant.
    """
    entities_to_add = _init_node_entities()
    if entities_to_add:
        async_add_entities(entities_to_add)


def create_static_entities(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the mesh and device entities.

    :param coordinator: The data update coordinator.
    :param async_add_entities: Callback to add entities to Home Assistant.
    """
    entities_to_add = _init_device_entities(coordinator) + _init_mesh_entities(
        coordinator
    )
    if entities_to_add:
        async_add_entities(entities_to_add)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise select entities.

    :param hass: The Home Assistant instance.
    :param config_entry: The configuration entry for the device.
    :param async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = config_entry.runtime_data.coordinator

    _remove_stale_entities(coordinator)
    create_static_entities(coordinator, async_add_entities)
    create_node_entities(coordinator, async_add_entities)

    config_entry.async_on_unload(
        coordinator.add_listener_for_timer_type(
            CoordinatorTimers.MESH,
            lambda: create_node_entities(coordinator, async_add_entities),
        )
    )
