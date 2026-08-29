# Gruvle Reach — orientation for Claude Code

An AI-powered Founder Growth OS: research the market, find high-fit customers
and investors, surface growth opportunities, turn them into a prioritized
action plan, and draft/generate content and outreach — with a human approval
gate before anything ever sends or publishes externally. Full product
description in [README.md](README.md); system design in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); build history and what's
actually live right now in [CURRENT_STATUS.md](CURRENT_STATUS.md) — **read
that file when picking up work here**, it's kept current and this file isn't
a substitute for it.

## Monorepo layout

```
apps/web/    Next.js App Router frontend (TypeScript, Tailwind, Radix)
apps/api/    FastAPI backend (models, routers, providers, agents, actions, workers)
docs/        Architecture, security, setup, provider/integration/extension guides
scripts/     seed_demo.py — isolated, clearly-marked demo dataset
infra/       SearxNG self-hosted search config
```

## The facts that aren't obvious from the code

**There is one Postgres database (Supabase), and it is both the dev database
and the production database.** `apps/api/.env`'s `DATABASE_URL` and the
Render production service point at the same instance. Running the pytest
suite, running `alembic upgrade head`, or running the app locally all
operate on live data. Tests are written to create uniquely-named rows and
clean up after themselves specifically because of this — but there is no
separate staging/test database to fall back on. Treat every migration and
every manual DB write as a production action.

