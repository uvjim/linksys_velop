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
from pyvelop.node import Node

from . import LinksysVelopMeshEntity, LinksysVelopNodeEntity, entity_cleanup
from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    SIGNAL_UPDATE_CHANNEL_SCANNING,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- button entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the button description."""

    press_action_arguments: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the button description."""

    press_action: str


@dataclasses.dataclass
class LinksysVelopButtonDescription(
    OptionalLinksysVelopDescription,
    ButtonEntityDescription,
    RequiredLinksysVelopDescription,
):
    """Describes button entity."""


# endregion


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    buttons: List[LinksysVelopMeshButton | LinksysVelopNodeButton] = []
    buttons_to_remove: List[LinksysVelopMeshButton | LinksysVelopNodeButton] = []

    # region #-- Mesh buttons --#
    mesh_button_descriptions: tuple[LinksysVelopButtonDescription, ...] = (
        LinksysVelopButtonDescription(
            icon="hass:update",
            key="",
            name="Check for Updates",
            press_action="async_check_for_updates",
        ),
        LinksysVelopButtonDescription(
            icon="mdi:wifi-sync",
            key="",
            name="Start Channel Scan",
            press_action="async_start_channel_scan",
            press_action_arguments={"signal": SIGNAL_UPDATE_CHANNEL_SCANNING},
        ),
        LinksysVelopButtonDescription(
            icon="hass:refresh",
            key="",
            name="Start Speedtest",
            press_action="async_start_speedtest",
            press_action_arguments={"signal": SIGNAL_UPDATE_SPEEDTEST_STATUS},
        ),
    )

    for button_description in mesh_button_descriptions:
        buttons.append(
            LinksysVelopMeshButton(
                config_entry=config_entry,
                coordinator=coordinator,
                description=button_description,
            )
        )

    # endregion

    # region #-- Node buttons --#
    node: Node
    for node in mesh.nodes:
        if node.type.lower() != "primary":
            buttons.append(
                LinksysVelopNodeButton(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopButtonDescription(
                        key="",
                        device_class=ButtonDeviceClass.RESTART,
                        name="Reboot",
                        press_action="async_reboot_node",
                        press_action_arguments={"node_name": node.name},
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
    if action and isinstance(action, Callable):
        if action_arguments is None:
            action_arguments = {}
        await action(**action_arguments)
        if signal:
            async_dispatcher_send(hass, signal)


class LinksysVelopMeshButton(LinksysVelopMeshEntity, ButtonEntity, ABC):
    """Representation for a button in the Mesh."""

    entity_description: LinksysVelopButtonDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopButtonDescription,
    ) -> None:
        """Initialise."""
        self.entity_domain = ENTITY_DOMAIN
        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    async def async_press(self) -> None:
        """Handle the button being pressed."""
        await _async_button_pressed(
            action=self.entity_description.press_action,
            action_arguments=self.entity_description.press_action_arguments.copy(),
            hass=self.hass,
            mesh=self._mesh,
        )


class LinksysVelopNodeButton(LinksysVelopNodeEntity, ButtonEntity, ABC):
    """Representation for a button related to a node."""

    entity_description: LinksysVelopButtonDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: LinksysVelopButtonDescription,
    ) -> None:
        """Intialise."""
        self.entity_domain = ENTITY_DOMAIN
        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            node=node,
        )

    async def async_press(self) -> None:
        """Handle the button being pressed."""
        await _async_button_pressed(
            action=self.entity_description.press_action,
            action_arguments=self.entity_description.press_action_arguments.copy(),
            hass=self.hass,
            mesh=self._mesh,
        )
