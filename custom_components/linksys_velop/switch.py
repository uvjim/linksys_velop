"""Switch entities for Linksys Velop."""

# region #-- imports --#
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from homeassistant.components.switch import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.device import Device, ParentalControl
from pyvelop.mesh import Mesh, MeshCapability

from . import LinksysVelopConfigEntry
from .const import CONF_UI_DEVICES
from .entities import (
    EntityContext,
    EntityDetails,
    EntityType,
    LinksysVelopEntity,
    build_entities,
)
from .helpers import remove_velop_entity_from_registry
from .types import CoordinatorTypes

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class SwitchDetails(EntityDetails):
    description: SwitchEntityDescription
    off_func: Callable | str = field(kw_only=True)
    on_func: Callable | str = field(kw_only=True)


def _get_device_internet_access_state(device_details: Device) -> bool | None:
    """Get the state of interent access for the device."""
    blocked_internet_access: dict[str, str] = (
        device_details.parental_control_schedule.get("blocked_internet_access", {})
    )

    if len(blocked_internet_access.values()) == 0:
        return True

    return not all(
        ",".join(hrs) == "00:00-00:00" for hrs in blocked_internet_access.values()
    )


async def _async_set_device_internet_access_state_off(
    config_entry: LinksysVelopConfigEntry, device_details: Device
) -> None:
    """Turn off Internet access for the given device."""
    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH)._mesh
    off_rules: dict[str, str] = {
        k: v[0]
        for k, v in ParentalControl.binary_to_human_readable(
            ParentalControl.ALL_PAUSED_SCHEDULE()
        ).items()
    }
    await mesh.async_set_parental_control_rules(
        device_details.unique_id,
        off_rules,
    )


async def _async_set_device_internet_access_state_on(
    config_entry: LinksysVelopConfigEntry, device_details: Device
) -> None:
    """Turn on Internet access for the given device."""
    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH)._mesh
    await mesh.async_set_parental_control_rules(device_details.unique_id, {})


async def _async_set_mesh_upnp_state_off(
    _: LinksysVelopConfigEntry, mesh: Mesh
) -> None:
    """Turn UPnP off for the Mesh."""

    cur_settings: dict[str, bool] = await mesh.async_get_upnp_state()
    new_settings: dict[str, bool] = {
        "enabled": False,
        "allow_change_settings": cur_settings.get("canUsersConfigure", False),
        "allow_disable_internet": cur_settings.get("canUsersDisableWANAccess", False),
    }
    await mesh.async_set_upnp_settings(**new_settings)


async def _async_set_mesh_upnp_state_on(_: LinksysVelopConfigEntry, mesh: Mesh) -> None:
    """Turn UPnP on for the Mesh."""

    cur_settings: dict[str, bool] = await mesh.async_get_upnp_state()
    new_settings: dict[str, bool] = {
        "enabled": True,
        "allow_change_settings": cur_settings.get("canUsersConfigure", False),
        "allow_disable_internet": cur_settings.get("canUsersDisableWANAccess", False),
    }
    await mesh.async_set_upnp_settings(**new_settings)


