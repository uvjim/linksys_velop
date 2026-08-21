"""Button entities for Linksys Velop."""

# region #-- imports --#
import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast, override

from homeassistant.components.button import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.action_registry import Actions
from pyvelop.mesh import Mesh
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
    IntensiveTask,
)
from .coordinator import (
    CoordinatorTimers,
    CoordinatorTypes,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
    LinksysVelopDataUpdateCoordinatorSpeedtest,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
    LinksysVelopSpeedtestEntity,
)
from .helpers import remove_velop_entity_from_registry
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass(frozen=True, kw_only=True)
class LinksysVelopButtonEntityDescription(
    LinksysVelopEntityDescription, ButtonEntityDescription
):
    """Describes Velop button entity."""

    press_fn: Callable[..., Awaitable[None]] | str


async def _wait_for_mesh(mesh: Mesh, wait_for_mins: float = 5.0) -> None:
    """Wait for the mesh to become available."""

    deadline: float = time.monotonic() + (wait_for_mins * 60)

    while time.monotonic() < deadline:
        await asyncio.sleep(10)
        available: str | None = await mesh.async_ping()
        if available == "pong":
            break


async def async_restart_primary_node(config_entry: LinksysVelopConfigEntry) -> None:
    """Restart the primary node."""

    hass: HomeAssistant = async_get_hass()

    # region #-- flag as rebooting and send event --#
    config_entry.runtime_data.mesh_is_rebooting = True
    if EventSubTypes.MESH_REBOOTING.value in config_entry.options.get(
        CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
    ):
        async_dispatcher_send(
            hass,
            f"{DOMAIN}_{EventSubTypes.MESH_REBOOTING.value}",
        )
    # endregion

    # reboot
    await config_entry.runtime_data.mesh.async_reboot_mesh()

    # wait for reboot to complete.
    # If the mesh doesn't reboot within the given timeframe then there
    # will likely be timeout warnings raised in the system log.
    # Don't want to wait infinitely though because that could cause issues.
    await _wait_for_mesh(config_entry.runtime_data.mesh)

    # region #-- flag reboot complete and send event --#
    config_entry.runtime_data.mesh_is_rebooting = False
    if EventSubTypes.MESH_REBOOTED.value in config_entry.options.get(
        CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
    ):
        async_dispatcher_send(
            hass,
            f"{DOMAIN}_{EventSubTypes.MESH_REBOOTED.value}",
        )
    # endregion


async def async_start_check_for_updates(config_entry: LinksysVelopConfigEntry) -> None:
    """Start checking for updates."""

    await config_entry.runtime_data.mesh.async_check_for_updates()


