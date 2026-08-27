"""
Deterministic scoring (§12, §34). Scoring is NOT delegated to the LLM — it's
plain arithmetic over evidence-derived factors, so it's reproducible,
explainable, and cheap (§79: "use deterministic logic before AI").
"""
from app.db.models.enums import CompanyFitCategory

COMPANY_SCORE_WEIGHTS = {
    "icp_match": 0.25,
    "industry": 0.10,
    "company_size": 0.10,
    "technology_fit": 0.15,
    "growth": 0.10,
    "funding": 0.10,
    "trigger": 0.10,
    "reachability": 0.10,
}


def score_company(factors: dict[str, float]) -> float:
    """factors: 0-100 values keyed by COMPANY_SCORE_WEIGHTS keys. Missing
    factors are treated as neutral (50) rather than zero, so an incomplete
    research pass doesn't unfairly tank a company's score."""
    total = 0.0
    for key, weight in COMPANY_SCORE_WEIGHTS.items():
        total += factors.get(key, 50.0) * weight
    return round(min(100.0, max(0.0, total)), 1)


def fit_category(score: float) -> CompanyFitCategory:
    if score >= 90:
        return CompanyFitCategory.EXCELLENT
    if score >= 75:
        return CompanyFitCategory.STRONG
    if score >= 60:
        return CompanyFitCategory.POTENTIAL
    return CompanyFitCategory.LOW_PRIORITY


OPPORTUNITY_SCORE_WEIGHTS = {
    "relevance": 0.25,
    "urgency": 0.20,
    "audience_quality": 0.15,
    "reachability": 0.15,
    "expected_value": 0.15,
    "evidence_quality": 0.10,
}


def score_opportunity(factors: dict[str, float]) -> float:
    total = 0.0
    for key, weight in OPPORTUNITY_SCORE_WEIGHTS.items():
        total += factors.get(key, 50.0) * weight
    # effort is a cost, not a benefit — high effort trims the final score slightly
    effort_penalty = factors.get("effort", 30.0) * 0.05
    return round(min(100.0, max(0.0, total - effort_penalty)), 1)


INVESTOR_MATCH_WEIGHTS = {
    "sector_fit": 0.30,
    "stage_fit": 0.25,
    "geography": 0.15,
    "portfolio_relevance": 0.15,
    "recent_activity": 0.15,
}


def score_investor_match(factors: dict[str, float]) -> float:
    total = 0.0
    for key, weight in INVESTOR_MATCH_WEIGHTS.items():
        total += factors.get(key, 50.0) * weight
    return round(min(100.0, max(0.0, total)), 1)
