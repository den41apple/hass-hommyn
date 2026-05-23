"""Fan platform for Hommyn ventilation / CO2 breezer devices (types 46, 69).

Breezer control model (verified on a Ballu ASP, devtype 69):
  state/mode  : 0 = off, 1 = manual, 4 = auto
  state/speed : 1..7 in manual mode (7 discrete steps);
                8 is reported by the device while in auto mode.
Heating setpoint (state/temperature) is exposed separately as a number entity.

Mapping to Home Assistant:
  - on/off            -> mode 0 vs non-zero
  - 7 discrete speeds -> manual mode (mode=1) + speed 1..7
  - "auto" preset     -> mode=4 (device picks the speed)
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

# 7 discrete manual speeds.
_SPEED_RANGE = (1, 7)

PRESET_AUTO = "auto"

MODE_OFF = "0"
MODE_MANUAL = "1"
MODE_AUTO = "4"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([HommynFan(coordinator, entry)])


class HommynFan(HommynEntity, FanEntity):
    """Hommyn breezer / ventilation unit."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_preset_modes = [PRESET_AUTO]
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(
        self, coordinator: HommynCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = self._mac
        self._mode: str | None = None
        self._raw_speed: int | None = None
        self._last_manual_speed = 3  # remembered for turn_on

    # ------------------------------------------------------------------
    # State decoding
    # ------------------------------------------------------------------

    def _apply_state(self, key: str, value: str) -> None:
        if key == "mode":
            self._mode = value.strip()
        elif key == "speed":
            try:
                self._raw_speed = int(float(value))
            except (TypeError, ValueError):
                self._raw_speed = None
            else:
                if 1 <= (self._raw_speed or 0) <= _SPEED_RANGE[1]:
                    self._last_manual_speed = self._raw_speed

    @property
    def is_on(self) -> bool | None:
        if self._mode is None:
            return None
        return self._mode != MODE_OFF

    @property
    def preset_mode(self) -> str | None:
        return PRESET_AUTO if self._mode == MODE_AUTO else None

    @property
    def percentage(self) -> int | None:
        # In auto mode the device drives the fan; show no manual % position.
        if self._mode in (None, MODE_OFF):
            return 0
        if self._mode == MODE_AUTO:
            return None
        if self._raw_speed is None:
            return None
        clamped = max(_SPEED_RANGE[0], min(_SPEED_RANGE[1], self._raw_speed))
        return ranged_value_to_percentage(_SPEED_RANGE, clamped)

    @property
    def speed_count(self) -> int:
        return _SPEED_RANGE[1]

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage <= 0:
            self._publish("mode", MODE_OFF)
            return
        raw = math.ceil(percentage_to_ranged_value(_SPEED_RANGE, percentage))
        raw = max(_SPEED_RANGE[0], min(_SPEED_RANGE[1], raw))
        # Setting a manual speed implies manual mode.
        self._publish("mode", MODE_MANUAL)
        self._publish("speed", raw)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_AUTO:
            self._publish("mode", MODE_AUTO)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if preset_mode == PRESET_AUTO:
            self._publish("mode", MODE_AUTO)
            return
        if percentage is not None and percentage > 0:
            await self.async_set_percentage(percentage)
            return
        self._publish("mode", MODE_MANUAL)
        self._publish("speed", self._last_manual_speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._publish("mode", MODE_OFF)
