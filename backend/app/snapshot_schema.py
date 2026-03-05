"""Phase 1 Snapshot Schema - Minimal contract for poller -> Redis -> API."""
from typing import Optional

from pydantic import BaseModel, Field

# Backend data models for requests and responses
class DriverPosition(BaseModel):
    """Driver position on track (normalized 0-1 coordinates)."""

    driver_number: int
    driver_code: str
    x_norm: float  # 0.0 to 1.0
    y_norm: float  # 0.0 to 1.0
    trail: list[tuple[float, float]] = Field(default_factory = list)


class LeaderboardEntry(BaseModel):
    """Leaderboard position."""

    position: int
    driver_code: str
    team: str
    gap_to_leader: float
    tire_compound: str


class SessionInfo(BaseModel):
    """Optional session metadata."""

    session_key: Optional[int] = None
    name: str = "Race"
    circuit: str = "Unknown"


class Snapshot(BaseModel):
    """
    Phase 1 Snapshot - the payload written to Redis by poller
    and returned by API to clients.
    """

    timestamp: str  # ISO format
    positions: list[DriverPosition]
    leaderboard: list[LeaderboardEntry]
    session: Optional[SessionInfo] = None
