import aiomqtt
import asyncio
import json
import logging
import ssl
from datetime import datetime, timezone, timedelta
import signal

from app import redis_store
from app.snapshot_schema import DriverPosition, LeaderboardEntry, SessionInfo, Snapshot
from app.circuit_bounds import normalize
from app.config import OPENF1_USERNAME, OPENF1_PASSWORD, MQTT_HOST, MQTT_PORT
from app.openf1 import get_token, fetch_latest_session, fetch_latest_positions, fetch_drivers, fetch_latest_laps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_positions: dict[int, dict] = {}
_laps: dict[int, dict] = {}
_drivers: dict[int, dict] = {}
_session: dict = {}
_last_snapshot_time: float = 0.0

SNAPSHOT_INTERVAL = 0.5  # seconds — max 2Hz

delay = 1.0
max_delay = 60.0
_shutdown = False


async def _bootstrap(token) -> None:
    global _session, _drivers, _positions, _laps

    sessions_list = await fetch_latest_session(token)
    _session = sessions_list[0]

    drivers_list = await fetch_drivers(_session["session_key"], token)
    _drivers = {driver["driver_number"]: driver for driver in drivers_list}

    positions_list = await fetch_latest_positions(_session["session_key"], token)
    _positions = {pos["driver_number"]: pos for pos in positions_list}

    laps_list = await fetch_latest_laps(_session["session_key"], token)
    _laps = {lap["driver_number"]: lap for lap in laps_list}


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

        lap = _laps.get(num, {})
        driver = _drivers.get(num, {})

        positions_list.append(DriverPosition(
            driver_number = num,
            driver_code = driver.get("name_acronym") or "UNK",
            x_norm = x_norm,
            y_norm = y_norm,
        ))

        leaderboard_list.append(LeaderboardEntry(
            position = lap.get("position") or 1,
            driver_code = driver.get("name_acronym") or "UNK",
            team = driver.get("team_name") or "Unknown",
            gap_to_leader = lap.get("gap_to_leader") or 0.0,
            tire_compound = lap.get("tire_compound") or "Unknown",
        ))

    leaderboard_list.sort(key=lambda e: e.position)

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
    global _last_snapshot_time
    async with aiomqtt.Client(
        hostname = MQTT_HOST,
        port = MQTT_PORT,
        username = OPENF1_USERNAME,
        password = token,
        tls_context = ssl.create_default_context(),
    ) as client:
        await client.subscribe("v1/location")
        await client.subscribe("v1/laps")
        await client.subscribe("v1/drivers")
        await client.subscribe("v1/sessions")

        async for message in client.messages:
            topic = str(message.topic)
            payload = json.loads(message.payload)
            driver_num = payload.get("driver_number")

            if (topic == "v1/location"):
                if driver_num is not None:
                    _positions[driver_num] = payload
                loop = asyncio.get_running_loop()
                now_ts = loop.time()
                if now_ts - _last_snapshot_time >= SNAPSHOT_INTERVAL:
                    _last_snapshot_time = now_ts
                    try:
                        snapshot = await _assemble_snapshot()
                        await redis_store.set_snapshot(snapshot.model_dump())
                    except Exception:
                        logger.exception("Failed to assemble snapshot")
            elif (topic == "v1/laps"):
                if driver_num is not None:
                    _laps[driver_num] = payload
            elif (topic == "v1/drivers"):
                if driver_num is not None:
                    _drivers[driver_num] = payload
            elif (topic == "v1/sessions"):
                global _session
                _session = payload


async def _worker_loop():
    # delay = 0.1

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
            # delay = 0.1
        except Exception as e:
            logger.error("Connection failed: %s (%s), retrying in %.1fs", e, type(e).__name__, delay, exc_info=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)

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