from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
from typing import Generator

from app.core.config import settings

# Create database engine
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DEBUG
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.DEBUG
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables."""
    from app.models import user, test, plan, audit
    
    Base.metadata.create_all(bind=engine)

def drop_db():
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)

class DatabaseManager:
    """Database management utilities."""
    
    @staticmethod
    def health_check() -> bool:
        """Check database health."""
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_table_count() -> int:
        """Get total number of tables."""
        try:
            if settings.DATABASE_URL.startswith("sqlite"):
                result = engine.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table'"
                ).scalar()
            else:
                result = engine.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
                ).scalar()
            return result
        except Exception:
            return 0
    
    @staticmethod
    def get_database_size() -> str:
        """Get database size."""
        try:
            if settings.DATABASE_URL.startswith("sqlite"):
                # For SQLite, get file size
                db_path = settings.DATABASE_URL.replace("sqlite:///", "")
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    size_mb = size_bytes / (1024 * 1024)
                    return f"{size_mb:.2f} MB"
            else:
                # For PostgreSQL
                result = engine.execute(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                ).scalar()
                return result
        except Exception:
            return "Unknown"