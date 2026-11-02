"""Select platform for writable enumerated nymea states."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity

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
            values = state_type.get("possibleValues") or param.get("allowedValues")
            if values:
                entities.append(
                    NymeaStateSelect(
                        coordinator, client, thing, state_type, action, param, values
                    )
                )
    async_add_entities(entities)


class NymeaStateSelect(NymeaWritableStateEntity, SelectEntity):
    """A writable state restricted to a list of values."""

    def __init__(
        self, coordinator, client, thing, state_type, action, param, values
    ) -> None:
        super().__init__(coordinator, client, thing, state_type, action, param)
        labels = state_type.get("possibleValuesDisplayNames") or []
        if len(labels) != len(values):
            labels = [str(value) for value in values]
        self._value_by_label: dict[str, Any] = dict(zip(labels, values, strict=True))
        self._label_by_value = {
            self._key(value): label for label, value in self._value_by_label.items()
        }
        self._attr_options = list(self._value_by_label)

    @staticmethod
    def _key(value: Any) -> tuple[str, str]:
        return type(value).__name__, str(value)

    @property
    def current_option(self) -> str | None:
        return self._label_by_value.get(self._key(self._value()))

    async def async_select_option(self, option: str) -> None:
        await self._write(self._value_by_label[option])
