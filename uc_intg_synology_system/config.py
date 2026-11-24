"""
Configuration for the Synology System integration.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict

from ucapi_framework import BaseConfigManager

from uc_intg_synology_system.helpers import SynologyConstants

_LOG = logging.getLogger(__name__)

DEVICE_ID = "synology_system"

_DEFAULT_FEATURES = {
    "docker_monitoring": True,
    "security_monitoring": True,
    "network_monitoring": True,
    "storage_monitoring": True,
    "ups_monitoring": True,
    "surveillance_monitoring": False,
    "enhanced_monitoring": True,
}


def _default_features() -> Dict[str, bool]:
    return dict(_DEFAULT_FEATURES)


def _default_polling() -> Dict[str, int]:
    return dict(SynologyConstants.DEFAULT_POLLING)


@dataclass
class SynologyConfig:
    """Synology NAS connection settings. New fields must always have defaults."""

    identifier: str = DEVICE_ID
    name: str = "Synology System"
    host: str = ""
    port: int = 5001
    username: str = ""
    password: str = ""
    use_https: bool = True
    temperature_unit: str = "celsius"
    dsm_version: int = 7
    device_token: str = ""
    available_packages: Dict[str, Any] = field(default_factory=dict)
    enabled_features: Dict[str, bool] = field(default_factory=_default_features)
    polling_intervals: Dict[str, int] = field(default_factory=_default_polling)

    def is_configured(self) -> bool:
        return bool(self.host and self.port and self.username and self.password)

    def get_enabled_sources(self) -> Dict[str, str]:
        """Sources offered by the monitoring dashboard media player."""
        sources = {
            "SYSTEM_OVERVIEW": "System Overview",
            "STORAGE_STATUS": "Storage Status",
        }

        features = self.enabled_features
        packages = self.available_packages

        if features.get("network_monitoring", True):
            sources["NETWORK_STATS"] = "Network Statistics"
        if features.get("security_monitoring", True):
            sources["SECURITY_STATUS"] = "Security Status"

        sources["SERVICES_STATUS"] = "Services Status"

        if features.get("enhanced_monitoring", True):
            sources.update({
                "THERMAL_STATUS": "Temperature Monitor",
                "CACHE_STATUS": "SSD Cache",
                "RAID_STATUS": "RAID Health",
                "VOLUME_STATUS": "Volume Usage",
                "UPS_STATUS": "UPS Monitor",
                "HARDWARE_MONITOR": "Hardware Monitor",
                "DRIVE_HEALTH": "Drive Health",
                "POWER_MANAGEMENT": "Power Management",
                "CACHE_PERFORMANCE": "Cache Performance",
                "PACKAGE_MANAGER": "Package Manager",
                "USER_SESSIONS": "User Sessions",
            })

        if features.get("surveillance_monitoring", True) and "SurveillanceStation" in packages:
            sources["SURVEILLANCE_STATUS"] = "Surveillance Station"

        if features.get("docker_monitoring", True) and "Docker" in packages:
            sources["DOCKER_STATUS"] = "Docker Containers"

        return sources


class SynologyConfigManager(BaseConfigManager[SynologyConfig]):
    """Stores the Synology device configuration."""


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    if value is None:
        return default
    return bool(value)


def migrate_legacy_config(config_dir: str) -> bool:
    """Convert the pre-1.2.0 ``{"synology_config": {...}}`` file to the framework format.

    Idempotent: a file that is already a list of devices is left untouched.
    The original is kept as ``config.json.legacy`` the first time it is converted.
    """
    config_file = os.path.join(config_dir, "config.json")
    if not os.path.exists(config_file):
        return False

    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as err:
        _LOG.error("Cannot read %s for migration: %s", config_file, err)
        return False

    if not isinstance(data, dict) or "synology_config" not in data:
        return False

    legacy = data.get("synology_config") or {}
    devices = []
    if legacy.get("host") and legacy.get("username") and legacy.get("password"):
        try:
            port = int(legacy.get("port", 5001))
        except (TypeError, ValueError):
            port = 5001
        device = SynologyConfig(
            host=str(legacy.get("host", "")).strip(),
            port=port,
            username=str(legacy.get("username", "")).strip(),
            password=str(legacy.get("password", "")),
            use_https=_as_bool(legacy.get("use_https"), True),
            temperature_unit=str(legacy.get("temperature_unit", "celsius")).lower(),
            dsm_version=int(legacy.get("dsm_version", 7) or 7),
            available_packages=dict(legacy.get("available_packages") or {}),
            enabled_features={**_DEFAULT_FEATURES, **(legacy.get("enabled_features") or {})},
            polling_intervals={**SynologyConstants.DEFAULT_POLLING, **(legacy.get("polling_intervals") or {})},
        )
        devices.append(device.__dict__)

    backup_file = config_file + ".legacy"
    temp_file = config_file + ".tmp"
    try:
        if not os.path.exists(backup_file):
            with open(backup_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
        with open(temp_file, "w", encoding="utf-8") as handle:
            json.dump(devices, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_file, config_file)
    except OSError as err:
        _LOG.error("Cannot write migrated configuration: %s", err)
        return False

    _LOG.info("Migrated legacy configuration (%d device)", len(devices))
    return True
