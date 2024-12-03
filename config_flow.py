"""Config flow for Nymea HEM integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv

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

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate input data
                host = user_input.get(CONF_HOST)
                port = user_input.get(CONF_PORT, DEFAULT_PORT)
                username = user_input.get(CONF_USERNAME)
                password = user_input.get(CONF_PASSWORD)
                ssl_enabled = user_input.get(CONF_SSL, DEFAULT_SSL)
                poll_interval = user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

                # Perform validation
                if not host:
                    errors[CONF_HOST] = "missing_host"
                if not username:
                    errors[CONF_USERNAME] = "missing_username"
                if not password:
                    errors[CONF_PASSWORD] = "missing_password"

                if errors:
                    return self._show_config_form(errors)

                # Attempt to authenticate
                client = NymeaClient(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    ssl_enabled=ssl_enabled                    
                )

                # Verify connection and authentication
                await client.authenticate()
                
                # Create unique entry
                return self.async_create_entry(
                    title=f"Nymea HEM - {host}",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_SSL: ssl_enabled,
                        CONF_POLL_INTERVAL: poll_interval
                    }
                )
            
            except Exception as err:
                _LOGGER.error(f"Connection error: {err}")
                errors["base"] = "cannot_connect"

        return self._show_config_form(errors)

    def _show_config_form(self, errors=None):
        """Show the configuration form."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=""): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_USERNAME, default=""): str,
                vol.Required(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int
            }),
            errors=errors or {}
        )