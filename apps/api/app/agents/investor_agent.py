"""Investor Agent (§16) — matches investors in the directory to a product/stage/market."""
from app.agents.base import BaseAgent
from app.agents.scoring import score_investor_match
from app.db.models.investor import Investor
from app.db.models.product import Product


def _overlap_score(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 50.0
    a_lower = {x.lower() for x in a}
    b_lower = {x.lower() for x in b}
    if not a_lower or not b_lower:
        return 50.0
    overlap = len(a_lower & b_lower)
    return min(100.0, 40.0 + overlap * 30.0)


class InvestorAgent(BaseAgent):
    name = "investor_agent"
    allowed_tools = ["ai_provider"]
    allowed_actions = ["database_write"]

    def match(self, *, product: Product, stage: str, investor: Investor) -> dict:
        factors = {
            "sector_fit": _overlap_score(product.category.split() if product.category else [], investor.sector),
            "stage_fit": 90.0 if stage and stage.lower() in [s.lower() for s in investor.stage] else 45.0,
            "geography": _overlap_score(product.target_countries, investor.geography),
            "portfolio_relevance": _overlap_score(product.competitors, investor.portfolio),
            "recent_activity": 70.0 if investor.recent_investments else 40.0,
        }
        fit_score = score_investor_match(factors)

        reasons = []
        if factors["sector_fit"] > 60:
            reasons.append({"reason": f"Invests in sectors overlapping with {product.category}", "factor": "sector_fit"})
        if factors["stage_fit"] > 60:
            reasons.append({"reason": f"Matches {stage} stage focus", "factor": "stage_fit"})
        if factors["geography"] > 60:
            reasons.append({"reason": "Geographic focus overlaps with target markets", "factor": "geography"})
        if factors["portfolio_relevance"] > 60:
            reasons.append({"reason": "Portfolio includes relevant/adjacent companies", "factor": "portfolio_relevance"})
        if investor.recent_investments:
            reasons.append({"reason": "Has made investments recently — actively deploying capital", "factor": "recent_activity"})

        return {"fit_score": fit_score, "factors": factors, "reasons": reasons}
