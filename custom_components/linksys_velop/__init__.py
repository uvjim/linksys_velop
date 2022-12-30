"""The Linksys Velop integration."""

# region #-- imports --#
from __future__ import annotations

import datetime
import logging
from datetime import timedelta
from typing import Any, Callable, Dict, List, Mapping, Set

import homeassistant.helpers.entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import device_registry as dr
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry, DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import slugify
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.device import Device
from pyvelop.exceptions import (
    MeshConnectionError,
    MeshDeviceNotFoundResponse,
    MeshException,
    MeshInvalidOutput,
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh
from pyvelop.node import Node, NodeType

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_COORDINATOR,
    CONF_COORDINATOR_MESH,
    CONF_DEVICE_TRACKERS,
    CONF_ENTRY_RELOAD,
    CONF_LOGGING_JNAP_RESPONSE,
    CONF_LOGGING_MODE,
    CONF_LOGGING_SERIAL,
    CONF_NODE,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SERVICES_HANDLER,
    CONF_UNSUB_UPDATE_LISTENER,
    DEF_API_REQUEST_TIMEOUT,
    DEF_LOGGING_JNAP_RESPONSE,
    DEF_LOGGING_MODE,
    DEF_LOGGING_SERIAL,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DOMAIN,
    ENTITY_SLUG,
    LOGGING_MODE_SELECTOR,
    PLATFORMS,
    SIGNAL_UPDATE_DEVICE_TRACKER,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .events import EVENT_TYPE, EventSubType, build_payload
from .helpers import (
    dr_nodes_for_mesh,
    mesh_intensive_action_running,
    stop_tracking_device,
)
from .logger import Logger
from .service_handler import LinksysVelopServiceHandler

# endregion

_LOGGER = logging.getLogger(__name__)

LOGGING_ON: str = logging.getLevelName(logging.DEBUG)
LOGGING_OFF: str = logging.getLevelName(_LOGGER.level)
LOGGING_REVERT: str = logging.getLevelName(logging.getLogger("").level)
LOGGING_DISABLED: bool = False


async def async_logging_state(
    config_entry: ConfigEntry, hass: HomeAssistant, log_formatter: Logger, state: bool
) -> None:
    """Turn logging on or off."""
    global LOGGING_DISABLED  # pylint: disable=global-statement

    logging_level: str = LOGGING_ON if state else LOGGING_OFF
    if logging_level == LOGGING_ON and config_entry.options.get(
        CONF_LOGGING_JNAP_RESPONSE, DEF_LOGGING_JNAP_RESPONSE
    ):
        logging_level_jnap_response: str = LOGGING_ON
    else:
        logging_level_jnap_response: str = LOGGING_REVERT
    if not state:
        _LOGGER.debug(log_formatter.format("log state: %s"), logging_level)
        _LOGGER.debug(
            log_formatter.format("JNAP response log state: %s"),
            logging_level_jnap_response,
        )
    try:
        await hass.services.async_call(
            blocking=True,
            domain="logger",
            service="set_level",
            service_data={
                f"custom_components.{DOMAIN}": logging_level,
                PYVELOP_NAME: logging_level,
                f"{PYVELOP_NAME}.jnap.verbose": logging_level_jnap_response,
            },
        )
    except ServiceNotFound:
        if not LOGGING_DISABLED:
            _LOGGER.warning(
                log_formatter.format(
                    "The logger integration is not enabled. Turning integration logging off."
                )
            )
            options: Dict = dict(**config_entry.options)
            options[CONF_LOGGING_MODE] = "off"
            hass.config_entries.async_update_entry(entry=config_entry, options=options)
            LOGGING_DISABLED = True
    else:
        _LOGGER.debug(log_formatter.format("log state: %s"), logging_level)
        _LOGGER.debug(
            log_formatter.format("JNAP response log state: %s"),
            logging_level_jnap_response,
        )
        if (
            not state
            and config_entry.options.get(CONF_LOGGING_MODE, DEF_LOGGING_MODE) != "off"
        ):
            options: Dict = dict(**config_entry.options)
            options[CONF_LOGGING_MODE] = "off"
            hass.config_entries.async_update_entry(entry=config_entry, options=options)
            if hass.state != CoreState.stopping:
                hass.bus.async_fire(
                    event_type=EVENT_TYPE,
                    event_data=build_payload(
                        config_entry=config_entry,
                        event=EventSubType.LOGGING_STOPPED,
                        hass=hass,
                    ),
                )


async def async_remove_config_entry_device(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow device removal.

    Do not allow the Mesh device to be removed
    """
    if config_entry.options.get(CONF_LOGGING_SERIAL, DEF_LOGGING_SERIAL):
        log_formatter = Logger(unique_id=config_entry.unique_id)
    else:
        log_formatter = Logger()

    if all(
        [  # check for Mesh device
            device_entry.name == "Mesh",
            device_entry.manufacturer == PYVELOP_AUTHOR,
            device_entry.model == f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
        ]
    ):
        _LOGGER.error(
            log_formatter.format("Attempt to remove the Mesh device rejected")
        )
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Create a config entry."""
    if config_entry.options.get(CONF_LOGGING_SERIAL, DEF_LOGGING_SERIAL):
        log_formatter = Logger(unique_id=config_entry.unique_id)
    else:
        log_formatter = Logger()

    # region #-- start logging if needed --#
    logging_mode: bool = config_entry.options.get(CONF_LOGGING_MODE, DEF_LOGGING_MODE)
    if (
        logging_mode in [mode.get("value") for mode in LOGGING_MODE_SELECTOR]
        and logging_mode != "off"
    ):
        await async_logging_state(
            config_entry=config_entry,
            hass=hass,
            log_formatter=log_formatter,
            state=True,
        )
    # endregion

    _LOGGER.debug(log_formatter.format("entered"))
    _LOGGER.debug(
        log_formatter.format("logging mode: %s"),
        logging_mode,
    )

    # region #-- prepare the memory storage --#
    _LOGGER.debug(log_formatter.format("preparing memory storage"))
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    hass.data[DOMAIN][config_entry.entry_id]["intensive_running"] = None
    # endregion

    # region #-- setup the coordinator for data updates --#
    _LOGGER.debug(log_formatter.format("setting up Mesh for the coordinator"))
    hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR_MESH] = Mesh(
        node=config_entry.options[CONF_NODE],
        password=config_entry.options[CONF_PASSWORD],
        request_timeout=config_entry.options.get(
            CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
        ),
        session=async_get_clientsession(hass=hass),
    )

    async def _async_get_mesh_data() -> Mesh:
        """Fetch the latest data from the Mesh.

        Will signal relevant sensors that have a state that needs updating more frequently
        """
        _LOGGER.debug(log_formatter.format("entered"))

        mesh: Mesh = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR_MESH]
        device_registry: dr.DeviceRegistry = dr.async_get(hass=hass)

        # -- get the existing devices --#
        _LOGGER.debug(
            log_formatter.format("retrieving existing devices for comparison")
        )
        device: Device
        try:
            previous_devices: Set[str] = {device.unique_id for device in mesh.devices}
        except MeshException:
            previous_devices: Set[str] = {}

        # -- get the existing nodes --#
        _LOGGER.debug(log_formatter.format("retrieving existing nodes for comparison"))
        if (
            previous_nodes := dr_nodes_for_mesh(
                config=config_entry, device_registry=device_registry
            )
        ) is not None:
            previous_nodes_serials: Set[str] = {
                next(iter(prev_node.identifiers))[1]  # serial number of node
                for prev_node in previous_nodes
            }

        try:
            # -- gather details from the API --#
            _LOGGER.debug(log_formatter.format("gathering details"))
            await mesh.async_gather_details()
            if mesh.speedtest_status:
                _LOGGER.debug(log_formatter.format("dispatching speedtest signal"))
                async_dispatcher_send(hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)
        except MeshTimeoutError as err:
            _LOGGER.warning(
                log_formatter.format(
                    "timeout gathering data from the mesh (current timeout: %.2f) - consider increasing the timeout"
                ),
                config_entry.options.get(
                    CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT
                ),
            )
            raise UpdateFailed(err) from err
        except Exception as err:
            _LOGGER.debug(log_formatter.format("error type: %s"), type(err))
            _LOGGER.error(log_formatter.format(err))
            raise UpdateFailed(err) from err
        else:
            # region #-- check for new devices --#
            if not previous_devices:
                _LOGGER.debug(
                    log_formatter.format("no previous devices - ignoring comparison")
                )
            else:
                _LOGGER.debug(log_formatter.format("comparing devices"))
                current_devices: Set[str] = {
                    device.unique_id for device in mesh.devices
                }
                new_devices: Set[str] = current_devices.difference(previous_devices)
                if new_devices:
                    for device in mesh.devices:
                        if device.unique_id in new_devices:
                            # -- fire the event --#
                            payload = build_payload(
                                config_entry=config_entry,
                                device=device,
                                event=EventSubType.NEW_DEVICE,
                                hass=hass,
                            )
                            _LOGGER.debug(
                                log_formatter.format("%s: %s"),
                                EventSubType.NEW_DEVICE.value,
                                payload,
                            )
                            hass.bus.async_fire(
                                event_type=EVENT_TYPE,
                                event_data=payload,
                            )
                _LOGGER.debug(log_formatter.format("devices compared"))
            # endregion

            # region #-- check for new or update nodes --#
            if not previous_nodes:
                _LOGGER.debug(
                    log_formatter.format("no previous nodes - ignoring comparison")
                )
            else:
                _LOGGER.debug(log_formatter.format("comparing nodes"))
                node: Node
                current_nodes: Set[str] = {node.serial for node in mesh.nodes}
                # region #-- process new nodes --#
                new_nodes: Set[str] = current_nodes.difference(previous_nodes_serials)
                is_reloading = (
                    hass.data[DOMAIN]
                    .get(CONF_ENTRY_RELOAD, {})
                    .get(config_entry.entry_id)
                )
                if new_nodes and not is_reloading:
                    for node in mesh.nodes:
                        if node.serial in new_nodes:
                            _LOGGER.debug(
                                log_formatter.format("new node found: %s"), node.serial
                            )
                            if hass.state == CoreState.running:  # reload the config
                                if CONF_ENTRY_RELOAD not in hass.data[DOMAIN]:
                                    hass.data[DOMAIN][CONF_ENTRY_RELOAD] = {}
                                hass.data[DOMAIN][CONF_ENTRY_RELOAD][
                                    config_entry.entry_id
                                ] = True
                                await hass.config_entries.async_reload(
                                    config_entry.entry_id
                                )
                                hass.data[DOMAIN].get(CONF_ENTRY_RELOAD, {}).pop(
                                    config_entry.entry_id, None
                                )

                            # -- fire the event --#
                            payload = build_payload(
                                config_entry=config_entry,
                                device=node,
                                event=EventSubType.NEW_NODE,
                                hass=hass,
                            )
                            _LOGGER.debug(
                                log_formatter.format("%s: %s"),
                                EventSubType.NEW_NODE,
                                payload,
                            )
                            hass.bus.async_fire(
                                event_type=EVENT_TYPE, event_data=payload
                            )
                # endregion
                # region #-- look for updates to nodes --#
                update_properties = ["name"]
                for node in mesh.nodes:
                    previous_node: List[
                        DeviceEntry
                    ] = [  # get the node from the device registry based on serial
                        prev_node
                        for prev_node in previous_nodes
                        if next(iter(prev_node.identifiers))[1].lower()
                        == node.serial.lower()
                    ]
                    if not previous_node:
                        continue

                    for prop in update_properties:
                        if getattr(previous_node[0], prop, None) != getattr(
                            node, prop, None
                        ):
                            _LOGGER.debug(
                                log_formatter.format("updating %s for %s (%s --> %s)"),
                                prop,
                                node.serial,
                                getattr(previous_node[0], prop, None),
                                getattr(node, prop),
                            )
                            device_registry.async_update_device(
                                device_id=previous_node[0].id, name=getattr(node, prop)
                            )

                # endregion
                _LOGGER.debug(log_formatter.format("nodes compared"))
            # endregion

            # region #-- check for a primary node change --#
            primary_node: List[Node] = [
                node for node in mesh.nodes if node.type == "primary"
            ]
            if primary_node and primary_node[0].serial != config_entry.unique_id:
                _LOGGER.debug(
                    log_formatter.format("assuming the primary node has changed")
                )
                if hass.state == CoreState.running:
                    if hass.config_entries.async_update_entry(
                        entry=config_entry, unique_id=primary_node[0].serial
                    ):
                        payload: Dict[str, Any] = build_payload(
                            config_entry=config_entry,
                            device=primary_node[0],
                            event=EventSubType.NEW_PRIMARY_NODE,
                            hass=hass,
                        )
                        hass.bus.async_fire(
                            event_type=EventSubType.NEW_PRIMARY_NODE, event_data=payload
                        )
                else:
                    _LOGGER.debug(
                        log_formatter.format(
                            "backing off updates until HASS is fully running"
                        )
                    )
            # endregion

            hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR_MESH] = mesh

        _LOGGER.debug(log_formatter.format("exited"))
        return mesh

    _LOGGER.debug(log_formatter.format("setting up the coordinator"))
    coordinator_name = DOMAIN
    if getattr(log_formatter, "_unique_id"):
        coordinator_name += f" ({getattr(log_formatter, '_unique_id')})"
    coordinator = DataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        name=coordinator_name,
        update_interval=timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEF_SCAN_INTERVAL)
        ),
        update_method=_async_get_mesh_data,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR] = coordinator
    # endregion

    if logging_mode == "single":
        await async_logging_state(
            config_entry=config_entry,
            hass=hass,
            log_formatter=log_formatter,
            state=False,
        )

    # region #-- setup the platforms --#
    setup_platforms: List[str] = list(filter(None, PLATFORMS))
    _LOGGER.debug(log_formatter.format("setting up platforms: %s"), setup_platforms)
    # TODO: remove try/except when minimum version is 2022.8.0
    try:
        await hass.config_entries.async_forward_entry_setups(
            config_entry, setup_platforms
        )
    except AttributeError:
        hass.config_entries.async_setup_platforms(config_entry, setup_platforms)
    # endregion

    # region #-- Service Definition --#
    _LOGGER.debug(log_formatter.format("registering services"))
    services = LinksysVelopServiceHandler(hass=hass)
    services.register_services()
    hass.data[DOMAIN][config_entry.entry_id][CONF_SERVICES_HANDLER] = services
    # endregion

    # region #-- listen for config changes --#
    _LOGGER.debug(log_formatter.format("listening for config changes"))
    hass.data[DOMAIN][config_entry.entry_id][
        CONF_UNSUB_UPDATE_LISTENER
    ] = config_entry.add_update_listener(_async_update_listener)
    # endregion

    async def device_tracker_update(_: datetime.datetime) -> None:
        """Manage the device tracker updates.

        Uses the _ variable to ignore IDE checking for unused variables

        Gets the device status from the mesh before dispatching the message

        :param _: datetime object for when the event was fired
        :return: None
        """
        mesh: Mesh = coordinator.data
        if mesh is not None:
            devices: List[Device] = []
            try:
                devices = await mesh.async_get_device_from_id(
                    device_id=config_entry.options.get(CONF_DEVICE_TRACKERS),
                    force_refresh=True,
                )
            except (MeshConnectionError, MeshTimeoutError) as err:
                # check if an intensive action is running so we can suppress warnings
                is_running, action = mesh_intensive_action_running(
                    config_entry=config_entry, hass=hass
                )
                if is_running:
                    if (
                        hass.data[DOMAIN][config_entry.entry_id]["intensive_running"]
                        is None
                    ):
                        hass.data[DOMAIN][config_entry.entry_id][
                            "intensive_running"
                        ] = is_running
                        _LOGGER.warning(
                            log_formatter.format(
                                "%s is running. Ignoring errors at this time."
                            ),
                            action,
                        )
                else:
                    _LOGGER.warning(log_formatter.format("%s"), err)
                    hass.data[DOMAIN][config_entry.entry_id]["intensive_running"] = None
                    return
            except MeshDeviceNotFoundResponse as err:
                # remove missing device trackers because they don't exist anymore
                _LOGGER.warning(
                    log_formatter.format("stop tracking %s as %s exist anymore"),
                    err.devices,
                    "they don't" if len(err.devices) != 1 else "it doesn't",
                )
                stop_tracking_device(
                    config_entry=config_entry, device_id=err.devices, hass=hass
                )
            except MeshInvalidOutput:
                _LOGGER.warning(
                    log_formatter.format(
                        "Invalid output received when checking device tracker status."
                    )
                )
                return

            # dispatch a message for the ones that were found
            device: Device
            for device in devices:
                async_dispatcher_send(
                    hass,
                    f"{SIGNAL_UPDATE_DEVICE_TRACKER}_{device.unique_id}",
                    device,
                )

    # region #-- set up the timer for checking device trackers --#
    if config_entry.options.get(CONF_DEVICE_TRACKERS, None):
        # only do setup if device trackers were selected
        _LOGGER.debug(log_formatter.format("setting up device trackers"))
        # update before setting the timer
        await device_tracker_update(datetime.datetime.now())
        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL_DEVICE_TRACKER, DEF_SCAN_INTERVAL_DEVICE_TRACKER
        )
        config_entry.async_on_unload(
            async_track_time_interval(
                hass, device_tracker_update, timedelta(seconds=scan_interval)
            )
        )
    else:
        _LOGGER.debug(log_formatter.format("no device trackers set"))
    # endregion

    _LOGGER.debug(log_formatter.format("exited"))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Cleanup when unloading a config entry."""
    if config_entry.options.get(CONF_LOGGING_SERIAL, DEF_LOGGING_SERIAL):
        log_formatter = Logger(unique_id=config_entry.unique_id)
    else:
        log_formatter = Logger()

    _LOGGER.debug(log_formatter.format("entered"))

    # region #-- unsubscribe from listening for updates --#
    if hass.data[DOMAIN][config_entry.entry_id][CONF_UNSUB_UPDATE_LISTENER]:
        _LOGGER.debug(log_formatter.format("stop listening for updates"))
        hass.data[DOMAIN][config_entry.entry_id][CONF_UNSUB_UPDATE_LISTENER]()
    # endregion

    # region #-- remove services but only if there are no other instances --#
    all_config_entries = hass.config_entries.async_entries(domain=DOMAIN)
    _LOGGER.debug(log_formatter.format("%i instances"), len(all_config_entries))
    if len(all_config_entries) == 1:
        _LOGGER.debug(log_formatter.format("unregistering services"))
        services: LinksysVelopServiceHandler = hass.data[DOMAIN][config_entry.entry_id][
            CONF_SERVICES_HANDLER
        ]
        services.unregister_services()
    # endregion

    # region #-- clean up the platforms --#
    _LOGGER.debug(log_formatter.format("cleaning up platforms"))
    ret = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if ret:
        _LOGGER.debug(log_formatter.format("removing data from memory"))
        hass.data[DOMAIN].pop(config_entry.entry_id)
        ret = True
    else:
        ret = False
    # endregion

    _LOGGER.debug(log_formatter.format("exited"))
    return ret


async def _async_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)


# region #-- base entities --#
class LinksysVelopMeshEntity(CoordinatorEntity):
    """Representation of a Mesh entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description,
    ) -> None:
        """Initialise Mesh entity."""
        super().__init__(coordinator=coordinator)
        self._config = config_entry
        self._log_formatter: Logger = Logger(unique_id=config_entry.unique_id)
        self._mesh: Mesh = coordinator.data

        self.entity_description = description

        if not getattr(self, "entity_domain", None):
            self.entity_domain: str = ""

        try:
            _ = self.has_entity_name
            self._attr_has_entity_name = True
            self._attr_name = self.entity_description.name
        except AttributeError:
            self._attr_name = f"{ENTITY_SLUG} Mesh: {self.entity_description.name}"

        self._attr_unique_id = (
            f"{config_entry.entry_id}::"
            f"{self.entity_domain.lower()}::"
            f"{slugify(self.entity_description.name)}"
        )

    def _handle_coordinator_update(self) -> None:
        """Update the information when the coordinator updates."""
        if self.coordinator.data is not None:
            self._mesh = self.coordinator.data
            self._attr_available = True
        else:
            self._attr_available = False
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        # noinspection HttpUrlsUsage
        ret = DeviceInfo(
            configuration_url=f"http://{self._mesh.connected_node}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._config.entry_id)},
            manufacturer=PYVELOP_AUTHOR,
            model=f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            name="Mesh",
            sw_version="",
        )
        return ret

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Additional attributes for the entity."""
        if hasattr(self.entity_description, "extra_attributes"):
            if isinstance(self.entity_description.extra_attributes, Callable):
                return self.entity_description.extra_attributes(self._mesh)

            if isinstance(self.entity_description.extra_attributes, str):
                if (
                    esa := getattr(self._mesh, self.entity_description.extra_attributes)
                ) is not None:
                    if not isinstance(esa, dict):
                        _LOGGER.debug(
                            self._log_formatter.format(
                                "%s is not a dictionary or None"
                            ),
                            self.entity_description.extra_attributes,
                        )
                    else:
                        return esa

        return None


class LinksysVelopNodeEntity(CoordinatorEntity):
    """Representation of a Node entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description,
        node: Node,
    ) -> None:
        """Initialise the Node entity."""
        super().__init__(coordinator=coordinator)

        self.entity_description = description
        if not getattr(self, "entity_description", None):
            self.entity_domain: str = ""
        else:
            if hasattr(self.entity_description, "entity_picture"):
                self._attr_entity_picture = self.entity_description.entity_picture

        self._config = config_entry
        self._mesh: Mesh = coordinator.data
        self._node_id: str = node.unique_id
        self._node: Node = self._get_node()

        try:
            _ = self.has_entity_name
            self._attr_has_entity_name = True
            self._attr_name = self.entity_description.name
        except AttributeError:
            self._attr_name = (
                f"{ENTITY_SLUG} {self._node.name}: {self.entity_description.name}"
            )

        self._attr_unique_id = (
            f"{self._node.unique_id}::"
            f"{self.entity_domain.lower()}::"
            f"{slugify(self.entity_description.name)}"
        )

    def _get_node(self) -> Node | None:
        """Get the current node."""
        node = [n for n in self._mesh.nodes if n.unique_id == self._node_id]
        if node:
            return node[0]

        return None

    def _handle_coordinator_update(self) -> None:
        """Update the information when the coordinator updates."""
        if self.coordinator.data is not None:
            self._mesh = self.coordinator.data
            if (node := self._get_node()) is not None:
                self._node = node
                self._attr_available = True
            else:
                self._attr_available = False
        else:
            self._attr_available = False
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        ret = DeviceInfo(
            hw_version=self._node.hardware_version,
            identifiers={(DOMAIN, self._node.serial)},
            model=self._node.model,
            name=self._node.name,
            manufacturer=self._node.manufacturer,
            sw_version=self._node.firmware.get("version", ""),
        )
        if self._node.connected_adapters:
            ret["configuration_url"] = (
                f"http://{self._node.connected_adapters[0].get('ip')}"
                f"{'/ca' if self._node.type is NodeType.SECONDARY else ''}"
            )

        return ret

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Additional attributes for the entity."""
        if (
            hasattr(self.entity_description, "extra_attributes")
            and isinstance(self.entity_description.extra_attributes, Callable)
            and self._node
        ):
            return self.entity_description.extra_attributes(self._node)

        return None


# endregion


# region #-- cleanup entities --#
def entity_cleanup(
    config_entry: ConfigEntry,
    entities: List[LinksysVelopMeshEntity | LinksysVelopNodeEntity],
    hass: HomeAssistant,
):
    """Remove entities from the registry if they are no longer needed."""
    if config_entry.options.get(CONF_LOGGING_SERIAL, DEF_LOGGING_SERIAL):
        log_formatter = Logger(
            unique_id=config_entry.unique_id,
            prefix=f"{entities[0].__class__.__name__} --> ",
        )
    else:
        log_formatter = Logger(
            prefix=f"{entities[0].__class__.__name__} --> ",
        )

    _LOGGER.debug(log_formatter.format("entered"))

    entity_registry: er.EntityRegistry = er.async_get(hass=hass)
    er_entries: List[er.RegistryEntry] = er.async_entries_for_config_entry(
        registry=entity_registry, config_entry_id=config_entry.entry_id
    )

    cleanup_unique_ids = [e.unique_id for e in entities]
    for entity in er_entries:
        if entity.unique_id not in cleanup_unique_ids:
            continue

        # remove the entity
        _LOGGER.debug(log_formatter.format("removing %s"), entity.entity_id)
        entity_registry.async_remove(entity_id=entity.entity_id)

    _LOGGER.debug(log_formatter.format("exited"))


# endregion
