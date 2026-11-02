"""Button platform for parameterless nymea actions."""

from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import NymeaEntity, writable_state_map


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    entities = []
    for thing in coordinator.data or []:
        writable_action_ids = {
            action["id"] for action, _ in writable_state_map(thing).values()
        }
        for action in thing.get("thingClassDetails", {}).get("actionTypes", []):
            if (
                action.get("id")
                and action["id"] not in writable_action_ids
                and not action.get("paramTypes")
            ):
                entities.append(NymeaActionButton(coordinator, client, thing, action))
    async_add_entities(entities)


class NymeaActionButton(NymeaEntity, ButtonEntity):
    """A parameterless nymea action."""

    def __init__(self, coordinator, client, thing, action) -> None:
        super().__init__(coordinator, client, thing)
        self._action = action
        self._attr_name = action.get("displayName") or action.get("name")
        self._attr_unique_id = f"{thing['id']}_{action['id']}_action"

    async def async_press(self) -> None:
        confirmed = await self._client.execute_action(
            self._thing["id"], self._action["id"]
        )
        if not confirmed:
            await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
