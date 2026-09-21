"""Exercise setup retry and cleanup through Home Assistant's native lifecycle."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import CoreState
from homeassistant.util import dt as dt_util
from pyvelop.exceptions import (
    MeshConnectionError,
    MeshInvalidCredentials,
    MeshNodeNotPrimary,
    MeshTimeoutError,
)
from pyvelop.mesh import Mesh, MeshSnapshot
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

import custom_components.linksys_velop as integration
from custom_components.linksys_velop.const import CONF_EVENTS_OPTIONS, CONF_NODE, DOMAIN


def mesh_transport(error=None):
    """Simulate only mesh transport; leave config-entry and coordinator code real."""
    mesh = MagicMock(spec=Mesh)
    snapshot = MeshSnapshot({}, {}, (), {})
    mesh.latest_snapshot = None
    mesh.async_authenticate_and_refresh = AsyncMock(
        return_value=snapshot, side_effect=error
    )
    mesh.async_refresh = AsyncMock(return_value=snapshot)
    mesh.connected_node = "192.0.2.1"
    mesh.timeout = 30
    return mesh


@pytest.fixture
def setup_boundary(hass, enable_custom_integrations):
    """Exclude service registration and entity platforms from the retry boundary."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test mesh",
        version=2,
        options={
            CONF_NODE: "192.0.2.1",
            "password": "synthetic",
            CONF_EVENTS_OPTIONS: [],
        },
    )
    entry.add_to_hass(hass)
    hass.config.components.add(DOMAIN)
    hass.set_state(CoreState.running)
    with (
        patch.object(
            integration, "async_get_integration_version", AsyncMock(return_value="test")
        ),
        patch.object(integration, "LinksysVelopServiceHandler"),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", AsyncMock()
        ) as forward,
        patch.object(
            hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
        ),
        patch("homeassistant.config_entries.randint", return_value=0),
    ):
        yield entry, forward


async def advance_retry_clock(hass, seconds):
    """Dispatch Home Assistant's actual scheduled retry callbacks."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize("error_type", [MeshConnectionError, MeshTimeoutError])
async def test_transient_setup_failure_retries_and_recovers(
    hass, setup_boundary, caplog, error_type
):
    """A failed setup leaves no polling and later succeeds without manual reload."""
    entry, forward = setup_boundary
    failed = mesh_transport(error_type())
    recovered = mesh_transport()
    with patch.object(integration, "Mesh", side_effect=[failed, recovered]) as factory:
        try:
            await entry.async_setup_locked(hass)
            first = entry.runtime_data.coordinator
            assert entry.state is ConfigEntryState.SETUP_RETRY
            assert entry._async_cancel_retry_setup is not None
            assert first._shutdown_requested
            assert not first._listeners
            assert first._unsub_refresh is None
            assert not entry._on_unload
            failed.async_refresh.assert_not_awaited()
            forward.assert_not_awaited()
            if error_type is MeshConnectionError:
                assert not [record for record in caplog.records if record.levelno >= 40]

            await advance_retry_clock(hass, 4)
            assert factory.call_count == 1
            await advance_retry_clock(hass, 6)
            assert factory.call_count == 2
            assert entry.state is ConfigEntryState.LOADED
            current = entry.runtime_data.coordinator
            assert current is not first
            assert current.data.mesh is recovered.async_refresh.return_value
            assert not current._shutdown_requested
            assert entry._async_cancel_retry_setup is None
            forward.assert_awaited_once()
        finally:
            await hass.config_entries.async_unload(entry.entry_id)
        assert current._shutdown_requested
        assert not current._listeners


@pytest.mark.parametrize("error_type", [MeshInvalidCredentials, MeshNodeNotPrimary])
async def test_permanent_setup_failure_does_not_retry(hass, setup_boundary, error_type):
    """Keep rejected credentials and non-primary nodes outside setup retry."""
    entry, forward = setup_boundary
    mesh = mesh_transport(error_type())
    with (
        patch.object(integration, "Mesh", return_value=mesh) as factory,
        patch.object(entry, "async_start_reauth") as reauth,
    ):
        await entry.async_setup_locked(hass)
        assert entry.state is ConfigEntryState.SETUP_ERROR
        assert entry._async_cancel_retry_setup is None
        if error_type is MeshInvalidCredentials:
            reauth.assert_called_once()
            assert reauth.call_args.args[0] is hass
            assert entry.error_reason_translation_key == "failed_login"
        else:
            reauth.assert_not_called()
            assert entry.error_reason_translation_key == "node_not_primary"
        mesh.async_refresh.assert_not_awaited()
        forward.assert_not_awaited()
        await advance_retry_clock(hass, 100)
        assert factory.call_count == 1


async def test_unload_cancels_pending_connection_retry(hass, setup_boundary):
    """Unloading a failed entry cancels its scheduled retry."""
    entry, forward = setup_boundary
    with patch.object(
        integration, "Mesh", return_value=mesh_transport(MeshConnectionError())
    ) as factory:
        await entry.async_setup_locked(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert entry._async_cancel_retry_setup is None
        await advance_retry_clock(hass, 100)
        assert factory.call_count == 1
        forward.assert_not_awaited()
