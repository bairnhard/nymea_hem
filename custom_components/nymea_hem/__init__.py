"""Nymea HEM Integration Setup."""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import config_validation as cv

from datetime import timedelta

from .const import DOMAIN
from .nymea_client import NymeaClient


_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema("nymea_hem")

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Nymea HEM component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Nymea HEM from a config entry."""
    if not all(key in entry.data for key in ["host", "username", "password"]):
        _LOGGER.error("Invalid configuration. Missing required parameters.")
        return False

    try:
        # Initialize Nymea client
        nymea_client = NymeaClient(
            host=entry.data["host"],
            port=entry.data.get("port", 2222),
            username=entry.data["username"],
            password=entry.data["password"],
            ssl_enabled=entry.data.get("ssl", True),
        )

        await nymea_client.authenticate()
        
            # Get Hello response
        hello_response = await nymea_client._handshake()
        hass.data[DOMAIN] = {
            "client": nymea_client,
            "server_info": getattr(nymea_client, '_server_info', {
                "name": "Unknown Nymea Server",
                "version": "Unknown"
            }),
        }

        async def async_update_data():
            """Fetch updated data from Nymea."""
            try:
                # Fetch all devices and their states
                devices = await nymea_client.get_things()
                return devices
            except Exception as err:
                raise UpdateFailed(f"Failed to update data: {err}")


        # Setup DataUpdateCoordinator
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_method=async_update_data,
            update_interval=timedelta(seconds=entry.data.get("poll_interval", 60)),
        )

        # Initial data refresh
        await coordinator.async_refresh()

    except Exception as err:
        _LOGGER.error(f"Failed to set up Nymea client: {err}")
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": nymea_client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
