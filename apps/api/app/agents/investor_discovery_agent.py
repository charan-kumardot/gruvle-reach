"""
Investor Discovery Agent (§12-15). Mirrors ResearchAgent's shape exactly:
search -> safe fetch -> strict anti-hallucination AI extraction -> evidence.
Investor is a global reference directory (shared across workspaces, same
design as the original build), so dedup is by website/name globally, not
per-workspace.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.db.models.enums import EvidenceStatus
from app.db.models.investor import Investor
from app.db.models.product import Product, ProductProfile
from app.providers.ai.base import AIProvider
from app.providers.search.base import SearchProvider
from app.research.evidence import record_evidence, recent_evidence_exists
from app.research.extractors import strip_html
from app.research.fetcher import SSRFBlockedError, safe_fetch

SCHEMA_HINT = """{
  "is_investor_page": true,
  "fund_name": "string or empty if unclear",
  "investor_type": "vc | angel | accelerator | corporate_vc | government | grant | empty if unclear",
  "stage": ["string"],
  "geography": ["string"],
  "sector": ["string"],
  "thesis": "string — based only on the text, empty if unclear",
  "portfolio": ["string — company names mentioned, empty list if none"],
  "confidence": "fact | hypothesis | inference | unknown"
}"""

SYSTEM_PROMPT = """You extract structured investor/fund information STRICTLY from the provided
page text. Never invent a fund name, sector, stage, or portfolio company not present in
the text. If the page is not about an investor or fund, set is_investor_page to false.
Use "fact" only for things explicitly stated, "hypothesis" for plausible interpretation,
"inference" for reasoning beyond the text, "unknown" if you cannot tell."""


def _default_investor_queries(product: Product, profile: ProductProfile | None) -> list[str]:
    # Biased toward phrasing that surfaces a fund's own site (portfolio/thesis
    # pages) rather than news articles ABOUT a funding round — the latter
    # dominate generic "investors in X" searches and are never themselves
    # investor pages, so the AI correctly (and should) reject them.
    category = (profile.product_category if profile else product.category) or "startup"
    queries = [
        f'venture capital fund "we invest in" {category}',
        f"seed stage venture capital firm portfolio {category}",
    ]
    if product.stage:
        queries.append(f"{product.stage} stage venture capital firm thesis {category}")
    return queries


class InvestorDiscoveryAgent(BaseAgent):
    name = "investor_discovery_agent"
    allowed_tools = ["search_provider", "safe_fetcher", "ai_provider"]
    allowed_actions = ["database_write"]

    def __init__(self, db: Session, ai_provider: AIProvider, search_provider: SearchProvider):
        super().__init__(db, ai_provider)
        self.search = search_provider

    def discover_investors(
        self,
        *,
        workspace_id: uuid.UUID,
        product: Product,
        profile: ProductProfile | None,
        queries: list[str] | None = None,
        max_results_per_query: int = 5,
    ) -> list[Investor]:
        queries = queries or _default_investor_queries(product, profile)
        discovered: list[Investor] = []
        seen_urls: set[str] = set()

        for query in queries:
            for result in self.search.search(query, max_results=max_results_per_query):
                if not result.url or result.url in seen_urls:
                    continue
                seen_urls.add(result.url)

                if recent_evidence_exists(self.db, workspace_id=workspace_id, source_url=result.url):
                    continue

                already_known = self.db.execute(
                    select(Investor).where(Investor.source_url == result.url)
                ).scalar_one_or_none()
                if already_known is not None:
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
                    input_summary=f"investor extraction from {result.url}",
                )
                if not ai_output or not ai_output.get("is_investor_page"):
                    continue

                fund_name = ai_output.get("fund_name") or result.title
                if not fund_name:
                    continue

                # Dedup by name too — different URLs (e.g. a directory listing
                # vs. the fund's own site) can describe the same fund.
                by_name = self.db.execute(select(Investor).where(Investor.fund_name == fund_name)).scalar_one_or_none()
                if by_name is not None:
                    continue

                confidence_map = {"fact": 0.85, "hypothesis": 0.6, "inference": 0.4, "unknown": 0.2}
                confidence_label = ai_output.get("confidence", "hypothesis")
                confidence = confidence_map.get(confidence_label, 0.5)
                try:
                    evidence_status = EvidenceStatus(confidence_label)
                except ValueError:
                    evidence_status = EvidenceStatus.HYPOTHESIS

                investor = Investor(
                    fund_name=fund_name,
                    investor_type=ai_output.get("investor_type", ""),
                    website=result.url,
                    stage=ai_output.get("stage", []),
                    geography=ai_output.get("geography", []),
                    sector=ai_output.get("sector", []),
                    thesis=ai_output.get("thesis", ""),
                    portfolio=ai_output.get("portfolio", []),
                    source_url=result.url,
                    confidence=confidence,
                )
                self.db.add(investor)
                self.db.flush()

                record_evidence(
                    self.db, workspace_id=workspace_id,
                    claim=f"{fund_name}: {ai_output.get('thesis', 'candidate investor')}",
                    source_url=result.url, evidence_snippet=result.snippet or page_text[:500],
                    source_type=result.source_type, confidence=confidence,
                    status=evidence_status,
                    related_entity_type="investor", related_entity_id=investor.id,
                )

                discovered.append(investor)

        self.db.flush()
        return discovered
