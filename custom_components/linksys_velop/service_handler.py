"""Manage the services for the pyvelop integration"""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pyvelop.mesh import Mesh

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS
)


class LinksysVelopServiceHandler:
    """"""

    SERVICES = {
        "check_updates": {},
        "delete_device": {
            "schema":
                vol.Schema(
                    {
                        vol.Optional("device_id"): str,
                        vol.Optional("device_name"): str
                    }
                )
        },
        "reboot_node": {
            "schema":
                vol.Schema(
                    {
                        vol.Required("node_name"): str,
                        vol.Optional("is_primary"): bool,
                    }
                )
        },
        "start_speedtest": {},
    }

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Constructor"""

        self._hass = hass
        self._config_entry = config_entry
        self._mesh: Mesh = self._hass.data[DOMAIN][self._config_entry.entry_id][CONF_COORDINATOR].data

    async def service_call(self, call: ServiceCall):
        """Call the required method based on the given argument

        :param call: the service call that should be made
        :return: None
        """

        method = getattr(self, call.service)
        await method(**call.data)

    def register_services(self) -> None:
        """Register the services"""

        for service_name, service_details in self.SERVICES.items():
            self._hass.services.async_register(
                domain=DOMAIN,
                service=service_name,
                service_func=self.service_call,
                schema=service_details.get("schema", None),
            )

    def unregister_services(self) -> None:
        """Unregister the services"""

        for service_name, service_details in self.SERVICES.items():
            self._hass.services.async_remove(domain=DOMAIN, service=service_name)

    async def delete_device(self, **kwargs) -> None:
        """Remove a device from the device list on the mesh"""
        await self._mesh.async_delete_device(**kwargs)

    async def reboot_node(self, **kwargs) -> None:
        """Instruct the mesg to restart a node

        N.B. Rebooting the primary node will cause all ndoes to reboot. To reboot the primary node you should also
        turn the is_primary toggle on.

        :return:None
        """
        await self._mesh.async_reboot_node(node_name=kwargs.get("node_name", ""), force=kwargs.get("is_primary", False))

    async def start_speedtest(self) -> None:
        """Start a Speedtest on the mesh

        The Speedtest is a long-running task so a signal is also sent to listeners to update the status more
        frequently.  This allows seeing the stages of the test in the UI.

        :return:None
        """

        await self._mesh.async_start_speedtest()
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)

    async def check_updates(self) -> None:
        """Instruct the mesh to check for updates

        The update check could be a long-running task so a signal is also sent to listeners to update the status more
        frequently.  This allows a more reactive UI but also paves the way for status messages later.

        :return: None
        """

        await self._mesh.async_check_for_updates()
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS)
