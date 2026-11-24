"""
Synology system sensor entities.

Values come from the data the device poll already fetches, so the sensors add
no extra requests to the NAS.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from ucapi.sensor import Attributes, DeviceClasses, Options, States
from ucapi_framework import SensorEntity

from uc_intg_synology_system.config import SynologyConfig
from uc_intg_synology_system.device import SynologyDevice

_LOG = logging.getLogger(__name__)


def _number(value: Any, digits: int = 1) -> Optional[float]:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _storage_used_percent(device: SynologyDevice) -> Optional[float]:
    total = device.storage.get("total_size")
    if not total:
        return None
    return _number(100.0 * float(device.storage.get("total_used") or 0) / float(total))


def _kilobytes_per_second(key: str) -> Callable[[SynologyDevice], Optional[float]]:
    def getter(device: SynologyDevice) -> Optional[float]:
        value = _number(device.overview.get(key))
        return None if value is None else round(value / 1024, 1)
    return getter


def _positive(value: Any) -> Optional[float]:
    number = _number(value)
    return number if number else None


def _drive_health(device: SynologyDevice) -> Optional[str]:
    drives = device.drives
    if not drives or "total_drives" not in drives or drives.get("status") in ("error", "unavailable"):
        return None
    return f"{str(drives.get('status', 'unknown')).title()} ({drives.get('healthy_drives', 0)}/{drives['total_drives']})"


def _raid_status(device: SynologyDevice) -> Optional[str]:
    raid = device.raid
    if not raid or raid.get("status") in (None, "error", "unavailable"):
        return None
    level = raid.get("raid_level")
    status = str(raid["status"]).title()
    return f"{status} (RAID {level})" if level and level != "unknown" else status


@dataclass(frozen=True)
class SensorSpec:
    identifier: str
    name: str
    device_class: DeviceClasses
    unit: Optional[str]
    getter: Callable[[SynologyDevice], Any]
    options: Optional[dict] = None


# The first seven identifiers shipped in 1.1.0 and must not change.
CORE_SENSORS = (
    SensorSpec("synology_cpu_usage", "Synology CPU Usage", DeviceClasses.CUSTOM, "%",
               lambda d: _number(d.overview.get("cpu_usage"))),
    SensorSpec("synology_memory_usage", "Synology Memory Usage", DeviceClasses.CUSTOM, "%",
               lambda d: _number(d.overview.get("memory_usage"))),
    SensorSpec("synology_temperature", "Synology Temperature", DeviceClasses.TEMPERATURE, None,
               lambda d: _number(d.overview.get("temperature_c")), {Options.NATIVE_UNIT: "°C"}),
    SensorSpec("synology_storage_used", "Synology Storage Used", DeviceClasses.CUSTOM, "%",
               _storage_used_percent),
    SensorSpec("synology_uptime", "Synology Uptime", DeviceClasses.CUSTOM, None,
               lambda d: d.overview.get("uptime") or None),
    SensorSpec("synology_status", "Synology Status", DeviceClasses.CUSTOM, None,
               lambda d: d.overview.get("status") or None),
    SensorSpec("synology_dsm_version", "Synology DSM Version", DeviceClasses.CUSTOM, None,
               lambda d: d.overview.get("version") or None),
)

EXTRA_SENSORS = (
    SensorSpec("synology_swap_usage", "Synology Swap Usage", DeviceClasses.CUSTOM, "%",
               lambda d: _number(d.overview.get("swap_usage"))),
    SensorSpec("synology_network_download", "Synology Network Download", DeviceClasses.CUSTOM, "KB/s",
               _kilobytes_per_second("network_rx")),
    SensorSpec("synology_network_upload", "Synology Network Upload", DeviceClasses.CUSTOM, "KB/s",
               _kilobytes_per_second("network_tx")),
    SensorSpec("synology_volume_usage", "Synology Volume Usage", DeviceClasses.CUSTOM, "%",
               lambda d: _number(d.volumes.get("average_usage")) if d.volumes.get("volume_count") else None),
    SensorSpec("synology_volume_status", "Synology Volume Status", DeviceClasses.CUSTOM, None,
               lambda d: str(d.volumes["status"]).title()
               if d.volumes.get("volume_count") and d.volumes.get("status") != "error" else None),
    SensorSpec("synology_disk_temperature", "Synology Disk Temperature", DeviceClasses.TEMPERATURE, None,
               lambda d: _positive(d.hardware.get("max_drive_temp")), {Options.NATIVE_UNIT: "°C"}),
    SensorSpec("synology_drive_health", "Synology Drive Health", DeviceClasses.CUSTOM, None,
               _drive_health),
    SensorSpec("synology_raid_status", "Synology RAID Status", DeviceClasses.CUSTOM, None,
               _raid_status),
    SensorSpec("synology_services_running", "Synology Services Running", DeviceClasses.CUSTOM, None,
               lambda d: d.services.get("running_count") if d.services.get("total_count") else None),
)

SURVEILLANCE_SENSORS = (
    SensorSpec("synology_cameras", "Synology Cameras", DeviceClasses.CUSTOM, None,
               lambda d: d.surveillance.get("camera_count") if d.surveillance.get("status") == "active" else None),
    SensorSpec("synology_cameras_recording", "Synology Cameras Recording", DeviceClasses.CUSTOM, None,
               lambda d: d.surveillance.get("recording_count") if d.surveillance.get("status") == "active" else None),
)


class SynologySensor(SensorEntity):
    """A single Synology sensor driven by a ``SensorSpec``."""

    def __init__(self, spec: SensorSpec, device: SynologyDevice) -> None:
        self._spec = spec
        self._device = device
        attributes = {Attributes.STATE: States.UNKNOWN, Attributes.VALUE: ""}
        if spec.unit:
            attributes[Attributes.UNIT] = spec.unit
        super().__init__(
            spec.identifier,
            spec.name,
            [],
            attributes,
            device_class=spec.device_class,
            options=spec.options,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if self._device.state == "UNAVAILABLE":
            self.update({Attributes.STATE: States.UNAVAILABLE})
            return

        try:
            value = self._spec.getter(self._device)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOG.debug("Sensor %s: cannot read value: %s", self._spec.identifier, err)
            value = None

        if value is None:
            self.update({Attributes.STATE: States.UNKNOWN, Attributes.VALUE: ""})
            return

        attributes = {Attributes.STATE: States.ON, Attributes.VALUE: value}
        if self._spec.unit:
            attributes[Attributes.UNIT] = self._spec.unit
        self.update(attributes)


def create_sensors(config: SynologyConfig, device: SynologyDevice) -> List[SynologySensor]:
    specs = list(CORE_SENSORS) + list(EXTRA_SENSORS)
    if "SurveillanceStation" in config.available_packages:
        specs += list(SURVEILLANCE_SENSORS)
    return [SynologySensor(spec, device) for spec in specs]
