from fastapi import FastAPI
from app.api.routes import events

app = FastAPI(title="EventRelay")

app.include_router(events.router)

@app.get("/health")
def health():
    return {"status": "ok"}
