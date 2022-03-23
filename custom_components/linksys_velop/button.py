""""""

# region #-- imports --#
import dataclasses
import logging
from abc import ABC
from typing import (
    Callable,
    List,
    Optional,
    Union,
)

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
    DOMAIN as ENTITY_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from . import (
    entity_cleanup,
    LinksysVelopMeshEntity,
    LinksysVelopNodeEntity,
)

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    ENTITY_SLUG,
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- button entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the button description."""

    press_action_arguments: Optional[dict] = dict


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the button description."""

    press_action: str


@dataclasses.dataclass
class LinksysVelopButtonDescription(
    OptionalLinksysVelopDescription,
    ButtonEntityDescription,
    RequiredLinksysVelopDescription
):
    """Describes button entity"""
# endregion


BUTTON_DESCRIPTIONS: tuple[LinksysVelopButtonDescription, ...] = (
    LinksysVelopButtonDescription(
        icon="hass:update",
        key="",
        name="Check for Updates",
        press_action="async_check_for_updates",
        press_action_arguments={
            "signal": SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS
        }
    ),
    LinksysVelopButtonDescription(
        icon="hass:refresh",
        key="",
        name="Start Speedtest",
        press_action="async_start_speedtest",
        press_action_arguments={
            "signal": SIGNAL_UPDATE_SPEEDTEST_STATUS
        }
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """"""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data

    buttons: List[Union[LinksysVelopMeshButton, LinksysVelopNodeButton]] = [
        LinksysVelopMeshButton(
            config_entry=config_entry,
            coordinator=coordinator,
            description=button_description,
        )
        for button_description in BUTTON_DESCRIPTIONS
    ]

    # region #-- node buttons --#
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
                        press_action_arguments={
                            "node_name": node.name
                        }
                    )
                )
            )
    # endregion

    async_add_entities(buttons)

    buttons_to_remove: List = []
    if buttons_to_remove:
        entity_cleanup(config_entry=config_entry, entities=buttons_to_remove, hass=hass)


class LinksysVelopMeshButton(LinksysVelopMeshEntity, ButtonEntity, ABC):
    """Representation for a button in the Mesh"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopButtonDescription
    ) -> None:
        """Constructor"""

        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self.entity_description: LinksysVelopButtonDescription = description

        self._attr_name = f"{ENTITY_SLUG} Mesh: {self.entity_description.name}"
        self._attr_unique_id = f"{config_entry.entry_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    async def async_press(self) -> None:
        """Handle the button being pressed"""

        action: Optional[Callable] = getattr(self._mesh, self.entity_description.press_action, None)
        action_arguments = self.entity_description.press_action_arguments.copy()
        signal: str = action_arguments.pop("signal", None)
        if action and isinstance(action, Callable):
            await action(**action_arguments)
            if signal:
                async_dispatcher_send(self.hass, signal)


class LinksysVelopNodeButton(LinksysVelopNodeEntity, ButtonEntity, ABC):
    """Representation for a button related to a node"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: LinksysVelopButtonDescription
    ) -> None:
        """Constructor"""

        self._node_id: str = node.unique_id
        super().__init__(config_entry=config_entry, coordinator=coordinator)

        self.entity_description: LinksysVelopButtonDescription = description

        self._attr_name = f"{ENTITY_SLUG} {self._node.name}: {self.entity_description.name}"
        self._attr_unique_id = f"{self._node.unique_id}::" \
                               f"{ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    async def async_press(self) -> None:
        """Handle the button being pressed"""

        action: Optional[Callable] = getattr(self._mesh, self.entity_description.press_action, None)
        action_arguments = self.entity_description.press_action_arguments.copy()
        signal: str = action_arguments.pop("signal", None)
        if action and isinstance(action, Callable):
            await action(**action_arguments)
            if signal:
                async_dispatcher_send(self.hass, signal)
