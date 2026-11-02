"""Config flow for Nymea HEM integration."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD

from .const import (
    DOMAIN,
    CONF_SSL,
    CONF_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_POLL_INTERVAL,
)
from .nymea_client import NymeaClient

_LOGGER = logging.getLogger(__name__)


class NymeaHEMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nymea HEM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client: NymeaClient | None = None
            try:
                data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_SSL: user_input.get(CONF_SSL, DEFAULT_SSL),
                    CONF_POLL_INTERVAL: user_input.get(
                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                    ),
                }
                client = NymeaClient(
                    host=data[CONF_HOST],
                    port=data[CONF_PORT],
                    username=data[CONF_USERNAME],
                    password=data[CONF_PASSWORD],
                    ssl_enabled=data[CONF_SSL],
                )
                await client.authenticate()
                return self.async_create_entry(
                    title=f"Nymea HEM - {data[CONF_HOST]}", data=data
                )
            except Exception as err:
                _LOGGER.error("Connection error: %s", err)
                errors["base"] = "cannot_connect"
            finally:
                if client is not None:
                    await client.close_connection()

        return self._show_config_form(errors)

    def _show_config_form(
        self, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the configuration form."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=""): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_USERNAME, default=""): str,
                    vol.Required(CONF_PASSWORD, default=""): str,
                    vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
                    vol.Optional(
                        CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                    ): int,
                }
            ),
            errors=errors or {},
        )
