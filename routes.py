"""
HTCPCP/1.0 — Routes
Implements: BREW, GET, PROPFIND, WHEN
RFC 2324 (coffee) + RFC 7168 (tea)
"""

import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
import os

from models import (
    DECAF_RESPONSE,
    SUPPORTED_ADDITIONS,
    CoffeePot,
    PotStatus,
    PotType,
    get_pot,
)
from hardware import get_controller
router = APIRouter()
log = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────────

def resolve_pot(pot_id: str) -> CoffeePot:
    pot = get_pot(pot_id)
    if not pot:
        raise HTTPException(status_code=404, detail={
            "error": "Not Found",
            "message": f"No pot registered at coffee://{pot_id} or tea://{pot_id}",
            "registered_pots": ["pot-1", "pot-2", "kettle-1", "kettle-2"],
        })
    return pot


def parse_accept_additions(header: str | None) -> dict[str, str]:
    """
    Parse the Accept-Additions header.
    Format: 'milk-type=Whole-milk; syrup-type=Vanilla; alcohol-type=Whisky'
    RFC 2324 §2.1.1
    """
    if not header:
        return {}
    additions = {}
    for part in header.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            additions[key.strip()] = value.strip()
    return additions


def validate_additions(additions: dict) -> None:
    """
    Validate additions against the RFC 2324 §2.1.1 spec.
    Raises 406 for decaf or unsupported values.
    """
    # RFC 2324 §2.1.1 — no decaf. Ever.
    if "decaf" in additions:
        log.warning("htcpcp.decaf_refused", additions=additions)
        raise HTTPException(status_code=406, detail={
            "error": "Not Acceptable",
            "message": "Decaffeinated coffee? What's the point?",
            "rfc": "RFC 2324 §2.1.1",
        })

    unsupported = [
        f"{k}={v}"
        for k, v in additions.items()
        if k in SUPPORTED_ADDITIONS and v not in SUPPORTED_ADDITIONS[k]
    ]
    if unsupported:
        raise HTTPException(status_code=406, detail={
            "error": "Not Acceptable",
            "unsupported_additions": unsupported,
            "hint": "Use PROPFIND to list valid additions.",
        })


# ── BREW ──────────────────────────────────────────────────────────────────────

@router.api_route("/coffee/{pot_id}", methods=["BREW", "POST"])
async def brew(pot_id: str, request: Request):
    """
    BREW — Trigger an infusion.
    RFC 2324 §2.1 — The BREW method.

    Returns:
        200 — Coffee is brewing
        406 — Not Acceptable (decaf, invalid additions)
        418 — I'm a teapot (if the target pot is a teapot)
        503 — Pot is empty
    """
    recipe = request.query_params.get("recipe", "default")
    log.info("htcpcp.brew_request_params", query_params=dict(request.query_params), resolved_recipe=recipe)
    pot = resolve_pot(pot_id)

    # RFC 2324 §2.3.2 — Any attempt to brew coffee with a teapot
    # MUST return 418. Non-negotiable.
    if pot.pot_type == PotType.TEAPOT:
        log.warning("htcpcp.teapot_detected", pot_id=pot_id, status_code=418)
        return JSONResponse(status_code=418, content={
            "status": 418,
            "error": "I'm a teapot",
            "body": "The requested entity body is short and stout.",
            "hint": "Tip me over and pour me out.",
            "pot_id": pot_id,
            "pot_type": "teapot",
            "rfc": "RFC 2324 §2.3.2",
            "suggestion": "Try coffee://pot-1 instead.",
        })

    # Validate that recipe exists
    controller = get_controller(pot_id)
    if controller and recipe not in controller.recipes:
        log.warning("htcpcp.invalid_recipe", pot_id=pot_id, requested_recipe=recipe)
        raise HTTPException(status_code=400, detail={
            "error": "Bad Request",
            "message": f"The recipe '{recipe}' does not exist in the configuration.",
            "available_recipes": list(controller.recipes.keys()),
        })

    # Validate that pot is not busy
    if pot.status not in [PotStatus.IDLE, PotStatus.READY, PotStatus.NO_MUG]:
        log.warning("htcpcp.pot_busy", pot_id=pot_id, current_status=pot.status)
        raise HTTPException(status_code=409, detail={
            "error": "Conflict",
            "message": "The pot is currently busy with another brewing cycle.",
            "current_status": pot.status,
        })

    # Optimistic concurrency CAS check
    expected_version = request.headers.get("x-brew-version")
    if expected_version is not None:
        try:
            if int(expected_version) != pot.brew_version:
                raise HTTPException(status_code=409, detail={
                    "error": "Conflict",
                    "message": "Pot was modified by a concurrent BREW.",
                    "current_version": pot.brew_version,
                    "hint": "Retry with current brew_version.",
                })
        except ValueError:
            raise HTTPException(status_code=400, detail={
                "error": "Bad Request",
                "message": "Invalid X-Brew-Version header value. Must be an integer.",
            })

    if not pot.mug_present:
        log.warning("htcpcp.no_mug", pot_id=pot_id)
        raise HTTPException(status_code=503, detail={
            "error": "Service Unavailable",
            "message": "No mug detected. Please place a mug under the spout.",
            "rfc": "RFC 2324 §2.3.2 (extended)",
        })

    additions_header = request.headers.get("accept-additions")
    additions = parse_accept_additions(additions_header)
    validate_additions(additions)

    record = pot.add_brew(additions)
    has_milk = "milk-type" in additions
    pot.status = PotStatus.POURING_MILK if has_milk else PotStatus.DISPENSING_GROUNDS

    # Trigger physical hardware sequence
    if controller:
        log.info("htcpcp.hardware_triggered", pot_id=pot_id, recipe=recipe)
        asyncio.create_task(controller.run_brew_sequence(recipe))

    log.info("htcpcp.brew",
        pot_id=pot_id,
        brew_id=record.id,
        additions=additions,
        milk_pouring=has_milk,
        status_code=200,
        protocol="HTCPCP/1.0",
    )

    return JSONResponse(status_code=200, content={
        "brew_id": record.id,
        "message": "Coffee is brewing.",
        "pot": pot_id,
        "accept-additions": additions,
        "milk_pouring": has_milk,
        "when_required": has_milk,
        "protocol": "HTCPCP/1.0",
    })


