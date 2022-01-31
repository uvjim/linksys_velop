""""""

# region #-- imports --#
import logging
from abc import ABC
from typing import Optional

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.node import Node

from .entity_helpers import (
    entity_setup,
    LinksysVelopNodeButton,
)

# endregion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """"""

    button_classes = [
        LinksysVelopNodeRebootButton,
    ]

    entity_setup(
        async_add_entities=async_add_entities,
        config=config,
        entity_classes=button_classes,
        hass=hass,
    )


class LinksysVelopNodeRebootButton(LinksysVelopNodeButton, ABC):
    """"""

    _attribute = "Reboot"

    async def async_press(self) -> None:
        """"""

        node: Node = self._get_node()
        await self._mesh.async_reboot_node(node_name=node.name)

    # region #-- properties --#
    @property
    def device_class(self) -> Optional[ButtonDeviceClass]:
        """"""

        return ButtonDeviceClass.RESTART
    # endregion
