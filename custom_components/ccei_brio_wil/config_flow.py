"""Config flow for the CCEI BRiO WiL integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from . import DOMAIN
from .wil import DEFAULT_PORT, BrioWil, BrioWilError

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class BrioWilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            device = BrioWil(host, port)
            try:
                await device.async_test_connection()
            except BrioWilError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Pool Light ({host})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
