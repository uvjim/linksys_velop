""""""

import logging
from datetime import timedelta, datetime
from typing import Mapping, Any, Union

from homeassistant.components.binary_sensor import DEVICE_CLASS_CONNECTIVITY
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
    SIGNAL_UPDATE_SPEEDTEST_RESULTS,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .entity_helpers import (
    entity_setup,
    LinksysVelopMeshPolledBinarySensor,
    LinksysVelopNodePolledBinarySensor,
    LinksysVelopMeshBinarySensor,
)
from .pyvelop.node import Node

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """"""

    binary_sensor_classes = [
        LinksysVelopMeshCheckForUpdateStatusBinarySensor,
        LinksysVelopMeshGuestWiFiBinarySensor,
        LinksysVelopMeshParentalControlBinarySensor,
        LinksysVelopMeshSpeedtestStatusBinarySensor,
        LinksysVelopMeshWANBinarySensor,
        LinksysVelopNodeStatusBinarySensor,
    ]

    entity_setup(
        async_add_entities=async_add_entities,
        config=config,
        entity_classes=binary_sensor_classes,
        hass=hass,
    )


class LinksysVelopMeshCheckForUpdateStatusBinarySensor(LinksysVelopMeshBinarySensor):
    """"""

    _attribute = "Check for Updates Status"
    _status_update_interval: int = 1
    _status_value: bool
    _remove_time_interval: Union[CALLBACK_TYPE, None] = None

    @callback
    async def async_update_callback(self, _: Union[datetime, None] = None):
        """"""

        self._status_value = await self._mesh.async_get_update_state()

        if self._status_value and not self._remove_time_interval:
            self._remove_time_interval = async_track_time_interval(
                self.hass,
                self.async_update_callback,
                timedelta(seconds=self._status_update_interval)
            )

        if not self._status_value and self._remove_time_interval:
            self._remove_time_interval()
            self._remove_time_interval = None

        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """"""

        self._status_value = self._mesh.check_for_update_status
        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_CHECK_FOR_UPDATES_STATUS,
                target=self.async_update_callback,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """"""

        if self._remove_time_interval:
            self._remove_time_interval()

    @property
    def is_on(self) -> bool:
        """"""

        return self._status_value


class LinksysVelopMeshSpeedtestStatusBinarySensor(LinksysVelopMeshBinarySensor):
    """"""

    _attribute = "Speedtest Status"
    _status_text: str = ""
    _status_update_interval: int = 1
    _remove_time_interval: Union[CALLBACK_TYPE, None] = None

    @callback
    async def async_update_callback(self, _: Union[datetime, None] = None):
        """"""

        self._status_text = await self._mesh.async_get_speedtest_state()
        if self._status_text:
            if not self._remove_time_interval:
                self._remove_time_interval = async_track_time_interval(
                    self.hass,
                    self.async_update_callback,
                    timedelta(seconds=self._status_update_interval)
                )
        else:
            if self._remove_time_interval:
                self._remove_time_interval()
                self._remove_time_interval = None
                async_dispatcher_send(self.hass, SIGNAL_UPDATE_SPEEDTEST_RESULTS)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """"""

        self.async_on_remove(
            async_dispatcher_connect(
                hass=self.hass,
                signal=SIGNAL_UPDATE_SPEEDTEST_STATUS,
                target=self.async_update_callback,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """"""

        if self._remove_time_interval:
            self._remove_time_interval()

    @property
    def is_on(self) -> bool:
        """"""

        return self._status_text != ""

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """"""

        return {
            "status": self._status_text
        }


class LinksysVelopMeshParentalControlBinarySensor(LinksysVelopMeshPolledBinarySensor):
    """"""

    _attribute = "Parental Control"

    @property
    def is_on(self) -> bool:
        return self._mesh.parental_control_enabled


class LinksysVelopMeshGuestWiFiBinarySensor(LinksysVelopMeshPolledBinarySensor):
    """"""

    _attribute = "Guest Wi-Fi"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        ret = {
            f"network {idx}": network
            for idx, network in enumerate(self._mesh.guest_wifi_details)
        }
        return ret

    @property
    def is_on(self) -> bool:
        return self._mesh.guest_wifi_enabled


class LinksysVelopMeshWANBinarySensor(LinksysVelopMeshPolledBinarySensor):
    """"""

    _attribute = "WAN Status"
    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "ip": self._mesh.wan_ip,
            "dns": self._mesh.wan_dns,
            "mac": self._mesh.wan_mac,
        }

    @property
    def is_on(self) -> bool:
        return self._mesh.wan_status


class LinksysVelopNodeStatusBinarySensor(LinksysVelopNodePolledBinarySensor):
    """"""

    _attribute = "Status"
    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        ret = {}
        node: Node = self._get_node()
        if node.connected_adapters:
            ret = node.connected_adapters[0]

        return ret

    @property
    def is_on(self) -> bool:
        node: Node = self._get_node()
        return node.status
