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

**Render's free plan silently drops the Celery beat scheduler.** `render.yaml`
declares a `type: worker` service (`gruvle-reach-worker`) running
`celery -A app.workers.celery_app worker --beat`, and `docker-compose.yml`
runs the same thing locally — but Render's API rejects `background_worker`
services on the free plan ("only web services allowed for plan"). That
worker has never successfully deployed to production. **Every entry in
`celery_app.py`'s `beat_schedule` — daily founder brief, competitor scan,
autonomous customer/investor discovery, daily content planning, scheduled
publish, weekly learning, everything — currently only runs if you run the
worker yourself (e.g. locally, or via `docker compose up worker`).** Nothing
here runs automatically in production today. Don't assume a scheduled task
has been firing; check whether the worker is actually deployed before
trusting time-based claims about production state. Fixing this for real
means either upgrading the Render plan or moving beat to something the free
tier allows.

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

**The self-hosted SearxNG search provider can go quietly to zero results —
and this looks structural, not transient.** `gruvle-reach-searxng.onrender.com`
(also free-tier) is the default `SearchProvider`. Its upstream engines
rate-limit or CAPTCHA-block cloud/datacenter IPs independently of anything
in this repo. Confirmed live via `GET /search?q=...&format=json`: with only
the default 4 engines enabled (brave/duckduckgo/google cse/startpage), all
4 failed. Tried widening the pool (`infra/searxng/settings.yml`'s `engines:`
list) to 7 engines total plus an increased per-engine timeout
(`outgoing.request_timeout: 8.0`) — every single one still failed:
brave/google cse rate-limited, startpage/qwant CAPTCHA-blocked,
duckduckgo/mojeek timed out even at 8s, yahoo hit an "HTTP protocol error"
(likely an engine-module compatibility issue, not a block). This is
consistent with the broader trend of search engines fingerprinting and
blocking known cloud-hosting IP ranges, not something fixable by picking a
different scraping-based engine — a real fix likely needs either an
official paid/free-tier search API (e.g. Brave Search API with a real API
key, not scraping) or a residential/rotating proxy in front of SearxNG,
both bigger changes than a settings tweak. Every discovery feature built on
search (company/investor/marketing discovery, brand mention scanning) degrades
gracefully to an empty list when this happens — no error, just nothing
found — which is correct behavior for the provider abstraction but can look
identical to "the feature is broken" from the outside. If a discovery
feature returns suspiciously empty results, check SearxNG's own
`unresponsive_engines` before assuming the bug is in this repo's code.

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
  of no `updated_at` progress" sweep as a self-healing safety net. Reach for
  this (or, better, get the Celery worker actually deployed) before adding
  new heavy synchronous work to a request handler.
- **Delete features completely.** When something is removed, remove the
  models, migrations-going-forward, routes, agents, workers, beat schedule
  entries, frontend pages/nav/types, config settings, and dependencies — not
  just the entry point. No commented-out code, no unused abstractions left
  "in case it comes back."

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

# Optional local services (Redis + self-hosted SearxNG; Postgres only if not using Supabase)
docker compose up -d redis searxng
docker compose --profile local-db up -d postgres

# Celery worker + beat (nothing runs on a schedule without this — see above)
cd apps/api && celery -A app.workers.celery_app worker --beat --loglevel=info
```

## Windows / git-bash quirks hit repeatedly in this repo

- Native `python.exe` cannot read git-bash's `/tmp/...` paths. Use the
  session scratchpad directory or repo-relative paths for any scratch file
  a Python process needs to read.
- `curl -F "file=@path"` fails (exit 26) when `path` contains spaces (this
  repo's own root directory does: `D:\AI gruvle reach\...`). Copy the file
  to a space-free path first.
