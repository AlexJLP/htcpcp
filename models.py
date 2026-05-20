"""
HTCPCP/1.0 — Data Models
RFC 2324 (coffee) + RFC 7168 (tea)
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from time import time


class PotType(str, Enum):
    COFFEE = "coffee"
    TEAPOT = "teapot"


class PotStatus(str, Enum):
    IDLE = "idle"
    BREWING = "brewing"
    DISPENSING_GROUNDS = "dispensing-grounds"
    POURING_MILK = "pouring-milk"
    HEATING_WATER = "heating"
    BLOOMING = "blooming"
    POURING = "pouring"
    INFUSING = "infusing"
    READY = "ready"
    NO_MUG = "no-mug"


@dataclass
class BrewRecord:
    id: int
    timestamp: float
    additions: dict[str, str]
    status: str = "completed"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "additions": self.additions,
            "status": self.status,
        }


@dataclass
class CoffeePot:
    id: str
    pot_type: PotType
    varieties: list[str] = field(default_factory=list)
    status: PotStatus = field(default=PotStatus.IDLE)
    brew_history: list[BrewRecord] = field(default_factory=list)
    brew_version: int = field(default=0)

    # Physical state
    temperature: float = field(default=20.0)
    mug_present: bool = field(default=True)
    level: float = field(default=100.0)
    current_phase: int = field(default=-1)
    progress: float = field(default=0.0)

    # Per-pot asyncio lock — prevents concurrent BREWs racing on level/status.
    # Classic TOCTOU: two requests both read level > 0, both proceed,
    # pot goes negative. Not RFC compliant. Definitely not coffee compliant.
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def to_dict(self) -> dict:
        return {
            "pot_id": self.id,
            "type": self.pot_type,
            "status": self.status,
            "varieties": self.varieties,
            "brew_count": len(self.brew_history),
            "brew_version": self.brew_version,
            "temperature": round(self.temperature, 2),
            "mug_present": self.mug_present,
        }

    def add_brew(self, additions: dict) -> BrewRecord:
        record = BrewRecord(
            id=len(self.brew_history) + 1,
            timestamp=time(),
            additions=additions,
        )
        self.brew_history.append(record)
        self.brew_version += 1
        return record


# ── RFC 2324 §2.1.1 — Supported additions ────────────────────────────────────

SUPPORTED_ADDITIONS: dict[str, list[str]] = {}

# RFC 2324 §2.1.1 — no decaf, intentionally.
# "What's the point?" — Larry Masinter, 1998
DECAF_RESPONSE = "NOT_ACCEPTABLE — What's the point? (RFC 2324 §2.1.1)"


# ── Pot registry ──────────────────────────────────────────────────────────────

POT_REGISTRY: dict[str, CoffeePot] = {
    "coffee://pot-1": CoffeePot(
        id="pot-1",
        pot_type=PotType.COFFEE,
        varieties=["Pourover"],
    ),
    "tea://kettle-1": CoffeePot(
        id="kettle-1",
        pot_type=PotType.TEAPOT,
        varieties=["Earl Grey"],
    ),
}


def get_pot(pot_id: str) -> CoffeePot | None:
    """Lookup a pot by ID, checking both coffee:// and tea:// URIs."""
    return POT_REGISTRY.get(f"coffee://{pot_id}") or POT_REGISTRY.get(f"tea://{pot_id}")
