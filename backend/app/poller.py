"""
Dummy poller loop for Phase 1.
Creates fake F1 snapshot data and writes to Redis every POLL_INTERVAL_SECONDS.
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Dict, Optional
import random as rand

from app import redis_store
from app.circuit_path import CircuitPath
from app.config import CIRCUIT_SVG_PATH, POLL_INTERVAL_SECONDS
from app.snapshot_schema import DriverPosition, LeaderboardEntry, SessionInfo, Snapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy driver data (22 drivers, 2026 season)
DUMMY_DRIVERS = [
    (1, "NOR"),
    (81, "PIA"),
    (63, "RUS"),
    (12, "ANT"),
    (3, "VER"),
    (6, "HAD"),
    (16, "LEC"),
    (44, "HAM"),
    (23, "ALB"),
    (55, "SAI"),
    (30, "LAW"),
    (41, "LIN"),
    (14, "ALO"),
    (18, "STR"),
    (31, "OCO"),
    (87, "BEA"),
    (27, "HUL"),
    (5, "BOR"),
    (10, "GAS"),
    (43, "COL"),
    (11, "PER"),
    (77, "BOT"),
]

DUMMY_TEAMS = {
    "NOR": "McLaren", "PIA": "McLaren",
    "RUS": "Mercedes", "ANT": "Mercedes",
    "VER": "Red Bull Racing", "HAD": "Red Bull Racing",
    "LEC": "Ferrari", "HAM": "Ferrari",
    "ALB": "Williams", "SAI": "Williams",
    "LAW": "Racing Bulls", "LIN": "Racing Bulls",
    "ALO": "Aston Martin", "STR": "Aston Martin",
    "OCO": "Haas", "BEA": "Haas",
    "HUL": "Audi", "BOR": "Audi",
    "GAS": "Alpine", "COL": "Alpine",
    "PER": "Cadillac", "BOT": "Cadillac",
}

DUMMY_COMPOUNDS = ["S", "M", "H"]

_shutdown = False

# In-memory state: driver_number -> t (lap progress, 0.0 to 1.0)
_driver_state: Dict[int, float] = {}

# Circuit path — loaded once from SVG on first use
_circuit_path: Optional[CircuitPath] = None


def _handle_signal(sig, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown
    logger.info("Received signal %s, shutting down...", sig)
    _shutdown = True


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _init_state_if_needed() -> None:
    """Initialize driver t values and load the circuit path from SVG."""
    global _driver_state, _circuit_path
    if _driver_state:
        return

    for idx, (num, _) in enumerate(DUMMY_DRIVERS):
        _driver_state[num] = idx / len(DUMMY_DRIVERS)

    logger.info("Loading circuit SVG from: %s", CIRCUIT_SVG_PATH)
    _circuit_path = CircuitPath(CIRCUIT_SVG_PATH)
    logger.info("Circuit path loaded (%d points)", len(_circuit_path._pts))


def _generate_dummy_snapshot() -> Snapshot:
    """Generate a fake snapshot with drivers moving along the circuit path."""
    _init_state_if_needed()
    assert _circuit_path is not None
    now = _utc_now_iso()

    positions = []
    for num, code in DUMMY_DRIVERS:
        # Advance t; small per-driver variance creates natural gaps.
        base = (num % 10) / 10000.0  # 0.0000 .. 0.0009
        dt = 0.004 + base
        t = (_driver_state[num] + dt) % 1.0
        _driver_state[num] = t

        x, y = _circuit_path.t_to_xy(t)
        positions.append(
            DriverPosition(
                driver_number=num,
                driver_code=code,
                x_norm=round(x, 4),
                y_norm=round(y, 4),
            )
        )

    # Leaderboard: sort by t descending (highest t = furthest around the lap).
    ordered = sorted(DUMMY_DRIVERS, key=lambda item: _driver_state[item[0]], reverse=True)
    leader_t = _driver_state[ordered[0][0]]
    leaderboard = [
        LeaderboardEntry(
            position=i + 1,
            driver_code=code,
            team=DUMMY_TEAMS.get(code, "Unknown"),
            gap_to_leader=round((leader_t - _driver_state[num]) % 1.0, 3),
            tire_compound=rand.choice(DUMMY_COMPOUNDS),
        )
        for i, (num, code) in enumerate(ordered)
    ]

    session = SessionInfo(
        name="Race",
        circuit="Monaco",
    )

    return Snapshot(
        timestamp=now,
        positions=positions,
        leaderboard=leaderboard,
        session=session,
    )


async def poll_loop():
    """Main polling loop - generates fake snapshots and writes to Redis."""
    logger.info("Starting dummy poller (interval=%ss)", POLL_INTERVAL_SECONDS)

    # Verify Redis connectivity
    if not await redis_store.ping():
        logger.error("Cannot connect to Redis, exiting")
        return

    logger.info("Redis connected, clearing stale snapshots...")
    await redis_store.clear_snapshots()
    logger.info("Stale snapshots cleared, starting poll loop...")

    while not _shutdown:
        try:
            snapshot = _generate_dummy_snapshot()
            await redis_store.set_snapshot(snapshot.model_dump())
            logger.info("Wrote snapshot (timestamp=%s)", snapshot.timestamp)
        except Exception as e:
            logger.exception("Error writing snapshot: %s", e)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    logger.info("Poll loop stopped")
    await redis_store.close_client()


def main():
    """Entry point for the poller."""
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        logger.info("Poller interrupted")


if __name__ == "__main__":
    main()
