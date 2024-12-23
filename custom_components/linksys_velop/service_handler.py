"""Manage the services for the Linksys Velop integration."""

# region #-- imports --#
from __future__ import annotations

import functools
import logging
import uuid
from collections.abc import Awaitable

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pyvelop.device import Device, ParentalControl
from pyvelop.exceptions import MeshInvalidInput
from pyvelop.mesh import Mesh
from pyvelop.node import Node, NodeType

from .const import CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS, DOMAIN
from .types import (
    EventSubTypes,
    LinksysVelopConfigEntry,
    LinksysVelopLogFormatter,
)

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

            return func(self, *args, **kwargs)

        return deprecated_wrapper

    return deprecated_decorator


class LinksysVelopServiceHandler:
    """Define and action serice calls."""

    SERVICES = {
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
        "device_internet_rules": {
            "schema": vol.Schema(
                {
                    vol.Required("mesh"): str,
                    vol.Required("device"): str,
                    vol.Optional("sunday"): list,
                    vol.Optional("monday"): list,
                    vol.Optional("tuesday"): list,
                    vol.Optional("wednesday"): list,
                    vol.Optional("thursday"): list,
                    vol.Optional("friday"): list,
                    vol.Optional("saturday"): list,
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
    }

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise."""
        self._hass: HomeAssistant = hass
        self._log_formatter: LinksysVelopLogFormatter = None

    def _get_config_entry_from_mesh_id(
        self, mesh_id: str
    ) -> LinksysVelopConfigEntry | None:
        """Retrieve the ConfigEntry based on the ID of the Mesh."""
        config_entry: LinksysVelopConfigEntry | None = None
        config_entry_id: str | None = None
        device_registry: dr.DeviceRegistry = dr.async_get(hass=self._hass)
        device: dr.DeviceEntry | None = device_registry.async_get(device_id=mesh_id)
        if device:
            for config_entry_id in device.config_entries:
                config_entry = self._hass.config_entries.async_get_entry(
                    config_entry_id
                )
                if config_entry.domain == DOMAIN:
                    self._log_formatter = config_entry.runtime_data.log_formatter
                    break

        return config_entry

    def _get_device(self, mesh: Mesh, value: str) -> list[Device] | None:
        """Get a device from the Mesh based on name or unique ID.

        N.B. this uses the devices from the last poll to retrieve
        details.
        """
        ret: list[Device] | None = None

        try:
            _ = uuid.UUID(value)
            ret = [
                device
                for device in mesh.devices
                if getattr(device, "unique_id", "").lower() == value.lower()
            ]
        except ValueError:
            ret = [
                device
                for device in mesh.devices
                if getattr(device, "name", "").lower() == value.lower()
            ]

        return ret or None

    async def _async_service_call(self, call: ServiceCall) -> None:
        """Call the required method based on the given argument.

        :param call: the service call that should be made
        :return: None
        """

        args = call.data.copy()
        config_entry_id: str | None = args.pop("mesh", None)
        config_entry: LinksysVelopConfigEntry
        if (
            config_entry := self._hass.config_entries.async_get_entry(config_entry_id)
        ) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_input",
                translation_placeholders={
                    "action": call.service,
                    "original_msg": "Invalid Mesh specified",
                },
            ) from None

        self._log_formatter = config_entry.runtime_data.log_formatter
        _LOGGER.debug(self._log_formatter("entered, call: %s"), call)

        _LOGGER.debug(self._log_formatter("Using %s"), config_entry.runtime_data.mesh)
        if (method := getattr(self, call.service, None)) is not None:
            try:
                await method(**args, config_entry=config_entry)
            except MeshInvalidInput as exc:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_input",
                    translation_placeholders={
                        "action": call.service,
                        "original_msg": str(exc),
                    },
                ) from exc
            except Exception as err:
                _LOGGER.warning(self._log_formatter("%s", include_caller=False), err)

        _LOGGER.debug(self._log_formatter("exited"))

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

    async def delete_device(
        self, config_entry: LinksysVelopConfigEntry, **kwargs
    ) -> None:
        """Remove a device from the device list on the mesh."""
        _LOGGER.debug(self._log_formatter("entered, kwargs: %s"), kwargs)

        coro: Awaitable[None]
        try:
            _ = uuid.UUID(kwargs.get("device"))
            coro = config_entry.runtime_data.mesh.async_delete_device_by_id
        except ValueError:
            coro = config_entry.runtime_data.mesh.async_delete_device_by_name

        try:
            await coro(kwargs.get("device"))
        except Exception as exc:
            raise MeshInvalidInput(str(exc)) from exc

        _LOGGER.debug(self._log_formatter("exited"))

    async def device_internet_access(
        self, config_entry: LinksysVelopConfigEntry, **kwargs
    ) -> None:
        """Change state of Internet access for a device."""
        _LOGGER.debug(self._log_formatter("entered, %s"), kwargs)

        device: list[Device] | None = None
        if (
            device := self._get_device(
                config_entry.runtime_data.mesh, kwargs.get("device", "")
            )
        ) is None:
            raise MeshInvalidInput(
                f"Unknown device: {kwargs.get('device', '')}"
            ) from None

        rules_to_apply: dict[str, str] = {}
        if kwargs.get("pause", False):
            rules_to_apply = dict(
                map(
                    lambda weekday, readable_schedule: (
                        weekday.name,
                        readable_schedule,
                    ),
                    ParentalControl.WEEKDAYS,
                    ("00:00-00:00",) * len(ParentalControl.WEEKDAYS),
                )
            )

        await config_entry.runtime_data.mesh.async_set_parental_control_rules(
            device_id=device[0].unique_id,
            force_enable=True if kwargs.get("pause", False) else False,
            rules=rules_to_apply,
        )

        _LOGGER.debug(self._log_formatter("exited"))

    async def device_internet_rules(
        self, config_entry: LinksysVelopConfigEntry, **kwargs
    ) -> None:
        """Set Parental Control rules for the device."""
        _LOGGER.debug(self._log_formatter("entered, %s"), kwargs)

        device: list[Device] | None = None
        if (
            device := self._get_device(
                config_entry.runtime_data.mesh, kwargs.get("device", "")
            )
        ) is None:
            raise MeshInvalidInput(
                f"Unknown device: {kwargs.get('device', '')}"
            ) from None

        def _process_times() -> dict[str, str]:
            """Process the times from the service call."""
            ret: dict[str, str] = {}
            for day in ParentalControl.WEEKDAYS:
                times: list[str] = kwargs.get(day.name, [])
                if times:
                    times = ["00:00-00:00" if t == "all_day" else t for t in times]
                    ret[day.name] = ",".join(times)
                else:
                    ret[day.name] = None

            return ret

        rules_to_apply: dict[str, str] = _process_times()
        _LOGGER.debug(self._log_formatter("rules_to_apply: %s"), rules_to_apply)

        await config_entry.runtime_data.mesh.async_set_parental_control_rules(
            device_id=device[0].unique_id,
            rules=rules_to_apply,
        )

        _LOGGER.debug(self._log_formatter("exited"))

    async def reboot_node(
        self, config_entry: LinksysVelopConfigEntry, **kwargs
    ) -> None:
        """Instruct the mesh to restart a node.

        N.B. Rebooting the primary node will cause all nodes to reboot. To reboot the primary node you should also
        turn the is_primary toggle on.

        :return:None
        """
        _LOGGER.debug(self._log_formatter("entered, kwargs: %s"), kwargs)

        node: Node = [
            n
            for n in config_entry.runtime_data.mesh.nodes
            if n.name == kwargs.get("node_name", "")
        ]
        if len(node) == 0:
            raise MeshInvalidInput(
                f"Unknown node: {kwargs.get('node_name', '')}"
            ) from None

        if node[0].type == NodeType.SECONDARY:
            _LOGGER.warning(
                self._log_formatter(
                    "The service %s.%s has been deprecated. %s",
                    include_caller=False,
                ),
                DOMAIN,
                "reboot_node",
                "Use the button available on the node device.",
            )

        await config_entry.runtime_data.mesh.async_reboot_node(
            kwargs.get("node_name", ""),
            force=kwargs.get("is_primary", False),
        )

        # region #-- flag the reboot --#
        if kwargs.get("is_primary", False):
            config_entry.runtime_data.mesh_is_rebooting = True
            if EventSubTypes.MESH_REBOOTING.value in config_entry.options.get(
                CONF_EVENTS_OPTIONS, DEF_EVENTS_OPTIONS
            ):
                async_dispatcher_send(
                    self._hass,
                    f"{DOMAIN}_{EventSubTypes.MESH_REBOOTING.value}",
                )
        # endregion

        _LOGGER.debug(self._log_formatter("exited"))

    async def rename_device(
        self, config_entry: LinksysVelopConfigEntry, **kwargs
    ) -> None:
        """Rename a device on the Mesh."""
        _LOGGER.debug(self._log_formatter("entered, kwargs: %s"), kwargs)

        device: list[Device] | None = None
        if (
            device := self._get_device(
                config_entry.runtime_data.mesh, kwargs.get("device", "")
            )
        ) is None:
            raise MeshInvalidInput(
                f"Unknown device: {kwargs.get('device', '')}"
            ) from None

        # only make the request to rename if they are different
        if device[0].name != kwargs.get("new_name"):
            _LOGGER.debug(
                self._log_formatter("renaming device: %s"),
                device[0].unique_id,
            )
            await config_entry.runtime_data.mesh.async_rename_device(
                device_id=device[0].unique_id, name=kwargs.get("new_name")
            )

        _LOGGER.debug(self._log_formatter("exited"))
