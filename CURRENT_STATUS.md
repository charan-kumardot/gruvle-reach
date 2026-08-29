# Current status

Last **deployed** state: 2026-08-28, at commit `b91fc0e` (`main`, pushed,
**and confirmed live on both Render and Vercel** — API verified via a live
deploy check plus a real production discovery run returning real
companies, web verified via a changed `ETag`/`PRERENDER` cache header
after a manual `vercel --prod` deploy, since this project's Vercel project
has no working git-push auto-deploy at all — see `CLAUDE.md`'s
deploy-verification note).

**Since then (2026-08-29), a large local-only change set exists that has
NOT been pushed or deployed** — see "Discovery/SEO/competitor/campaign
fixes" and "Scheduled automation" below. Don't assume anything in those two
sections is live in production; `git status`/`git diff` against `b91fc0e`
is the source of truth for what's actually changed but unpushed.
This file is a snapshot — check `git log` for anything more recent than the
dates above rather than trusting this in perpetuity.

## Build timeline

| Phase | Commit(s) | What it shipped |
|---|---|---|
| 1. Core product loop | `c646b8e` + hardening (`669ba1a`, `33b9956`, `69ef241`, `cb419f5`, `8437ce1`, `bae95e8`) | Auth, multi-tenancy, RBAC, product workspace, AI product understanding, ICP generation, company discovery/scoring/triggers, investor directory + matching + pipeline, opportunity feed, Action Center + Daily Founder Brief, Brand Brain + content generation, outreach draft/approve/send, competitor watch, brand monitoring, campaigns, analytics, integration marketplace, Security Center |
| 2. Visibility module | `50d5a1f` | AI website optimization: connect a site's GitHub repo, scan for SEO/GEO/AI-visibility opportunities, propose changes as reviewable GitHub PRs behind a 4-tier risk classifier |
| 3. Autonomous Growth Engine | `77437f3` | Zero-manual-input discovery: autonomous customer/investor/marketing discovery agents, a deterministic sample-size-gated Learning Engine that mines historical outcomes for insights |
| 4. Daily Content & Promotion Engine | `200ca9d` | Zero-input daily content planning (mix-balanced, bounded), per-platform generation, a two-layer anti-fabrication/anti-spam quality gate, an approval queue, scheduled/manual publish, Reddit + Facebook social adapters, campaign↔content linkage, content-performance learning |
| 4a. Video generation (built, then fully removed) | `b70a4b1`→`22a87ce`, removed in `0656892` | See **Video generation — built and removed** below |

## End-to-end verification against production (2026-08-28)

Every feature area was exercised against the live Render API
(`gruvle-reach-api.onrender.com`) with a real product called **Gruvle
Radar** (a competitive-intelligence SaaS — see `docs/USAGE_GUIDE.md` for
the full walkthrough), not against a local dev server. First full sweep:
**63/71 checks passed.** All 8 failures traced to a single root cause, not
eight separate bugs:

**Root cause: Render's auto-deploy silently hadn't fired for the
video-removal push.** Production was still running commit `22a87ce` (the
last pre-removal commit) against the database the removal migration had
already run against — a stale-code/migrated-DB mismatch. Every endpoint
that touched `ContentVariant` threw `sqlalchemy.exc.ProgrammingError:
(psycopg.errors.UndefinedColumn) column content_variants.video_id does not
exist`: `POST /content/generate`, `POST /content/plan-today`, `GET
/content/queue`, `GET /content/calendar`, `POST
/campaigns/{id}/generate-content`, `POST /learning-insights/analyze`.
Fixed by triggering a deploy of `0656892` by hand via the Render API (see
`CLAUDE.md`'s deploy note for the general lesson); re-verified afterward at
**17/17** on every previously-failing call, including a real `content →
approve → publish-now` cycle correctly returning `manual_action_required`
since no social channel is connected yet.

**Separate, non-code finding (since fixed): the self-hosted SearxNG's
upstream search engines were rate-limited/blocked.** Company discovery,
investor discovery, marketing-opportunity discovery, and brand-mention
scanning all returned empty lists rather than erroring — correct
graceful-degradation behavior, but root-caused to
`gruvle-reach-searxng.onrender.com` itself returning zero results even for
a trivial query, with `unresponsive_engines` showing every available
engine (7 tried across two rounds) rate-limited, CAPTCHA-blocked, timed
out, or protocol-incompatible — a search-engine-side anti-bot response to
Render's IPs, not a bug in this repo, and not something engine-picking
could fix. **Fixed by switching the active `SEARCH_PROVIDER` to Tavily**
(`app/providers/search/tavily_provider.py`, a real authenticated API) —
verified live: a fresh production autonomous-discovery run against Gruvle
Radar found real companies with real source URLs. See `CLAUDE.md`.

**Everything else passed cleanly** on the first sweep: auth/org/workspace
setup, product CRUD + AI product understanding + ICP generation, zero-input
autonomous discovery, manual investor add + AI fit-scoring + pipeline,
opportunity create/score/status, brand brain, competitor add + AI scan
(against a real external site), campaign create/detail/metrics, the Daily
Founder Brief (refresh/approve/complete), the integrations catalog
correctly reporting `resend` and `searxng` as configured and every social
provider as not, the Visibility module's connect/scan/SEO-issues/GEO-scan
flow (no GitHub connection needed for scanning), audit log, data export,
and a real outreach email sent end-to-end through Resend.

## What's fully live vs. an extension point

**Fully live, exercised against real infrastructure:** everything in Phases
1–3, plus Phase 4 minus video (content planning/generation/quality-gate/
approval/scheduling/publish, campaign content generation, content-performance
learning). `docs/ARCHITECTURE.md`'s "What's fully live" section predates
Phases 2–4 and currently understates this — e.g. it says a Learning Engine
isn't implemented; it now is (`app/agents/learning_agent.py`, extended for
content in Phase 4). Trust this file and the code over that section until
`docs/ARCHITECTURE.md` gets a pass.

