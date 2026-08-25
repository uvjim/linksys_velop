"""Sensor entities for Linksys Velop."""

# region #-- imports --#
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast, override

from homeassistant.components.binary_sensor import DOMAIN as ENTITY_DOMAIN
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyvelop.action_registry import Actions
from pyvelop.mesh import Mesh
from pyvelop.mesh_attribute import MeshAttribute
from pyvelop.mesh_entity import AdapterInfo, DeviceEntity, NodeEntity

from .const import CONF_UI_DEVICES, IntensiveTask
from .coordinator import (
    CoordinatorTimers,
    CoordinatorTypes,
    LinksysVelopConfigEntry,
    LinksysVelopDataUpdateCoordinatorMultiUse,
    LinksysVelopDataUpdateCoordinatorSpeedtest,
    SpeedtestStatus,
)
from .entities import (
    EntityType,
    LinksysVelopEntityContext,
    LinksysVelopEntityDescription,
    LinksysVelopMultiUseEntity,
    LinksysVelopSpeedtestEntity,
)
from .helpers import remove_velop_entity_from_registry
from .logger import Logger

# endregion

_LOGGER: Logger = Logger(logging.getLogger(__name__))


@dataclass(frozen=True, kw_only=True)
class LinksysVelopBinarySensorEntityDescription(
    LinksysVelopEntityDescription, BinarySensorEntityDescription
):
    """Describes Velop binary sensor entity."""

    esa_fn: Callable[..., dict[str, Any] | None] | None = None
    value_fn: Callable[..., bool | None] | None = None


def get_device_adapter_info(device: DeviceEntity, key: str) -> Any:
    """Retrieve the give details about a device adapter."""

    ret: Any = None
    adi: AdapterInfo | None = next(iter(device.adapter_info), None)
    if adi is not None:
        ret = getattr(adi, key, None)

    return ret


