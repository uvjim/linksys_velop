"""The Linksys Velop integration"""

# region #-- imports --#
from __future__ import annotations

import datetime
import logging
from datetime import timedelta
from typing import (
    Any,
    Dict,
    List,
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
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_AUTHOR as PYVELOP_AUTHOR
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_NAME as PYVELOP_NAME
# noinspection PyProtectedMember
from pyvelop.const import _PACKAGE_VERSION as PYVELOP_VERSION
from pyvelop.device import Device
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
    PLATFORMS,
    SIGNAL_UPDATE_DEVICE_TRACKER,
    SIGNAL_UPDATE_SPEEDTEST_STATUS,
)
from .logger import VelopLogger
from .service_handler import LinksysVelopServiceHandler

# endregion

_LOGGER = logging.getLogger(__name__)

EVENT_NEW_DEVICE_ON_MESH: str = f"{DOMAIN}_new_device_on_mesh"
EVENT_NEW_DEVICE_ON_MESH_PROPERTIES: List[str] = [
    "connected_adapters",
    "description",
    "manufacturer",
    "model",
    "name",
    "operating_system",
    "parent_name",
    "serial",
    "status",
]
EVENT_NEW_NODE_ON_MESH: str = f"{DOMAIN}_new_node_on_mesh"
EVENT_NEW_NODE_ON_MESH_PROPERTIES: List[str] = [
    "backhaul",
    "connected_adapters",
    "model",
    "name",
    "parent_name",
    "serial",
    "status",
]


