import httpx


async def fetch_drivers_for_season() -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openf1.org/v1/drivers",
            params={"session_key": "latest"},
        )
        response.raise_for_status()
        return response.json()


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
        return response.json()
    

async def fetch_drivers(session_key: int, token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
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
        return response.json()
