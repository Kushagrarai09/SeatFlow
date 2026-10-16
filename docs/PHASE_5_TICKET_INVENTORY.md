# Module 2 — Ticket categories and inventory

## Scope
This module implements general-admission ticket categories, not individual seat maps, booking holds, payments, or confirmed bookings.

Each category belongs to an event and records its name, description, price, total quantity, sold quantity, reserved quantity, order bounds, sales window, and status.

`available_quantity = total_quantity - sold_quantity - reserved_quantity`

The response field `sales_open` is true only when the category is active, inventory remains, and the current time is inside the configured window.

Database constraints enforce valid prices and quantities, inventory bounds, per-order bounds, allowed statuses, and unique category names per event.

## Endpoints

| Method | Endpoint | Access |
| --- | --- | --- |
| POST | `/api/v1/events/{event_id}/ticket-categories` | Owning organizer / admin |
| GET | `/api/v1/events/{event_id}/ticket-categories` | Public for published events; owners see their categories |
| GET | `/api/v1/events/{event_id}/ticket-categories?include_inactive=true` | Owning organizer / admin |
| GET | `/api/v1/events/{event_id}/ticket-categories/{category_id}` | Public for published events; owners can see drafts/inactive |
| PATCH | `/api/v1/events/{event_id}/ticket-categories/{category_id}` | Owning organizer / admin |
| DELETE | `/api/v1/events/{event_id}/ticket-categories/{category_id}` | Owning organizer / admin; only with no sold/reserved tickets |
| POST | `/api/v1/ticket-categories/{category_id}/inventory/adjust?quantity_delta=10` | Owning organizer / admin |

The adjustment uses a conditional SQL update and rejects totals below sold/reserved counts, at/below zero, or where category totals would exceed event capacity. Existing category quantity cannot exceed its event's capacity. The booking module must still define cross-category allocation and implement transactions, idempotency, reservation expiry, cancellation, and payment state.

## Verification
Run in the backend virtual environment:

```powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH = (Get-Location).Path
pytest -q
alembic upgrade head
```

Use a disposable MySQL database for Alembic. SQLite tests do not prove MySQL DDL compatibility.
