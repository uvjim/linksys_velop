"""Device triggers."""

# region #-- imports --#
from __future__ import annotations

from typing import Dict, List

import voluptuous as vol
from homeassistant.components.device_automation import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    DEVICE_TRIGGER_BASE_SCHEMA,
)
from homeassistant.components.device_automation.exceptions import DeviceNotFound
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.config_entries import device_registry as dr
from homeassistant.const import CONF_EVENT, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SUBTYPE, DOMAIN
from .events import EVENT_TYPE, EventSubType
from .helpers import dr_device_is_mesh

# endregion

TRIGGER_TYPES: List[str] = list(EventSubType.__members__.values())

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: EVENT_TYPE,
            event_trigger.CONF_EVENT_DATA: {
                CONF_SUBTYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> List[Dict[str, str]]:
    """Return a list of triggers."""
    device_registry: dr.DeviceRegistry = dr.async_get(hass=hass)
    device: dr.DeviceEntry = device_registry.async_get(device_id)
    if device is None:
        raise DeviceNotFound(f"Device ID {device_id} is not valid")

    if dr_device_is_mesh(device=device):
        return [
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: trigger_type,
            }
            for trigger_type in TRIGGER_TYPES
        ]

    return []
