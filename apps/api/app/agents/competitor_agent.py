"""Competitor Agent (§31) — periodically fetches a competitor's public pages and
flags meaningful changes via content hashing + AI summarization of the diff."""
import datetime as dt

from app.agents.base import BaseAgent
from app.db.models.competitor import Competitor, CompetitorChange
from app.research.evidence import content_hash
from app.research.extractors import strip_html
from app.research.fetcher import SSRFBlockedError, safe_fetch

SCHEMA_HINT = """{
  "change_type": "pricing | feature | launch | funding | hiring | content | press",
  "description": "string — what changed, in plain language",
  "potential_impact": "low | medium | high",
  "recommended_response": "string"
}"""

SYSTEM_PROMPT = """You compare two snapshots of a competitor's public webpage text (OLD and NEW)
and describe what meaningfully changed, if anything. Base your answer only on the text
provided. If the change looks cosmetic/irrelevant, set potential_impact to "low"."""


class CompetitorAgent(BaseAgent):
    name = "competitor_agent"
    allowed_tools = ["safe_fetcher", "ai_provider"]
    allowed_actions = ["database_write"]

    def scan(self, competitor: Competitor, previous_text: str = "") -> CompetitorChange | None:
        if not competitor.website:
            return None
        try:
            fetched = safe_fetch(competitor.website)
        except SSRFBlockedError:
            return None
        except Exception:  # noqa: BLE001
            return None

        text = strip_html(fetched.text)
        new_hash = content_hash(text)

        if new_hash == competitor.last_content_hash:
            competitor.last_scanned_at = dt.datetime.now(dt.timezone.utc)
            return None  # no change — don't waste an AI call

        ai_output = None
        if previous_text:
            ai_output = self.call_ai_json(
                workspace_id=competitor.workspace_id,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=f"OLD:\n{previous_text[:3000]}\n\nNEW:\n{text[:3000]}",
                schema_hint=SCHEMA_HINT,
                input_summary=f"competitor diff for {competitor.name}",
            )

        change = CompetitorChange(
            competitor_id=competitor.id,
            change_type=(ai_output or {}).get("change_type", "content"),
            description=(ai_output or {}).get("description", "Page content changed since last scan."),
            detected_at=dt.datetime.now(dt.timezone.utc),
            source_url=competitor.website,
            potential_impact=(ai_output or {}).get("potential_impact", "medium"),
            evidence_snippet=text[:500],
            recommended_response=(ai_output or {}).get("recommended_response", "Review the change and assess differentiation impact."),
            content_hash=new_hash,
        )
        self.db.add(change)

        competitor.last_content_hash = new_hash
        competitor.last_scanned_at = dt.datetime.now(dt.timezone.utc)
        self.db.flush()
        return change
