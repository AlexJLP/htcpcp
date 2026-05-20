"""
HTCPCP/1.0 — Raw TCP Server
RFC 2324 (coffee) + RFC 7168 (tea)

Usage:
    python server.py
"""

import asyncio
import json
import re
import structlog

from models import (
    DECAF_RESPONSE,
    SUPPORTED_ADDITIONS,
    PotStatus,
    PotType,
    get_pot,
)
from hardware import HardwareController, CONTROLLERS, get_controller
from typing import Any

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

HOST = "0.0.0.0"
PORT = 2324


# ── HTTP helpers ──────────────────────────────────────────────────────────────

STATUS_TEXTS = {
    200: "OK",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    409: "Conflict",
    418: "I'm a Teapot",
    503: "Service Unavailable",
}


def http_response(
    status: int, body: Any, content_type: str = "application/json"
) -> bytes:
    if content_type == "application/json":
        body_bytes = json.dumps(body, indent=2).encode("utf-8")
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    status_text = STATUS_TEXTS.get(status, "Unknown")
    headers = (
        f"HTTP/1.1 {status} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"X-Protocol: HTCPCP/1.0\r\n"
        f"X-RFC: RFC-2324, RFC-7168\r\n"
        f"X-Powered-By: Coffee\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return headers.encode("utf-8") + body_bytes


async def read_request(reader: asyncio.StreamReader) -> bytes:
    """Read until double CRLF, then read Content-Length body if present."""
    raw = b""
    while b"\r\n\r\n" not in raw:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        if not chunk:
            break
        raw += chunk

    head = raw.split(b"\r\n\r\n")[0].decode(errors="replace")
    for line in head.split("\r\n")[1:]:
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1].strip())
            if length > 0:
                body = await asyncio.wait_for(reader.read(length), timeout=5.0)
                raw += body
            break

    return raw


