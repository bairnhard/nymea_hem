"""Constants for Nymea HEM integration."""

DOMAIN = "nymea_hem"
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

ATTR_DEVICE_ID = "device_id"
ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_TYPE = "device_type"