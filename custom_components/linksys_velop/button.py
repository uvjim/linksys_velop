"""Button entities for Linksys Velop."""

# region #-- imports --#
import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast, override

from homeassistant.components.button import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from pyvelop.mesh import Mesh, SpeedtestResult
from pyvelop.mesh_entity import DeviceEntity, NodeEntity, NodeType

from .const import (
    CONF_ALLOW_MESH_REBOOT,
    CONF_EVENTS_OPTIONS,
    CONF_UI_DEVICES,
    DEF_ALLOW_MESH_REBOOT,
    DEF_EVENTS_OPTIONS,
    DOMAIN,
    SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE,
    EventSubTypes,
)
from .coordinator import (
    BlockingTasks,
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
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))
CAP_REBOOT: str = "REBOOT"


@dataclass(frozen=True, kw_only=True)
class LinksysVelopButtonEntityDescription(
    LinksysVelopEntityDescription, ButtonEntityDescription
):
    """Describes Velop button entity."""

    press_fn: (
        Callable[[LinksysVelopDataUpdateCoordinatorMultiUse], Awaitable[None]] | str
    )


async def async_restart_primary_node(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> None:
    """Restart the primary node."""

    config_entry: LinksysVelopConfigEntry = coordinator.config_entry

    # region #-- flag as rebooting and send event --#
    config_entry.runtime_data.blocking_tasks.add(BlockingTasks.REBOOT)
    if EventSubTypes.MESH_REBOOTING.value in config_entry.options.get(
        CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
    ):
        async_dispatcher_send(
            coordinator.hass,
            f"{DOMAIN}_{EventSubTypes.MESH_REBOOTING.value}",
        )
    # endregion

    await config_entry.runtime_data.mesh.async_reboot_mesh(True)

    # region #-- flag reboot complete and send event --#
    config_entry.runtime_data.blocking_tasks.remove(BlockingTasks.REBOOT)
    if EventSubTypes.MESH_REBOOTED.value in config_entry.options.get(
        CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
    ):
        async_dispatcher_send(
            coordinator.hass,
            f"{DOMAIN}_{EventSubTypes.MESH_REBOOTED.value}",
        )
    # endregion


async def async_start_check_for_updates(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> None:
    """Start checking for updates."""

    await coordinator.config_entry.runtime_data.mesh.async_check_for_updates()


async def async_start_speedtest(
    coordinator: LinksysVelopDataUpdateCoordinatorMultiUse,
) -> None:
    """Start a Speedtest."""

    def _handle_updates(progress: SpeedtestResult) -> None:
        """Update the speedtest data in the runtime."""

        coordinator.config_entry.runtime_data.speedtest_data = progress
        coordinator.async_update_listeners()

    await coordinator.config_entry.runtime_data.mesh.async_start_speedtest(
        wait=True, callback_func=_handle_updates
    )

    results: tuple[SpeedtestResult, ...] = (
        await coordinator.config_entry.runtime_data.mesh.async_get_speedtest_results(
            only_completed=True
        )
    )
    coordinator.config_entry.runtime_data.speedtest_data = max(
        results,
        key=lambda result: result.timestamp,
        default=None,
    )
    coordinator.async_update_listeners()
    coordinator.config_entry.runtime_data.speedtest_data = None


def has_capability(capabilities: tuple[Mapping[str, Any], ...], name: str) -> bool:
    """Determine of the mesh has a spevcified capability.

    :param capabilities: Capabilities as returned from the mesh.
    :returns: `True` if the capability is available, `False` otherwise.
    """

    found: Mapping[str, Any] | None = next(
        (cap for cap in capabilities if cap.get("key", "") == name), None
    )

    return bool(found)


ENTITIES: Mapping[str, tuple[LinksysVelopButtonEntityDescription, ...]] = (
    MappingProxyType(
        {
            "DELETE_DEVICE": (
                LinksysVelopButtonEntityDescription(
                    key="",
                    name="Delete",
                    translation_key="delete",
                    target_type=EntityType.DEVICE,
                    press_fn="_async_delete_device",
                ),
            ),
            "START_CHANNEL_SCAN": (
                LinksysVelopButtonEntityDescription(
                    entity_registry_enabled_default=False,
                    key="",
                    name="Start Channel Scan",
                    translation_key="channel_scan",
                    target_type=EntityType.MESH,
                    press_fn="_async_start_channel_scan",
                ),
            ),
            "START_SPEEDTEST": (
                LinksysVelopButtonEntityDescription(
                    entity_registry_enabled_default=False,
                    key="",
                    name="Start Speedtest",
                    translation_key="speedtest",
                    target_type=EntityType.MESH,
                    press_fn=async_start_speedtest,
                ),
            ),
            "UPDATE_FIRMWARE": (
                LinksysVelopButtonEntityDescription(
                    key="",
                    name="Check for Updates",
                    translation_key="check_for_updates",
                    target_type=EntityType.MESH,
                    press_fn=async_start_check_for_updates,
                ),
            ),
        }
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise a button."""

    known_nodes: set[str] = set()

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopButtonCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if entities_to_add:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopButtonCoordinatorEntity, ...]:
        """Describe the entities that target devices."""

        device_ids = config_entry.options.get(CONF_UI_DEVICES, [])

        descriptions = tuple(
            entity
            for entities in ENTITIES.values()
            for entity in entities
            if entity.target_type == EntityType.DEVICE
        )

        coordinator = cast(
            LinksysVelopDataUpdateCoordinatorMultiUse,
            config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
        )

        return tuple(
            LinksysVelopButtonMultiUseEntity(
                entity_context=LinksysVelopEntityContext(unique_id=device_id),
                coordinator=coordinator,
                description=description,
            )
            for device_id in device_ids
            for description in descriptions
        )

    def _init_mesh_entities() -> tuple[LinksysVelopButtonCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""

        ret: tuple[LinksysVelopButtonCoordinatorEntity, ...] = ()
        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )
        mesh_capabilities: tuple[Mapping[str, Any], ...] = (
            config_entry.runtime_data.mesh.capabilities
        )
        descriptions: tuple[LinksysVelopButtonEntityDescription, ...] = tuple(
            entity
            for cap, entities in ENTITIES.items()
            if has_capability(mesh_capabilities, cap)
            for entity in entities
            if entity.target_type == EntityType.MESH
        )

        if config_entry.options.get(
            CONF_ALLOW_MESH_REBOOT, DEF_ALLOW_MESH_REBOOT
        ) and has_capability(mesh_capabilities, CAP_REBOOT):
            descriptions = descriptions + (
                LinksysVelopButtonEntityDescription(
                    device_class=ButtonDeviceClass.RESTART,
                    key="",
                    name="Reboot the Whole Mesh",
                    translation_key="reboot_mesh",
                    target_type=EntityType.MESH,
                    press_fn=async_restart_primary_node,
                ),
            )

        coordinator = cast(
            LinksysVelopDataUpdateCoordinatorMultiUse,
            config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
        )

        return tuple(
            LinksysVelopButtonMultiUseEntity(
                entity_context=context,
                coordinator=coordinator,
                description=description,
            )
            for description in descriptions
        )

        return ret

    def _init_node_entities() -> tuple[LinksysVelopButtonCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""

        current_nodes = {
            node.unique_id.value
            for node in config_entry.runtime_data.mesh.nodes
            if node.unique_id.value is not None
        }
        new_nodes = current_nodes - known_nodes

        if not new_nodes:
            return ()

        known_nodes.update(new_nodes)

        coordinator = cast(
            LinksysVelopDataUpdateCoordinatorMultiUse,
            config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
        )

        nodes_by_id = {
            node.unique_id.value: node
            for node in config_entry.runtime_data.mesh.nodes
            if node.unique_id.value is not None
        }

        entities: list[LinksysVelopButtonCoordinatorEntity] = []

        for node_id in new_nodes:
            node = nodes_by_id[node_id]
            context = LinksysVelopEntityContext(unique_id=node_id)

            descriptions: tuple[LinksysVelopButtonEntityDescription, ...] = ()

            if node.type.value == NodeType.SECONDARY and has_capability(
                config_entry.runtime_data.mesh.capabilities, CAP_REBOOT
            ):
                descriptions = (
                    LinksysVelopButtonEntityDescription(
                        device_class=ButtonDeviceClass.RESTART,
                        key="",
                        name="Reboot",
                        translation_key="reboot",
                        target_type=EntityType.NODE,
                        press_fn="_async_restart_node",
                    ),
                )

            entities.extend(
                LinksysVelopButtonMultiUseEntity(
                    entity_context=context,
                    coordinator=coordinator,
                    description=description,
                )
                for description in descriptions
            )

        return tuple(entities)

    def _remove_stale_entities() -> None:
        """Remove entities that are no longer required."""

        mesh = config_entry.runtime_data.mesh
        capabilities = mesh.capabilities
        can_reboot = has_capability(capabilities, CAP_REBOOT)

        entities_to_remove = {
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::{slugify(str(entity.name))}"
            for cap, entities in ENTITIES.items()
            if not has_capability(mesh.capabilities, cap)
            for entity in entities
            if entity.target_type == EntityType.MESH
        }

        entities_to_remove.update(
            f"{node.unique_id.value}::{ENTITY_DOMAIN}::reboot"
            for node in mesh.nodes
            if node.type != NodeType.SECONDARY or not can_reboot
        )

        allow_mesh_reboot = config_entry.options.get(
            CONF_ALLOW_MESH_REBOOT,
            DEF_ALLOW_MESH_REBOOT,
        )

        if not allow_mesh_reboot or not can_reboot:
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::reboot_the_whole_mesh"
            )

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

        entities_to_add: tuple[LinksysVelopButtonCoordinatorEntity, ...] = (
            _init_node_entities()
        )

        if entities_to_add:
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


class LinksysVelopButtonEntity(ButtonEntity):
    """Base class representing a button entity."""

    entity_description: LinksysVelopButtonEntityDescription
    _entity_domain: str = ENTITY_DOMAIN


class LinksysVelopButtonMultiUseEntity(
    LinksysVelopButtonEntity, LinksysVelopMultiUseEntity
):
    """Linksys Velop button that uses the multi use DataUpdateCoordinator."""

    async def _async_delete_device(self, device: DeviceEntity) -> None:
        """Delete the device."""

        if device is not None:
            await device.async_delete()
            async_dispatcher_send(self.hass, SIGNAL_UI_PLACEHOLDER_DEVICE_UPDATE, None)
            await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)

    async def _async_restart_node(self, node: NodeEntity) -> None:
        """Restart the node."""

        if node is not None:
            await node.async_reboot()

    async def _async_start_channel_scan(self, mesh: Mesh) -> None:
        """Start the channel scan."""

        # flag as an intensive task running
        self.coordinator.config_entry.runtime_data.blocking_tasks.add(
            BlockingTasks.CHANNEL_SCAN
        )
        # force refresh so the state is picked up - it'll be rejected but the binary sensor should change status
        await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)

        # start the channel scan
        await mesh.async_start_channel_scan()

        # region #-- wait for the channel scan to finish --#
        while True:
            await asyncio.sleep(2)  # sleep first to let the scan start
            csi: dict[str, Any] | None = (
                await self.coordinator.config_entry.runtime_data.mesh.async_get_channel_scan_info()
            )
            if (
                csi is not None
                and not csi.get("isRunning", False)
                and BlockingTasks.CHANNEL_SCAN
                in self.coordinator.config_entry.runtime_data.blocking_tasks
            ):
                self.coordinator.config_entry.runtime_data.blocking_tasks.remove(
                    BlockingTasks.CHANNEL_SCAN
                )
                await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)
                break
        # endregion

    @override
    async def async_press(self) -> None:

        if isinstance(self.entity_description.press_fn, str):
            if (func := getattr(self, self.entity_description.press_fn)) is not None:
                await func(self._get_target())
        else:
            await self.entity_description.press_fn(self.coordinator)


type LinksysVelopButtonCoordinatorEntity = LinksysVelopButtonMultiUseEntity
