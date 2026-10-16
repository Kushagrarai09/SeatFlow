# Module 2 — Ticket categories and inventory

## Scope

This module adds general-admission ticket categories to an event. It does not implement individual seat selection, reservation/hold records, payment, or booking confirmation. Those are separate milestones.

## Ticket inventory fields

Each category belongs to exactly one event and stores its name, description, price, total quantity, sold quantity, reserved quantity, minimum and maximum per order, optional sales start/end times, and active/inactive status.

The remaining quantity is calculated as:

\`available_quantity = total_quantity - sold_quantity - reserved_quantity\`

The \`sales_open\` response field is true only when the category is active, remaining inventory is positive, and the current time falls inside the configured sales window.

Database constraints enforce non-negative sold/reserved amounts, sold plus reserved not exceeding total, valid prices, per-order bounds, unique category names per event, and valid status values.

## Endpoints

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| POST | \`/api/v1/events/{event_id}/ticket-categories\` | Organizer owner / admin | Create category |
| GET | \`/api/v1/events/{event_id}/ticket-categories\` | Public for published events | List active categories |
| GET | \`/api/v1/events/{event_id}/ticket-categories?include_inactive=true\` | Organizer owner / admin | List active and inactive categories |
| GET | \`/api/v1/events/{event_id}/ticket-categories/{category_id}\` | Public for published events | Get category |
| PATCH | \`/api/v1/events/{event_id}/ticket-categories/{category_id}\` | Organizer owner / admin | Update pricing, inventory target, order rules, dates, or status |
| DELETE | \`/api/v1/events/{event_id}/ticket-categories/{category_id}\` | Organizer owner / admin | Delete only if no sold/reserved units exist |
| POST | \`/api/v1/ticket-categories/{category_id}/inventory/adjust?quantity_delta=10\` | Organizer owner / admin | Atomically adjust total inventory up/down |

A ticket category's total quantity cannot exceed event capacity. The API deliberately does not claim that total category quantities across an event are seat-allocated or transactionally constrained against each other; the booking module must introduce a cross-category reservation/allocation policy before general sales.

## Local verification

From \`backend\` in an activated Python environment:

\`\`\`powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH = (Get-Location).Path
pytest -q
alembic upgrade head
\`\`\`

Set \`DATABASE_URL\` to a disposable MySQL database before running Alembic. The test suite uses isolated SQLite and does not validate MySQL DDL compatibility.

## Security and booking boundaries

- Ticket mutations require an authenticated organizer account that owns the event, or an administrator.
- Attendees and anonymous users cannot create, modify, adjust, or delete ticket categories.
- Public users see active categories for published events only.
- A category with sold or reserved inventory cannot be deleted; mark it inactive instead.
- The atomic inventory adjustment uses a conditional database update and refuses a quantity that would be less than sold plus reserved tickets or exceed event capacity.
- Creating/editing inventory does not itself reserve tickets or create bookings. Reservation expiry, atomic booking allocation, idempotency, cancellation, and payment remain part of Module 3 / booking workflows.
