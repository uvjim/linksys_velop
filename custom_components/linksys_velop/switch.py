"""Switches for the mesh"""

import logging
from datetime import datetime
from typing import Any, Union, Mapping

from homeassistant.components.switch import DEVICE_CLASS_SWITCH
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# TODO: Remove the try/except block when setting the minimum HASS version to 2021.11
try:
    from homeassistant.const import (
        ENTITY_CATEGORY_CONFIG,
        ENTITY_CATEGORY_DIAGNOSTIC,
    )
except ImportError:
    ENTITY_CATEGORY_CONFIG: str = ""
    ENTITY_CATEGORY_DIAGNOSTIC: str = ""

from .const import (
    SIGNAL_UPDATE_PARENTAL_CONTROL_STATUS,
)
from .entity_helpers import (
    entity_setup,
    LinksysVelopMeshSwitch,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup the switches from a config entry"""

    switch_classes = [
        LinksysVelopMeshGuestWiFiSwitch,
        LinksysVelopMeshParentalControlSwitch,
    ]

    entity_setup(
        async_add_entities=async_add_entities,
        config=config,
        entity_classes=switch_classes,
        hass=hass,
    )


# noinspection PyAbstractClass
class LinksysVelopMeshParentalControlSwitch(LinksysVelopMeshSwitch):
    """Representation of the switch entity for the Parental Control state"""

    _attribute = "Parental Control"
    _attr_device_class = DEVICE_CLASS_SWITCH
    _state_value: bool = False

    @callback
    async def async_update_callback(self, _: Union[datetime, None] = None):
        """Update the state of the switch"""

        self._state_value = self._mesh.parental_control_enabled
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and set initial status"""

        self._state_value = self._mesh.parental_control_enabled
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_PARENTAL_CONTROL_STATUS,
                target=self.async_update_callback,
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off"""

        to_state: bool = False
        await self._mesh.async_set_parental_control_state(state=to_state)
        self._state_value = to_state
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on"""

        to_state: bool = True
        await self._mesh.async_set_parental_control_state(state=to_state)
        self._state_value = to_state
        self.async_schedule_update_ha_state()

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_CONFIG

    @property
    def icon(self) -> str:
        """Returns the icon for the switch"""

        return "hass:account" if self.is_on else "hass:account-off"

    @property
    def is_on(self) -> bool:
        """Returns True if the switch is on, False otherwise"""

        return self._state_value


# noinspection PyAbstractClass
class LinksysVelopMeshGuestWiFiSwitch(LinksysVelopMeshSwitch):
    """Representation of the switch entity for the guest Wi-Fi state"""

    _attribute = "Guest Wi-Fi"
    _attr_device_class = DEVICE_CLASS_SWITCH
    _state_value: bool = False

    @callback
    async def async_update_callback(self, _: Union[datetime, None] = None):
        """Update the state of the switch"""

        self._state_value = self._mesh.guest_wifi_enabled
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and set initial status"""

        self._state_value = self._mesh.guest_wifi_enabled
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_PARENTAL_CONTROL_STATUS,
                target=self.async_update_callback,
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off"""

        to_state: bool = False
        await self._mesh.async_set_guest_wifi_state(state=to_state)
        self._state_value = to_state
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on"""

        to_state: bool = True
        await self._mesh.async_set_guest_wifi_state(state=to_state)
        self._state_value = to_state
        self.async_schedule_update_ha_state()

    @property
    def entity_category(self) -> Union[str, None]:
        return ENTITY_CATEGORY_CONFIG

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Set additional attributes detailing the available guest networks"""

        ret = {
            f"network {idx}": network
            for idx, network in enumerate(self._mesh.guest_wifi_details)
        }
        return ret

    @property
    def icon(self) -> str:
        """Returns the icon for the switch"""

        return "hass:wifi" if self.is_on else "hass:wifi-off"

    @property
    def is_on(self) -> bool:
        """Returns True if the switch is on, False otherwise"""

        return self._state_value
