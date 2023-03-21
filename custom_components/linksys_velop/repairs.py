"""Repairs."""
# region #-- imports --#
from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import device_registry as dr
from homeassistant.config_entries import entity_registry as er
from .const import ISSUE_MISSING_DEVICE_TRACKER, ISSUE_MISSING_UI_DEVICE

# endregion


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == ISSUE_MISSING_DEVICE_TRACKER:
        return IssueMissingDeviceTrackerRepairFlow()

    if issue_id == ISSUE_MISSING_UI_DEVICE:
        return IssueMissingUIDeviceRepairFlow()


class IssueMissingDeviceTrackerRepairFlow(RepairsFlow):
    """Handler for fixing a device tracker."""

    async def async_step_init(
        self, _: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await (self.async_step_confirm_removal())

    async def async_step_confirm_removal(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            entity_registry: er.EntityRegistry = er.async_get(hass=self.hass)
            if (
                entity_registry.async_get(entity_id=self.data.get("device_id"))
                is not None
            ):
                entity_registry.async_remove(entity_id=self.data.get("device_id"))
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm_removal",
            data_schema=vol.Schema({}),
            description_placeholders={"device_name": self.data.get("device_name")},
        )


class IssueMissingUIDeviceRepairFlow(RepairsFlow):
    """Handler for fixing a missing UI device."""

    async def async_step_init(
        self, _: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await (self.async_step_confirm_removal())

    async def async_step_confirm_removal(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            device_registry: dr.DeviceRegistry = dr.async_get(hass=self.hass)
            device_registry.async_remove_device(device_id=self.data.get("device_id"))
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm_removal",
            data_schema=vol.Schema({}),
            description_placeholders={"device_name": self.data.get("device_name")},
        )
