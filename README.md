# SeatFlow

**Discover events. Secure your seat. Make every experience count.**

SeatFlow is a full-stack platform for discovering events, managing venues, and building reliable seat-booking workflows.

## Current progress

- **Phase 1 — Foundation:** starter UI, FastAPI service, environment examples, and health checks.
- **Phase 2 — Database foundation (PR #1, pending review):** SQLAlchemy configuration, MySQL driver, Alembic migration, and initial Venue, Organizer, and Event models.
- **Phase 3 — Event and catalog API (PR #2, pending review):** versioned endpoints for venues, organizer profiles, event creation, public discovery filters, and partial updates.
- **Module 1 — Authentication (in progress):** attendee registration/login, refresh-token rotation, logout, account roles, admin role provisioning, and ownership checks for catalog mutations. See [docs/PHASE_4_AUTHENTICATION.md](docs/PHASE_4_AUTHENTICATION.md).

Seat inventory, holds, bookings, payments, email verification, and password reset are not implemented yet. Authentication changes are in a separate review branch and have not been merged.

## Technology stack

- **Frontend:** Next.js, React, TypeScript
- **Backend:** FastAPI, Python
- **Database:** MySQL with SQLAlchemy ORM and Alembic migrations
- **Local development:** Docker Compose (container setup will be added in a later foundation task)

## Repository layout

```text
SeatFlow/
├── frontend/              # Next.js web application
├── backend/               # FastAPI service
├── docs/                  # Architecture and phase notes
├── .gitignore
└── README.md
```

## Prerequisites

- Node.js 20 or newer and npm
- Python 3.11 or newer
- Git

MySQL is not required for the basic `/health` endpoint or frontend landing page. The `/health/database` endpoint and database migrations require a configured, running MySQL database.

## Run the backend

Open a terminal at the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

On macOS/Linux, create and activate the virtual environment with:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:
- API health: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs

## Run the frontend

In a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

On macOS/Linux, replace the copy command with `cp .env.local.example .env.local`.

Open http://localhost:3000.

## Environment variables

The frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://127.0.0.1:8000`). The backend reads `FRONTEND_URL` for CORS origins and `DATABASE_URL` for SQLAlchemy. Copy `backend/.env.example` to `backend/.env` and set your local database credentials; do not commit `.env` files. See [docs/PHASE_2.md](docs/PHASE_2.md) for setup and migration commands.

## Project principles

1. Build in small, reviewable phases.
2. Validate the foundation before implementing booking features.
3. Keep booking correctness and preventing double-booking as core design goals.
4. Never commit credentials, database passwords, tokens, or local `.env` files.

## Roadmap

- **Phase 1:** project foundation, starter UI, API health check, setup documentation
- **Phase 2:** database integration and initial domain models (implementation on `feat/phase-2-database`)
- **Phase 3:** event and catalog API (current branch: `feat/phase-3-event-api`)
- **Module 1:** account authentication, roles, and organizer ownership authorization (this PR)
- **Next:** ticket categories, inventory, temporary reservations, and concurrency-safe booking
- **Later:** payment test mode, ticket validation, notifications, testing, observability, deployment, and production hardening

**Security note:** this branch adds authentication and authorization to catalog mutations, but it is still under review. Do not treat the platform as production-ready until migrations and tests pass and deployment controls are configured.

See [docs/PHASE_1.md](docs/PHASE_1.md), [docs/PHASE_2.md](docs/PHASE_2.md), [docs/PHASE_3.md](docs/PHASE_3.md), and [docs/PHASE_4_AUTHENTICATION.md](docs/PHASE_4_AUTHENTICATION.md) for setup and acceptance checklists.
