"""
Enhanced helper functions and constants for Synology System integration.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Union

_LOG = logging.getLogger(__name__)


class SynologyConstants:
    """Enhanced constants for Synology integration."""
    
    DSM_API_INFO = "/webapi/query.cgi?api=SYNO.API.Info&version=1&method=query&query=all"
    DSM_AUTH = "/webapi/auth.cgi"
    
    DEFAULT_POLLING = {
        "system_status": 10,
        "storage_info": 30,
        "service_status": 15,
        "network_stats": 20,
        "security_status": 60,
        "hardware_monitor": 15,
        "drive_health": 45,
        "power_management": 30,
        "cache_performance": 20,
        "package_manager": 60,
        "user_sessions": 30
    }
    
    # Enhanced system sources with new monitoring capabilities
    SYSTEM_SOURCES = {
        "SYSTEM_OVERVIEW": "System Overview",
        "STORAGE_STATUS": "Storage Status",
        "NETWORK_STATS": "Network Statistics", 
        "SERVICES_STATUS": "Services Status",
        "SECURITY_STATUS": "Security Status",
        "DOCKER_STATUS": "Docker Containers",
        "THERMAL_STATUS": "Temperature Monitor",
        "CACHE_STATUS": "SSD Cache",
        "RAID_STATUS": "RAID Health",
        "VOLUME_STATUS": "Volume Usage",
        "UPS_STATUS": "UPS Monitor",
        "HARDWARE_MONITOR": "Hardware Monitor",
        "DRIVE_HEALTH": "Drive Health Monitor",
        "POWER_MANAGEMENT": "Power Management",
        "CACHE_PERFORMANCE": "Cache Performance",
        "PACKAGE_MANAGER": "Package Manager",
        "USER_SESSIONS": "User Sessions"
    }
    
    SYSTEM_COMMANDS = [
        "SYSTEM_RESTART", 
        "SYSTEM_SHUTDOWN", 
        "BEEP_START",
        "BEEP_STOP",
        "SET_FAN_MODE_QUIET",
        "SET_FAN_MODE_COOL",
        "SET_FAN_MODE_FULL"
    ]
    
    SYNOLOGY_PACKAGES = {
        "Docker": {"name": "Docker", "api": "SYNO.Docker"},
        "SecurityAdvisor": {"name": "Security Advisor", "api": "SYNO.SecurityAdvisor"},
    }


def celsius_to_fahrenheit(celsius: float) -> float:
    return (celsius * 9/5) + 32


def format_temperature(temp_celsius: float, unit: str = "celsius") -> str:
    """Format temperature with appropriate unit."""
    if unit.lower() == "fahrenheit":
        temp_f = celsius_to_fahrenheit(temp_celsius)
        return f"{temp_f:.1f}°F"
    return f"{temp_celsius:.1f}°C"


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable format."""
    if bytes_value == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(bytes_value)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"


def format_uptime(total_seconds: int) -> str:
    """Format uptime in human readable format."""
    if total_seconds == 0:
        return "0 seconds"
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "< 1m"


def parse_uptime_string(uptime_str: str) -> int:
    """Parse uptime string to seconds."""
    try:
        # Format: "days:hours:minutes" or similar
        parts = uptime_str.split(':')
        if len(parts) >= 3:
            days, hours, minutes = map(int, parts[:3])
            return days * 86400 + hours * 3600 + minutes * 60
    except (ValueError, AttributeError):
        pass
    return 0


def get_asset_path(filename: str) -> str:
    """Get full path to asset file with enhanced error handling."""
    try:
        current_file = Path(__file__)
        assets_dir = current_file.parent.parent / "assets" / "icons"
        asset_path = assets_dir / filename
        
        if asset_path.exists():
            return str(asset_path)
        else:
            _LOG.warning(f"Asset file not found: {asset_path}")
            # Return default synology logo path
            default_path = assets_dir / "synology_logo.png"
            return str(default_path)
            
    except Exception as ex:
        _LOG.error(f"Error getting asset path for {filename}: {ex}")
        return ""


def validate_ip_address(ip_string: str) -> bool:
    """Validate IP address format."""
    try:
        parts = ip_string.split('.')
        if len(parts) != 4: return False
        for part in parts:
            if not 0 <= int(part) <= 255: return False
        return True
    except (ValueError, AttributeError):
        return False


