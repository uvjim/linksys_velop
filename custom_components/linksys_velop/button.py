"""Button entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass, field
from typing import Callable

from homeassistant.components.button import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.mesh import Mesh, MeshCapability
from pyvelop.node import Node, NodeType

from .const import (
    CONF_ALLOW_MESH_REBOOT,
    CONF_EVENTS_OPTIONS,
    DEF_ALLOW_MESH_REBOOT,
    DEF_EVENTS_OPTIONS,
    DOMAIN,
    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
    IntensiveTask,
)
from .entities import (
    EntityContext,
    EntityDetails,
    EntityType,
    LinksysVelopEntity,
    build_entities,
)
from .helpers import remove_velop_entity_from_registry
from .types import CoordinatorTypes, EventSubTypes, LinksysVelopConfigEntry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class ButtonDetails(EntityDetails):
    """Representation of the button."""

    description: ButtonEntityDescription
    press_func: Callable | str = field(kw_only=True)
    refresh_after: bool = field(default=True)


async def _async_restart_primary_node(config_entry: LinksysVelopConfigEntry) -> None:
    """Restart the primary node."""

    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    primary_node: Node | list[Node] = [
        node for node in mesh.nodes if node.type == NodeType.PRIMARY
    ]
    if len(primary_node) > 0:
        _hass: HomeAssistant = async_get_hass()
        config_entry.runtime_data.mesh_is_rebooting = True
        if EventSubTypes.MESH_REBOOTING.value in config_entry.options.get(
            CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
        ):
            async_dispatcher_send(
                _hass,
                f"{DOMAIN}_{EventSubTypes.MESH_REBOOTING.value}",
            )
        await mesh.async_reboot_node(node_name=primary_node[0].name, force=True)


async def _async_start_channel_scan(config_entry: LinksysVelopConfigEntry) -> None:
    """Start the channel scan."""

    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    config_entry.runtime_data.intensive_running_tasks.append(IntensiveTask.CHANNEL_SCAN)
    await mesh.async_start_channel_scan()


async def _async_start_check_for_updates(config_entry: LinksysVelopConfigEntry) -> None:
    """Start checking for updates."""

    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    await mesh.async_check_for_updates()


async def _async_start_speedtest(config_entry: LinksysVelopConfigEntry) -> None:
    """Start a Speedtest."""

    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    await mesh.async_start_speedtest()


ENTITY_DETAILS: list[ButtonDetails] = [
    # region #-- device buttons --#
    ButtonDetails(
        description=ButtonEntityDescription(
            key="",
            name="Delete",
            translation_key="delete",
        ),
        entity_type=EntityType.DEVICE,
        press_func="_async_delete_device",
    ),
    # endregion
    # region #-- mesh buttons --#
    # endregion
    # region #-- node buttons --#
    ButtonDetails(
        description=ButtonEntityDescription(
            device_class=ButtonDeviceClass.RESTART,
            key="",
            name="Reboot",
            translation_key="reboot",
        ),
        entity_type=EntityType.SECONDARY_NODE,
        press_func="_async_restart_node",
    ),
    # endregion
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a button."""

    entities_to_add: list[LinksysVelopButton] = []

    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)
    # region #-- add additional conditional buttons --#
    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    if MeshCapability.GET_FIRMWARE_UPDATE_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    ButtonDetails(
                        description=ButtonEntityDescription(
                            key="",
                            name="Check for Updates",
                            translation_key="check_for_updates",
                        ),
                        entity_type=EntityType.MESH,
                        press_func=_async_start_check_for_updates,
                    )
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::check_for_updates",
        )

    if MeshCapability.GET_CHANNEL_SCAN_STATUS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    ButtonDetails(
                        coordinator_type=CoordinatorTypes.CHANNEL_SCAN,
                        description=ButtonEntityDescription(
                            entity_registry_enabled_default=False,
                            key="",
                            name="Start Channel Scan",
                            translation_key="channel_scan",
                        ),
                        entity_type=EntityType.MESH,
                        press_func=_async_start_channel_scan,
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::start_channel_scan",
        )

    if MeshCapability.GET_SPEEDTEST_RESULTS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    ButtonDetails(
                        coordinator_type=CoordinatorTypes.SPEEDTEST,
                        description=ButtonEntityDescription(
                            entity_registry_enabled_default=False,
                            key="",
                            name="Start Speedtest",
                            translation_key="speedtest",
                        ),
                        entity_type=EntityType.MESH,
                        press_func=_async_start_speedtest,
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::start_speedtest",
        )

    if config_entry.options.get(CONF_ALLOW_MESH_REBOOT, DEF_ALLOW_MESH_REBOOT):
        entities.extend(
            build_entities(
                [
                    ButtonDetails(
                        description=ButtonEntityDescription(
                            device_class=ButtonDeviceClass.RESTART,
                            key="",
                            name="Reboot the Whole Mesh",
                            translation_key="reboot_mesh",
                        ),
                        entity_type=EntityType.MESH,
                        press_func=_async_restart_primary_node,
                        refresh_after=False,
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        remove_velop_entity_from_registry(
            hass,
            config_entry.entry_id,
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::reboot_the_whole_mesh",
        )

    # endregion
    entities_to_add = [LinksysVelopButton(**entity) for entity in entities]

    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)


class LinksysVelopButton(LinksysVelopEntity, ButtonEntity):
    """Linksys Velop button."""

    def __init__(
        self,
        context: EntityContext,
        config_entry: LinksysVelopConfigEntry,
        entity_details: ButtonDetails,
        entity_domain: str,
    ) -> None:
        """Initialise."""

        super().__init__(context, config_entry, entity_details, entity_domain)
        self._press_func: Callable = entity_details.press_func
        self._refresh_after: bool = entity_details.refresh_after

    async def _async_delete_device(self) -> None:
        """Delete the device."""

        if self._context_data is not None:
            mesh: Mesh = self._config_entry.runtime_data.coordinators.get(
                CoordinatorTypes.MESH
            ).data
            await mesh.async_delete_device_by_id(self._context_data.unique_id)
            async_dispatcher_send(self.hass, SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE, None)

    async def _async_restart_node(self) -> None:
        """Restart the node."""

        if self._context_data is not None:
            mesh: Mesh = self._config_entry.runtime_data.coordinators.get(
                CoordinatorTypes.MESH
            ).data
            await mesh.async_reboot_node(self._context_data.name)

    async def async_press(self) -> None:
        """Carry out the button press action."""

        if isinstance(self._press_func, Callable):
            await self._press_func(self._config_entry)
        elif isinstance(self._press_func, str):
            if hasattr(self, self._press_func):
                await getattr(self, self._press_func)()

        if self._refresh_after:
            await self.coordinator.async_refresh()
