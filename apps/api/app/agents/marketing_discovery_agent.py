"""
Marketing Discovery Agent (§25). Same shape as ResearchAgent/
InvestorDiscoveryAgent: search -> safe fetch -> strict AI classification ->
Opportunity rows in the existing unified feed (§16-18) — no new opportunity
storage mechanism, just a new source that fills it.
"""
import uuid

from app.agents.base import BaseAgent
from app.db.models.enums import OpportunityType
from app.db.models.opportunity import Opportunity
from app.db.models.product import Product, ProductProfile
from app.providers.ai.base import AIProvider
from app.providers.search.base import SearchProvider
from app.research.evidence import record_evidence, recent_evidence_exists
from app.research.extractors import strip_html
from app.research.fetcher import SSRFBlockedError, safe_fetch

SCHEMA_HINT = """{
  "is_marketing_opportunity": true,
  "opportunity_type": "community | newsletter | podcast | media | event | launch | accelerator | grant | other",
  "name": "string — name of the community/newsletter/podcast/platform, empty if unclear",
  "audience": "string — who reads/listens/participates, based only on the text",
  "submission_method": "string — how to submit/participate if stated, empty if unclear",
  "confidence": "fact | hypothesis | inference | unknown"
}"""

SYSTEM_PROMPT = """You classify whether a webpage describes a real marketing opportunity for a
product (a community, newsletter, podcast, media outlet, event, launch platform,
accelerator, or grant) STRICTLY from the given text. Never invent an audience size or
submission process not stated in the text. If the page isn't a genuine opportunity like
this, set is_marketing_opportunity to false."""

_TYPE_MAP = {
    "community": OpportunityType.COMMUNITY, "newsletter": OpportunityType.NEWSLETTER,
    "podcast": OpportunityType.PODCAST, "media": OpportunityType.MEDIA, "event": OpportunityType.EVENT,
    "launch": OpportunityType.LAUNCH, "accelerator": OpportunityType.ACCELERATOR, "grant": OpportunityType.GRANT,
}


def _default_marketing_queries(product: Product, profile: ProductProfile | None) -> list[str]:
    category = (profile.product_category if profile else product.category) or "startup"
    return [
        f"{category} newsletter submit",
        f"{category} community founders",
        f"best podcasts about {category}",
        f"startup launch platforms directories",
    ]


CONTENT_TREND_SCHEMA_HINT = """{
  "is_content_opportunity": true,
  "opportunity_kind": "trend | reactive_competitive | industry_news",
  "title": "string — short, specific headline for the content angle",
  "summary": "string — why this is relevant to the product, based only on the text",
  "confidence": "fact | hypothesis | inference | unknown"
}"""

CONTENT_TREND_SYSTEM_PROMPT = """You classify whether a webpage describes something worth creating
marketing content about for a specific product: an industry trend, a competitor
announcement/change, or genuine industry news relevant to the product's category.
Judge relevance STRICTLY from the given text and the product's category/problem — do not
assume relevance that isn't supported by the text. If a competitor's product or company
name appears together with a real change (launch, pricing, feature, funding), classify it
as reactive_competitive. If the page is not genuinely relevant content-opportunity
material, set is_content_opportunity to false."""


def _default_content_trend_queries(product: Product, profile: ProductProfile | None) -> list[str]:
    category = (profile.product_category if profile else product.category) or "startup"
    queries = [f"{category} industry trends", f"{category} news"]
    for competitor in (product.competitors or [])[:2]:
        queries.append(f"{competitor} announcement OR launch OR pricing update")
    return queries


