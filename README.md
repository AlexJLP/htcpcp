# HTCPCP/1.0 — Coffee Pot Control Server

> Hyper Text Coffee Pot Control Protocol · RFC 2324 + RFC 7168

A production-grade implementation of the most important protocol you've never deployed.

## Installation & Dependency Management

This project utilizes `pyproject.toml` for standard PEP 621 project declarations, managed via **`uv`** — the ultra-fast Python package installer and resolver.

### 1. Setup & Installation

To set up a virtual environment and install dependencies:

```bash
# Create a virtual environment
uv venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows

# A) Standard Development Install (Mock Mode, macOS/Windows/Linux)
uv pip install -e . --group dev

# B) Raspberry Pi Physical Install (GPIO + OLED hardware support)
uv pip install -e . --group pi

# C) Complete Setup (Full suite of dev tools + physical packages)
uv pip install -e . --group dev --group pi
```

Alternatively, install using the pre-compiled, locked dependency lists:

```bash
# Install minimal platform-agnostic production dependencies
uv pip install -r requirements-min.txt

# Install all dependencies (including dev and hardware packages)
uv pip install -r requirements.txt
```

### 2. Compile & Lock Dependencies

When making changes to dependencies in `pyproject.toml`, compile and lock the entire dependency graph instantly:

```bash
# Compile and lock full production + dev + pi graph
uv pip compile pyproject.toml --group dev --group pi -o requirements.txt

# Compile and lock lightweight platform-agnostic production graph
uv pip compile pyproject.toml -o requirements-min.txt
```

## Endpoints

| Method | URI | Description |
|--------|-----|-------------|
| `BREW` | `/coffee/{pot_id}` | Trigger an infusion |
| `GET` | `/coffee/{pot_id}/status` | Current pot state |
| `GET` | `/coffee/{pot_id}/history` | Brew history |
| `PROPFIND` | `/coffee/{pot_id}/additions` | List valid additions |
| `WHEN` | `/coffee/{pot_id}/stop-milk` | Stop pouring milk |
| `GET` | `/` | Full pot registry |

Interactive docs: http://localhost:2324/htcpcp-docs

## Example requests

```bash
# Brew a coffee with milk and whisky (Irish coffee — RFC compliant)
curl -X BREW http://localhost:2324/coffee/pot-1 \
  -H "Accept-Additions: milk-type=Whole-milk; alcohol-type=Whisky"

# Check pot status
curl http://localhost:2324/coffee/pot-1/status

# List available additions
curl -X PROPFIND http://localhost:2324/coffee/pot-1/additions

# Stop the milk
curl -X WHEN http://localhost:2324/coffee/pot-1/stop-milk

# Try brewing with a teapot (spoiler: 418)
curl -X BREW http://localhost:2324/coffee/kettle-1

# Try ordering decaf (spoiler: 406)
curl -X BREW http://localhost:2324/coffee/pot-1 \
  -H "Accept-Additions: decaf=true"
```

## Registered pots

| URI | Type | Varieties |
|-----|------|-----------|
| `coffee://pot-1` | ☕ Coffee pot | Espresso, Lungo, Americano |
| `coffee://pot-2` | ☕ Coffee pot | Espresso |
| `tea://kettle-1` | 🫖 Teapot | Earl Grey, Chamomile, Darjeeling |
| `tea://kettle-2` | 🫖 Teapot | Oolong |

## HTTP Status codes

| Code | Meaning |
|------|---------|
| `200` | Coffee is brewing |
| `406` | Not Acceptable (decaf attempted, or invalid addition) |
| `418` | I'm a teapot — BREW sent to a teapot |
| `503` | Pot is empty — refill required |

> ⚠️ An empty coffee pot returns **503**, not 418. The pot is still a coffee pot — it's just empty. Common mistake.

## Tests

```bash
# Run tests inside the virtual environment:
pytest test_htcpcp.py -v

# Or run tests using uv run directly:
uv run pytest test_htcpcp.py -v
```

## RFC references

- [RFC 2324](https://tools.ietf.org/html/rfc2324) — Hyper Text Coffee Pot Control Protocol (1 April 1998)
- [RFC 7168](https://tools.ietf.org/html/rfc7168) — HTCPCP-TEA: Tea Efflux Appliances (1 April 2014)

---

## Why `server.py` instead of `main.py` + uvicorn?

uvicorn validates HTTP method names at the socket level, before h11 even parses the request.
`BREW`, `WHEN`, and `PROPFIND` are not registered IANA methods, so uvicorn rejects them with
`Invalid HTTP request received` regardless of any h11 patch.

`server.py` is a raw asyncio TCP server with a minimal HTTP/1.1 parser that accepts any valid
RFC 7230 token as a method name — which `BREW`, `WHEN`, and `PROPFIND` are.

```bash
# Run the raw TCP server inside the virtual environment:
python server.py

# Or run instantly using uv:
uv run python server.py
```

`main.py` is kept for reference and for the test suite (FastAPI TestClient bypasses
the HTTP layer entirely, so custom methods work fine in tests).
