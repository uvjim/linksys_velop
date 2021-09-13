import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS
)
from .pyvelop.mesh import Mesh


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
        "parental_control_state": {
            "schema":
                vol.Schema(
                    {vol.Optional("state"): cv.boolean}
                ),
        },
        "start_speedtest": {},
    }

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self._hass = hass
        self._config_entry = config_entry
        self._mesh: Mesh = self._hass.data[DOMAIN][self._config_entry.entry_id][CONF_COORDINATOR].data

    async def service_call(self, call: ServiceCall):
        method = getattr(self, call.service)
        await method(**call.data)

    def register_services(self) -> None:
        for service_name, service_details in self.SERVICES.items():
            self._hass.services.async_register(
                domain=DOMAIN,
                service=service_name,
                service_func=self.service_call,
                schema=service_details.get("schema", None),
            )

    def unregister_services(self) -> None:
        for service_name, service_details in self.SERVICES.items():
            self._hass.services.async_remove(domain=DOMAIN, service=service_name)

    async def delete_device(self, **kwargs) -> None:
        await self._mesh.async_delete_device(**kwargs)

    async def parental_control_state(self, **kwargs) -> None:
        await self._mesh.async_set_parental_control_state(state=bool(kwargs.get("state", False)))

    async def start_speedtest(self) -> None:
        await self._mesh.async_start_speedtest()
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)

    async def check_updates(self) -> None:
        await self._mesh.async_check_for_updates()
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS)
