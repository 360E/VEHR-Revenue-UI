import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.db.base import Base
from app.db.session import engine, SessionLocal

def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    default_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://the-trapp-house.com",
        "https://www.the-trapp-house.com",
    ]
    if not raw:
        return default_origins
    if raw == "*":
        return ["*"]
    configured = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return sorted(set(configured + default_origins))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import app.db.models  # register models

    auto_create = os.getenv("AUTO_CREATE_TABLES", "").strip().lower() in {"1", "true", "yes"}
    if auto_create:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="VEHR API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/health/db")
def health_db():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    return {"status": "ok", "db": "ok"}

@app.get("/")
def root():
    return {"status": "VEHR backend running"}
