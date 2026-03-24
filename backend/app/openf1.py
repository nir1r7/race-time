from datetime import datetime, timedelta, timezone

import httpx

from app.config import OPENF1_PASSWORD, OPENF1_USERNAME


async def get_token() -> tuple[str, datetime]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openf1.org/token",
            data={
                "username": OPENF1_USERNAME,
                "password": OPENF1_PASSWORD,
                "grant_type": "password",
            },
        )
        response.raise_for_status()
        data = response.json()
        token = data["access_token"]
        expires_in = int(data["expires_in"])
        expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return token, expiry_time


async def fetch_latest_session(token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openf1.org/v1/sessions",
            headers = {"Authorization": f"Bearer {token}"},
            params = {"session_key": "latest"},
        )
        response.raise_for_status()
        return response.json()


async def fetch_latest_positions(session_key: int, token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openf1.org/v1/position",
            headers = {"Authorization": f"Bearer {token}"},
            params = {"session_key": session_key},
        )
        response.raise_for_status()
        entries = response.json()
        return sorted(entries, key=lambda e: e.get("date", ""))


async def fetch_drivers(session_key: int, token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.openf1.org/v1/drivers",
            headers={"Authorization": f"Bearer {token}"},
            params={"session_key": session_key},
        )
        response.raise_for_status()
        return response.json()


async def fetch_latest_laps(session_key: int, token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openf1.org/v1/laps",
            headers={"Authorization": f"Bearer {token}"},
            params={"session_key": session_key},
        )
        response.raise_for_status()
        entries = response.json()
        return sorted(entries, key=lambda e: e.get("lap_number", 0))


async def fetch_latest_intervals(session_key: int, token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.openf1.org/v1/intervals",
            headers={"Authorization": f"Bearer {token}"},
            params={"session_key": session_key},
        )
        response.raise_for_status()
        return response.json()


async def fetch_next_race(token: str) -> dict | None:
    now = datetime.now(timezone.utc)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://api.openf1.org/v1/sessions",
            headers={"Authorization": f"Bearer {token}"},
            params={"year": now.year, "session_type": "Race"},
        )
        response.raise_for_status()
        sessions = response.json()

    # Check for a currently-live session first
    for s in sessions:
        if not s.get("date_start") or not s.get("date_end"):
            continue
        date_start = datetime.fromisoformat(s["date_start"])
        date_end = datetime.fromisoformat(s["date_end"])
        if date_start <= now <= date_end:
            return {
                "circuit_short_name": s["circuit_short_name"],
                "date_start": s["date_start"],
                "session_name": s["session_name"],
                "session_key": s["session_key"],
                "is_live": True,
            }

    future = [
        s for s in sessions
        if s.get("date_start") and datetime.fromisoformat(s["date_start"]) > now
    ]

    if not future:
        return None

    next_session = min(future, key=lambda s: s["date_start"])

    return {
        "circuit_short_name": next_session["circuit_short_name"],
        "date_start": next_session["date_start"],
        "session_name": next_session["session_name"],
        "session_key": next_session["session_key"],
        "is_live": False,
    }
