""""""

# region #-- imports --#
import logging
from abc import ABC
from typing import Optional

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .entity_helpers import (
    entity_setup,
    LinksysVelopMeshButton,
    LinksysVelopNodeButton,
)

# endregion

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """"""

    button_classes = [
        LinksysVelopMeshCheckForUpdates,
        LinksysVelopMeshStartSpeedtest,
        LinksysVelopNodeRebootButton,
    ]

    entity_setup(
        async_add_entities=async_add_entities,
        config=config,
        entity_classes=button_classes,
        hass=hass,
    )


class LinksysVelopMeshCheckForUpdates(LinksysVelopMeshButton, ABC):
    """"""

    _attribute: str = "Check for Updates"

    async def async_press(self) -> None:
        """"""

        await self._mesh.async_check_for_updates()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS)

    # region #-- properties --#
    @property
    def device_class(self) -> Optional[ButtonDeviceClass]:
        """"""

        return None
    # endregion


class LinksysVelopMeshStartSpeedtest(LinksysVelopMeshButton, ABC):
    """"""

    _attribute: str = "Start Speedtest"

    async def async_press(self) -> None:
        """"""

        await self._mesh.async_start_speedtest()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)

    # region #-- properties --#
    @property
    def device_class(self) -> Optional[ButtonDeviceClass]:
        """"""

        return None
    # endregion


class LinksysVelopNodeRebootButton(LinksysVelopNodeButton, ABC):
    """"""

    _attribute = "Reboot"

    async def async_press(self) -> None:
        """"""

        await self._mesh.async_reboot_node(node_name=self._node.name)

    # region #-- properties --#
    @property
    def device_class(self) -> Optional[ButtonDeviceClass]:
        """"""

        return ButtonDeviceClass.RESTART
    # endregion
