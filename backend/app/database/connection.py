"""
database/connection.py
SQLAlchemy engine, session factory, Base class, and get_db dependency.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import DATABASE_URL

# SQLite-specific: allow multiple threads to use the same connection
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=StaticPool if ":memory:" in DATABASE_URL else None,
    echo=False,
)

# Session factory — call SessionLocal() to get a new DB session
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Base class that all ORM models inherit from
class Base(DeclarativeBase):
    pass

def get_db():
    """
    FastAPI dependency. Yields a DB session and closes it after the request.
    Usage in a route:
        def my_route(db: Session = Depends(get_db)):
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
