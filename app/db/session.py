"""
SQLite (for now) engine and session factory.

Per the project roadmap, this swaps to Postgres later just by
changing DATABASE_URL -- no other code here is SQLite-specific.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Base

# check_same_thread=False is needed for SQLite when used outside a
# single-threaded context (e.g. FastAPI's request handling).
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Creates all tables if they don't already exist."""
    Base.metadata.create_all(bind=engine)
