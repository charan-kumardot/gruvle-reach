"""
Learning Agent (§24). Deterministic — no AI call, same "deterministic
before AI" principle as app/agents/scoring.py. Groups outcomes by a
dimension (industry, ICP fit category, trigger type, channel, investor
sector) and only ever surfaces an insight once a minimum sample size is
met, per the spec's own explicit anti-overfitting instruction.
"""
import datetime as dt
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.company import Company, CompanyTrigger
from app.db.models.enums import LearningInsightStatus, PipelineStage
from app.db.models.growth import LearningInsight
from app.db.models.investor import InvestorInteraction
from app.db.models.outreach import Outreach

MIN_SAMPLE_SIZE = 5
_REPLIED_STAGES = {PipelineStage.REPLIED, PipelineStage.MEETING, PipelineStage.WON}
_SENT_OR_LATER_STAGES = {PipelineStage.SENT, PipelineStage.REPLIED, PipelineStage.MEETING, PipelineStage.WON, PipelineStage.LOST, PipelineStage.NOT_NOW}


def _confidence_for_sample(n: int) -> float:
    """Small, explicit, monotonic-in-n heuristic — not a real statistical
    test, and we say so wherever this is surfaced. More samples -> more
    confidence, capped well short of certainty."""
    return round(min(0.85, 0.25 + n * 0.03), 2)


def _upsert_insight(
    db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID, dimension: str,
    group_label: str, group_rate: float, baseline_rate: float, sample_size: int, group_n: int,
) -> LearningInsight | None:
    if group_n < MIN_SAMPLE_SIZE:
        return None
    lift = (group_rate / baseline_rate) if baseline_rate > 0 else 0.0
    if lift < 1.3:  # only surface a genuinely meaningful difference, not noise
        return None

    hypothesis = f"{group_label} convert {lift:.1f}x more often than your average ({dimension.replace('_', ' ')})"

    existing = db.execute(
        select(LearningInsight).where(
            LearningInsight.workspace_id == workspace_id, LearningInsight.product_id == product_id,
            LearningInsight.dimension == dimension, LearningInsight.hypothesis == hypothesis,
            LearningInsight.status == LearningInsightStatus.PENDING,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None  # already surfaced, awaiting founder response — don't spam duplicates

    insight = LearningInsight(
        workspace_id=workspace_id, product_id=product_id, dimension=dimension, hypothesis=hypothesis,
        sample_size=group_n,
        result_summary={
            "group": group_label, "group_rate": round(group_rate, 3), "baseline_rate": round(baseline_rate, 3),
            "lift": round(lift, 2), "total_sample_size": sample_size,
        },
        confidence=_confidence_for_sample(group_n),
    )
    db.add(insight)
    return insight


def analyze_outreach_by_industry(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[LearningInsight]:
    rows = db.execute(
        select(Outreach, Company)
        .join(Company, Company.id == Outreach.target_id)
        .where(Outreach.workspace_id == workspace_id, Outreach.product_id == product_id, Outreach.target_type == "company")
    ).all()

    by_industry: dict[str, list[bool]] = defaultdict(list)  # industry -> [replied?]
    total_sent = 0
    total_replied = 0
    for outreach, company in rows:
        if outreach.status not in _SENT_OR_LATER_STAGES:
            continue
        industry = company.industry or "unspecified"
        replied = outreach.status in _REPLIED_STAGES
        by_industry[industry].append(replied)
        total_sent += 1
        total_replied += int(replied)

    if total_sent == 0:
        return []
    baseline_rate = total_replied / total_sent

    insights = []
    for industry, outcomes in by_industry.items():
        if industry == "unspecified":
            continue
        n = len(outcomes)
        rate = sum(outcomes) / n
        insight = _upsert_insight(
            db, workspace_id=workspace_id, product_id=product_id, dimension="industry",
            group_label=f"{industry} companies", group_rate=rate, baseline_rate=baseline_rate,
            sample_size=total_sent, group_n=n,
        )
        if insight:
            insights.append(insight)
    db.flush()
    return insights


def analyze_outreach_by_trigger(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[LearningInsight]:
    rows = db.execute(
        select(Outreach, CompanyTrigger)
        .join(Company, Company.id == Outreach.target_id)
        .join(CompanyTrigger, CompanyTrigger.company_id == Company.id)
        .where(Outreach.workspace_id == workspace_id, Outreach.product_id == product_id, Outreach.target_type == "company")
    ).all()

    by_trigger: dict[str, list[bool]] = defaultdict(list)
    total_sent = 0
    total_replied = 0
    seen_pairs: set[tuple] = set()
    for outreach, trigger in rows:
        if outreach.status not in _SENT_OR_LATER_STAGES:
            continue
        key = (outreach.id, trigger.trigger_type)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        replied = outreach.status in _REPLIED_STAGES
        by_trigger[trigger.trigger_type].append(replied)
        total_sent += 1
        total_replied += int(replied)

    if total_sent == 0:
        return []
    baseline_rate = total_replied / total_sent

    insights = []
    for trigger_type, outcomes in by_trigger.items():
        n = len(outcomes)
        rate = sum(outcomes) / n
        insight = _upsert_insight(
            db, workspace_id=workspace_id, product_id=product_id, dimension="trigger_type",
            group_label=f"companies with a '{trigger_type}' trigger", group_rate=rate, baseline_rate=baseline_rate,
            sample_size=total_sent, group_n=n,
        )
        if insight:
            insights.append(insight)
    db.flush()
    return insights


def run_learning_analysis(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> list[LearningInsight]:
    insights = analyze_outreach_by_industry(db, workspace_id=workspace_id, product_id=product_id)
    insights += analyze_outreach_by_trigger(db, workspace_id=workspace_id, product_id=product_id)
    return insights