def status_extra_attributes(n: NodeEntity) -> dict[str, Any] | None:
    """Return the extra attributes for the Status binary sensor."""

    ret: dict[str, Any] | None = None

    primary_adapter: AdapterInfo | None
    if (
        primary_adapter := next((adi for adi in n.adapter_info if adi.primary), None)
    ) is not None:
        ret = primary_adapter.to_dict()
        del ret["primary"]

    return ret


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinksysVelopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialise a binary sensor."""

    known_nodes: set[str] = set()

    def _create_entities() -> None:
        """Create the mesh and device entities."""

        entities_to_add: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = (
            _init_device_entities() + _init_mesh_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    def _init_device_entities() -> (
        tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]
    ):
        """Describe the entities that target devices."""
        ret: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopBinarySensorCoordinatorEntity] = []

        for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
            context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                unique_id=ui_device
            )
            mesh_entities: list[LinksysVelopBinarySensorEntityDescription] = []

            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    key="status",
                    name="Status",
                    target_type=EntityType.DEVICE,
                    translation_key="status",
                )
            )

            if (
                Actions.GET_GUEST_NETWORK_INFO.key
                in config_entry.runtime_data.mesh.capabilities
            ):
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="Guest Network",
                        target_type=EntityType.DEVICE,
                        translation_key="guest_network",
                        value_fn=lambda d: (
                            get_device_adapter_info(d, "guest_network")
                            if d is not None
                            else None
                        ),
                    )
                )

            if (
                Actions.GET_LAN_SETTINGS.key
                in config_entry.runtime_data.mesh.capabilities
            ):
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        key="",
                        name="Reserved IP",
                        target_type=EntityType.DEVICE,
                        translation_key="reserved_ip",
                        value_fn=lambda d: (
                            get_device_adapter_info(d, "reservation")
                            if d is not None
                            else None
                        ),
                    )
                )

            if (
                Actions.GET_PARENTAL_CONTROL_INFO.key
                in config_entry.runtime_data.mesh.capabilities
            ):
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        esa_fn=lambda d: (
                            d.parental_control_schedule.get("blocked_internet_access")
                            if d is not None
                            else None
                        ),
                        key="",
                        name="Blocked Times",
                        target_type=EntityType.DEVICE,
                        translation_key="blocked_times",
                        value_fn=lambda d: (
                            (
                                d.parental_control_schedule is not None
                                and d.parental_control_schedule.get(
                                    "blocked_internet_access"
                                )
                                is not None
                                and any(
                                    d.parental_control_schedule.get(
                                        "blocked_internet_access"
                                    ).values()
                                )
                            )
                            if d is not None
                            else None
                        ),
                    )
                )

            ret_temp.extend(
                [
                    LinksysVelopBinarySensorMultiUseEntity(
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

    def _init_mesh_entities() -> tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]:
        """Describe the entities that target the mesh."""
        ret: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = ()
        context: LinksysVelopEntityContext = LinksysVelopEntityContext(
            unique_id=config_entry.entry_id
        )
        mesh_entities: list[LinksysVelopBinarySensorEntityDescription] = []
        speedtest_entities: list[LinksysVelopBinarySensorEntityDescription] = []

        if Actions.GET_ALG_SETTINGS.key in config_entry.runtime_data.mesh.capabilities:
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="sip_enabled",
                    name="SIP",
                    target_type=EntityType.MESH,
                    translation_key="sip",
                ),
            )

        if (
            Actions.GET_CHANNEL_SCAN_STATUS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Channel Scanning",
                    target_type=EntityType.MESH,
                    translation_key="channel_scanning",
                    value_fn=lambda _: IntensiveTask.CHANNEL_SCAN
                    in config_entry.runtime_data.intensive_running_tasks,
                )
            )

        if (
            Actions.GET_EXPRESS_FORWARDING.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="express_forwarding_enabled",
                    name="Express Forwarding",
                    target_type=EntityType.MESH,
                    translation_key="express_forwarding",
                )
            )

        if (
            Actions.GET_HOMEKIT_SETTINGS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="homekit_paired",
                    name="HomeKit Integration Paired",
                    target_type=EntityType.MESH,
                    translation_key="homekit_paired",
                )
            )

        if Actions.GET_LAN_SETTINGS.key in config_entry.runtime_data.mesh.capabilities:
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="dhcp_enabled",
                    name="DHCP Server",
                    target_type=EntityType.MESH,
                    translation_key="dhcp_server",
                )
            )

        if (
            Actions.GET_MAC_FILTERING_SETTINGS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    esa_fn=lambda m: (
                        {
                            "mode": str(cast(Mesh, m).mac_filtering_mode),
                            "addresses": cast(Mesh, m).mac_filtering_addresses.value,
                        }
                        if m is not None
                        else None
                    ),
                    key="mac_filtering_enabled",
                    name="MAC Filtering",
                    translation_key="mac_filtering",
                    target_type=EntityType.MESH,
                )
            )

        if Actions.GET_MLO_SETTINGS.key in config_entry.runtime_data.mesh.capabilities:
            if config_entry.runtime_data.mesh.mlo_state is not None:
                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="mlo_state",
                        name="Muti-Link Operation (MLO)",
                        translation_key="multi_link_operation",
                        target_type=EntityType.MESH,
                    )
                )

        if (
            Actions.GET_SPEEDTEST_STATUS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            speedtest_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.RUNNING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    key="",
                    name="Speedtest Status",
                    target_type=EntityType.MESH,
                    translation_key="speedtest_status",
                    value_fn=lambda r: (
                        r.friendly_status
                        not in (SpeedtestStatus.NOT_RUNNING, SpeedtestStatus.UNKNOWN)
                        if r is not None
                        else None
                    ),
                )
            )

        if (
            Actions.GET_TOPOLOGY_OPTIMISATION_SETTINGS.key
            in config_entry.runtime_data.mesh.capabilities
        ):
            mesh_entities.extend(
                [
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="client_steering_enabled",
                        name="Client Steering",
                        target_type=EntityType.MESH,
                        translation_key="client_steering",
                    ),
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="node_steering_enabled",
                        name="Node Steering",
                        target_type=EntityType.MESH,
                        translation_key="node_steering",
                    ),
                ],
            )

        if Actions.GET_UPNP_SETTINGS.key in config_entry.runtime_data.mesh.capabilities:
            mesh_entities.extend(
                [
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="upnp_allow_change_settings",
                        name="UPnP Allow Users to Configure",
                        target_type=EntityType.MESH,
                        translation_key="upnp_allow_change_settings",
                    ),
                    LinksysVelopBinarySensorEntityDescription(
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=False,
                        key="upnp_allow_disable_internet",
                        name="UPnP Allow Users to Disable Internet",
                        target_type=EntityType.MESH,
                        translation_key="upnp_allow_disable_internet",
                    ),
                ]
            )

        if Actions.GET_WAN_INFO.key in config_entry.runtime_data.mesh.capabilities:
            mesh_entities.append(
                LinksysVelopBinarySensorEntityDescription(
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    esa_fn=lambda m: (
                        {
                            "ip": cast(Mesh, m).wan_ip.value,
                            "dns": cast(Mesh, m).wan_dns.value or None,
                            "mac": cast(Mesh, m).wan_mac.value,
                        }
                        if m is not None
                        else None
                    ),
                    key="wan_status",
                    name="WAN Status",
                    target_type=EntityType.MESH,
                    translation_key="wan_status",
                )
            )

        ret = (
            *[
                LinksysVelopBinarySensorMultiUseEntity(
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
            ],
            *[
                LinksysVelopBinarySensorSpeedtestEntity(
                    entity_context=context,
                    coordinator=cast(
                        LinksysVelopDataUpdateCoordinatorSpeedtest,
                        config_entry.runtime_data.coordinators.get(
                            CoordinatorTypes.SPEEDTEST
                        ),
                    ),
                    description=desc,
                )
                for desc in speedtest_entities
            ],
        )

        return ret

    def _init_node_entities() -> tuple[LinksysVelopBinarySensorCoordinatorEntity, ...]:
        """Describe the entities that target nodes."""
        ret: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = ()
        ret_temp: list[LinksysVelopBinarySensorCoordinatorEntity] = []

        current_nodes: set[str] = {
            str(cast(NodeEntity, n).unique_id)
            for n in config_entry.runtime_data.mesh.nodes
            if cast(NodeEntity, n).unique_id.value is not None
        }
        new_nodes: set[str] = current_nodes - known_nodes

        if new_nodes:
            known_nodes.update(new_nodes)
            for node in new_nodes:
                context: LinksysVelopEntityContext = LinksysVelopEntityContext(
                    unique_id=node
                )
                mesh_entities: list[LinksysVelopBinarySensorEntityDescription] = []

                mesh_entities.append(
                    LinksysVelopBinarySensorEntityDescription(
                        device_class=BinarySensorDeviceClass.CONNECTIVITY,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        esa_fn=status_extra_attributes,
                        key="status",
                        name="Status",
                        target_type=EntityType.NODE,
                        translation_key="status",
                    )
                )

                ret_temp.extend(
                    [
                        LinksysVelopBinarySensorMultiUseEntity(
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

    def _remove_stale_entities() -> None:
        """Remove entities is they are no longer required."""

        entities_to_remove: set[str] = {
            f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp",  # 2024.11.1b4 remove as we now have a switch
        }

        if (
            Actions.GET_ALG_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(f"{config_entry.entry_id}::{ENTITY_DOMAIN}::sip")

        if (
            Actions.GET_CHANNEL_SCAN_STATUS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::channel_scanning"
            )

        if (
            Actions.GET_EXPRESS_FORWARDING.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::express_forwarding"
            )

        if (
            Actions.GET_GUEST_NETWORK_INFO.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::guest_network")

        if (
            Actions.GET_HOMEKIT_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::homekit_integration_paired"
            )

        if (
            Actions.GET_LAN_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::dhcp_server"
            )
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::reserved_ip")

        if (
            Actions.GET_PARENTAL_CONTROL_INFO.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            for ui_device in config_entry.options.get(CONF_UI_DEVICES, []):
                entities_to_remove.add(f"{ui_device}::{ENTITY_DOMAIN}::blocked_times")

        if (
            Actions.GET_MAC_FILTERING_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::mac_filtering"
            )

        if (
            Actions.GET_MLO_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
            or config_entry.runtime_data.mesh.mlo_state is None
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::mlo_state"
            )

        if (
            Actions.GET_SPEEDTEST_STATUS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::speedtest_status"
            )

        if (
            Actions.GET_TOPOLOGY_OPTIMISATION_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.update(
                {
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::client_steering",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::node_steering",
                }
            )

        if (
            Actions.GET_UPNP_SETTINGS.key
            not in config_entry.runtime_data.mesh.capabilities
        ):
            entities_to_remove.update(
                {
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp_allow_users_to_configure",
                    f"{config_entry.entry_id}::{ENTITY_DOMAIN}::upnp_allow_users_to_disable_internet",
                }
            )

        if Actions.GET_WAN_INFO.key not in config_entry.runtime_data.mesh.capabilities:
            entities_to_remove.add(
                f"{config_entry.entry_id}::{ENTITY_DOMAIN}::wan_status"
            )

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

        entities_to_add: tuple[LinksysVelopBinarySensorCoordinatorEntity, ...] = (
            _init_node_entities()
        )

        if len(entities_to_add) > 0:
            async_add_entities(entities_to_add)

    _remove_stale_entities()
    _create_entities()
    create_node_entities()

    config_entry.async_on_unload(
        cast(
            LinksysVelopDataUpdateCoordinatorMultiUse,
            config_entry.runtime_data.coordinators.get(CoordinatorTypes.MESH),
        ).add_listener_for_timer_type(CoordinatorTimers.MESH, create_node_entities)
    )


class LinksysVelopBinarySensorEntity(BinarySensorEntity):
    """Base class representing a binary sensor entity."""

    entity_description: LinksysVelopBinarySensorEntityDescription
    _entity_domain: str = ENTITY_DOMAIN


class LinksysVelopBinarySensorMultiUseEntity(
    LinksysVelopBinarySensorEntity, LinksysVelopMultiUseEntity
):
    """Linksys Velop binary sensor that uses the multi use DataUpdateCoordinator."""

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:

        ret: dict[str, Any] | None = None

        if self.entity_description.esa_fn is not None:
            ret = self.entity_description.esa_fn(self._get_target())

        return ret

    @property
    @override
    def is_on(self) -> bool | None:

        ret: bool | None = None

        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self._get_target())
        elif self.entity_description.key:
            ret = getattr(
                self._get_target(),
                self.entity_description.key,
                None,
            )
            if isinstance(ret, MeshAttribute):
                ret = ret.value

        return ret


class LinksysVelopBinarySensorSpeedtestEntity(
    LinksysVelopBinarySensorEntity, LinksysVelopSpeedtestEntity
):
    """Linksys Velop binary sensor that uses the Speedtest DataUpdateCoordinator."""

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:

        ret: dict[str, Any] | None = None

        if self.entity_description.esa_fn is not None:
            ret = self.entity_description.esa_fn(self.coordinator.data)

        return ret

    @property
    @override
    def is_on(self) -> bool | None:

        ret: bool | None = None
        if self.entity_description.value_fn is not None:
            ret = self.entity_description.value_fn(self.coordinator.data)
        elif self.entity_description.key:
            ret = getattr(self.coordinator.data, self.entity_description.key, None)

        return ret


type LinksysVelopBinarySensorCoordinatorEntity = LinksysVelopBinarySensorMultiUseEntity | LinksysVelopBinarySensorSpeedtestEntity
