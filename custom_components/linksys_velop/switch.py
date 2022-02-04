"""Switches for the mesh"""
# TODO: Fix up the try/except block when setting the minimum HASS version to 2021.12
# HASS 2021.12 introduces StrEnum for DEVICE_CLASS_* constants
try:
    from homeassistant.components.switch import SwitchDeviceClass
    DEVICE_CLASS_SWITCH = SwitchDeviceClass.SWITCH
except ImportError:
    SwitchDeviceClass = None
    from homeassistant.components.switch import DEVICE_CLASS_SWITCH
    
import logging
from typing import Any, Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data_update_coordinator import LinksysVelopDataUpdateCoordinator
from .entity_helpers import (
    entity_remove,
    entity_setup,
    LinksysVelopConfigurationEntity,
    LinksysVelopMeshSwitch,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the switches from a config entry"""

    remove_binary_sensor_classes = []

    entity_remove(config=config, entity_classes=remove_binary_sensor_classes, hass=hass)

    switch_classes = [
        LinksysVelopMeshGuestWiFiSwitch,
        LinksysVelopMeshParentalControlSwitch,
    ]

    entity_setup(async_add_entities=async_add_entities, config=config, entity_classes=switch_classes, hass=hass)


# noinspection PyAbstractClass
class LinksysVelopMeshParentalControlSwitch(LinksysVelopMeshSwitch, LinksysVelopConfigurationEntity):
    """Representation of the switch entity for the Parental Control state"""

    _attribute = "Parental Control"
    _attr_device_class = DEVICE_CLASS_SWITCH
    _state_value: bool = False

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str):
        """"""

        self._coordinator: LinksysVelopDataUpdateCoordinator = coordinator

        LinksysVelopMeshSwitch.__init__(self, coordinator, identity)

    def update_state_value(self):
        """"""

        self._state_value = self._mesh.parental_control_enabled
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and set initial status"""

        self.update_state_value()
        self.async_on_remove(
            self._coordinator.async_add_listener(update_callback=self.update_state_value)
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
    def icon(self) -> str:
        """Returns the icon for the switch"""

        return "hass:account" if self.is_on else "hass:account-off"

    @property
    def is_on(self) -> bool:
        """Returns True if the switch is on, False otherwise"""

        return self._state_value


# noinspection PyAbstractClass
class LinksysVelopMeshGuestWiFiSwitch(LinksysVelopMeshSwitch, LinksysVelopConfigurationEntity):
    """Representation of the switch entity for the guest Wi-Fi state"""

    _attribute = "Guest Wi-Fi"
    _attr_device_class = DEVICE_CLASS_SWITCH
    _state_value: bool = False

    def __init__(self, coordinator: LinksysVelopDataUpdateCoordinator, identity: str):
        """"""

        self._coordinator: LinksysVelopDataUpdateCoordinator = coordinator

        LinksysVelopMeshSwitch.__init__(self, coordinator, identity)

    def update_state_value(self):
        """"""

        self._state_value = self._mesh.guest_wifi_enabled
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks and set initial status"""

        self.update_state_value()
        self.async_on_remove(
            self._coordinator.async_add_listener(update_callback=self.update_state_value)
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
