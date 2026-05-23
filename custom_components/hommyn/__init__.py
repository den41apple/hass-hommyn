"""Hommyn Cloud (Rusklimat) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CLIMATE_TYPES,
    CONF_DEVICE_MAC,
    CONF_DEVICE_TOKEN,
    CONF_DEVICE_TYPE,
    DOMAIN,
    FAN_TYPES,
    HEAT_TYPES,
    SENSOR_TYPES,
)
from .coordinator import HommynCoordinator

_LOGGER = logging.getLogger(__name__)


def _platforms_for(devtype: int) -> list[Platform]:
    """Return every HA platform a given Hommyn device type maps to."""
    platforms: list[Platform] = []
    if devtype in CLIMATE_TYPES:
        platforms.append(Platform.CLIMATE)
    if devtype in FAN_TYPES:
        platforms.append(Platform.FAN)
    if devtype in SENSOR_TYPES:
        platforms.append(Platform.SENSOR)
    if devtype in HEAT_TYPES:
        platforms.append(Platform.NUMBER)
    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Hommyn device from a config entry."""
    # Single coordinator (shared MQTT connection) for the whole integration.
    coordinator: HommynCoordinator | None = hass.data.get(DOMAIN, {}).get("coordinator")
    if coordinator is None:
        coordinator = HommynCoordinator(hass)
        await coordinator.async_start()
        hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator
        hass.data[DOMAIN].setdefault("entries", set())

    hass.data[DOMAIN]["entries"].add(entry.entry_id)

    devtype: int = entry.data[CONF_DEVICE_TYPE]
    token: str = entry.data[CONF_DEVICE_TOKEN]
    coordinator.add_device("rusclimate", devtype, token)

    platforms = _platforms_for(devtype)
    if not platforms:
        _LOGGER.warning(
            "Unknown Hommyn device type %s (mac=%s); only state mirroring",
            devtype, entry.data.get(CONF_DEVICE_MAC),
        )
        return True

    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Tear down a Hommyn device."""
    devtype: int = entry.data[CONF_DEVICE_TYPE]
    token: str = entry.data[CONF_DEVICE_TOKEN]

    platforms = _platforms_for(devtype)
    if platforms:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
        if not unload_ok:
            return False

    coordinator: HommynCoordinator = hass.data[DOMAIN]["coordinator"]
    coordinator.remove_device(token)

    entries: set[str] = hass.data[DOMAIN]["entries"]
    entries.discard(entry.entry_id)
    if not entries:
        await coordinator.async_stop()
        hass.data.pop(DOMAIN, None)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
