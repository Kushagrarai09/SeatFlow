# Frontend live event and reservation integration

This change connects the SeatFlow Next.js frontend to the existing FastAPI APIs on the feature branch.

## Connected flows
- The homepage requests published events from `GET /api/v1/events` and venue details from `GET /api/v1/venues`; hard-coded sample event cards are removed.
- Event detail pages load event details and active ticket categories.
- Attendees can register or sign in through the existing auth endpoints.
- Signed-in attendees can create a 10-minute reservation hold, confirm it, or cancel it.
- The frontend refreshes ticket availability after confirmation/cancellation.

## Local configuration
Set `frontend/.env.local` to:
```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```
Configure `backend/.env` with the local MySQL URL and `FRONTEND_URL=http://localhost:3000`, apply Alembic migrations, and run the API and frontend in separate terminals.

## Important scope and security notes
- Payment processing is not implemented. The confirmation action confirms the reservation in the current backend; do not treat it as a paid order.
- Organizer event creation/management UI is not included in this first integration slice; organizers can use the API docs until a dashboard is built.
- The current frontend stores access/refresh tokens in localStorage for this local development MVP. For production, use a reviewed secure session design, ideally HttpOnly secure cookies and refresh-token handling.
- Do not self-assign an organizer role in a deployed system. Provision organizer/admin roles through a trusted administrative path.
- This PR is a frontend integration implementation, not proof that local MySQL end-to-end testing has passed. Run typecheck/build and manually test against a migrated database.
