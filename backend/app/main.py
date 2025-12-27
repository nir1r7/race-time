from fastapi import FastAPI
from app.api.routes import events
from app.db import database


app = FastAPI(title="EventRelay")

app.include_router(events.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()