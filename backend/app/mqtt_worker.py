import asyncio
import json
import logging
import signal
import ssl
from collections import deque
from datetime import datetime, timedelta, timezone

import aiomqtt

from app import redis_store
from app.circuit_bounds import normalize
from app.config import MQTT_HOST, MQTT_PORT, OPENF1_USERNAME
from app.openf1 import (
    fetch_drivers,
    fetch_latest_intervals,
    fetch_latest_laps,
    fetch_latest_positions,
    fetch_latest_session,
    get_token,
)
from app.snapshot_schema import DriverPosition, LeaderboardEntry, SessionInfo, Snapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMPOUND_MAP: dict[str, str] = {
    "SOFT": "S", "MEDIUM": "M", "HARD": "H",
    "INTERMEDIATE": "I", "WET": "W",
    "S": "S", "M": "M", "H": "H", "I": "I", "W": "W",
}


def _normalize_compound(raw: str | None) -> str:
    if not raw:
        return "?"
    return COMPOUND_MAP.get(raw.upper(), raw[0].upper())


MAX_TRAIL_LEN = 6

_positions: dict[int, dict] = {}
_intervals: dict[int, dict] = {}
_laps: dict[int, dict] = {}
_drivers: dict[int, dict] = {}
_session: dict = {}
_driver_trail: dict[int, deque] = {}
_last_snapshot_time: float = 0.0

# seconds - max 2Hz
SNAPSHOT_INTERVAL = 0.5

# test with values from 0.1 to 2
DEFAULT_DELAY = 0.1
MAX_DELAY = 60.0
_shutdown = False


async def _bootstrap(token) -> None:
    global _session, _drivers, _positions, _laps, _intervals

    sessions_list = await fetch_latest_session(token)
    _session = sessions_list[0]

    drivers_list = await fetch_drivers(_session["session_key"], token)
    _drivers = {driver["driver_number"]: driver for driver in drivers_list}

    positions_list = await fetch_latest_positions(_session["session_key"], token)
    _positions = {pos["driver_number"]: pos for pos in positions_list}

    laps_list = await fetch_latest_laps(_session["session_key"], token)
    _laps = {lap["driver_number"]: lap for lap in laps_list}

    intervals_list = await fetch_latest_intervals(_session["session_key"], token)
    _intervals = {
        interval["driver_number"]: interval
        for interval in intervals_list
        if interval.get("driver_number") is not None
    }


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_gap(value) -> tuple[float | None, bool]:
    """Return (gap, is_lapped) where lap gaps are flagged and gap None."""
    if value is None:
        return None, False

    if isinstance(value, (int, float)):
        return float(value), False

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None, False

        upper = s.upper()
        if "LAP" in upper:
            return None, True

        if s.startswith("+"):
            s = s[1:]

        try:
            return float(s), False
        except ValueError:
            return None, False

    return None, False


async def _assemble_snapshot() -> Snapshot:
    positions_list = []
    leaderboard_list = []

    circuit_key = str(_session.get("circuit_key", ""))

    for num, pos in _positions.items():
        raw_x = pos.get("x")
        raw_y = pos.get("y")

        if raw_x is None or raw_y is None:
            continue

        x_norm, y_norm = normalize(circuit_key, raw_x, raw_y)

        driver = _drivers.get(num, {})

        positions_list.append(DriverPosition(
            driver_number = num,
            driver_code = driver.get("name_acronym") or "UNK",
            x_norm = x_norm,
            y_norm = y_norm,
            trail = list(_driver_trail.get(num, deque())),
        ))

    interval_entries: list[tuple[int, float | None, bool]] = []
    for num, interval in _intervals.items():
        gap_val, is_lapped = _parse_gap(interval.get("gap_to_leader"))
        if gap_val is None:
            alt_gap, alt_lapped = _parse_gap(interval.get("interval"))
            if alt_gap is not None or alt_lapped:
                gap_val, is_lapped = alt_gap, alt_lapped
        interval_entries.append((num, gap_val, is_lapped))

    # Order: leader first (gap 0), then finite gaps ascending, then lapped/unknown.
    def _interval_sort_key(entry: tuple[int, float | None, bool]):
        num, gap_val, is_lapped = entry
        if gap_val is None:
            return (2 if is_lapped else 3, float("inf"), num)
        return (0, gap_val, num)

    ordered_from_intervals = [num for num, _, _ in sorted(interval_entries, key=_interval_sort_key)]

    lap_only = [n for n in _laps.keys() if n not in _intervals]
    lap_only.sort(key=lambda n: (_safe_int(_laps.get(n, {}).get("position")) or 9999, n))

    remaining = [n for n in _drivers.keys() if n not in _intervals and n not in _laps]
    remaining.sort()

    ordered_driver_numbers = ordered_from_intervals + lap_only + remaining

    position_counter = 1
    for num in ordered_driver_numbers:
        driver = _drivers.get(num, {})
        interval = _intervals.get(num, {})
        lap = _laps.get(num, {})

        gap_val, is_lapped = _parse_gap(interval.get("gap_to_leader") if interval else lap.get("gap_to_leader"))
        if gap_val is None and interval:
            alt_gap, alt_lapped = _parse_gap(interval.get("interval"))
            if alt_gap is not None or alt_lapped:
                gap_val, is_lapped = alt_gap, alt_lapped

        if gap_val is None and position_counter == 1:
            gap_val = 0.0

        leaderboard_list.append(LeaderboardEntry(
            position = position_counter,
            driver_code = driver.get("name_acronym") or "UNK",
            team = driver.get("team_name") or "Unknown",
            gap_to_leader = gap_val,
            tire_compound = _normalize_compound(lap.get("compound") or lap.get("tire_compound")),
        ))
        position_counter += 1

    return Snapshot(
        timestamp = datetime.now(timezone.utc).isoformat(),
        positions = positions_list,
        leaderboard = leaderboard_list,
        session = SessionInfo(
            session_key = _session.get("session_key"),
            name = _session.get("session_name", "Race"),
            circuit = _session.get("circuit_short_name", "Unknown"),
        )
    )


