"""Shared entity helpers for the Nymea HEM integration."""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NUMERIC_TYPES = {"Double", "Int", "Uint"}


def value_type_matches(state_type: dict[str, Any], param_type: dict[str, Any]) -> bool:
    """Return whether a generated action parameter can write a state."""
    return state_type.get("type") == param_type.get("type")


def values_match(actual: Any, expected: Any) -> bool:
    """Compare a read-back value with the requested value."""
    if (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and isinstance(expected, (int, float))
        and not isinstance(expected, bool)
    ):
        return math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9)
    return actual == expected


def find_state_action(
    state_type: dict[str, Any], action_types: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Find the single-parameter action automatically generated for a state.

    Nymea normally reuses the state id for the generated action. Name matching
    supports older/vendor forks, but only when the result is unambiguous and its
    sole parameter has the same data type.
    """
    state_id = state_type.get("id")
    state_name = state_type.get("name")
    candidates = [
        action
        for action in action_types
        if action.get("id") == state_id
    ]
    if not candidates and state_name:
        candidates = [
            action
            for action in action_types
            if action.get("name") == state_name
        ]
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for action in candidates:
        param_types = action.get("paramTypes") or []
        if len(param_types) != 1:
            continue
        param_type = param_types[0]
        if value_type_matches(state_type, param_type):
            matches.append((action, param_type))
    return matches[0] if len(matches) == 1 else None


def writable_state_map(thing: dict[str, Any]) -> dict[str, tuple[dict, dict]]:
    """Return state id -> (action type, parameter type) for writable states."""
    details = thing.get("thingClassDetails", {})
    actions = details.get("actionTypes", [])
    result = {}
    for state_type in details.get("stateTypes", []):
        match = find_state_action(state_type, actions)
        if match and state_type.get("id"):
            result[state_type["id"]] = match
    return result


class NymeaEntity(CoordinatorEntity):
    """Base class for entities backed by a nymea thing."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, client, thing: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._client = client
        self._thing = thing

    @property
    def device_info(self) -> DeviceInfo:
        server_identifier = getattr(
            self.coordinator, "server_identifier", "unknown"
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._thing["id"])},
            name=self._thing.get("name", "Nymea Thing"),
            manufacturer="Nymea",
            model=self._thing.get("thingClassName")
            or self._thing.get("thingClassId")
            or "Thing",
            via_device=(DOMAIN, server_identifier),
        )

    def _live_thing(self) -> dict[str, Any]:
        for thing in self.coordinator.data or []:
            if thing.get("id") == self._thing.get("id"):
                return thing
        return self._thing

    def _state(self, state_type_id: str) -> dict[str, Any] | None:
        for state in self._live_thing().get("states", []):
            if state.get("stateTypeId") == state_type_id:
                return state
        return None

    async def _set_state(
        self,
        action_type: dict[str, Any],
        param_type: dict[str, Any],
        state_type_id: str,
        value: Any,
    ) -> None:
        confirmed = await self._client.execute_action(
            self._thing["id"],
            action_type["id"],
            [{"paramTypeId": param_type["id"], "value": value}],
        )
        if not confirmed:
            # Consolinno applies some actions asynchronously. Give the device a
            # moment before reading back the authoritative state.
            await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
        if not confirmed:
            state = self._state(state_type_id)
            actual_value = state.get("value") if state else None
            if values_match(actual_value, value):
                _LOGGER.info(
                    "Unconfirmed nymea action %s was verified by state read-back",
                    action_type["id"],
                )
            else:
                _LOGGER.warning(
                    "Nymea action %s timed out and state verification failed: "
                    "requested=%r actual=%r",
                    action_type["id"],
                    value,
                    actual_value,
                )


class NymeaWritableStateEntity(NymeaEntity):
    """Base class for a writable state and its generated action."""

    def __init__(
        self,
        coordinator,
        client,
        thing: dict[str, Any],
        state_type: dict[str, Any],
        action_type: dict[str, Any],
        param_type: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, client, thing)
        self._state_type = state_type
        self._action_type = action_type
        self._param_type = param_type
        self._attr_name = state_type.get("displayName") or state_type.get("name")
        self._attr_unique_id = f"{thing['id']}_{state_type['id']}"

    @property
    def available(self) -> bool:
        return super().available and self._state(self._state_type["id"]) is not None

    def _value(self) -> Any:
        state = self._state(self._state_type["id"])
        return state.get("value") if state else None

    async def _write(self, value: Any) -> None:
        await self._set_state(
            self._action_type,
            self._param_type,
            self._state_type["id"],
            value,
        )
