# Security

## Tenant isolation

Every workspace-scoped table has a `workspace_id` column. Every router that
touches one depends on `require_workspace_member` (`app/core/deps.py`), which:

1. Loads the workspace by the `workspace_id` path parameter.
2. Checks the authenticated user has an `OrganizationMember` row for that
   workspace's organization.
3. Returns **404** (not 403) if either check fails — a non-member never
   learns whether a given workspace ID exists.

This is enforced server-side on every request; the frontend's stored
`workspace_id` is never trusted as an authorization decision. See
`app/tests/test_tenant_isolation.py`.

## RBAC

Roles: `OWNER > ADMIN > MEMBER > VIEWER` (`app/db/models/enums.py::OrgRole`).
`require_workspace_role(min_role)` wraps `require_workspace_member` with a
rank check. Viewers can read; only MEMBER+ can create/mutate; only ADMIN+ can
delete or manage integrations/research sources. See `app/tests/test_rbac.py`.

## Approval gate for external actions

No code path can send an email or publish a social post without a human
approval step:

- `OutreachMessage.status` must be `APPROVED` before `send_outreach_email`
  (`app/actions/executor.py`) will touch it — verified in
  `app/tests/test_approval_gate.py`.
- Approving requires MEMBER+ role (`app/actions/policy.py::can_approve`).
- Agents (`app/agents/*`) have no reference to `EmailProvider` or
  `SocialProvider` — they can only write recommendations to the database.

## SSRF protection

`app/research/fetcher.py::safe_fetch` is the only way anything in this
codebase makes an outbound request to a URL that came from research data or
a user. It:

- Resolves DNS itself and rejects private/loopback/link-local/multicast/
  reserved ranges and known cloud metadata addresses (169.254.169.254,
  100.100.100.200) before connecting.
- Re-validates on every redirect hop (redirects aren't auto-followed by the
  underlying HTTP client — each hop is validated manually).
- Enforces a hard timeout and a streamed response-size cap.
- Only allows `http`/`https` schemes and blocks a set of non-web ports.

See `app/tests/test_ssrf.py`.

## Credential handling

- Integration credentials are encrypted at rest with Fernet
  (`app/core/security.py::CredentialCipher`), keyed by `ENCRYPTION_KEY`.
- Audit log writes never include the raw credential payload — see
  `app/api/routers/integrations.py::connect_integration` (metadata only
  records the provider name) and `app/tests/test_credentials.py`.
- Nothing is ever passed into an AI prompt from `integration_credentials`.
- Revocation: `POST /integrations/{provider}/disconnect` deletes the stored
  credential row and marks the integration `DISCONNECTED`.

## Passwords and sessions

- Passwords are hashed with bcrypt directly (`app/core/security.py`), never
  logged, and truncated to bcrypt's 72-byte input limit before hashing (not
  silently mis-handled).
- Sessions are stateless JWTs (`HS256`, signed with `SECRET_KEY`), default
  7-day expiry.

## Data export and deletion

`GET /workspaces/{id}/export/{entity}` (CSV/JSON) and
`DELETE /workspaces/{id}/data/{entity}/{id}` cover the Security Center's
data-control requirements for the core exportable entities (companies,
investors, opportunities) — extend `_EXPORTABLE` in
`app/api/routers/settings.py` for more.

## Demo data

`scripts/seed_demo.py` creates an isolated organization/workspace
(`is_demo=True`) with every synthetic record prefixed `[DEMO]`. It never
writes into a real user's workspace and is not invoked by any production
code path.

## Reporting a concern

This is a local/self-hosted reference build. If you deploy it, review
`.env` handling, rotate `SECRET_KEY`/`ENCRYPTION_KEY` per environment, and
put TLS in front of the API — none of that is done for you by this repo.
