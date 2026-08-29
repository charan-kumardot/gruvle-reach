# Local setup

## Prerequisites

- Python 3.12+
- Node.js 20+
- A PostgreSQL database (a free Supabase project works — this repo was
  built and tested against one)
- Docker, for the self-hosted SearxNG search backend (optional but
  recommended)
- [Ollama](https://ollama.com) installed locally if you want the default,
  fully-free AI path — otherwise a Groq API key (free tier)

## 1. Environment

```bash
cp .env.example .env
```

Only `DATABASE_URL` needs to be real for the app to start. Everything else
degrades gracefully:

- `AI_PROVIDER=ollama` (default) — needs Ollama running at `OLLAMA_BASE_URL`
  with `OLLAMA_MODEL` pulled (`ollama pull llama3.1`, or any chat model —
  this repo was verified against `qwen3:8b` and `qwen3:4b`). AI calls on
  CPU-only Ollama are slow (single digits of tokens/sec) — that's expected,
  not a bug. Switch to Groq for speed during development.
- `SEARCH_PROVIDER=searxng` (default) — needs a SearxNG instance at
  `SEARXNG_BASE_URL`. `docker compose up -d searxng` brings one up with JSON
  output already enabled (`infra/searxng/settings.yml`).
- `EMAIL_PROVIDER=disabled` by default — outreach drafting/approval works
  either way; sending needs `EMAIL_PROVIDER=resend` + `RESEND_API_KEY`, or
  `smtp` + SMTP settings.
- Social provider env vars (`LINKEDIN_CLIENT_ID`, etc.) — leave blank; the
  Settings → Integrations page will show them as "Not configured" and the
  app functions fully without them.

Generate a real `ENCRYPTION_KEY` (used to encrypt stored integration
credentials):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. Database migrations

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
alembic upgrade head
```

If your Postgres provider uses a transaction-pooled connection (e.g.
Supabase's pooler on port 6543), the app already disables psycopg's
server-side prepared statements for compatibility
(`prepare_threshold=None` in `app/db/session.py` and `alembic/env.py`). If
you hit migration issues anyway, set `DATABASE_URL_DIRECT` to a
non-pooled connection string.

## 3. Run the API

```bash
uvicorn app.main:app --reload
```

Check `http://localhost:8000/health` and `http://localhost:8000/ready`
(the latter verifies the DB connection).

## 4. Run the frontend

```bash
cd apps/web
npm install
npm run dev
```

`apps/web/.env.local` should have `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.

## 5. Scheduled jobs (optional for local dev)

Scheduled jobs (daily founder brief, discovery, content planning, etc.) run
via secured HTTP endpoints, not a background worker process — see
`CLAUDE.md`. Trigger one locally:

```bash
cd apps/api
curl -X POST http://localhost:8000/api/v1/cron/daily-founder-brief -H "X-Cron-Secret: $CRON_SECRET"
```

Needs `CRON_SECRET` set in `.env`. In production, `.github/workflows/
scheduled-tasks.yml` calls these same endpoints on a schedule.

## 6. Demo data

```bash
cd apps/api
python ../../scripts/seed_demo.py
```

Creates an isolated `[DEMO]` organization/workspace/product with the
"Gruvle Radar" example from the product spec. Login at
`http://localhost:3000/login`:

```
demo@gruvle-reach.io / demo12345
```

## 7. Full stack via Docker Compose

```bash
docker compose up -d --build
```

Brings up SearxNG, the API, and the web app. Postgres is optional
(`docker compose --profile local-db up -d postgres`) if you'd rather not use
a managed database.

## Running tests

```bash
cd apps/api
pytest app/tests -v
```

Tests run against whatever `DATABASE_URL` is configured — they create their
own uniquely-named organizations and clean up after themselves, but don't
point this at a production database.

## Troubleshooting

- **"AI provider unavailable"** — confirm `AI_PROVIDER` matches a running
  service (`curl http://localhost:11434/api/tags` for Ollama,
  or check `GROQ_API_KEY` is set).
- **Company discovery returns nothing** — confirm SearxNG is reachable at
  `SEARXNG_BASE_URL` and returns JSON: `curl "http://localhost:8888/search?q=test&format=json"`.
  If that 403s, your SearxNG instance has JSON output disabled — use the
  `infra/searxng/settings.yml` this repo ships, or set `search.formats` to
  include `json` in your own instance's config.
- **Emails don't send** — check `Settings → Integrations` in the app; the
  catalog shows exactly why (`configured: false` means the env var isn't
  set, `connected: false` means the workspace hasn't connected it yet via
  `POST /integrations/resend/connect`).
