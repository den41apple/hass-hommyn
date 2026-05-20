"""Config flow for Hommyn Cloud.

A single Home Assistant config entry corresponds to one paired device.
The user pastes the `rusklimat://device-share/...` link from the Hommyn
app and we extract the MAC, device type, token, and friendly name.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TOKEN,
    CONF_DEVICE_TYPE,
    CONF_SHARE_LINK,
    DEVICE_TYPES,
    DOMAIN,
)
from .share_link import ShareLinkError, parse_share_link

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SHARE_LINK): str,
        vol.Optional(CONF_DEVICE_NAME): str,
    }
)


class HommynConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Hommyn config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input[CONF_SHARE_LINK]
            try:
                link = parse_share_link(raw)
            except ShareLinkError as exc:
                _LOGGER.debug("Share link rejected: %s", exc)
                errors["base"] = "invalid_share_link"
            else:
                # Use a stable unique id so re-adding the same device updates
                # the existing entry instead of duplicating it.
                await self.async_set_unique_id(link.unique_id)
                self._abort_if_unique_id_configured()

                name = (
                    user_input.get(CONF_DEVICE_NAME)
                    or link.name
                    or _default_name(link.device_type, link.mac)
                )

                data = {
                    CONF_DEVICE_TYPE: link.device_type,
                    CONF_DEVICE_TOKEN: link.token,
                    CONF_DEVICE_MAC: link.mac,
                    CONF_DEVICE_NAME: name,
                    CONF_DEVICE_MODEL: link.model,
                }
                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "supported": ", ".join(
                    f"{t} ({label.split('/')[0].strip()})"
                    for t, (_, label) in sorted(DEVICE_TYPES.items())
                ),
            },
        )


def _default_name(devtype: int, mac: str) -> str:
    label = DEVICE_TYPES.get(devtype, ("?", "Hommyn device"))[1]
    short_label = label.split("/")[0].strip()
    return f"{short_label} {mac[-4:].upper()}"
