"""Minimal SeatFlow API entry point for Phase 1."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def allowed_origins() -> list[str]:
    """Read browser origins from FRONTEND_URL without requiring a .env file."""
    raw_origins = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app = FastAPI(
    title="SeatFlow API",
    description="Backend API for the SeatFlow event discovery and seat-booking platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    """Return API metadata useful during local development."""
    return {"name": "SeatFlow API", "version": app.version, "status": "running"}

@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    """Lightweight liveness check; this does not claim the database is healthy."""
    return {"status": "ok", "service": "seatflow-api"}