async def _run_mqtt_session(token):
    global _session
    global _last_snapshot_time
    async with aiomqtt.Client(
        hostname = MQTT_HOST,
        port = MQTT_PORT,
        username = OPENF1_USERNAME,
        password = token,
        tls_context = ssl.create_default_context(),
    ) as client:
        await client.subscribe("v1/location")
        await client.subscribe("v1/intervals")
        await client.subscribe("v1/laps")
        await client.subscribe("v1/drivers")
        await client.subscribe("v1/sessions")

        async for message in client.messages:
            topic = str(message.topic)
            payload = json.loads(message.payload)
            driver_num = _safe_int(payload.get("driver_number"))

            if (topic == "v1/location"):
                if driver_num is not None:
                    _positions[driver_num] = payload
                    raw_x = payload.get("x")
                    raw_y = payload.get("y")
                    if raw_x is not None and raw_y is not None:
                        circuit_key = str(_session.get("circuit_key", ""))
                        x_norm, y_norm = normalize(circuit_key, raw_x, raw_y)
                        if driver_num not in _driver_trail:
                            _driver_trail[driver_num] = deque(maxlen=MAX_TRAIL_LEN)
                        _driver_trail[driver_num].append((round(x_norm, 4), round(y_norm, 4)))
                loop = asyncio.get_running_loop()
                now_ts = loop.time()
                if now_ts - _last_snapshot_time >= SNAPSHOT_INTERVAL:
                    _last_snapshot_time = now_ts
                    try:
                        snapshot = await _assemble_snapshot()
                        await redis_store.set_snapshot(snapshot.model_dump())
                        await redis_store.set_heartbeat()
                    except Exception:
                        logger.exception("Failed to assemble snapshot")
            elif (topic == "v1/laps"):
                if driver_num is not None:
                    _laps[driver_num] = payload
            elif (topic == "v1/intervals"):
                if driver_num is not None:
                    _intervals[driver_num] = payload
            elif (topic == "v1/drivers"):
                if driver_num is not None:
                    _drivers[driver_num] = payload
            elif (topic == "v1/sessions"):
                _session = payload


async def _worker_loop():
    delay = DEFAULT_DELAY
    attempt = 0

    if not await redis_store.ping():
        logger.error("Cannot connect to Redis, exiting")
        return

    token, token_expiry = await get_token()
    await _bootstrap(token)

    logger.info("Bootstrap complete, connecting to MQTT broker...")

    while not _shutdown:
        if datetime.now(timezone.utc) >= token_expiry - timedelta(seconds=60):
            token, token_expiry = await get_token()

        try:
            await _run_mqtt_session(token)
            delay = DEFAULT_DELAY
            attempt = 0
        except Exception as e:
            attempt += 1
            logger.error("Connection failed (attempt %d): %s — retrying in %.1fs", attempt, e, delay, exc_info=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)

    logger.info("Worker loop stopped")
    await redis_store.close_client()


def _handle_signal(sig, frame):
    global _shutdown
    _shutdown = True
    logger.info("Shutdown signal received")


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        asyncio.run(_worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")



if __name__ == "__main__":
    main()
