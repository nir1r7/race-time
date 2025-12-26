from fastapi import APIRouter, status
from app.models.event import EventIn
from app.db import database
from app.core.logging import get_logger
import json

router = APIRouter(prefix="/events", tags=["events"])
logger = get_logger("eventrelay.events")

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: EventIn):
    query = """
    INSERT INTO events(source, type, payload)
    VALUES (:source, :type, :payload)
    RETURNING id;
    """
    # Convert payload dict to JSON string for JSONB column
    values = event.dict()
    values['payload'] = json.dumps(values['payload'])
    
    event_id = await database.execute(query = query, values=values)

    logger.info(f"Stored event id={event_id} source={event.source} type={event.type}")

    return {
        "status": "accepted",
        "id": event_id,
    }

@router.get("")
async def get_all_events():
    query = "SELECT * FROM events"

    events = await database.fetch_all(query = query)

    logger.info(f"Retrieved all events")

    return events