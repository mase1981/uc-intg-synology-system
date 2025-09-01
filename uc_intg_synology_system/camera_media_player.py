"""
Camera Media Player entity - not implemeneted due to large complex versions of cameras. only worked on Reolink Doorbell

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import base64
import logging
import os
import time
from typing import Any, Dict, List

import ucapi
from ucapi import StatusCodes
from ucapi.media_player import Attributes, Commands, Features, MediaPlayer, States

from uc_intg_synology_system.client import SynologySystemClient
from uc_intg_synology_system.config import SynologyConfig
from uc_intg_synology_system.helpers import create_two_line_display, safe_get_nested_value

_LOG = logging.getLogger(__name__)

# CRITICAL: Commands to suppress to prevent red error messages
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


class SynologyCameraMonitor:
    """Synology camera monitoring using HOME ASSISTANT exact method."""

    def __init__(self, api: ucapi.IntegrationAPI, client: SynologySystemClient, config: SynologyConfig):
        """Initialize camera monitor."""
        self._api = api
        self._client = client
        self._config = config
        self._current_camera = "All Cameras"
        self._cameras = {}
        self._camera_id_to_name = {}
        self._polling_task = None
        self._icon_cache = {}
        self._snapshot_cache = {}
        
        self.snapshot_quality = "MEDIUM"
        
        _LOG.info("Initializing camera monitor with HOME ASSISTANT method")
        
        self._entity = self._create_camera_media_player()

    async def _discover_cameras(self) -> Dict[str, Dict[str, Any]]:
        """Camera discovery using working method."""
        if not self._client._surveillance:
            _LOG.warning("Surveillance Station not available")
            return {}
        
        try:
            cameras_data = self._client._surveillance.camera_list()
            
            if not cameras_data or not cameras_data.get('success', False):
                _LOG.warning("Camera list API call unsuccessful")
                return {}
            
            cameras_raw = safe_get_nested_value(cameras_data, ['data', 'cameras'], [])
            if not cameras_raw:
                _LOG.warning("No cameras found in API response")
                return {}
            
            camera_dict = {}
            self._camera_id_to_name = {}
            
            for camera in cameras_raw:
                camera_id = str(camera.get('id', ''))
                camera_name = camera.get('newName', f'Camera {camera_id}')
                if not camera_name or camera_name.strip() == '':
                    camera_name = f'Camera {camera_id}'
                
                camera_status = camera.get('status', 0)
                record_schedule = camera.get('recordSchedule', '')
                is_recording = len(record_schedule) > 100 and '1' in record_schedule
                camera_ip = camera.get('ip', '')
                
                camera_dict[camera_name] = {
                    "id": camera_id,
                    "name": camera_name,
                    "enabled": True,
                    "status": camera_status,
                    "recording": is_recording,
                    "ip": camera_ip,
                    "model": camera.get('model', 'Unknown')
                }
                
                self._camera_id_to_name[camera_id] = camera_name
                
                _LOG.info(f"Found camera: {camera_name} (ID: {camera_id}) - Status: {camera_status}")
            
            _LOG.info(f"Successfully discovered {len(camera_dict)} cameras")
            return camera_dict
            
        except Exception as ex:
            _LOG.error(f"Error discovering cameras: {ex}")
            return {}

    async def _get_camera_snapshot_home_assistant_method(self, camera_name: str) -> str:
        camera_info = self._cameras.get(camera_name, {})
        camera_id = camera_info.get('id', '')
        
        if not camera_id:
            return ""
        
        # Check cache first (30 second cache)
        cache_key = f"snapshot_{camera_id}"
        cached_snapshot = self._snapshot_cache.get(cache_key, {})
        current_time = time.time()
        
        if cached_snapshot and (current_time - cached_snapshot.get('timestamp', 0)) < 30:
            return cached_snapshot.get('data', '')
        
        try:
            if hasattr(self._client._surveillance, 'get_camera_image'):
                try:
                    camera_id_int = int(camera_id)
                    image_bytes = await self._client._surveillance.get_camera_image(
                        camera_id_int, self.snapshot_quality
                    )
                    
                    if isinstance(image_bytes, bytes) and len(image_bytes) > 100:
                        base64_data = base64.b64encode(image_bytes).decode('utf-8')
                        data_url = f"data:image/jpeg;base64,{base64_data}"
                        
                        self._snapshot_cache[cache_key] = {
                            'data': data_url,
                            'timestamp': current_time
                        }
                        
                        _LOG.info(f"✅ HOME ASSISTANT method worked for {camera_name}: {len(image_bytes)} bytes")
                        return data_url
                        
                except Exception as ha_ex:
                    _LOG.debug(f"HOME ASSISTANT get_camera_image failed for {camera_name}: {ha_ex}")
            
            if hasattr(self._client._surveillance, 'get_snapshot'):
                try:
                    snapshot_data = self._client._surveillance.get_snapshot(camera_id)
                    
                    if isinstance(snapshot_data, bytes) and len(snapshot_data) > 100:
                        base64_data = base64.b64encode(snapshot_data).decode('utf-8')
                        data_url = f"data:image/jpeg;base64,{base64_data}"
                        
                        self._snapshot_cache[cache_key] = {
                            'data': data_url,
                            'timestamp': current_time
                        }
                        
                        _LOG.info(f"✅ Fallback get_snapshot worked for {camera_name}: {len(snapshot_data)} bytes")
                        return data_url
                        
                except Exception as fallback_ex:
                    _LOG.debug(f"Fallback get_snapshot failed for {camera_name}: {fallback_ex}")
            
            _LOG.debug(f"No working snapshot method for camera {camera_name}")
            return ""
            
        except Exception as ex:
            _LOG.error(f"Error getting snapshot for camera {camera_name}: {ex}")
            return ""

    def _get_camera_sources(self) -> List[str]:
        """Get camera sources list."""
        sources = ["All Cameras"]
        for camera_name in sorted(self._cameras.keys()):
            if camera_name != "All Cameras":
                sources.append(camera_name)
        return sources

    def _get_camera_icon_base64(self, icon_filename: str) -> str:
        """Get base64 encoded camera icon."""
        if icon_filename in self._icon_cache:
            return self._icon_cache[icon_filename]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(script_dir, "icons")
        icon_path = os.path.join(icon_dir, icon_filename)
        
        fallback_icons = ["surveillance_status.png", "synology_logo.png"]
        
        if not os.path.exists(icon_path):
            for fallback in fallback_icons:
                icon_path = os.path.join(icon_dir, fallback)
                if os.path.exists(icon_path):
                    break
            else:
                return ""

        try:
            with open(icon_path, 'rb') as f:
                icon_data = f.read()
                base64_data = base64.b64encode(icon_data).decode('utf-8')
                data_url = f"data:image/png;base64,{base64_data}"
                self._icon_cache[icon_filename] = data_url
                return data_url
        except Exception as e:
            _LOG.error(f"Failed to read camera icon {icon_path}: {e}")
            return ""

    def _get_status_icon(self, camera_name: str) -> str:
        """Get appropriate status icon for camera."""
        if camera_name == "All Cameras":
            return self._get_camera_icon_base64("surveillance_status.png")
        
        camera_info = self._cameras.get(camera_name, {})
        status = camera_info.get('status', 0)
        recording = camera_info.get('recording', False)
        
        if status == 1 and recording:
            return self._get_camera_icon_base64("camera_recording.png")
        elif status == 1:
            return self._get_camera_icon_base64("camera_online.png")
        else:
            return self._get_camera_icon_base64("camera_offline.png")

    def _create_camera_media_player(self) -> MediaPlayer:
        """Create camera media player entity."""
        features = [
            Features.ON_OFF,
            Features.SELECT_SOURCE,
            Features.VOLUME_UP_DOWN,
            Features.MEDIA_TITLE,
            Features.MEDIA_ARTIST,
            Features.MEDIA_IMAGE_URL,
        ]
        
        initial_icon = self._get_camera_icon_base64("surveillance_status.png")
        
        attributes = {
            Attributes.STATE: States.PAUSED,
            Attributes.SOURCE: self._current_camera,
            Attributes.SOURCE_LIST: ["All Cameras"],
            Attributes.MEDIA_TITLE: "Synology Camera Monitor",
            Attributes.MEDIA_ARTIST: "Discovering cameras...",
            Attributes.MEDIA_IMAGE_URL: initial_icon,
            Attributes.VOLUME: 50
        }
        
        return MediaPlayer(
            identifier="synology_camera_monitor",
            name="Synology Camera Monitor",
            features=features,
            attributes=attributes,
            cmd_handler=self.handle_command
        )

    async def handle_command(self, entity_arg: ucapi.entity.Entity, cmd_id: str, params: Dict[str, Any] = None) -> StatusCodes:
        """Handle camera media player commands."""
        try:
            if cmd_id == Commands.SELECT_SOURCE:
                source = params.get("source") if params else None
                if source:
                    await self._handle_camera_selection(source)
                    return StatusCodes.OK
                return StatusCodes.BAD_REQUEST
            elif cmd_id == Commands.ON:
                await self._handle_camera_on()
                return StatusCodes.OK
            elif cmd_id == Commands.OFF:
                await self._handle_camera_off()
                return StatusCodes.OK
            elif cmd_id == Commands.VOLUME_UP:
                await self._refresh_camera_display()
                return StatusCodes.OK
            elif cmd_id == Commands.VOLUME_DOWN:
                await self._refresh_camera_display()
                return StatusCodes.OK
            elif cmd_id in SUPPRESSED_COMMANDS:
                return StatusCodes.OK
            else:
                return StatusCodes.NOT_IMPLEMENTED
                
        except Exception as ex:
            _LOG.error(f"Error handling camera command '{cmd_id}': {ex}")
            return StatusCodes.SERVER_ERROR

    async def _handle_camera_selection(self, camera_source: str) -> None:
        """Handle camera source selection."""
        if camera_source != self._current_camera:
            _LOG.info(f"Switching to camera source: {camera_source}")
            self._current_camera = camera_source
            self._entity.attributes[Attributes.SOURCE] = camera_source
            await self._update_camera_display()
            self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)

    async def _handle_camera_on(self) -> None:
        """Start camera monitoring."""
        self._entity.attributes[Attributes.STATE] = States.PLAYING
        await self.start()
        self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)

    async def _handle_camera_off(self) -> None:
        """Stop camera monitoring."""
        await self.stop()
        self._entity.attributes[Attributes.STATE] = States.PAUSED
        self._api.configured_entities.update_attributes(self.entity_id, {Attributes.STATE: States.PAUSED})

    async def _update_camera_display(self) -> None:
        """Update camera display based on current selection."""
        if self._current_camera == "All Cameras":
            await self._update_all_cameras_display()
        else:
            await self._update_single_camera_display(self._current_camera)

    async def _update_all_cameras_display(self) -> None:
        """Update display showing all cameras overview."""
        total_cameras = len(self._cameras)
        recording_cameras = sum(1 for cam in self._cameras.values() if cam.get('recording', False))
        online_cameras = sum(1 for cam in self._cameras.values() if cam.get('status', 0) == 1)
        
        line1 = f"Surveillance - {total_cameras} cameras"
        line2 = f"Online: {online_cameras} | Recording: {recording_cameras}"
        
        self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)
        self._entity.attributes[Attributes.MEDIA_IMAGE_URL] = self._get_status_icon("All Cameras")

    async def _update_single_camera_display(self, camera_name: str) -> None:
        """Update display for single camera with HOME ASSISTANT snapshot method."""
        camera_info = self._cameras.get(camera_name, {})
        
        if not camera_info:
            return
        
        camera_id = camera_info.get('id', '')
        recording = camera_info.get('recording', False)
        status = camera_info.get('status', 0)
        enabled = camera_info.get('enabled', False)
        camera_ip = camera_info.get('ip', '')
        
        # Status text
        status_text = "Online" if status == 1 else "Offline"
        recording_text = "Recording" if recording else "Idle"
        
        line1 = f"{camera_name} - {status_text}"
        line2 = f"{recording_text} | IP: {camera_ip}"
        
        self._entity.attributes[Attributes.MEDIA_TITLE], self._entity.attributes[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)
        
        # HOME ASSISTANT: Try snapshot for online cameras
        if status == 1 and enabled:
            snapshot_image = await self._get_camera_snapshot_home_assistant_method(camera_name)
            if snapshot_image:
                self._entity.attributes[Attributes.MEDIA_IMAGE_URL] = snapshot_image
                return
        
        # Fallback to status icon
        self._entity.attributes[Attributes.MEDIA_IMAGE_URL] = self._get_status_icon(camera_name)

    async def _refresh_camera_display(self) -> None:
        """Refresh current camera display."""
        await self._update_camera_status()
        await self._update_camera_display()
        self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)

    async def _update_camera_status(self) -> None:
        """Update camera status."""
        if not self._client._surveillance:
            return
        
        try:
            cameras_data = self._client._surveillance.camera_list()
            
            if cameras_data and cameras_data.get('success', False):
                cameras_raw = safe_get_nested_value(cameras_data, ['data', 'cameras'], [])
                
                for camera in cameras_raw:
                    camera_id = str(camera.get('id', ''))
                    camera_name = camera.get('newName', f'Camera {camera_id}')
                    
                    if camera_name in self._cameras:
                        camera_status = camera.get('status', 0)
                        record_schedule = camera.get('recordSchedule', '')
                        is_recording = len(record_schedule) > 100 and '1' in record_schedule
                        
                        self._cameras[camera_name].update({
                            "status": camera_status,
                            "recording": is_recording
                        })
                        
        except Exception as ex:
            _LOG.error(f"Error updating camera status: {ex}")

    async def _camera_polling_loop(self) -> None:
        """Camera monitoring polling loop."""
        _LOG.info("Camera polling loop started")
        while True:
            try:
                await self._update_camera_status()
                await self._update_camera_display()
                self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)
                await asyncio.sleep(20)
            except asyncio.CancelledError:
                _LOG.info("Camera polling loop cancelled")
                break
            except Exception as ex:
                _LOG.error(f"Error in camera polling: {ex}")
                await asyncio.sleep(30)

    async def initialize_cameras(self) -> bool:
        """Initialize camera discovery."""
        self._cameras = await self._discover_cameras()
        
        if not self._cameras:
            return False
        
        camera_sources = self._get_camera_sources()
        self._entity.attributes[Attributes.SOURCE_LIST] = camera_sources
        
        _LOG.info(f"Initialized {len(self._cameras)} cameras")
        return True

    async def push_initial_state(self) -> None:
        """Initialize cameras and push initial state."""
        try:
            if await self.initialize_cameras():
                await self._update_camera_display()
                self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)
                await self.start()
            else:
                self._entity.attributes[Attributes.MEDIA_TITLE] = "Surveillance Station"
                self._entity.attributes[Attributes.MEDIA_ARTIST] = "No cameras configured"
                self._entity.attributes[Attributes.STATE] = States.UNAVAILABLE
                self._api.configured_entities.update_attributes(self.entity_id, self._entity.attributes)
                
        except Exception as ex:
            _LOG.error(f"Error pushing initial camera state: {ex}")

    async def start(self) -> None:
        """Start camera monitoring."""
        if not self._polling_task or self._polling_task.done():
            if self._client.connected and self._cameras:
                self._entity.attributes[Attributes.STATE] = States.PLAYING
                self._polling_task = asyncio.create_task(self._camera_polling_loop())

    async def stop(self) -> None:
        """Stop camera monitoring."""
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

    @property
    def has_cameras(self) -> bool:
        return len(self._cameras) > 0