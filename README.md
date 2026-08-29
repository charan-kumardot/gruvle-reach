# Gruvle Reach

**Find the people, opportunities and actions that move your product forward.**

Gruvle Reach is an AI-powered Founder Growth OS. It researches your market, finds
high-fit customers and investors, discovers growth opportunities, and turns them
into a prioritized, evidence-backed action plan — with a human approval gate before
anything is ever sent or published externally.

This is **not** a lead-gen scraper, a generic CRM, a bulk-outreach tool, or a
chatbot wrapper. The core loop is:

```
Discovery → Qualification → Prioritization → Research → Content
  → Outreach Draft → Approval → Action → Tracking → Learning
```

## Status

This build implements the full core product loop end-to-end against real
infrastructure (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for exactly
what's live vs. scaffolded-for-extension). Everything below has been verified
running against a live Postgres database, a real local Ollama model, and a
real Groq model — see [docs/SETUP.md](docs/SETUP.md) for how to reproduce.

## Quick start

**Requirements:** Python 3.12+, Node 20+, PostgreSQL (or a Supabase project),
Docker (optional, for SearxNG), and either [Ollama](https://ollama.com)
running locally (free, default) or a Groq API key (free tier available).

```bash
# 1. Configure
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL. Everything else has a working default.

# 2. Backend
cd apps/api
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend (new terminal)
cd apps/web
npm install
npm run dev

# 4. Optional: bring up self-hosted search (new terminal, from repo root)
docker compose up -d searxng

# 5. Optional: seed demo data (clearly marked, isolated workspace)
cd apps/api && python ../../scripts/seed_demo.py
# Login at http://localhost:3000/login with demo@gruvle-reach.io / demo12345
```

Full setup detail, including Ollama model selection, is in
[docs/SETUP.md](docs/SETUP.md).

## Documentation

- [docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md) — every feature walked through end to end with one example product, real API output, integration requirements, and flow diagrams
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design, what's fully live vs. extension points
- [docs/SECURITY.md](docs/SECURITY.md) — tenant isolation, RBAC, SSRF protection, credential handling, approval gates
- [docs/SETUP.md](docs/SETUP.md) — local development, environment variables, migrations
- [docs/AI_PROVIDERS.md](docs/AI_PROVIDERS.md) — Ollama/Groq/OpenAI-compatible setup
- [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) — adding a new provider adapter
- [docs/EXTENDING.md](docs/EXTENDING.md) — adding a new agent or research source
- [docs/VISIBILITY.md](docs/VISIBILITY.md) — the AI website optimization module: connect a site's GitHub repo, get scanned SEO/GEO opportunities turned into reviewable pull requests

## Stack

- **Frontend:** Next.js (App Router) · TypeScript · Tailwind CSS · Radix UI · Framer Motion
- **Backend:** FastAPI · SQLAlchemy 2 · Alembic · Pydantic
- **Database:** PostgreSQL
- **Scheduling:** GitHub Actions cron → secured `/cron/*` HTTP endpoints (no queue/broker — see `CLAUDE.md`)
- **AI:** Provider abstraction — Ollama (default, local, free), Groq, or any OpenAI-compatible endpoint
- **Search:** Provider abstraction — self-hosted SearxNG (default, free), RSS/Atom, or manual URL submission

Every external integration (email, LinkedIn, X, Instagram, Product Hunt) is an
optional adapter behind a shared interface. The app starts and the full core
loop works with **zero** paid credentials configured.
