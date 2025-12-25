from fastapi import APIRouter, status
from app.models.event import EventIn
from app.core.logging import get_logger

router = APIRouter(prefix="/events", tags=["events"])
logger = get_logger("eventrelay.events")

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: EventIn):
    logger.info(
        "event_recieved",
        extra={
            "extra": {
                "source": event.source,
                "type": event.type,
                "timestamp": event.timestamp.isoformat(),
            }
        },
    )

    return {
        "status": "accepted",
        "event_type": event.type,
    }