"""Nymea HEM Integration Setup."""

from __future__ import annotations

import logging
from datetime import timedelta

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

    try:
        await nymea_client.authenticate()

        async def async_update_data():
            """Fetch updated data from Nymea."""
            try:
                return await nymea_client.get_things()
            except Exception as err:
                raise UpdateFailed(f"Failed to update data: {err}") from err

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_method=async_update_data,
            update_interval=timedelta(
                seconds=entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            ),
        )

        await coordinator.async_config_entry_first_refresh()

    except Exception as err:
        _LOGGER.error("Failed to set up Nymea client: %s", err)
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
        await client.close_connection()

    return unload_ok
