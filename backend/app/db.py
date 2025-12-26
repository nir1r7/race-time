from databases import Database
from app.core.config import DATABASE_URL

database = Database(DATABASE_URL)

async def connect_db():
    await database.connect()

async def disconnect_db():
    await database.disconnect()
