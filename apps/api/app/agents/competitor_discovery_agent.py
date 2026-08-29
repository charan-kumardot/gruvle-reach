"""
Competitor Discovery Agent. Same shape as InvestorDiscoveryAgent/
MarketingDiscoveryAgent: search -> safe fetch -> strict anti-hallucination
AI extraction -> Competitor rows + evidence. Fills the gap where the only
way to track a competitor was typing its name and URL by hand.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.db.models.competitor import Competitor
from app.db.models.product import Product, ProductProfile
from app.providers.ai.base import AIProvider
from app.providers.search.base import SearchProvider
from app.research.evidence import record_evidence, recent_evidence_exists
from app.research.extractors import strip_html
from app.research.fetcher import SSRFBlockedError, safe_fetch

SCHEMA_HINT = """{
  "is_competitor_page": true,
  "company_name": "string or empty if unclear",
  "one_line_description": "string — what the product/company does, based only on the text",
  "confidence": "fact | hypothesis | inference | unknown"
}"""

SYSTEM_PROMPT = """You classify whether a webpage is a competing product or company's OWN
homepage/product page STRICTLY from the given text — not a "best of" listicle, review site,
news article, or directory page that merely mentions competitors. Never invent a company
name or description not supported by the text. If the page isn't itself a real product's
own site, set is_competitor_page to false. Use "fact" only for things explicitly stated,
"hypothesis" for plausible interpretation, "inference" for reasoning beyond the text,
"unknown" if you cannot tell."""


def _default_competitor_queries(product: Product, profile: ProductProfile | None) -> list[str]:
    category = (profile.product_category if profile else product.category) or "startup"
    queries = [
        f"{category} alternatives",
        f"{category} competitors",
        f"best {category} software",
        f"top {category} tools",
        f"{category} vs",
    ]
    for named in (profile.competitive_categories if profile else [])[:3]:
        queries.append(f"{named} software company")
    for named in (product.competitors or [])[:5]:
        queries.append(f"{named} official website")
    return queries


class CompetitorDiscoveryAgent(BaseAgent):
    name = "competitor_discovery_agent"
    allowed_tools = ["search_provider", "safe_fetcher", "ai_provider"]
    allowed_actions = ["database_write"]

    def __init__(self, db: Session, ai_provider: AIProvider, search_provider: SearchProvider):
        super().__init__(db, ai_provider)
        self.search = search_provider

    def discover_competitors(
        self,
        *,
        workspace_id: uuid.UUID,
        product: Product,
        profile: ProductProfile | None,
        queries: list[str] | None = None,
        max_results_per_query: int = 15,
    ) -> list[Competitor]:
        queries = queries or _default_competitor_queries(product, profile)
        discovered: list[Competitor] = []
        seen_urls: set[str] = set()

        existing_websites = {
            w for (w,) in self.db.execute(
                select(Competitor.website).where(Competitor.workspace_id == workspace_id)
            ).all()
            if w
        }

        for query in queries:
            for result in self.search.search(query, max_results=max_results_per_query):
                if not result.url or result.url in seen_urls or result.url in existing_websites:
                    continue
                seen_urls.add(result.url)

                if recent_evidence_exists(self.db, workspace_id=workspace_id, source_url=result.url):
                    continue

                try:
                    fetched = safe_fetch(result.url)
                except SSRFBlockedError:
                    continue
                except Exception:  # noqa: BLE001 — a single bad source shouldn't kill the whole run
                    continue

                page_text = strip_html(fetched.text) if "<html" in fetched.text[:200].lower() else fetched.text
                if len(page_text) < 50:
                    continue

                ai_output = self.call_ai_json(
                    workspace_id=workspace_id,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=f"Source URL: {result.url}\n\nPage text (truncated):\n{page_text[:4000]}",
                    schema_hint=SCHEMA_HINT,
                    input_summary=f"competitor extraction from {result.url}",
                )
                if not ai_output or not ai_output.get("is_competitor_page"):
                    continue

                company_name = ai_output.get("company_name") or result.title
                if not company_name:
                    continue

                by_name = self.db.execute(
                    select(Competitor).where(Competitor.workspace_id == workspace_id, Competitor.name == company_name)
                ).scalar_one_or_none()
                if by_name is not None:
                    continue

                competitor = Competitor(
                    workspace_id=workspace_id,
                    product_id=product.id,
                    name=company_name,
                    website=result.url,
                    notes=ai_output.get("one_line_description", ""),
                )
                self.db.add(competitor)
                self.db.flush()

                record_evidence(
                    self.db, workspace_id=workspace_id,
                    claim=f"{company_name}: {ai_output.get('one_line_description', 'candidate competitor')}",
                    source_url=result.url, evidence_snippet=result.snippet or page_text[:500],
                    source_type=result.source_type,
                    related_entity_type="competitor", related_entity_id=competitor.id,
                )

                discovered.append(competitor)

        self.db.flush()
        return discovered
