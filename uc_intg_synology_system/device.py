"""
Synology NAS device: owns the DSM client and polls it for the entities.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import time
from typing import Any, Dict

from ucapi_framework import DeviceEvents, PollingDevice

from uc_intg_synology_system.client import SynologySystemClient
from uc_intg_synology_system.config import SynologyConfig

_LOG = logging.getLogger(__name__)

POLL_INTERVAL = 15
_SLOW_EVERY = 20
_FAILURES_BEFORE_UNAVAILABLE = 3
_RETRY_MIN = 60
_RETRY_MAX = 900


class SynologyDevice(PollingDevice):
    """One Synology NAS. A single DSM session is created and reused for the device lifetime."""

    def __init__(self, device_config: SynologyConfig, **kwargs: Any) -> None:
        super().__init__(device_config, poll_interval=POLL_INTERVAL, **kwargs)
        self._device_config = device_config
        self._client = SynologySystemClient(
            host=device_config.host,
            port=device_config.port,
            username=device_config.username,
            password=device_config.password,
            secure=device_config.use_https,
            dsm_version=device_config.dsm_version,
            temperature_unit=device_config.temperature_unit,
            device_token=device_config.device_token,
        )
        self._connect_lock = asyncio.Lock()
        self._client_lock = asyncio.Lock()
        self._state = "UNAVAILABLE"
        self._failures = 0
        self._retry_at = 0.0
        self._retry_delay = _RETRY_MIN
        self._cycle = 0
        self._login_refused = False

        self.overview: Dict[str, Any] = {}
        self.storage: Dict[str, Any] = {}
        self.volumes: Dict[str, Any] = {}
        self.drives: Dict[str, Any] = {}
        self.raid: Dict[str, Any] = {}
        self.hardware: Dict[str, Any] = {}
        self.services: Dict[str, Any] = {}
        self.surveillance: Dict[str, Any] = {}

    @property
    def identifier(self) -> str:
        return self._device_config.identifier

    @property
    def name(self) -> str:
        return self._device_config.name

    @property
    def address(self) -> str:
        return self._device_config.host

    @property
    def log_id(self) -> str:
        return f"{self.name} ({self.address})"

    @property
    def state(self) -> str:
        return self._state

    @property
    def client(self) -> SynologySystemClient:
        return self._client

    @property
    def config(self) -> SynologyConfig:
        return self._device_config

    @property
    def login_refused(self) -> bool:
        """True after DSM refused the credentials; no further logins are attempted."""
        return self._login_refused

    async def connect(self) -> bool:
        async with self._connect_lock:
            return await super().connect()

    async def establish_connection(self) -> None:
        """Never raises: a failed first login is retried by the poll loop."""
        await self._refresh()

    async def poll_device(self) -> None:
        if self._state == "UNAVAILABLE" and (self._login_refused or time.monotonic() < self._retry_at):
            return
        await self._refresh()

    async def disconnect(self) -> None:
        async with self._connect_lock:
            async with self._client_lock:
                await self._client.disconnect()
            self._state = "UNAVAILABLE"
            await super().disconnect()

    async def _refresh(self) -> None:
        try:
            async with self._client_lock:
                if not self._client.connected or self._client.session_invalid:
                    if not await self._login():
                        self._set_unavailable()
                        return

                overview = await self._client.get_system_overview()
                if not overview:
                    self._failures += 1
                    _LOG.warning("[%s] Status request failed (%d/%d)", self.log_id, self._failures,
                                 _FAILURES_BEFORE_UNAVAILABLE)
                    if self._client.session_invalid:
                        self._client.mark_disconnected()
                    elif self._failures >= _FAILURES_BEFORE_UNAVAILABLE:
                        self._client.mark_disconnected()
                        self._set_unavailable()
                    return

                self.overview = overview
                self._failures = 0
                if self._cycle % _SLOW_EVERY == 0:
                    await self._refresh_slow_data()
                self._cycle += 1

            self._retry_delay = _RETRY_MIN
            self._state = "ON"
            self.push_update()
        except Exception as err:  # pylint: disable=broad-except
            _LOG.error("[%s] Refresh error: %s", self.log_id, err)
            self._failures += 1
            if self._failures >= _FAILURES_BEFORE_UNAVAILABLE:
                self._client.mark_disconnected()
                self._set_unavailable()

    async def _login(self) -> bool:
        if await self._client.connect():
            self._cycle = 0
            self._failures = 0
            self._persist_login_state()
            return True

        if self._client.auth_failed:
            blocked = "blocked" in (self._client.last_error or "").lower()
            if blocked:
                _LOG.error("[%s] %s. Retrying with backoff.", self.log_id, self._client.last_error)
            else:
                _LOG.error("[%s] DSM refused the login (%s). Not retrying; reconfigure the integration.",
                           self.log_id, self._client.last_error)
                self._login_refused = True
        return False

    def _persist_login_state(self) -> None:
        changes = {}
        token = self._client.device_token or ""
        if token != self._device_config.device_token:
            changes["device_token"] = token
        packages = self._client.available_packages
        if packages and packages != self._device_config.available_packages:
            changes["available_packages"] = dict(packages)
        if changes:
            self.update_config(**changes)

    async def _refresh_slow_data(self) -> None:
        """Storage-based and package data changes slowly, so it is not fetched every poll."""
        self.storage = await self._client.get_storage_status() or self.storage
        self.volumes = await self._client.get_volume_status() or self.volumes
        self.drives = await self._client.get_drive_health() or self.drives
        self.raid = await self._client.get_raid_status() or self.raid
        self.hardware = await self._client.get_hardware_monitor() or self.hardware
        self.services = await self._client.get_services_status() or self.services
        if "SurveillanceStation" in self._client.available_packages:
            self.surveillance = await self._client.get_surveillance_status() or self.surveillance

    def _set_unavailable(self) -> None:
        was_available = self._state != "UNAVAILABLE"
        self._state = "UNAVAILABLE"
        self._retry_at = time.monotonic() + self._retry_delay
        self._retry_delay = min(self._retry_delay * 2, _RETRY_MAX)
        if was_available:
            _LOG.warning("[%s] NAS unreachable: %s", self.log_id, self._client.last_error or "no response")
            self.events.emit(DeviceEvents.DISCONNECTED, self.identifier)
        self.push_update()

    async def run_system_command(self, command: str) -> bool:
        """Execute a remote entity command against the NAS."""
        if self._state == "UNAVAILABLE" or not self._client.connected:
            _LOG.error("[%s] Cannot execute %s - NAS not connected", self.log_id, command)
            return False
        try:
            async with self._client_lock:
                if command == "BEEP_ON":
                    await self._client.beep(True)
                elif command == "BEEP_OFF":
                    await self._client.beep(False)
                elif command == "SYSTEM_RESTART":
                    _LOG.warning("[%s] System restart requested", self.log_id)
                    await self._client.reboot()
                elif command == "SYSTEM_SHUTDOWN":
                    _LOG.warning("[%s] System shutdown requested", self.log_id)
                    await self._client.shutdown()
                else:
                    _LOG.warning("[%s] Unknown command: %s", self.log_id, command)
                    return False
            return True
        except Exception as err:  # pylint: disable=broad-except
            _LOG.error("[%s] Command %s failed: %s", self.log_id, command, err)
            return False