**Scheduled jobs run via GitHub Actions cron hitting secured HTTP endpoints,
not Celery.** Render's free plan rejects a `type: worker` service ("only web
services allowed for plan"), so the `gruvle-reach-worker`/Celery-beat setup
that used to be here never actually ran in production — see git history
around `.github/workflows/scheduled-tasks.yml` if you need the full story.
It's been replaced: `app/workers/tasks.py` holds the same plain functions
(daily founder brief, competitor scan, autonomous customer/investor/
marketing discovery, daily content planning, the hourly quality sweep, the
15-minute publish check, weekly learning), each exposed at
`POST /api/v1/cron/{job-name}` (`app/api/routers/cron.py`, job names listed
there) behind `require_cron_secret` (`app/core/deps.py`) — a shared secret
compared via `Header("X-Cron-Secret")`, rejecting every request if
`CRON_SECRET` isn't set (never "open by default"). `.github/workflows/
scheduled-tasks.yml` fires on the same schedule the old `beat_schedule` used
and calls the matching endpoint with a `CRON_SECRET` GitHub Actions repo
secret. **Both must be configured for this to actually run**: `CRON_SECRET`
as a Render env var on `gruvle-reach-api` (same value), and as a GitHub
Actions repository secret (Settings → Secrets and variables → Actions) —
until both are set to the same value, every scheduled trigger 401s. Timing
is best-effort (GitHub can delay scheduled workflows under load); fine for
daily/weekly jobs, and acceptable for the 15-minute/hourly ones too unless
you need tighter precision, in which case point a free external pinger
(cron-job.org or similar) at the same endpoint instead — no code change
needed, it's just another caller of the same secured route. Don't assume a
scheduled task has been firing in production; check the GitHub Actions run
history for `scheduled-tasks.yml` and the Render logs for `cron job ...
completed`/`failed` lines before trusting time-based claims about production
state.

**Alembic migrations already applied to that shared database are permanent.**
Once a migration file is committed and pushed, never edit or delete it —
write a new forward migration instead, even to fully undo a prior one. See
`apps/api/alembic/versions/014ae6027253_remove_video_generation_feature.py`
for a real example: it drops tables and a column added by two earlier
migrations rather than touching those files. When autogenerating a migration
that adds a `NOT NULL` column to a table with existing rows, add
`server_default=` by hand — Alembic's autogenerate never adds it, and the
migration will fail against live data without it.

**A push to `origin/main` does not reliably deploy either service — verify,
never assume.** There is no staging environment and no manual promote step,
which makes it easy to assume "pushed" means "live." It doesn't:

- **Render (API)** has `autoDeploy: yes` (confirmed via `GET /v1/services/{id}`)
  and usually redeploys on push, but the webhook has already silently failed
  to fire once: the video-removal commit (`0656892`) sat unpicked-up for half
  an hour while the live API kept running the prior commit against the
  already-migrated database, throwing `UndefinedColumn:
  content_variants.video_id` 500s on every endpoint touching `ContentVariant`
  (content generate/plan-today/queue/calendar, campaign content generation,
  learning analysis) until fixed by hand via
  `POST /v1/services/{id}/deploys` (Render API key in `.env.deploy`,
  `RENDER_API_KEY`). Verify: `GET /v1/services/{id}/deploys?limit=1` shows a
  `live` deploy at the new commit SHA.
- **Vercel (web) has no working git-push integration at all on this
  project** — confirmed via `gh api repos/.../deployments` and
  `.../commits/{sha}/check-runs` both returning empty for this repo's entire
  history, and directly observed: after a push, the live site's `ETag`
  stayed byte-identical and `Age` climbed in lockstep with real time for 5+
  minutes straight — a stale edge cache being served forever, not a slow
  rollout. Every frontend deploy has to be triggered by hand:
  `cd apps/web && VERCEL_TOKEN=... npx vercel --prod --yes` (token in
  `.env.deploy`). Verify: refetch a page and confirm the `ETag` changed and
  `X-Vercel-Cache` reads `PRERENDER`/`MISS`, not a long-lived `HIT`.

Always confirm with the user before `git push`ing to main or before
triggering either deploy directly, even if they approved a previous one
earlier in the session — each deploy needs its own confirmation. And after
triggering one, confirm it actually landed using the checks above before
telling the user it's live.

**The search provider is now Tavily, not SearxNG — because SearxNG's
blocking turned out to be structural, not transient.**
`gruvle-reach-searxng.onrender.com` (still deployed, still free) is the
`SearchProvider` used when `SEARCH_PROVIDER=searxng`, but its upstream
engines rate-limit or CAPTCHA-block cloud/datacenter IPs independently of
anything in this repo. Confirmed live via `GET /search?q=...&format=json`:
tried the default 4 engines, then widened to 7 plus a longer per-engine
timeout (`infra/searxng/settings.yml`) — every single one still failed
(rate-limited, CAPTCHA-blocked, timed out, or protocol-incompatible). This
is the broader trend of search engines fingerprinting and blocking known
cloud-hosting IP ranges, not fixable by picking a different scraping-based
engine. **Fixed by switching to `app/providers/search/tavily_provider.py`**
— a real authenticated API (`TAVILY_API_KEY`, both in `.env` and on the
Render API service), not scraped HTML, so it doesn't hit this at all;
verified live producing real discovered companies with real source URLs.
`SEARCH_PROVIDER=searxng`/`rss`/`manual` still work in code (the provider
abstraction didn't change, just the active choice) — if a discovery
feature ever returns suspiciously empty results again, check which
provider is actually configured before assuming the bug is in this repo's
agent code.

**The AI provider is a chain (Groq → Cerebras → Gemini → Ollama), not one
provider — because any single free tier runs out under real load.**
`AI_PROVIDER=chain` (`app/providers/ai/chain_provider.py`) tries each
configured provider in order and falls through to the next on any failure
(HTTP error, rate limit, quota exhaustion) or if a tier is unconfigured.
Two gotchas found live, not obvious from the code: **Gemini's free tier for
`gemini-3.6-flash` is 20 requests per DAY** (a `RESOURCE_EXHAUSTED` /
`GenerateRequestsPerDayPerProjectPerModel-FreeTier` quota — confirmed via
the actual error body; no amount of waiting/retrying helps until the daily
window resets), so it contributes little in practice once the tiers ahead
of it in the chain are working; and the configured **Cerebras account needs
billing set up** before `/chat/completions` will serve anything (`/models`
responds fine, completions return `payment_required`) — that tier is a
harmless no-op until then. Every tier gets one short retry-with-backoff on
a 429 (`app/providers/ai/utils.py::request_with_retry`) before giving up on
it, which helps genuine per-minute limits but can't fix a per-day one. See
`docs/AI_PROVIDERS.md` and `CURRENT_STATUS.md`'s 2026-08-29 entry.

## Conventions this codebase actually follows

- **Provider abstraction, everywhere.** Every external dependency (AI, search,
  email, social, git, deployment, storage) is an ABC in `app/providers/<kind>/`
  with a `configured()` check and a factory (`get_x_provider()`/`build_x_provider()`)
  that reads `Settings` and returns a disabled/mock implementation when
  credentials are absent — never raises at import or startup. `app/main.py`
  boots with zero optional credentials configured. Follow this shape for any
  new external integration; don't special-case one.
- **Agents never send.** `app/agents/*` can use an `AIProvider`, a
  `SearchProvider`, the SSRF-safe fetcher (`app/research/fetcher.py::safe_fetch`),
  and a DB session — nothing else. Only `app/actions/executor.py` (outreach
  email) and `app/actions/content_executor.py` (social publish) are allowed
  to call a provider's send/publish method, and only after a role check
  (`app/actions/policy.py::can_send`) and an `APPROVED`/`SCHEDULED` status
  gate. Never give an agent a path to publish directly.
- **Deterministic before AI.** Scoring (`app/agents/scoring.py`), risk
  classification (`app/agents/risk_classifier.py`), CTA selection
  (`app/agents/cta_rules.py`), quality-gate dedup/length/forbidden-word checks
  (`app/agents/content_quality_gate.py`) are all plain Python — constants and
  pure functions. AI calls are reserved for genuinely generative work (writing
  copy, extracting signal from fetched text), and always go through
  `call_ai_json` with anti-fabrication prompting grounded in `BrandBrain`/
  `ProductTruth`. Don't reach for an LLM call where a lookup table works.
- **Long-running work on a free-tier web dyno needs the async-thread pattern.**
  Render's free web service has a request timeout and can restart under
  memory pressure, silently killing in-flight synchronous work. The pattern
  used for this: insert a row in `PENDING`/`RENDERING` state and commit fast,
  do the heavy work in a background `threading.Thread` with its own
  `SessionLocal()`, and run a periodic "mark stale rows FAILED after N minutes
  of no `updated_at` progress" sweep as a self-healing safety net. This is
  also exactly how `/api/v1/cron/{job}` (see above) avoids blocking on a
  potentially slow scheduled scan. Reach for this before adding new heavy
  synchronous work to a request handler.
- **Delete features completely.** When something is removed, remove the
  models, migrations-going-forward, routes, agents, `app/workers/tasks.py`
  entries + their `/cron/{job}` mapping, frontend pages/nav/types, config
  settings, and dependencies — not just the entry point. No commented-out
  code, no unused abstractions left "in case it comes back."

## Dev commands

```bash
# Backend
cd apps/api
.venv/Scripts/activate            # or: source .venv/bin/activate
uvicorn app.main:app --reload     # http://localhost:8000
alembic upgrade head              # apply migrations (hits the live shared DB — see above)
alembic revision --autogenerate -m "..."   # then hand-check server_default on new NOT NULL columns
python -m pytest -q               # ~3-4 min, hits the live shared DB — see above

# Frontend
cd apps/web
npm run dev                       # http://localhost:3000
npm run build                     # production build + typecheck
npm run lint

# Optional local services (self-hosted SearxNG; Postgres only if not using Supabase)
docker compose up -d searxng
docker compose --profile local-db up -d postgres

# Trigger a scheduled job locally (see "Scheduled jobs run via GitHub Actions
# cron..." above) — requires CRON_SECRET set in apps/api/.env
curl -X POST http://localhost:8000/api/v1/cron/daily-founder-brief -H "X-Cron-Secret: $CRON_SECRET"
```

## Windows / git-bash quirks hit repeatedly in this repo

- Native `python.exe` cannot read git-bash's `/tmp/...` paths. Use the
  session scratchpad directory or repo-relative paths for any scratch file
  a Python process needs to read.
- `curl -F "file=@path"` fails (exit 26) when `path` contains spaces (this
  repo's own root directory does: `D:\AI gruvle reach\...`). Copy the file
  to a space-free path first.
