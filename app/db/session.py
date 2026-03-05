# Compatibility shim — پرانے imports کام کریں
# اصل file اب app/core/database.py ہے
from app.core.database import engine, get_session, init_db

__all__ = ["engine", "get_session", "init_db"]
