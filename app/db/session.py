import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQLite file at project root
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vehr.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
