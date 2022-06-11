"""The Linksys Velop integration"""

# region #-- imports --#
from __future__ import annotations

import datetime
import logging
from datetime import timedelta
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Set,
)

import homeassistant.helpers.entity_registry as er
from homeassistant.config_entries import (
    ConfigEntry,
    device_registry as dr,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import (
    CoreState,
    HomeAssistant,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed
)
from homeassistant.util import slugify
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.device import Device
from pyvelop.exceptions import MeshTimeoutError
from pyvelop.mesh import Mesh
from pyvelop.node import Node

from .const import (
    CONF_API_REQUEST_TIMEOUT,
    CONF_COORDINATOR,
    CONF_COORDINATOR_MESH,
    CONF_DEVICE_TRACKERS,
    CONF_ENTRY_RELOAD,
    CONF_NODE,
    CONF_SCAN_INTERVAL_DEVICE_TRACKER,
    CONF_SERVICES_HANDLER,
    CONF_UNSUB_UPDATE_LISTENER,
    DEF_API_REQUEST_TIMEOUT,
    DEF_SCAN_INTERVAL,
    DEF_SCAN_INTERVAL_DEVICE_TRACKER,
    DOMAIN,
    ENTITY_SLUG,
    EVENT_NEW_PARENT_NODE,
    PLATFORMS,
    SIGNAL_UPDATE_DEVICE_TRACKER,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .logger import Logger
from .service_handler import LinksysVelopServiceHandler

# endregion

_LOGGER = logging.getLogger(__name__)

EVENT_NEW_DEVICE_ON_MESH: str = f"{DOMAIN}_new_device_on_mesh"
EVENT_NEW_NODE_ON_MESH: str = f"{DOMAIN}_new_node_on_mesh"


def build_event_payload(
    config_entry: ConfigEntry,
    device: Device | Node,
    event: str,
    hass: HomeAssistant
) -> Dict[str, Any]:
    """"""

    event_properties: List[str] = []

    if event == EVENT_NEW_NODE_ON_MESH:
        event_properties = [
            "backhaul",
            "connected_adapters",
            "model",
            "name",
            "parent_name",
            "serial",
            "status",
            "unique_id",
        ]
    elif event == EVENT_NEW_DEVICE_ON_MESH:
        event_properties = [
            "connected_adapters",
            "description",
            "manufacturer",
            "model",
            "name",
            "operating_system",
            "parent_name",
            "serial",
            "status",
            "unique_id",
        ]
    elif event == EVENT_NEW_PARENT_NODE:
        event_properties = [
            "connected_adapters",
            "model",
            "name",
            "serial",
            "unique_id",
        ]

    ret: Dict[str, Any] = {
        prop: getattr(device, prop, None)
        for prop in event_properties
    }
    if ret:
        # region #-- get the mesh device_id --#
        device_registry: dr.DeviceRegistry = dr.async_get(hass=hass)
        my_devices: List[DeviceEntry] = dr.async_entries_for_config_entry(
            registry=device_registry,
            config_entry_id=config_entry.entry_id
        )
        dr_device: dr.DeviceEntry
        mesh_details: List[DeviceEntry] = [
            dr_device
            for dr_device in my_devices
            if (
                dr_device.manufacturer == PYVELOP_AUTHOR
                and dr_device.name.lower() == "mesh"
            )
        ]
        # endregion

        if mesh_details:
            ret["mesh_device_id"] = mesh_details[0].id

    return ret


# noinspection PyUnusedLocal
async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry
) -> bool:
    """"""

    log_formatter = Logger(unique_id=config_entry.unique_id)

    if all([  # check for Mesh device
        device_entry.name == "Mesh",
        device_entry.manufacturer == PYVELOP_AUTHOR,
        device_entry.model == f"{PYVELOP_NAME} ({PYVELOP_VERSION})"
    ]):
        _LOGGER.error(log_formatter.format("Attempt to remove the Mesh device rejected"))
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Setup a config entry"""

    log_formatter = Logger(unique_id=config_entry.unique_id)
    _LOGGER.debug(log_formatter.format("entered"))

    # region #-- prepare the memory storage --#
    _LOGGER.debug(log_formatter.format("preparing memory storage"))
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    # endregion

    # region #-- setup the coordinator for data updates --#
    _LOGGER.debug(log_formatter.format("setting up Mesh for the coordinator"))
    hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR_MESH] = Mesh(
        node=config_entry.options[CONF_NODE],
        password=config_entry.options[CONF_PASSWORD],
        request_timeout=config_entry.options.get(CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT),
        session=async_get_clientsession(hass=hass),
    )

    async def _async_get_mesh_data() -> Mesh:
        """Fetch the latest data from the Mesh

        Will signal relevant sensors that have a state that needs updating more frequently
        """

        _LOGGER.debug(log_formatter.format("entered"))

        mesh: Mesh = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR_MESH]
        device_registry: dr.DeviceRegistry = dr.async_get(hass=hass)

        # -- get the existing devices --#
        _LOGGER.debug(log_formatter.format("retrieving existing devices for comparison"))
        device: Device
        previous_devices: Set[str] = {device.unique_id for device in mesh.devices}

        # -- get the existing nodes --#
        _LOGGER.debug(log_formatter.format("retrieving existing nodes for comparison"))
        my_devices: List[DeviceEntry] = dr.async_entries_for_config_entry(
            registry=device_registry,
            config_entry_id=config_entry.entry_id
        )
        dr_device: dr.DeviceEntry
        previous_nodes: Set[str] = {
            next(iter(dr_device.identifiers))[1]  # serial number of node
            for dr_device in my_devices
            if all([
                dr_device.manufacturer != PYVELOP_AUTHOR,
                dr_device.name.lower() != "mesh",
            ])
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
                config_entry.options.get(CONF_API_REQUEST_TIMEOUT, DEF_API_REQUEST_TIMEOUT)
            )
            raise UpdateFailed(err)
        except Exception as err:
            _LOGGER.debug(log_formatter.format("error type: %s"), type(err))
            raise UpdateFailed(err)
        else:
            # region #-- check for new devices --#
            if not previous_devices:
                _LOGGER.debug(log_formatter.format("no previous devices - ignoring comparison"))
            else:
                _LOGGER.debug(log_formatter.format("comparing devices"))
                current_devices: Set[str] = {device.unique_id for device in mesh.devices}
                new_devices: Set[str] = current_devices.difference(previous_devices)
                if new_devices:
                    for device in mesh.devices:
                        if device.unique_id in new_devices:
                            # -- fire the event --#
                            payload = build_event_payload(
                                config_entry=config_entry,
                                device=device,
                                event=EVENT_NEW_DEVICE_ON_MESH,
                                hass=hass
                            )
                            _LOGGER.debug(log_formatter.format("%s: %s"), EVENT_NEW_DEVICE_ON_MESH, payload)
                            hass.bus.async_fire(event_type=EVENT_NEW_DEVICE_ON_MESH, event_data=payload)
                _LOGGER.debug(log_formatter.format("devices compared"))
            # endregion

            # region #-- check for new nodes --#
            if not previous_nodes:
                _LOGGER.debug(log_formatter.format("no previous nodes - ignoring comparison"))
            else:
                _LOGGER.debug(log_formatter.format("comparing nodes"))
                node: Node
                current_nodes: Set[str] = {node.serial for node in mesh.nodes}
                new_nodes: Set[str] = current_nodes.difference(previous_nodes)
                is_reloading = hass.data[DOMAIN].get(CONF_ENTRY_RELOAD, {}).get(config_entry.entry_id)
                if new_nodes and not is_reloading:
                    for node in mesh.nodes:
                        if node.serial in new_nodes:
                            _LOGGER.debug(log_formatter.format("new node found: %s"), node.serial)
                            if hass.state == CoreState.running:  # reload the config
                                if CONF_ENTRY_RELOAD not in hass.data[DOMAIN]:
                                    hass.data[DOMAIN][CONF_ENTRY_RELOAD] = {}
                                hass.data[DOMAIN][CONF_ENTRY_RELOAD][config_entry.entry_id] = True
                                await hass.config_entries.async_reload(config_entry.entry_id)
                                hass.data[DOMAIN].get(CONF_ENTRY_RELOAD, {}).pop(config_entry.entry_id, None)

                            # -- fire the event --#
                            payload = build_event_payload(
                                config_entry=config_entry,
                                device=node,
                                event=EVENT_NEW_DEVICE_ON_MESH,
                                hass=hass
                            )
                            _LOGGER.debug(log_formatter.format("%s: %s"), EVENT_NEW_NODE_ON_MESH, payload)
                            hass.bus.async_fire(event_type=EVENT_NEW_NODE_ON_MESH, event_data=payload)
                _LOGGER.debug(log_formatter.format("nodes compared"))
            # endregion

            # region #-- check for a primary node change --#
            primary_node: List[Node] = [
                node
                for node in mesh.nodes
                if node.type == "primary"
            ]
            if primary_node and primary_node[0].serial != config_entry.unique_id:
                _LOGGER.debug(log_formatter.format("assuming the primary node has changed"))
                if hass.state == CoreState.running:
                    if hass.config_entries.async_update_entry(entry=config_entry, unique_id=primary_node[0].serial):
                        payload: Dict[str, Any] = build_event_payload(
                            config_entry=config_entry,
                            device=primary_node[0],
                            event=EVENT_NEW_PARENT_NODE,
                            hass=hass,
                        )
                        hass.bus.async_fire(event_type=EVENT_NEW_PARENT_NODE, event_data=payload)
                else:
                    _LOGGER.debug(log_formatter.format("backing off updates until HASS is fully running"))
            # endregion

            hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR_MESH] = mesh

        _LOGGER.debug(log_formatter.format("exited"))
        return mesh

    _LOGGER.debug(log_formatter.format("setting up the coordinator"))
    coordinator = DataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        name=f"{DOMAIN} ({getattr(log_formatter, '_unique_id')})",
        update_interval=timedelta(seconds=config_entry.options[CONF_SCAN_INTERVAL]),
        update_method=_async_get_mesh_data
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR] = coordinator
    # endregion

    # region #-- setup the platforms --#
    setup_platforms: List[str] = list(filter(None, PLATFORMS))
    _LOGGER.debug(log_formatter.format("setting up platforms: %s"), setup_platforms)
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
    hass.data[DOMAIN][config_entry.entry_id][CONF_UNSUB_UPDATE_LISTENER] = config_entry.add_update_listener(
        _async_update_listener
    )
    # endregion

    async def device_tracker_update(_: datetime.datetime) -> None:
        """Manage the device tracker updates

        Uses the _ variable to ignore IDE checking for unused variables

        Gets the device list from the mesh before dispatching the message

        :param _: datetime object for when the event was fired
        :return: None
        """

        async_dispatcher_send(hass, SIGNAL_UPDATE_DEVICE_TRACKER)

    # region #-- set up the timer for checking device trackers --#
    if config_entry.options[CONF_DEVICE_TRACKERS]:  # only do setup if device trackers were selected
        _LOGGER.debug(log_formatter.format("setting up device trackers"))
        await device_tracker_update(datetime.datetime.now())  # update before setting the timer
        scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL_DEVICE_TRACKER, DEF_SCAN_INTERVAL_DEVICE_TRACKER)
        config_entry.async_on_unload(
            async_track_time_interval(hass, device_tracker_update, timedelta(seconds=scan_interval))
        )
    # endregion

    _LOGGER.debug(log_formatter.format("exited"))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Cleanup when unloading a config entry"""

    log_formatter = Logger(unique_id=config_entry.unique_id)
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
        services: LinksysVelopServiceHandler = hass.data[DOMAIN][config_entry.entry_id][CONF_SERVICES_HANDLER]
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


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry"""

    await hass.config_entries.async_reload(config_entry.entry_id)


# region #-- base entities --#
class LinksysVelopMeshEntity(CoordinatorEntity):
    """"""

    ENTITY_DOMAIN: str

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description,
    ) -> None:
        """"""

        super().__init__(coordinator=coordinator)
        self._config = config_entry
        self._mesh: Mesh = coordinator.data

        self.entity_description = description

        self._attr_name = f"{ENTITY_SLUG} Mesh: {self.entity_description.name}"
        self._attr_unique_id = f"{config_entry.entry_id}::" \
                               f"{self.ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    def _handle_coordinator_update(self) -> None:
        """Update the information when the coordinator updates"""

        self._mesh = self.coordinator.data
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""

        # noinspection HttpUrlsUsage
        ret = DeviceInfo(
            configuration_url=f"http://{self._mesh.connected_node}",
            identifiers={(DOMAIN, self._config.entry_id)},
            manufacturer=PYVELOP_AUTHOR,
            model=f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            name="Mesh",
            sw_version="",
        )
        return ret

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """"""

        if (
            hasattr(self.entity_description, "extra_attributes")
            and isinstance(self.entity_description.extra_attributes, Callable)
        ):
            return self.entity_description.extra_attributes(self._mesh)


class LinksysVelopNodeEntity(CoordinatorEntity):
    """"""

    ENTITY_DOMAIN: str

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        description,
        node: Node,
    ) -> None:
        """"""

        super().__init__(coordinator=coordinator)

        self.entity_description = description

        self._config = config_entry
        self._mesh: Mesh = coordinator.data
        self._node_id: str = node.unique_id
        self._node: Node = self._get_node()

        self._attr_name = f"{ENTITY_SLUG} {self._node.name}: {self.entity_description.name}"
        self._attr_unique_id = f"{self._node.unique_id}::" \
                               f"{self.ENTITY_DOMAIN.lower()}::" \
                               f"{slugify(self.entity_description.name)}"

    def _get_node(self) -> Optional[Node]:
        """Get the current node"""

        node = [n for n in self._mesh.nodes if n.unique_id == self._node_id]
        if node:
            return node[0]

        return None

    def _handle_coordinator_update(self) -> None:
        """Update the information when the coordinator updates"""

        self._mesh = self.coordinator.data
        self._node = self._get_node()
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

        return ret

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Additional attributes for the entity"""

        if (
            hasattr(self.entity_description, "extra_attributes")
            and isinstance(self.entity_description.extra_attributes, Callable)
        ):
            return self.entity_description.extra_attributes(self._node)
# endregion


# region #-- cleanup entities --#
def entity_cleanup(
    config_entry: ConfigEntry,
    entities: List[LinksysVelopMeshEntity | LinksysVelopNodeEntity],
    hass: HomeAssistant
):
    """"""

    log_formatter = Logger(unique_id=config_entry.unique_id, prefix=f"{entities[0].__class__.__name__} --> ")
    _LOGGER.debug(log_formatter.format("entered"))

    entity_registry: er.EntityRegistry = er.async_get(hass=hass)
    er_entries: List[er.RegistryEntry] = er.async_entries_for_config_entry(
        registry=entity_registry,
        config_entry_id=config_entry.entry_id
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
