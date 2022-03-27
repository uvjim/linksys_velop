"""Manage the services for the pyvelop integration"""
import logging
from typing import (
    List,
    Optional,
)

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pyvelop.mesh import Mesh

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS
)
from .logger import VelopLogger

_LOGGER = logging.getLogger(__name__)


class LinksysVelopServiceHandler:
    """"""

    SERVICES = {
        "check_updates": {
            "schema":
                vol.Schema(
                    {
                        vol.Required("mesh"): str,
                    }
                )
        },
        "delete_device": {
            "schema":
                vol.Schema(
                    {
                        vol.Required("mesh"): str,
                        vol.Optional("device_id"): str,
                        vol.Optional("device_name"): str
                    }
                )
        },
        "reboot_node": {
            "schema":
                vol.Schema(
                    {
                        vol.Required("mesh"): str,
                        vol.Required("node_name"): str,
                        vol.Optional("is_primary"): bool,
                    }
                )
        },
        "start_speedtest": {
            "schema":
                vol.Schema(
                    {
                        vol.Required("mesh"): str,
                    }
                )
        },
    }

    def __init__(self, hass: HomeAssistant) -> None:
        """Constructor"""

        self._hass: HomeAssistant = hass
        self._log_formatter: VelopLogger = VelopLogger()
        self._mesh: Optional[Mesh] = None

    def _get_mesh(self, mesh_id: str) -> Optional[Mesh]:
        """Get the Mesh class for the service call to operate against

        :param mesh_id: the device id of the mesh
        :return: the Mesh class or None
        """

        device_registry: dr.DeviceRegistry = dr.async_get(hass=self._hass)
        device: List[dr.DeviceEntry] = [d for i, d in device_registry.devices.items() if i == mesh_id]
        ce: Optional[str] = None
        if device:
            for ce in device[0].config_entries:
                config_entry: ConfigEntry = self._hass.config_entries.async_get_entry(entry_id=ce)
                if config_entry.domain == DOMAIN:
                    self._log_formatter = VelopLogger(unique_id=config_entry.unique_id)
                    break
            else:
                ce = None

        ret = self._hass.data[DOMAIN][ce][CONF_COORDINATOR].data if ce else None

        return ret

    async def _async_service_call(self, call: ServiceCall):
        """Call the required method based on the given argument

        :param call: the service call that should be made
        :return: None
        """

        _LOGGER.debug(self._log_formatter.message_format("entered, call: %s"), call)

        args = call.data.copy()
        self._mesh = self._get_mesh(mesh_id=args.pop("mesh", ""))
        if not self._mesh:
            _LOGGER.warning("Unknown Mesh specified")
        else:
            _LOGGER.debug(self._log_formatter.message_format("Using %s"), self._mesh)
            method = getattr(self, call.service, None)
            if method:
                try:
                    await method(**args)
                except Exception as err:
                    _LOGGER.warning(self._log_formatter.message_format("%s"), err)

        _LOGGER.debug(self._log_formatter.message_format("exited"))

    def register_services(self) -> None:
        """Register the services"""

        for service_name, service_details in self.SERVICES.items():
            self._hass.services.async_register(
                domain=DOMAIN,
                service=service_name,
                service_func=self._async_service_call,
                schema=service_details.get("schema", None),
            )

    def unregister_services(self) -> None:
        """Unregister the services"""

        for service_name, service_details in self.SERVICES.items():
            self._hass.services.async_remove(domain=DOMAIN, service=service_name)

    async def check_updates(self) -> None:
        """Instruct the mesh to check for updates

        The update check could be a long-running task so a signal is also sent to listeners to update the status more
        frequently.  This allows a more reactive UI but also paves the way for status messages later.

        :return: None
        """

        _LOGGER.debug(self._log_formatter.message_format("entered"))

        await self._mesh.async_check_for_updates()
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS)

        _LOGGER.debug(self._log_formatter.message_format("exited"))

    async def delete_device(self, **kwargs) -> None:
        """Remove a device from the device list on the mesh"""

        _LOGGER.debug(self._log_formatter.message_format("entered, kwargs: %s"), kwargs)

        await self._mesh.async_delete_device(**kwargs)

        _LOGGER.debug(self._log_formatter.message_format("exited"))

    async def reboot_node(self, **kwargs) -> None:
        """Instruct the mesg to restart a node

        N.B. Rebooting the primary node will cause all ndoes to reboot. To reboot the primary node you should also
        turn the is_primary toggle on.

        :return:None
        """

        _LOGGER.debug(self._log_formatter.message_format("entered, kwargs: %s"), kwargs)

        await self._mesh.async_reboot_node(node_name=kwargs.get("node_name", ""), force=kwargs.get("is_primary", False))

        _LOGGER.debug(self._log_formatter.message_format("exited"))

    async def start_speedtest(self) -> None:
        """Start a Speedtest on the mesh

        The Speedtest is a long-running task so a signal is also sent to listeners to update the status more
        frequently.  This allows seeing the stages of the test in the UI.

        :return:None
        """

        _LOGGER.debug(self._log_formatter.message_format("entered"))

        await self._mesh.async_start_speedtest()
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)

        _LOGGER.debug(self._log_formatter.message_format("exited"))
