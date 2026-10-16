# Phase 2 — Database foundation

## Goal

Add the first persistent domain layer without starting authentication or booking logic yet.

## Included

- SQLAlchemy 2.x engine and request-scoped session dependency.
- MySQL connection configuration via `DATABASE_URL`.
- Alembic migration infrastructure and an initial migration.
- `venues`, `organizers`, and `events` tables with foreign keys, constraints, timestamps, and useful indexes.
- Pydantic create/read schemas for the three domain objects.
- `GET /health/database` to test connectivity separately from API liveness.
- SQLite-backed unit tests for metadata and model relationships.

## Domain relationships

- One organizer can host many events.
- One venue can host many events.
- Every event references exactly one organizer and one venue.
- Organizer email is unique.
- Venue and event capacity must be positive.
- Event price cannot be negative.
- Event status is limited to `draft`, `published`, `cancelled`, or `completed`.
- An event's end time must be later than its start time in the API schema.

Authentication, API CRUD endpoints, event publication workflows, tickets, seat holds, reservations, and payments are out of scope for this phase.

## Windows setup

From the repository root, activate the backend virtual environment and install dependencies:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set `DATABASE_URL` to your local MySQL username, password, host, port, and database. Example:

```dotenv
DATABASE_URL=mysql+pymysql://seatflow:YOUR_PASSWORD@127.0.0.1:3306/seatflow
FRONTEND_URL=http://localhost:3000
```

Create the MySQL database and a local database user with privileges for that database before migrating. Do not commit `.env` or credentials.

PowerShell does not automatically load `.env` files into process environment variables. For a local terminal session, set the variables before running Alembic and Uvicorn, or use your preferred environment-file loader:

```powershell
$env:DATABASE_URL = "mysql+pymysql://seatflow:YOUR_PASSWORD@127.0.0.1:3306/seatflow"
$env:FRONTEND_URL = "http://localhost:3000"
```

Run the migration:

```powershell
alembic upgrade head
alembic current
```

Start the API:

```powershell
uvicorn app.main:app --reload
```

Verify the two health endpoints:

- `GET http://127.0.0.1:8000/health` checks that the API process is alive.
- `GET http://127.0.0.1:8000/health/database` runs `SELECT 1` and returns HTTP 503 if the database is unavailable.

Run automated tests (the model tests use in-memory SQLite and do not need a MySQL server):

```powershell
pytest -q
```

## Acceptance checklist

- [x] SQLAlchemy, PyMySQL, and Alembic dependencies added.
- [x] Initial Venue, Organizer, and Event models and schemas added.
- [x] Initial Alembic migration checked in.
- [x] Database connectivity endpoint added.
- [x] SQLite model relationship tests added.
- [ ] Install dependencies and run tests on a developer machine.
- [ ] Apply migration to a local MySQL database and verify `alembic current`.
- [ ] Confirm `/health/database` returns connected with MySQL running.

## Important implementation notes

- Importing the API creates a SQLAlchemy engine but does not open a database connection.
- `/health` is a liveness check; `/health/database` is a database connectivity check.
- Schema changes should be made with new Alembic migrations rather than manual production table edits.
- The current model capacity is event-level inventory only. Seat maps, individually held seats, reservation concurrency, and payment state will be designed in later phases.
