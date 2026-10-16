"""Database engine and SQLAlchemy session dependency for SeatFlow."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SeatFlow ORM models."""


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://seatflow:change_me@127.0.0.1:3306/seatflow",
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one database session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
