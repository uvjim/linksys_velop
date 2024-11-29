"""Repairs."""

# region #-- imports --#
import copy
import logging

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_UI_DEVICES,
    ISSUE_MISSING_DEVICE_TRACKER,
    ISSUE_MISSING_NODE,
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

    if issue_id.startswith(ISSUE_MISSING_NODE):
        return IssueMissingNodeRepairFlow()

    if issue_id.startswith(ISSUE_MISSING_UI_DEVICE):
        return IssueMissingUIDeviceRepairFlow()


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
            entity_registry: er.EntityRegistry = er.async_get(hass=self.hass)
            tracker_entity: er.RegistryEntry
            if (
                tracker_entity := entity_registry.async_get(self.data.get("device_id"))
            ) is not None:
                # region #-- disassociate mac with mesh --#
                if (
                    tracker_state := self.hass.states.get(tracker_entity.entity_id)
                ) is not None:
                    tracker_mac: str
                    if (tracker_mac := tracker_state.attributes.get("mac")) is not None:
                        device_registry: dr.DeviceRegistry = dr.async_get(self.hass)
                        mesh_device: dr.DeviceEntry
                        if (
                            mesh_device := device_registry.async_get(
                                tracker_entity.device_id
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
            description_placeholders={"device_name": self.data.get("device_name")},
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
            remove_velop_device_from_registry(self.hass, self.data.get("device_id"))

            # -- cleanup the config entry --#
            new_options = copy.deepcopy(dict(**self.data.get("config_entry").options))
            if self.data.get("device_id") in new_options.get(CONF_UI_DEVICES, []):
                new_options.get(CONF_UI_DEVICES).remove(self.data.get("device_id"))
                self.hass.config_entries.async_update_entry(
                    self.data.get("config_entry"), options=new_options
                )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm_removal",
            data_schema=vol.Schema({}),
            description_placeholders={"device_name": self.data.get("device_name")},
        )


class IssueMissingNodeRepairFlow(RepairsFlow):
    """Handler for fixing a missing node."""

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
            remove_velop_device_from_registry(self.hass, self.data.get("device_id"))

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm_removal",
            data_schema=vol.Schema({}),
            description_placeholders={"device_name": self.data.get("device_name")},
        )
