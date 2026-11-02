"""Number platform for writable numeric nymea states."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity

from .const import DOMAIN
from .entity import (
    NUMERIC_TYPES,
    NymeaWritableStateEntity,
    writable_state_map,
)
from .sensor import UNIT_MAP

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
            possible = state_type.get("possibleValues") or param.get("allowedValues")
            if state_type.get("type") in NUMERIC_TYPES and not possible:
                entities.append(
                    NymeaStateNumber(
                        coordinator, client, thing, state_type, action, param
                    )
                )
    _LOGGER.info("Adding %d writable nymea number entities", len(entities))
    async_add_entities(entities)


class NymeaStateNumber(NymeaWritableStateEntity, NumberEntity):
    """A writable numeric nymea state."""

    def __init__(self, coordinator, client, thing, state_type, action, param) -> None:
        super().__init__(coordinator, client, thing, state_type, action, param)
        live_state = next(
            (
                state
                for state in thing.get("states", [])
                if state.get("stateTypeId") == state_type.get("id")
            ),
            {},
        )
        minimum = live_state.get("minValue", state_type.get("minValue"))
        maximum = live_state.get("maxValue", state_type.get("maxValue"))
        step = state_type.get("stepSize")
        minimum = param.get("minValue") if minimum is None else minimum
        maximum = param.get("maxValue") if maximum is None else maximum
        step = param.get("stepSize") if step is None else step
        self._attr_native_min_value = float(0 if minimum is None else minimum)
        self._attr_native_max_value = float(100 if maximum is None else maximum)
        self._attr_native_step = float(1 if step is None else step)
        unit = state_type.get("unit") or param.get("unit")
        self._attr_native_unit_of_measurement = UNIT_MAP.get(unit, unit)

    @property
    def native_value(self) -> float | None:
        value = self._value()
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        if self._state_type.get("type") in {"Int", "Uint"}:
            value = int(value)
        await self._write(value)
