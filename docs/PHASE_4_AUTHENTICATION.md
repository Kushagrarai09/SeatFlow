# Module 1 — Authentication and authorization foundation

## Included in this change

- Attendee self-registration; request payloads cannot assign privileged roles or active status.
- Salted PBKDF2-HMAC-SHA256 password hashes.
- Login issues signed 30-minute access tokens and 14-day refresh tokens.
- Refresh-token rotation; previously consumed tokens are rejected.
- Logout revokes the refresh token, while issued access tokens expire naturally.
- Current-user profile endpoint and reusable role-check dependency.
- Account active-state verification for authenticated requests.
- Authentication tests use an isolated SQLite database.

## Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | \`/api/v1/auth/register\` | Register an attendee |
| POST | \`/api/v1/auth/login\` | Verify credentials and receive tokens |
| POST | \`/api/v1/auth/refresh\` | Rotate a refresh token |
| POST | \`/api/v1/auth/logout\` | Revoke refresh token (requires access token) |
| GET | \`/api/v1/auth/me\` | Return the logged-in user's profile |

Self-registration always creates an attendee. Organizer/admin privileges must be assigned through a trusted administrative workflow, never accepted from a public registration payload.

## Local setup

1. Install the backend development requirements.
2. Copy \`.env.example\` to \`.env\`.
3. Set \`JWT_SECRET_KEY\` to a unique random value of at least 32 characters.
4. Configure the database URL and ensure the process loads the environment variables before startup.
5. Start the API and try the endpoints through \`/docs\`.

Never use the example secret in a shared or deployed environment.

## Security boundaries and follow-up

- Passwords and password hashes are never included in API responses.
- Refresh-token records store digests of token identifiers instead of full tokens.
- Logout does not immediately invalidate already issued access tokens; they expire within 30 minutes.
- Rate limiting, email verification, password reset, MFA, and operational secret rotation are not included yet.
- Role-check helpers exist, but the current organizer/venue/event management routes still need to enforce authentication and per-resource ownership. Do not deploy those management routes publicly before that work is complete.
- Account roles are \`attendee\`, \`organizer\`, and \`admin\`. Registration only grants \`attendee\`.

## Verification checklist

- [ ] Run \`pytest -q\` in the backend virtual environment.
- [ ] Register an attendee and ensure sensitive fields are absent from the response.
- [ ] Try to submit \`role: "admin"\`; expect 422.
- [ ] Log in and call \`/api/v1/auth/me\` with the returned access token.
- [ ] Confirm incorrect credentials return 401.
- [ ] Refresh once and confirm the old refresh token cannot be reused.
- [ ] Log out and confirm the refresh token can no longer be refreshed.
- [ ] Protect management routes and verify organizer ownership before public deployment.
