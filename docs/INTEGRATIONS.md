# Adding an integration

Every external platform is an adapter behind a shared interface, discovered
by a factory, and surfaced in the Settings → Integrations catalog
(`GET /workspaces/{id}/integrations/catalog`,
`app/api/routers/integrations.py`). The catalog reports `configured` (does
this deployment have credentials at all) separately from `connected` (has
this specific workspace completed connecting it) — never conflate the two.

## Search (`app/providers/search/`)

```python
class SearchProvider(ABC):
    name: str
    def configured(self) -> bool: ...
    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]: ...
```

Add a new file, implement the interface, register it in
`app/providers/search/factory.py::build_search_provider`, and add a branch
for it in `Settings.search_provider`'s `Literal` type
(`app/core/config.py`).

## Email (`app/providers/email/`)

```python
class EmailProvider(ABC):
    name: str
    def configured(self) -> bool: ...
    def send(self, *, to: str, subject: str, html_body: str, text_body: str = "") -> EmailSendResult: ...
```

Register in `app/providers/email/factory.py`. Remember: only
`app/actions/executor.py` is allowed to call `.send()` — don't call it from
a router or agent directly, or you bypass the approval gate.

## Social (`app/providers/social/`)

```python
class SocialProvider(ABC):
    name: str
    def configured(self) -> bool: ...          # this app's OAuth client credentials exist
    def capabilities(self) -> SocialCapabilities: ...
    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None: ...
    def publish_post(self, *, access_token: str, body: str, media_urls=None) -> PublishResult: ...
```

If the platform's official API doesn't support a capability (Product Hunt
has no launch-submission API, Instagram requires a media asset + Meta app
review), `publish_post` must return
`PublishResult(status="manual_action_required", message="...")` — never
fake success. Register the new provider in
`app/providers/social/factory.py::get_social_providers`.

### Wiring up real OAuth credentials

1. Register a developer app on the platform.
2. Set the client ID/secret env vars (see `.env.example` — the pattern is
   `{PROVIDER}_CLIENT_ID` / `{PROVIDER}_CLIENT_SECRET`).
3. `configured()` now returns `True`; the Settings page will offer
   "Connect", which calls `GET /integrations/{provider}/authorize-url` to
   get the real platform authorize URL.
4. The OAuth callback → token exchange → `POST /integrations/{provider}/connect`
   flow (storing the resulting token via `credential_payload`) is the
   remaining piece to wire up per-platform — see the TODO note in
   `app/api/routers/integrations.py::connect_integration`. No database or
   business-logic changes are needed to add this; it's purely a new router
   handler that does the platform's token exchange and calls the existing
   `connect_integration` logic.

## Enrichment / Analytics

`app/providers/enrichment/base.py` and `app/providers/analytics/base.py`
define the interfaces with a disabled/no-op default. Follow the same
pattern: implement, add a factory, keep the disabled default as the
fallback when unconfigured.
