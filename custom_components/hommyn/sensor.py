"""Sensor platform for Hommyn ventilation / breezer devices.

Exposes the measurement topics that matter on a breezer: CO2, the built-in
air-temperature probe, filter resource, and WiFi signal. These complement
the `fan` entity (on/off + speed).
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HommynCoordinator
from .entity import HommynEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HommynSensorDescription(SensorEntityDescription):
    """Sensor description with a parser from the raw MQTT payload."""

    # state key relative to .../state/  (e.g. "sensor/co2")
    state_key: str
    # parse a raw payload string into the native value (or None to ignore)
    parse: Callable[[str], float | int | None] = float


def _parse_float(raw: str) -> float | None:
    try:
        return round(float(raw), 1)
    except (TypeError, ValueError):
        return None


def _parse_int(raw: str) -> int | None:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _parse_filter(raw: str) -> int | None:
    """`expendables` looks like "[66]" — a JSON list of consumable percents."""
    try:
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return int(data[0])
    except (ValueError, TypeError):
        pass
    return _parse_int(raw)


SENSORS: tuple[HommynSensorDescription, ...] = (
    HommynSensorDescription(
        key="co2",
        state_key="sensor/co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        parse=_parse_int,
    ),
    HommynSensorDescription(
        key="air_temperature",
        state_key="sensor/temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        parse=_parse_float,
    ),
    HommynSensorDescription(
        key="filter",
        state_key="expendables",
        translation_key="filter",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        parse=_parse_filter,
    ),
    HommynSensorDescription(
        key="rssi",
        state_key="diag/rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        parse=_parse_int,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(
        HommynSensor(coordinator, entry, desc) for desc in SENSORS
    )


class HommynSensor(HommynEntity, SensorEntity):
    """A single measurement from a Hommyn device."""

    entity_description: HommynSensorDescription

    def __init__(
        self,
        coordinator: HommynCoordinator,
        entry: ConfigEntry,
        description: HommynSensorDescription,
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._mac}_{description.key}"

    def _apply_state(self, key: str, value: str) -> None:
        if key == self.entity_description.state_key:
            self._attr_native_value = self.entity_description.parse(value)
