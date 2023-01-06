"""Binary sensors for the mesh, nodes and devices."""

# region #-- imports --#
from __future__ import annotations

import dataclasses
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, List, Mapping

from homeassistant.components.binary_sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from . import LinksysVelopMeshEntity, LinksysVelopNodeEntity, entity_cleanup
from .const import (
    CONF_COORDINATOR,
    DOMAIN,
    SIGNAL_UPDATE_CHANNEL_SCANNING,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
    UPDATE_DOMAIN,
)

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- binary sensor entity descriptions --#
@dataclasses.dataclass
class OptionalLinksysVelopDescription:
    """Represent the optional attributes of the binary sensor description."""

    extra_attributes: Callable | None = None
    state_value: Callable | None = None


@dataclasses.dataclass
class RequiredLinksysVelopDescription:
    """Represent the required attributes of the binary sensor description."""


@dataclasses.dataclass
class LinksysVelopBinarySensorDescription(
    OptionalLinksysVelopDescription,
    BinarySensorEntityDescription,
    RequiredLinksysVelopDescription,
):
    """Describe binary sensor entity."""


# endregion


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
    mesh: Mesh = coordinator.data
    binary_sensors: List[
        LinksysVelopMeshBinarySensor
        | LinksysVelopNodeBinarySensor
        | LinksysVelopMeshRecurringBinarySensor
    ] = []
    binary_sensors_to_remove: List[
        LinksysVelopMeshBinarySensor
        | LinksysVelopNodeBinarySensor
        | LinksysVelopMeshRecurringBinarySensor
    ] = []

    # region #-- Mesh binary sensors --#
    mesh_binary_sensor_descriptions: tuple[LinksysVelopBinarySensorDescription, ...] = (
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="client_steering_enabled",
            name="Client Steering",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="dhcp_enabled",
            name="DHCP Server",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="express_forwarding_enabled",
            name="Express Forwarding",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="homekit_enabled",
            name="HomeKit Integration",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="homekit_paired",
            name="HomeKit Integration Paired",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            extra_attributes=lambda m: {
                "mode": m.mac_filtering_mode,
                "addresses": m.mac_filtering_addresses,
            },
            key="mac_filtering_enabled",
            name="MAC Filtering",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="node_steering_enabled",
            name="Node Steering",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="sip_enabled",
            name="SIP",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="upnp_allow_change_settings",
            name="UPnP Allow Users to Configure",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="upnp_allow_disable_internet",
            name="UPnP Allow Users to Disable Internet",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="upnp_enabled",
            name="UPnP",
        ),
        LinksysVelopBinarySensorDescription(
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            extra_attributes=lambda m: {
                "ip": m.wan_ip,
                "dns": m.wan_dns or None,
                "mac": m.wan_mac,
            },
            key="wan_status",
            name="WAN Status",
        ),
        LinksysVelopBinarySensorDescription(
            entity_registry_enabled_default=False,
            key="wps_state",
            name="WPS",
        ),
    )

    for binary_sensor_description in mesh_binary_sensor_descriptions:
        binary_sensors.append(
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=binary_sensor_description,
            )
        )
    # endregion

    # region #-- Mesh recurring binary sensors --#
    binary_sensors.extend(
        [
            LinksysVelopMeshRecurringBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=LinksysVelopBinarySensorDescription(
                    key="is_channel_scan_running",
                    name="Channel Scanning",
                ),
                recurrence_interval=40,
                recurrence_trigger=SIGNAL_UPDATE_CHANNEL_SCANNING,
                state_method="async_get_channel_scan_info",
                state_processor=lambda s: s.get("isRunning", False),
            ),
            LinksysVelopMeshRecurringBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=LinksysVelopBinarySensorDescription(
                    extra_attributes=lambda r: {
                        "status": r,
                    },
                    key="",
                    name="Speedtest Status",
                    state_value=lambda m: m.speedtest_status != "",
                ),
                recurrence_interval=1,
                recurrence_post_signal=SIGNAL_UPDATE_SPEEDTEST_RESULTS,
                recurrence_trigger=SIGNAL_UPDATE_SPEEDTEST_STATUS,
                state_method="async_get_speedtest_state",
                state_processor=lambda s: s != "",
            ),
        ]
    )
    # endregion

    # region #-- Node binary sensors --#
    for node in mesh.nodes:
        # region #-- update binary sensor for older versions --#
        # -- need to keep this here for upgrading from older HASS versions --#
        binary_sensor_update: LinksysVelopNodeBinarySensor = (
            LinksysVelopNodeBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=LinksysVelopBinarySensorDescription(
                    device_class=BinarySensorDeviceClass.UPDATE,
                    key="update_available",
                    name="Update Available",
                    state_value=lambda n: n.firmware.get("version")
                    != n.firmware.get("latest_version"),
                ),
            )
        )

        if UPDATE_DOMAIN is None:
            binary_sensors.append(binary_sensor_update)
        else:
            binary_sensors_to_remove.append(binary_sensor_update)
        # endregion

        # region #-- build the additional binary sensors --#
        binary_sensors.extend(
            [
                LinksysVelopNodeBinarySensor(
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=LinksysVelopBinarySensorDescription(
                        device_class=BinarySensorDeviceClass.CONNECTIVITY,
                        extra_attributes=lambda n: n.connected_adapters[0]
                        if n.connected_adapters
                        else {},
                        key="status",
                        name="Status",
                    ),
                ),
            ]
        )
        # endregion
    # endregion

    async_add_entities(binary_sensors)

    binary_sensors_to_remove.append(
        # -- an old binary sensor that needs to be removed --#
        LinksysVelopMeshBinarySensor(
            config_entry=config_entry,
            coordinator=coordinator,
            description=LinksysVelopBinarySensorDescription(
                key="",
                name="Check for Updates Status",
            ),
        )
    )

    if binary_sensors_to_remove:
        entity_cleanup(
            config_entry=config_entry, entities=binary_sensors_to_remove, hass=hass
        )


