# Reservation expiry worker

SeatFlow creates temporary reservation holds that expire after 10 minutes. The
admin expiry endpoint remains available for manual operations, but production
deployments should run the background worker as a **separate process**.

## Run locally

From the repository's `backend` directory, after configuring `DATABASE_URL`
and applying migrations:

```powershell
python -m app.expiry_worker
```

The worker uses the same database configuration as the API. It polls every 30
seconds by default and expires at most 500 holds per pass.

Environment variables:

| Variable | Default | Purpose |
| --- | ---: | --- |
| `DATABASE_URL` | existing SeatFlow MySQL URL | SQLAlchemy connection |
| `RESERVATION_EXPIRY_INTERVAL_SECONDS` | `30` | Polling interval; minimum 5 seconds |
| `RESERVATION_EXPIRY_BATCH_SIZE` | `500` | Maximum holds per sweep; range 1–5000 |
| `LOG_LEVEL` | `INFO` | Worker log level |

## Deployment notes

- Run this command as a supervised worker process/container, not inside each
  FastAPI application startup hook. This avoids starting one scheduler per API
  replica.
- Configure the process manager/container platform to restart it after crashes.
- The sweep commits reservation status changes and inventory releases together.
  Failed sweeps roll back and retry on the next poll.
- Multiple workers may run, but verify locking and conditional updates against
  the target MySQL/InnoDB version before production.
- This worker does not run database migrations. Apply `alembic upgrade head`
  as a separate deployment step before starting API/worker processes.
- MySQL migration and concurrent reservation integration tests must pass before
  treating production concurrency safety as verified.
