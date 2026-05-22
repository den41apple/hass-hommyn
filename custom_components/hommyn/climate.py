"""Climate platform for Hommyn split air conditioners."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FAN_TO_SPEED,
    HVAC_TO_MODE,
    MAX_TEMP,
    MIN_TEMP,
    MODE_TO_HVAC,
    SPEED_TO_FAN,
    SWING_DEFAULT,
    SWING_FIELD,
    SWING_IDX_HORIZONTAL,
    SWING_IDX_VERTICAL,
)
from .coordinator import HommynCoordinator
from .entity import HommynEntity

_LOGGER = logging.getLogger(__name__)

# Most split ACs we've tested support these. Some sub-families ignore turbo/max
# but won't fault on the command — they just clamp to high.
SUPPORTED_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.HEAT,
    HVACMode.FAN_ONLY,
]
SUPPORTED_FAN_MODES = ["auto", "low", "medium", "high", "turbo"]
SUPPORTED_SWING_MODES = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register the climate entity for this device."""
    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([HommynClimate(coordinator, entry)])


class HommynClimate(HommynEntity, ClimateEntity):
    """A Ballu / Electrolux / Zanussi / Hommyn split AC."""

    _attr_has_entity_name = True
    _attr_name = None  # use device name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 1
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_fan_modes = SUPPORTED_FAN_MODES
    _attr_swing_modes = SUPPORTED_SWING_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self, coordinator: HommynCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = self._mac
        # Raw 8-char louver string; kept so set_swing_mode preserves fixed angles.
        self._swing_raw = SWING_DEFAULT

    # ------------------------------------------------------------------
    # State decoding
    # ------------------------------------------------------------------

    def _apply_state(self, key: str, value: str) -> None:
        if key == "mode":
            self._attr_hvac_mode = HVACMode(MODE_TO_HVAC.get(value.strip(), "off"))
        elif key == "temperature":
            self._attr_target_temperature = _parse_int(value)
        elif key == "sensor/temperature":
            self._attr_current_temperature = _parse_float(value)
        elif key == "speed":
            self._attr_fan_mode = SPEED_TO_FAN.get(value.strip(), "auto")
        elif key == SWING_FIELD:
            self._decode_swing(value.strip())

    def _decode_swing(self, raw: str) -> None:
        # Pad/normalise to at least 4 chars so indexing is safe.
        if len(raw) < 4:
            raw = raw.ljust(8, "0")
        self._swing_raw = raw
        vertical = raw[SWING_IDX_VERTICAL] != "0"
        horizontal = raw[SWING_IDX_HORIZONTAL] != "0"
        if vertical and horizontal:
            self._attr_swing_mode = SWING_BOTH
        elif vertical:
            self._attr_swing_mode = SWING_VERTICAL
        elif horizontal:
            self._attr_swing_mode = SWING_HORIZONTAL
        else:
            self._attr_swing_mode = SWING_OFF

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        code = HVAC_TO_MODE.get(hvac_mode.value)
        if code is None:
            raise ValueError(f"Unsupported hvac_mode {hvac_mode}")
        self._publish("mode", code)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        # The device expects an integer Celsius value; HA sometimes hands us
        # 23.0 even with target_temperature_step=1.
        self._publish("temperature", int(round(float(temp))))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        code = FAN_TO_SPEED.get(fan_mode)
        if code is None:
            raise ValueError(f"Unsupported fan_mode {fan_mode}")
        self._publish("speed", code)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        want_vertical = swing_mode in (SWING_VERTICAL, SWING_BOTH)
        want_horizontal = swing_mode in (SWING_HORIZONTAL, SWING_BOTH)
        # Preserve any non-swing positions in the current louver string.
        raw = list((self._swing_raw or SWING_DEFAULT).ljust(8, "0"))
        raw[SWING_IDX_VERTICAL] = "1" if want_vertical else "0"
        raw[SWING_IDX_HORIZONTAL] = "1" if want_horizontal else "0"
        self._publish(SWING_FIELD, "".join(raw))

    async def async_turn_on(self) -> None:
        # Restore last non-off mode if we remember one; otherwise default to auto.
        last = (self._coordinator.state.get(self._token, {}).get("mode") or "1")
        if last == "0":
            last = "1"
        self._publish("mode", last)

    async def async_turn_off(self) -> None:
        self._publish("mode", "0")


def _parse_int(raw: str) -> int | None:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _parse_float(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
