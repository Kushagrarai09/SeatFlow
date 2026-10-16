# Phase 3 — Event and catalog API

## Goal

Expose the first usable API for creating event data and discovering published events. This phase builds on the database models and migration from Phase 2.

## Endpoints

All endpoints use the `/api/v1` prefix.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/venues` | Create a venue |
| GET | `/venues` | List venues; optional `city`, `offset`, and `limit` |
| POST | `/organizers` | Create an organizer profile |
| GET | `/organizers` | List organizer profiles |
| POST | `/events` | Create an event as a draft or with a selected status |
| GET | `/events` | Discover published events |
| GET | `/events/{event_id}` | Read a published event |
| PATCH | `/events/{event_id}` | Partially update an event |

Event discovery supports `q` (title search), `category`, `city`, `starts_after`, `starts_before`, `offset`, and `limit`. The default limit is 20 and maximum is 100. Discovery endpoints expose published events only; draft, cancelled, and completed records do not appear in public discovery.

## Local setup

Complete Phase 2 setup first, install the development requirements, configure MySQL, and apply the initial migration:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:DATABASE_URL = "mysql+pymysql://seatflow:YOUR_PASSWORD@127.0.0.1:3306/seatflow"
alembic upgrade head
pytest -q
uvicorn app.main:app --reload
```

For quick API testing, open http://127.0.0.1:8000/docs. The tests use an isolated SQLite database, so the API tests do not need MySQL; MySQL is still needed for migration and end-to-end verification.

## Example workflow

1. Create a venue with `POST /api/v1/venues`.
2. Create an organizer with `POST /api/v1/organizers`.
3. Create an event with `POST /api/v1/events`, referencing those IDs. Keep `status: "draft"` while preparing it.
4. Publish it using `PATCH /api/v1/events/{id}` with `{"status":"published"}`.
5. Discover it using `GET /api/v1/events?city=Mumbai&category=technology`.

## Security boundary

**This is a development-stage API, not ready for public production deployment.** This phase does not yet include authentication or role/ownership authorization. The organizer, venue, and event management endpoints currently accept requests without login, and the event patch endpoint does not yet enforce organizer ownership. Do not expose these management routes to the public internet until authentication and authorization are implemented and tested. Public discovery endpoints intentionally return published events only.

## Acceptance checklist

- [ ] Run `pytest -q` and confirm all tests pass.
- [ ] Start the API and inspect the generated OpenAPI page at `/docs`.
- [ ] Apply Alembic migration against a local MySQL database.
- [ ] Create a venue and organizer, then create a draft event.
- [ ] Confirm the draft is not returned by event discovery.
- [ ] Publish the event and confirm city/category filters return it.
- [ ] Confirm unknown organizer/venue IDs return 404 and duplicate organizer email returns 409.
- [ ] Add authentication and authorization before any public deployment.
