"""Helpers."""

# region #-- imports --#
from __future__ import annotations

import copy
import logging
from typing import List

from homeassistant.config_entries import device_registry as dr
from homeassistant.config_entries import entity_registry as er
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceRegistry,
)
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION

from .const import (  # CONF_DEVICE_TRACKERS_MISSING,
    CONF_DEVICE_TRACKERS,
    CONF_DEVICE_UI_MISSING,
    CONF_LOGGING_OPTION_INCLUDE_SERIAL,
    CONF_LOGGING_OPTIONS,
    CONF_UI_DEVICES,
    DEF_LOGGING_OPTIONS,
    DEVICE_TRACKER_DOMAIN,
    DOMAIN,
    ISSUE_MISSING_DEVICE_TRACKER,
    ISSUE_MISSING_UI_DEVICE,
)
from .logger import Logger
from .types import LinksysVelopConfigEntry

# endregion


_LOGGER: logging.Logger = logging.getLogger(__name__)


def get_mesh_device_for_config_entry(
    hass: HomeAssistant, config_entry: LinksysVelopConfigEntry
) -> DeviceEntry | None:
    """"""
    device_registry: DeviceRegistry = dr.async_get(hass)
    found_mesh: DeviceEntry | None = device_registry.async_get_device(
        {(DOMAIN, config_entry.entry_id)}
    )
    return found_mesh


def include_serial_logging(config_entry: LinksysVelopConfigEntry):
    """Establish if the serial number should be logged."""
    return CONF_LOGGING_OPTION_INCLUDE_SERIAL in config_entry.options.get(
        CONF_LOGGING_OPTIONS, DEF_LOGGING_OPTIONS
    )


def remove_velop_device_from_registry(hass: HomeAssistant, device_id: str) -> None:
    """"""

    _LOGGER.debug("remove_velop_device_from_registry: entered, (%s)", device_id)
    device_registry: DeviceRegistry = dr.async_get(hass)
    found_device: DeviceEntry | None
    if (
        found_device := device_registry.async_get_device({(DOMAIN, device_id)})
    ) is not None:
        device_registry.async_remove_device(found_device.id)
    else:
        _LOGGER.debug("remove_velop_device_from_registry: device not found")

    _LOGGER.debug("remove_velop_device_from_registry: exited")


def remove_velop_entity_from_registry(
    hass: HomeAssistant, config_entry_id: str, unique_id: str
) -> None:
    """Remove an entity from the registry."""

    _LOGGER.debug("remove_velop_entity_from_registry: entered, (%s)", unique_id)
    entity_registry: EntityRegistry = er.async_get(hass)
    config_entities: list[RegistryEntry] = er.async_entries_for_config_entry(
        entity_registry, config_entry_id
    )
    found_entity: list[RegistryEntry]
    if found_entity := [e for e in config_entities if e.unique_id == unique_id]:
        entity_registry.async_remove(found_entity[0].entity_id)
    else:
        _LOGGER.debug("remove_velop_entity_from_registry: entity not found")

    _LOGGER.debug("remove_velop_entity_from_registry: exited, (%s)", unique_id)


#
#  TODO: Check all the following to see if they are required.
#


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
    config: LinksysVelopConfigEntry, device_registry: dr.DeviceRegistry
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
    config: LinksysVelopConfigEntry, device_registry: dr.DeviceRegistry
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
                len(dr_device.connections) == 0,
            ]
        )
    ]

    return ret or None


def stop_tracking_device(
    config_entry: LinksysVelopConfigEntry,
    device_id: List[str] | str,
    hass: HomeAssistant,
    device_type: str = CONF_DEVICE_TRACKERS,
    raise_repair: bool = True,
) -> None:
    """Stop tracking the given device."""
    if include_serial_logging(config_entry):
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
            if device_type in (CONF_UI_DEVICES, CONF_DEVICE_UI_MISSING):
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
            elif device_type in (
                CONF_DEVICE_TRACKERS
            ):  # , CONF_DEVICE_TRACKERS_MISSING):
                entity_registry: er.EntityRegistry = er.async_get(hass=hass)
                entity_details: List[er.RegistryEntry] = (
                    er.async_entries_for_config_entry(
                        registry=entity_registry,
                        config_entry_id=config_entry.entry_id,
                    )
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
