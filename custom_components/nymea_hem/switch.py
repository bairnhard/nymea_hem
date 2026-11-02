"""Switch platform for writable boolean nymea states."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import NymeaWritableStateEntity, writable_state_map

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    entities = []
    for thing in coordinator.data or []:
        state_types = {
            state["id"]: state
            for state in thing.get("thingClassDetails", {}).get("stateTypes", [])
            if state.get("id")
        }
        for state_id, (action, param) in writable_state_map(thing).items():
            state_type = state_types[state_id]
            if (
                state_type.get("type") == "Bool"
                and not (
                    state_type.get("possibleValues")
                    or param.get("allowedValues")
                )
            ):
                entities.append(
                    NymeaStateSwitch(
                        coordinator, client, thing, state_type, action, param
                    )
                )
    _LOGGER.info("Adding %d writable nymea switch entities", len(entities))
    async_add_entities(entities)


class NymeaStateSwitch(NymeaWritableStateEntity, SwitchEntity):
    """A writable nymea boolean state."""

    @property
    def is_on(self) -> bool | None:
        value = self._value()
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(False)
