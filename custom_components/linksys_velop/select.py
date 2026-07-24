"""Select entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast, override

from homeassistant.components.select import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh import Mesh, MeshCapability, ScheduledRebootInterval
from pyvelop.mesh_entity import EMPTY_NAME, DeviceEntity, UiType

from .const import (
    CONF_NODE_IMAGES,
    CONF_UI_DEVICES,
    DEF_UI_PLACEHOLDER_DEVICE_ID,
    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
)
from .coordinator import (
    CoordinatorTimers,
    CoordinatorTypes,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
)
from .helpers import remove_velop_entity_from_registry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinksysVelopSelectEntityDescription(
    LinksysVelopEntityDescription, SelectEntityDescription
):
    """Describes Velop select entity."""

    options_fn: Callable[[Mesh], list[str]] | None = None
    pic_fn: Callable[..., str | None] | None = None
    set_fn: Callable[[Any, str], Awaitable[None]] | None = None
    value_fn: Callable[[Mesh, str], str | None] | None = None


def get_current_reboot_schedule(mesh: Mesh, *args) -> str | None:
    """Retrieve the current reboot schedule for display in the select entity."""

    if mesh.scheduled_reboot_enabled:
        ret = (
            mesh.scheduled_reboot_interval.value.lower()
            if mesh.scheduled_reboot_interval is not None
            else None
        )
    else:
        ret = "off"

    return ret


def get_placeholder_device_options(mesh: Mesh) -> dict[str, str]:
    """Retrieve the list of device options available for the placeholder device."""

    ret: dict[str, str] = {}

    for d in mesh.devices:
        name: str = (
            d.name
            if d.name != EMPTY_NAME
            else f"{d.name} ({next(iter(d.adapter_info), {}).get('ip') if d.status else d.unique_id})"
        )
        if d.unique_id is not None:
            ret[d.unique_id] = name

    return ret


async def async_update_reboot_schedule(mesh: Mesh, option: str) -> None:
    """Set the reboot schedule on the mesh."""

    if option == "off":
        await mesh.async_set_scheduled_reboot_state(False)
    else:
        await mesh.async_set_scheduled_reboot_interval(
            ScheduledRebootInterval(option.title())
        )


async def async_update_placeholder_device(mesh: Mesh, option: str) -> None:
    """Calculate the new placeholder device ID and send the signal."""

    velop_id: str | None = None
    hass: HomeAssistant = async_get_hass()

    # region #-- match the display name back to an ID --#
    match_on: str = (
        option
        if not option.startswith(f"{EMPTY_NAME} (")
        else option.split("(")[1].strip(")")
    )
    for dev in mesh.devices:
        match_against: list[str] = [dev.name.lower(), str(dev.unique_id)]
        if option.startswith(f"{EMPTY_NAME} (") and dev.status:
            match_against.append(dev.adapter_info[0].get("ip", ""))
        if match_on.lower() in match_against:
            velop_id = dev.unique_id
            break
    # endregion

    # region #-- send a signal informing that the placeholder device has updated --#
    if velop_id is not None:
        async_dispatcher_send(
            hass,
            SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
            velop_id,
        )
    # endregion


async def async_update_placeholder_device_icon(
    device: DeviceEntity, option: str
) -> None:
    """Set the new UI type/icon for the device."""

    ui_type: UiType = UiType(option)
    await device.async_set_icon(ui_type)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise select entities."""

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: list[LinksysVelopSelectEntity] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> list[LinksysVelopSelectEntity]:
        """Describe the entities that target devices."""
        ret: list[LinksysVelopSelectEntity] = []
        mesh_entities: list[LinksysVelopSelectEntityDescription] = []

        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                unique_id=ui_device
            )

            mesh_entities.append(
                LinksysVelopSelectEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="ui_type",
                    name="Icon",
                    options_fn=lambda _: sorted(
                        list(
                            map(
                                str.lower,
                                UiType,
                            )
                        )
                    ),
                    pic_fn=lambda d: (
                        f"{prefix.rstrip('/').strip()}/{cast(DeviceEntity, d).ui_type}.png"
                        if d is not None
                        and (prefix := config_entry.options.get(CONF_NODE_IMAGES))
                        not in (None, "")
                        else None
                    ),
                    set_fn=async_update_placeholder_device_icon,
                    target_type=EntityType.DEVICE,
                    translation_key="ui_type",
                )
            )

            if context.unique_id == DEF_UI_PLACEHOLDER_DEVICE_ID:
                mesh_entities.append(
                    LinksysVelopSelectEntityDescription(
                        entity_category=EntityCategory.CONFIG,
                        key="",
                        name="Devices",
                        options_fn=lambda m: list(
                            get_placeholder_device_options(m).values()
                        ),
                        set_fn=async_update_placeholder_device,
                        target_type=EntityType.DEVICE,
                        translation_key="mesh_devices",
                        value_fn=lambda m, uid: get_placeholder_device_options(m).get(
                            uid
                        ),
                    )
                )

            for desc in mesh_entities:
                ret.append(
                    LinksysVelopSelectEntity(
                        entity_context=context,
                        coordinator=cast(
                            LinksysVelopDataUpdateCoordinatorMultiUse,
                            config_entry.runtime_data.coordinators.get(
                                CoordinatorTypes.MESH
                            ),
                        ),
                        description=desc,
                    )
                )

        return ret

    def _init_mesh_entities() -> list[LinksysVelopSelectEntity]:
        """Describe the entities that target the mesh."""
        ret = []

        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )

        mesh_entities: list[LinksysVelopSelectEntityDescription] = []
        speedtest_entities: list[LinksysVelopSelectEntityDescription] = []

        if (
            MeshCapability.GET_SCHEDULED_REBOOT_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
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
            )

        for desc in mesh_entities:
            ret.append(
                LinksysVelopSelectEntity(
                    entity_context=context,
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorMultiUse,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.MESH
                        ),
                    ),
                    description=desc,
                )
            )

        for desc in speedtest_entities:
            ret.append(
                LinksysVelopSelectEntity(
                    entity_context=context,
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorMultiUse,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.SPEEDTEST
                        ),
                    ),
                    description=desc,
                )
            )

        return ret

    def _init_node_entities() -> list[LinksysVelopSelectEntity]:
        """Describe the entities that target nodes."""
        ret = []

        return ret

    def _remove_stale_entities() -> None:
        """Remove entities is they are no longer required."""

        entities_to_remove: set[str] = set()

        if (
            MeshCapability.GET_SCHEDULED_REBOOT_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::scheduled_reboot"
            )

        if len(entities_to_remove) > 0:
            for entity_unique_id in entities_to_remove:
                remove_velop_entity_from_registry(
                    hass,
                    config_entry.entry_id,
                    entity_unique_id,
                )

    def create_node_entities() -> None:
        """Create the node entities.

        This is in a separate function because new nodes can be added to the mesh whilst the integration is running.
        """

        entities_to_add: list[LinksysVelopSelectEntity] = _init_node_entities()

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    _create_entities()
    create_node_entities()

    config_entry.async_on_unload(
        cast(
            LinksysVelopDataUpdateCoordinatorMultiUse,
            config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
        ).add_listener_for_timer_type(CoordinatorTimers.MESH, create_node_entities)
    )


