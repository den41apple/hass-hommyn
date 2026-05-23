"""Number platform for Hommyn breezer heating setpoint."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    DEFAULT_HEAT_RANGE,
    DOMAIN,
    HEAT_RANGE_BY_TYPE,
)
from .coordinator import HommynCoordinator
from .entity import HommynEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([HommynHeatSetpoint(coordinator, entry)])


class HommynHeatSetpoint(HommynEntity, NumberEntity):
    """Breezer / air-curtain heating setpoint (state & control/temperature)."""

    _attr_has_entity_name = True
    _attr_translation_key = "heat_setpoint"
    _attr_icon = "mdi:radiator"
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: HommynCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._mac}_heat_setpoint"
        devtype: int = entry.data[CONF_DEVICE_TYPE]
        lo, hi = HEAT_RANGE_BY_TYPE.get(devtype, DEFAULT_HEAT_RANGE)
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi

    def _apply_state(self, key: str, value: str) -> None:
        if key == "temperature":
            try:
                self._attr_native_value = int(float(value))
            except (TypeError, ValueError):
                self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        self._publish("temperature", int(round(value)))
