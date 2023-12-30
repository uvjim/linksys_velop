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

from . import (
    LinksysVelopDeviceEntity,
    LinksysVelopMeshEntity,
    LinksysVelopNodeEntity,
    entity_cleanup,
)
from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_UI,
    DEF_UI_DEVICE_ID,
    DOMAIN,
    SIGNAL_UPDATE_CHANNEL_SCANNING,
    SIGNAL_UPDATE_SPEEDTEST_PROGRESS,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
    UPDATE_DOMAIN,
)

# endregion

_LOGGER = logging.getLogger(__name__)


# region #-- binary sensor entity descriptions --#
@dataclasses.dataclass(frozen=True)
class AdditionalBinarySensorDescription:
    """Represent the additional attributes of the binary sensor description."""

    extra_attributes: Callable | None = None
    state_value: Callable | None = None


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
        | LinksysVelopDeviceBinarySensor
    ] = []
    binary_sensors_to_remove: List[
        LinksysVelopMeshBinarySensor
        | LinksysVelopNodeBinarySensor
        | LinksysVelopMeshRecurringBinarySensor
        | LinksysVelopDeviceBinarySensor
    ] = []

    # region #-- Device binary sensors --#
    for device_id in config_entry.options.get(CONF_DEVICE_UI, []):
        binary_sensors.extend(
            [
                LinksysVelopDeviceBinarySensor(
                    additional_description=AdditionalBinarySensorDescription(
                        extra_attributes=lambda d: d.parental_control_schedule.get(
                            "blocked_internet_access"
                        ),
                        state_value=lambda d: d.parental_control_schedule is not None
                        and d.parental_control_schedule.get("blocked_internet_access")
                        is not None
                        and any(
                            d.parental_control_schedule.get(
                                "blocked_internet_access"
                            ).values()
                        )
                        if d.unique_id != DEF_UI_DEVICE_ID
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=BinarySensorEntityDescription(
                        key="",
                        name="Blocked Times",
                        translation_key="blocked_times",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceBinarySensor(
                    additional_description=AdditionalBinarySensorDescription(
                        state_value=lambda d: next(iter(d.connected_adapters), {}).get(
                            "guest_network"
                        )
                        if d.unique_id != DEF_UI_DEVICE_ID
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=BinarySensorEntityDescription(
                        key="",
                        name="Guest Network",
                        translation_key="guest_network",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceBinarySensor(
                    additional_description=AdditionalBinarySensorDescription(
                        state_value=lambda d: next(iter(d.connected_adapters), {}).get(
                            "reservation"
                        )
                        if d.unique_id != DEF_UI_DEVICE_ID
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=BinarySensorEntityDescription(
                        key="",
                        name="Reserved IP",
                        translation_key="reserved_ip",
                    ),
                    device_id=device_id,
                ),
                LinksysVelopDeviceBinarySensor(
                    additional_description=AdditionalBinarySensorDescription(
                        extra_attributes={"device": True},
                        state_value=lambda d: d.status
                        if d.unique_id != DEF_UI_DEVICE_ID
                        else None,
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    description=BinarySensorEntityDescription(
                        device_class=BinarySensorDeviceClass.CONNECTIVITY,
                        key="",
                        name="Status",
                        translation_key="status",
                    ),
                    device_id=device_id,
                ),
            ]
        )
    # endregion

    # region #-- Mesh binary sensors --#
    binary_sensors.extend(
        [
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="client_steering_enabled",
                    name="Client Steering",
                    translation_key="client_steering",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="dhcp_enabled",
                    name="DHCP Server",
                    translation_key="dhcp_server",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="express_forwarding_enabled",
                    name="Express Forwarding",
                    translation_key="express_forwarding",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="homekit_paired",
                    name="HomeKit Integration Paired",
                    translation_key="homekit_paired",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                additional_description=AdditionalBinarySensorDescription(
                    extra_attributes=lambda m: {
                        "mode": m.mac_filtering_mode,
                        "addresses": m.mac_filtering_addresses,
                    },
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="mac_filtering_enabled",
                    name="MAC Filtering",
                    translation_key="mac_filtering",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="node_steering_enabled",
                    name="Node Steering",
                    translation_key="node_steering",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="sip_enabled",
                    name="SIP",
                    translation_key="sip",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="upnp_allow_change_settings",
                    name="UPnP Allow Users to Configure",
                    translation_key="upnp_allow_change_settings",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="upnp_allow_disable_internet",
                    name="UPnP Allow Users to Disable Internet",
                    translation_key="upnp_allow_disable_internet",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="upnp_enabled",
                    name="UPnP",
                    translation_key="upnp",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                additional_description=AdditionalBinarySensorDescription(
                    extra_attributes=lambda m: {
                        "ip": m.wan_ip,
                        "dns": m.wan_dns or None,
                        "mac": m.wan_mac,
                    },
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    key="wan_status",
                    name="WAN Status",
                    translation_key="wan_status",
                ),
            ),
        ]
    )
    # endregion

    # region #-- Mesh recurring binary sensors --#
    binary_sensors.extend(
        [
            LinksysVelopMeshRecurringBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    key="is_channel_scan_running",
                    name="Channel Scanning",
                    translation_key="channel_scanning",
                ),
                recurrence_interval=40,
                recurrence_trigger=SIGNAL_UPDATE_CHANNEL_SCANNING,
                state_method="async_get_channel_scan_info",
                state_processor=lambda s: s.get("isRunning", False),
            ),
            LinksysVelopMeshRecurringBinarySensor(
                additional_description=AdditionalBinarySensorDescription(
                    state_value=lambda m: m.speedtest_status != "",
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    key="",
                    name="Speedtest Status",
                    translation_key="speedtest_status",
                ),
                recurrence_interval=1,
                recurrence_post_signal=SIGNAL_UPDATE_SPEEDTEST_RESULTS,
                recurrence_progress_signal=SIGNAL_UPDATE_SPEEDTEST_PROGRESS,
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
                additional_description=AdditionalBinarySensorDescription(
                    state_value=lambda n: n.firmware.get("version")
                    != n.firmware.get("latest_version"),
                ),
                config_entry=config_entry,
                coordinator=coordinator,
                node=node,
                description=BinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.UPDATE,
                    key="update_available",
                    name="Update Available",
                    translation_key="update_available",
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
                    additional_description=AdditionalBinarySensorDescription(
                        extra_attributes=lambda n: n.connected_adapters[0]
                        if n.connected_adapters
                        else {},
                    ),
                    config_entry=config_entry,
                    coordinator=coordinator,
                    node=node,
                    description=BinarySensorEntityDescription(
                        device_class=BinarySensorDeviceClass.CONNECTIVITY,
                        key="status",
                        name="Status",
                        translation_key="status",
                    ),
                ),
            ]
        )
        # endregion
    # endregion

    async_add_entities(binary_sensors)

    binary_sensors_to_remove.extend(
        [
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    key="",
                    name="Check for Updates Status",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    entity_registry_enabled_default=False,
                    key="homekit_enabled",
                    name="HomeKit Integration",
                ),
            ),
            LinksysVelopMeshBinarySensor(
                config_entry=config_entry,
                coordinator=coordinator,
                description=BinarySensorEntityDescription(
                    key="wps_state",
                    name="WPS",
                ),
            ),
        ]
    )

    if binary_sensors_to_remove:
        entity_cleanup(
            config_entry=config_entry, entities=binary_sensors_to_remove, hass=hass
        )


class LinksysVelopDeviceBinarySensor(LinksysVelopDeviceEntity, BinarySensorEntity):
    """Representation of a device binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: BinarySensorEntityDescription,
        device_id: str,
        additional_description: AdditionalBinarySensorDescription | None = None,
    ) -> None:
        """Initialise Device sensor."""
        self.entity_domain = ENTITY_DOMAIN
        self._additional_description: AdditionalBinarySensorDescription | None = (
            additional_description
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        super().__init__(
            config_entry=config_entry,
            coordinator=coordinator,
            description=description,
            device_id=device_id,
        )

    @property
    def is_on(self) -> bool | None:
        """Get the state of the binary sensor."""
        if (
            self._additional_description is not None
            and self._additional_description.state_value
        ):
            return self._additional_description.state_value(self._device)
        return getattr(self._device, self.entity_description.key, None)


class LinksysVelopMeshBinarySensor(LinksysVelopMeshEntity, BinarySensorEntity):
    """Representation of a binary sensor for the mesh."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: BinarySensorEntityDescription,
        additional_description: AdditionalBinarySensorDescription | None = None,
    ) -> None:
        """Initialise."""
        self.entity_domain = ENTITY_DOMAIN
        self._additional_description: AdditionalBinarySensorDescription | None = (
            additional_description
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        super().__init__(
            config_entry=config_entry, coordinator=coordinator, description=description
        )

    @property
    def is_on(self) -> bool | None:
        """Get the state of the binary sensor."""
        if (
            self._additional_description is not None
            and self._additional_description.state_value
        ):
            return self._additional_description.state_value(self._mesh)
        else:
            return getattr(self._mesh, self.entity_description.key, None)


class LinksysVelopNodeBinarySensor(LinksysVelopNodeEntity, BinarySensorEntity):
    """Representaion of a binary sensor related to a node."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        node: Node,
        config_entry: ConfigEntry,
        description: BinarySensorEntityDescription,
        additional_description: AdditionalBinarySensorDescription | None = None,
    ) -> None:
        """Initialise."""
        self._additional_description: AdditionalBinarySensorDescription | None = (
            additional_description
        )
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
        if (
            self._additional_description is not None
            and self._additional_description.state_value
        ):
            return self._additional_description.state_value(self._node)
        else:
            return getattr(self._node, self.entity_description.key, None)


class LinksysVelopMeshRecurringBinarySensor(LinksysVelopMeshEntity, BinarySensorEntity):
    """Representation of a binary sensor that may need out of band updates."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: BinarySensorEntityDescription,
        recurrence_interval: int,
        recurrence_trigger: str,
        state_method: str,
        state_processor: Callable[..., bool],
        additional_description: AdditionalBinarySensorDescription | None = None,
        recurrence_post_signal: str | None = None,
        recurrence_progress_signal: str | None = None,
    ) -> None:
        """Initialise."""
        self.entity_domain = ENTITY_DOMAIN
        self._additional_description: AdditionalBinarySensorDescription | None = (
            additional_description
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._state: bool | None = None

        self._esa: Mapping[str, Any] | None = None
        self._remove_action_interval: Callable | None = None
        self._recurrence_interval: int = recurrence_interval
        self._recurrence_trigger: str = recurrence_trigger
        self._recurrence_post_signal: str | None = recurrence_post_signal
        self._recurrence_progress_signal: str | None = recurrence_progress_signal
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
        if self._additional_description is not None and isinstance(
            self._additional_description_description.extra_attributes, Callable
        ):
            self._esa = self._additional_description.extra_attributes(
                state_method_results
            )

        if self._recurrence_progress_signal is not None:
            async_dispatcher_send(
                self.hass, self._recurrence_progress_signal, state_method_results
            )

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
        if (
            self._additional_description is not None
            and self._additional_description.state_value
        ):
            queried_state = self._additional_description.state_value(self._mesh)
        else:
            queried_state = getattr(self._mesh, self.entity_description.key, None)

        if self._state is not None:
            ret = self._state
        else:
            ret = queried_state

        return ret