class LinksysVelopSelectEntity(LinksysVelopMultiUseEntity, SelectEntity):
    """Linksys Velop select entity."""

    entity_description: LinksysVelopSelectEntityDescription
    _entity_domain: str = ENTITY_DOMAIN

    @property
    @override
    def current_option(self) -> str | None:

        if (
            self.entity_description.value_fn is not None
            and (mesh := self.coordinator.data.get(CoordinatorTimers.MESH)) is not None
        ):
            return self.entity_description.value_fn(
                mesh, self.entity_context.data.get("velop", {}).get("id")
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
        if self.entity_description.pic_fn is not None:
            ret = self.entity_description.pic_fn(self._get_target())

        return ret

    @property
    @override
    def options(self) -> list[str]:

        ret: list[str] = []
        if (
            self.entity_description.options_fn is not None
            and (mesh := self.coordinator.data.get(CoordinatorTimers.MESH)) is not None
        ):
            ret = self.entity_description.options_fn(mesh)
        elif self.entity_description.options is not None:
            ret = self.entity_description.options

        return ret

    @override
    async def async_select_option(self, option: str) -> None:

        # region #-- set the currnet option - redundant in most cases --#
        self._attr_current_option = option
        # endregion

        # region #-- call the appropriate function or the default if none provided --#
        if (
            self.entity_description.set_fn is not None
            and (mesh := self.coordinator.data.get(CoordinatorTimers.MESH)) is not None
        ):
            if (
                self.entity_context.unique_id == DEF_UI_PLACEHOLDER_DEVICE_ID
                and self.entity_description.key
            ):
                await self.entity_description.set_fn(
                    self._get_target(),
                    option,
                )
            else:
                await self.entity_description.set_fn(
                    mesh,
                    option,
                )
            # refresh the data
            await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)
        else:
            await super().async_select_option(option)
        # endregion
