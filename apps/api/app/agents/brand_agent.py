"""Brand Agent (§32) — finds public mentions of tracked keywords via the search provider
and categorizes relevance. Never auto-posts a response (§32: 'Do not automatically post')."""
import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.db.models.brand import BrandMention
from app.db.models.enums import MentionCategory
from app.providers.ai.base import AIProvider
from app.providers.search.base import SearchProvider

SCHEMA_HINT = """{
  "category": "positive | neutral | negative | question | purchase_intent | competitor_comparison | feedback",
  "relevance_score": 0,
  "recommended_action": "string"
}"""

SYSTEM_PROMPT = """Classify a public mention of a brand/product keyword. Base the classification
only on the excerpt given. relevance_score is 0-100: how worth a founder's attention is
this mention? recommended_action should be a specific, low-risk suggested response
(e.g. "Reply with an educational answer" or "No action needed") — never suggest
anything that reads as automated spam."""


class BrandAgent(BaseAgent):
    name = "brand_agent"
    allowed_tools = ["search_provider", "ai_provider"]
    allowed_actions = ["database_write"]

    def __init__(self, db: Session, ai_provider: AIProvider, search_provider: SearchProvider):
        super().__init__(db, ai_provider)
        self.search = search_provider

    def scan_mentions(self, *, workspace_id: uuid.UUID, product_id: uuid.UUID, keywords: list[str]) -> list[BrandMention]:
        mentions: list[BrandMention] = []
        for keyword in keywords:
            for result in self.search.search(keyword, max_results=5):
                ai_output = self.call_ai_json(
                    workspace_id=workspace_id,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=f"Keyword: {keyword}\nExcerpt: {result.snippet}\nSource: {result.url}",
                    schema_hint=SCHEMA_HINT,
                    input_summary=f"brand mention scan: {keyword}",
                )
                if not ai_output:
                    continue
                try:
                    category = MentionCategory(ai_output.get("category", "neutral"))
                except ValueError:
                    category = MentionCategory.NEUTRAL

                mention = BrandMention(
                    workspace_id=workspace_id,
                    product_id=product_id,
                    keyword=keyword,
                    source_url=result.url,
                    source_type=result.source_type,
                    excerpt=result.snippet,
                    category=category,
                    relevance_score=float(ai_output.get("relevance_score", 0)),
                    recommended_action=ai_output.get("recommended_action", ""),
                    detected_at=dt.datetime.now(dt.timezone.utc),
                )
                self.db.add(mention)
                mentions.append(mention)
        self.db.flush()
        return mentions
