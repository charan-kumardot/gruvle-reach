"""
Content Strategy Agent (§2-3, §41). Deterministic composition (mirrors
chief_growth_agent.py's shape) over signals other agents already produced —
open Opportunity rows and accepted LearningInsight rows — falling back to
BrandBrain.key_messages if neither exists yet. One AI call happens per
chosen idea (in content_agent.py), not for the whole plan.

This file is also the spec's "CampaignAgent" (§25-26) —
plan_campaign_content is a bounded, guardrailed invocation of the same
composer, not separate decision logic.
"""
import datetime as dt
import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.cta_rules import cta_for_content_type
from app.db.models.campaign import Campaign
from app.db.models.content import Content
from app.db.models.enums import LearningInsightStatus, OpportunityType
from app.db.models.growth import LearningInsight
from app.db.models.opportunity import Opportunity
from app.db.models.product import BrandBrain

MAX_DAILY_CONTENT_ITEMS = 3
# Core social channels for autonomous daily generation — blog/newsletter
# stay manual-trigger-only (heavier formats, not a daily cadence), keeping
# total autonomous daily output bounded (§2 "do not blindly create maximum content").
AUTONOMOUS_CHANNELS = ["linkedin", "x", "instagram"]

# §3 content mix — target count per content_type over a rolling 7-day
# window. The planner picks under-quota types first so the mix
# self-corrects toward balance instead of generating whatever's easiest.
CONTENT_MIX_WEEKLY_TARGET: dict[str, int] = {
    "educational": 2,
    "product": 1,
    "authority": 1,
    "social_proof": 1,
    "engagement": 1,
    "promotional": 1,
}

_MIX_WINDOW_DAYS = 7
_OPPORTUNITY_TYPES_FOR_CONTENT = (OpportunityType.CONTENT, OpportunityType.MARKETING, OpportunityType.SOCIAL, OpportunityType.LAUNCH)

# §25 launch-campaign asset angles, cycled to produce `count` campaign ideas.
_CAMPAIGN_ASSET_ANGLES: list[tuple[str, str]] = [
    ("announcement", "promotional"),
    ("teaser", "engagement"),
    ("feature highlight", "product"),
    ("FAQ", "educational"),
    ("follow-up / results so far", "social_proof"),
]


def _under_quota_types(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[str]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=_MIX_WINDOW_DAYS)
    recent = db.execute(
        select(Content.content_type).where(
            Content.workspace_id == workspace_id, Content.product_id == product_id, Content.created_at >= cutoff
        )
    ).scalars().all()
    counts = Counter(recent)
    under_quota = [
        content_type
        for content_type, target in CONTENT_MIX_WEEKLY_TARGET.items()
        if counts.get(content_type, 0) < target
    ]
    # Deterministic order: most-under-quota first.
    under_quota.sort(key=lambda t: counts.get(t, 0) - CONTENT_MIX_WEEKLY_TARGET[t])
    return under_quota or list(CONTENT_MIX_WEEKLY_TARGET.keys())


def _reactive_opportunity_ids(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> set[uuid.UUID]:
    """§5/§7 — reactive competitive-response opportunities are excluded from
    the fully-autonomous plan entirely; they only ever get generated
    on-demand and land APPROVAL_REQUIRED with no auto-schedule."""
    rows = db.execute(
        select(Opportunity.id).where(
            Opportunity.workspace_id == workspace_id,
            Opportunity.product_id == product_id,
            Opportunity.related_entity_type == "competitor_change",
        )
    ).scalars().all()
    return set(rows)


def _opportunity_ideas(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[dict]:
    excluded = _reactive_opportunity_ids(db, workspace_id=workspace_id, product_id=product_id)
    rows = db.execute(
        select(Opportunity)
        .where(
            Opportunity.workspace_id == workspace_id,
            Opportunity.product_id == product_id,
            Opportunity.status == "open",
            Opportunity.type.in_(_OPPORTUNITY_TYPES_FOR_CONTENT),
        )
        .order_by(Opportunity.created_at.desc())
        .limit(10)
    ).scalars().all()

    ideas = []
    for opp in rows:
        if opp.id in excluded:
            continue
        ideas.append({
            "idea": f"{opp.title} — {opp.description}" if opp.description else opp.title,
            "content_type": "authority" if opp.type == OpportunityType.CONTENT else "engagement",
            "origin": "autonomous",
            "source_opportunity_id": opp.id,
        })
    return ideas


def _insight_ideas(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[dict]:
    """Only ACCEPTED insights drive strategy — a PENDING insight is an
    unreviewed finding awaiting a founder's Accept/Ignore decision, and
    acting on it before that would silently change strategy on an
    unconfirmed conclusion (§22's explicit anti-silent-change instruction)."""
    rows = db.execute(
        select(LearningInsight)
        .where(
            LearningInsight.workspace_id == workspace_id,
            LearningInsight.product_id == product_id,
            LearningInsight.status == LearningInsightStatus.ACCEPTED,
            LearningInsight.dimension.startswith("content_"),
        )
        .order_by(LearningInsight.confidence.desc())
        .limit(5)
    ).scalars().all()
    return [
        {
            "idea": f"Double down on what's working: {insight.hypothesis}",
            "content_type": "product",
            "origin": "autonomous",
            "source_opportunity_id": None,
        }
        for insight in rows
    ]


def _brand_message_ideas(brand: BrandBrain | None) -> list[dict]:
    if not brand or not brand.key_messages:
        return []
    return [
        {"idea": message, "content_type": "authority", "origin": "autonomous", "source_opportunity_id": None}
        for message in brand.key_messages
    ]


def plan_daily_content(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID, brand: BrandBrain | None) -> list[dict]:
    """Returns up to MAX_DAILY_CONTENT_ITEMS idea dicts:
    {idea, content_type, cta_hint, origin, source_opportunity_id}. Does not
    call AI and does not write to the DB — the caller (a scheduled job or the
    /content/plan-today route) generates variants per idea and marks any
    Opportunity used here as "actioned" once consumed."""
    under_quota = _under_quota_types(db, workspace_id=workspace_id, product_id=product_id)
    candidates = _opportunity_ideas(db, workspace_id=workspace_id, product_id=product_id)
    candidates += _insight_ideas(db, workspace_id=workspace_id, product_id=product_id)
    if not candidates:
        candidates = _brand_message_ideas(brand)
    if not candidates:
        return []

    # Prefer candidates whose content_type is currently under-quota;
    # deterministic stable sort keeps ties in original (most-recent-first) order.
    candidates.sort(key=lambda c: 0 if c["content_type"] in under_quota else 1)

    selected = candidates[:MAX_DAILY_CONTENT_ITEMS]
    for item in selected:
        item["cta_hint"] = cta_for_content_type(item["content_type"])
    return selected


def plan_campaign_content(db: Session, *, campaign: Campaign, brand: BrandBrain | None, count: int = 5) -> list[dict]:
    """§25-26 — CampaignAgent. Same composer, bounded invocation scoped to
    the campaign's own goal/audience rather than the workspace's general
    content mix."""
    count = min(count, len(_CAMPAIGN_ASSET_ANGLES))
    angles = _CAMPAIGN_ASSET_ANGLES[:count]
    audience = campaign.audience_description or "the target audience"
    ideas = []
    for angle, content_type in angles:
        idea = f"{angle.capitalize()} for the '{campaign.name}' campaign — goal: {campaign.goal or 'awareness'}, audience: {audience}"
        ideas.append({
            "idea": idea,
            "content_type": content_type,
            "cta_hint": cta_for_content_type(content_type),
            "origin": "campaign",
            "source_opportunity_id": None,
        })
    return ideas
