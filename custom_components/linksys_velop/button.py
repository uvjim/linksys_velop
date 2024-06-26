"""Buttons for the mesh, nodes and devices."""

# region #-- imports --#
from __future__ import annotations

import dataclasses
import logging
from abc import ABC
from typing import Callable, List

from homeassistant.components.button import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.mesh import Mesh
from pyvelop.node import Node, NodeType

from . import (
    LinksysVelopDeviceEntity,
    LinksysVelopMeshEntity,
    LinksysVelopNodeEntity,
    entity_cleanup,
)
from .const import (
    CONF_ALLOW_MESH_REBOOT,
    CONF_COORDINATOR,
    CONF_DEVICE_UI,
    DEF_ALLOW_MESH_REBOOT,
    DEF_UI_DEVICE_ID,
    DOMAIN,
    SIGNAL_UPDATE_CHANNEL_SCANNING,
    SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- button entity descriptions --#
@dataclasses.dataclass(frozen=True)
class AdditionalButtonDescription:
    """Represent the additional attributes of the button description."""

    press_action: str
    press_action_arguments: dict | Callable = dataclasses.field(default_factory=dict)


# endregion


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    buttons: List[
        LinksysVelopDeviceButton | LinksysVelopMeshButton | LinksysVelopNodeButton
    ] = []
    buttons_to_remove: List[
        LinksysVelopDeviceButton | LinksysVelopMeshButton | LinksysVelopNodeButton
    ] = []

    # region #-- Device button --#
    for device_id in config_entry.options.get(CONF_DEVICE_UI, []):
        buttons.extend(
            [
                LinksysVelopDeviceButton(
                    additional_description=AdditionalButtonDescription(
                        press_action="async_delete_device_by_id",
                        press_action_arguments=lambda d: {
                            "device": d.unique_id,
                            "signal": SIGNAL_UPDATE_PLACEHOLDER_UI_DEVICE,
                            "signal_arguments": [DEF_UI_DEVICE_ID],
                        },
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=ButtonEntityDescription(
                        icon="mdi:delete",
                        key="",
                        name="Delete",
                        translation_key="delete",
                    ),
                    device_id=device_id,
                )
            ]
        )
    # endregion

    # region #-- Mesh buttons --#
    buttons.extend(
        [
            LinksysVelopMeshButton(
                additional_description=AdditionalButtonDescription(
                    press_action="async_check_for_updates",
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=ButtonEntityDescription(
                    icon="hass:update",
                    key="",
                    name="Check for Updates",
                    translation_key="check_for_updates",
                ),
            ),
            LinksysVelopMeshButton(
                additional_description=AdditionalButtonDescription(
                    press_action="async_start_channel_scan",
                    press_action_arguments={"signal": SIGNAL_UPDATE_CHANNEL_SCANNING},
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=ButtonEntityDescription(
                    icon="mdi:wifi-sync",
                    key="",
                    name="Start Channel Scan",
                    translation_key="channel_scan",
                ),
            ),
            LinksysVelopMeshButton(
                additional_description=AdditionalButtonDescription(
                    press_action="async_start_speedtest",
                    press_action_arguments={"signal": SIGNAL_UPDATE_SPEEDTEST_STATUS},
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=ButtonEntityDescription(
                    icon="hass:refresh",
                    key="",
                    name="Start Speedtest",
                    translation_key="speedtest",
                ),
            ),
        ]
    )
    # region #-- add conditional mesh buttons --#
    primary_node: Node | List[Node] = [node for node in mesh.nodes if node.type == NodeType.PRIMARY]
    if primary_node:
        primary_node = primary_node[0]
    if config_entry.options.get(CONF_ALLOW_MESH_REBOOT, DEF_ALLOW_MESH_REBOOT):
        buttons.append(
            LinksysVelopMeshButton(
                additional_description=AdditionalButtonDescription(
                    press_action="async_reboot_node",
                    press_action_arguments={"node_name": primary_node.name, "force": True},
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=ButtonEntityDescription(
                    device_class=ButtonDeviceClass.RESTART,
                    key="",
                    name="Reboot the Whole Mesh",
                    translation_key="reboot_mesh",
                ),
            )
        )
    else:
        buttons_to_remove.append(
            LinksysVelopMeshButton(
                config_entry=config_entry,
                coordinator=coordinator,
                description=ButtonEntityDescription(
                    key="",
                    name="Reboot the Whole Mesh",
                    translation_key="reboot_mesh",
                ),
            )
        )
    # endregion
    # endregion

    # region #-- Node buttons --#
    node: Node
    for node in mesh.nodes:
        if node.type.lower() != "primary":
            buttons.append(
                LinksysVelopNodeButton(
                    additional_description=AdditionalButtonDescription(
                        press_action="async_reboot_node",
                        press_action_arguments={"node_name": node.name},
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=ButtonEntityDescription(
                        key="",
                        device_class=ButtonDeviceClass.RESTART,
                        name="Reboot",
                        translation_key="reboot",
                    ),
                )
            )
    # endregion

    async_add_entities(buttons)

    if buttons_to_remove:
        entity_cleanup(config_entry=config_entry, entities=buttons_to_remove, hass=hass)


async def _async_button_pressed(
    action: str,
    hass: HomeAssistant,
    mesh: Mesh,
    action_arguments: dict | None = None,
):
    """Carry out the button press action."""
    action: Callable | None = getattr(mesh, action, None)
    signal: str = action_arguments.pop("signal", None)
    signal_arguments: list = action_arguments.pop("signal_arguments", [])
    if action and isinstance(action, Callable):
        if action_arguments is None:
            action_arguments = {}
        await action(**action_arguments)
        if signal is not None:
            async_dispatcher_send(hass, signal, *signal_arguments)


class LinksysVelopDeviceButton(LinksysVelopDeviceEntity, ButtonEntity, ABC):
    """Representation of a device button."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: ButtonEntityDescription,
        device_id: str,
        additional_description: AdditionalButtonDescription | None = None,
    ) -> None:
        """Initialise."""
        self._additional_description: AdditionalButtonDescription | None = (
            additional_description
        )
        self.entity_domain = ENTITY_DOMAIN
        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            device_id=device_id,
        )

    async def async_press(self) -> None:
        """Handle the button being pressed."""
        if self._additional_description is not None:
            if isinstance(
                self._additional_description.press_action_arguments, Callable
            ):
                action_args = self._additional_description.press_action_arguments(
                    self._device
                )
            else:
                action_args = self._additional_description.press_action_arguments.copy()

            await _async_button_pressed(
                action=self._additional_description.press_action,
                action_arguments=action_args,
                hass=self.hass,
                mesh=self._mesh,
            )


class LinksysVelopMeshButton(LinksysVelopMeshEntity, ButtonEntity, ABC):
    """Representation for a button in the Mesh."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: ButtonEntityDescription,
        additional_description: AdditionalButtonDescription | None = None,
    ) -> None:
        """Initialise."""
        self._additional_description: AdditionalButtonDescription | None = (
            additional_description
        )
        self.entity_domain = ENTITY_DOMAIN
        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    async def async_press(self) -> None:
        """Handle the button being pressed."""
        if self._additional_description is not None:
            await _async_button_pressed(
                action=self._additional_description.press_action,
                action_arguments=self._additional_description.press_action_arguments.copy(),
                hass=self.hass,
                mesh=self._mesh,
            )


class LinksysVelopNodeButton(LinksysVelopNodeEntity, ButtonEntity, ABC):
    """Representation for a button related to a node."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: ButtonEntityDescription,
        additional_description: AdditionalButtonDescription | None = None,
    ) -> None:
        """Intialise."""
        self._additional_description: AdditionalButtonDescription | None = (
            additional_description
        )
        self.entity_domain = ENTITY_DOMAIN
        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            node=node,
        )

    async def async_press(self) -> None:
        """Handle the button being pressed."""
        if self._additional_description is not None:
            await _async_button_pressed(
                action=self._additional_description.press_action,
                action_arguments=self._additional_description.press_action_arguments.copy(),
                hass=self.hass,
                mesh=self._mesh,
            )
