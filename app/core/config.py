import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "DMS - Digital Management System"
    VERSION: str = "1.0.0"

    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database (SQLModel/SQLAlchemy format)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./db.sqlite3")

    # Static & Media
    STATIC_URL: str = "/static/"
    MEDIA_URL: str = "/media/"
    MEDIA_ROOT: Path = BASE_DIR / "media"

    # SMS
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "fast2sms")
    SMS_API_KEY: str = os.getenv("SMS_API_KEY", "")
    SMS_SENDER_ID: str = os.getenv("SMS_SENDER_ID", "FSTSMS")

    # Production Server (proxy کے پیچھے چلنے پر اصل domain)
    # Server کی .env میں لگائیں: PRODUCTION_HOST=demo.esabaq.com
    PRODUCTION_HOST: str = os.getenv("PRODUCTION_HOST", "")

settings = Settings()
