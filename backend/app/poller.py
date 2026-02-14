"""
Dummy poller loop for Phase 1.
Creates fake F1 snapshot data and writes to Redis every POLL_INTERVAL_SECONDS.
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Dict, Tuple

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

_shutdown = False

# In-memory state: driver_number -> (x_norm, y_norm)
# This avoids "teleporting" positions every tick.
_driver_state: Dict[int, Tuple[float, float]] = {}


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
    """Initialize positions the first time we run."""
    global _driver_state
    if _driver_state:
        return

    # Spread drivers around the unit square deterministically-ish.
    # Using a simple pattern keeps the first render stable.
    for idx, (num, _) in enumerate(DUMMY_DRIVERS):
        x = (idx / len(DUMMY_DRIVERS)) % 1.0
        y = ((idx * 7) / len(DUMMY_DRIVERS)) % 1.0
        _driver_state[num] = (x, y)


def _step_position(x: float, y: float, dx: float, dy: float) -> Tuple[float, float]:
    """Move a point slightly and wrap around [0, 1)."""
    x = (x + dx) % 1.0
    y = (y + dy) % 1.0
    return x, y


def _generate_dummy_snapshot(tick: int) -> Snapshot:
    """
    Generate a fake snapshot with smoothly changing positions.

    Args:
        tick: monotonically increasing tick counter for deterministic motion.
    """
    _init_state_if_needed()
    now = _utc_now_iso()

    # Create a consistent, smooth movement pattern:
    # - everyone moves a bit each tick
    # - slight per-driver variation based on driver_number
    positions = []
    for num, code in DUMMY_DRIVERS:
        x, y = _driver_state[num]

        # Small deterministic deltas; avoids random teleporting.
        # Keep deltas tiny so movement looks realistic-ish.
        base = (num % 10) / 10000.0  # 0.0000 .. 0.0009
        dx = 0.0020 + base
        dy = 0.0015 + ((tick % 5) / 10000.0)

        x, y = _step_position(x, y, dx, dy)
        _driver_state[num] = (x, y)

        positions.append(
            DriverPosition(
                driver_number=num,
                driver_code=code,
                x_norm=round(x, 4),
                y_norm=round(y, 4),
            )
        )

    # Dummy leaderboard:
    # Keep it stable and derived from x position so it "feels" connected to movement.
    # Sort descending by x_norm (arbitrary but deterministic).
    ordered = sorted(positions, key=lambda p: p.x_norm, reverse=True)
    leaderboard = [
        LeaderboardEntry(
            position=i + 1,
            driver_number=p.driver_number,
            driver_code=p.driver_code,
        )
        for i, p in enumerate(ordered)
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

    tick = 0
    while not _shutdown:
        try:
            snapshot = _generate_dummy_snapshot(tick=tick)
            await redis_store.set_snapshot(snapshot.model_dump())
            logger.info("Wrote snapshot (timestamp=%s)", snapshot.timestamp)
        except Exception as e:
            logger.exception("Error writing snapshot: %s", e)

        tick += 1
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
