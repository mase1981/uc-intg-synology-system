"""
Remote entity for Synology System control commands

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any, Dict

from ucapi import StatusCodes
from ucapi.remote import Attributes, Commands, Features, States
from ucapi_framework import RemoteEntity

from uc_intg_synology_system.config import SynologyConfig
from uc_intg_synology_system.device import SynologyDevice

_LOG = logging.getLogger(__name__)

SIMPLE_COMMANDS = [
    "BEEP_ON",
    "BEEP_OFF",
    "SYSTEM_RESTART",
    "SYSTEM_SHUTDOWN",
]


class SynologySystemRemote(RemoteEntity):
    """Synology System control remote entity."""

    def __init__(self, config: SynologyConfig, device: SynologyDevice):
        self._device = device
        super().__init__(
            "synology_system_remote",
            "Synology System Control",
            [Features.ON_OFF, Features.SEND_CMD],
            {Attributes.STATE: States.UNKNOWN},
            simple_commands=SIMPLE_COMMANDS,
            cmd_handler=self.handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if self._device.state == "UNAVAILABLE":
            self.update({Attributes.STATE: States.UNAVAILABLE})
            return
        self.update({Attributes.STATE: States.ON})

    async def handle_command(self, entity, cmd_id: str, params: Dict[str, Any] = None) -> StatusCodes:
        """Handle remote control commands."""
        params = params or {}
        _LOG.info(f"Remote command received: {cmd_id}")

        try:
            if cmd_id in (Commands.ON, Commands.OFF):
                await self.sync_state()
                return StatusCodes.OK
            if cmd_id == Commands.SEND_CMD:
                command = params.get("command")
                if not command:
                    return StatusCodes.BAD_REQUEST
                repeat = max(1, int(params.get("repeat", 1) or 1))
                return await self._send_commands([command] * repeat, params)
            if cmd_id == Commands.SEND_CMD_SEQUENCE:
                sequence = params.get("sequence", [])
                commands = sequence.split(",") if isinstance(sequence, str) else list(sequence or [])
                if not commands:
                    return StatusCodes.BAD_REQUEST
                return await self._send_commands(commands, params)
            return StatusCodes.NOT_IMPLEMENTED
        except Exception as ex:
            _LOG.error(f"Error handling remote command '{cmd_id}': {ex}")
            return StatusCodes.SERVER_ERROR

    async def _send_commands(self, commands, params: Dict[str, Any]) -> StatusCodes:
        delay = int(params.get("delay", 0) or 0) / 1000
        for index, command in enumerate(commands):
            command = str(command).strip()
            if command not in SIMPLE_COMMANDS:
                _LOG.warning(f"Unknown command: {command}")
                return StatusCodes.BAD_REQUEST
            if not await self._device.run_system_command(command):
                return StatusCodes.SERVER_ERROR
            if delay and index < len(commands) - 1:
                await asyncio.sleep(delay)
        return StatusCodes.OK
