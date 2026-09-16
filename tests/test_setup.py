"""Offline checks using HA's config-entry retry scheduler."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState
from homeassistant.util import dt as dt_util
from pyvelop.exceptions import MeshConnectionError
from pyvelop.mesh import Mesh
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

import custom_components.linksys_velop as integration
from custom_components.linksys_velop.const import CONF_EVENTS_OPTIONS, CONF_NODE, DOMAIN
from custom_components.linksys_velop.coordinator import CoordinatorTypes


def transport(error_stage=None):
    """Return only a mocked mesh transport, with real HA/integration lifecycle."""
    mesh = MagicMock(spec=Mesh)
    mesh.async_test_credentials = AsyncMock(return_value=True)
    mesh.async_initialise = AsyncMock()
    mesh.async_gather_details = AsyncMock()
    mesh.nodes = ()
    mesh.devices = ()
    mesh.capabilities = set()
    mesh.connected_node = "192.0.2.1"
    mesh.timeout = 30
    if error_stage:
        getattr(mesh, error_stage).side_effect = MeshConnectionError()
    return mesh


@pytest.fixture
def setup_boundary(hass, enable_custom_integrations):
    """Keep platform/service work outside the setup-retry boundary."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Offline test mesh",
        version=2,
        options={
            CONF_NODE: "192.0.2.1",
            "password": "synthetic",
            CONF_EVENTS_OPTIONS: [],
        },
    )
    entry.add_to_hass(hass)
    hass.config.components.add(DOMAIN)
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


