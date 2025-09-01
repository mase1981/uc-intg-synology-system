"""
Media Player entity for Synology System monitoring dashboard

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import base64
import logging
import os
from typing import Any, Dict

import ucapi
from ucapi import StatusCodes
from ucapi.media_player import Attributes, Commands, Features, MediaPlayer, States

from uc_intg_synology_system.client import SynologySystemClient
from uc_intg_synology_system.config import SynologyConfig
from uc_intg_synology_system.helpers import create_two_line_display

_LOG = logging.getLogger(__name__)

# Commands to suppress to prevent red error messages and accidental system actions
SUPPRESSED_COMMANDS = [
    Commands.PLAY_PAUSE,
    Commands.STOP,
    Commands.SHUFFLE,
    Commands.REPEAT,
    Commands.NEXT,
    Commands.PREVIOUS,
    Commands.FAST_FORWARD,
    Commands.REWIND,
    Commands.SEEK,
    Commands.RECORD,
    Commands.MY_RECORDINGS,
    Commands.EJECT,
    Commands.OPEN_CLOSE,
]


class SynologySystemDashboard:

    def __init__(self, api: ucapi.IntegrationAPI, client: SynologySystemClient, config: SynologyConfig):
        """
        Initialize system dashboard.
        
        :param api: The ucapi IntegrationAPI instance
        :param client: Synology API client
        :param config: Configuration manager
        """
        self._api = api
        self._client = client
        self._config = config
        self._current_source = "System Overview"
        self._sources = self._get_enabled_sources()
        self._polling_task = None
        self._last_data = {}
        self._icon_cache = {}  # Cache for base64 icons
        
        _LOG.info(f"Initializing dashboard with sources: {list(self._sources.keys())}")
        
        self._entity = self._create_media_player_entity()
        
        _LOG.info(f"Synology System Dashboard initialized with sources: {list(self._sources.keys())}")

    def _get_enabled_sources(self) -> Dict[str, str]:
        sources = self._config.get_enabled_sources()
        
        # Limit to 25 sources maximum for media player
        if len(sources) > 25:
            _LOG.warning(f"Too many sources ({len(sources)}), limiting to 20")
            source_items = list(sources.items())[:25]
            sources = dict(source_items)
        
        return sources

    def _get_icon_base64(self, icon_filename: str) -> str:
        if icon_filename in self._icon_cache:
            return self._icon_cache[icon_filename]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(script_dir, "icons")
        icon_path = os.path.join(icon_dir, icon_filename)
        
        fallback_icons = ["synology_logo.png", "system_overview.png"]

        if not os.path.exists(icon_path):
            _LOG.warning(f"Icon not found: {icon_filename}")
            for fallback in fallback_icons:
                icon_path = os.path.join(icon_dir, fallback)
                if os.path.exists(icon_path):
                    _LOG.info(f"Using fallback icon: {fallback}")
                    break
            else:
                _LOG.error("No fallback icons found")
                return ""

        try:
            with open(icon_path, 'rb') as f:
                icon_data = f.read()
                base64_data = base64.b64encode(icon_data).decode('utf-8')
                data_url = f"data:image/png;base64,{base64_data}"
                self._icon_cache[icon_filename] = data_url
                _LOG.info(f"Loaded and cached icon: {icon_filename}")
                return data_url
        except Exception as e:
            _LOG.error(f"Failed to read icon {icon_path}: {e}")
            return ""

    def _get_source_image(self, source: str) -> str:
        """Get the proper base64 image data for a given source with complete mapping."""
        source_images = {
            "System Overview": "system_overview.png",
            "Storage Status": "storage_status.png", 
            "Network Statistics": "network_stats.png",
            "Services Status": "services_status.png",
            "Security Status": "security_status.png",
            "Docker Containers": "docker_status.png",
            "Surveillance Station": "surveillance_status.png",
            "Temperature Monitor": "thermal_status.png",
            "SSD Cache": "cache_status.png",
            "RAID Health": "raid_status.png",
            "Volume Usage": "volume_status.png",
            "UPS Monitor": "ups_status.png",
            # Enhanced source mappings
            "Hardware Monitor": "hardware_monitor.png",
            "Drive Health": "drive_health.png", 
            "Power Management": "power_management.png",
            "Cache Performance": "cache_performance.png",
            "Package Manager": "package_manager.png",
            "User Sessions": "user_sessions.png"
        }
        
        image_filename = source_images.get(source, "synology_logo.png")
        _LOG.debug(f"Source '{source}' mapped to icon '{image_filename}'")
        return self._get_icon_base64(image_filename)

    def _create_media_player_entity(self) -> MediaPlayer:
        """Create media player entity for system dashboard."""
        features = [
            Features.ON_OFF,
            Features.SELECT_SOURCE,
            Features.VOLUME_UP_DOWN,
            Features.MEDIA_TITLE,
            Features.MEDIA_ARTIST,
            Features.MEDIA_IMAGE_URL,
        ]
        
        initial_icon_base64 = self._get_source_image(self._current_source)
        
        attributes = {
            Attributes.STATE: States.PAUSED,
            Attributes.SOURCE: self._current_source,
            Attributes.SOURCE_LIST: list(self._sources.values()),
            Attributes.MEDIA_TITLE: "Synology System Monitor",
            Attributes.MEDIA_ARTIST: "Initializing...",
            Attributes.MEDIA_IMAGE_URL: initial_icon_base64,
            Attributes.VOLUME: 50
        }
        
        _LOG.debug(f"Created media player with base64 icon loaded: {bool(initial_icon_base64)}")
        
        return MediaPlayer(
            identifier="synology_system_dashboard",
            name="Synology System Monitor",
            features=features,
            attributes=attributes,
            cmd_handler=self.handle_command
        )

    async def handle_command(self, entity_arg: ucapi.entity.Entity, cmd_id: str, params: Dict[str, Any] = None) -> StatusCodes:
        """Handle media player commands - HTCP exact pattern."""
        _LOG.debug(f"Received command: {cmd_id} with params: {params}")
        
        try:
            if cmd_id == Commands.SELECT_SOURCE:
                source = params.get("source") if params else None
                if source:
                    await self._handle_source_selection(source)
                    return StatusCodes.OK
                return StatusCodes.BAD_REQUEST
            elif cmd_id == Commands.ON:
                await self._handle_power_on()
                return StatusCodes.OK
            elif cmd_id == Commands.OFF:
                await self._handle_power_off()
                return StatusCodes.OK
            elif cmd_id == Commands.VOLUME_UP:
                await self._handle_navigate_next()
                return StatusCodes.OK
            elif cmd_id == Commands.VOLUME_DOWN:
                await self._handle_navigate_previous()
                return StatusCodes.OK
            elif cmd_id in SUPPRESSED_COMMANDS:
                # HTCP exact pattern - silently ignore to prevent red errors
                _LOG.debug(f"Ignoring unsupported media command '{cmd_id}' to prevent UI error.")
                return StatusCodes.OK
            elif cmd_id in ["REFRESH_STATUS", "UPDATE_DISPLAY", "SYSTEM_INFO"]:
                await self._handle_custom_command(cmd_id, params)
                return StatusCodes.OK
            else:
                _LOG.warning(f"Unhandled command: {cmd_id}")
                return StatusCodes.NOT_IMPLEMENTED
                
        except Exception as ex:
            _LOG.error(f"Error handling command '{cmd_id}': {ex}")
            return StatusCodes.SERVER_ERROR

    async def push_initial_state(self) -> None:
        """Fetch initial data, push it to the remote, and start monitoring - HTCP pattern."""
        try:
            _LOG.info("Pushing initial state for Synology System Dashboard.")
            await self._update_source_display()
            self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)
            await self.start()
        except Exception as ex:
            _LOG.error(f"Error pushing initial state for dashboard: {ex}", exc_info=True)

    async def _handle_source_selection(self, source_name: str) -> None:
        """Handle source selection - HTCP exact pattern."""
        if source_name != self._current_source:
            _LOG.info(f"Switching monitoring view to: {source_name}")
            self._current_source = source_name
            self._entity.attributes[Attributes.SOURCE] = source_name
            self._entity.attributes[Attributes.MEDIA_IMAGE_URL] = self._get_source_image(source_name)
            await self._update_current_data()
            self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)

    async def _handle_power_on(self) -> None:
        """Handle power on - start monitoring."""
        await self.start()
        await self._update_current_data()
        self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)

    async def _handle_power_off(self) -> None:
        """Handle power off - pause monitoring."""
        await self.stop()
        self._entity.attributes[Attributes.STATE] = States.PAUSED
        self._api.configured_entities.update_attributes(self.entity_id, {Attributes.STATE: States.PAUSED})

    async def _handle_navigate_next(self) -> None:
        await self._refresh_display()

    async def _handle_navigate_previous(self) -> None:
        await self._refresh_display()

    async def _handle_custom_command(self, cmd_id: str, params: Dict[str, Any] = None) -> None:
        if cmd_id in ["REFRESH_STATUS", "SYSTEM_INFO", "UPDATE_DISPLAY"]:
            await self._refresh_display()

    async def _update_source_display(self) -> None:
        """Update display for current source."""
        # Set base64 icon for current source
        icon_base64 = self._get_source_image(self._current_source)
        if icon_base64:
            self._entity.attributes[Attributes.MEDIA_IMAGE_URL] = icon_base64
            _LOG.debug(f"Set base64 icon for source {self._current_source}")
        
        await self._update_current_data()

    async def _update_current_data(self, force_refresh: bool = False) -> None:
        """Update current data based on selected source."""
        if not self._client.connected:
            _LOG.warning("Client not connected, skipping data update")
            return
        
        # Source key mapping - handle both internal keys and display names
        source_key = self._current_source
        if self._current_source in self._sources.values():
            # Convert display name back to key
            source_key = next((key for key, name in self._sources.items() if name == self._current_source), self._current_source)
        
        fetcher_map = {
            "SYSTEM_OVERVIEW": self._client.get_system_overview,
            "STORAGE_STATUS": self._client.get_storage_status,
            "NETWORK_STATS": self._client.get_network_stats,
            "SERVICES_STATUS": self._client.get_services_status,
            "SECURITY_STATUS": self._client.get_security_status,
            "DOCKER_STATUS": self._client.get_docker_status,
            "SURVEILLANCE_STATUS": self._client.get_surveillance_status,
            "THERMAL_STATUS": self._client.get_thermal_status,
            "CACHE_STATUS": self._client.get_cache_status,
            "RAID_STATUS": self._client.get_raid_status,
            "VOLUME_STATUS": self._client.get_volume_status,
            "UPS_STATUS": self._client.get_ups_status,
            # Enhanced monitoring sources
            "HARDWARE_MONITOR": self._client.get_hardware_monitor,
            "DRIVE_HEALTH": self._client.get_drive_health,
            "POWER_MANAGEMENT": self._client.get_power_management,
            "CACHE_PERFORMANCE": self._client.get_cache_performance,
            "PACKAGE_MANAGER": self._client.get_package_manager,
            "USER_SESSIONS": self._client.get_user_sessions,
        }
        
        updater_map = {
            "SYSTEM_OVERVIEW": self._update_system_overview_display,
            "STORAGE_STATUS": self._update_storage_status_display,
            "NETWORK_STATS": self._update_network_stats_display,
            "SERVICES_STATUS": self._update_services_status_display,
            "SECURITY_STATUS": self._update_security_status_display,
            "DOCKER_STATUS": self._update_docker_status_display,
            "SURVEILLANCE_STATUS": self._update_surveillance_status_display,
            "THERMAL_STATUS": self._update_thermal_status_display,
            "CACHE_STATUS": self._update_cache_status_display,
            "RAID_STATUS": self._update_raid_status_display,
            "VOLUME_STATUS": self._update_volume_status_display,
            "UPS_STATUS": self._update_ups_status_display,
            "HARDWARE_MONITOR": self._update_hardware_monitor_display,
            "DRIVE_HEALTH": self._update_drive_health_display,
            "POWER_MANAGEMENT": self._update_power_management_display,
            "CACHE_PERFORMANCE": self._update_cache_performance_display,
            "PACKAGE_MANAGER": self._update_package_manager_display,
            "USER_SESSIONS": self._update_user_sessions_display,
        }

        fetcher = fetcher_map.get(source_key)
        updater = updater_map.get(source_key)

        if fetcher and updater:
            _LOG.debug(f"Fetching data for source: {source_key}")
            try:
                data = await fetcher()
                _LOG.debug(f"Received data for {source_key}: {data}")
                await updater(data)
            except AttributeError as ex:
                _LOG.warning(f"Method not implemented for {source_key}: {ex}")
                self._entity.attributes[Attributes.MEDIA_TITLE] = f"{self._current_source}"
                self._entity.attributes[Attributes.MEDIA_ARTIST] = "Feature not available"
        else:
            _LOG.warning(f"No fetcher/updater found for source: {source_key}")
            self._entity.attributes[Attributes.MEDIA_TITLE] = f"{self._current_source}"
            self._entity.attributes[Attributes.MEDIA_ARTIST] = "Coming soon"

    async def _update_system_overview_display(self, data: Dict[str, Any]) -> None:
        if data:
            self._entity.attributes[Attributes.STATE] = States.PLAYING if data.get('status') == "healthy" else States.PAUSED
            line1 = f"{data.get('model', 'NAS')} - {data.get('status', '...').title()}"
            line2 = f"CPU: {data.get('cpu_usage', 0):.1f}% | Mem: {data.get('memory_usage', 0):.1f}% | {data.get('temperature', 'N/A')}"
            self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_storage_status_display(self, data: Dict[str, Any]) -> None:
        if data and data.get('total_size', 0) > 0:
            usage_pct = (data.get('total_used', 0) / data['total_size']) * 100
            line1 = f"Storage - {data.get('health_status', '...').title()}"
            line2 = f"Used: {usage_pct:.1f}%"
            self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_network_stats_display(self, data: Dict[str, Any]) -> None:
        """Update network statistics display to show live totals from utilization API."""
        if data:
            # Handle interface count properly
            interface_count = data.get('interfaces', 0)
            if isinstance(interface_count, list):
                interface_count = len(interface_count)
            elif isinstance(interface_count, dict):
                interface_count = len(interface_count)
            
            status = data.get('status', 'unknown')
            
            rx_bytes = data.get('total_rx', 0)
            tx_bytes = data.get('total_tx', 0)
            
            # Convert bytes to MB for display
            rx_mb = rx_bytes / (1024 * 1024) if rx_bytes > 0 else 0
            tx_mb = tx_bytes / (1024 * 1024) if tx_bytes > 0 else 0
            
            line1 = f"{status.title()} | Interfaces: {interface_count}"
            line2 = f"RX: {rx_mb:.1f}MB | TX: {tx_mb:.1f}MB"
        else:
            line1 = "Network data unavailable"
            line2 = "Network Statistics"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_services_status_display(self, data: Dict[str, Any]) -> None:
        """Update services status display."""
        if data:
            # Use the correct data structure from client
            system_services = data.get('system_services', [])
            package_services = data.get('package_services', []) 
            running_count = data.get('running_count', 0)
            total_count = data.get('total_count', 0)
            
            # If no running count, calculate from service list
            if running_count == 0 and system_services:
                running_count = sum(1 for s in system_services if s.get('enable_status') == 'enabled' or s.get('status') == 'running')
                total_count = len(system_services)
            
            line1 = f"Services - {running_count}/{total_count} running"
            line2 = f"System: {len(system_services)} | Packages: {len(package_services)}"
        else:
            line1 = "Services Status"
            line2 = "Service information unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_security_status_display(self, data: Dict[str, Any]) -> None:
        if data:
            firewall = "enabled" if data.get('firewall_enabled') else "disabled"
            line1 = f"Security - {data.get('status', '...').title()}"
            line2 = f"Issues: {data.get('issues_found', 0)} | Firewall: {firewall}"
            self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_docker_status_display(self, data: Dict[str, Any]) -> None:
        if data:
            status = data.get('status', 'unknown')
            running_count = data.get('running_count', 0)
            total_count = data.get('total_count', 0)
            
            line1 = f"Docker - {status.title()}"
            line2 = f"Containers: {running_count}/{total_count} running"
            
            self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_surveillance_status_display(self, data: Dict[str, Any]) -> None:
        if data:
            camera_count = data.get('camera_count', 0)
            recording_count = data.get('recording_count', 0)
            line1 = f"Surveillance - {data.get('status', 'Unknown').title()}"
            line2 = f"Cameras: {camera_count} | Recording: {recording_count}"
            self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_thermal_status_display(self, data: Dict[str, Any]) -> None:
        """Update thermal status display with properly formatted temperature."""
        if data and data.get('system_temp', 0) > 0:
            status = data.get('status', 'unknown').title()
            temp_formatted = data.get('temperature_formatted', 'N/A')
            fan_mode = data.get('fan_mode', 'auto')
            
            line1 = f"Thermal - {status}"
            line2 = f"Temp: {temp_formatted} | Fan: {fan_mode}"
        else:
            line1 = "Thermal Monitor"
            line2 = "Temperature sensor unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_cache_status_display(self, data: Dict[str, Any]) -> None:
        """Update SSD cache status display."""
        if data and data.get('cache_enabled', False):
            cache_usage = data.get('cache_usage', 0)
            cache_hit_rate = data.get('cache_hit_rate', 0)
            ssd_count = data.get('ssd_count', 0)
            
            line1 = f"Usage: {cache_usage}% | Hit Rate: {cache_hit_rate}% | SSDs: {ssd_count}"
            line2 = f"SSD Cache - {data.get('status', 'Unknown').title()}"
        else:
            line1 = "No SSD cache detected or configured"
            line2 = "SSD Cache - Disabled"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_raid_status_display(self, data: Dict[str, Any]) -> None:
        """Update RAID status display with real RAID data."""
        if data:
            raid_level = data.get('raid_level', 'unknown')
            total_drives = data.get('total_drives', 0)
            healthy_drives = data.get('healthy_drives', 0)
            degraded_drives = data.get('degraded_drives', 0)
            rebuilding = data.get('rebuilding', False)
            
            if rebuilding:
                status_text = "Rebuilding"
            elif degraded_drives > 0:
                status_text = "Degraded"
            else:
                status_text = data.get('status', 'Unknown').title()
            
            line1 = f"RAID {raid_level} - {status_text}"
            line2 = f"Drives: {healthy_drives}/{total_drives} healthy"
            
            if degraded_drives > 0:
                line2 += f" | {degraded_drives} degraded"
        else:
            line1 = "RAID Health"
            line2 = "RAID information unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_volume_status_display(self, data: Dict[str, Any]) -> None:
        """Update volume status display."""
        if data:
            volume_count = data.get('volume_count', 0)
            healthy_volumes = data.get('healthy_volumes', 0)
            warning_volumes = data.get('warning_volumes', 0)
            critical_volumes = data.get('critical_volumes', 0)
            avg_usage = data.get('average_usage', 0)
            
            status = data.get('status', 'unknown').title()
            
            line1 = f"Healthy: {healthy_volumes}/{volume_count} | Avg Usage: {avg_usage}%"
            line2 = f"Volumes - {status}"
            
            if warning_volumes > 0 or critical_volumes > 0:
                line1 = f"Issues: {warning_volumes + critical_volumes} | Usage: {avg_usage}%"
        else:
            line1 = "Volume information unavailable"
            line2 = "Volume Usage"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_ups_status_display(self, data: Dict[str, Any]) -> None:
        """Update UPS status display to show model and status information."""
        if data:
            ups_connected = data.get('ups_connected', False)
            ups_model = data.get('ups_model', 'Unknown')
            battery_level = data.get('battery_level', 0)
            runtime_minutes = data.get('runtime_minutes', 0)
            status = data.get('status', 'unknown').title()
            
            if ups_connected:
                runtime_hours = runtime_minutes // 60
                runtime_mins = runtime_minutes % 60
                
                if ups_model and ups_model not in ["Unknown", "Not Detected"]:
                    line1 = f"{ups_model} - {status}"  # e.g. "APC Smart-UPS 1500 - Connected"
                else:
                    line1 = f"UPS - {status}"  # Fallback if no model detected
                
                line2 = f"Battery: {battery_level}% | Runtime: {runtime_hours}h {runtime_mins}m"
                
            else:
                line1 = f"UPS - {status}"
                line2 = "No UPS detected or configured"
                
        else:
            line1 = "UPS Monitor"
            line2 = "UPS information unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_hardware_monitor_display(self, data: Dict[str, Any]) -> None:
        """Update hardware monitoring display with properly formatted temperatures."""
        if data:
            cpu_temp_formatted = data.get('cpu_temp_formatted', data.get('cpu_temp', 0))
            drive_count = data.get('monitored_drives', 0)
            avg_temp_formatted = data.get('average_drive_temp_formatted', data.get('average_drive_temp', 0))
            
            # Handle case where we get numeric value instead of formatted string
            if isinstance(cpu_temp_formatted, (int, float)):
                cpu_temp_formatted = f"{cpu_temp_formatted}°C"
            if isinstance(avg_temp_formatted, (int, float)):
                avg_temp_formatted = f"{avg_temp_formatted}°C"
            
            line1 = f"CPU: {cpu_temp_formatted} | {drive_count} drives | Avg: {avg_temp_formatted}"
            line2 = f"Hardware - {data.get('status', 'Unknown').title()}"
        else:
            line1 = "Hardware data unavailable"
            line2 = "Hardware Monitor"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_drive_health_display(self, data: Dict[str, Any]) -> None:
        """Update drive health display."""
        if data:
            total_drives = data.get('total_drives', 0)
            healthy_drives = data.get('healthy_drives', 0)
            warning_drives = data.get('warning_drives', 0)
            
            line1 = f"Drive Health - {data.get('status', 'Unknown').title()}"
            line2 = f"Healthy: {healthy_drives}/{total_drives}"
            
            if warning_drives > 0:
                line2 += f" | Warnings: {warning_drives}"
        else:
            line1 = "Drive Health"
            line2 = "Drive health data unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)

    async def _update_power_management_display(self, data: Dict[str, Any]) -> None:
        """Update power management display with properly formatted temperature."""
        if data and data.get('status') == 'active':
            line1 = data.get('detailed_info', 'Power management loading...')
            
            ups_connected = data.get('ups_connected', False)
            if ups_connected:
                line2 = "Connected"
            else:
                line2 = "Not Connected"
                
        elif data and data.get('status') == 'api_error':
            line1 = data.get('detailed_info', 'Power Management API error - check connection')
            line2 = "API Error"
            
        elif data and data.get('status') == 'error':
            error_msg = data.get('error', 'Unknown error')
            line1 = f"Power Management Error: {error_msg}"
            line2 = "Error"
            
        else:
            line1 = "Power Management unavailable - NAS not connected"
            line2 = "Unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_cache_performance_display(self, data: Dict[str, Any]) -> None:
        """Update cache performance display with SSD cache data."""
        if data and data.get('status') in ['active', 'disabled']:
            line1 = data.get('detailed_info', 'Cache performance loading...')
            line2 = data.get('short_status', 'Cache Performance')
            
        elif data and data.get('status') == 'api_error':
            line1 = data.get('detailed_info', 'Cache Performance API error - check storage access')
            line2 = "API Error"
            
        elif data and data.get('status') == 'error':
            error_msg = data.get('error', 'Unknown error')
            line1 = f"Cache Performance Error: {error_msg}"
            line2 = "Error"
            
        else:
            line1 = "Cache performance unavailable - NAS not connected"
            line2 = "Unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_package_manager_display(self, data: Dict[str, Any]) -> None:
        """Update package manager display with installed package counts."""
        if data and data.get('status') in ['active', 'healthy']:
            installed_packages = data.get('installed_packages', 0)
            running_packages = data.get('running_packages', 0)
            updates_available = data.get('updates_available', 0)
            package_names = data.get('package_names', [])
            
            major_packages = [name for name in package_names if not name.startswith('SYNO.Core') and not name.startswith('SYNO.API')]
            major_count = len(major_packages)
            
            line1 = f"Installed: {installed_packages} | Running: {running_packages} | Major: {major_count}"
            line2 = "Package Manager"
            
            if updates_available > 0:
                line1 += f" | Updates: {updates_available}"
                
        elif data and data.get('status') == 'api_error':
            line1 = "Package Manager API error - check services access"
            line2 = "API Error"
            
        elif data and data.get('status') == 'no_data':
            line1 = "No package data available from NAS"
            line2 = "No Data"
            
        elif data and data.get('status') == 'error':
            error_msg = data.get('error', 'Unknown error')
            line1 = f"Package Manager Error: {error_msg}"
            line2 = "Error"
            
        else:
            line1 = "Package manager unavailable - NAS not connected"
            line2 = "Unavailable"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _update_user_sessions_display(self, data: Dict[str, Any]) -> None:
        """Update user sessions display."""
        if data:
            active_sessions = data.get('active_sessions', 0)
            logged_in_users = data.get('logged_in_users', 0)
            session_duration = data.get('avg_session_duration', 0)
            
            line1 = f"Active: {active_sessions} | Users: {logged_in_users}"
            line2 = f"User Sessions - {data.get('status', 'Unknown').title()}"
            
            if session_duration > 0:
                hours = session_duration // 60
                mins = session_duration % 60
                line1 += f" | Avg: {hours}h{mins}m"
        else:
            line1 = "Session data unavailable"
            line2 = "User Sessions"
        
        self._entity.attributes[Attributes.MEDIA_TITLE] = line1
        self._entity.attributes[Attributes.MEDIA_ARTIST] = line2

    async def _refresh_display(self) -> None:
        """Force refresh of current display."""
        await self._update_current_data(force_refresh=True)
        self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)

    async def _polling_loop(self) -> None:
        """Main polling loop for data updates - HTCP exact pattern."""
        _LOG.info("Polling loop started.")
        while True:
            try:
                await self._update_current_data()
                self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)
                interval = self._config.polling_intervals.get(self._current_source.lower(), 15)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                _LOG.info("Polling loop cancelled.")
                break
            except Exception as ex:
                _LOG.error(f"Error in polling loop: {ex}")
                await asyncio.sleep(30)

    async def start(self) -> None:
        """Start the system dashboard's polling loop."""
        if not self._polling_task or self._polling_task.done():
            if self._client.connected:
                self._entity.attributes[Attributes.STATE] = States.PLAYING
                self._polling_task = asyncio.create_task(self._polling_loop())

    async def stop(self) -> None:
        """Stop the system dashboard."""
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

    @property
    def entity(self) -> MediaPlayer:
        return self._entity

    @property
    def entity_id(self) -> str:
        return self._entity.id