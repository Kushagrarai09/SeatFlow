"""SeatFlow FastAPI application and system health endpoints."""

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes import router as api_router
from app.auth_routes import router as auth_router
from app.admin_routes import router as admin_router
from app.ticket_routes import router as ticket_router
from app.reservation_routes import router as reservation_router


def allowed_origins() -> list[str]:
    """Read browser origins from FRONTEND_URL without requiring a .env file."""
    raw_origins = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app = FastAPI(
    title="SeatFlow API",
    description="Backend API for the SeatFlow event discovery and seat-booking platform.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(ticket_router)
app.include_router(reservation_router)


@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    """Return API metadata useful during local development."""
    return {"name": "SeatFlow API", "version": app.version, "status": "running"}


@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    """Lightweight liveness check; this does not claim the database is healthy."""
    return {"status": "ok", "service": "seatflow-api"}


@app.get("/health/database", tags=["System"])
def database_health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Check database connectivity separately from API process liveness."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "connected"}
