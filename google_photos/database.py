import contextlib
import datetime
import uuid

from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.types import DateTime, JSON

DATABASE_URL = f"sqlite:///photos.db"

GLOBAL_ENGINE = create_engine(
    DATABASE_URL,
    connect_args={'timeout': 15},  # Increase the timeout as needed
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=5
)


@event.listens_for(GLOBAL_ENGINE, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()


# Create a session factory
global_session_factory = sessionmaker(bind=GLOBAL_ENGINE)


# Construct a base object for declarative class definitions
Base = declarative_base()


class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)
    filename = Column(String)
    suffix = Column(String)
    file_id = Column(String)
    physical_path = Column(String)

    # A json object representing metadata
    asset_metadata = Column(JSON)
    creation_time = Column(DateTime)


class FailedAsset(Base):
    __tablename__ = "failed_assets"
    id = Column(String, primary_key=True)
    filename = Column(String)
    error = Column(String)


# Create the session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=GLOBAL_ENGINE)

# Create the table
Base.metadata.create_all(bind=GLOBAL_ENGINE)


@contextlib.contextmanager
def session():
    """Provide a transactional scope around a series of operations."""
    session_ = global_session_factory()
    try:
        yield session_
        session_.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        session_.rollback()
        raise
    finally:
        session_.close()
