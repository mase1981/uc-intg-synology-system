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
from typing import Any, Dict, List, Optional

from ucapi import StatusCodes
from ucapi.media_player import Attributes, Commands, Features, States
from ucapi_framework import MediaPlayerEntity

from uc_intg_synology_system.config import SynologyConfig
from uc_intg_synology_system.device import SynologyDevice
from uc_intg_synology_system.helpers import create_two_line_display, safe_get_nested_value

_LOG = logging.getLogger(__name__)

REFRESH_INTERVAL = 20
DISCOVERY_RETRY = 60

# Commands to suppress to prevent red error messages
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


class SynologyCameraMonitor(MediaPlayerEntity):
    """Synology Surveillance Station camera monitor."""

    def __init__(self, config: SynologyConfig, device: SynologyDevice):
        self._device = device
        self._config = config
        self._current_camera = "All Cameras"
        self._cameras = {}
        self._camera_id_to_name = {}
        self._icon_cache = {}
        self._snapshot_cache = {}
        self._powered = True
        self._refresh_task: Optional[asyncio.Task] = None
        self._last_refresh = 0.0
        self._last_discovery = 0.0
        self._view: Dict[str, Any] = {
            Attributes.MEDIA_TITLE: "Synology Camera Monitor",
            Attributes.MEDIA_ARTIST: "Discovering cameras...",
            Attributes.MEDIA_IMAGE_URL: self._get_camera_icon_base64("surveillance_status.png"),
        }

        self.snapshot_quality = "MEDIUM"

        features = [
            Features.ON_OFF,
            Features.SELECT_SOURCE,
            Features.VOLUME_UP_DOWN,
            Features.MEDIA_TITLE,
            Features.MEDIA_ARTIST,
            Features.MEDIA_IMAGE_URL,
        ]
        super().__init__(
            "synology_camera_monitor",
            "Synology Camera Monitor",
            features,
            {
                Attributes.STATE: States.UNKNOWN,
                Attributes.SOURCE: "",
                Attributes.SOURCE_LIST: [],
                Attributes.MEDIA_TITLE: "",
                Attributes.MEDIA_ARTIST: "",
                Attributes.MEDIA_IMAGE_URL: "",
                Attributes.VOLUME: 0,
            },
            cmd_handler=self.handle_command,
        )
        self.subscribe_to_device(device)

    @property
    def _client(self):
        return self._device.client

    async def sync_state(self) -> None:
        if self._device.state == "UNAVAILABLE":
            self.update({Attributes.STATE: States.UNAVAILABLE})
            return
        self._schedule_refresh()
        self._push()

    def _push(self) -> None:
        discovery_done = bool(self._cameras) or self._last_discovery > 0
        if discovery_done and not self._cameras:
            self.update({
                Attributes.STATE: States.UNAVAILABLE,
                Attributes.MEDIA_TITLE: "Surveillance Station",
                Attributes.MEDIA_ARTIST: "No cameras configured",
            })
            return

        powered = self._powered
        self.update({
            Attributes.STATE: States.ON if powered else States.OFF,
            Attributes.SOURCE: self._current_camera,
            Attributes.SOURCE_LIST: self._get_camera_sources(),
            Attributes.MEDIA_TITLE: self._view.get(Attributes.MEDIA_TITLE, ""),
            Attributes.MEDIA_ARTIST: self._view.get(Attributes.MEDIA_ARTIST, ""),
            Attributes.MEDIA_IMAGE_URL: self._view.get(Attributes.MEDIA_IMAGE_URL, "") if powered else "",
            Attributes.VOLUME: 50,
        })

    def _schedule_refresh(self) -> None:
        """Refresh in the background; sync_state never waits on the NAS."""
        if not self._powered or (self._refresh_task and not self._refresh_task.done()):
            return
        now = time.monotonic()
        if self._cameras:
            if now - self._last_refresh < REFRESH_INTERVAL:
                return
        elif self._last_discovery and now - self._last_discovery < DISCOVERY_RETRY:
            return
        self._refresh_task = asyncio.create_task(self._refresh_and_push())

    async def _refresh_and_push(self) -> None:
        try:
            if not self._cameras:
                await self.initialize_cameras()
                self._last_discovery = time.monotonic()
            if self._cameras:
                await self._update_camera_status()
                await self._update_camera_display()
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error(f"Error refreshing cameras: {ex}")
        finally:
            self._last_refresh = time.monotonic()
        self._push()

    async def _discover_cameras(self) -> Dict[str, Dict[str, Any]]:
        """Camera discovery using working method."""
        if not self._client._surveillance:
            _LOG.warning("Surveillance Station not available")
            return {}
        
        try:
            cameras_data = await self._client._call(self._client._surveillance.camera_list)
            
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
                    snapshot_data = await self._client._call(self._client._surveillance.get_snapshot, camera_id)
                    
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

    async def handle_command(self, entity_arg, cmd_id: str, params: Dict[str, Any] = None) -> StatusCodes:
        """Handle camera media player commands."""
        try:
            if cmd_id == Commands.SELECT_SOURCE:
                source = params.get("source") if params else None
                if source:
                    await self._handle_camera_selection(source)
                    return StatusCodes.OK
                return StatusCodes.BAD_REQUEST
            elif cmd_id == Commands.ON:
                self._powered = True
                await self._refresh_camera_display()
                return StatusCodes.OK
            elif cmd_id == Commands.OFF:
                self._powered = False
                self._push()
                return StatusCodes.OK
            elif cmd_id in (Commands.VOLUME_UP, Commands.VOLUME_DOWN):
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
        if camera_source != self._current_camera and camera_source in self._get_camera_sources():
            _LOG.info(f"Switching to camera source: {camera_source}")
            self._current_camera = camera_source
            await self._update_camera_display()
            self._push()

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
        
        self._view[Attributes.MEDIA_TITLE], self._view[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)
        self._view[Attributes.MEDIA_IMAGE_URL] = self._get_status_icon("All Cameras")

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
        
        self._view[Attributes.MEDIA_TITLE], self._view[Attributes.MEDIA_ARTIST] = create_two_line_display(line1, line2)
        
        # HOME ASSISTANT: Try snapshot for online cameras
        if status == 1 and enabled:
            snapshot_image = await self._get_camera_snapshot_home_assistant_method(camera_name)
            if snapshot_image:
                self._view[Attributes.MEDIA_IMAGE_URL] = snapshot_image
                return
        
        # Fallback to status icon
        self._view[Attributes.MEDIA_IMAGE_URL] = self._get_status_icon(camera_name)

    async def _update_camera_status(self) -> None:
        """Update camera status."""
        if not self._client._surveillance:
            return
        
        try:
            cameras_data = await self._client._call(self._client._surveillance.camera_list)
            
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

    async def _refresh_camera_display(self) -> None:
        """Refresh current camera display."""
        if not self._cameras:
            await self.initialize_cameras()
            self._last_discovery = time.monotonic()
        await self._update_camera_status()
        await self._update_camera_display()
        self._last_refresh = time.monotonic()
        self._push()

    async def initialize_cameras(self) -> bool:
        """Initialize camera discovery."""
        if not await self._client.ensure_surveillance():
            return False

        self._cameras = await self._discover_cameras()
        if not self._cameras:
            return False

        if self._current_camera not in self._get_camera_sources():
            self._current_camera = "All Cameras"
        await self._update_camera_display()
        _LOG.info(f"Initialized {len(self._cameras)} cameras")
        return True

