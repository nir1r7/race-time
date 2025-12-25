from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class EventIn(BaseModel):
    source: str = Field(..., example="auth-service")
    type: str = Field(..., example="user.login")
    payload: Dict = Field(..., example={"user_id": 123})
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.utcnow
    )
