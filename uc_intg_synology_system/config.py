"""
Configuration management for Synology System integration.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from uc_intg_synology_system.helpers import SynologyConstants, validate_ip_address, validate_port

_LOG = logging.getLogger(__name__)


class SynologyConfig:
    """Configuration management for Synology integration."""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        :param config_file: Path to configuration file
        """
        self._config_file = config_file or "config.json"
        self._config_data = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r', encoding='utf-8') as file:
                    self._config_data = json.load(file)
                    _LOG.info(f"Configuration loaded from {self._config_file}")
            else:
                _LOG.info(f"Configuration file {self._config_file} not found, using defaults")
                self._create_default_config()
        except Exception as ex:
            _LOG.error(f"Error loading configuration: {ex}")
            self._create_default_config()

    def _create_default_config(self) -> None:
        """Create default configuration structure."""
        self._config_data = {
            "synology_config": {
                "host": "",
                "port": 5001,
                "username": "",
                "password": "",
                "use_https": True,
                "temperature_unit": "celsius",
                "otp_enabled": False,
                "dsm_version": 7,
                "polling_intervals": SynologyConstants.DEFAULT_POLLING.copy(),
                "enabled_features": {
                    "docker_monitoring": True,
                    "security_monitoring": True,
                    "network_monitoring": True,
                    "storage_monitoring": True,
                    "ups_monitoring": True,
                    "surveillance_monitoring": False,
                    "enhanced_monitoring": True  # Enable all enhanced features
                },
                "available_packages": {}
            }
        }

    def save_config(self) -> bool:
        """Save configuration to file."""
        try:
            config_path = Path(self._config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._config_file, 'w', encoding='utf-8') as file:
                json.dump(self._config_data, file, indent=2, ensure_ascii=False)
            
            _LOG.info(f"Configuration saved to {self._config_file}")
            return True
        except Exception as ex:
            _LOG.error(f"Error saving configuration: {ex}")
            return False

    def update_from_setup_data(self, setup_data: Dict[str, Any]) -> bool:
        """
        Update configuration from setup data.
        
        :param setup_data: Setup data from Remote Two/3
        :return: True if configuration was updated successfully
        """
        try:
            synology_config = self._config_data.get("synology_config", {})
            
            required_fields = ["host", "port", "username", "password"]
            for field in required_fields:
                if field not in setup_data or not setup_data[field]:
                    _LOG.error(f"Missing required field: {field}")
                    return False
            
            if not validate_ip_address(setup_data["host"]):
                _LOG.error(f"Invalid IP address: {setup_data['host']}")
                return False
            
            if not validate_port(int(setup_data["port"])):
                _LOG.error(f"Invalid port: {setup_data['port']}")
                return False
            
            synology_config.update({
                "host": setup_data["host"].strip(),
                "port": int(setup_data["port"]),
                "username": setup_data["username"].strip(),
                "password": setup_data["password"],
                "use_https": setup_data.get("use_https", True),
                "temperature_unit": setup_data.get("temperature_unit", "celsius").lower(),
                "otp_enabled": bool(setup_data.get("otp_code", "").strip())
            })
            
            self._config_data["synology_config"] = synology_config
            _LOG.info("Configuration updated from setup data")
            return self.save_config()
            
        except Exception as ex:
            _LOG.error(f"Error updating configuration from setup data: {ex}")
            return False

    def update_available_packages(self, packages: Dict[str, Any]) -> None:
        """
        Update available packages information.
        
        :param packages: Dictionary of available packages
        """
        try:
            synology_config = self._config_data.get("synology_config", {})
            synology_config["available_packages"] = packages
            
            enabled_features = synology_config.get("enabled_features", {})
            
            if "Docker" in packages:
                enabled_features["docker_monitoring"] = True
                _LOG.info("Docker package detected - enabling Docker monitoring")
            if "SurveillanceStation" in packages:
                enabled_features["surveillance_monitoring"] = True
                _LOG.info("Surveillance Station detected - enabling surveillance monitoring")
            
            synology_config["enabled_features"] = enabled_features
            self._config_data["synology_config"] = synology_config
            
            _LOG.info(f"Updated available packages: {list(packages.keys())}")
            self.save_config()
            
        except Exception as ex:
            _LOG.error(f"Error updating available packages: {ex}")

    def is_configured(self) -> bool:
        """Check if basic configuration is complete."""
        synology_config = self._config_data.get("synology_config", {})
        required_fields = ["host", "port", "username", "password"]
        
        for field in required_fields:
            if not synology_config.get(field):
                return False
        
        return True

    def get_connection_params(self) -> Dict[str, Any]:
        synology_config = self._config_data.get("synology_config", {})
        return {
            "host": synology_config.get("host", ""),
            "port": synology_config.get("port", 5001),
            "username": synology_config.get("username", ""),
            "password": synology_config.get("password", ""),
            "secure": synology_config.get("use_https", True),
            "dsm_version": synology_config.get("dsm_version", 7),
            "otp_code": None  # CRITICAL: Never store OTP codes
        }

    @property
    def host(self) -> str:
        return self._config_data.get("synology_config", {}).get("host", "")

    @property
    def port(self) -> int:
        return self._config_data.get("synology_config", {}).get("port", 5001)

    @property
    def username(self) -> str:
        return self._config_data.get("synology_config", {}).get("username", "")

    @property
    def use_https(self) -> bool:
        return self._config_data.get("synology_config", {}).get("use_https", True)

    @property
    def temperature_unit(self) -> str:
        return self._config_data.get("synology_config", {}).get("temperature_unit", "celsius")

    @property
    def polling_intervals(self) -> Dict[str, int]:
        return self._config_data.get("synology_config", {}).get("polling_intervals", SynologyConstants.DEFAULT_POLLING)

    @property
    def enabled_features(self) -> Dict[str, bool]:
        return self._config_data.get("synology_config", {}).get("enabled_features", {})

    @property
    def available_packages(self) -> Dict[str, Any]:
        return self._config_data.get("synology_config", {}).get("available_packages", {})

    def get_enabled_sources(self) -> Dict[str, str]:
        """Get enabled sources for the monitoring dashboard."""
        sources = {
            # Core system monitoring (always available)
            "SYSTEM_OVERVIEW": "System Overview",
            "STORAGE_STATUS": "Storage Status"
        }
        
        enabled_features = self.enabled_features
        available_packages = self.available_packages
        
        # Add network and security if enabled
        if enabled_features.get("network_monitoring", True):
            sources["NETWORK_STATS"] = "Network Statistics"
        if enabled_features.get("security_monitoring", True):
            sources["SECURITY_STATUS"] = "Security Status"
        
        # Always add services status
        sources["SERVICES_STATUS"] = "Services Status"
        
        # Enhanced monitoring sources (always available for complete monitoring)
        if enabled_features.get("enhanced_monitoring", True):
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
                "USER_SESSIONS": "User Sessions"  # CRITICAL: Ensure this is included
            })

        if enabled_features.get("surveillance_monitoring", True) and "SurveillanceStation" in available_packages:
            sources["SURVEILLANCE_STATUS"] = "Surveillance Station"
            
        # Package-dependent sources
        if enabled_features.get("docker_monitoring", True) and "Docker" in available_packages:
            sources["DOCKER_STATUS"] = "Docker Containers"
        
        if enabled_features.get("surveillance_monitoring", True) and "SurveillanceStation" in available_packages:
            sources["SURVEILLANCE_STATUS"] = "Surveillance Station"
        
        _LOG.info(f"Final enabled sources ({len(sources)}): {list(sources.values())}")
        return sources

    def update_polling_interval(self, source: str, interval: int) -> bool:
        try:
            synology_config = self._config_data.get("synology_config", {})
            polling_intervals = synology_config.get("polling_intervals", {})
            polling_intervals[source] = interval
            synology_config["polling_intervals"] = polling_intervals
            self._config_data["synology_config"] = synology_config
            return self.save_config()
        except Exception as ex:
            _LOG.error(f"Error updating polling interval: {ex}")
            return False