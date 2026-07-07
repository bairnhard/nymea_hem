import asyncio
import json
import ssl
import logging
from typing import Optional, Dict, Any

_LOGGER = logging.getLogger(__name__)


@property
def server_info(self) -> dict[str, Any]:
    """Return cached server info from handshake."""
    return getattr(self, "_server_info", {})


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
        self._connection_timeout = 10  # seconds
        self._read_timeout = 15  # seconds

    def is_connected(self) -> bool:
        """Check if the connection is currently active."""
        if not self._reader or not self._writer:
            _LOGGER.debug("Connection check: No reader/writer")
            return False
        
        if self._writer.is_closing():
            _LOGGER.debug("Connection check: Writer is closed")
            return False
            
        return True

    async def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for secure connection."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    async def _connect(self):
        """Establish connection with SSL/TLS or plain socket."""
        if self.is_connected():
            _LOGGER.debug("Reusing existing connection.")
            return

        ssl_context = await self._create_ssl_context() if self._ssl_enabled else None
        try:
            _LOGGER.debug(
                "Attempting to connect to %s:%d (SSL: %s)",
                self._host,
                self._port,
                self._ssl_enabled
            )
            
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._host,
                    self._port,
                    ssl=ssl_context
                ),
                timeout=self._connection_timeout
            )
            _LOGGER.info("Successfully connected to %s:%d", self._host, self._port)
            
        except asyncio.TimeoutError as e:
            _LOGGER.error(
                "Connection timeout after %d seconds to %s:%d",
                self._connection_timeout,
                self._host,
                self._port
            )
            raise ConnectionError(f"Connection timeout to {self._host}:{self._port}") from e
            
        except (ConnectionRefusedError, OSError) as e:
            _LOGGER.error(
                "Failed to connect to %s:%d: %s",
                self._host,
                self._port,
                e
            )
            raise ConnectionError(f"Connection refused to {self._host}:{self._port}") from e
            
        except Exception as e:
            _LOGGER.error("Unexpected connection error: %s", e)
            raise

    async def _read_full_response(self) -> str:
        """Read a full JSON response from the reader."""
        buffer = ""
        try:
            while True:
                chunk = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=self._read_timeout
                )
                if not chunk:
                    _LOGGER.warning("Connection closed by server")
                    raise ConnectionError("Connection closed by remote host")
                    
                buffer += chunk.decode()
                try:
                    json.loads(buffer)  # Validate if JSON is complete
                    return buffer
                except json.JSONDecodeError:
                    continue
                    
        except asyncio.TimeoutError as e:
            _LOGGER.error("Read timeout after %d seconds", self._read_timeout)
            raise ConnectionError("Read timeout from server") from e
            
        except Exception as e:
            if isinstance(e, ConnectionError):
                raise
            _LOGGER.error("Error reading response: %s", e)
            raise ConnectionError(f"Failed to read response: {e}") from e

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
            _LOGGER.debug("Hello Response received")
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
            _LOGGER.info("Server handshake successful: %s (version: %s)", 
                        self._server_info.get("name"), 
                        self._server_info.get("version"))

        except Exception as e:
            _LOGGER.error("Error during handshake: %s", e)
            # Close connection on handshake failure
            await self.close_connection()
            raise


    async def authenticate(self):
        """Authenticate and establish session."""
        try:
            _LOGGER.debug("Starting authentication process")
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
            _LOGGER.debug("Authentication response received")

            auth_data = json.loads(auth_response)
            if not auth_data.get("params", {}).get("success", False):
                _LOGGER.error("Authentication failed: Invalid credentials or server error")
                raise ValueError("Authentication failed.")
                
            self._token = auth_data["params"]["token"]
            _LOGGER.info("Successfully authenticated and received token")

        except Exception as e:
            _LOGGER.error("Authentication error: %s", e)
            await self.close_connection()
            raise
        
    async def close_connection(self):
        """Close the writer connection gracefully, with fallback to forceful closure."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
                _LOGGER.debug("Connection closed cleanly.")
            except Exception as e:
                _LOGGER.debug("Error during clean close: %s", e)
                try:
                    self._writer.transport.abort()
                    _LOGGER.debug("Connection forcefully closed.")
                except Exception as inner_e:
                    _LOGGER.debug("Error during force close: %s", inner_e)
            finally:
                self._reader = None
                self._writer = None

    async def _ensure_authenticated(self):
        """Ensure the connection is established and authenticated."""
        try:
            if not self.is_connected():
                _LOGGER.debug("No active connection. Re-authenticating...")
                await self.authenticate()
            elif not self._token:
                _LOGGER.debug("No valid token. Re-authenticating...")
                await self.authenticate()
        except Exception as e:
            _LOGGER.error("Error ensuring authentication: %s", e)
            await self.close_connection()
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
            _LOGGER.debug("Things response received")

            things_data = json.loads(things_response)
            devices = things_data.get("params", {}).get("things", [])
            _LOGGER.info("Retrieved %d devices from Nymea", len(devices))
            return devices
            
        except ConnectionError as e:
            _LOGGER.error("Connection error while fetching things: %s", e)
            await self.close_connection()
            raise
            
        except Exception as e:
            _LOGGER.error("Error fetching things: %s", e)
            await self.close_connection()
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
            _LOGGER.debug("Thing class details response received")

            data = json.loads(response)
            if data.get("status") == "success":
                return data.get("params", {}).get("thingClasses", [])
            else:
                raise ValueError(f"Error fetching thing class details: {data.get('error')}")

        except ConnectionError as e:
            _LOGGER.error("Connection error while fetching thing class details: %s", e)
            await self.close_connection()
            raise
            
        except Exception as e:
            _LOGGER.error("Error in get_thing_class_details: %s", e)
            raise
