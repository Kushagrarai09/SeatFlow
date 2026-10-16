# Module 1 — Authentication and authorization foundation

## Included

- Attendee self-registration; callers cannot choose their role or account-active state.
- Salted PBKDF2-HMAC-SHA256 password hashes.
- Login returns a signed 30-minute access token and a 14-day refresh token.
- Refresh token rotation uses a conditional database update so a consumed token cannot be reused.
- Logout revokes the refresh token; existing access tokens expire naturally within 30 minutes.
- \`GET /api/v1/auth/me\` returns a safe account profile.
- Role dependencies for \`attendee\`, \`organizer\`, and \`admin\`.
- Admin-only role assignment between attendee and organizer, plus account activation/deactivation.
- Organizer profiles and organizer-created venues are linked to user accounts.
- Event, venue, and organizer management mutations require organizer/admin permissions. Organizers may modify only events linked to their own organizer profile and cannot use another organizer's privately owned venue.
- A database migration adds account, refresh-token, and account-ownership fields.
- SQLite API tests cover authentication and management endpoint access boundaries.

## Authentication endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | \`/api/v1/auth/register\` | Register an attendee |
| POST | \`/api/v1/auth/login\` | Verify credentials and receive tokens |
| POST | \`/api/v1/auth/refresh\` | Rotate a refresh token |
| POST | \`/api/v1/auth/logout\` | Revoke refresh token (requires access token) |
| GET | \`/api/v1/auth/me\` | Return the logged-in user's profile |

## Administrator endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| PATCH | \`/api/v1/admin/users/{user_id}/role\` | Assign attendee or organizer role |
| PATCH | \`/api/v1/admin/users/{user_id}/active\` | Activate/deactivate a user |

Only authenticated administrators can call these endpoints. The public role endpoint intentionally cannot create another admin account or change an existing admin's role.

## Local setup

1. Work from the \`backend\` directory and install development requirements.
2. Copy \`.env.example\` to \`.env\`.
3. Set \`JWT_SECRET_KEY\` to a unique random value at least 32 characters long. Generate one with \`python -c "import secrets; print(secrets.token_urlsafe(48))"\`.
4. Configure \`DATABASE_URL\` and ensure your shell/process manager actually loads environment variables from \`.env\`.
5. Run \`alembic upgrade head\` against your development database.
6. Start the API and use \`/docs\` to explore the endpoints.

Never use the example secret outside local-only experimentation.

## Provisioning the first administrator

Register the account through \`POST /api/v1/auth/register\`, then use trusted database access from the backend directory:

\`\`\`powershell
python -m app.manage_account admin@example.com admin
\`\`\`

Replace the email with the registered account's email. This CLI requires direct database access and must never be exposed through a public endpoint. After that, sign in again and use the resulting access token to promote attendee accounts to organizer role via the admin endpoint.

## Security boundaries

- Passwords/password hashes are never returned by APIs.
- Refresh-token rows store SHA-256 digests of token identifiers, not the raw refresh tokens.
- A deactivated account cannot use an existing access token or refresh token.
- Logout does not immediately invalidate already-issued access tokens; they expire naturally within 30 minutes.
- Rate limiting, email verification, password reset, MFA, and operational secret rotation are not included yet.
- Existing database rows created before the ownership migration have no account owner. They should be reviewed and explicitly linked by an administrator before organizer accounts manage them.
- Do not deploy the application publicly until the migration, tests, secret configuration, and deployment controls have been verified.

## Verification checklist

- [ ] Run \`pytest -q\` from \`backend\`.
- [ ] Register an attendee and check that sensitive fields are absent.
- [ ] Try to submit \`role: "admin"\`; expect 422.
- [ ] Log in and request \`/api/v1/auth/me\` with the access token.
- [ ] Confirm unauthenticated mutations return 401 and attendees receive 403 for organizer-only mutations.
- [ ] Rotate a refresh token and confirm the original cannot be reused.
- [ ] Log out and confirm the refresh token cannot be refreshed afterward.
- [ ] Use a provisioned admin to promote a user to organizer.
- [ ] Confirm organizer A cannot update organizer B's event.
- [ ] Apply Alembic migrations to a disposable database and verify upgrade/downgrade behavior.
