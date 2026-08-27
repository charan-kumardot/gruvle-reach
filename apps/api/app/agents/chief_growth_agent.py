"""
Chief Growth Agent (§35, §68) — combines findings from the other agents
(top-scored companies, investor matches, opportunities, competitor/brand
signals) into the Daily Founder Brief: a ranked, evidence-backed set of
Action rows. Purely deterministic composition over data other agents/services
already produced — no LLM call needed here, keeping the daily brief fast,
free, and reproducible (§79).
"""
import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.action import Action
from app.db.models.brand import BrandMention
from app.db.models.company import Company
from app.db.models.competitor import CompetitorChange
from app.db.models.enums import ActionCategory, ActionStatus, CompanyFitCategory
from app.db.models.investor import Investor, InvestorMatch
from app.db.models.opportunity import Opportunity

MAX_DAILY_ACTIONS = 7


def _has_open_action(db: Session, *, workspace_id: uuid.UUID, related_entity_type: str, related_entity_id: uuid.UUID) -> bool:
    existing = db.execute(
        select(Action.id).where(
            Action.workspace_id == workspace_id,
            Action.related_entity_type == related_entity_type,
            Action.related_entity_id == related_entity_id,
            Action.status.in_([ActionStatus.TODAY, ActionStatus.UPCOMING, ActionStatus.WAITING]),
        )
    ).scalar_one_or_none()
    return existing is not None


def generate_daily_actions(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[Action]:
    """Surfaces new candidate actions from the workspace's current data. Safe
    to call repeatedly — it skips entities that already have an open action."""
    created: list[Action] = []

    top_companies = db.execute(
        select(Company)
        .where(
            Company.workspace_id == workspace_id,
            Company.product_id == product_id,
            Company.icp_fit_category.in_([CompanyFitCategory.EXCELLENT, CompanyFitCategory.STRONG]),
        )
        .order_by(Company.icp_fit_score.desc())
        .limit(5)
    ).scalars().all()

    for company in top_companies:
        if _has_open_action(db, workspace_id=workspace_id, related_entity_type="company", related_entity_id=company.id):
            continue
        action = Action(
            workspace_id=workspace_id,
            product_id=product_id,
            title=f"Contact {company.name}",
            description=f"{company.name} scored {company.icp_fit_score}/100 fit — {company.potential_pain or 'strong ICP match'}.",
            category=ActionCategory.CUSTOMER,
            why=company.potential_pain or "Strong ICP match based on discovered evidence.",
            impact="high" if company.icp_fit_score >= 90 else "medium",
            effort="low",
            evidence_ids=company.evidence_ids,
            expected_value_score=company.icp_fit_score,
            status=ActionStatus.TODAY,
            requires_approval=True,
            related_entity_type="company",
            related_entity_id=company.id,
        )
        db.add(action)
        created.append(action)

    top_matches = db.execute(
        select(InvestorMatch, Investor)
        .join(Investor, Investor.id == InvestorMatch.investor_id)
        .where(InvestorMatch.workspace_id == workspace_id, InvestorMatch.product_id == product_id, InvestorMatch.fit_score >= 80)
        .order_by(InvestorMatch.fit_score.desc())
        .limit(3)
    ).all()

    for match, investor in top_matches:
        if _has_open_action(db, workspace_id=workspace_id, related_entity_type="investor_match", related_entity_id=match.id):
            continue
        reasons_text = "; ".join(r.get("reason", "") for r in (match.reasons or [])[:3])
        action = Action(
            workspace_id=workspace_id,
            product_id=product_id,
            title=f"Reach out to {investor.fund_name or investor.investor_name}",
            description=reasons_text or "High investor fit score.",
            category=ActionCategory.INVESTOR,
            why=reasons_text or "High computed fit score across sector/stage/geography.",
            impact="high" if match.fit_score >= 90 else "medium",
            effort="medium",
            expected_value_score=match.fit_score,
            status=ActionStatus.TODAY,
            requires_approval=True,
            related_entity_type="investor_match",
            related_entity_id=match.id,
        )
        db.add(action)
        created.append(action)

    top_opportunities = db.execute(
        select(Opportunity)
        .where(Opportunity.workspace_id == workspace_id, Opportunity.product_id == product_id, Opportunity.status == "open")
        .order_by(Opportunity.created_at.desc())
        .limit(3)
    ).scalars().all()

    for opp in top_opportunities:
        if _has_open_action(db, workspace_id=workspace_id, related_entity_type="opportunity", related_entity_id=opp.id):
            continue
        action = Action(
            workspace_id=workspace_id,
            product_id=product_id,
            title=opp.title,
            description=opp.description,
            category=ActionCategory.MARKETING if opp.type.value in ("marketing", "launch", "community", "event", "media") else ActionCategory.CONTENT,
            why=opp.description,
            impact="medium",
            effort="low",
            status=ActionStatus.UPCOMING,
            requires_approval=True,
            related_entity_type="opportunity",
            related_entity_id=opp.id,
            deadline=opp.deadline,
        )
        db.add(action)
        created.append(action)

    recent_changes = db.execute(
        select(CompetitorChange)
        .where(CompetitorChange.potential_impact.in_(["medium", "high"]))
        .order_by(CompetitorChange.detected_at.desc())
        .limit(2)
    ).scalars().all()

    for change in recent_changes:
        if _has_open_action(db, workspace_id=workspace_id, related_entity_type="competitor_change", related_entity_id=change.id):
            continue
        action = Action(
            workspace_id=workspace_id,
            product_id=product_id,
            title="Review competitor change",
            description=change.description,
            category=ActionCategory.COMPETITOR,
            why=change.recommended_response,
            impact=change.potential_impact,
            effort="low",
            status=ActionStatus.UPCOMING,
            requires_approval=False,
            related_entity_type="competitor_change",
            related_entity_id=change.id,
        )
        db.add(action)
        created.append(action)

    db.flush()
    return created


def get_daily_brief(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[Action]:
    generate_daily_actions(db, workspace_id=workspace_id, product_id=product_id)
    actions = db.execute(
        select(Action)
        .where(
            Action.workspace_id == workspace_id,
            Action.product_id == product_id,
            Action.status.in_([ActionStatus.TODAY, ActionStatus.UPCOMING]),
        )
        .order_by(Action.expected_value_score.desc())
        .limit(MAX_DAILY_ACTIONS)
    ).scalars().all()
    return actions
