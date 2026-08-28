# Current status

Last updated 2026-08-28, at commit `0656892` (`main`, pushed, **and confirmed
live in production** — see the end-to-end verification below; it wasn't, for
about half an hour, until this same pass caught and fixed it).
This file is a snapshot — check `git log` for anything more recent than the
date above rather than trusting this in perpetuity.

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

**Separate, non-code finding: the self-hosted SearxNG's upstream search
engines are currently rate-limited/blocked.** Company discovery, investor
discovery, marketing-opportunity discovery, and brand-mention scanning all
returned empty lists rather than erroring — correct graceful-degradation
behavior, but root-caused to `gruvle-reach-searxng.onrender.com` itself
returning zero results even for a trivial query like `openai`, with
`unresponsive_engines` showing Brave and Google CSE suspended for "too many
requests" and Startpage suspended for CAPTCHA, DuckDuckGo timing out. This
is a search-engine-side anti-bot response to Render's IPs, not a bug in
this repo. See `CLAUDE.md` for how to spot this again.

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

## Known limitation: scheduled automation doesn't run in production yet

Render's free plan won't run the `type: worker` service `render.yaml`
declares (`gruvle-reach-worker`, running `celery ... --beat`) — Render's API
rejects it ("only web services allowed for plan"). This means **the entire
`beat_schedule` in `app/workers/celery_app.py` has never run automatically in
production**, across any phase of this project:

- `daily-founder-brief`, `competitor-scan`, `weekly-market-brief`
- `autonomous-customer-discovery`, `autonomous-investor-discovery`, `weekly-marketing-discovery`
- `daily-content-planning`, `content-quality-sweep`, `publish-due-content`, `weekly-content-learning`

Every one of these currently only runs if someone runs the Celery worker
themselves (locally, or via `docker compose up worker`), or via whatever
manual "run it now" trigger exists for that feature in the UI/API. This is a
pre-existing gap, not something the video removal touched — resolving it
needs either a paid Render worker plan or moving beat off Render's free tier.

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
- Scheduled automation doesn't run in production (see above) — the single
  biggest gap between "code exists" and "actually happens autonomously."
- SearxNG's upstream engines are currently blocked/rate-limited (see
  above) — every search-driven discovery feature is silently finding
  nothing. Worth a periodic spot-check (`GET /search?q=test&format=json`
  against the SearxNG service, check `unresponsive_engines`); may self-
  resolve, may need an engine config change or a different free search
  backend.
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
