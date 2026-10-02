#!/usr/bin/env python3
"""
Main driver for Synology System integration

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

import ucapi
from ucapi import Events, DeviceStates

if __name__ == "__main__" and __package__ is None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from uc_intg_synology_system.client import SynologySystemClient
from uc_intg_synology_system.config import SynologyConfig
from uc_intg_synology_system.setup import setup_handler, get_setup_client, clear_setup_client
from uc_intg_synology_system.media_player import SynologySystemDashboard
from uc_intg_synology_system.remote import SynologySystemRemote
from uc_intg_synology_system.camera_media_player import SynologyCameraMonitor
from uc_intg_synology_system.sensor import SynologySensors

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

_LOG = logging.getLogger(__name__)

# Global variables for reboot survival
api: ucapi.IntegrationAPI = None
_config: SynologyConfig = None
_client: SynologySystemClient = None
_media_player: SynologySystemDashboard = None
_camera_monitor: SynologyCameraMonitor = None
_remote: SynologySystemRemote = None
_monitoring_task: Optional[asyncio.Task] = None
_sensors: Optional[SynologySensors] = None

# The monitoring loop runs every 30 s; storage is refreshed every 10th cycle.
_STORAGE_EVERY = 10


# Reconnect backoff (seconds). DSM's Auto Block bans an IP after repeated failed
# logins, so reconnect attempts back off instead of retrying every cycle.
_RECONNECT_MIN = 60
_RECONNECT_MAX = 900


def _create_entities() -> None:
    """Create the entities for the current client, or rebind existing ones to it.

    Called at startup (from the saved configuration, so entities survive a
    driver or Remote restart) and after setup completes.
    """
    global _media_player, _camera_monitor, _remote, _sensors

    if _sensors is None:
        _sensors = SynologySensors(api)
        for sensor in _sensors.entities:
            api.available_entities.add(sensor)

    if _media_player is None:
        _media_player = SynologySystemDashboard(api, _client, _config)
        api.available_entities.add(_media_player.entity)
    else:
        _media_player._client = _client  # pylint: disable=protected-access

    if _remote is None:
        _remote = SynologySystemRemote(api, _client, _config)
        api.available_entities.add(_remote.entity)
    else:
        _remote._client = _client  # pylint: disable=protected-access

    packages = _client.available_packages or _config.available_packages
    if "SurveillanceStation" in packages:
        if _camera_monitor is None:
            _LOG.info("Surveillance Station detected - creating camera monitor entity")
            _camera_monitor = SynologyCameraMonitor(api, _client, _config)
            api.available_entities.add(_camera_monitor.entity)
        else:
            _camera_monitor._client = _client  # pylint: disable=protected-access

    _LOG.info("Synology entities are created and available.")


def _client_from_config() -> SynologySystemClient:
    """Build a (not yet connected) client from the saved configuration."""
    connection_params = _config.get_connection_params()
    client = SynologySystemClient(
        host=connection_params["host"],
        port=connection_params["port"],
        username=connection_params["username"],
        password=connection_params["password"],
        secure=connection_params["secure"],
        dsm_version=connection_params["dsm_version"],
        otp_code=None,  # No OTP for reconnection
        temperature_unit=_config.temperature_unit,
    )
    client._initial_connection_made = True  # pylint: disable=protected-access
    return client


async def setup_handler_wrapper(msg: ucapi.SetupDriver) -> ucapi.SetupAction:
    """Handle integration setup flow and create entities."""
    global _config, _client

    if not _config:
        config_path = os.path.join(api.config_dir_path, "config.json")
        _config = SynologyConfig(config_path)
    
    # Call setup handler from setup.py
    action = await setup_handler(msg, _config)
    
    # Entity creation happens ONLY on SetupComplete
    if isinstance(action, ucapi.SetupComplete):
        _LOG.info("Setup confirmed. Initializing integration components...")
        
        # Reuse the connected client from setup
        setup_client = get_setup_client()
        if setup_client and setup_client.connected:
            _LOG.info("Reusing connected client from setup process")
            _client = setup_client
            clear_setup_client()
        else:
            _LOG.error("No setup client available")
            return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
        
        _create_entities()
    
    return action


async def on_connect() -> None:
    """CRITICAL: Handle Remote Two connection with 2FA reboot survival."""
    global _client, _config
    
    _LOG.info("Remote Two connected. Attempting reboot survival reconnection...")
    await api.set_device_state(DeviceStates.CONNECTING)
    
    # Load config from disk (may have been updated)
    if not _config:
        config_path = os.path.join(api.config_dir_path, "config.json")
        _config = SynologyConfig(config_path)
    elif hasattr(_config, '_load_config'):
        _config._load_config()  # Force reload from disk
    
    # Handle client reconnection with 2FA consideration
    if _client:
        if _client.connected:
            _LOG.info("Client already connected - setting device state to CONNECTED")
            await api.set_device_state(DeviceStates.CONNECTED)
            return
        else:
            _LOG.info("Client exists but not connected - attempting 2FA-aware reconnection")
            
            # CRITICAL: Use special reconnection method for 2FA environments
            if hasattr(_client, 'reconnect_after_reboot'):
                if await _client.reconnect_after_reboot():
                    _LOG.info("✅ 2FA-aware reconnection successful")
                    await api.set_device_state(DeviceStates.CONNECTED)
                    return
                else:
                    _LOG.warning("2FA-aware reconnection failed, trying standard reconnection")
            
            # Fallback to standard reconnection
            if await _client.connect():
                _LOG.info("✅ Standard reconnection successful")
                await api.set_device_state(DeviceStates.CONNECTED)
                return
            else:
                _LOG.error("❌ All reconnection attempts failed")
                await api.set_device_state(DeviceStates.ERROR)
                return
    
    # If no client exists, try to recreate from config
    if _config and _config.is_configured():
        _LOG.info("No client exists but config available - recreating client")
        
        try:
            _client = _client_from_config()
            _create_entities()

            if await _client.connect():
                _LOG.info("✅ Client recreated and connected successfully")
                await api.set_device_state(DeviceStates.CONNECTED)
            else:
                _LOG.error("❌ Failed to connect recreated client")
                await api.set_device_state(DeviceStates.ERROR)
                
        except Exception as ex:
            _LOG.error(f"Error recreating client: {ex}")
            await api.set_device_state(DeviceStates.ERROR)
    else:
        _LOG.error("No configuration available for reconnection")
        await api.set_device_state(DeviceStates.ERROR)


async def on_subscribe_entities(entity_ids: list[str]):
    """Handle entity subscriptions and push initial state."""
    global _monitoring_task
    _LOG.info(f"Entities subscribed: {entity_ids}. Pushing initial state and starting monitoring.")
    
    # CRITICAL: Verify client is connected before proceeding
    if not _client or not _client.connected:
        _LOG.warning("Client not connected during subscription - attempting reconnection")
        if _client and hasattr(_client, 'reconnect_after_reboot'):
            await _client.reconnect_after_reboot()
        elif _client:
            await _client.connect()
    
    # Push initial state for each subscribed entity
    for entity_id in entity_ids:
        if _media_player and entity_id == _media_player.entity_id:
            _LOG.info(f"Pushing initial state for system media player: {entity_id}")
            await _media_player.push_initial_state()
            
        if _remote and entity_id == _remote.entity_id:
            _LOG.info(f"Pushing initial state for remote: {entity_id}")
            await _remote.push_initial_state()
            
        if _camera_monitor and entity_id == _camera_monitor.entity_id:
            _LOG.info(f"Pushing initial state for camera monitor: {entity_id}")
            await _camera_monitor.push_initial_state()

        if _sensors and _sensors.owns(entity_id):
            _sensors.push_initial_state(entity_id)
    
    # Start background monitoring after subscription. It also reconnects when the
    # NAS was unreachable, so it runs even if the client is not connected yet.
    if (not _monitoring_task or _monitoring_task.done()) and _client:
        _LOG.info("Starting background monitoring after entity subscription")
        _monitoring_task = asyncio.create_task(_background_monitoring_loop())


async def _background_monitoring_loop():
    """Background monitoring task with connection health checks and reconnect."""
    _LOG.info("Background monitoring loop started")
    consecutive_failures = 0
    max_failures = 3
    reconnect_delay = _RECONNECT_MIN
    next_reconnect = 0.0
    cycle = 0
    loop = asyncio.get_running_loop()

    while True:
        try:
            if _client and _client.connected:
                try:
                    test_data = await _client.get_system_overview()
                    if test_data:
                        consecutive_failures = 0
                        reconnect_delay = _RECONNECT_MIN
                        if _sensors:
                            _sensors.update_overview(test_data)
                            if cycle % _STORAGE_EVERY == 0:
                                _sensors.update_storage(await _client.get_storage_status())
                        cycle += 1
                    else:
                        consecutive_failures += 1
                        _LOG.warning(f"Connection health check failed ({consecutive_failures}/{max_failures})")
                except Exception as health_ex:
                    consecutive_failures += 1
                    _LOG.warning(f"Connection health check exception ({consecutive_failures}/{max_failures}): {health_ex}")

                if consecutive_failures >= max_failures:
                    _LOG.warning("Too many health check failures - marking disconnected")
                    _client._connected = False  # pylint: disable=protected-access
                    await api.set_device_state(DeviceStates.ERROR)
                    if _sensors:
                        _sensors.set_unavailable()
            elif _client and loop.time() >= next_reconnect:
                _LOG.info("Client disconnected - attempting reconnection")
                if await _client.connect():
                    _LOG.info("Reconnection successful")
                    consecutive_failures = 0
                    reconnect_delay = _RECONNECT_MIN
                    cycle = 0
                    await api.set_device_state(DeviceStates.CONNECTED)
                    _create_entities()  # adds the camera entity if it is new
                else:
                    next_reconnect = loop.time() + reconnect_delay
                    _LOG.warning(f"Reconnection failed, next attempt in {reconnect_delay}s")
                    reconnect_delay = min(reconnect_delay * 2, _RECONNECT_MAX)

            await asyncio.sleep(30)

        except asyncio.CancelledError:
            _LOG.info("Background monitoring loop cancelled")
            break
        except Exception as ex:
            _LOG.error(f"Error in background monitoring: {ex}")
            await asyncio.sleep(60)


async def on_disconnect() -> None:
    """Handle Remote Two disconnection."""
    global _monitoring_task
    _LOG.info("Remote Two disconnected. Setting device state to DISCONNECTED.")
    await api.set_device_state(DeviceStates.DISCONNECTED)
    
    # Cancel background monitoring
    if _monitoring_task and not _monitoring_task.done():
        _monitoring_task.cancel()
        try:
            await _monitoring_task
        except asyncio.CancelledError:
            pass
        _monitoring_task = None
    
    if _media_player:
        await _media_player.stop()
        
    if _camera_monitor:
        await _camera_monitor.stop()
    
    # CRITICAL: DO NOT disconnect client on Remote disconnect
    # Keep Synology session alive for reboot survival
    _LOG.info("Keeping Synology session alive for reboot survival")


def find_driver_json() -> str:
    """Find driver.json file with robust path resolution."""
    search_paths = []
    
    if __package__:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        search_paths.append(os.path.join(project_root, "driver.json"))
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        search_paths.extend([
            os.path.join(current_dir, "..", "driver.json"),
            os.path.join(current_dir, "driver.json"),
            os.path.join(os.getcwd(), "driver.json")
        ])
    
    for path in search_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path
    
    search_details = "\n".join(f"  {i+1}. {os.path.abspath(path)}" for i, path in enumerate(search_paths))
    raise FileNotFoundError(f"driver.json not found. Searched paths:\n{search_details}")


async def main():
    """Main integration entry point."""
    global api, _config, _client
    
    try:
        logging.basicConfig(
            level=logging.DEBUG, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        _LOG.info(f"Starting Synology Integration Driver with 2FA reboot survival")
        
        loop = asyncio.get_running_loop()
        api = ucapi.IntegrationAPI(loop)
        
        # Add event listeners
        api.add_listener(Events.CONNECT, on_connect)
        api.add_listener(Events.DISCONNECT, on_disconnect)
        api.add_listener(Events.SUBSCRIBE_ENTITIES, on_subscribe_entities)
        
        # Find and initialize with driver.json
        driver_json_path = find_driver_json()
        await api.init(driver_json_path, setup_handler_wrapper)
        await api.set_device_state(DeviceStates.DISCONNECTED)

        # Reboot survival: recreate the entities from the saved configuration so
        # they exist before the Remote subscribes. on_connect connects the client.
        _config = SynologyConfig(os.path.join(api.config_dir_path, "config.json"))
        if _config.is_configured():
            _client = _client_from_config()
            _create_entities()
        
        _LOG.info("Driver initialized. Waiting for remote connection and setup.")
        await asyncio.Future()
        
    except asyncio.CancelledError:
        _LOG.info("Driver task cancelled.")
    finally:
        if _monitoring_task:
            _monitoring_task.cancel()
        # Only disconnect on final shutdown, not on Remote disconnect
        if _client:
            await _client.disconnect()
        _LOG.info("Synology Integration Driver has stopped.")


if __name__ == "__main__":
    asyncio.run(main())