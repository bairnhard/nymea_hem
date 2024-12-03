from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_FREQUENCY,

    UnitOfTemperature,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfFrequency,
    UnitOfTime,
)

from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

UNIT_MAP = {
    "UnitAmpere": UnitOfElectricCurrent.AMPERE,
    "UnitDegreeCelsius": UnitOfTemperature.CELSIUS,
    "UnitEuroCentPerKiloWattHour": "€/kWh",
    "UnitHertz": UnitOfFrequency.HERTZ,
    "UnitHours": UnitOfTime.HOURS,
    "UnitKiloWattHour": UnitOfEnergy.KILO_WATT_HOUR,
    "UnitLux": "lx",
    "UnitMinutes": UnitOfTime.MINUTES,
    "UnitNone": None,
    "UnitOhm": "Ω",
    "UnitPartsPerMillion": "ppm",
    "UnitPercentage": "%",
    "UnitSeconds": UnitOfTime.SECONDS,
    "UnitUnixTime": "Unix Time",
    "UnitVolt": UnitOfElectricPotential.VOLT,
    "UnitVoltAmpereReactive": "VAR",
    "UnitWatt": UnitOfPower.WATT,
}

INTERFACE_DEVICE_CLASS_MAP = {
    "temperaturesensor": DEVICE_CLASS_TEMPERATURE,
    "energymeter": DEVICE_CLASS_ENERGY,
    "smartmeter": DEVICE_CLASS_ENERGY,
    "smartmeterproducer": DEVICE_CLASS_POWER,
    "powersocket": DEVICE_CLASS_POWER,
    "humiditysensor": "humidity", 
}


# Type conversion helpers
def convert_value(value, value_type):
    """Convert value based on type."""
    type_converters = {
        'Bool': lambda x: bool(x),
        'Double': lambda x: float(x),
        'Int': lambda x: int(x),
        'Uint': lambda x: abs(int(x)),
        'String': lambda x: str(x),
        # Default is to return as-is
        'Object': lambda x: x,
        'Color': lambda x: x
    }
    
    converter = type_converters.get(value_type, lambda x: x)
    try:
        return converter(value)
    except (ValueError, TypeError):
        _LOGGER.warning(f"Could not convert {value} to {value_type}")
        return value


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Nymea sensors dynamically based on states."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]

    sensors = []

    for thing in coordinator.data:
        thing_class_id = thing.get("thingClassId")
        
        # Fetch thing class details
        try:
            thing_class_details = await client.get_thing_class_details(thing_class_id)
            if thing_class_details:
                thing['thingClassDetails'] = thing_class_details[0]
            else:
                _LOGGER.warning(f"No class details found for thing: {thing.get('name')}")
                continue
        except Exception as e:
            _LOGGER.error(f"Error fetching thing class details for {thing.get('name')}: {e}")
            continue

        # Create sensors for each state
        for state in thing.get("states", []):
            state_type = next(
                (
                    t
                    for t in thing['thingClassDetails'].get("stateTypes", [])
                    if t["id"] == state["stateTypeId"]
                ),
                None
            )
            
            if state_type:
                sensors.append(
                    NymeaHEMStateSensor(
                        coordinator, 
                        thing, 
                        state_type
                    )
                )

    async_add_entities(sensors)


class NymeaHEMStateSensor(CoordinatorEntity, SensorEntity):
    """Representation of a single state from a thing."""

    def __init__(self, coordinator, thing_data, state_type):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._thing_data = thing_data
        self._state_type = state_type
        
        # Construct name with fallback
        display_name = state_type.get('displayName', state_type.get('name', 'Unknown'))
        self._attr_name = f"{thing_data['name']} {display_name}"
        
        # Unique ID with fallback
        self._attr_unique_id = f"{thing_data['id']}_{state_type['id']}"
        
        # Convert unit and Interface
        nymea_unit = state_type.get("unit")
        self._attr_unit_of_measurement = UNIT_MAP.get(nymea_unit, nymea_unit)
        self._attr_device_class = INTERFACE_DEVICE_CLASS_MAP.get(
            thing_data.get("interfaces", [None])[0], None
        )
        
        # Determine state type for conversion
        self._value_type = state_type.get('type', 'String')

    @property
    def native_value(self):
        """Return the current value of the state with type conversion."""
        for state in self._thing_data.get("states", []):
            if state["stateTypeId"] == self._state_type["id"]:
                value = state.get("value", "Unknown")
                return convert_value(value, self._value_type)
        return "Unknown"

    @property
    def extra_state_attributes(self):
        """Return additional attributes with HASS-friendly formatting."""
        return {
            "state_type_id": self._state_type["id"],
            "state_name": self._state_type["name"],
            "state_type": self._value_type,
            "thing_id": self._thing_data["id"],
            "unit": self._attr_unit_of_measurement,
            "thing_name": self._thing_data['name'],
            "thing_class_id": self._thing_data.get("thingClassId"),
            "interfaces": self._thing_data.get("interfaces", []),
            "thing_class_name": self._thing_data.get("thingClassName")
        }