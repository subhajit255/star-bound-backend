from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# Create SQLAlchemy engine for MySQL
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # recommended for MySQL connections
    pool_recycle=3600    # recycle connections before they timeout
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy models
Base = declarative_base()
