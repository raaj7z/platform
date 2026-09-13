from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("OSINT_DB_PATH", str(BASE_DIR / "data" / "sih.db"))
SCHEMA_PATH = os.getenv("SHARED_SCHEMA_PATH", str(BASE_DIR / "shared" / "schema_sqlite.sql"))
CRAWLER_PATH = os.getenv("CRAWLER_PATH", "../DarkWeb-Deanonymization")
OSINT_ENGINE_PATH = os.getenv("OSINT_ENGINE_PATH", "../osint-engine")

