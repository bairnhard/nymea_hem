import asyncio
import json
import ssl
import logging
from typing import Optional, Dict, Any

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)  # Enable detailed logging for debugging


class NymeaClient:
    """Client for Nymea HEM JSON-RPC communication."""

    def __init__(self, host: str, port: int, username: str, password: str, ssl_enabled: bool = True):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssl_enabled = ssl_enabled
        self._token = None
        self._reader = None
        self._writer = None

    async def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for secure connection."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    async def _connect(self):
        """Establish connection with SSL/TLS or plain socket."""
        if self._reader and self._writer:
            _LOGGER.debug("Reusing existing connection.")
            return

        ssl_context = await self._create_ssl_context() if self._ssl_enabled else None
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host,
                self._port,
                ssl=ssl_context
            )
            _LOGGER.debug(f"Connected to {self._host}:{self._port}")
        except Exception as e:
            _LOGGER.error(f"Connection error: {e}")
            raise

    async def _read_full_response(self) -> str:
        """Read a full JSON response from the reader."""
        buffer = ""
        while True:
            chunk = await self._reader.read(4096)
            if not chunk:
                break
            buffer += chunk.decode()
            try:
                json.loads(buffer)  # Validate if JSON is complete
                return buffer
            except json.JSONDecodeError:
                continue
        raise ValueError("Incomplete JSON response")

    async def _handshake(self):
        """Perform the JSONRPC.Hello handshake."""
        await self._connect()

        hello_message = {
            "id": 1,
            "method": "JSONRPC.Hello"
        }
        if self._token:
            # Include the token in the handshake if it's available
            hello_message["token"] = self._token

        try:
            self._writer.write((json.dumps(hello_message) + "\n").encode())
            await self._writer.drain()
            hello_response = await self._read_full_response()
            _LOGGER.debug(f"Hello Response: {hello_response}")
            response_data = json.loads(hello_response)

            if response_data.get("status") != "success":
                error = response_data.get("error", "Unknown error")
                raise ValueError(f"Handshake failed: {error}")

            # Store server details
            params = response_data.get("params", {})
            self._server_info = {
                "authentication_required": params.get("authenticationRequired"),
                "experiences": params.get("experiences", []),
                "initial_setup_required": params.get("initialSetupRequired"),
                "language": params.get("language"),
                "locale": params.get("locale"),
                "name": params.get("name"),
                "protocol_version": params.get("protocol version"),
                "server": params.get("server"),
                "uuid": params.get("uuid"),
                "version": params.get("version"),                
            }
            _LOGGER.info(f"Server Info: {self._server_info}")

        except Exception as e:
            _LOGGER.error(f"Error during handshake: {e}")
            raise


    async def authenticate(self):
        """Authenticate and establish session."""
        try:
            await self._connect()
            await self._handshake()

            auth_message = json.dumps({
                "id": 2,
                "method": "JSONRPC.Authenticate",
                "params": {
                    "username": self._username,
                    "password": self._password,
                    "deviceName": "HomeAssistant"
                }
            }) + "\n"
            self._writer.write(auth_message.encode())
            await self._writer.drain()
            auth_response = await self._read_full_response()
            _LOGGER.debug(f"Auth Response: {auth_response}")

            auth_data = json.loads(auth_response)
            if not auth_data.get("params", {}).get("success", False):
                _LOGGER.error("Authentication failed.")
                raise ValueError("Authentication failed.")
            self._token = auth_data["params"]["token"]
            _LOGGER.info(f"Authenticated successfully. Token: {self._token}")

        except Exception as e:
            _LOGGER.error(f"Authentication error: {e}")
            raise
        
    async def close_connection(self):
        """Close the writer connection gracefully, with fallback to forceful closure."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
                _LOGGER.debug("Connection closed cleanly.")
            except Exception as e:
                _LOGGER.warning(f"Error closing connection: {e}")
                self._writer.transport.abort()
                _LOGGER.debug("Connection forcefully closed.")
            finally:
                self._reader = None
                self._writer = None

    async def _ensure_authenticated(self):
        """Ensure the connection is established and authenticated."""
        try:
            if not self._reader or not self._writer:
                _LOGGER.debug("No active connection. Re-authenticating...")
                await self.authenticate()
            elif not self._token:
                _LOGGER.debug("No valid token. Re-authenticating...")
                await self.authenticate()
        except Exception as e:
            _LOGGER.error(f"Error ensuring authentication: {e}")
            raise

    async def get_things(self):
        """Retrieve all Nymea things/devices."""
        await self._ensure_authenticated()

        try:
            get_things_message = json.dumps({
                "id": 3,
                "method": "Integrations.GetThings",
                "token": self._token
            }) + "\n"
            self._writer.write(get_things_message.encode())
            await self._writer.drain()
            things_response = await self._read_full_response()
            _LOGGER.debug(f"Things Response: {things_response}")

            things_data = json.loads(things_response)
            devices = things_data.get("params", {}).get("things", [])
            _LOGGER.info(f"Retrieved {len(devices)} devices.")
            return devices
        except Exception as e:
            _LOGGER.error(f"Error fetching things: {e}")
            raise

    async def get_thing_class_details(self, thing_class_id):
        """
        Fetch details for a specific thing class.

        :param thing_class_id: UUID of the thing class.
        :return: Dictionary containing the thing class details.
        """
        await self._ensure_authenticated()

        request = {
            "id": 5,  # Unique ID for the request
            "method": "Integrations.GetThingClasses",
            "params": {
                "thingClassIds": [thing_class_id]
            },
            "token": self._token
        }

        try:
            self._writer.write((json.dumps(request) + "\n").encode())
            await self._writer.drain()
            response = await self._read_full_response()
            _LOGGER.debug(f"Thing Class Details Response: {response}")

            data = json.loads(response)
            if data.get("status") == "success":
                return data.get("params", {}).get("thingClasses", [])
            else:
                raise ValueError(f"Error fetching thing class details: {data.get('error')}")

        except Exception as e:
            _LOGGER.error(f"Error in get_thing_class_details: {e}")
            raise