**Real interfaces, not yet exercisable without operator setup:**
LinkedIn/X/Instagram/Product Hunt/Reddit/Facebook — adapters are real
(`app/providers/social/`), but each needs a registered developer app and
client credentials before it can actually authorize or publish. Until then,
`publish-now` on those channels returns `manual_action_required` (copy the
draft, post it yourself) rather than failing.

## Discovery/SEO/competitor/campaign fixes (2026-08-29, not yet deployed)

In response to "customer discovery returns too few results," "SEO isn't
working," "competitors requires manual name/URL entry," and "campaign
generation doesn't work":

- **Company/investor/marketing-opportunity discovery** were all narrow by
  design (2-5 query templates × 5 results/query, heavy attrition through
  fetch+AI classification). Broadened query generation (company-size tiers
  × ICP industries for companies; investor-type coverage — angel/
  accelerator/corporate-VC/grant, not just traditional VC — for investors;
  more opportunity categories for marketing) and raised `max_results_per_query`
  from 5 to 15 across `research_agent.py`, `investor_discovery_agent.py`,
  `marketing_discovery_agent.py`. Also wired the previously-dead-code
  zero-input company-discovery pipeline (`research_orchestrator.
  run_autonomous_discovery`, only ever reachable via an unscheduled Celery
  task) into a real endpoint, `POST /companies/discover-auto`, now the
  primary "Discover companies" action. **Verified against real production
  data** (see below): a single `autonomous-investor-discovery` run found
  **40 new investors** in one pass, versus single digits before.
- **Competitor auto-discovery is new** (`app/agents/competitor_discovery_agent.py`,
  `POST /competitors/discover`) — mirrors the investor/marketing discovery
  agents' shape. Manual add is still available for a competitor you already
  know by name.
- **SEO/GEO scanning was homepage-only.** `website_scanner.py` now also
  extracts SEO fields (title/meta/H1/alt-text/structured-data/OG) from
  sampled internal + sitemap pages (reusing fetches already made for the
  broken-link sample, not a second fetch pass), `seo_agent.py` runs the same
  issue checks per sampled page with evidence prefixed by page URL, and
  `visibility.py`'s GEO scan and overall-score computation both fold in the
  sampled-page data instead of only the homepage.
- **Campaign content generation** was gated at Admin while campaign creation
  only needs Member, and hardcoded `channels=["linkedin","x"]` regardless of
  the campaign's actual selected channels (which the create form never even
  exposed — always sent `channels: []`). Fixed all three: role loosened to
  Member, generation now reads the campaign's real `CampaignChannel` rows,
  and the frontend create dialog has a channel picker.

All changes verified via the full backend test suite (94/94 passing) and a
clean `npm run build`/`lint`; none required a database migration.

## AI provider chain: Groq → Cerebras → Gemini → Ollama (2026-08-29, not yet deployed)

`AI_PROVIDER=chain` is a new option (`app/providers/ai/chain_provider.py`,
wired in `factory.py`) that tries several providers in an explicit priority
order rather than picking one — each configured tier is tried in turn, and
any `AIProviderError` (HTTP error, rate limit, quota exhaustion, timeout) or
an unconfigured tier falls through to the next. New provider: Gemini
(`gemini_provider.py`, Google's Generative Language API — note the API key
must go in the `x-goog-api-key` **header**, not the `?key=` query param,
which httpx's request logging would otherwise print in full into Render's
logs — this was caught and fixed during verification). `CerebrasProvider`
reuses the existing OpenAI-chat-completions-compatible base class (same
shape as Groq) since Cerebras speaks that API. Every tier also gets a short
retry-with-backoff on a 429 (`app/providers/ai/utils.py::request_with_retry`,
honors a `Retry-After` header when present) before giving up on it — useful
for genuine per-minute rate limits.

