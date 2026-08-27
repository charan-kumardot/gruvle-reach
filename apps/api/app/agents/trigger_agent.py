"""Trigger Agent (§13) — turns company signals into 'reason to act now' triggers."""
import datetime as dt

from sqlalchemy.orm import Session

from app.db.models.company import Company, CompanySignal, CompanyTrigger

SIGNAL_TO_TRIGGER = {
    "funding": ("funding", "Recently raised funding", 80.0),
    "hiring": ("hiring", "Actively hiring / expanding team", 55.0),
    "product_launch": ("product_launch", "Launched a new product or feature", 75.0),
    "technology_adoption": ("technology_adoption", "Adopted a relevant technology", 60.0),
}


class TriggerAgent:
    name = "trigger_agent"
    allowed_tools = ["database_read"]
    allowed_actions = ["database_write"]

    def __init__(self, db: Session):
        self.db = db

    def detect_triggers(self, company: Company, signals: list[CompanySignal]) -> list[CompanyTrigger]:
        triggers: list[CompanyTrigger] = []
        for signal in signals:
            mapping = SIGNAL_TO_TRIGGER.get(signal.signal_type)
            if not mapping:
                continue
            trigger_type, why_template, base_relevance = mapping

            trigger = CompanyTrigger(
                company_id=company.id,
                trigger_type=trigger_type,
                description=signal.description,
                trigger_date=dt.date.today(),
                source_url=signal.source_url,
                evidence_snippet=signal.description,
                confidence=signal.confidence,
                relevance_score=base_relevance * signal.confidence / 0.6,
                product_fit_score=company.icp_fit_score,
                why_it_matters=f"{why_template} — increases likelihood the company has budget/urgency for this category now.",
            )
            self.db.add(trigger)
            triggers.append(trigger)

        self.db.flush()
        return triggers
