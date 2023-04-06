"""Helpers."""

# region #-- imports --#
from __future__ import annotations

import copy
import logging

from typing import List, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import device_registry as dr
from homeassistant.config_entries import entity_registry as er
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers import issue_registry as ir
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION

from .const import (
    CONF_DEVICE_TRACKERS,
    CONF_DEVICE_TRACKERS_MISSING,
    CONF_DEVICE_UI,
    CONF_DEVICE_UI_MISSING,
    CONF_LOGGING_OPTION_INCLUDE_SERIAL,
    CONF_LOGGING_OPTIONS,
    DEF_LOGGING_OPTIONS,
    DEVICE_TRACKER_DOMAIN,
    DOMAIN,
    ISSUE_MISSING_DEVICE_TRACKER,
    ISSUE_MISSING_UI_DEVICE,
)
from .logger import Logger

# endregion


_LOGGER = logging.getLogger(__name__)


def dr_device_is_mesh(device: DeviceEntry) -> bool:
    """Establish if the given device is the Mesh."""
    return all(
        [
            device.entry_type == DeviceEntryType.SERVICE,
            device.manufacturer == PYVELOP_AUTHOR,
            device.model == f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            device.name.lower() == "mesh",
        ]
    )


def dr_mesh_for_config_entry(
    config: ConfigEntry, device_registry: dr.DeviceRegistry
) -> DeviceEntry | None:
    """Get the Mesh object for the ConfigEntry."""
    my_devices: List[DeviceEntry] = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=config.entry_id
    )
    ret: List[DeviceEntry] = [
        dr_device for dr_device in my_devices if dr_device_is_mesh(device=dr_device)
    ]

    if ret:
        return ret[0]

    return None


def dr_nodes_for_mesh(
    config: ConfigEntry, device_registry: dr.DeviceRegistry
) -> List[DeviceEntry]:
    """Get the Nodes for a Mesh object."""
    my_devices: List[DeviceEntry] = dr.async_entries_for_config_entry(
        registry=device_registry, config_entry_id=config.entry_id
    )
    ret: List[DeviceEntry] = [
        dr_device
        for dr_device in my_devices
        if all(
            [
                dr_device.manufacturer != PYVELOP_AUTHOR,
                dr_device.name.lower() != "mesh",
            ]
        )
    ]

    return ret or None


def include_serial_logging(config: ConfigEntry):
    """Establish if the serial number should be logged."""
    return CONF_LOGGING_OPTION_INCLUDE_SERIAL in config.options.get(
        CONF_LOGGING_OPTIONS, DEF_LOGGING_OPTIONS
    )


def mesh_intensive_action_running(
    config_entry: ConfigEntry,
    hass: HomeAssistant,
) -> Tuple[bool, str]:
    """Establish if an intesive action is running."""
    intensive_actions: List[str] = ["Channel Scanning"]

    entity_registry: EntityRegistry = er.async_get(hass=hass)

    reg_entry: er.RegistryEntry
    ce_entities: List[er.RegistryEntry] = [
        reg_entry
        for _, reg_entry in entity_registry.entities.items()
        if reg_entry.domain == "binary_sensor"
        and reg_entry.config_entry_id == config_entry.entry_id
        and reg_entry.original_name in intensive_actions
    ]
    ce_entity_states: List[bool] = [
        hass.states.is_state(ce_entity.entity_id, "on") for ce_entity in ce_entities
    ]
    if any(ce_entity_states):
        idx: int = ce_entity_states.index(True)
        ret = (True, ce_entities[idx].original_name)
    else:
        ret = (False, "")

    return ret


