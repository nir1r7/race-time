from dotenv import load_dotenv
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# load_dotenv(BASE_DIR / ".env")

DB_USER = os.getenv("POSTGRES_USER", "eventrelayuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "123")
DB_NAME = os.getenv("POSTGRES_DB", "eventrelay")
DB_HOST = os.getenv("POSTGRES_HOST", "db")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

print(f"DEBUG - DB Config: user={DB_USER}, db={DB_NAME}, host={DB_HOST}, port={DB_PORT}")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
print(f"DEBUG - DATABASE_URL: {DATABASE_URL}")

