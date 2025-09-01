"""
Remote entity for Synology System control commands

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from typing import Any, Dict, Optional

import ucapi
from ucapi import StatusCodes
from ucapi.remote import Attributes, Commands, Features, Remote, States

from uc_intg_synology_system.client import SynologySystemClient
from uc_intg_synology_system.config import SynologyConfig

_LOG = logging.getLogger(__name__)


class SynologySystemRemote:
    """Synology System control remote entity with placeholder support."""

    def __init__(self, api: ucapi.IntegrationAPI, client: Optional[SynologySystemClient], config: SynologyConfig):
        """
        Initialize system remote - supports None client for placeholders.
        
        :param api: The ucapi IntegrationAPI instance
        :param client: Synology API client (can be None for placeholders)
        :param config: Configuration manager
        """
        self._api = api
        self._client = client  # Can be None for placeholder entities
        self._config = config
        
        self._entity = self._create_remote_entity()
        
        _LOG.info("Synology System Remote initialized")

    def _create_remote_entity(self) -> Remote:
        """Create remote entity with only working commands."""
        features = [Features.ON_OFF, Features.SEND_CMD]
        
        # CRITICAL: Initialize with proper state attribute for reboot survival
        attributes = {Attributes.STATE: States.OFF}
        
        # ONLY FUNCTIONAL COMMANDS
        simple_commands = [
            "BEEP_ON",           # Uses enable_beep_control(True)
            "BEEP_OFF",          # Uses enable_beep_control(False) 
            "SYSTEM_RESTART",    # Uses reboot() - requires confirmation
            "SYSTEM_SHUTDOWN"    # Uses shutdown() - requires confirmation
        ]
        
        return Remote(
            identifier="synology_system_remote",
            name="Synology System Control",
            features=features,
            attributes=attributes,
            simple_commands=simple_commands,
            cmd_handler=self.handle_command
        )

    async def handle_command(self, entity_arg: ucapi.entity.Entity, cmd_id: str, params: Dict[str, Any] = None) -> StatusCodes:
        """Handle remote control commands."""
        _LOG.info(f"Remote command received: {cmd_id}")
        
        try:
            if cmd_id == Commands.ON:
                await self._handle_remote_on()
                return StatusCodes.OK
            elif cmd_id == Commands.OFF:
                await self._handle_remote_off()
                return StatusCodes.OK
            elif cmd_id == Commands.SEND_CMD:
                command = params.get("command") if params else None
                if command:
                    success = await self._handle_system_command(command, params)
                    return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST
            return StatusCodes.NOT_IMPLEMENTED
        except Exception as ex:
            _LOG.error(f"Error handling remote command '{cmd_id}': {ex}")
            return StatusCodes.SERVER_ERROR

    async def _handle_remote_on(self) -> None:
        """Handle remote on command."""
        self._entity.attributes[Attributes.STATE] = States.ON
        self._api.configured_entities.update_attributes(self.entity_id, {Attributes.STATE: States.ON})

    async def _handle_remote_off(self) -> None:
        """Handle remote off command."""
        self._entity.attributes[Attributes.STATE] = States.OFF
        self._api.configured_entities.update_attributes(self.entity_id, {Attributes.STATE: States.OFF})

    async def _handle_system_command(self, command: str, params: Dict[str, Any] = None) -> bool:
        """Execute only functional system commands."""
        _LOG.info(f"Executing system command: {command}")
        
        if not self._client or not self._client.connected:
            _LOG.error("Cannot execute command - client not available or not connected")
            return False
        
        try:
            if command == "BEEP_ON":
                _LOG.info("Activating NAS beep")
                self._client._sys_info.enable_beep_control(True)
                return True
                
            elif command == "BEEP_OFF":
                _LOG.info("Deactivating NAS beep")
                self._client._sys_info.enable_beep_control(False)
                return True
                
            elif command == "SYSTEM_RESTART":
                _LOG.warning("SYSTEM RESTART REQUESTED - This will reboot your NAS!")
                self._client._sys_info.reboot()
                return True
                
            elif command == "SYSTEM_SHUTDOWN":
                _LOG.warning("SYSTEM SHUTDOWN REQUESTED - This will shutdown your NAS!")
                self._client._sys_info.shutdown()
                return True
                
            else:
                _LOG.warning(f"Unknown command: {command}")
                return False
                
        except Exception as ex:
            _LOG.error(f"Error executing command '{command}': {ex}")
            return False

    async def push_initial_state(self) -> None:
        """Update remote state based on connection status."""
        try:
            new_state = States.ON if self._client and self._client.connected else States.OFF
            if self._entity.attributes[Attributes.STATE] != new_state:
                self._entity.attributes[Attributes.STATE] = new_state
                _LOG.info(f"Pushing initial remote state: {new_state}")
                self._api.configured_entities.update_attributes(self.entity_id, {Attributes.STATE: new_state})
        except Exception as ex:
            _LOG.error(f"Error pushing initial state for remote: {ex}", exc_info=True)

    def update_client(self, client: SynologySystemClient) -> None:
        """Update client reference for placeholder entities."""
        self._client = client
        _LOG.info("Client updated for remote entity")

    @property
    def entity(self) -> Remote:
        return self._entity

    @property
    def entity_id(self) -> str:
        return self._entity.id