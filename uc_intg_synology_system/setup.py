"""
Setup flow for Synology System integration.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from typing import Any, Dict

import ucapi

from uc_intg_synology_system.client import SynologySystemClient
from uc_intg_synology_system.config import SynologyConfig
from uc_intg_synology_system.helpers import validate_ip_address, validate_port

_LOG = logging.getLogger(__name__)

# Global variable to store the validated client from setup
_setup_client: SynologySystemClient = None


async def setup_handler(msg: ucapi.SetupDriver, config: SynologyConfig) -> ucapi.SetupAction:

    global _setup_client
    
    try:
        _LOG.info(f"Setup handler called with message type: {type(msg)}")
        
        if isinstance(msg, ucapi.DriverSetupRequest):
            _LOG.info("Processing DriverSetupRequest")
            
            setup_data = msg.setup_data
            reconfigure = msg.reconfigure
            
            if reconfigure:
                _LOG.info("Reconfiguring existing integration")
            
            # Validate required fields
            required_fields = ["host", "port", "username", "password"]
            for field in required_fields:
                if field not in setup_data or not str(setup_data[field]).strip():
                    _LOG.error(f"Missing required field: {field}")
                    return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
            
            # Validate and sanitize input
            host = str(setup_data["host"]).strip()
            try:
                port = int(setup_data["port"])
            except ValueError:
                _LOG.error(f"Invalid port number: {setup_data['port']}")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
            
            username = str(setup_data["username"]).strip()
            password = str(setup_data["password"])
            
            # Validate IP address
            if not validate_ip_address(host):
                _LOG.error(f"Invalid IP address format: {host}")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
            
            # Validate port
            if not validate_port(port):
                _LOG.error(f"Invalid port number: {port}")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
            
            # Get optional parameters
            use_https = setup_data.get("use_https", True)
            if isinstance(use_https, str):
                use_https = use_https.lower() in ("true", "1", "yes")
            
            temperature_unit = str(setup_data.get("temperature_unit", "celsius")).lower()
            otp_code = str(setup_data.get("otp_code", "")).strip()
            
            # Validate temperature unit
            if temperature_unit not in ["celsius", "fahrenheit"]:
                temperature_unit = "celsius"
            
            _LOG.info(f"Attempting to connect to Synology NAS at {host}:{port}")
            
            # Test connection to Synology NAS
            try:
                client = SynologySystemClient(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    secure=use_https,
                    dsm_version=7,  # Only support DSM 7.x
                    otp_code=otp_code if otp_code else None,
                    temperature_unit=temperature_unit
                )
                
                # Attempt connection
                if not await client.connect():
                    error_msg = client.last_error or "Connection failed"
                    _LOG.error(f"Failed to connect to Synology NAS: {error_msg}")
                    
                    # Determine appropriate error code
                    if "authentication" in error_msg.lower() or "login" in error_msg.lower():
                        return ucapi.SetupError(ucapi.IntegrationSetupError.AUTHORIZATION_ERROR)
                    elif "timeout" in error_msg.lower():
                        return ucapi.SetupError(ucapi.IntegrationSetupError.TIMEOUT)
                    elif "connection refused" in error_msg.lower():
                        return ucapi.SetupError(ucapi.IntegrationSetupError.CONNECTION_REFUSED)
                    else:
                        return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
                
                _LOG.info("Successfully connected to Synology NAS")
                
                # Get basic system information for validation
                system_info = await client.get_system_overview()
                if not system_info:
                    _LOG.error("Failed to retrieve system information")
                    return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
                
                _LOG.info(f"Connected to Synology {system_info.get('model', 'Unknown')} "
                         f"running DSM {system_info.get('version', 'Unknown')}")
                
                # Update configuration with validated data
                config_data = {
                    "host": host,
                    "port": port,
                    "username": username,
                    "password": password,
                    "use_https": use_https,
                    "temperature_unit": temperature_unit,
                    "otp_code": otp_code
                }
                
                if not config.update_from_setup_data(config_data):
                    _LOG.error("Failed to save configuration")
                    return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
                
                # Update available packages
                available_packages = client.available_packages
                config.update_available_packages(available_packages)
                
                _LOG.info("Setup completed successfully")
                _LOG.info(f"Available packages: {list(available_packages.keys())}")
                
                # Store the connected client for reuse instead of disconnecting
                _setup_client = client
                _LOG.info("Stored connected client for entity creation")
                
                return ucapi.SetupComplete()
                
            except ValueError as ve:
                # DSM version or other validation error
                _LOG.error(f"Configuration error: {ve}")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
                
            except Exception as ex:
                _LOG.error(f"Unexpected error during setup: {ex}")
                return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
        
        elif isinstance(msg, ucapi.UserDataResponse):
            # Currently not used - setup is single-step
            _LOG.info("User data response received (not implemented)")
            return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
        
        elif isinstance(msg, ucapi.UserConfirmationResponse):
            # Currently not used - setup is single-step  
            _LOG.info("User confirmation response received (not implemented)")
            return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
        
        elif isinstance(msg, ucapi.AbortDriverSetup):
            _LOG.info(f"Setup aborted: {msg.error}")
            
            # Clean up stored client if setup is aborted
            if _setup_client:
                try:
                    await _setup_client.disconnect()
                except:
                    pass
                _setup_client = None
                
            return ucapi.SetupComplete()
        
        else:
            _LOG.warning(f"Unknown setup message type: {type(msg)}")
            return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)
        
    except Exception as ex:
        _LOG.error(f"Setup handler exception: {ex}")
        
        # Clean up on any error
        if _setup_client:
            try:
                await _setup_client.disconnect()
            except:
                pass
            _setup_client = None
            
        return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)


def get_setup_client() -> SynologySystemClient:

    global _setup_client
    return _setup_client


def clear_setup_client():
    """Clear the stored setup client."""
    global _setup_client
    _setup_client = None