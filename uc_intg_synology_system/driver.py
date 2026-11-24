"""
Integration driver for the Synology System integration.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from typing import Optional

from ucapi_framework import BaseIntegrationDriver

from uc_intg_synology_system.camera_media_player import SynologyCameraMonitor
from uc_intg_synology_system.config import DEVICE_ID, SynologyConfig
from uc_intg_synology_system.device import SynologyDevice
from uc_intg_synology_system.media_player import SynologySystemDashboard
from uc_intg_synology_system.remote import SynologySystemRemote
from uc_intg_synology_system.sensor import create_sensors

# Changing the driver_id would make the Remote treat an upgrade as a new integration.
DRIVER_ID = "uc_synology_system"


def _create_camera_monitor(config: SynologyConfig, device: SynologyDevice) -> list:
    if "SurveillanceStation" in config.available_packages:
        return [SynologyCameraMonitor(config, device)]
    return []


class SynologyDriver(BaseIntegrationDriver[SynologyDevice, SynologyConfig]):
    """Synology System integration driver."""

    def __init__(self):
        super().__init__(
            device_class=SynologyDevice,
            entity_classes=[
                create_sensors,
                SynologySystemDashboard,
                SynologySystemRemote,
                _create_camera_monitor,
            ],
            driver_id=DRIVER_ID,
        )

    # Entity ids shipped as "synology_*" (no separator) and are referenced by users'
    # pages and activities, so they are kept. The integration manages a single NAS.
    def device_from_entity_id(self, entity_id: str) -> Optional[str]:
        if entity_id and entity_id.startswith("synology_"):
            return DEVICE_ID
        return None

    def sub_device_from_entity_id(self, entity_id: str) -> Optional[str]:
        return None
