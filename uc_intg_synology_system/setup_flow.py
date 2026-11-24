"""
Setup flow for the Synology System integration.

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import re
from typing import Any

from ucapi import RequestUserInput
from ucapi_framework import BaseSetupFlow

from uc_intg_synology_system.client import SynologySystemClient
from uc_intg_synology_system.config import DEVICE_ID, SynologyConfig
from uc_intg_synology_system.helpers import validate_port

_LOG = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 40
_HOSTNAME = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
_TEMPERATURE_UNITS = ("celsius", "fahrenheit")


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("true", "1", "yes")


class SynologySetupFlow(BaseSetupFlow[SynologyConfig]):
    """Collects the NAS address and credentials and verifies them against DSM."""

    def get_manual_entry_form(self, error: str = "", values: dict[str, Any] | None = None) -> RequestUserInput:
        current = self.selected_config_entry
        values = values or {}

        def pick(key: str, fallback: Any) -> Any:
            if key in values:
                return values[key]
            if current is not None:
                return getattr(current, key, fallback)
            return fallback

        try:
            port = int(float(pick("port", 5001)))
        except (TypeError, ValueError):
            port = 5001
        if not validate_port(port):
            port = 5001

        temperature = str(pick("temperature_unit", "celsius")).lower()
        if temperature not in _TEMPERATURE_UNITS:
            temperature = "celsius"

        settings = []
        if error:
            settings.append({
                "id": "error",
                "label": {"en": ""},
                "field": {"label": {"value": {"en": f"⚠️ {error}"}}},
            })
        settings += [
            {"id": "host", "label": {"en": "Synology NAS IP Address"},
             "field": {"text": {"value": str(pick("host", ""))}}},
            {"id": "port", "label": {"en": "DSM Port"},
             "field": {"number": {"value": port, "min": 1, "max": 65535}}},
            {"id": "username", "label": {"en": "Username"},
             "field": {"text": {"value": str(pick("username", ""))}}},
            {"id": "password",
             "label": {"en": "Password (leave empty to keep the saved password)" if current else "Password"},
             "field": {"password": {"value": ""}}},
            {"id": "use_https", "label": {"en": "Use HTTPS"},
             "field": {"checkbox": {"value": _as_bool(pick("use_https", True), True)}}},
            {"id": "temperature_unit", "label": {"en": "Temperature Unit"},
             "field": {"dropdown": {"value": temperature, "items": [
                 {"id": "celsius", "label": {"en": "Celsius (°C)"}},
                 {"id": "fahrenheit", "label": {"en": "Fahrenheit (°F)"}},
             ]}}},
            {"id": "otp_code", "label": {"en": "2FA Code (Optional)"},
             "field": {"text": {"value": ""}}},
        ]
        return RequestUserInput({"en": "Synology System Setup"}, settings)

    async def query_device(self, input_values: dict[str, Any]) -> SynologyConfig | RequestUserInput:
        current = self.selected_config_entry

        host = str(input_values.get("host", "")).strip()
        username = str(input_values.get("username", "")).strip()
        password = str(input_values.get("password", ""))
        otp_code = str(input_values.get("otp_code", "")).strip()
        use_https = _as_bool(input_values.get("use_https"), True)
        temperature_unit = str(input_values.get("temperature_unit", "celsius")).lower()
        if temperature_unit not in _TEMPERATURE_UNITS:
            temperature_unit = "celsius"

        if not password and current is not None:
            password = current.password

        def error_form(message: str) -> RequestUserInput:
            return self.get_manual_entry_form(message, {
                "host": host, "port": input_values.get("port", 5001), "username": username,
                "use_https": use_https, "temperature_unit": temperature_unit,
            })

        if not host or not (_HOSTNAME.match(host)):
            return error_form("Enter the IP address or host name of the NAS.")
        if not username or not password:
            return error_form("Username and password are required.")
        try:
            port = int(float(input_values.get("port", 5001)))
        except (TypeError, ValueError):
            return error_form("The port must be a number.")
        if not validate_port(port):
            return error_form("The port must be between 1 and 65535.")

        client = SynologySystemClient(
            host=host,
            port=port,
            username=username,
            password=password,
            secure=use_https,
            dsm_version=7,
            otp_code=otp_code or None,
            temperature_unit=temperature_unit,
            device_token=current.device_token if current is not None and not otp_code else None,
        )
        try:
            connected = await asyncio.wait_for(client.connect(), timeout=_CONNECT_TIMEOUT)
            if not connected:
                return error_form(client.last_error or "Could not connect to the NAS.")
            overview = await client.get_system_overview()
            if not overview:
                return error_form("Connected, but the NAS returned no system information.")
            _LOG.info("Connected to Synology %s running DSM %s", overview.get("model"), overview.get("version"))
            packages = dict(client.available_packages)
            device_token = client.device_token or ""
            model = str(overview.get("model") or "").strip()
        except asyncio.TimeoutError:
            return error_form(f"Timed out connecting to {host}:{port}. Check the address, port and HTTPS setting.")
        except Exception as err:  # pylint: disable=broad-except
            _LOG.error("Setup connection error: %s", err)
            return error_form(f"Could not connect: {err}")
        finally:
            await client.disconnect()

        return SynologyConfig(
            identifier=DEVICE_ID,
            name=f"Synology {model}" if model and model != "N/A" else "Synology System",
            host=host,
            port=port,
            username=username,
            password=password,
            use_https=use_https,
            temperature_unit=temperature_unit,
            device_token=device_token,
            available_packages=packages,
        )
