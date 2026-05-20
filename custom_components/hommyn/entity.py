"""Shared base class for Hommyn entities."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TOKEN,
    CONF_DEVICE_TYPE,
    DEVICE_TYPES,
    DOMAIN,
    SIGNAL_AVAILABILITY,
    SIGNAL_STATE_UPDATE,
)
from .coordinator import HommynCoordinator


class HommynEntity(Entity):
    """Mixin: handles availability + state dispatcher subscription."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: HommynCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._token: str = entry.data[CONF_DEVICE_TOKEN]
        self._devtype: int = entry.data[CONF_DEVICE_TYPE]
        self._mac: str = entry.data[CONF_DEVICE_MAC]
        self._attr_unique_id = f"{self._mac}_{self.entity_description.key}" \
            if getattr(self, "entity_description", None) else self._mac

        model_id: str | None = entry.data.get(CONF_DEVICE_MODEL)
        family_label = DEVICE_TYPES.get(self._devtype, ("?", "Hommyn device"))[1]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=entry.data.get(CONF_DEVICE_NAME) or family_label,
            manufacturer="Rusklimat (Hommyn)",
            model=model_id or family_label,
            connections={("mac", _format_mac(self._mac))},
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_STATE_UPDATE.format(token=self._token),
                self._handle_state_update,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_AVAILABILITY.format(token=self._token),
                self._handle_availability,
            )
        )
        # Seed from any state the coordinator has already cached.
        cached = self._coordinator.state.get(self._token, {})
        for key, value in cached.items():
            self._apply_state(key, value)
        self._refresh()

    # ------------------------------------------------------------------
    # Override points
    # ------------------------------------------------------------------

    def _apply_state(self, key: str, value: str) -> None:
        """Update entity attributes from a single state/* key."""

    # ------------------------------------------------------------------
    # Coordinator -> entity plumbing
    # ------------------------------------------------------------------

    @callback
    def _handle_state_update(self, key: str, value: str) -> None:
        self._apply_state(key, value)
        self._refresh()

    @callback
    def _handle_availability(self, is_available: bool) -> None:
        self._attr_available = is_available
        self._refresh()

    @property
    def available(self) -> bool:
        return self._coordinator.available.get(self._token, True)

    @callback
    def _refresh(self) -> None:
        if self.hass is not None and self.entity_id is not None:
            self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Convenience for subclasses
    # ------------------------------------------------------------------

    def _publish(self, key: str, value: Any) -> None:
        """Send `control/{key} = {value}`."""
        self._coordinator.publish_control(
            "rusclimate", self._devtype, self._token, key, str(value)
        )


def _format_mac(mac: str) -> str:
    """Format a 12-char hex MAC as aa:bb:cc:dd:ee:ff for HA device registry."""
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))
