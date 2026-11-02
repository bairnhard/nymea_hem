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

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TEXT,
    Platform.BUTTON,
]

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
        _LOGGER.info("Nymea client authenticated successfully")
        thing_class_cache: dict[str, dict | None] = {}

        class NymeaUpdateCoordinator(DataUpdateCoordinator):
            """Coordinator for fetching Nymea data."""

            async def _async_update_data(self):
                """Fetch the latest data from Nymea."""
                try:
                    things = await nymea_client.get_things()
                    for thing in things:
                        thing_class_id = thing.get("thingClassId")
                        if not thing_class_id:
                            continue
                        if thing_class_id not in thing_class_cache:
                            details = await nymea_client.get_thing_class_details(
                                thing_class_id
                            )
                            thing_class_cache[thing_class_id] = (
                                details[0] if details else None
                            )
                        if details := thing_class_cache.get(thing_class_id):
                            thing["thingClassDetails"] = details
                            thing.setdefault(
                                "thingClassName",
                                details.get("displayName") or details.get("name"),
                            )
                    return things
                except Exception as err:
                    raise UpdateFailed(f"Error updating Nymea data: {err}") from err

        poll_interval_seconds = entry.data.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        update_interval = timedelta(seconds=poll_interval_seconds)

        _LOGGER.debug(
            "Creating DataUpdateCoordinator with poll interval: %d seconds",
            poll_interval_seconds
        )

        coordinator = NymeaUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=update_interval,
        )

        await coordinator.async_config_entry_first_refresh()
        coordinator.server_identifier = getattr(
            nymea_client, "_server_info", {}
        ).get("uuid", f"unknown_{entry.entry_id}")
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
