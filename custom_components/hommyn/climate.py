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
    FAN_TO_SPEED_BY_TYPE,
    HVAC_TO_MODE,
    MAX_TEMP,
    MAX_TEMP_BY_TYPE,
    MIN_TEMP,
    MODE_TO_HVAC,
    SPEED_TO_FAN,
    SPEED_TO_FAN_BY_TYPE,
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
        # Fan scale: per-devtype table if we have one, otherwise the generic
        # split-AC scale. Keeps the exposed fan_modes in sync with the codes
        # we actually publish.
        self._speed_to_fan = SPEED_TO_FAN_BY_TYPE.get(self._devtype, SPEED_TO_FAN)
        self._fan_to_speed = FAN_TO_SPEED_BY_TYPE.get(self._devtype, FAN_TO_SPEED)
        if self._devtype in SPEED_TO_FAN_BY_TYPE:
            self._attr_fan_modes = list(self._speed_to_fan.values())
            # Gives the non-standard speeds (quiet, mid_low, ...) readable
            # names in the UI via translations/*.json.
            self._attr_translation_key = "split_ac"
        self._attr_max_temp = MAX_TEMP_BY_TYPE.get(self._devtype, MAX_TEMP)

    # ------------------------------------------------------------------
    # State decoding
    # ------------------------------------------------------------------

    def _apply_state(self, key: str, value: str) -> None:
        if key == "mode":
            self._attr_hvac_mode = HVACMode(MODE_TO_HVAC.get(value.strip(), "off"))
        elif key == "temperature":
            self._attr_target_temperature = _parse_int(value)
        elif key == "sensor/temperature":
            self._attr_current_temperature = _parse_room_temp(value)
        elif key == "speed":
            self._attr_fan_mode = self._speed_to_fan.get(value.strip(), "auto")
        elif key == SWING_FIELD:
            self._decode_swing(value.strip())

    def _decode_swing(self, raw: str) -> None:
        # Pad/normalise to at least 4 chars so indexing is safe.
        if len(raw) < 4:
            raw = raw.ljust(8, "0")
        self._swing_raw = raw
        # Only "1" means the louver is sweeping; any other non-zero value is a
        # fixed angle, which must not be reported as swinging.
        vertical = raw[SWING_IDX_VERTICAL] == "1"
        horizontal = raw[SWING_IDX_HORIZONTAL] == "1"
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
        code = self._fan_to_speed.get(fan_mode)
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


def _parse_room_temp(raw: str) -> float | None:
    """Parse `state/sensor/temperature`, dropping the not-measured placeholder.

    Split ACs that have no room sensor on the indoor unit either never publish
    this field or publish a retained 0 once, which Home Assistant would show as
    a real "0 °C". devtype 55 (Zanussi Barocco DC) is one of them: over several
    minutes of runtime it publishes mode and diag/* only. Treat 0 and anything
    outside a plausible indoor range as "no reading" so the UI hides it.
    """
    value = _parse_float(raw)
    if value is None or value == 0 or not -40 <= value <= 70:
        return None
    return value
