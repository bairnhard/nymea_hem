"""Text platform for writable string nymea states."""

from __future__ import annotations

from homeassistant.components.text import TextEntity

from .const import DOMAIN
from .entity import NymeaWritableStateEntity, writable_state_map


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
            if state_type.get("type") == "String" and not (
                state_type.get("possibleValues") or param.get("allowedValues")
            ):
                entities.append(
                    NymeaStateText(
                        coordinator, client, thing, state_type, action, param
                    )
                )
    async_add_entities(entities)


class NymeaStateText(NymeaWritableStateEntity, TextEntity):
    """A writable string state."""

    _attr_native_min = 0
    _attr_native_max = 255

    @property
    def native_value(self) -> str | None:
        value = self._value()
        return str(value) if value is not None else None

    async def async_set_value(self, value: str) -> None:
        await self._write(value)
