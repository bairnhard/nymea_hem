"""Async client for the nymea JSON-RPC API."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Any

_LOGGER = logging.getLogger(__name__)


class NymeaError(Exception):
    """Base exception raised by the nymea client."""


class NymeaRequestTimeout(NymeaError):
    """The server did not answer a request within the expected time."""


class NymeaClient:
    """Client for Nymea HEM JSON-RPC communication."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        ssl_enabled: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssl_enabled = ssl_enabled
        self._token: str | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connection_timeout = 10
        self._read_timeout = 15
        self._request_id = 0
        self._receive_buffer = ""
        # A StreamReader may only have one active reader. All requests, including
        # reconnect/authentication, therefore share one lock.
        self._request_lock = asyncio.Lock()
        self._server_info: dict[str, Any] = {}

    def is_connected(self) -> bool:
        """Return whether the socket is open."""
        return bool(
            self._reader
            and self._writer
            and not self._writer.is_closing()
        )

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create a TLS context without loading system certificates.

        Consolinno appliances commonly use a self-signed certificate. Building
        this minimal context also avoids blocking certificate-store I/O in HA's
        event loop.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    async def _connect_locked(self) -> None:
        if self.is_connected():
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._host,
                    self._port,
                    ssl=self._create_ssl_context() if self._ssl_enabled else None,
                ),
                timeout=self._connection_timeout,
            )
        except (asyncio.TimeoutError, OSError) as err:
            raise ConnectionError(
                f"Could not connect to {self._host}:{self._port}: {err}"
            ) from err
        _LOGGER.info("Successfully connected to %s:%d", self._host, self._port)

    async def _read_response_locked(
        self, request_id: int, timeout: float | None = None
    ) -> dict[str, Any]:
        """Read JSON objects until the response for request_id arrives."""
        assert self._reader is not None
        decoder = json.JSONDecoder()
        read_timeout = self._read_timeout if timeout is None else timeout
        while True:
            while self._receive_buffer.lstrip():
                stripped = self._receive_buffer.lstrip()
                try:
                    message, end = decoder.raw_decode(stripped)
                except json.JSONDecodeError:
                    break
                self._receive_buffer = stripped[end:]
                if not isinstance(message, dict):
                    continue
                if message.get("id") == request_id:
                    return message
                _LOGGER.debug(
                    "Ignoring unsolicited or late nymea message id=%s while "
                    "waiting for id=%s",
                    message.get("id"),
                    request_id,
                )

            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(4096), timeout=read_timeout
                )
            except asyncio.TimeoutError as err:
                raise NymeaRequestTimeout(
                    f"No response for request {request_id} within {read_timeout} seconds"
                ) from err
            if not chunk:
                raise ConnectionError("Connection closed by remote host")
            self._receive_buffer += chunk.decode()

    async def _send_locked(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        include_token: bool = True,
        response_timeout: float | None = None,
    ) -> dict[str, Any]:
        assert self._writer is not None
        request_id = self._next_request_id()
        request: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        if include_token and self._token:
            request["token"] = self._token

        # Never log the authentication token or password.
        _LOGGER.debug("Sending nymea request id=%s method=%s", request_id, method)
        self._writer.write((json.dumps(request) + "\n").encode())
        await self._writer.drain()
        response = await self._read_response_locked(request_id, response_timeout)
        if response.get("status") != "success":
            raise NymeaError(
                f"{method} failed: {response.get('error', 'Unknown error')}"
            )
        return response

    async def _authenticate_locked(self) -> None:
        await self._close_locked()
        await self._connect_locked()
        hello = await self._send_locked("JSONRPC.Hello", include_token=False)
        hello_params = hello.get("params", {})
        self._server_info = {
            "authentication_required": hello_params.get("authenticationRequired"),
            "experiences": hello_params.get("experiences", []),
            "initial_setup_required": hello_params.get("initialSetupRequired"),
            "language": hello_params.get("language"),
            "locale": hello_params.get("locale"),
            "name": hello_params.get("name"),
            "protocol_version": hello_params.get("protocol version"),
            "server": hello_params.get("server"),
            "uuid": hello_params.get("uuid"),
            "version": hello_params.get("version"),
        }
        auth = await self._send_locked(
            "JSONRPC.Authenticate",
            {
                "username": self._username,
                "password": self._password,
                "deviceName": "HomeAssistant",
            },
            include_token=False,
        )
        auth_params = auth.get("params", {})
        if not auth_params.get("success", False) or not auth_params.get("token"):
            raise NymeaError("Authentication failed")
        self._token = auth_params["token"]
        _LOGGER.info(
            "Authenticated with %s (version %s)",
            self._server_info.get("name"),
            self._server_info.get("version"),
        )

    async def authenticate(self) -> None:
        """Create a fresh authenticated session."""
        async with self._request_lock:
            try:
                await self._authenticate_locked()
            except Exception:
                await self._close_locked()
                raise

    async def _rpc_call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        response_timeout: float | None = None,
    ) -> dict[str, Any]:
        async with self._request_lock:
            try:
                if not self.is_connected() or not self._token:
                    await self._authenticate_locked()
                return await self._send_locked(
                    method, params, response_timeout=response_timeout
                )
            except NymeaRequestTimeout:
                # A timed-out command may still be running on the appliance.
                # Keep the healthy socket open so a late response can be
                # discarded by request id and the state can be read back.
                raise
            except Exception:
                await self._close_locked()
                raise

    async def get_things(self) -> list[dict[str, Any]]:
        """Retrieve all configured things."""
        response = await self._rpc_call("Integrations.GetThings")
        things = response.get("params", {}).get("things", [])
        _LOGGER.info("Retrieved %d devices from Nymea", len(things))
        return things

    async def get_thing_class_details(
        self, thing_class_id: str
    ) -> list[dict[str, Any]]:
        """Retrieve complete metadata for one thing class."""
        response = await self._rpc_call(
            "Integrations.GetThingClasses", {"thingClassIds": [thing_class_id]}
        )
        return response.get("params", {}).get("thingClasses", [])

    async def execute_action(
        self,
        thing_id: str,
        action_type_id: str,
        action_params: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Execute an action and return whether nymea confirmed completion.

        Consolinno may apply a command but either answer late or return
        ThingErrorTimeout. Both cases mean "unconfirmed", not "rejected".
        """
        params: dict[str, Any] = {
            "thingId": thing_id,
            "actionTypeId": action_type_id,
        }
        if action_params:
            params["params"] = action_params
        _LOGGER.info(
            "Executing nymea action thing=%s actionType=%s paramTypes=%s",
            thing_id,
            action_type_id,
            [item.get("paramTypeId") for item in action_params or []],
        )
        try:
            response = await self._rpc_call(
                "Integrations.ExecuteAction", params, response_timeout=5
            )
        except NymeaRequestTimeout:
            _LOGGER.info(
                "Nymea action %s was not confirmed in time; keeping the "
                "connection open and refreshing its state",
                action_type_id,
            )
            return False
        result = response.get("params", {})
        thing_error = result.get("thingError")
        if thing_error == "ThingErrorTimeout":
            _LOGGER.info(
                "Nymea action %s returned ThingErrorTimeout; the command may "
                "still have been applied and its state will be refreshed",
                action_type_id,
            )
            return False
        if thing_error not in (None, "ThingErrorNoError", 0):
            message = result.get("displayMessage") or thing_error
            raise NymeaError(f"Action failed: {message}")
        _LOGGER.info("Nymea action %s completed successfully", action_type_id)
        return True

    async def _close_locked(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        self._token = None
        self._receive_buffer = ""
        if writer:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError, ssl.SSLError):
                pass

    async def close_connection(self) -> None:
        """Close the connection safely."""
        async with self._request_lock:
            await self._close_locked()
