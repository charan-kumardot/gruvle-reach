# Architecture

## Monorepo layout

```
apps/
  web/    Next.js App Router frontend
  api/    FastAPI backend (models, routers, providers, agents, actions, workers)
scripts/
  seed_demo.py   Isolated, clearly-marked demo dataset
infra/
  searxng/       Self-hosted search config
docs/
```

## Request flow

```
Browser (Next.js, client components)
  → fetch with Bearer JWT
  → FastAPI router (/api/v1/...)
    → require_workspace_member / require_workspace_role   (tenant + RBAC gate)
    → agent or direct DB query
    → SQLAlchemy session → Postgres
```

Every workspace-scoped router depends on `require_workspace_member` (see
`app/core/deps.py`), which resolves the caller's organization membership
server-side on every request — the frontend never gets to assert which
workspace it belongs to.

## The core loop, and what actually runs it

| Spec stage | Implementation |
|---|---|
| Discovery | `ResearchAgent` (search provider → SSRF-safe fetch → deterministic signal extraction → AI extraction with anti-hallucination prompting) |
| Qualification | `app/agents/scoring.py` — deterministic weighted scoring, not an LLM call |
| Prioritization | `ChiefGrowthAgent.generate_daily_actions` — composes Action rows from top-scored companies/investor matches/opportunities/competitor changes |
| Research | `app/research/` (fetcher, evidence, extractors) + `Evidence` table |
| Content | `ContentAgent`, grounded in `BrandBrain` |
| Outreach Draft | `OutreachAgent` |
| Approval | `app/actions/policy.py` + `OutreachMessageStatus` state machine |
| Action | `app/actions/executor.py` — the only module allowed to call `EmailProvider.send` / `SocialProvider.publish_post` |
| Tracking | `OutreachEvent`, `AuditLog`, `ai_runs` |
| Learning | Not implemented as a standalone "Learning Engine" in this pass — the schema (scores, outcomes, evidence) is in place for it; see [EXTENDING.md](EXTENDING.md) |

## Provider abstractions

Every external dependency is behind an interface in `app/providers/`:

- `ai/base.py` — `AIProvider` (Ollama default, Groq, OpenAI-compatible)
- `search/base.py` — `SearchProvider` (SearxNG default, RSS, manual URLs)
- `email/base.py` — `EmailProvider` (Resend, SMTP, or a `DisabledEmailProvider` that reports `configured() == False` rather than raising)
- `social/base.py` — `SocialProvider` (LinkedIn, X, Instagram, Product Hunt — all optional, all report real capability/configuration state)
- `enrichment/base.py`, `analytics/base.py` — interfaces exist; no paid default is wired in

Factories (`build_*_provider`) read `Settings` and return the disabled/mock
variant when credentials are absent — nothing raises at import or startup
time. `app/main.py` boots with zero optional credentials configured.

## Safety boundary: agents never send

`app/agents/*` only have access to: `AIProvider`, `SearchProvider`, the
SSRF-safe fetcher, and a DB session. None of them import `EmailProvider` or
`SocialProvider`. Only `app/actions/executor.py` — called exclusively from an
authenticated, role-checked API route — is allowed to call
`email_provider.send()` or `social_provider.publish_post()`, and only after
checking the message/action is in an `APPROVED` state (`app/actions/policy.py`).

## What's fully live vs. an extension point

**Fully live, tested against real infrastructure** (see the repo's test suite
and the manual verification described in `docs/SETUP.md`): auth, multi-tenancy,
RBAC, product workspace, AI product understanding, ICP generation, company
discovery + scoring + triggers, investor directory + matching + pipeline,
opportunity feed, Action Center + Daily Founder Brief, Brand Brain + content
generation, outreach draft/approve/send via email, competitor watch, brand
monitoring, campaigns, analytics dashboard, integration marketplace,
Security Center (audit log, export, encrypted credentials), command palette.

**Real interfaces, extension points** (see [EXTENDING.md](EXTENDING.md) and
[INTEGRATIONS.md](INTEGRATIONS.md)): LinkedIn/X/Instagram/Product Hunt OAuth —
the adapters implement real authorize-URL construction and (for LinkedIn/X)
real publish calls, but require the operator to register a developer app and
supply client credentials before they can be exercised; a standalone
"Learning Engine" that mines historical outcome data for recommendations;
broader automated test coverage beyond the security-critical suite; hosted
CI/CD.
