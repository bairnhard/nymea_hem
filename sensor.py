from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import async_get
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import SensorDeviceClass

from homeassistant.const import (
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
    "temperaturesensor": SensorDeviceClass.TEMPERATURE,
    "energymeter": SensorDeviceClass.ENERGY,
    "smartmeter": SensorDeviceClass.ENERGY,
    "smartmeterproducer": SensorDeviceClass.POWER,
    "powersocket": SensorDeviceClass.POWER,
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
    """Set up sensors for the Nymea integration."""
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    server_info = hass.data[DOMAIN].get("server_info", {})
    
    device_registry = async_get(hass)
    
    nymea_server_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, server_info.get("uuid", "unknown_uuid"))},
        name=server_info.get("name", "Nymea Server"),
        manufacturer="Nymea",
        model=server_info.get("server", "Unknown Model"),
        sw_version=server_info.get("version", "Unknown"),
    )

    sensors = []
    
    # Add Nymea Server Info sensor
    sensors.append(
        NymeaServerInfoSensor(
            coordinator, 
            "Nymea Server Info", 
            server_info,
            device_id=nymea_server_device.id
        )
    )


    # Fetch all devices and their states

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
                        state_type,
                        device_id=nymea_server_device.id
                    )
                )    
    async_add_entities(sensors)


class NymeaHEMStateSensor(CoordinatorEntity, SensorEntity):    
    """Representation of a single state from a thing."""

    def __init__(self, coordinator, thing_data, state_type, device_id=None):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._thing_data = thing_data
        self._state_type = state_type
        self._device_id = device_id
        
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
        
class NymeaServerInfoSensor(CoordinatorEntity):
    """Sensor to display Nymea server information."""

    def __init__(self, coordinator, name, server_info, device_id=None):
        """Initialize the server info sensor."""
        super().__init__(coordinator)
        self._name = name
        self._server_info = server_info
        self._device_id = device_id

    @property
    def device_info(self):
        """Return device information if available."""
        if self._device_id:
            return DeviceInfo(
                identifiers={(DOMAIN, self._server_info.get("uuid", "unknown_uuid"))},
                name=self._server_info.get("name", "Nymea Server"),
                manufacturer="Nymea",
                model=self._server_info.get("server", "Unknown Model"),
                sw_version=self._server_info.get("version", "Unknown"),                
            )

    @property
    def name(self):
        return f"{self._server_info.get('name')} Server Info"

    @property
    def state(self):    
        return self._server_info.get("version")

    @property
    def extra_state_attributes(self):
        """Return other attributes of the server."""
        return {
            "uuid": self._server_info.get("uuid"),
            "protocol_version": self._server_info.get("protocol version"),
            "server_name": self._server_info.get("name"),
            "language": self._server_info.get("language"),
            "locale": self._server_info.get("locale"),
            "experiences": [exp["name"] for exp in self._server_info.get("experiences", [])],
        }

    @property
    def icon(self):        
        return "mdi:server"