class LinksysVelopMeshBinarySensor(LinksysVelopMeshEntity, BinarySensorEntity):
    """Representation of a binary sensor for the mesh."""

    entity_description: LinksysVelopBinarySensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopBinarySensorDescription,
    ) -> None:
        """Initialise."""
        self.entity_domain = ENTITY_DOMAIN
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    @property
    def is_on(self) -> bool | None:
        """Get the state of the binary sensor."""
        if self.entity_description.state_value:
            return self.entity_description.state_value(self._mesh)
        else:
            return getattr(self._mesh, self.entity_description.key, None)


class LinksysVelopNodeBinarySensor(LinksysVelopNodeEntity, BinarySensorEntity):
    """Representaion of a binary sensor related to a node."""

    entity_description: LinksysVelopBinarySensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: LinksysVelopBinarySensorDescription,
    ) -> None:
        """Initialise."""
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self.entity_domain = ENTITY_DOMAIN
        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            node=node,
        )

    @property
    def is_on(self) -> bool | None:
        """Get the state of the binary sensor."""
        if self.entity_description.state_value:
            return self.entity_description.state_value(self._node)
        else:
            return getattr(self._node, self.entity_description.key, None)


class LinksysVelopMeshRecurringBinarySensor(LinksysVelopMeshEntity, BinarySensorEntity):
    """Representation of a binary sensor that may need out of band updates."""

    entity_description: LinksysVelopBinarySensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: LinksysVelopBinarySensorDescription,
        recurrence_interval: int,
        recurrence_trigger: str,
        state_method: str,
        state_processor: Callable[..., bool],
        recurrence_post_signal: str | None = None,
    ) -> None:
        """Initialise."""
        self.entity_domain = ENTITY_DOMAIN
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._state: bool | None = None

        self._esa: Mapping[str, Any] | None = None
        self._remove_action_interval: Callable | None = None
        self._recurrence_interval: int = recurrence_interval
        self._recurrence_trigger: str = recurrence_trigger
        self._recurrence_post_signal: str | None = recurrence_post_signal
        self._state_method: str = state_method
        self._state_processor: Callable[..., bool] = state_processor

        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    def _handle_coordinator_update(self) -> None:
        """React to updates from the coordinator."""
        super()._handle_coordinator_update()
        if self.is_on:
            if self._remove_action_interval is None:
                async_dispatcher_send(hass=self.hass, signal=self._recurrence_trigger)
        else:
            self._stop_interval()

        self.async_write_ha_state()

    def _stop_interval(self) -> None:
        """Stop the interval from running."""
        if isinstance(self._remove_action_interval, Callable):
            self._remove_action_interval()
            self._remove_action_interval = None
            self._state = None
            if self._recurrence_post_signal is not None:
                async_dispatcher_send(self.hass, self._recurrence_post_signal)

    async def _async_action(self, _: datetime | None = None) -> None:
        """Calculate the actual state based on the current state in the Mesh.

        This is required because we don't want to query a full update of all
        entities from the Mesh.
        """
        state_method: Callable | None = getattr(self._mesh, self._state_method, None)
        if not isinstance(state_method, Callable):
            raise RuntimeError("State method is not callable") from None

        if not isinstance(self._state_processor, Callable):
            raise RuntimeError("State processor is not callable") from None

        state_method_results: Any = await state_method()
        if isinstance(self.entity_description.extra_attributes, Callable):
            self._esa = self.entity_description.extra_attributes(state_method_results)
        temp_state: bool = self._state_processor(state_method_results)
        if temp_state:
            if self._remove_action_interval is None:
                self._remove_action_interval = async_track_time_interval(
                    hass=self.hass,
                    action=self._async_action,
                    interval=timedelta(seconds=self._recurrence_interval),
                )
        self._state = temp_state

        self.async_schedule_update_ha_state()

        if not temp_state:
            self._stop_interval()

    async def async_added_to_hass(self) -> None:
        """Do stuff when entity is added to registry."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=self._recurrence_trigger,
                target=self._async_action,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Tidy up when removed."""
        self._stop_interval()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        return self._esa

    @property
    def is_on(self) -> bool | None:
        """Get the state of the binary sensor."""
        queried_state: bool
        ret: bool
        if self.entity_description.state_value:
            queried_state = self.entity_description.state_value(self._mesh)
        else:
            queried_state = getattr(self._mesh, self.entity_description.key, None)

        if self._state is not None:
            ret = self._state
        else:
            ret = queried_state

        return ret
