import asyncio
import os

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from web.hardware import CONTROLLERS, HardwareController
from web.models import POT_REGISTRY
from web.routes import dashboard as get_dashboard_html
from web.routes import router

# ── Structured logging ────────────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HTCPCP/1.0",
    description="Hyper Text Coffee Pot Control Protocol — RFC 2324 + RFC 7168",
    version="1.0.0",
    docs_url="/htcpcp-docs",
    redoc_url="/htcpcp-redoc",
)


# ── Middleware ────────────────────────────────────────────────────────────────


class HTCPCPMiddleware(BaseHTTPMiddleware):
    """
    Enforce HTCPCP protocol headers on all responses.
    Also intercepts rogue BREW calls on non-coffee routes.
    """

    async def dispatch(self, request: Request, call_next):
        # Detect a BREW on a non-coffee route
        # A developer confused about which universe they're in deserves a 418
        if request.method == "BREW" and not request.url.path.startswith("/coffee"):
            log.warning(
                "htcpcp.wrong_universe",
                method="BREW",
                path=request.url.path,
                status_code=418,
            )
            return JSONResponse(
                status_code=418,
                content={
                    "error": "Wrong universe",
                    "message": f"BREW is not valid on {request.url.path}",
                    "hint": "BREW is only valid on coffee:// URIs — try /coffee/pot-1",
                    "rfc": "RFC 2324 §2.1",
                },
            )

        response = await call_next(request)

        # Stamp every response with protocol headers
        response.headers["X-Protocol"] = "HTCPCP/1.0"
        response.headers["X-RFC"] = "RFC-2324, RFC-7168"
        response.headers["X-Powered-By"] = "Coffee"

        return response


app.add_middleware(HTCPCPMiddleware)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return await get_dashboard_html()


# ── Startup ───────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup():

    log.info(
        "htcpcp.startup",
        protocol="HTCPCP/1.0",
        rfc=["RFC-2324", "RFC-7168"],
        registered_pots=list(POT_REGISTRY.keys()),
        port=2324,
    )

    # Initialize Hardware Controllers
    use_mock = os.getenv("HTCPCP_MOCK_HARDWARE", "0") == "1"
    for uri, pot in POT_REGISTRY.items():
        # Strip the scheme for the controller registry
        pot_id = uri.rsplit("://", maxsplit=1)[-1]
        controller = HardwareController(pot, use_mock=use_mock)
        CONTROLLERS[pot_id] = controller

        # Start the background sensor loop
        asyncio.create_task(controller.update_loop())
        log.info("hardware.controller_started", pot_id=pot_id, mock=use_mock)
