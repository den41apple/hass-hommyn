"""Switch platform for Hommyn split-AC display backlight and buzzer.

`backlight` takes "true"/"false"; the buzzer lives in `volume` and takes
"1"/"0" — verified on devtype 55 from the AC -> HA stream.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    DISPLAY_SWITCH_TYPES,
    DOMAIN,
    KEY_BACKLIGHT,
    KEY_SOUND,
    SOUND_SWITCH_TYPES,
)
from .coordinator import HommynCoordinator
from .entity import HommynEntity

_LOGGER = logging.getLogger(__name__)

# `backlight` reports "true"/"false" and `volume` "1"/"0"; accept both forms
# when decoding.
_TRUTHY = {"true", "1", "on"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register the device-setting switches this device type has."""
    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    devtype: int = entry.data[CONF_DEVICE_TYPE]

    entities: list[SwitchEntity] = []
    if devtype in DISPLAY_SWITCH_TYPES:
        entities.append(
            HommynSettingSwitch(
                coordinator,
                entry,
                "display",
                KEY_BACKLIGHT,
                "mdi:television-ambient-light",
                ("true", "false"),
            )
        )
    if devtype in SOUND_SWITCH_TYPES:
        entities.append(
            HommynSettingSwitch(
                coordinator,
                entry,
                "sound",
                KEY_SOUND,
                "mdi:volume-high",
                ("1", "0"),
            )
        )
    async_add_entities(entities)


class HommynSettingSwitch(HommynEntity, SwitchEntity):
    """A boolean device setting mirrored from state/<key>."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HommynCoordinator,
        entry: ConfigEntry,
        key: str,
        mqtt_key: str,
        icon: str,
        payloads: tuple[str, str],
    ) -> None:
        self._key = key
        self._mqtt_key = mqtt_key
        self._on_payload, self._off_payload = payloads
        super().__init__(coordinator, entry)
        self._attr_translation_key = key
        self._attr_unique_id = f"{self._mac}_{key}"
        self._attr_icon = icon

    def _apply_state(self, key: str, value: str) -> None:
        if key == self._mqtt_key:
            self._attr_is_on = value.strip().lower() in _TRUTHY

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._publish(self._mqtt_key, self._on_payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._publish(self._mqtt_key, self._off_payload)
