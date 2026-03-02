from sqlmodel import create_engine, Session, SQLModel
import os
from app.core.config import settings

# Database configuration logic
if "sqlite3" in settings.DB_ENGINE:
    sqlite_url = f"sqlite:///{settings.BASE_DIR / settings.DB_NAME}"
    connect_args = {"check_same_thread": False}
    engine = create_engine(sqlite_url, connect_args=connect_args, echo=True)
elif "mysql" in settings.DB_ENGINE:
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    mysql_url = f"mysql+mysqlclient://{user}:{password}@{host}:{port}/{settings.DB_NAME}"
    engine = create_engine(mysql_url, echo=True)
else:
    sqlite_url = f"sqlite:///{settings.BASE_DIR / 'db.sqlite3'}"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    SQLModel.metadata.create_all(engine)