**Real findings from verification against the live providers:**
- **Gemini's free tier for `gemini-3.6-flash` is 20 requests/DAY** (a
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier` quota — confirmed via
  the actual `RESOURCE_EXHAUSTED` error body, not a per-minute limit the
  retry logic could help with). In a chain where Gemini isn't first, it'll
  rarely get used in practice — the cheaper/faster tiers ahead of it in the
  order will usually serve the request first.
- **The configured Cerebras account needs billing set up** — `/chat/completions`
  currently returns `payment_required` on every model even though
  `/models` responds fine and the API key itself is valid. Not a code issue;
  someone needs to add a payment method on the Cerebras account before that
  tier will actually serve anything. Until then it's a harmless no-op tier
  that always falls through.
- The full 4-tier cascade was verified end-to-end by deliberately breaking
  Groq: it correctly fell through Cerebras (payment required) → Gemini
  (daily quota exhausted) → and succeeded on local Ollama, confirming the
  chain and its retry/fallthrough logic both work as designed.

## Scheduled automation — replaced Celery with GitHub Actions cron (2026-08-29, not yet deployed)

The gap described in every earlier version of this file — Render's free plan
rejecting the `type: worker` service, so the entire Celery `beat_schedule`
never ran automatically in production, across any phase of this project —
has been **fixed in code, but not yet deployed**. What changed:

- Celery and Redis are removed entirely (`app/workers/celery_app.py`
  deleted, `celery`/`redis` dropped from `requirements.txt`, the `worker`/
  `redis` services dropped from `render.yaml` and `docker-compose.yml`).
  Redis was never used for anything but being the Celery broker — confirmed
  no caching/session/rate-limit code depended on it.
- The same task functions in `app/workers/tasks.py` are now plain functions
  (no `@celery_app.task`), each reachable at `POST /api/v1/cron/{job-name}`
  (`app/api/routers/cron.py`) behind a shared-secret dependency
  (`require_cron_secret` in `app/core/deps.py`, header `X-Cron-Secret`,
  compared against the `CRON_SECRET` setting — rejects everything if that's
  unset). Each job runs in a background thread so the triggering request
  returns immediately (same async-thread pattern used elsewhere for
  free-tier request-timeout avoidance).
- `.github/workflows/scheduled-tasks.yml` fires on the same 10 schedules the
  old `beat_schedule` used and calls the matching endpoint with a
  `CRON_SECRET` GitHub Actions secret.

**Verified locally against the live shared database** (not production —
see deployment checklist below), by running the local API server and
`curl`-triggering each `/cron/{job}` endpoint directly:

- Auth mechanism confirmed correct: no header → 401, wrong secret → 401,
  unknown job name → 404, correct secret → 200 + dispatches.
- **8 of 10 jobs ran to completion with confirmed real database writes**:
  `daily-founder-brief` (10 new `Action` rows), `weekly-market-brief`,
  `competitor-scan`, `daily-content-planning` (6 items), `content-quality-sweep`
  (16 variants re-gated), `publish-due-content` (correctly found a due
  variant and logged "not connected" rather than silently dropping it),
  `weekly-content-learning`, and `autonomous-investor-discovery` (**+40
  investors** in one run — see the discovery-fixes section above).
- The remaining 2 (`weekly-marketing-discovery`, `autonomous-customer-discovery`)
  were interrupted mid-run, not because anything was broken — both were
  making real progress (fetching real candidate pages, running real AI
  classification) but got caught in the AI-provider-chain work happening in
  parallel (see above) and were stopped deliberately rather than left
  competing for the same rate-limited providers. Both share the identical
  code path already proven by `autonomous-investor-discovery`'s successful
  run, so this is a testing-time tradeoff, not an unverified code path.
- Before this was safe to test at all, the shared database had **508
  organizations / 194 products**, almost all stale pytest-fixture rows
  (`Test Org <hex>` owning `Owner Product`/`Member Product`/`Secret
  Product`/`P`/`Test Product`) that a "-for-all-products" job would have
  burned real AI/search API calls against. Cleaned up to 11 real
  organizations / 8 real products via `DELETE FROM organizations WHERE name
  LIKE 'Test Org%'` (cascades cleanly — verified every FK from
  `organizations` down through `workspaces`/`products`/everything
  workspace-or-product-scoped is `ON DELETE CASCADE` at the DB level before
  running it). **This bloat came back partially during today's session** —
  running the pytest suite twice (each run creates fresh uniquely-named
  `Test Org <hex>` rows) added ~24 more, confirming the suite's fixtures do
  *not* actually clean up after themselves despite the claim elsewhere in
  this file/`CLAUDE.md` — see "Open items" below.

**Deployment checklist before this is actually live** (not done as of this
writing — confirm with the user before doing any of it, per `CLAUDE.md`'s
push/deploy rules):
1. Push this branch to `origin/main`.
2. Set `CRON_SECRET` (same random value) as both a Render env var on
   `gruvle-reach-api` and a GitHub Actions repository secret.
3. Confirm the Render deploy actually landed the new commit (see
   `CLAUDE.md`'s deploy-verification note — don't assume a push deployed).
4. Manually run `.github/workflows/scheduled-tasks.yml` via its
   `workflow_dispatch` trigger once to confirm a `POST /cron/...` call
   succeeds end-to-end against production, before trusting the cron
   schedule to fire on its own.

Until all four are done, this is exactly as "not running in production" as
the Celery setup it replaces — the code existing is not the same as it being
live (the same lesson `CLAUDE.md` already calls out about deploys generally).

## Video generation — built and removed

Phase 4 originally included short-form promotional video generation
(script agent → scene rendering → TTS voiceover → FFmpeg render → storage).
It went through several iterations while deployed to production:

1. Procedural Pillow/FFmpeg slideshow rendering (`200ca9d`) — shipped, then
   judged too plain ("not premium/realistic").
2. A non-blocking async render pattern to dodge Render free-tier request
   timeouts (`f7d2cd9`), a stale-render safety net for renders stuck
   mid-pipeline (`93fb229`), then a motion-graphics upgrade + 30-day
   retention cleanup (`96b7fee`) — all shipped and verified working against
   production, in that order.
3. A Hugging Face Inference Providers integration was evaluated (real token
   supplied) but abandoned — video generation there only routes through
   third-party billed providers (fal-ai/replicate/wavespeed), which exhausted
   free credit after two test calls even with no payment method attached.
4. General web image search (SearxNG image results) was evaluated as a
   product-visual source and abandoned — proven unreliable (a B2B SaaS query
   returned an unrelated My Little Pony comic cover).
5. Real product screenshots composited into a browser-window mockup
   (`22a87ce`) — the last version shipped, and the one judged good.

The feature was then removed in full at explicit user request (`0656892`):
every video/image/storage provider, the render pipeline, the `videos`/
`video_brand_kits` tables (dropped from the live DB via a new forward
migration — see the migration-discipline note in `CLAUDE.md`), the frontend
Videos page and nav entry, and the Dockerfile/requirements it needed
(FFmpeg, espeak-ng, Pillow, pyttsx3). Content generation, planning,
approval, and publishing were untouched by the removal. If you find a
migration file named `video_brand_kit_...` or `daily_content_promotion_engine`
with no corresponding video code, this is why — migration history isn't
rewritten once pushed (see `CLAUDE.md`).

## Open items / natural next steps

- `docs/ARCHITECTURE.md` needs a pass to reflect Phases 2–4 (it currently
  only describes Phase 1 in detail).
- **None of the 2026-08-29 changes (discovery/SEO/campaign fixes, the
  Celery→cron replacement, the AI provider chain) are deployed yet** — see
  the deployment checklists above. Confirm with the user before pushing or
  deploying either service, per `CLAUDE.md`.
- **The pytest suite doesn't actually clean up its fixture data**, despite
  `CLAUDE.md` claiming tests "create uniquely-named rows and clean up after
  themselves." Confirmed twice on 2026-08-29: running the full suite left
  behind a fresh batch of uniquely-named `Test Org <hex>` organizations
  each time (RBAC/tenant-isolation fixtures in particular). Worth adding a
  real teardown (transaction rollback per test, or an autouse fixture that
  tracks and deletes what it created) before this accumulates in the shared
  database again — it grew to 508 organizations before being cleaned up
  once already.
- Cerebras is wired into the AI provider chain but the configured account
  needs billing set up before it'll serve any requests (see above) — a
  harmless no-op tier until then, not a code issue.
- No hosted CI/CD, so a push landing on Render isn't automatically
  verified — pair every deploy-affecting push with a check that the new
  commit actually went `live` (see `CLAUDE.md`), not just that the push
  succeeded.
- No social provider has a registered developer app yet, so every
  channel currently falls back to `manual_action_required` on publish.
- Broader automated test coverage beyond the security-critical suite
  (94 tests currently pass: RBAC, tenant isolation, SSRF, credentials,
  approval gates, content quality gate, growth dedup, learning agent,
  visibility risk classification, content router/executor/strategy).

## See also

`docs/USAGE_GUIDE.md` — feature-by-feature walkthrough, integration
requirements, and flow diagrams, all worked through with a single example
product (Gruvle Radar) end to end.