async def advance(hass, seconds):
    """Run HA's scheduled callbacks after controlled clock advancement."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_real_retry_backoff_cleanup_and_fresh_runtime(hass, setup_boundary):
    """Two failed attempts are disposed, followed by one successful setup."""
    entry, forward = setup_boundary
    hass.set_state(CoreState.running)
    meshes = [
        transport("async_test_credentials"),
        transport("async_initialise"),
        transport(),
    ]
    with patch.object(integration, "Mesh", side_effect=meshes) as factory:
        await entry.async_setup_locked(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        first = entry.runtime_data
        assert first.mesh is meshes[0]
        assert not first.coordinators
        assert not entry._on_unload
        forward.assert_not_awaited()

        await advance(hass, 4)
        assert factory.call_count == 1
        await advance(hass, 6)
        assert factory.call_count == 2
        assert entry.state is ConfigEntryState.SETUP_RETRY
        second = entry.runtime_data
        assert second is not first
        assert second.mesh is meshes[1]
        assert not second.coordinators
        assert not entry._on_unload
        forward.assert_not_awaited()

        await advance(hass, 9)
        assert factory.call_count == 2
        await advance(hass, 17)
        assert factory.call_count == 3
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data is not second
        current = entry.runtime_data.coordinators[CoordinatorTypes.MESH]
        assert not current._shutdown_requested
        assert current.data["mesh"] is meshes[2]
        assert entry._async_cancel_retry_setup is None
        forward.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert current._shutdown_requested
        assert not current._listeners


async def test_startup_retry_waits_for_started_and_unload_cancels(hass, setup_boundary):
    """Startup retries use the HA started event; later unload cancels backoff."""
    entry, forward = setup_boundary
    hass.set_state(CoreState.starting)
    with patch.object(
        integration, "Mesh", side_effect=lambda **kwargs: transport("async_initialise")
    ) as factory:
        await entry.async_setup_locked(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        await advance(hass, 90)
        assert factory.call_count == 1
        hass.set_state(CoreState.running)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert factory.call_count == 2
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert entry._async_cancel_retry_setup is None
        await advance(hass, 100)
        assert factory.call_count == 2
        forward.assert_not_awaited()


async def test_rejected_auth_is_not_scheduled_for_retry(hass, setup_boundary):
    """A negative credential check retains the separate reauthentication path."""
    entry, forward = setup_boundary
    hass.set_state(CoreState.running)
    mesh = transport()
    mesh.async_test_credentials.return_value = False
    with (
        patch.object(integration, "Mesh", return_value=mesh) as factory,
        patch.object(entry, "async_start_reauth") as reauth,
    ):
        await entry.async_setup_locked(hass)
        assert entry.state is ConfigEntryState.SETUP_ERROR
        assert entry._async_cancel_retry_setup is None
        reauth.assert_called_once()
        assert reauth.call_args.args[0] is hass
        assert entry.error_reason_translation_key == "failed_login"
        assert not entry.runtime_data.coordinators
        assert not entry._on_unload
        mesh.async_initialise.assert_not_awaited()
        await advance(hass, 100)
        assert factory.call_count == 1
        forward.assert_not_awaited()


@pytest.mark.parametrize("stage", ["async_test_credentials", "async_initialise"])
@pytest.mark.parametrize("failure", ["connection", "timeout"])
async def test_setup_failure_retains_translated_reason(
    hass, setup_boundary, caplog, stage, failure
):
    """Native entry setup retains translated reasons without unexpected errors."""
    from pyvelop.exceptions import MeshTimeoutError

    entry, forward = setup_boundary
    hass.set_state(CoreState.running)
    mesh = transport()
    error = MeshConnectionError() if failure == "connection" else MeshTimeoutError()
    getattr(mesh, stage).side_effect = error
    with patch.object(integration, "Mesh", return_value=mesh):
        await entry.async_setup_locked(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert entry.error_reason_translation_key == (
            "init_connection_error" if failure == "connection" else "init_mesh_timeout"
        )
        assert entry.error_reason_translation_placeholders == (
            {"exc_msg": str(error), "primary_ip": "192.0.2.1"}
            if failure == "connection"
            else {"current_timeout": "30"}
        )
        assert not [record for record in caplog.records if record.levelno >= 40]
        assert not entry._on_unload
        assert not entry.runtime_data.coordinators
        mesh.async_gather_details.assert_not_awaited()
        forward.assert_not_awaited()
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("stage", ["async_test_credentials", "async_initialise"])
async def test_persistent_connection_failure_uses_quiet_native_retries(
    hass, setup_boundary, caplog, stage
):
    """Repeated outages keep translated diagnostics and dispose each attempt."""
    entry, forward = setup_boundary
    hass.set_state(CoreState.running)
    meshes = [transport(stage) for _ in range(4)]
    with patch.object(integration, "Mesh", side_effect=meshes) as factory:
        await entry.async_setup_locked(hass)
        for attempt, advance_seconds in enumerate((6, 17, 38, None), 1):
            assert factory.call_count == attempt
            assert entry.state is ConfigEntryState.SETUP_RETRY
            assert entry.error_reason_translation_key == "init_connection_error"
            assert not entry._on_unload
            assert not entry.runtime_data.coordinators
            if advance_seconds is not None:
                await advance(hass, advance_seconds)
        assert not [record for record in caplog.records if record.levelno >= 40]
        forward.assert_not_awaited()
        await hass.config_entries.async_unload(entry.entry_id)
        await advance(hass, 200)
        assert factory.call_count == 4


@pytest.mark.parametrize("failure", ["late_auth", "unexpected"])
async def test_other_initialization_failures_keep_existing_retry(
    hass, setup_boundary, failure
):
    """Moving initialization preserves the prior generic retry boundary."""
    from pyvelop.exceptions import MeshInvalidCredentials

    entry, forward = setup_boundary
    hass.set_state(CoreState.running)
    mesh = transport()
    mesh.async_initialise.side_effect = (
        MeshInvalidCredentials()
        if failure == "late_auth"
        else RuntimeError("synthetic")
    )
    with patch.object(integration, "Mesh", return_value=mesh):
        await entry.async_setup_locked(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert not entry._on_unload
        assert not entry.runtime_data.coordinators
        forward.assert_not_awaited()
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("stage", ["async_test_credentials", "async_initialise"])
async def test_setup_cancellation_acquires_no_coordinator_callbacks(
    hass, setup_boundary, stage
):
    """Cancellation still reaches Core without leaving timers or callbacks."""

    entry, forward = setup_boundary
    hass.set_state(CoreState.running)
    mesh = transport()
    entered = asyncio.Event()

    async def blocked():
        entered.set()
        await asyncio.Event().wait()

    getattr(mesh, stage).side_effect = blocked
    with patch.object(integration, "Mesh", return_value=mesh):
        task = asyncio.create_task(entry.async_setup_locked(hass))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not entry._on_unload
        assert entry._async_cancel_retry_setup is None
        assert not entry.runtime_data.coordinators
        forward.assert_not_awaited()


@pytest.mark.parametrize("stage", ["async_test_credentials", "async_initialise"])
async def test_scheduled_refresh_waits_for_initialization(hass, setup_boundary, stage):
    """Slow initialization cannot race a constructor-scheduled mesh refresh."""
    entry, forward = setup_boundary
    hass.set_state(CoreState.running)
    entered, release = asyncio.Event(), asyncio.Event()
    mesh = transport()

    async def blocked():
        entered.set()
        await release.wait()
        return True

    async def forward_after_refresh(*args):
        mesh.async_test_credentials.assert_awaited_once()
        mesh.async_initialise.assert_awaited_once()
        mesh.async_gather_details.assert_awaited_once()
        assert (
            entry.runtime_data.coordinators[CoordinatorTypes.MESH].data["mesh"] is mesh
        )

    getattr(mesh, stage).side_effect = blocked
    forward.side_effect = forward_after_refresh
    with patch.object(integration, "Mesh", return_value=mesh):
        setup_task = asyncio.create_task(entry.async_setup_locked(hass))
        await entered.wait()
        coordinator = entry.runtime_data.coordinators.get(CoordinatorTypes.MESH)
        interval = None
        # Exercise the native timer path if construction regresses ahead of init.
        if coordinator is not None:
            assert coordinator._listeners
            assert coordinator._unsub_refresh is not None
            coordinator._unsub_refresh()
            interval = asyncio.create_task(coordinator._handle_refresh_interval())
        try:
            for _ in range(20):
                await asyncio.sleep(0)
            assert not setup_task.done()
            mesh.async_gather_details.assert_not_awaited()
            assert not entry.runtime_data.coordinators
            assert not entry._on_unload
            forward.assert_not_awaited()
        finally:
            release.set()
            await asyncio.gather(setup_task, *([interval] if interval else []))
            await hass.config_entries.async_unload(entry.entry_id)
        forward.assert_awaited_once()
