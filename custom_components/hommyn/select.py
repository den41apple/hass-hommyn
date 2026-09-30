"""Select platform for Hommyn split-AC louver positions.

Verified on devtype 55 from the AC -> HA stream:

* `program_data/0` is an 8-char flag string; "1" at an axis index means the
  louver is sweeping.
* `program_data/3` holds the horizontal louver's fixed angle, "01".."05".
* `program_data/4` holds the vertical louver's fixed angle, "01".."05".

ASSUMPTION: which index of `program_data/0` (1 = vertical, 3 = horizontal)
maps to which physical louver plane comes from a source comment and is not
confirmed by the dump.

The climate entity's swing_mode only covers sweep on/off; these two selects
expose the five fixed angles the Hommyn app offers.
"""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LOUVER_ANGLE_FIELD_HORIZONTAL,
    LOUVER_ANGLE_FIELD_VERTICAL,
    LOUVER_ANGLES,
    LOUVER_ANGLES_REV,
    LOUVER_OPTION_SWING,
    LOUVER_OPTIONS,
    SWING_DEFAULT,
    SWING_FIELD,
    SWING_IDX_HORIZONTAL,
    SWING_IDX_VERTICAL,
)
from .coordinator import HommynCoordinator
from .entity import HommynEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register both louver selects for this device."""
    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(
        [
            HommynLouverSelect(
                coordinator,
                entry,
                "louver_vertical",
                SWING_IDX_VERTICAL,
                LOUVER_ANGLE_FIELD_VERTICAL,
            ),
            HommynLouverSelect(
                coordinator,
                entry,
                "louver_horizontal",
                SWING_IDX_HORIZONTAL,
                LOUVER_ANGLE_FIELD_HORIZONTAL,
            ),
        ]
    )


class HommynLouverSelect(HommynEntity, SelectEntity):
    """One louver axis: swing or one of five fixed angles."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:air-filter"
    _attr_options = LOUVER_OPTIONS

    def __init__(
        self,
        coordinator: HommynCoordinator,
        entry: ConfigEntry,
        key: str,
        index: int,
        angle_field: str,
    ) -> None:
        self._key = key
        self._index = index
        self._angle_field = angle_field
        self._swinging = False
        self._angle: str | None = None
        super().__init__(coordinator, entry)
        self._attr_translation_key = key
        self._attr_unique_id = f"{self._mac}_{key}"

    # ------------------------------------------------------------------
    # State decoding
    # ------------------------------------------------------------------

    def _apply_state(self, key: str, value: str) -> None:
        if key == SWING_FIELD:
            raw = (value.strip() or SWING_DEFAULT).ljust(8, "0")
            self._swinging = raw[self._index] == "1"
        elif key == self._angle_field:
            self._angle = LOUVER_ANGLES.get(value.strip().zfill(2))
        else:
            return
        # Sweeping wins: the angle field keeps its last value while the louver
        # is in motion, so it must not override the swing state.
        self._attr_current_option = (
            LOUVER_OPTION_SWING if self._swinging else self._angle
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_select_option(self, option: str) -> None:
        if option == LOUVER_OPTION_SWING:
            self._publish(SWING_FIELD, self._swing_string("1"))
            return

        code = LOUVER_ANGLES_REV.get(option)
        if code is None:
            raise ValueError(f"Unsupported louver position {option}")
        # Stop the sweep first, then park the louver — the order the Hommyn
        # app uses.
        self._publish(SWING_FIELD, self._swing_string("0"))
        self._publish(self._angle_field, code)

    def _swing_string(self, flag: str) -> str:
        """Current program_data/0 with this axis set to `flag`."""
        cached = self._coordinator.state.get(self._token, {}).get(SWING_FIELD)
        raw = list((cached or SWING_DEFAULT).ljust(8, "0"))
        raw[self._index] = flag
        return "".join(raw)
