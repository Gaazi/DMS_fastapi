"""
DMS Core — بنیادی اور مرکزی components

Modules:
  config.py    → Settings & environment variables
  database.py  → SQLModel engine, session, init_db
  constants.py → App-wide constants
"""
from app.core.config import settings
from app.core.database import engine, get_session, init_db

__all__ = ["settings", "engine", "get_session", "init_db"]
