"""Fan platform for Hommyn ventilation / CO2 breezer devices (types 46, 69).

This is intentionally minimal: on/off + 6-step speed. Per-model extras
(filter life, child lock, schedules, etc.) can be added as dedicated
sensor / switch entities later.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from .coordinator import HommynCoordinator
from .entity import HommynEntity

_LOGGER = logging.getLogger(__name__)

# Hommyn breezer "speed" payload is 0..6, where 0 means "off".
_SPEED_RANGE = (1, 6)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([HommynFan(coordinator, entry)])


class HommynFan(HommynEntity, FanEntity):
    """Generic Hommyn fan/breezer."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(
        self, coordinator: HommynCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = self._mac
        self._raw_speed: int | None = None
        self._last_on_speed: int = 3  # remember last positive speed for turn_on

    # ------------------------------------------------------------------
    # State decoding
    # ------------------------------------------------------------------

    def _apply_state(self, key: str, value: str) -> None:
        if key == "speed":
            try:
                self._raw_speed = int(float(value))
            except (TypeError, ValueError):
                self._raw_speed = None
            else:
                if self._raw_speed and self._raw_speed > 0:
                    self._last_on_speed = self._raw_speed

    @property
    def is_on(self) -> bool | None:
        if self._raw_speed is None:
            return None
        return self._raw_speed > 0

    @property
    def percentage(self) -> int | None:
        if self._raw_speed is None or self._raw_speed <= 0:
            return 0
        return ranged_value_to_percentage(_SPEED_RANGE, self._raw_speed)

    @property
    def speed_count(self) -> int:
        return _SPEED_RANGE[1]

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage <= 0:
            self._publish("speed", 0)
            return
        raw = math.ceil(percentage_to_ranged_value(_SPEED_RANGE, percentage))
        raw = max(_SPEED_RANGE[0], min(_SPEED_RANGE[1], raw))
        self._publish("speed", raw)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is not None and percentage > 0:
            await self.async_set_percentage(percentage)
            return
        self._publish("speed", self._last_on_speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._publish("speed", 0)
