import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "DMS FastAPI"
    VERSION: str = "1.0.0"
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # Database
    DB_ENGINE: str = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
    DB_NAME: str = os.getenv("DB_NAME", "db.sqlite3")
    
    # Static & Media
    STATIC_URL: str = "/static/"
    MEDIA_URL: str = "/media/"
    MEDIA_ROOT: Path = BASE_DIR / "media"

settings = Settings()