# noinspection PyUnusedLocal
async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry
) -> bool:
    """"""

    log_formatter = VelopLogger(unique_id=config_entry.unique_id)

    if all([  # check for Mesh device
        device_entry.name == "Mesh",
        device_entry.manufacturer == PYVELOP_AUTHOR,
        device_entry.model == f"{PYVELOP_NAME} ({PYVELOP_VERSION})"
    ]):
        _LOGGER.error(log_formatter.message_format("Attempt to remove the Mesh device rejected"))
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Setup a config entry"""

    log_formatter = VelopLogger(unique_id=config_entry.unique_id)
    _LOGGER.debug(log_formatter.message_format("entered"))

    # region #-- prepare the memory storage --#
    _LOGGER.debug(log_formatter.message_format("preparing memory storage"))
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    # endregion

    # region #-- setup the coordinator for data updates --#
    _LOGGER.debug(log_formatter.message_format("setting up Mesh for the coordinator"))
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

        mesh: Mesh = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR_MESH]
        device_registry: dr.DeviceRegistry = dr.async_get(hass=hass)

        # -- get the existing devices --#
        device: Device
        previous_devices: Set[str] = {device.unique_id for device in mesh.devices}

        # -- get the existing nodes --#
        previous_nodes: Set[str] = {
            next(iter(dr_device.identifiers))[1]  # serial number of node
            for dr_id, dr_device in device_registry.devices.items()
            if all([
                config_entry.entry_id in dr_device.config_entries,
                dr_device.manufacturer != PYVELOP_AUTHOR,
                dr_device.name.lower() != "mesh",
            ])
        }

        try:
            # -- gather details from the API --#
            await mesh.async_gather_details()
            if mesh.speedtest_status:
                async_dispatcher_send(hass, SIGNAL_UPDATE_SPEEDTEST_STATUS)
        except Exception as err:
            raise UpdateFailed(err)
        else:
            # region #-- get the mesh device_id --#
            def _get_mesh() -> Optional[DeviceEntry]:

                dr_device: dr.DeviceEntry
                m = [
                    dr_device
                    for dr_id, dr_device in device_registry.devices.items()
                    if (
                            config_entry.entry_id in dr_device.config_entries
                            and dr_device.manufacturer == PYVELOP_AUTHOR
                            and dr_device.name.lower() == "mesh"
                    )
                ]
                if m:
                    return m[0]
            # endregion

            # region #-- check for new devices --#
            if previous_devices:
                current_devices: Set[str] = {device.unique_id for device in mesh.devices}
                new_devices: Set[str] = current_devices.difference(previous_devices)
                if new_devices:
                    for device in mesh.devices:
                        if device.unique_id in new_devices:
                            payload: Dict[str, Any] = {
                                prop: getattr(device, prop, None)
                                for prop in EVENT_NEW_DEVICE_ON_MESH_PROPERTIES
                            }
                            mesh_details: DeviceEntry = _get_mesh()
                            if mesh_details:
                                payload["mesh_device_id"] = mesh_details.id
                            _LOGGER.debug(log_formatter.message_format("%s: %s"), EVENT_NEW_DEVICE_ON_MESH, payload)
                            hass.bus.async_fire(event_type=EVENT_NEW_DEVICE_ON_MESH, event_data=payload)
            # endregion

            # region #-- check for new nodes --#
            if previous_nodes:
                node: Node
                current_nodes: Set[str] = {node.serial for node in mesh.nodes}
                new_nodes: Set[str] = current_nodes.difference(previous_nodes)
                is_reloading = hass.data[DOMAIN].get(CONF_ENTRY_RELOAD, {}).get(config_entry.entry_id)
                if new_nodes and not is_reloading:
                    for node in mesh.nodes:
                        if node.serial in new_nodes:
                            _LOGGER.debug(log_formatter.message_format("new node found: %s"), node.serial)
                            _LOGGER.debug(log_formatter.message_format("hass state: %s"), hass.state)
                            if hass.state == CoreState.running:  # reload the config
                                if CONF_ENTRY_RELOAD not in hass.data[DOMAIN]:
                                    hass.data[DOMAIN][CONF_ENTRY_RELOAD] = {}
                                hass.data[DOMAIN][CONF_ENTRY_RELOAD][config_entry.entry_id] = True
                                await hass.config_entries.async_reload(config_entry.entry_id)
                                hass.data[DOMAIN].get(CONF_ENTRY_RELOAD, {}).pop(config_entry.entry_id, None)

                            # -- fire the event --#
                            payload: Dict[str, Any] = {
                                prop: getattr(node, prop, None)
                                for prop in EVENT_NEW_NODE_ON_MESH_PROPERTIES
                            }
                            mesh_details: DeviceEntry = _get_mesh()
                            if mesh_details:
                                payload["mesh_id"] = mesh_details.id
                            _LOGGER.debug(log_formatter.message_format("%s: %s"), EVENT_NEW_NODE_ON_MESH, payload)
                            hass.bus.async_fire(event_type=EVENT_NEW_NODE_ON_MESH, event_data=payload)
            # endregion
        return mesh

    _LOGGER.debug(log_formatter.message_format("setting up the coordinator"))
    coordinator = DataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        name=DOMAIN,
        update_interval=timedelta(seconds=config_entry.options[CONF_SCAN_INTERVAL]),
        update_method=_async_get_mesh_data
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR] = coordinator
    # endregion

    # region #-- setup the platforms --#
    setup_platforms: List[str] = list(filter(None, PLATFORMS))
    _LOGGER.debug(log_formatter.message_format("setting up platforms: %s"), setup_platforms)
    hass.config_entries.async_setup_platforms(config_entry, setup_platforms)
    # endregion

    # region #-- Service Definition --#
    _LOGGER.debug(log_formatter.message_format("registering services"))
    services = LinksysVelopServiceHandler(hass=hass)
    services.register_services()
    hass.data[DOMAIN][config_entry.entry_id][CONF_SERVICES_HANDLER] = services
    # endregion

    # region #-- listen for config changes --#
    _LOGGER.debug(log_formatter.message_format("listening for config changes"))
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
        _LOGGER.debug(log_formatter.message_format("setting up device trackers"))
        await device_tracker_update(datetime.datetime.now())  # update before setting the timer
        scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL_DEVICE_TRACKER, DEF_SCAN_INTERVAL_DEVICE_TRACKER)
        config_entry.async_on_unload(
            async_track_time_interval(hass, device_tracker_update, timedelta(seconds=scan_interval))
        )
    # endregion

    _LOGGER.debug(log_formatter.message_format("exited"))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Cleanup when unloading a config entry"""

    log_formatter = VelopLogger(unique_id=config_entry.unique_id)
    _LOGGER.debug(log_formatter.message_format("entered"))

    # region #-- unsubscribe from listening for updates --#
    _LOGGER.debug(log_formatter.message_format("stop listening for updates"))
    hass.data[DOMAIN][config_entry.entry_id][CONF_UNSUB_UPDATE_LISTENER]()
    # endregion

    # region #-- remove services but only if there are no other instances --#
    all_config_entries = hass.config_entries.async_entries(domain=DOMAIN)
    _LOGGER.debug(log_formatter.message_format("%i instances"), len(all_config_entries))
    if len(all_config_entries) == 1:
        _LOGGER.debug(log_formatter.message_format("unregistering services"))
        services: LinksysVelopServiceHandler = hass.data[DOMAIN][config_entry.entry_id][CONF_SERVICES_HANDLER]
        services.unregister_services()
    # endregion

    # region #-- clean up the platforms --#
    _LOGGER.debug(log_formatter.message_format("cleaning up platforms"))
    ret = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if ret:
        _LOGGER.debug(log_formatter.message_format("removing data from memory"))
        hass.data[DOMAIN].pop(config_entry.entry_id)
        ret = True
    else:
        ret = False
    # endregion

    _LOGGER.debug(log_formatter.message_format("exited"))
    return ret


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Reload the config entry"""

    return await hass.config_entries.async_reload(config_entry.entry_id)


# region #-- base entities --#
class LinksysVelopMeshEntity(CoordinatorEntity):
    """"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry
    ) -> None:
        """"""

        super().__init__(coordinator=coordinator)
        self._config = config_entry
        self._mesh: Mesh = coordinator.data

    def _handle_coordinator_update(self) -> None:
        """Update the information when the coordinator updates"""

        self._mesh = self.coordinator.data
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""

        # noinspection HttpUrlsUsage
        ret = DeviceInfo(**{
            "configuration_url": f"http://{self._mesh.connected_node}",
            "identifiers": {(DOMAIN, self._config.entry_id)},
            "manufacturer": PYVELOP_AUTHOR,
            "model": f"{PYVELOP_NAME} ({PYVELOP_VERSION})",
            "name": "Mesh",
            "sw_version": "",
        })
        return ret


