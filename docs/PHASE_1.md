# Phase 1 — Project Foundation

## Goal

Create a clean, runnable starting point for SeatFlow in its own repository. Phase 1 is a UI/API foundation; the event cards are illustrative previews, not live listings, and booking/authentication are not implemented yet.

## Deliverables

- [x] Root README with setup steps and roadmap
- [x] Root .gitignore for Python, Node, IDE, and environment artifacts
- [x] FastAPI app with / and /health
- [x] Configurable CORS using FRONTEND_URL
- [x] Backend health endpoint tests
- [x] Next.js App Router + TypeScript starter configuration
- [x] Frontend API URL configured via NEXT_PUBLIC_API_URL
- [x] Example environment files instead of local secrets
- [ ] Run and verify tests in a developer environment
- [ ] Add CI after local setup has been verified

## Architecture at this phase

Browser -> Next.js frontend (localhost:3000) -> GET /health -> FastAPI (localhost:8000)

Database: not connected in Phase 1.

## API contract

GET / returns service metadata. GET /health returns {"status":"ok","service":"seatflow-api"}. The health endpoint is a liveness check, not a database readiness check.

## Verify backend (PowerShell)

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload
```

In another terminal: `Invoke-RestMethod http://127.0.0.1:8000/health`

## Verify frontend (PowerShell)

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
npm run typecheck
npm run lint
npm run build
```

Open http://localhost:3000. The page should render and the footer should indicate whether the API health route is reachable.

## Out of scope

Authentication, venues/events persistence, MySQL schema, seat maps, temporary seat holds, concurrency-safe bookings, waitlists, payments, email, production deployment, and observability. Add these incrementally only after this foundation runs correctly.