def stop_tracking_device(
    config_entry: ConfigEntry,
    device_id: List[str] | str,
    hass: HomeAssistant,
    device_type: str = CONF_DEVICE_TRACKERS,
    raise_repair: bool = True,
) -> None:
    """Stop tracking the given device."""
    if include_serial_logging(config=config_entry):
        log_formatter = Logger(unique_id=config_entry.unique_id)
    else:
        log_formatter = Logger()

    _LOGGER.debug(log_formatter.format("entered"))
    if not isinstance(device_id, list):
        device_id = [device_id]

    _LOGGER.debug(
        log_formatter.format("processing devices: %s of type %s, raise_repair: %s"),
        device_id,
        device_type,
        raise_repair,
    )
    new_options = copy.deepcopy(
        dict(**config_entry.options)
    )  # deepcopy a dict copy so we get all the options
    trackers: List[str] | None
    if (trackers := new_options.get(device_type, None)) is not None:
        for tracker_id in device_id:
            if tracker_id in trackers:
                _LOGGER.debug(
                    log_formatter.format("removing %s from config key"), tracker_id
                )
                trackers.remove(tracker_id)
        new_options[device_type] = trackers
        _LOGGER.debug(log_formatter.format("updating stored config key"))
        hass.config_entries.async_update_entry(entry=config_entry, options=new_options)
        for dev in device_id:
            _LOGGER.debug(log_formatter.format("processing %s"), dev)
            # region #-- manage UI devices --#
            if device_type in (CONF_DEVICE_UI, CONF_DEVICE_UI_MISSING):
                device_registry: dr.DeviceRegistry = dr.async_get(hass=hass)
                device_details: dr.DeviceEntry | None = (
                    device_registry.async_get_device(identifiers={(DOMAIN, dev)})
                )
                if device_details is not None:
                    if raise_repair:
                        _LOGGER.debug(
                            log_formatter.format("raising repair for device: %s"),
                            device_details.id,
                        )
                        ir.async_create_issue(
                            hass=hass,
                            data={
                                "device_id": device_details.id,
                                "device_name": device_details.name,
                            },
                            domain=DOMAIN,
                            is_fixable=True,
                            is_persistent=True,
                            issue_id=ISSUE_MISSING_UI_DEVICE,
                            severity=ir.IssueSeverity.WARNING,
                            translation_key=ISSUE_MISSING_UI_DEVICE,
                            translation_placeholders={
                                "device_name": device_details.name,
                            },
                        )
                    else:
                        _LOGGER.debug(
                            log_formatter.format("removing device: %s"),
                            device_details.id,
                        )
                        device_registry.async_remove_device(device_id=device_details.id)
            # endregion
            # region #-- manage device trackers --#
            elif device_type in (CONF_DEVICE_TRACKERS, CONF_DEVICE_TRACKERS_MISSING):
                entity_registry: er.EntityRegistry = er.async_get(hass=hass)
                entity_details: List[
                    er.RegistryEntry
                ] = er.async_entries_for_config_entry(
                    registry=entity_registry,
                    config_entry_id=config_entry.entry_id,
                )
                ent: List[er.RegistryEntry] = [
                    e
                    for e in entity_details
                    if e.unique_id.endswith(f"::{DEVICE_TRACKER_DOMAIN}::{dev}")
                ]
                if len(ent) != 0:
                    if raise_repair:
                        _LOGGER.debug(
                            log_formatter.format("raising repair for: %s"),
                            ent[0].entity_id,
                        )
                        ir.async_create_issue(
                            hass=hass,
                            data={
                                "device_id": ent[0].entity_id,
                                "device_name": ent[0].name or ent[0].original_name,
                            },
                            domain=DOMAIN,
                            is_fixable=True,
                            is_persistent=True,
                            issue_id=ISSUE_MISSING_DEVICE_TRACKER,
                            severity=ir.IssueSeverity.WARNING,
                            translation_key=ISSUE_MISSING_DEVICE_TRACKER,
                            translation_placeholders={
                                "device_name": ent[0].name or ent[0].original_name,
                            },
                        )
                    else:
                        _LOGGER.debug(
                            log_formatter.format("removing entity: %s"),
                            ent[0].entity_id,
                        )
                        entity_registry.async_remove(entity_id=ent[0].entity_id)
            # endregion

    _LOGGER.debug(log_formatter.format("entered"))