# ── GET ───────────────────────────────────────────────────────────────────────

@router.get("/coffee/{pot_id}/status")
def get_status(pot_id: str):
    """
    GET — Return the current state of a coffee pot.
    RFC 2324 §2.1.2
    """
    pot = resolve_pot(pot_id)
    log.info("htcpcp.get_status", pot_id=pot_id, status=pot.status)
    return pot.to_dict()


@router.get("/coffee/{pot_id}/history")
def get_history(pot_id: str):
    """Return the brew history for a pot."""
    pot = resolve_pot(pot_id)
    return {
        "pot_id": pot_id,
        "total_brews": len(pot.brew_history),
        "brews": [r.to_dict() for r in pot.brew_history],
    }


# ── PROPFIND ──────────────────────────────────────────────────────────────────

@router.api_route("/coffee/{pot_id}/additions", methods=["PROPFIND"])
def propfind(pot_id: str):
    """
    PROPFIND — List all available additions for this pot.
    RFC 2324 §2.1.1 — Accept-Additions header values.
    """
    resolve_pot(pot_id)  # Validate pot exists
    log.info("htcpcp.propfind", pot_id=pot_id)
    return {
        **SUPPORTED_ADDITIONS,
        "decaf": DECAF_RESPONSE,
        "rfc": "RFC 2324 §2.1.1",
    }


# ── WHEN ──────────────────────────────────────────────────────────────────────

@router.api_route("/coffee/{pot_id}/stop-milk", methods=["WHEN"])
def when(pot_id: str):
    """
    WHEN — Stop pouring milk. The client determines when enough is enough.
    RFC 2324 §2.1.3

    This is the most human method in the history of network protocols.
    """
    pot = resolve_pot(pot_id)

    if pot.status != PotStatus.POURING_MILK:
        log.info("htcpcp.when_noop", pot_id=pot_id, current_status=pot.status)
        return JSONResponse(status_code=200, content={
            "message": "WHEN acknowledged.",
            "note": "No milk was being poured, but your enthusiasm is appreciated.",
            "current_status": pot.status,
            "rfc": "RFC 2324 §2.1.3",
        })

    pot.status = PotStatus.DISPENSING_GROUNDS

    log.info("htcpcp.when_milk_stopped", pot_id=pot_id, status_code=200)

    return JSONResponse(status_code=200, content={
        "message": "Milk pouring stopped.",
        "detail": "The server has acknowledged WHEN and stopped the milk stream.",
        "current_status": pot.status,
        "protocol": "HTCPCP/1.0",
        "rfc": "RFC 2324 §2.1.3",
    })


# ── Registry ──────────────────────────────────────────────────────────────────

# ── WEB UI ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the minimal dashboard from index.html."""
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Dashboard file not found."

@router.get("/api/recipes")
async def get_api_recipes():
    """Returns all loaded recipes and calibration for the viewer."""
    controller = get_controller("pot-1")
    if not controller:
        return {"error": "Controller not found"}
    return {
        "recipes": controller.recipes,
        "calibration": controller.calibration
    }

@router.get("/api/pots")
async def get_api_pots():
    """List available pots."""
    from models import POT_REGISTRY
    return [{"id": p.id, "name": uri} for uri, p in POT_REGISTRY.items()]

@router.get("/api/status")
async def get_api_status(pot: str = "pot-1"):
    """Real-time status for the web UI."""
    from models import get_pot
    p = get_pot(pot)
    if not p:
        return {"error": "Pot not found"}
    return {
        "id": p.id,
        "status": p.status.name.replace("_", " "),
        "temperature": p.temperature,
        "mug_present": p.mug_present,
        "level": p.level,
        "current_phase": p.current_phase,
        "progress": p.progress,
    }

@router.get("/{filename}.jpg")
async def get_jpg(filename: str):
    """Serve static JPG images."""
    path = f"{filename}.jpg"
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"error": "Not Found"})

@router.get("/{filename}.js")
async def get_js(filename: str):
    """Serve static JS files."""
    path = f"{filename}.js"
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"error": "Not Found"})

@router.get("/{filename}.css")
async def get_css(filename: str):
    """Serve static CSS files."""
    path = f"{filename}.css"
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"error": "Not Found"})