def parse_request(raw: bytes):
    """Returns (method, path, headers, body) or None."""
    try:
        if b"\r\n\r\n" in raw:
            head_bytes, body = raw.split(b"\r\n\r\n", 1)
        else:
            head_bytes, body = raw, b""

        lines = head_bytes.decode(errors="replace").split("\r\n")
        parts = lines[0].split(" ")
        if len(parts) < 2:
            return None

        method = parts[0].upper()
        full_path = parts[1]
        path = full_path.split("?")[0]

        query_params = {}
        if "?" in full_path:
            query_str = full_path.split("?", 1)[1]
            for pair in query_str.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    query_params[k] = v

        headers = {}
        for line in lines[1:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                headers[k.lower()] = v.strip()

        return method, path, headers, body, query_params
    except Exception as e:
        log.error("htcpcp.parse_error", error=str(e))
        return None


def parse_additions(header: str | None) -> dict:
    if not header:
        return {}
    result = {}
    for part in header.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip()
    return result


# ── Handlers ──────────────────────────────────────────────────────────────────


async def handle_brew(pot_id: str, headers: dict, query_params: dict) -> bytes:
    pot = get_pot(pot_id)
    if not pot:
        return http_response(404, {"error": "Not Found", "pot_id": pot_id})

    # RFC 2324 §2.3.2 — teapot → 418, no lock needed, pot_type is immutable
    if pot.pot_type == PotType.TEAPOT:
        log.warning("htcpcp.teapot_detected", pot_id=pot_id)
        return http_response(
            418,
            {
                "status": 418,
                "error": "I'm a teapot",
                "body": "The requested entity body is short and stout.",
                "hint": "Tip me over and pour me out.",
                "pot_id": pot_id,
                "rfc": "RFC 2324 §2.3.2",
                "suggestion": "Try /coffee/pot-1 instead.",
            },
        )

    # Validate additions before acquiring the lock — pure read, no race risk
    additions = parse_additions(headers.get("accept-additions"))

    if "decaf" in additions:
        log.warning("htcpcp.decaf_refused")
        return http_response(
            406,
            {
                "error": "Not Acceptable",
                "message": "Decaffeinated coffee? What's the point?",
                "rfc": "RFC 2324 §2.1.1",
            },
        )

    unsupported = [
        f"{k}={v}"
        for k, v in additions.items()
        if k in SUPPORTED_ADDITIONS and v not in SUPPORTED_ADDITIONS[k]
    ]
    if unsupported:
        return http_response(
            406,
            {
                "error": "Not Acceptable",
                "unsupported_additions": unsupported,
            },
        )

    # ── Critical section — acquire per-pot lock ───────────────────────────────
    # Prevents concurrent BREWs from racing on level/status.
    # Two requests both read level > 0, both proceed → pot goes negative.
    # Not RFC compliant. Definitely not coffee compliant.
    async with pot._lock:

        if not pot.mug_present:
            log.warning("htcpcp.no_mug", pot_id=pot_id)
            return http_response(
                503,
                {
                    "error": "Service Unavailable",
                    "message": "No mug detected. Please place a mug under the spout.",
                    "rfc": "RFC 2324 §2.3.2 (extended)",
                },
            )

        # Validate that recipe exists
        controller = get_controller(pot_id)
        recipe = query_params.get("recipe", "default")
        if controller and recipe not in controller.recipes:
            log.warning("htcpcp.invalid_recipe", pot_id=pot_id, requested_recipe=recipe)
            return http_response(
                400,
                {
                    "error": "Bad Request",
                    "message": f"The recipe '{recipe}' does not exist in the configuration.",
                    "available_recipes": list(controller.recipes.keys()),
                },
            )

        # Validate that pot is not busy
        if pot.status not in [PotStatus.IDLE, PotStatus.READY, PotStatus.NO_MUG]:
            log.warning("htcpcp.pot_busy", pot_id=pot_id, current_status=pot.status)
            return http_response(
                409,
                {
                    "error": "Conflict",
                    "message": "The pot is currently busy with another brewing cycle.",
                    "current_status": pot.status,
                },
            )

        # CAS check — optional header X-Brew-Version for optimistic concurrency
        expected_version = headers.get("x-brew-version")
        if expected_version is not None:
            try:
                if int(expected_version) != pot.brew_version:
                    return http_response(
                        409,
                        {
                            "error": "Conflict",
                            "message": "Pot was modified by a concurrent BREW.",
                            "current_version": pot.brew_version,
                            "hint": "Retry with current brew_version.",
                        },
                    )
            except ValueError:
                return http_response(
                    400,
                    {
                        "error": "Bad Request",
                        "message": "Invalid X-Brew-Version header value. Must be an integer.",
                    },
                )

        record = pot.add_brew(additions)  # increments brew_version
        has_milk = "milk-type" in additions
        pot.status = (
            PotStatus.POURING_MILK if has_milk else PotStatus.DISPENSING_GROUNDS
        )

        # Trigger physical hardware sequence
        if controller:
            asyncio.create_task(controller.run_brew_sequence(recipe))

    # ── End critical section ──────────────────────────────────────────────────

    log.info(
        "htcpcp.brew",
        pot_id=pot_id,
        brew_id=record.id,
        brew_version=pot.brew_version,
        additions=additions,
        milk_pouring=has_milk,
    )
    return http_response(
        200,
        {
            "brew_id": record.id,
            "message": "Coffee is brewing.",
            "pot": pot_id,
            "brew_version": pot.brew_version,
            "accept-additions": additions,
            "milk_pouring": has_milk,
            "when_required": has_milk,
            "protocol": "HTCPCP/1.0",
        },
    )


async def handle_get_status(pot_id: str, _headers: dict, _query_params: dict) -> bytes:
    pot = get_pot(pot_id)
    if not pot:
        return http_response(404, {"error": "Not Found", "pot_id": pot_id})
    return http_response(200, pot.to_dict())


async def handle_get_history(pot_id: str, _headers: dict, _query_params: dict) -> bytes:
    pot = get_pot(pot_id)
    if not pot:
        return http_response(404, {"error": "Not Found", "pot_id": pot_id})
    return http_response(
        200,
        {
            "pot_id": pot_id,
            "total_brews": len(pot.brew_history),
            "brews": [r.to_dict() for r in pot.brew_history],
        },
    )


async def handle_propfind(pot_id: str, _headers: dict, _query_params: dict) -> bytes:
    pot = get_pot(pot_id)
    if not pot:
        return http_response(404, {"error": "Not Found", "pot_id": pot_id})
    return http_response(
        200,
        {
            **SUPPORTED_ADDITIONS,
            "decaf": DECAF_RESPONSE,
            "rfc": "RFC 2324 §2.1.1",
        },
    )


async def handle_when(pot_id: str, _headers: dict, _query_params: dict) -> bytes:
    pot = get_pot(pot_id)
    if not pot:
        return http_response(404, {"error": "Not Found", "pot_id": pot_id})

    async with pot._lock:
        if pot.status != PotStatus.POURING_MILK:
            return http_response(
                200,
                {
                    "message": "WHEN acknowledged.",
                    "note": "No milk was being poured, but your enthusiasm is appreciated.",
                    "rfc": "RFC 2324 §2.1.3",
                },
            )

        pot.status = PotStatus.BREWING

    log.info("htcpcp.when_milk_stopped", pot_id=pot_id)
    return http_response(
        200,
        {
            "message": "Milk pouring stopped.",
            "detail": "The server acknowledged WHEN and stopped the milk stream.",
            "current_status": pot.status,
            "rfc": "RFC 2324 §2.1.3",
        },
    )


async def handle_dashboard(_id, _headers: dict, _query_params: dict) -> bytes:
    try:
        with open("index.html", "r") as f:
            html = f.read()
        return http_response(200, html, content_type="text/html")
    except FileNotFoundError:
        return http_response(
            404, "Dashboard file not found.", content_type="text/plain"
        )


async def handle_static(filename: str, _headers: dict, _query_params: dict) -> bytes:
    import os
    import mimetypes

    if not filename or ".." in filename or not os.path.exists(filename):
        return http_response(404, "File not found.", content_type="text/plain")

    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"

    try:
        with open(filename, "rb") as f:
            content = f.read()
        return http_response(200, content, content_type=content_type)
    except Exception as e:
        return http_response(500, str(e), content_type="text/plain")


async def handle_api_recipes(_id, _headers: dict, _query_params: dict) -> bytes:
    from hardware import CONTROLLERS

    controller = CONTROLLERS.get("pot-1")
    if not controller:
        return http_response(404, {"error": "Controller not found"})
    return http_response(
        200, {"recipes": controller.recipes, "calibration": controller.calibration}
    )


async def handle_api_pots(_id, _headers: dict, _query_params: dict) -> bytes:
    from models import POT_REGISTRY

    pots = [{"id": pot.id, "name": uri} for uri, pot in POT_REGISTRY.items()]
    return http_response(200, pots)


async def handle_api_status(_id, _headers: dict, _query_params: dict) -> bytes:
    """JSON status for the web UI."""
    from models import get_pot

    pot_id = _query_params.get("pot", "pot-1")
    pot = get_pot(pot_id)
    if not pot:
        return http_response(404, {"error": "Pot not found"})
    return http_response(
        200,
        {
            "id": pot.id,
            "status": pot.status.name.replace("_", " "),
            "temperature": pot.temperature,
            "mug_present": pot.mug_present,
            "level": pot.level,
            "current_phase": pot.current_phase,
            "progress": pot.progress,
        },
    )


# ── Router ────────────────────────────────────────────────────────────────────

ROUTES = [
    (re.compile(r"^/coffee/([^/]+)$"), {"BREW": handle_brew, "POST": handle_brew}),
    (re.compile(r"^/coffee/([^/]+)/status$"), {"GET": handle_get_status}),
    (re.compile(r"^/coffee/([^/]+)/history$"), {"GET": handle_get_history}),
    (re.compile(r"^/coffee/([^/]+)/additions$"), {"PROPFIND": handle_propfind}),
    (re.compile(r"^/coffee/([^/]+)/stop-milk$"), {"WHEN": handle_when}),
    (re.compile(r"^/api/recipes$"), {"GET": handle_api_recipes}),
    (re.compile(r"^/api/pots$"), {"GET": handle_api_pots}),
    (re.compile(r"^/api/status$"), {"GET": handle_api_status}),
    (re.compile(r"^/htcpcp-docs$"), {"GET": handle_docs_info}),
    (re.compile(r"^/(.*\.jpg)$"), {"GET": handle_static}),
    (re.compile(r"^/(.*\.js)$"), {"GET": handle_static}),
    (re.compile(r"^/(.*\.css)$"), {"GET": handle_static}),
    (re.compile(r"^/$"), {"GET": handle_dashboard}),
]


async def dispatch(method: str, path: str, headers: dict, query_params: dict) -> bytes:
    if method == "BREW" and not path.startswith("/coffee/"):
        return http_response(
            418,
            {
                "error": "Wrong universe",
                "hint": "BREW is only valid on /coffee/{pot_id}",
                "rfc": "RFC 2324 §2.1",
            },
        )

    for pattern, method_map in ROUTES:
        m = pattern.match(path)
        if m:
            pot_id = m.group(1) if m.lastindex else None
            handler = method_map.get(method)
            if handler is None:
                return http_response(
                    405,
                    {
                        "error": "Method Not Allowed",
                        "allowed": list(method_map.keys()),
                    },
                )
            return await handler(pot_id, headers, query_params)

    return http_response(404, {"error": "Not Found", "path": path})


# ── TCP server ────────────────────────────────────────────────────────────────


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    try:
        raw = await read_request(reader)
        if not raw:
            return

        parsed = parse_request(raw)
        if not parsed:
            writer.write(
                b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            await writer.drain()
            return

        method, path, headers, body, query_params = parsed
        log.info(
            "htcpcp.request",
            method=method,
            path=path,
            peer=str(peer),
            query=query_params,
        )

        response = await dispatch(method, path, headers, query_params)
        writer.write(response)
        await writer.drain()

    except asyncio.TimeoutError:
        log.warning("htcpcp.timeout", peer=str(peer))
    except Exception as e:
        log.error("htcpcp.error", error=str(e), peer=str(peer))
        try:
            writer.write(
                b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            await writer.drain()
        except Exception:
            pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def main():
    server = await asyncio.start_server(handle_connection, HOST, PORT)
    log.info(
        "htcpcp.startup",
        protocol="HTCPCP/1.0",
        host=HOST,
        port=PORT,
    )
    print(f"\n☕  HTCPCP/1.0 — RFC 2324  ({HOST}:{PORT})\n")
    print(f"    curl -X BREW http://{HOST}:{PORT}/coffee/pot-1 \\")
    print(f'         -H "Accept-Additions: milk-type=Whole-milk; alcohol-type=Whisky"')
    print(f"\n    # Optimistic concurrency:")
    print(f"    curl -X BREW http://{HOST}:{PORT}/coffee/pot-1 \\")
    print(f'         -H "X-Brew-Version: 0"  # → 409 if pot was modified\n')
    # Initialize Hardware Controllers
    from models import POT_REGISTRY

    use_mock = False  # Default to mock for TCP server unless changed
    for uri, pot in POT_REGISTRY.items():
        pot_id = uri.split("://")[-1]
        controller = HardwareController(pot, use_mock=use_mock)
        CONTROLLERS[pot_id] = controller
        asyncio.create_task(controller.update_loop())

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
