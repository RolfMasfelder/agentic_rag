"""Raspberry Pi hardware tools for the agent.

Thin wrappers around the raspi-mcp MCP server (streamable-http transport).
The MCP session is initialised lazily on the first call and cached for the
lifetime of the process.  If the server is unreachable a RuntimeError is
raised so the agent can report the failure instead of silently doing nothing.
"""

import json
import logging
import threading
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_session_id: str | None = None
_session_lock = threading.Lock()
_rpc_counter = 0
_rpc_lock = threading.Lock()


def _next_id() -> int:
    global _rpc_counter
    with _rpc_lock:
        _rpc_counter += 1
        return _rpc_counter


def _mcp_url() -> str:
    return getattr(settings, "RASPI_MCP_URL", "http://pi1:8080/mcp")


def _initialize_session() -> str:
    """Perform the MCP initialize handshake and return the session ID."""
    payload = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "agentic-rag", "version": "1.0"},
        },
    }
    try:
        resp = httpx.post(_mcp_url(), json=payload, headers=_MCP_HEADERS, timeout=10)
    except httpx.ConnectError as exc:
        raise RuntimeError(f"raspi-mcp nicht erreichbar unter {_mcp_url()}: {exc}") from exc
    resp.raise_for_status()
    session_id = resp.headers.get("mcp-session-id")
    if not session_id:
        raise RuntimeError("MCP-Server hat keine Session-ID zurückgegeben.")
    logger.debug("MCP-Session initialisiert: %s", session_id)
    return session_id


def _get_session() -> str:
    global _session_id
    with _session_lock:
        if _session_id is None:
            _session_id = _initialize_session()
    return _session_id


def _reset_session() -> None:
    global _session_id
    with _session_lock:
        _session_id = None


def _call_tool(tool_name: str, arguments: dict[str, Any], _retry: bool = True) -> Any:
    """Call a tool on the raspi-mcp server and return the parsed result dict."""
    session_id = _get_session()
    headers = {**_MCP_HEADERS, "Mcp-Session-Id": session_id}
    payload = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    try:
        resp = httpx.post(_mcp_url(), json=payload, headers=headers, timeout=15)
    except httpx.ConnectError as exc:
        raise RuntimeError(f"raspi-mcp nicht erreichbar unter {_mcp_url()}: {exc}") from exc

    if resp.status_code == 400 and _retry:
        # Session abgelaufen — einmal neu initialisieren
        logger.warning("MCP-Session abgelaufen, wird neu initialisiert.")
        _reset_session()
        return _call_tool(tool_name, arguments, _retry=False)

    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"MCP-Fehler bei {tool_name}: {data['error']}")

    # result.content ist eine Liste von {"type": "text", "text": "<json-string>"}
    content = data.get("result", {}).get("content", [])
    if content and content[0].get("type") == "text":
        text = content[0]["text"]
        if not text:
            raise RuntimeError(f"MCP-Tool {tool_name!r} antwortete mit leerem Text-Inhalt.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"MCP-Tool {tool_name!r} lieferte kein gültiges JSON: {text[:120]!r}") from exc
    return data.get("result")


# ---------------------------------------------------------------------------
# LED tools
# ---------------------------------------------------------------------------


def raspi_led_on(pin: int) -> dict[str, Any]:
    """Turn on the LED connected to the given BCM GPIO pin on the Raspberry Pi.

    Args:
        pin: BCM GPIO pin number (1–40).

    Returns:
        Dict with keys ``pin`` and ``state`` ("on").
    """
    return _call_tool("gpio_led_on", {"pin": pin})


def raspi_led_off(pin: int) -> dict[str, Any]:
    """Turn off the LED connected to the given BCM GPIO pin on the Raspberry Pi.

    Args:
        pin: BCM GPIO pin number (1–40).

    Returns:
        Dict with keys ``pin`` and ``state`` ("off").
    """
    return _call_tool("gpio_led_off", {"pin": pin})


def raspi_led_blink(
    pin: int,
    n: int = 3,
    on_time: float = 0.5,
    off_time: float = 0.5,
) -> dict[str, Any]:
    """Blink the LED on the given BCM GPIO pin n times (blocking).

    Args:
        pin: BCM GPIO pin number (1–40).
        n: Number of blink cycles (1–20).
        on_time: Seconds the LED stays on per cycle.
        off_time: Seconds the LED stays off per cycle.

    Returns:
        Dict with keys ``pin``, ``n``, ``on_time``, ``off_time``.
    """
    return _call_tool(
        "gpio_led_blink",
        {"pin": pin, "n": n, "on_time": on_time, "off_time": off_time},
    )


def raspi_led_status(pin: int) -> dict[str, Any]:
    """Return the current state of the LED on the given BCM GPIO pin.

    Args:
        pin: BCM GPIO pin number (1–40).

    Returns:
        Dict with keys ``pin`` and ``state`` ("on" or "off").
    """
    return _call_tool("gpio_led_status", {"pin": pin})


# ---------------------------------------------------------------------------
# Temperature tools
# ---------------------------------------------------------------------------


def raspi_temperature_list_sensors() -> dict[str, Any]:
    """List all connected DS18B20 1-Wire temperature sensors on the Raspberry Pi.

    Returns:
        Dict with keys ``sensors`` (list of sensor IDs) and ``count``.
    """
    return _call_tool("temperature_list_sensors", {})


def raspi_temperature_read(sensor_id: str) -> dict[str, Any]:
    """Read the current temperature from a DS18B20 sensor.

    Args:
        sensor_id: 1-Wire sensor ID as returned by raspi_temperature_list_sensors.

    Returns:
        Dict with keys ``sensor_id``, ``temperature_c``, ``temperature_f``.
    """
    return _call_tool("temperature_read", {"sensor_id": sensor_id})
