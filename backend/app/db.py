import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from .models.database import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./devsko.db")


def _default_devsko_database_url() -> str:
    explicit_url = os.getenv("DEVSKO_DATABASE_URL")
    if explicit_url:
        return explicit_url

    if DATABASE_URL.startswith("postgresql") and DATABASE_URL.rstrip("/").endswith("/interview"):
        return DATABASE_URL.rsplit("/", 1)[0] + "/devsko"

    return DATABASE_URL


DEVSKO_DATABASE_URL = _default_devsko_database_url()

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

devsko_engine = create_engine(
    DEVSKO_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DEVSKO_DATABASE_URL else {},
)
DevskoSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=devsko_engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_devsko_db():
    db = DevskoSessionLocal()
    try:
        yield db
    finally:
        db.close()