class LinksysVelopNodeEntity(CoordinatorEntity):
    """"""

    _node_id: str

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry
    ) -> None:
        """"""

        super().__init__(coordinator=coordinator)
        self._config = config_entry
        self._mesh: Mesh = coordinator.data
        self._node: Node = self._get_node()

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

        ret = DeviceInfo(**{
            "hw_version": self._node.hardware_version,
            "identifiers": {(DOMAIN, self._node.serial)},
            "model": self._node.model,
            "name": self._node.name,
            "manufacturer": self._node.manufacturer,
            "sw_version": self._node.firmware.get("version", ""),
        })

        return ret
# endregion


# region #-- cleanup entities --#
def entity_cleanup(
    config_entry: ConfigEntry,
    entities: List[LinksysVelopMeshEntity | LinksysVelopNodeEntity],
    hass: HomeAssistant
):
    """"""

    log_formatter = VelopLogger(unique_id=config_entry.unique_id, prefix=f"{entities[0].__class__.__name__} --> ")
    _LOGGER.debug(log_formatter.message_format("entered"))

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
        _LOGGER.debug(log_formatter.message_format("removing %s"), entity.entity_id)
        entity_registry.async_remove(entity_id=entity.entity_id)

    _LOGGER.debug(log_formatter.message_format("exited"))
# endregion
