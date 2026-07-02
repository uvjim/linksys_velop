"""Repairs."""

# region #-- imports --#
import copy
import logging
from typing import cast

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_UI_DEVICES,
    ISSUE_MISSING_DEVICE_TRACKER,
    ISSUE_MISSING_UI_DEVICE,
)
from .helpers import remove_velop_device_from_registry

# endregion


_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith(ISSUE_MISSING_DEVICE_TRACKER):
        return IssueMissingDeviceTrackerRepairFlow()

    if issue_id.startswith(ISSUE_MISSING_UI_DEVICE):
        return IssueMissingUIDeviceRepairFlow()

    raise ValueError(f"unknown repair {issue_id}")


class IssueMissingDeviceTrackerRepairFlow(RepairsFlow):
    """Handler for fixing a device tracker."""

    async def async_step_init(
        self, _: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm_removal()

    async def async_step_confirm_removal(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            entity_registry: er.EntityRegistry = er.async_get(self.hass)
            tracker_entity: er.RegistryEntry | None
            if (
                tracker_entity := entity_registry.async_get(
                    str(cast(dict, self.data).get("device_id"))
                )
            ) is not None:
                # region #-- disassociate mac with mesh --#
                if (
                    tracker_state := self.hass.states.get(tracker_entity.entity_id)
                ) is not None:
                    tracker_mac: str | None
                    if (tracker_mac := tracker_state.attributes.get("mac")) is not None:
                        device_registry: dr.DeviceRegistry = dr.async_get(self.hass)
                        mesh_device: dr.DeviceEntry | None
                        if (
                            mesh_device := device_registry.async_get(
                                str(tracker_entity.device_id)
                            )
                        ) is not None:
                            connections: set[tuple[str, str]] = mesh_device.connections
                            connections.discard(
                                (
                                    dr.CONNECTION_NETWORK_MAC,
                                    dr.format_mac(tracker_mac),
                                )
                            )
                            device_registry.async_update_device(
                                mesh_device.id,
                                new_connections=connections,
                            )
                # endregion
                # region #-- remove entity from registry --#
                entity_registry.async_remove(tracker_entity.entity_id)
                # endregion

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm_removal",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device_name": str(cast(dict, self.data).get("device_name", ""))
            },
        )


class IssueMissingUIDeviceRepairFlow(RepairsFlow):
    """Handler for fixing a missing UI device."""

    async def async_step_init(
        self, _: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm_removal()

    async def async_step_confirm_removal(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            # -- remove from the registry --#
            remove_velop_device_from_registry(
                self.hass, str(cast(dict, self.data).get("device_id"))
            )

            # -- cleanup the config entry --#
            config_entry: ConfigEntry | None = self.hass.config_entries.async_get_entry(
                str(cast(dict, self.data).get("config_entry", ""))
            )
            if config_entry is not None:
                new_options = copy.deepcopy(config_entry.options)
                if cast(dict, self.data).get("device_id") in new_options.get(
                    CONF_UI_DEVICES, []
                ):
                    new_options.get(CONF_UI_DEVICES, {}).remove(
                        cast(dict, self.data).get("device_id")
                    )
                    self.hass.config_entries.async_update_entry(
                        cast(dict, self.data).get("config_entry", {}),
                        options=new_options,
                    )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm_removal",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device_name": cast(dict, self.data).get("device_name", "")
            },
        )
