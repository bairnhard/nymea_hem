"""Sensor platform for Nymea HEM."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_STATE_NAME,
    ATTR_STATE_TYPE_ID,
    ATTR_THING_CLASS_ID,
    ATTR_THING_CLASS_NAME,
    ATTR_VALUE_IN_STATE,
    ATTR_VALUE_PAYLOAD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

UNIT_MAP: dict[str, str | None] = {
    "UnitAmpere": UnitOfElectricCurrent.AMPERE,
    "UnitDegreeCelsius": UnitOfTemperature.CELSIUS,
    "UnitEuroCentPerKiloWattHour": "ct/kWh",
    "UnitHertz": UnitOfFrequency.HERTZ,
    "UnitHours": UnitOfTime.HOURS,
    "UnitKiloWattHour": UnitOfEnergy.KILO_WATT_HOUR,
    "UnitLux": "lx",
    "UnitMinutes": UnitOfTime.MINUTES,
    "UnitNone": None,
    "UnitOhm": "Ω",
    "UnitPartsPerMillion": "ppm",
    "UnitPercentage": PERCENTAGE,
    "UnitSeconds": UnitOfTime.SECONDS,
    "UnitUnixTime": None,
    "UnitVolt": UnitOfElectricPotential.VOLT,
    "UnitVoltAmpereReactive": "var",
    "UnitWatt": UnitOfPower.WATT,
}

INTERFACE_DEVICE_CLASS_MAP: dict[str, SensorDeviceClass] = {
    "temperaturesensor": SensorDeviceClass.TEMPERATURE,
    "energymeter": SensorDeviceClass.ENERGY,
    "smartmeter": SensorDeviceClass.ENERGY,
    "smartmeterproducer": SensorDeviceClass.POWER,
    "powersocket": SensorDeviceClass.POWER,
    "humiditysensor": SensorDeviceClass.HUMIDITY,
}

MEASUREMENT_DEVICE_CLASSES = {
    SensorDeviceClass.TEMPERATURE,
    SensorDeviceClass.POWER,
    SensorDeviceClass.CURRENT,
    SensorDeviceClass.VOLTAGE,
    SensorDeviceClass.FREQUENCY,
    SensorDeviceClass.HUMIDITY,
    SensorDeviceClass.ILLUMINANCE,
}

ENERGY_TOTAL_KEYWORDS = {
    "energy",
    "meter",
    "consumption",
    "production",
    "import",
    "export",
    "total",
}
POWER_KEYWORDS = {"power", "load"}
TEMPERATURE_KEYWORDS = {"temperature", "temp"}
HUMIDITY_KEYWORDS = {"humidity", "humid"}
CURRENT_KEYWORDS = {"current", "ampere", "amps"}
VOLTAGE_KEYWORDS = {"voltage", "volt"}
FREQUENCY_KEYWORDS = {"frequency", "hertz"}
ILLUMINANCE_KEYWORDS = {"illuminance", "brightness", "lux"}


def convert_value(value: Any, value_type: str) -> Any:
    """Convert value based on Nymea type."""
    type_converters = {
        "Bool": lambda x: bool(x),
        "Double": lambda x: float(x),
        "Int": lambda x: int(x),
        "Uint": lambda x: abs(int(x)),
        "String": lambda x: str(x),
        "Object": lambda x: x,
        "Color": lambda x: x,
    }

    converter = type_converters.get(value_type, lambda x: x)

    try:
        return converter(value)
    except (ValueError, TypeError):
        _LOGGER.warning("Could not convert %s to %s", value, value_type)
        return value


def is_numeric_value_type(value_type: str) -> bool:
    """Return True if the Nymea type is numeric."""
    return value_type in {"Double", "Int", "Uint"}


def infer_device_class(
    thing_data: dict[str, Any],
    state_type: dict[str, Any],
    native_unit: str | None,
) -> SensorDeviceClass | None:
    """Infer Home Assistant device class from interface, unit and naming."""
    interfaces = [str(i).lower() for i in thing_data.get("interfaces", [])]
    for interface in interfaces:
        if interface in INTERFACE_DEVICE_CLASS_MAP:
            return INTERFACE_DEVICE_CLASS_MAP[interface]

    if native_unit == UnitOfTemperature.CELSIUS:
        return SensorDeviceClass.TEMPERATURE
    if native_unit == UnitOfEnergy.KILO_WATT_HOUR:
        return SensorDeviceClass.ENERGY
    if native_unit == UnitOfPower.WATT:
        return SensorDeviceClass.POWER
    if native_unit == UnitOfElectricPotential.VOLT:
        return SensorDeviceClass.VOLTAGE
    if native_unit == UnitOfElectricCurrent.AMPERE:
        return SensorDeviceClass.CURRENT
    if native_unit == UnitOfFrequency.HERTZ:
        return SensorDeviceClass.FREQUENCY
    if native_unit == "lx":
        return SensorDeviceClass.ILLUMINANCE

    state_name = str(state_type.get("name", "")).lower()
    display_name = str(state_type.get("displayName", "")).lower()
    text = f"{state_name} {display_name}"

    if any(k in text for k in TEMPERATURE_KEYWORDS):
        return SensorDeviceClass.TEMPERATURE
    if any(k in text for k in POWER_KEYWORDS):
        return SensorDeviceClass.POWER
    if any(k in text for k in HUMIDITY_KEYWORDS):
        return SensorDeviceClass.HUMIDITY
    if any(k in text for k in CURRENT_KEYWORDS):
        return SensorDeviceClass.CURRENT
    if any(k in text for k in VOLTAGE_KEYWORDS):
        return SensorDeviceClass.VOLTAGE
    if any(k in text for k in FREQUENCY_KEYWORDS):
        return SensorDeviceClass.FREQUENCY
    if any(k in text for k in ILLUMINANCE_KEYWORDS):
        return SensorDeviceClass.ILLUMINANCE
    if any(k in text for k in ENERGY_TOTAL_KEYWORDS):
        return SensorDeviceClass.ENERGY

    return None


def infer_state_class(
    thing_data: dict[str, Any],
    state_type: dict[str, Any],
    device_class: SensorDeviceClass | None,
    native_unit: str | None,
    value_type: str,
) -> SensorStateClass | None:
    """Infer Home Assistant state class."""
    if not is_numeric_value_type(value_type):
        return None

    if device_class in MEASUREMENT_DEVICE_CLASSES:
        return SensorStateClass.MEASUREMENT

    if device_class == SensorDeviceClass.ENERGY and native_unit == UnitOfEnergy.KILO_WATT_HOUR:
        state_name = str(state_type.get("name", "")).lower()
        display_name = str(state_type.get("displayName", "")).lower()
        text = f"{state_name} {display_name}"

        if any(k in text for k in ENERGY_TOTAL_KEYWORDS):
            return SensorStateClass.TOTAL_INCREASING

        interfaces = [str(i).lower() for i in thing_data.get("interfaces", [])]
        if "energymeter" in interfaces or "smartmeter" in interfaces:
            return SensorStateClass.TOTAL_INCREASING

    return None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for the Nymea integration."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator = entry_data["coordinator"]
    server_info = entry_data.get("server_info", {})

    device_registry = async_get_device_registry(hass)

    server_identifier = server_info.get("uuid", f"unknown_{config_entry.entry_id}")
    server_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, server_identifier)},
        name=server_info.get("name", "Nymea Server"),
        manufacturer="Nymea",
        model=server_info.get("server", "Unknown Model"),
        sw_version=server_info.get("version", "Unknown"),
    )

    sensors: list[SensorEntity] = [
        NymeaServerInfoSensor(
            coordinator=coordinator,
            server_info=server_info,
            server_identifier=server_identifier,
        )
    ]

    for thing in coordinator.data or []:
        thing_class_id = thing.get("thingClassId")
        thing_class_details = None

        try:
            if thing_class_id:
                result = await client.get_thing_class_details(thing_class_id)
                if result:
                    thing_class_details = result[0]
        except Exception as err:
            _LOGGER.error(
                "Error fetching thing class details for %s: %s",
                thing.get("name"),
                err,
            )

        if thing_class_details:
            thing["thingClassDetails"] = thing_class_details

        state_types = thing.get("thingClassDetails", {}).get("stateTypes", [])
        if not state_types:
            _LOGGER.debug("No stateTypes available for thing %s", thing.get("name"))
            continue

        thing_identifier = thing.get("id")
        if not thing_identifier:
            continue

        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, thing_identifier)},
            name=thing.get("name", "Nymea Thing"),
            manufacturer="Nymea",
            model=thing.get("thingClassName") or thing.get("thingClassId") or "Thing",
            via_device=(DOMAIN, server_identifier),
        )

        state_type_map = {state_type["id"]: state_type for state_type in state_types if "id" in state_type}

        for state in thing.get("states", []):
            state_type = state_type_map.get(state.get("stateTypeId"))
            if not state_type:
                continue

            sensors.append(
                NymeaHEMStateSensor(
                    coordinator=coordinator,
                    thing_data=thing,
                    state_type=state_type,
                    server_identifier=server_identifier,
                )
            )

    async_add_entities(sensors)


class NymeaHEMStateSensor(CoordinatorEntity, SensorEntity):
    """Representation of a single Nymea state as Home Assistant sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        thing_data: dict[str, Any],
        state_type: dict[str, Any],
        server_identifier: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._thing_data = thing_data
        self._state_type = state_type
        self._server_identifier = server_identifier
        self._value_type = state_type.get("type", "String")
        self._max_state_len = 255

        display_name = state_type.get("displayName") or state_type.get("name") or "Unknown"
        self._attr_name = display_name
        self._attr_unique_id = f"{thing_data['id']}_{state_type['id']}"

        nymea_unit = state_type.get("unit")
        native_unit = UNIT_MAP.get(nymea_unit, nymea_unit)
        self._attr_native_unit_of_measurement = native_unit

        self._attr_device_class = infer_device_class(
            thing_data=thing_data,
            state_type=state_type,
            native_unit=native_unit,
        )
        self._attr_state_class = infer_state_class(
            thing_data=thing_data,
            state_type=state_type,
            device_class=self._attr_device_class,
            native_unit=native_unit,
            value_type=self._value_type,
        )

        if self._value_type == "Double":
            self._attr_suggested_display_precision = 2

    @property
    def device_info(self) -> DeviceInfo:
        """Return the Home Assistant device this sensor belongs to."""
        thing_identifier = self._thing_data.get("id", self._attr_unique_id)
        return DeviceInfo(
            identifiers={(DOMAIN, thing_identifier)},
            name=self._thing_data.get("name", "Nymea Thing"),
            manufacturer="Nymea",
            model=self._thing_data.get("thingClassName")
            or self._thing_data.get("thingClassId")
            or "Thing",
            via_device=(DOMAIN, self._server_identifier),
        )

    def _get_live_thing_data(self) -> dict[str, Any]:
        """Return the latest thing data from coordinator."""
        current_thing_id = self._thing_data.get("id")
        for thing in self.coordinator.data or []:
            if thing.get("id") == current_thing_id:
                return thing
        return self._thing_data

    def _get_live_state(self) -> dict[str, Any] | None:
        """Return the current state object."""
        thing = self._get_live_thing_data()
        for state in thing.get("states", []):
            if state.get("stateTypeId") == self._state_type.get("id"):
                return state
        return None

    def _get_live_value(self) -> tuple[Any, Any]:
        """Return converted and raw value."""
        state = self._get_live_state()
        if not state:
            return None, None

        raw_value = state.get("value")
        converted = convert_value(raw_value, self._value_type)
        return converted, raw_value

    @property
    def native_value(self) -> Any:
        """Return the current value in a HA-safe shape."""
        value, _ = self._get_live_value()

        if isinstance(value, (dict, list, tuple, set)):
            return None

        if isinstance(value, str) and len(value) > self._max_state_len:
            return None

        return value

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._get_live_state() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        thing = self._get_live_thing_data()
        value, raw_value = self._get_live_value()

        attributes: dict[str, Any] = {
            ATTR_STATE_TYPE_ID: self._state_type["id"],
            ATTR_STATE_NAME: self._state_type.get("name"),
            "state_value_type": self._value_type,
            "thing_id": self._thing_data.get("id"),
            "thing_name": thing.get("name", self._thing_data.get("name")),
            ATTR_THING_CLASS_ID: thing.get(
                "thingClassId", self._thing_data.get("thingClassId")
            ),
            ATTR_THING_CLASS_NAME: thing.get(
                "thingClassName", self._thing_data.get("thingClassName")
            ),
            "interfaces": thing.get("interfaces", self._thing_data.get("interfaces", [])),
            "nymea_unit": self._state_type.get("unit"),
            "value_type": self._value_type,
        }

        if isinstance(value, (dict, list, tuple, set)):
            attributes[ATTR_VALUE_PAYLOAD] = raw_value
            attributes[ATTR_VALUE_IN_STATE] = False
        elif isinstance(value, str) and len(value) > self._max_state_len:
            attributes[ATTR_VALUE_PAYLOAD] = raw_value
            attributes["value_length"] = len(value)
            attributes[ATTR_VALUE_IN_STATE] = False
        else:
            attributes[ATTR_VALUE_IN_STATE] = True

        return attributes


