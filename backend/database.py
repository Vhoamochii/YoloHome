import logging
import os
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_FILE = os.path.join(BASE_DIR, "yolohome.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_FILE}")

log = logging.getLogger("database")


def _sqlite_engine(url: str):
    # Routes, the scheduler and the MQTT thread all write: wait for the lock instead of failing.
    eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(eng, "connect")
    def _set_wal(conn, _record):
        conn.execute("PRAGMA journal_mode=WAL")

    return eng


def init_engine(url: str):
    if url.startswith("sqlite"):
        return _sqlite_engine(url)
    try:
        eng = create_engine(url)
        with eng.connect():
            pass
        return eng
    except Exception as e:
        # Keep the demo running, but never silently write to a different database.
        log.error("Cannot use DATABASE_URL (%s); FALLING BACK TO SQLITE at %s", e, DEFAULT_DB_FILE)
        return _sqlite_engine(f"sqlite:///{DEFAULT_DB_FILE}")

engine = init_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def upgrade_schema():
    """create_all() never alters an existing table: add columns newer than the local DB."""
    insp = inspect(engine)
    if not insp.has_table("lich_trinh"):
        return
    existing = {c["name"] for c in insp.get_columns("lich_trinh")}
    with engine.begin() as conn:
        if "speed" not in existing:
            conn.execute(text("ALTER TABLE lich_trinh ADD COLUMN speed INTEGER"))
        if "last_run_at" not in existing:
            conn.execute(text("ALTER TABLE lich_trinh ADD COLUMN last_run_at TIMESTAMP"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
