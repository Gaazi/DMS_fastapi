from sqlmodel import create_engine, Session, SQLModel
from app.core.config import settings


def _build_engine():
    url = settings.DATABASE_URL

    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG
        )
    else:
        # MySQL / PostgreSQL
        return create_engine(url, echo=settings.DEBUG)


engine = _build_engine()


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
