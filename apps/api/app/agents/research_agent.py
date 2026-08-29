"""
Research Agent (§10-11). Discovers candidate target companies for a product
by: searching (SearchProvider) -> fetching each result safely (SSRF-safe
fetcher) -> extracting deterministic signals -> asking the LLM to summarize
ONLY what's supported by the fetched text (explicit anti-hallucination
instructions, §45) -> persisting Company + Evidence + CompanySignal rows.

Allowed tools: search provider, safe fetcher, AI provider, database write.
Never sends/publishes anything.
"""
import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.scoring import fit_category, score_company
from app.db.models.company import Company, CompanySignal
from app.db.models.enums import EvidenceStatus
from app.providers.ai.base import AIProvider
from app.providers.search.base import SearchProvider
from app.research.evidence import record_evidence, recent_evidence_exists
from app.research.extractors import extract_signals, strip_html
from app.research.fetcher import SSRFBlockedError, safe_fetch

SCHEMA_HINT = """{
  "is_company_page": true,
  "company_name": "string or empty if unclear",
  "industry": "string, based only on the text",
  "country": "string, based only on the text, empty if unclear",
  "employee_estimate": "string range like '20-200', empty if unclear",
  "funding_stage": "string, empty if unclear",
  "potential_pain": "string — plausible pain this product could address, marked as inference",
  "confidence": "fact | hypothesis | inference | unknown"
}"""

SYSTEM_PROMPT = """You extract structured company information STRICTLY from the provided page
text. Never invent facts not present in the text. If information isn't in the text,
leave the field empty and set confidence appropriately. Use "fact" only for things
explicitly stated (e.g. an exact employee count stated in the text), "hypothesis" for
plausible interpretation, "inference" for your own reasoning beyond the text, and
"unknown" if you cannot tell."""


class ResearchAgent(BaseAgent):
    name = "research_agent"
    allowed_tools = ["search_provider", "safe_fetcher", "ai_provider"]
    allowed_actions = ["database_write"]

    def __init__(self, db: Session, ai_provider: AIProvider, search_provider: SearchProvider):
        super().__init__(db, ai_provider)
        self.search = search_provider

    def discover_companies(
        self,
        *,
        workspace_id: uuid.UUID,
        product_id: uuid.UUID,
        queries: list[str],
        max_results_per_query: int = 15,
    ) -> list[Company]:
        discovered: list[Company] = []
        seen_websites: set[str] = set()

        for query in queries:
            results = self.search.search(query, max_results=max_results_per_query)
            for result in results:
                if not result.url or result.url in seen_websites:
                    continue
                seen_websites.add(result.url)

                # Research memory (§23) — don't re-research a URL this
                # workspace already has recent evidence for.
                if recent_evidence_exists(self.db, workspace_id=workspace_id, source_url=result.url):
                    continue

                try:
                    fetched = safe_fetch(result.url)
                except SSRFBlockedError:
                    continue
                except Exception:  # noqa: BLE001 — a single bad source shouldn't kill the whole run
                    continue

                page_text = strip_html(fetched.text) if "html" in fetched.content_type or "<html" in fetched.text[:200].lower() else fetched.text
                if len(page_text) < 50:
                    continue

                signals = extract_signals(page_text)

                ai_output = self.call_ai_json(
                    workspace_id=workspace_id,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=f"Source URL: {result.url}\n\nPage text (truncated):\n{page_text[:4000]}",
                    schema_hint=SCHEMA_HINT,
                    input_summary=f"company extraction from {result.url}",
                )
                if not ai_output or not ai_output.get("is_company_page"):
                    continue

                company_name = ai_output.get("company_name") or result.title or result.url
                confidence_str = ai_output.get("confidence", "hypothesis")
                try:
                    confidence_status = EvidenceStatus(confidence_str)
                except ValueError:
                    confidence_status = EvidenceStatus.HYPOTHESIS

                company = Company(
                    workspace_id=workspace_id,
                    product_id=product_id,
                    name=company_name,
                    website=result.url,
                    industry=ai_output.get("industry", ""),
                    country=ai_output.get("country", ""),
                    employee_estimate=ai_output.get("employee_estimate", ""),
                    funding_stage=ai_output.get("funding_stage", ""),
                    potential_pain=ai_output.get("potential_pain", ""),
                    technology_signals=[s.description for s in signals if s.signal_type == "technology_adoption"],
                    growth_signals=[s.description for s in signals if s.signal_type in ("hiring", "product_launch")],
                    source_urls=[result.url],
                    confidence=confidence_status,
                )
                self.db.add(company)
                self.db.flush()

                evidence = record_evidence(
                    self.db,
                    workspace_id=workspace_id,
                    claim=f"{company_name}: {ai_output.get('potential_pain', 'candidate target company')}",
                    source_url=result.url,
                    evidence_snippet=result.snippet or page_text[:500],
                    source_type=result.source_type,
                    confidence=0.7 if confidence_status == EvidenceStatus.FACT else 0.5,
                    status=confidence_status,
                    related_entity_type="company",
                    related_entity_id=company.id,
                )
                company.evidence_ids = [str(evidence.id)]

                for sig in signals:
                    self.db.add(
                        CompanySignal(
                            company_id=company.id,
                            signal_type=sig.signal_type,
                            description=sig.description,
                            source_url=result.url,
                            confidence=sig.confidence,
                            detected_at=dt.datetime.now(dt.timezone.utc),
                        )
                    )

                factors = {
                    "icp_match": 60.0,
                    "technology_fit": 70.0 if company.technology_signals else 40.0,
                    "growth": 70.0 if company.growth_signals else 40.0,
                    "funding": 65.0 if company.funding_stage else 40.0,
                }
                company.icp_fit_score = score_company(factors)
                company.icp_fit_category = fit_category(company.icp_fit_score)
                company.icp_fit_factors = factors

                discovered.append(company)
                # Commit per-company rather than once at the end of the whole
                # run — a full discovery pass can take several minutes (many
                # queries x many candidates), and founders watching the UI
                # saw nothing appear until it finished, with no results at
                # all if the process was killed partway through.
                self.db.commit()

        self.db.flush()
        return discovered
