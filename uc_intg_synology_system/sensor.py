"""
Synology system sensor entities.

Expose the key NAS values as sensors so they can be placed on Remote pages and
used in activities. Values come from the data the background monitoring loop
already fetches, so the sensors add no extra polling of the NAS (storage is
refreshed less often by the loop).

:copyright: (c) 2024 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from typing import Any, Dict, Optional

import ucapi
from ucapi.sensor import Attributes, DeviceClasses, Options, Sensor, States

_LOG = logging.getLogger(__name__)

# (entity id, name, device class, unit, options)
_SENSORS = (
    ("synology_cpu_usage", "Synology CPU Usage", DeviceClasses.CUSTOM, "%", None),
    ("synology_memory_usage", "Synology Memory Usage", DeviceClasses.CUSTOM, "%", None),
    ("synology_temperature", "Synology Temperature", DeviceClasses.TEMPERATURE, None,
     {Options.NATIVE_UNIT: "°C"}),
    ("synology_storage_used", "Synology Storage Used", DeviceClasses.CUSTOM, "%", None),
    ("synology_uptime", "Synology Uptime", DeviceClasses.CUSTOM, None, None),
    ("synology_status", "Synology Status", DeviceClasses.CUSTOM, None, None),
    ("synology_dsm_version", "Synology DSM Version", DeviceClasses.CUSTOM, None, None),
)


class SynologySensors:
    """Creates and updates the Synology sensor entities."""

    def __init__(self, api: ucapi.IntegrationAPI) -> None:
        self._api = api
        self._values: Dict[str, Any] = {}
        self._entities: Dict[str, Sensor] = {}
        for identifier, name, device_class, unit, options in _SENSORS:
            attributes = {Attributes.STATE: States.UNKNOWN, Attributes.VALUE: ""}
            if unit:
                attributes[Attributes.UNIT] = unit
            self._entities[identifier] = Sensor(
                identifier=identifier,
                name=name,
                features=[],
                attributes=attributes,
                device_class=device_class,
                options=options,
            )

    @property
    def entities(self) -> list:
        return list(self._entities.values())

    def owns(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def update_overview(self, overview: Dict[str, Any]) -> None:
        """Update from ``SynologySystemClient.get_system_overview()``."""
        if not overview:
            return
        self._set("synology_cpu_usage", _number(overview.get("cpu_usage")))
        self._set("synology_memory_usage", _number(overview.get("memory_usage")))
        self._set("synology_temperature", _number(overview.get("temperature_c")))
        self._set("synology_uptime", overview.get("uptime") or None)
        self._set("synology_status", overview.get("status") or None)
        self._set("synology_dsm_version", overview.get("version") or None)

    def update_storage(self, storage: Dict[str, Any]) -> None:
        """Update from ``SynologySystemClient.get_storage_status()``."""
        total = storage.get("total_size") if storage else None
        used = storage.get("total_used") if storage else None
        if total:
            self._set("synology_storage_used", round(100.0 * float(used or 0) / float(total), 1))

    def set_unavailable(self) -> None:
        for identifier in self._entities:
            self._values.pop(identifier, None)
            self._push(identifier, {Attributes.STATE: States.UNAVAILABLE})

    def push_initial_state(self, entity_id: str) -> None:
        """Send the latest value of one sensor (e.g. after it was subscribed)."""
        value = self._values.get(entity_id)
        if value is None:
            return
        self._push(entity_id, self._attributes(entity_id, value))

    def _set(self, identifier: str, value: Optional[Any]) -> None:
        if value is None:
            return
        self._values[identifier] = value
        self._push(identifier, self._attributes(identifier, value))

    def _attributes(self, identifier: str, value: Any) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {Attributes.STATE: States.ON, Attributes.VALUE: value}
        unit = self._entities[identifier].attributes.get(Attributes.UNIT)
        if unit:
            # The unit must be sent together with the value.
            attributes[Attributes.UNIT] = unit
        return attributes

    def _push(self, identifier: str, attributes: Dict[str, Any]) -> None:
        if self._api.configured_entities.contains(identifier):
            self._api.configured_entities.update_attributes(identifier, attributes)


def _number(value: Any) -> Optional[float]:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None