def validate_port(port: int) -> bool:
    """Validate port number."""
    return 1 <= port <= 65535


def get_source_icon_path(source: str) -> str:
    """Get icon path for media player source with enhanced mapping."""
    icon_mapping = {
        "SYSTEM_OVERVIEW": "system_overview.png",
        "STORAGE_STATUS": "storage_status.png", 
        "NETWORK_STATS": "network_stats.png",
        "SERVICES_STATUS": "services_status.png",
        "SECURITY_STATUS": "security_status.png",
        "DOCKER_STATUS": "docker_status.png",
        "THERMAL_STATUS": "thermal_status.png",
        "CACHE_STATUS": "cache_status.png",
        "RAID_STATUS": "raid_status.png",
        "VOLUME_STATUS": "volume_status.png",
        "UPS_STATUS": "ups_status.png",
        # NEW ENHANCED SOURCES
        "HARDWARE_MONITOR": "hardware_monitor.png",
        "DRIVE_HEALTH": "drive_health.png",
        "POWER_MANAGEMENT": "power_management.png",
        "CACHE_PERFORMANCE": "cache_performance.png",
        "PACKAGE_MANAGER": "package_manager.png",
        "USER_SESSIONS": "user_sessions.png"
    }
    
    icon_filename = icon_mapping.get(source, "synology_logo.png")
    icon_path = get_asset_path(icon_filename)
    
    return icon_path


def safe_get_nested_value(data: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def create_two_line_display(line1: str, line2: str, max_length: int = 80) -> tuple[str, str]:
    """Create properly formatted two-line display for media player with scrolling.
    
    Args:
        line1: First line of text
        line2: Second line of text 
        max_length: Maximum length before truncation
    
    Returns:
        Tuple of formatted line1 and line2
    """
    if len(line1) > max_length:
        line1 = line1[:max_length-3] + "..."
    if len(line2) > max_length:
        line2 = line2[:max_length-3] + "..."
    return line1, line2


def determine_system_health_status(system_data: Dict[str, Any]) -> str:
    """Determine overall system health from various metrics."""
    try:
        # Check critical indicators
        cpu_usage = system_data.get('cpu_usage', 0)
        memory_usage = system_data.get('memory_usage', 0)
        temperature = system_data.get('system_temp', 0)
        
        # Determine health level
        if cpu_usage > 90 or memory_usage > 95 or temperature > 80:
            return "critical"
        elif cpu_usage > 70 or memory_usage > 85 or temperature > 70:
            return "warning"
        else:
            return "healthy"
    except Exception:
        return "unknown"


def format_cache_hit_rate(hit_rate: float) -> str:
    """Format cache hit rate with performance indication."""
    if hit_rate >= 90:
        return f"{hit_rate:.1f}% (Excellent)"
    elif hit_rate >= 75:
        return f"{hit_rate:.1f}% (Good)"
    elif hit_rate >= 50:
        return f"{hit_rate:.1f}% (Fair)"
    else:
        return f"{hit_rate:.1f}% (Poor)"


def format_drive_temperature(temp: int, is_ssd: bool = False) -> str:
    """Format drive temperature with health indication."""
    if temp == 0:
        return "N/A"
    
    # Different thresholds for SSD vs HDD
    if is_ssd:
        if temp < 50:
            status = "Cool"
        elif temp < 70:
            status = "Normal"
        elif temp < 85:
            status = "Warm"
        else:
            status = "Hot"
    else:  # HDD
        if temp < 40:
            status = "Cool"
        elif temp < 50:
            status = "Normal"
        elif temp < 60:
            status = "Warm"
        else:
            status = "Hot"
    
    return f"{temp}°C ({status})"


def parse_ups_runtime(runtime_minutes: int) -> str:
    """Format UPS runtime in human-readable format."""
    if runtime_minutes == 0:
        return "No backup"
    
    hours = runtime_minutes // 60
    minutes = runtime_minutes % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def get_performance_indicator(value: float, thresholds: Dict[str, float]) -> str:
    """Get performance indicator based on value and thresholds."""
    if value >= thresholds.get('excellent', 90):
        return "🟢 Excellent"
    elif value >= thresholds.get('good', 75):
        return "🟡 Good"
    elif value >= thresholds.get('fair', 50):
        return "🟠 Fair"
    else:
        return "🔴 Poor"