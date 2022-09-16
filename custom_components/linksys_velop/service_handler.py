"""Manage the services for the pyvelop integration."""

# region #-- imports --#
import logging
from typing import List, Optional

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pyvelop.mesh import Mesh

from .const import (
    CONF_COORDINATOR,
    CONF_LOGGING_SERIAL,
    DEF_LOGGING_SERIAL,
    DOMAIN,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .logger import Logger

# endregion


_LOGGER = logging.getLogger(__name__)


class LinksysVelopServiceHandler:
    """Define and action serice calls."""

    SERVICES = {
        "check_updates": {
            "schema": vol.Schema(
                {
                    vol.Required("mesh"): str,
                }
            )
        },
        "delete_device": {
            "schema": vol.Schema(
                {
                    vol.Required("mesh"): str,
                    vol.Optional("device_id"): str,
                    vol.Optional("device_name"): str,
                }
            )
        },
        "reboot_node": {
            "schema": vol.Schema(
                {
                    vol.Required("mesh"): str,
                    vol.Required("node_name"): str,
                    vol.Optional("is_primary"): bool,
                }
            )
        },
        "start_speedtest": {
            "schema": vol.Schema(
                {
                    vol.Required("mesh"): str,
                }
            )
        },
    }

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise."""
        self._hass: HomeAssistant = hass
        self._log_formatter: Logger = Logger()
        self._mesh: Optional[Mesh] = None

    def _get_mesh(self, mesh_id: str) -> Optional[Mesh]:
        """Get the Mesh class for the service call to operate against.

        :param mesh_id: the device id of the mesh
        :return: the Mesh class or None
        """
        device_registry: dr.DeviceRegistry = dr.async_get(hass=self._hass)
        device: List[dr.DeviceEntry] = [
            d for i, d in device_registry.devices.items() if i == mesh_id
        ]
        config_entry_id: Optional[str] = None
        if device:
            for config_entry_id in device[0].config_entries:
                config_entry: ConfigEntry = self._hass.config_entries.async_get_entry(
                    entry_id=config_entry_id
                )
                if config_entry.domain == DOMAIN:
                    if config_entry.options.get(
                        CONF_LOGGING_SERIAL, DEF_LOGGING_SERIAL
                    ):
                        self._log_formatter = Logger(unique_id=config_entry.unique_id)
                    else:
                        self._log_formatter = Logger()
                    break
            else:
                config_entry = None

        ret = (
            self._hass.data[DOMAIN][config_entry_id][CONF_COORDINATOR].data
            if config_entry
            else None
        )

        return ret

    async def _async_service_call(self, call: ServiceCall) -> None:
        """Call the required method based on the given argument.

        :param call: the service call that should be made
        :return: None
        """
        _LOGGER.debug(self._log_formatter.format("entered, call: %s"), call)

        args = call.data.copy()
        self._mesh = self._get_mesh(mesh_id=args.pop("mesh", ""))
        if not self._mesh:
            _LOGGER.warning("Unknown Mesh specified")
        else:
            _LOGGER.debug(self._log_formatter.format("Using %s"), self._mesh)
            method = getattr(self, call.service, None)
            if method:
                try:
                    await method(**args)
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.warning(self._log_formatter.format("%s"), err)

        _LOGGER.debug(self._log_formatter.format("exited"))

    def register_services(self) -> None:
        """Register the services."""
        for service_name, service_details in self.SERVICES.items():
            self._hass.services.async_register(
                domain=DOMAIN,
                service=service_name,
                service_func=self._async_service_call,
                schema=service_details.get("schema", None),
            )

    def unregister_services(self) -> None:
        """Unregister the services."""
        for service_name in self.SERVICES:
            self._hass.services.async_remove(domain=DOMAIN, service=service_name)

    async def check_updates(self) -> None:
        """Instruct the mesh to check for updates.

        The update check could be a long-running task so a signal is also sent to listeners to update the status more
        frequently.  This allows a more reactive UI but also paves the way for status messages later.

        :return: None
        """
        _LOGGER.debug(self._log_formatter.format("entered"))

        await self._mesh.async_check_for_updates()

        _LOGGER.debug(self._log_formatter.format("exited"))

    async def delete_device(self, **kwargs) -> None:
        """Remove a device from the device list on the mesh."""
        _LOGGER.debug(self._log_formatter.format("entered, kwargs: %s"), kwargs)

        if kwargs.get("device_id"):
            await self._mesh.async_delete_device_by_id(device=kwargs.get("device_id"))
        elif kwargs.get("device_name"):
            await self._mesh.async_delete_device_by_name(
                device=kwargs.get("device_name")
            )

        _LOGGER.debug(self._log_formatter.format("exited"))

    async def reboot_node(self, **kwargs) -> None:
        """Instruct the mesh to restart a node.

        N.B. Rebooting the primary node will cause all ndoes to reboot. To reboot the primary node you should also
        turn the is_primary toggle on.

        :return:None
        """
        _LOGGER.debug(self._log_formatter.format("entered, kwargs: %s"), kwargs)

        await self._mesh.async_reboot_node(
            node_name=kwargs.get("node_name", ""), force=kwargs.get("is_primary", False)
        )

        _LOGGER.debug(self._log_formatter.format("exited"))

    async def start_speedtest(self) -> None:
        """Start a Speedtest on the mesh.

        The Speedtest is a long-running task so a signal is also sent to listeners to update the status more
        frequently.  This allows seeing the stages of the test in the UI.

        :return:None
        """
        _LOGGER.debug(self._log_formatter.format("entered"))

        await self._mesh.async_start_speedtest()
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)

        _LOGGER.debug(self._log_formatter.format("exited"))
