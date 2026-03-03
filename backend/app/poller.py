"""
Dummy poller loop for Phase 1.
Creates fake F1 snapshot data and writes to Redis every POLL_INTERVAL_SECONDS.
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Dict, Tuple
import random as rand

from app import redis_store
from app.config import POLL_INTERVAL_SECONDS
from app.snapshot_schema import DriverPosition, LeaderboardEntry, SessionInfo, Snapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy driver data (20 drivers)
DUMMY_DRIVERS = [
    (1, "VER"),
    (11, "PER"),
    (44, "HAM"),
    (63, "RUS"),
    (16, "LEC"),
    (55, "SAI"),
    (4, "NOR"),
    (81, "PIA"),
    (14, "ALO"),
    (18, "STR"),
    (10, "GAS"),
    (31, "OCO"),
    (23, "ALB"),
    (2, "SAR"),
    (77, "BOT"),
    (24, "ZHO"),
    (20, "MAG"),
    (27, "HUL"),
    (22, "TSU"),
    (3, "RIC"),
]

DUMMY_TEAMS = {
    "VER": "Red Bull", "PER": "Red Bull",
    "HAM": "Mercedes", "RUS": "Mercedes",
    "LEC": "Ferrari", "SAI": "Ferrari",
    "NOR": "McLaren", "PIA": "McLaren",
    "ALO": "Aston Martin", "STR": "Aston Martin",
    "GAS": "Alpine", "OCO": "Alpine",
    "ALB": "Williams", "SAR": "Williams",
    "BOT": "Alfa Romeo", "ZHO": "Alfa Romeo",
    "MAG": "Haas", "HUL": "Haas",
    "TSU": "AlphaTauri", "RIC": "AlphaTauri",
}

DUMMY_COMPOUNDS = ["S", "M", "H"]

_shutdown = False

# In-memory state: driver_number -> t (perimeter progress, 0.0 to 1.0)
_driver_state: Dict[int, float] = {}

# Perimeter parameterisation — must match frontend circuit dimensions (720 x 480).
# Each segment's share of the total perimeter: 2*(720+480) = 2400px.
_W, _H = 720, 480
_P = 2 * (_W + _H)
_SEG_TOP    = _W / _P          # 0.300  top edge
_SEG_RIGHT  = _H / _P          # 0.200  right edge
_SEG_BOTTOM = _W / _P          # 0.300  bottom edge
# _SEG_LEFT = _H / _P          # 0.200  left edge (remainder)

# Cumulative breakpoints for each corner (clockwise from top-left)
_B1 = _SEG_TOP                           # 0.30
_B2 = _SEG_TOP + _SEG_RIGHT              # 0.50
_B3 = _SEG_TOP + _SEG_RIGHT + _SEG_BOTTOM  # 0.80


def _t_to_xy(t: float) -> Tuple[float, float]:
    """Convert perimeter progress t [0, 1) to (x_norm, y_norm).

    Clockwise from top-left:
      top    edge: x 0→1, y=1
      right  edge: x=1,   y 1→0
      bottom edge: x 1→0, y=0
      left   edge: x=0,   y 0→1
    """
    t = t % 1.0
    if t < _B1:
        return t / _SEG_TOP, 1.0
    elif t < _B2:
        return 1.0, 1.0 - (t - _B1) / _SEG_RIGHT
    elif t < _B3:
        return 1.0 - (t - _B2) / _SEG_BOTTOM, 0.0
    else:
        return 0.0, (t - _B3) / (1.0 - _B3)


def _handle_signal(sig, frame):
    """Handle shutdown signals gracefully."""
    # frame is unused but part of the signal handler signature
    global _shutdown
    logger.info("Received signal %s, shutting down...", sig)
    _shutdown = True


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _init_state_if_needed() -> None:
    """Initialize t values spread evenly around the perimeter."""
    global _driver_state
    if _driver_state:
        return

    for idx, (num, _) in enumerate(DUMMY_DRIVERS):
        _driver_state[num] = idx / len(DUMMY_DRIVERS)


def _generate_dummy_snapshot() -> Snapshot:
    """Generate a fake snapshot with drivers moving around the circuit perimeter."""
    _init_state_if_needed()
    now = _utc_now_iso()

    positions = []
    for num, code in DUMMY_DRIVERS:
        # Advance t; small per-driver variance creates natural gaps.
        base = (num % 10) / 10000.0  # 0.0000 .. 0.0009
        dt = 0.0020 + base
        t = (_driver_state[num] + dt) % 1.0
        _driver_state[num] = t

        x, y = _t_to_xy(t)
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

    logger.info("Redis connected, starting poll loop...")

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
