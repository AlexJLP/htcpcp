# HTCPCP Coffee Pot Control Server
## Directory Structure

The project is organised into several subdirectories:

*   **`web/`**: The main web component package. It contains the FastAPI application (`main.py`), the raw TCP server (`server.py`), routing logic (`routes.py`), data models (`models.py`), hardware integration (`hardware.py`), the dashboard interface (`index.html`), and recipe configurations (`recipes.yaml`).
*   **`models/`**: OpenSCAD files for the physical hardware enclosure. These models have been split into modular components (`config.scad` for shared parameters, `base.scad` for the console body, `pump.scad` for the water pump pod sleeve). 
*   **`standalone_scripts/`**: Standalone scripts used for manual hardware testing and debugging .

## Installation & Setup

This project uses `pyproject.toml` to declare dependencies. You can manage the virtual environment and install packages using your preferred package manager.

To set up a virtual environment and install packages:

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate 

# Install dependencies in editable mode
pip install -e .
```

If you are developing or running on a Raspberry Pi with physical hardware accessories (OLED screen, stepper motor, and distance sensor), make sure to install the optional Pi dependencies:

```bash
pip install -e .[pi]
```

## Running the Servers

Because uvicorn filters out non-standard HTTP methods like `BREW`, `WHEN`, and `PROPFIND` at the socket level, running the application through standard ASGI servers will block those commands. 

To bypass this restriction, use the custom raw TCP server which parses RFC-compliant custom methods:

```bash
# Run the raw TCP server from the root directory
python -m web.server
```

## Endpoints

The server supports the following HTCPCP and HTTP methods:

| Method | Path | Description |
|--------|------|-------------|
| `BREW` / `POST` | `/coffee/{pot_id}` | Starts a brewing cycle for the specified pot. |
| `GET` | `/coffee/{pot_id}/status` | Retrieves the current state of a pot. |
| `GET` | `/coffee/{pot_id}/history` | Retrieves the brew history log. |
| `PROPFIND` | `/coffee/{pot_id}/additions` | Lists all available milk/syrup additions. |
| `WHEN` | `/coffee/{pot_id}/stop-milk` | Signals the server to stop pouring milk. |
| `GET` | `/` | Serves the web-based HTML dashboard interface. |

## Example Requests

```bash
# Start brewing a coffee with Whole-milk and Whisky
curl -X BREW http://localhost:2324/coffee/pot-1 \
  -H "Accept-Additions: milk-type=Whole-milk; alcohol-type=Whisky"

# Check the current status of the pot
curl http://localhost:2324/coffee/pot-1/status

# Signal the pot to stop pouring milk
curl -X WHEN http://localhost:2324/coffee/pot-1/stop-milk
```