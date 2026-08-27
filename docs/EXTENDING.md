# Adding an agent or research source

## Adding an agent

Agents live in `app/agents/` and subclass `BaseAgent`
(`app/agents/base.py`):

```python
class MyAgent(BaseAgent):
    name = "my_agent"
    allowed_tools = ["ai_provider"]       # document what it's allowed to touch
    allowed_actions = ["database_write"]  # never "send_email" / "publish_post"

    def run(self, ...):
        return self.call_ai_json(
            workspace_id=...,
            system_prompt="...",
            user_prompt="...",
            schema_hint="{...}",
            input_summary="...",
        )
```

`call_ai_json` logs every call to the `ai_runs` table (provider, model,
latency, token count, success/failure) and returns `None` on an unparseable
response — callers must handle that (see every router that calls an agent
for the pattern: return HTTP 503 with a clear message rather than crashing).

**The one rule that must never be broken:** an agent must never import or
call `EmailProvider`/`SocialProvider`. If a new agent needs to trigger an
external send, it should instead create a `Content`/`Outreach` draft row (or
an `Action` with `requires_approval=True`) for a human to approve through
the existing `app/actions/executor.py` path.

Wire the agent into a router (see `app/api/routers/*.py` for the pattern:
resolve tenant context via `require_workspace_role`, instantiate the agent
with `get_ai_provider()` and/or `get_search_provider()`, call it, commit).

## Adding a research source

Two levels:

1. **Ad-hoc / user-submitted**: `POST /workspaces/{id}/research/sources`
   already supports `source_type: user_submitted | rss | atom | sitemap |
   webpage | api | official_integration` — no code change needed, just data.
2. **A new source *type* the research engine should crawl differently**
   (e.g. a sitemap-walking crawler, or a platform-specific API client):
   add the fetch/parse logic under `app/research/`, following the pattern
   in `app/providers/search/rss_provider.py` (implements `SearchProvider`
   so it plugs into `ResearchAgent`/`BrandAgent` without their code
   changing), or add a standalone module if it doesn't fit the search
   abstraction (e.g. a sitemap walker feeding URLs into `safe_fetch`).

Always route actual HTTP fetches through `app/research/fetcher.py::safe_fetch`
— never call `httpx`/`requests` directly against a URL that came from
research data, a search result, or user input.

## Extending the Learning Engine

The schema already has what a learning engine needs: `ICPProfile.score`,
`Company.icp_fit_score`, `Outreach.status` outcomes, `OutreachEvent` (sent/
opened/replied), and `campaign_metrics` conversions. A natural next step is
a scheduled task (add to `app/workers/tasks.py` + `celery_app.py`'s beat
schedule) that groups outreach/companies by ICP or segment, computes
response-rate deltas, and writes a `Recommendation`-style row — store the
hypothesis, sample size, result, and confidence explicitly (per the
product's anti-overfitting principle) rather than silently re-ranking
things.
