# Module 3 — Booking and Reservation Engine

This module introduces temporary general-admission ticket holds. It builds on the authentication and ticket inventory modules.

## Reservation lifecycle

`pending → confirmed` or `pending → cancelled` or `pending → expired`.

- A hold lasts 10 minutes.
- Creating a hold atomically increments `ticket_categories.reserved_quantity` only if enough inventory remains.
- Confirmation moves quantity from reserved to sold in one transaction.
- Cancelling a pending hold releases reserved quantity.
- Expiry releases reserved quantity exactly once through a conditional status transition.
- Confirming an expired/cancelled hold is rejected.
- Repeating confirmation or cancellation for the same already-completed action is safe where documented.
- Confirmed-booking cancellation/refunds are intentionally not implemented; they require a separate payment/refund workflow.

## API

All endpoints are prefixed with `/api/v1`.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/reservations` | Create a temporary hold |
| GET | `/reservations/{reservation_id}` | Read your reservation (admins may read any) |
| POST | `/reservations/{reservation_id}/confirm` | Confirm a live hold |
| POST | `/reservations/{reservation_id}/cancel` | Cancel a pending hold |
| POST | `/admin/reservations/expire?limit=500` | Admin-triggered expiry sweep |

### Create a hold

Send a valid access token and an `Idempotency-Key` header (8–128 characters):

```http
POST /api/v1/reservations
Authorization: Bearer <access-token>
Idempotency-Key: checkout-attempt-2026-001
Content-Type: application/json

{
  "ticket_category_id": 12,
  "quantity": 2
}
```

The response includes the reservation ID, unit price, total price, state, and expiry timestamp. Repeating the same key with the same payload returns the existing reservation without reserving inventory twice. Reusing that key with a different payload returns HTTP 409. Keys are scoped per user.

### Expiry worker

The admin endpoint is an MVP operational hook, not a substitute for a scheduler. In a deployed environment, invoke the expiry sweep from a trusted scheduled worker (for example, every minute). Keep the batch size bounded. The sweep is safe to retry because state changes are conditional.

## Concurrency and data integrity

- The inventory update is a conditional SQL update; it checks available quantity in the database rather than relying only on a value read into application memory.
- The category row is locked with `SELECT ... FOR UPDATE` on databases that support it.
- The reservation table has a unique constraint on `(user_id, idempotency_key)`.
- Reservation status transitions and inventory changes share a database transaction.
- These tests use SQLite for fast API-level coverage. SQLite ignores `FOR UPDATE`, so this suite does **not** prove MySQL concurrency behavior. Before production, run migration and parallel booking/load tests against MySQL, and verify transaction isolation and deadlock retries.

## Not included yet

Payments, payment webhooks, refund processing, assigned seats/seat maps, ticket QR codes, email delivery, distributed locks, and background-worker deployment are outside Module 3.
