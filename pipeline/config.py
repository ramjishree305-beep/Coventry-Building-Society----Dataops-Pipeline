import os

SOURCE_PATH = os.getenv("SOURCE_PATH", "data/raw")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "data/processed")
QUARANTINE_DIR = os.getenv("QUARANTINE_DIR", "data/quarantine")
LOG_DIR = os.getenv("LOG_DIR", "logs")

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "analytics")
DB_USER = os.getenv("DB_USER", "pipeline")
SQLITE_PATH = os.getenv("SQLITE_PATH", "data/warehouse.db")

MAX_REJECT_PERCENT = float(os.getenv("MAX_REJECT_PERCENT", "5"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
