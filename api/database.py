"""
Database connection and session management for YouTube Contextual Product Pipeline.
Uses SQLAlchemy ORM with SQLite (migration-ready to PostgreSQL).
"""
import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from api.config import settings

logger = logging.getLogger(__name__)

# Create database engine
if settings.database_url.startswith("sqlite"):
    url = make_url(settings.database_url)
    if url.database:
        db_path = Path(url.database).expanduser()
        parent_dir = db_path.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                logger.warning(
                    "No permission to create database directory %s. Ensure this path exists.",
                    parent_dir,
                )

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False  # Set to True for SQL query logging during development
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    Yields a database session and ensures it's closed after use.
    
    Usage in FastAPI endpoints:
        def my_endpoint(db: Session = Depends(get_db)):
            # Use db here
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.
    Should be called on application startup.
    """
    from api.models import Campaign, Keyword, YouTubeVideo, VideoScore, YouTubeChannel  # Import models to register metadata
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully")