ENTITY_DETAILS: list[SwitchDetails] = []


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize a switch."""

    entities_to_add: list[LinksysVelopSwitch] = []
    entities_to_remove: list[str] = []
    entities = build_entities(ENTITY_DETAILS, config_entry, ENTITY_DOMAIN)

    # region #-- add conditional switches --#
    mesh: Mesh = config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH).data
    if MeshCapability.GET_GUEST_NETWORK_INFO in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    SwitchDetails(
                        description=SwitchEntityDescription(
                            entity_category=EntityCategory.CONFIG,
                            key="guest_wifi_enabled",
                            name="Guest Wi-Fi",
                            translation_key="guest_wifi",
                        ),
                        entity_type=EntityType.MESH,
                        esa_value_func=lambda m: {
                            f"network {idx}": network
                            for idx, network in enumerate(m.guest_wifi_details)
                        },
                        off_func="async_set_guest_wifi_state",
                        on_func="async_set_guest_wifi_state",
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::guest_wi_fi"
        )

    if MeshCapability.GET_HOMEKIT_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    SwitchDetails(
                        description=SwitchEntityDescription(
                            entity_category=EntityCategory.CONFIG,
                            key="homekit_enabled",
                            name="HomeKit Integration",
                            translation_key="homekit",
                        ),
                        entity_type=EntityType.MESH,
                        off_func="async_set_homekit_state",
                        on_func="async_set_homekit_state",
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::homekit_integration"
        )

    if MeshCapability.GET_PARENTAL_CONTROL_INFO in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    SwitchDetails(
                        description=SwitchEntityDescription(
                            entity_category=EntityCategory.CONFIG,
                            key="",
                            name="Internet Access",
                            translation_key="internet_access",
                        ),
                        entity_type=EntityType.DEVICE,
                        off_func=_async_set_device_internet_access_state_off,
                        on_func=_async_set_device_internet_access_state_on,
                        state_value_func=_get_device_internet_access_state,
                    ),
                    SwitchDetails(
                        description=SwitchEntityDescription(
                            entity_category=EntityCategory.CONFIG,
                            key="parental_control_enabled",
                            name="Parental Control",
                            translation_key="parental_control",
                        ),
                        entity_type=EntityType.MESH,
                        esa_value_func=lambda m: (
                            {
                                "rules": {
                                    device.name: device.parental_control_schedule
                                    for device in m.devices
                                    if device.parental_control_schedule
                                }
                            }
                        ),
                        off_func="async_set_parental_control_state",
                        on_func="async_set_parental_control_state",
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::parental_control"
        )
        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            entities_to_remove.append(f"{ui_device}::{ENTITY_DOMAIN}::internet_access")

    if MeshCapability.GET_UPNP_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    SwitchDetails(
                        description=SwitchEntityDescription(
                            entity_category=EntityCategory.CONFIG,
                            key="upnp_enabled",
                            name="UPnP",
                            translation_key="upnp",
                        ),
                        entity_type=EntityType.MESH,
                        off_func=_async_set_mesh_upnp_state_off,
                        on_func=_async_set_mesh_upnp_state_on,
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp")

    if MeshCapability.GET_WPS_SERVER_SETTINGS in mesh.capabilities:
        entities.extend(
            build_entities(
                [
                    SwitchDetails(
                        description=SwitchEntityDescription(
                            entity_category=EntityCategory.CONFIG,
                            key="wps_state",
                            name="WPS",
                            translation_key="wps",
                        ),
                        entity_type=EntityType.MESH,
                        off_func="async_set_wps_state",
                        on_func="async_set_wps_state",
                    ),
                ],
                config_entry,
                ENTITY_DOMAIN,
            )
        )
    else:
        entities_to_remove.append(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::wps")

    # endregion

    entities_to_add = [LinksysVelopSwitch(**entity) for entity in entities]
    if len(entities_to_add) > 0:
        async_add_entities(entities_to_add)

    if len(entities_to_remove) > 0:
        for entity_unique_id in entities_to_remove:
            remove_velop_entity_from_registry(
                hass,
                config_entry.entry_id,
                entity_unique_id,
            )


class LinksysVelopSwitch(LinksysVelopEntity, SwitchEntity):
    """Linksys Velop switch."""

    def __init__(
        self,
        context: EntityContext,
        config_entry: LinksysVelopConfigEntry,
        entity_details: SwitchDetails,
        entity_domain: str,
    ) -> None:
        """Initialise."""
        super().__init__(
            context,
            config_entry,
            entity_details,
            entity_domain,
        )

        self._off_func = entity_details.off_func
        self._on_func = entity_details.on_func

    async def async_turn_on(self, **kwargs: Any) -> None:
        """"""
        if isinstance(self._on_func, Callable):
            await self._on_func(self._config_entry, self._context_data)
            await self.coordinator.async_refresh()
        elif (func := getattr(self.coordinator.data, self._on_func, None)) is not None:
            if isinstance(func, Callable):
                await func(True)
                await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """"""
        if isinstance(self._off_func, Callable):
            await self._off_func(self._config_entry, self._context_data)
            await self.coordinator.async_refresh()
        elif (func := getattr(self.coordinator.data, self._off_func, None)) is not None:
            if isinstance(func, Callable):
                await func(False)
                await self.coordinator.async_refresh()

    @callback
    def _update_attr_value(self) -> None:
        """"""

        if self._context_data is None:
            self._attr_is_on = None
            return

        if self._entity_details.state_value_func is not None:
            self._attr_is_on = self._entity_details.state_value_func(self._context_data)
        elif self.entity_description.key:
            try:
                self._attr_is_on = getattr(
                    self._context_data, self.entity_description.key
                )
            except AttributeError:
                self._attr_is_on = None
        else:
            self._attr_is_on = None