class MarketingDiscoveryAgent(BaseAgent):
    name = "marketing_discovery_agent"
    allowed_tools = ["search_provider", "safe_fetcher", "ai_provider"]
    allowed_actions = ["database_write"]

    def __init__(self, db, ai_provider: AIProvider, search_provider: SearchProvider):
        super().__init__(db, ai_provider)
        self.search = search_provider

    def discover_opportunities(
        self,
        *,
        workspace_id: uuid.UUID,
        product: Product,
        profile: ProductProfile | None,
        queries: list[str] | None = None,
        max_results_per_query: int = 5,
    ) -> list[Opportunity]:
        queries = queries or _default_marketing_queries(product, profile)
        discovered: list[Opportunity] = []
        seen_urls: set[str] = set()

        for query in queries:
            for result in self.search.search(query, max_results=max_results_per_query):
                if not result.url or result.url in seen_urls:
                    continue
                seen_urls.add(result.url)

                if recent_evidence_exists(self.db, workspace_id=workspace_id, source_url=result.url):
                    continue

                try:
                    fetched = safe_fetch(result.url)
                except SSRFBlockedError:
                    continue
                except Exception:  # noqa: BLE001
                    continue

                page_text = strip_html(fetched.text) if "<html" in fetched.text[:200].lower() else fetched.text
                if len(page_text) < 50:
                    continue

                ai_output = self.call_ai_json(
                    workspace_id=workspace_id,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=f"Source URL: {result.url}\n\nPage text (truncated):\n{page_text[:4000]}",
                    schema_hint=SCHEMA_HINT,
                    input_summary=f"marketing opportunity classification for {result.url}",
                )
                if not ai_output or not ai_output.get("is_marketing_opportunity"):
                    continue

                name = ai_output.get("name") or result.title or result.url
                opp_type = _TYPE_MAP.get(ai_output.get("opportunity_type", ""), OpportunityType.MARKETING)

                opportunity = Opportunity(
                    workspace_id=workspace_id, product_id=product.id, type=opp_type,
                    title=name, description=ai_output.get("audience", ""),
                    audience=ai_output.get("audience", ""),
                    submission_method=ai_output.get("submission_method", ""),
                    status="open",
                )
                self.db.add(opportunity)
                self.db.flush()

                record_evidence(
                    self.db, workspace_id=workspace_id,
                    claim=f"{name}: {ai_output.get('audience', 'marketing opportunity')}",
                    source_url=result.url, evidence_snippet=result.snippet or page_text[:500],
                    source_type=result.source_type,
                    related_entity_type="opportunity", related_entity_id=opportunity.id,
                )

                discovered.append(opportunity)

        self.db.flush()
        return discovered

    def discover_content_opportunities(
        self,
        *,
        workspace_id: uuid.UUID,
        product: Product,
        profile: ProductProfile | None,
        queries: list[str] | None = None,
        max_results_per_query: int = 5,
    ) -> list[Opportunity]:
        """§2, §6-7 — the spec's MarketingIntelligenceAgent: discovers trend
        and reactive-competitive content opportunities, feeding
        content_strategy_agent.plan_daily_content. Same search -> fetch ->
        AI-classify -> Evidence pipeline as discover_opportunities above."""
        queries = queries or _default_content_trend_queries(product, profile)
        discovered: list[Opportunity] = []
        seen_urls: set[str] = set()

        for query in queries:
            for result in self.search.search(query, max_results=max_results_per_query):
                if not result.url or result.url in seen_urls:
                    continue
                seen_urls.add(result.url)

                if recent_evidence_exists(self.db, workspace_id=workspace_id, source_url=result.url):
                    continue

                try:
                    fetched = safe_fetch(result.url)
                except SSRFBlockedError:
                    continue
                except Exception:  # noqa: BLE001
                    continue

                page_text = strip_html(fetched.text) if "<html" in fetched.text[:200].lower() else fetched.text
                if len(page_text) < 50:
                    continue

                ai_output = self.call_ai_json(
                    workspace_id=workspace_id,
                    system_prompt=CONTENT_TREND_SYSTEM_PROMPT,
                    user_prompt=(
                        f"Product category: {product.category}\nProduct competitors: {product.competitors}\n\n"
                        f"Source URL: {result.url}\n\nPage text (truncated):\n{page_text[:4000]}"
                    ),
                    schema_hint=CONTENT_TREND_SCHEMA_HINT,
                    input_summary=f"content opportunity classification for {result.url}",
                )
                if not ai_output or not ai_output.get("is_content_opportunity"):
                    continue

                kind = ai_output.get("opportunity_kind", "trend")
                title = ai_output.get("title") or result.title or result.url
                opp_type = OpportunityType.SOCIAL if kind == "reactive_competitive" else OpportunityType.CONTENT

                opportunity = Opportunity(
                    workspace_id=workspace_id, product_id=product.id, type=opp_type,
                    title=title, description=ai_output.get("summary", ""),
                    # Tagged so content_strategy_agent excludes it from the
                    # fully-autonomous nightly plan — reactive competitive
                    # content only ever lands via a manual trigger,
                    # APPROVAL_REQUIRED, never auto-scheduled (§5, §7).
                    related_entity_type="competitor_change" if kind == "reactive_competitive" else "content_trend",
                    status="open",
                )
                self.db.add(opportunity)
                self.db.flush()

                record_evidence(
                    self.db, workspace_id=workspace_id,
                    claim=f"{title}: {ai_output.get('summary', 'content opportunity')}",
                    source_url=result.url, evidence_snippet=result.snippet or page_text[:500],
                    source_type=result.source_type,
                    related_entity_type="opportunity", related_entity_id=opportunity.id,
                )

                discovered.append(opportunity)

        self.db.flush()
        return discovered
