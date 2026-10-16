# SeatFlow — Smart Event Platform

## Product direction

SeatFlow is an independent smart event platform for attendees, event organizers, and platform administrators. It helps people discover relevant events, explore venues, and manage tickets through a reliable booking experience.

This product direction is specific to the SeatFlow repository. It must be designed and implemented independently; do not use another event-booking repository as its implementation base.

## Users and core journeys

### Attendees
- Browse published events and explore event details.
- Search and filter by keyword, category, city, venue, and date.
- Save favorite events and manage personal preferences.
- Book tickets and review booking status and history.

### Organizers
- Create and maintain venues and event listings.
- Configure ticket categories and inventory.
- View bookings and basic event performance metrics.
- Manage only resources they are authorized to control.

### Administrators
- Review and moderate event listings.
- Manage platform accounts and investigate reported content.
- Access operational views with explicit administrative permissions.

## Product principles

1. **Discoverability first:** event listings must be searchable, filterable, paginated, and limited to public/published content.
2. **Correctness over convenience:** booking and inventory updates must be transactional and protected against overselling.
3. **Secure by default:** authenticated identity, role checks, and resource ownership are required for management operations.
4. **Build incrementally:** ship a tested modular backend before adding the full frontend experience.
5. **Recommendations must be explainable:** start with transparent rules based on declared preferences, categories, city, and event popularity; avoid claiming machine-learning personalization until it exists.
6. **Observable behavior:** meaningful errors, structured logs, health checks, and tests are part of the feature—not afterthoughts.
7. **No real payments in the initial MVP:** use a clearly labeled test checkout flow until a later, separately reviewed payment integration.

## Initial MVP boundary

Included:
- Account registration, login, and role-aware authorization.
- Venue and organizer profiles.
- Event creation, publishing, editing, and public discovery.
- Search, filters, pagination, and event detail.
- Ticket types and inventory.
- Reliable bookings, booking history, and cancellation rules.
- Favorites and a simple preference-based recommendation endpoint.
- Automated tests, API documentation, and local setup instructions.

Deferred:
- Real payment processing.
- Native mobile apps.
- Microservices and Kubernetes.
- Complex machine-learning recommendations.
- Multi-region deployment and advanced ticket resale.

## Proposed architecture

Use a modular monolith with a versioned REST API. Keep domain modules separate while sharing one application and relational database.

- **API layer:** request validation, response schemas, versioned routes, and consistent errors.
- **Application/domain layer:** event publishing rules, permissions, inventory, booking workflows, and recommendations.
- **Persistence layer:** relational models, constraints, indexes, and versioned migrations.
- **Background work:** add asynchronous notifications only after the core synchronous workflows are tested.
- **Frontend:** build the attendee and organizer experience after the backend's contracts and security boundaries are stable.

Keep the repository's current FastAPI/Python and Next.js/TypeScript direction unless a documented decision record justifies a change. The database choice must be settled explicitly before the persistence phase is accepted; avoid silently mixing database-specific assumptions.

## Security requirements

- Hash passwords using a dedicated password-hashing library; never store plaintext passwords.
- Validate all input and enforce authorization on the server.
- Check resource ownership for organizer-managed venues, events, tickets, and bookings.
- Keep secrets in environment variables and commit only examples.
- Never expose draft or unpublished events in public discovery.
- Do not deploy management endpoints publicly until authentication and authorization tests pass.
- Avoid storing payment-card data; the initial checkout flow is test-only.
