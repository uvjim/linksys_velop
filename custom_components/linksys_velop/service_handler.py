"""Manage the services for the pyvelop integration."""

# region #-- imports --#
from __future__ import annotations

import functools
import logging
import uuid
from typing import List

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pyvelop.device import Device
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


def deprectated_service(solution: str):
    """Mark a service as deprecated."""

    def deprecated_decorator(func):
        """Decorate the function."""

        @functools.wraps(func)
        def deprecated_wrapper(self, *args, **kwargs):
            """Wrap for the original function."""
            logger = logging.getLogger(func.__module__)
            log_formatter = getattr(self, "_log_formatter", None)
            if log_formatter is not None:
                logger.warning(
                    log_formatter.format(
                        "The service %s.%s has been deprecated. %s",
                        include_caller=False,
                    ),
                    DOMAIN,
                    func.__name__,
                    solution,
                )
            else:
                pass

            return func(self, *args, **kwargs)

        return deprecated_wrapper

    return deprecated_decorator


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
                    vol.Required("device"): str,
                }
            )
        },
        "device_internet_access": {
            "schema": vol.Schema(
                {
                    vol.Required("mesh"): str,
                    vol.Required("device"): str,
                    vol.Required("pause"): bool,
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
        "rename_device": {
            "schema": vol.Schema(
                {
                    vol.Required("mesh"): str,
                    vol.Required("device"): str,
                    vol.Required("new_name"): str,
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
        self._mesh: Mesh | None = None

    def _get_device(self, attribute: str, value: str) -> List[Device] | None:
        """Get a device from the Mesh using the given attribute.

        N.B. this uses the devices from the last poll to retrieve
        details.
        """
        ret: List[Device] | None = None
        if isinstance(self._mesh, Mesh):
            ret = [
                device
                for device in self._mesh.devices
                if getattr(device, attribute, "").lower() == value.lower()
            ]

        return ret or None

    def _get_mesh(self, mesh_id: str) -> Mesh | None:
        """Get the Mesh class for the service call to operate against.

        :param mesh_id: the device id of the mesh
        :return: the Mesh class or None
        """
        config_entry: ConfigEntry | None = None
        config_entry_id: str | None = None
        device_registry: dr.DeviceRegistry = dr.async_get(hass=self._hass)
        device: dr.DeviceEntry | None = device_registry.async_get(device_id=mesh_id)
        if device:
            for config_entry_id in device.config_entries:
                config_entry = self._hass.config_entries.async_get_entry(
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
            _LOGGER.warning(
                self._log_formatter.format(
                    "Unknown Mesh specified", include_caller=False
                )
            )
        else:
            _LOGGER.debug(self._log_formatter.format("Using %s"), self._mesh)
            method = getattr(self, call.service, None)
            if method:
                try:
                    await method(**args)
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.warning(
                        self._log_formatter.format("%s", include_caller=False), err
                    )

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

    @deprectated_service(solution="Use the associated button.press native service.")
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

        try:
            _ = uuid.UUID(kwargs.get("device"))
            await self._mesh.async_delete_device_by_id(device=kwargs.get("device"))
        except ValueError:
            await self._mesh.async_delete_device_by_name(device=kwargs.get("device"))

        _LOGGER.debug(self._log_formatter.format("exited"))

    async def device_internet_access(self, **kwargs) -> None:
        """Change state of Internet access for a device."""
        _LOGGER.debug(self._log_formatter.format("entered, %s"), kwargs)

        try:
            _ = uuid.UUID(kwargs.get("device"))
            device: List[Device] | None = self._get_device(
                attribute="unique_id", value=kwargs.get("device", "")
            )
        except ValueError:
            device: List[Device] | None = self._get_device(
                attribute="name", value=kwargs.get("device", "")
            )

        if device is None:
            raise ValueError(f"Unknown device: {kwargs.get('device', '')}") from None

        await self._mesh.async_device_internet_access_state(
            device_id=device[0].unique_id,
            state=not kwargs.get("pause", False),
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

    async def rename_device(self, **kwargs) -> None:
        """Rename a device on the Mesh."""
        _LOGGER.debug(self._log_formatter.format("entered, kwargs: %s"), kwargs)
        try:
            _ = uuid.UUID(kwargs.get("device"))
            device: List[Device] | None = self._get_device(
                attribute="unique_id", value=kwargs.get("device", "")
            )
        except ValueError:
            device: List[Device] | None = self._get_device(
                attribute="name", value=kwargs.get("device", "")
            )

        if device is None:
            raise ValueError(f"Unknown device: {kwargs.get('device', '')}") from None

        # only make the request to rename if they are different
        if device[0].name != kwargs.get("new_name"):
            _LOGGER.debug(
                self._log_formatter.format("renaming device: %s"), device[0].unique_id
            )
            await self._mesh.async_rename_device(
                device_id=device[0].unique_id, name=kwargs.get("new_name")
            )

        _LOGGER.debug(self._log_formatter.format("exited"))

    @deprectated_service(solution="Use the associated button.press native service.")
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
