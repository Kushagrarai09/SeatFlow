# SeatFlow

**Discover events. Secure your seat. Make every experience count.**

SeatFlow is a full-stack platform for discovering events, managing venues, and building reliable seat-booking workflows.

## Phase 1 — Foundation

This phase establishes the project structure, configuration examples, a health-check API, and a branded frontend landing page. Booking, authentication, seat holds, payments, and organizer dashboards are planned for later phases and are not implemented yet.

## Technology stack

- **Frontend:** Next.js, React, TypeScript
- **Backend:** FastAPI, Python
- **Database:** MySQL (introduced with the persistence phase)
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

MySQL is not required to run the Phase 1 health-check endpoint or frontend landing page.

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

The frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://127.0.0.1:8000`). The backend reads `FRONTEND_URL` for CORS origins. Keep real secrets out of Git; commit only example configuration files.

## Project principles

1. Build in small, reviewable phases.
2. Validate the foundation before implementing booking features.
3. Keep booking correctness and preventing double-booking as core design goals.
4. Never commit credentials, database passwords, tokens, or local `.env` files.

## Roadmap

- **Phase 1:** project foundation, starter UI, API health check, setup documentation
- **Phase 2:** database integration and initial domain models
- **Phase 3:** accounts, authentication, and roles
- **Phase 4:** event discovery and organizer event management
- **Phase 5:** seat maps, temporary seat holds, and concurrency-safe booking
- **Phase 6:** checkout/payment test mode and booking confirmations
- **Phase 7:** testing, observability, deployment, and production hardening

See [docs/PHASE_1.md](docs/PHASE_1.md) for the acceptance checklist.
