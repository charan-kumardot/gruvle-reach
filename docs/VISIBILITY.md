# Visibility module

Lets a founder connect a website + its GitHub repo and have Gruvle Reach
scan it, find SEO/GEO/AI-visibility opportunities, and turn approved ones
into a branch + pull request — never touching `main`, never merging, never
deploying. Your existing GitHub → deploy pipeline (Render/Vercel/whatever
you already use) takes it from there once you merge.

## The loop

```
Connect website + GitHub repo
  -> Scan (real HTTP analysis, SSRF-safe, every fact tagged
     VERIFIED / ESTIMATED / UNKNOWN)
  -> SEO Agent + AI-Visibility Agent find issues -> become Opportunities
     (mirrored into the existing unified Opportunity feed / Daily Brief)
  -> Generate Proposal: AI drafts a minimal, targeted file change
  -> Risk Classifier (LOW/MEDIUM/HIGH/CRITICAL, deterministic)
  -> Product Truth Validator (blocks unsupported claims)
  -> Approve (LOW/MEDIUM only — HIGH/CRITICAL can never be auto-approved)
  -> Prepare: real branch + commit + PR created via the GitHub API
  -> You review and merge on GitHub
  -> Your existing deployment pipeline deploys
```

## Where things live

- `app/db/models/visibility.py` — `Website`, `WebsiteScan`, `SEOIssue`,
  `VisibilityQuestion`, `ProductTruth`, `DesignConstitution`,
  `ProtectedPath`, `WebsiteGuardrails`, `WebsiteOpportunity`, `WebsiteChange`
- `app/providers/git/` — `GitProvider` interface, `GitHubProvider` (real,
  PAT-based), `MockGitProvider`
- `app/providers/deployment/` — `DeploymentProvider` interface,
  `DisabledDeploymentProvider` (the honest default), a read-only
  `VercelProvider` stub for a founder's *own* target-site Vercel token
- `app/research/website_scanner.py` — the scanner (reuses the core app's
  SSRF-safe `safe_fetch`)
- `app/agents/risk_classifier.py`, `product_truth_validator.py`,
  `semantic_diff.py`, `seo_agent.py`, `ai_visibility_agent.py`,
  `website_optimization_agent.py` — the analysis/proposal pipeline
- `app/actions/git_executor.py` — the **only** module allowed to call
  `GitProvider.create_branch` / `commit_file_change` / `create_pull_request`,
  mirroring `app/actions/executor.py`'s email-send approval gate exactly
- `app/api/routers/visibility.py` — the API
- `apps/web/app/(app)/visibility/page.tsx` +
  `apps/web/components/app/visibility/*` — the UI (tab-based: Overview,
  SEO, GEO / AI Visibility, Opportunities, Website Changes, Settings)

## Safety model

- **`GitProvider` has no `merge()`, `delete()`, or `force_push()` method at
  all** — those actions are structurally unrepresentable, not just
  policy-disallowed.
- **CRITICAL-risk paths are hard-blocked** before an AI call is even made —
  `.env` files, secrets, auth, billing, CI config, Docker/deploy config, and
  anything matching a founder-defined Protected Path. No role or approval
  can override this.
- **HIGH-risk paths (hero, pricing, nav, layout, routing) can be proposed
  and validated for review, but can never be auto-approved into a
  branch/PR** — only LOW and MEDIUM risk changes can reach that stage
  (`app/agents/risk_classifier.py::is_auto_prepareable`).
- **The Product Truth Validator blocks unsupported claims** — verified in
  this build against a real mismatch (proposing content for the wrong
  product) and a real pass (an Open Graph tag addition that only restates
  existing approved facts).
- **A new file can be created** (e.g. a missing `robots.txt`) via the same
  path as an edit — GitHub's Contents API creates when `sha` is omitted,
  updates when it's provided; the safety checks (risk classification,
  Product Truth validation) apply identically either way.
- Scanned webpage content is always treated as **untrusted data** in every
  AI prompt that touches it — system prompts explicitly instruct the model
  to ignore anything in that content that looks like an instruction.

## What's real vs. an extension point

Real and verified end-to-end against the live `gruvle-reach` repo on
GitHub (see the PR created during development,
`github.com/charan-kumardot/gruvle-reach/pull/1`): GitHub PAT connect +
validation, repo listing, website scan, framework detection, SEO issue
detection + AI recommendations, opportunity generation into the existing
feed, GEO self-assessment, proposal generation (including new-file
creation), Product Truth validation (both block and pass cases), risk
classification (LOW/HIGH/CRITICAL all exercised), approve gating, and real
branch + PR creation.

Extension points, honestly not fully live: visual regression (interface +
a real Playwright implementation exists but is only ever invoked once a
`DeploymentProvider` supplies a preview URL, which needs a founder's own
target-site deployment credentials); local build/lint/test execution
(intentionally not implemented — see the "key scope decision" in the
project's plan history; CI status is read from GitHub's own Checks API on
the PR instead); Autonomous mode (`OptimizationMode.AUTONOMOUS` exists in
the enum but the API has no path that accepts it — disabled by design).
