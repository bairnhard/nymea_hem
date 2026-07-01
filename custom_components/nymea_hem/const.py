"""Constants for Nymea HEM integration."""

from homeassistant.const import Platform

DOMAIN = "nymea_hem"

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SSL = "ssl"
CONF_POLL_INTERVAL = "poll_interval"

DEFAULT_PORT = 2222
DEFAULT_SSL = True
DEFAULT_POLL_INTERVAL = 60

JSONRPC_HELLO_METHOD = "JSONRPC.Hello"
JSONRPC_AUTH_METHOD = "JSONRPC.Authenticate"
INTEGRATIONS_GET_THINGS = "Integrations.GetThings"
INTEGRATIONS_GET_THING_STATE = "Integrations.GetThingState"
INTEGRATIONS_GET_THING_CLASSES = "Integrations.GetThingClasses"

ATTR_DEVICE_ID = "device_id"
ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_TYPE = "device_type"
ATTR_THING_CLASS_ID = "thing_class_id"
ATTR_THING_CLASS_NAME = "thing_class_name"
ATTR_STATE_TYPE_ID = "state_type_id"
ATTR_STATE_NAME = "state_name"
ATTR_VALUE_IN_STATE = "value_in_state"
ATTR_VALUE_PAYLOAD = "value_payload"
