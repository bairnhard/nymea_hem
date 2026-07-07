"""Nymea HEM Integration Setup."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DOMAIN,
)
from .nymea_client import NymeaClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Retry configuration constants
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 5  # seconds
MAX_RETRY_DELAY = 300  # 5 minutes max
RETRY_MULTIPLIER = 2  # exponential backoff


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Nymea HEM component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nymea HEM from a config entry."""
    if not all(key in entry.data for key in (CONF_HOST, CONF_USERNAME, CONF_PASSWORD)):
        _LOGGER.error("Invalid configuration. Missing required parameters.")
        return False

    nymea_client = NymeaClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        ssl_enabled=entry.data.get(CONF_SSL, DEFAULT_SSL),
    )

    coordinator: DataUpdateCoordinator | None = None
    
    try:
        await nymea_client.authenticate()
        _LOGGER.info("Nymea client authenticated successfully")

        # Track failed update attempts for smart retry logic
        class NymeaUpdateCoordinator(DataUpdateCoordinator):
            """Custom coordinator with retry logic."""
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.last_error: Exception | None = None
                self.consecutive_failures = 0
                self.max_consecutive_failures = DEFAULT_RETRY_ATTEMPTS
                
            async def _async_update_data(self) -> Any:
                """Fetch data with improved error handling and retry logic."""
                try:
                    # Ensure connection is still alive before attempting update
                    if not nymea_client.is_connected():
                        _LOGGER.debug("Connection lost, attempting to re-authenticate")
                        await nymea_client.authenticate()
                    
                    data = await nymea_client.get_things()
                    
                    # Reset failure counter on success
                    if self.consecutive_failures > 0:
                        _LOGGER.info(
                            "Connection recovered after %d consecutive failures",
                            self.consecutive_failures
                        )
                        self.consecutive_failures = 0
                    
                    self.last_error = None
                    return data
                    
                except asyncio.TimeoutError as err:
                    self.consecutive_failures += 1
                    error_msg = f"Connection timeout (attempt {self.consecutive_failures}/{self.max_consecutive_failures})"
                    _LOGGER.warning(error_msg)
                    self.last_error = err
                    
                    # If we haven't exceeded max attempts, raise UpdateFailed to trigger retry
                    if self.consecutive_failures < self.max_consecutive_failures:
                        raise UpdateFailed(error_msg) from err
                    else:
                        # After max attempts, log severity and still raise but with different message
                        raise UpdateFailed(
                            f"Failed to connect after {self.max_consecutive_failures} attempts: {err}"
                        ) from err
                        
                except ConnectionError as err:
                    self.consecutive_failures += 1
                    error_msg = f"Connection lost (attempt {self.consecutive_failures}/{self.max_consecutive_failures}): {err}"
                    _LOGGER.warning(error_msg)
                    self.last_error = err
                    
                    if self.consecutive_failures < self.max_consecutive_failures:
                        raise UpdateFailed(error_msg) from err
                    else:
                        raise UpdateFailed(
                            f"Connection permanently lost after {self.max_consecutive_failures} attempts"
                        ) from err
                        
                except Exception as err:
                    self.consecutive_failures += 1
                    error_msg = f"Unexpected error updating Nymea data (attempt {self.consecutive_failures}/{self.max_consecutive_failures})"
                    _LOGGER.error(
                        "%s: %s",
                        error_msg,
                        err,
                        exc_info=True
                    )
                    self.last_error = err
                    raise UpdateFailed(error_msg) from err

        async def async_update_data():
            """Fetch updated data from Nymea."""
            return await coordinator._async_update_data()

        # Configure update interval from config or use default
        poll_interval_seconds = entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        update_interval = timedelta(seconds=poll_interval_seconds)
        
        _LOGGER.debug(
            "Creating DataUpdateCoordinator with poll interval: %d seconds",
            poll_interval_seconds
        )

        coordinator = NymeaUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_method=async_update_data,
            update_interval=update_interval,
        )

        # Do the first refresh
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Nymea HEM integration initialized successfully")

    except Exception as err:
        _LOGGER.error("Failed to set up Nymea client: %s", err, exc_info=True)
        await nymea_client.close_connection()
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": nymea_client,
        "coordinator": coordinator,
        "server_info": getattr(
            nymea_client,
            "_server_info",
            {
                "name": "Unknown Nymea Server",
                "version": "Unknown",
                "uuid": f"unknown_{entry.entry_id}",
            },
        ),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if entry_data and (client := entry_data.get("client")):
        _LOGGER.debug("Closing Nymea client connection")
        await client.close_connection()

    return unload_ok
