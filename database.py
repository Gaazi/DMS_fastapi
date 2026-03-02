import os
from sqlmodel import create_engine, Session, SQLModel
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Database configuration logic
DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
DB_NAME = os.getenv("DB_NAME", "db.sqlite3")

if "sqlite3" in DB_ENGINE:
    # SQLite URL format
    sqlite_url = f"sqlite:///{BASE_DIR / DB_NAME}"
    connect_args = {"check_same_thread": False} # Required for SQLite + FastAPI
    engine = create_engine(sqlite_url, connect_args=connect_args, echo=True)
elif "mysql" in DB_ENGINE:
    # MySQL URL format: mysql+pymysql://user:password@host:port/name
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    mysql_url = f"mysql+mysqlclient://{user}:{password}@{host}:{port}/{DB_NAME}"
    engine = create_engine(mysql_url, echo=True)
else:
    # Fallback/Default
    sqlite_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def get_session():
    with Session(engine) as session:
        yield session

# Helper function to initialize database (rarely used if DB already exists)
def init_db():
    SQLModel.metadata.create_all(engine)
