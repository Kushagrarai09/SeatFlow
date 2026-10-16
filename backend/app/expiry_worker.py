"""Scheduled worker that releases inventory from expired reservation holds.

Run as a separate process:
    python -m app.expiry_worker

The worker is intentionally separate from FastAPI so API replicas do not each
start their own scheduler. Multiple worker instances remain safe because the
expiry transition is conditional and performed inside a database transaction.
"""
from __future__ import annotations

import logging
import os
import signal
import time

from app.database import SessionLocal
from app.reservation_routes import _expire_due, _now

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("seatflow.expiry_worker")

POLL_INTERVAL_SECONDS = max(5, int(os.getenv("RESERVATION_EXPIRY_INTERVAL_SECONDS", "30")))
BATCH_SIZE = min(5000, max(1, int(os.getenv("RESERVATION_EXPIRY_BATCH_SIZE", "500"))))
_stop = False


def _request_stop(signum: int, _frame: object) -> None:
    global _stop
    logger.info("Received signal %s; stopping after current sweep", signum)
    _stop = True


def expire_once() -> int:
    """Expire one bounded batch and commit inventory releases atomically."""
    db = SessionLocal()
    try:
        count = _expire_due(db, _now(), limit=BATCH_SIZE)
        db.commit()
        if count:
            logger.info("Expired %s reservation hold(s)", count)
        return count
    except Exception:
        db.rollback()
        logger.exception("Reservation expiry sweep failed; it will retry next cycle")
        raise
    finally:
        db.close()


def main() -> None:
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    logger.info(
        "Reservation expiry worker started (interval=%ss, batch=%s)",
        POLL_INTERVAL_SECONDS,
        BATCH_SIZE,
    )
    while not _stop:
        try:
            expire_once()
        except Exception:
            # A transient DB issue must not permanently stop the worker.
            pass
        # Sleep in short intervals so shutdown signals are handled promptly.
        deadline = time.monotonic() + POLL_INTERVAL_SECONDS
        while not _stop and time.monotonic() < deadline:
            time.sleep(min(1, deadline - time.monotonic()))
    logger.info("Reservation expiry worker stopped")


if __name__ == "__main__":
    main()