async def async_start_speedtest(mesh: Mesh) -> None:
    """Start a Speedtest."""

    await mesh.async_start_speedtest()


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

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopButtonCoordinatorEntity, ...]:
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopButtonCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopButtonCoordinatorEntity] = []

        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                unique_id=ui_device
            )
            mesh_entities: list[LinksysVelopButtonEntityDescription] = []

            mesh_entities.append(
                LinksysVelopButtonEntityDescription(
                    key="",
                    name="Delete",
                    translation_key="delete",
                    target_type=EntityType.DEVICE,
                    press_fn="_async_delete_device",
                ),
            )

            ret_temp.extend(
                [
                    LinksysVelopButtonMultiUseEntity(
                        entity_context=context,
                        coordinator=cast(
                            LinksysVelopDataUpdateCoordinatorMultiUse,
                            config_entry.runtime_data.coordinators.get(
                                CoordinatorTypes.MESH
                            ),
                        ),
                        description=desc,
                    )
                    for desc in mesh_entities
                ]
            )

        ret = tuple(ret_temp)
        return ret

    def _init_mesh_entities() -> tuple[LinksysVelopButtonCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopButtonCoordinatorEntity, ...] = ()
        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )
        mesh_entities: list[LinksysVelopButtonEntityDescription] = []
        speedtest_entities: list[LinksysVelopButtonEntityDescription] = []

        if (
            Actions.GET_UPDATE_SETTINGS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopButtonEntityDescription(
                    key="",
                    name="Check for Updates",
                    translation_key="check_for_updates",
                    target_type=EntityType.MESH,
                    press_fn=async_start_check_for_updates,
                ),
            )

        if (
            Actions.GET_CHANNEL_SCAN_STATUS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopButtonEntityDescription(
                    entity_registry_enabled_default=False,
                    key="",
                    name="Start Channel Scan",
                    translation_key="channel_scan",
                    target_type=EntityType.MESH,
                    press_fn="_async_start_channel_scan",
                ),
            )

        if (
            Actions.GET_SPEEDTEST_RESULTS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            speedtest_entities.append(
                LinksysVelopButtonEntityDescription(
                    entity_registry_enabled_default=False,
                    key="",
                    name="Start Speedtest",
                    translation_key="speedtest",
                    target_type=EntityType.MESH,
                    press_fn=async_start_speedtest,
                ),
            )

        if config_entry.options.get(CONF_ALLOW_MESH_REBOOT, DEF_ALLOW_MESH_REBOOT):
            mesh_entities.append(
                LinksysVelopButtonEntityDescription(
                    device_class=ButtonDeviceClass.RESTART,
                    key="",
                    name="Reboot the Whole Mesh",
                    translation_key="reboot_mesh",
                    target_type=EntityType.MESH,
                    press_fn=async_restart_primary_node,
                ),
            )

        ret = (
            *[
                LinksysVelopButtonMultiUseEntity(
                    entity_context=context,
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorMultiUse,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.MESH
                        ),
                    ),
                    description=desc,
                )
                for desc in mesh_entities
            ],
            *[
                LinksysVelopButtonSpeedtestEntity(
                    entity_context=context,
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorSpeedtest,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.SPEEDTEST
                        ),
                    ),
                    description=desc,
                )
                for desc in speedtest_entities
            ],
        )

        return ret

    def _init_node_entities() -> tuple[LinksysVelopButtonCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""

        ret: tuple[LinksysVelopButtonCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopButtonCoordinatorEntity] = []
        current_nodes: set[str] = {
            n.unique_id
            for n in config_entry.runtime_data.mesh.nodes
            if n.unique_id is not None
        }
        new_nodes: set[str] = current_nodes - known_nodes

        if new_nodes:
            known_nodes.update(new_nodes)
            for node in new_nodes:
                mesh_entities: list[LinksysVelopButtonEntityDescription] = []
                context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                    unique_id=node
                )
                node_details: NodeEntity | None = next(
                    (
                        n
                        for n in config_entry.runtime_data.mesh.nodes
                        if n.unique_id.value == context.unique_id
                    ),
                    None,
                )

                if node_details is not None:
                    if node_details.type == NodeType.SECONDARY:
                        mesh_entities.append(
                            LinksysVelopButtonEntityDescription(
                                device_class=ButtonDeviceClass.RESTART,
                                key="",
                                name="Reboot",
                                translation_key="reboot",
                                target_type=EntityType.NODE,
                                press_fn="_async_restart_node",
                            )
                        )

                ret_temp.extend(
                    [
                        LinksysVelopButtonMultiUseEntity(
                            entity_context=context,
                            coordinator=cast(
                                LinksysVelopDataUpdateCoordinatorMultiUse,
                                config_entry.runtime_data.coordinators.get(
                                    CoordinatorTypes.MESH
                                ),
                            ),
                            description=desc,
                        )
                        for desc in mesh_entities
                    ]
                )

        ret = tuple(ret_temp)
        return ret

    def _remove_stale_entities() -> None:
        """Remove entities is they are no longer required."""

        entities_to_remove: set[str] = set()

        # region #-- remove unnecessary node entities --#
        for node in config_entry.runtime_data.mesh.nodes:
            if node.type != NodeType.SECONDARY:
                entities_to_remove.add(f"{node.unique_id}::{ENTITY_DOMAIN}::reboot")
        # endregion

        if (
            Actions.GET_UPDATE_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::check_for_updates"
            )

        if (
            Actions.GET_CHANNEL_SCAN_STATUS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::start_channel_scan"
            )

        if (
            Actions.GET_SPEEDTEST_RESULTS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::start_speedtest"
            )

        if not config_entry.options.get(CONF_ALLOW_MESH_REBOOT, DEF_ALLOW_MESH_REBOOT):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::reboot_the_whole_mesh"
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

        entities_to_add: tuple[LinksysVelopButtonCoordinatorEntity, ...] = (
            _init_node_entities()
        )

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
        self.coordinator.config_entry.runtime_data.intensive_running_tasks.append(
            IntensiveTask.CHANNEL_SCAN
        )
        # force refresh so the state is picked up - it'll be debounced but the binary sesnor should change status
        await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)

        # start the channel scan
        await mesh.async_start_channel_scan()

        # region #-- wait for the channel scan to finish --#
        while True:
            await asyncio.sleep(2)  # sleep first to let the scan start
            csi: dict[str, Any] | None = (
                await self.coordinator.config_entry.runtime_data.mesh.async_get_channel_scan_info()
            )
            if csi is not None and not csi.get("isRunning", False):
                if (
                    IntensiveTask.CHANNEL_SCAN
                    in self.coordinator.config_entry.runtime_data.intensive_running_tasks
                ):
                    self.coordinator.config_entry.runtime_data.intensive_running_tasks.remove(
                        IntensiveTask.CHANNEL_SCAN
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
            await self.entity_description.press_fn(self.coordinator.config_entry)


class LinksysVelopButtonSpeedtestEntity(
    LinksysVelopButtonEntity, LinksysVelopSpeedtestEntity
):
    """Linksys Velop button that uses the Speedtest DataUpdateCoordinator."""

    @override
    async def async_press(self) -> None:

        if isinstance(self.entity_description.press_fn, str):
            if (func := getattr(self, self.entity_description.press_fn)) is not None:
                func(self.coordinator.config_entry.runtime_data.mesh)
        else:
            await self.entity_description.press_fn(
                self.coordinator.config_entry.runtime_data.mesh
            )
        await self.coordinator.async_refresh()


type LinksysVelopButtonCoordinatorEntity = LinksysVelopButtonMultiUseEntity | LinksysVelopButtonSpeedtestEntity