class NymeaServerInfoSensor(CoordinatorEntity, SensorEntity):
    """Sensor to expose Nymea server information."""

    _attr_has_entity_name = True
    _attr_name = "Server Info"
    _attr_icon = "mdi:server"

    def __init__(self, coordinator, server_info: dict[str, Any], server_identifier: str) -> None:
        """Initialize the server info sensor."""
        super().__init__(coordinator)
        self._server_info = server_info
        self._server_identifier = server_identifier
        self._attr_unique_id = f"{server_identifier}_server_info"

    @property
    def device_info(self) -> DeviceInfo:
        """Return server device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._server_identifier)},
            name=self._server_info.get("name", "Nymea Server"),
            manufacturer="Nymea",
            model=self._server_info.get("server", "Unknown Model"),
            sw_version=self._server_info.get("version", "Unknown"),
        )

    @property
    def native_value(self) -> str | None:
        """Return server version as sensor state."""
        return self._server_info.get("version")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return server attributes."""
        return {
            "uuid": self._server_info.get("uuid"),
            "protocol_version": self._server_info.get("protocol_version"),
            "server_name": self._server_info.get("name"),
            "language": self._server_info.get("language"),
            "locale": self._server_info.get("locale"),
            "experiences": [
                exp.get("name") for exp in self._server_info.get("experiences", []) if isinstance(exp, dict)
            ],
            "authentication_required": self._server_info.get("authentication_required"),
            "initial_setup_required": self._server_info.get("initial_setup_required"),
        }
