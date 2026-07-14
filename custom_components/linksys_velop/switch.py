"""Switch entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast, override

from homeassistant.components.switch import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.const import Weekdays
from pyvelop.mesh import Mesh, MeshCapability
from pyvelop.mesh_entity import DeviceEntity, ParentalControl

from . import LinksysVelopConfigEntry
from .const import CONF_UI_DEVICES
from .coordinator import (
    CoordinatorTimers,
    CoordinatorTypes,
    LinksysVelopDataUpdateCoordinatorMultiUse,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
)
from .helpers import remove_velop_entity_from_registry

# endregion

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinksysVelopSwitchEntityDescription(
    LinksysVelopEntityDescription, SwitchEntityDescription
):
    """Describes Velop switch entity."""

    esa_fn: Callable[..., dict[str, Any]] | None = None
    off_fn: Callable[..., Awaitable[None]]
    on_fn: Callable[..., Awaitable[None]]
    value_fn: Callable[..., bool | None] | None = None


def get_device_internet_access_state(device: DeviceEntity | None) -> bool | None:
    """Get the state of interent access for the device."""

    ret: bool | None = None

    if device is not None:
        blocked_internet_access: dict[str, str] = device.parental_control_schedule.get(
            "blocked_internet_access", {}
        )

        if len(blocked_internet_access.values()) == 0:
            ret = True
        else:
            ret = not all(
                ",".join(hrs) == "00:00-00:00"
                for hrs in blocked_internet_access.values()
            )

    return ret


async def async_set_device_internet_access_state(
    device: DeviceEntity, state: bool
) -> None:
    """Turn off Internet access for the given device."""

    rules_to_apply: dict[str, str | None] = {}
    if state:
        for weekday in Weekdays:
            rules_to_apply[weekday.name.lower()] = None
    else:
        for weekday in Weekdays:
            rules_to_apply[weekday.name.lower()] = str(
                ParentalControl.binary_to_human_readable(
                    ParentalControl.ALL_PAUSED_SCHEDULE().get(weekday.name.lower(), "")
                )
            )

    await device.async_set_parental_control_rules(rules_to_apply)


async def async_set_mesh_guest_wifi_state(mesh: Mesh, state: bool) -> None:
    """Set the state for the guest wi-fi on the Mesh."""

    await mesh.async_set_guest_wifi_state(state)


async def async_set_mesh_homekit_wifi_state(mesh: Mesh, state: bool) -> None:
    """Set the state of Homekit on the Mesh."""

    await mesh.async_set_homekit_state(state)


async def async_set_mesh_parental_control_state(mesh: Mesh, state: bool) -> None:
    """Set the state of Parental Control on the Mesh."""

    await mesh.async_set_parental_control_state(state)


async def async_set_mesh_upnp_state(mesh: Mesh, state: bool) -> None:
    """Set the  UPnP state for the Mesh."""

    cur_settings: dict[str, bool] = await mesh.async_get_upnp_state()
    new_settings: dict[str, bool] = {
        "enabled": state,
        "allow_change_settings": cur_settings.get("canUsersConfigure", False),
        "allow_disable_internet": cur_settings.get("canUsersDisableWANAccess", False),
    }
    await mesh.async_set_upnp_settings(**new_settings)


async def async_set_mesh_wps_state(mesh: Mesh, state: bool) -> None:
    """Set the WPS state for the Mesh."""

    await mesh.async_set_wps_state(state)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise a switch."""

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopSwitchCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> tuple[LinksysVelopSwitchCoordinatorEntity, ...]:
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopSwitchCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopSwitchCoordinatorEntity] = []

        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                unique_id=ui_device
            )
            mesh_entities: list[LinksysVelopSwitchEntityDescription] = []

            mesh_entities.append(
                LinksysVelopSwitchEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="",
                    name="Internet Access",
                    translation_key="internet_access",
                    target_type=EntityType.DEVICE,
                    off_fn=async_set_device_internet_access_state,
                    on_fn=async_set_device_internet_access_state,
                    value_fn=get_device_internet_access_state,
                ),
            )

            ret_temp.extend(
                [
                    LinksysVelopSwitchMultiUseEntity(
                        entity_context=context,
                        coordinator=cast(
                            LinksysVelopDataUpdateCoordinatorMultiUse,
                            config_entry.runtime_data.coordinators.get(
                                CoordinatorTypes.MESH
                            ),
                        ),
                        description=desc,
                    )
                    for desc in mesh_entities
                ]
            )

        ret = tuple(ret_temp)
        return ret

    def _init_mesh_entities() -> tuple[LinksysVelopSwitchCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopSwitchCoordinatorEntity, ...] = ()
        mesh_entities: list[LinksysVelopSwitchEntityDescription] = []

        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )

        if (
            MeshCapability.GET_GUEST_NETWORK_INFO
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSwitchEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    esa_fn=lambda m: {
                        f"network {idx}": network
                        for idx, network in enumerate(m.guest_wifi_details)
                    },
                    key="guest_wifi_enabled",
                    name="Guest Wi-Fi",
                    off_fn=async_set_mesh_guest_wifi_state,
                    on_fn=async_set_mesh_guest_wifi_state,
                    target_type=EntityType.MESH,
                    translation_key="guest_wifi",
                )
            )

        if (
            MeshCapability.GET_HOMEKIT_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSwitchEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="homekit_enabled",
                    name="HomeKit Integration",
                    off_fn=async_set_mesh_homekit_wifi_state,
                    on_fn=async_set_mesh_homekit_wifi_state,
                    target_type=EntityType.MESH,
                    translation_key="homekit",
                ),
            )

        if (
            MeshCapability.GET_PARENTAL_CONTROL_INFO
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSwitchEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    esa_fn=lambda m: (
                        {
                            "rules": {
                                device.name: device.parental_control_schedule
                                for device in m.devices
                                if device.parental_control_schedule
                            }
                        }
                    ),
                    key="parental_control_enabled",
                    name="Parental Control",
                    off_fn=async_set_mesh_parental_control_state,
                    on_fn=async_set_mesh_parental_control_state,
                    target_type=EntityType.MESH,
                    translation_key="parental_control",
                ),
            )

        if (
            MeshCapability.GET_UPNP_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSwitchEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="upnp_enabled",
                    name="UPnP",
                    off_fn=async_set_mesh_upnp_state,
                    on_fn=async_set_mesh_upnp_state,
                    target_type=EntityType.MESH,
                    translation_key="upnp",
                ),
            )

        if (
            MeshCapability.GET_WPS_SERVER_SETTINGS
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopSwitchEntityDescription(
                    entity_category=EntityCategory.CONFIG,
                    key="wps_state",
                    name="WPS",
                    off_fn=async_set_mesh_wps_state,
                    on_fn=async_set_mesh_wps_state,
                    target_type=EntityType.MESH,
                    translation_key="wps",
                )
            )

        ret = tuple(
            [
                LinksysVelopSwitchMultiUseEntity(
                    entity_context=context,
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorMultiUse,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.MESH
                        ),
                    ),
                    description=desc,
                )
                for desc in mesh_entities
            ]
        )

        return ret

    def _init_node_entities() -> tuple[LinksysVelopSwitchCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""
        ret: tuple[LinksysVelopSwitchCoordinatorEntity, ...] = ()

        return ret

    def _remove_stale_entities() -> None:
        """Remove entities is they are no longer required."""

        entities_to_remove: set[str] = set()

        if (
            MeshCapability.GET_GUEST_NETWORK_INFO
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::guest_wi_fi"
            )

        if (
            MeshCapability.GET_HOMEKIT_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::homekit_integration"
            )

        if (
            MeshCapability.GET_PARENTAL_CONTROL_INFO
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::parental_control"
            )
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::internet_access")

        if (
            MeshCapability.GET_UPNP_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp")

        if (
            MeshCapability.GET_WPS_SERVER_SETTINGS
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::wps")

        if len(entities_to_remove) > 0:
            for entity_unique_id in entities_to_remove:
                remove_velop_entity_from_registry(
                    hass,
                    config_entry.entry_id,
                    entity_unique_id,
                )

    def create_node_entities() -> None:
        """Create the node entities.

        This is in a separate function because new nodes can be added to the mesh whilst the integration is running.
        """

        entities_to_add: tuple[LinksysVelopSwitchCoordinatorEntity, ...] = (
            _init_node_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    _create_entities()
    create_node_entities()


class LinksysVelopSwitchEntity(SwitchEntity):
    """Base class representing a button entity."""

    entity_description: LinksysVelopSwitchEntityDescription
    _entity_domain: str = ENTITY_DOMAIN


class LinksysVelopSwitchMultiUseEntity(
    LinksysVelopSwitchEntity, LinksysVelopMultiUseEntity
):
    """Linksys Velop switch that uses the multi use DataUpdateCoordinator."""

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:

        await self.entity_description.on_fn(self._get_target(), True)
        await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:

        await self.entity_description.off_fn(self._get_target(), False)
        await self.coordinator.async_force_refresh(CoordinatorTimers.MESH)

    @property
    @override
    def is_on(self) -> bool | None:

        ret: bool | None = None

        if self.entity_description.value_fn is None:
            if self.entity_description.key != "":
                ret = getattr(
                    self._get_target(),
                    self.entity_description.key,
                    None,
                )
        else:
            ret = self.entity_description.value_fn(self._get_target())

        return ret


type LinksysVelopSwitchCoordinatorEntity = LinksysVelopSwitchMultiUseEntity
