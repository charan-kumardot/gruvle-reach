"""
Shared idea->variants->quality-gate pipeline used by the /content router,
the /campaigns router, and the daily-content scheduled jobs — factored out
so background tasks don't have to reach into the API layer to reuse it.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.content_agent import ContentAgent
from app.agents.content_quality_gate import run_quality_gate
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import ContentStatus
from app.db.models.product import BrandBrain
from app.db.models.visibility import ProductTruth
from app.providers.ai.factory import get_ai_provider


def get_brand(db: Session, workspace_id: uuid.UUID, product_id: uuid.UUID) -> BrandBrain | None:
    return db.execute(
        select(BrandBrain).where(BrandBrain.workspace_id == workspace_id, BrandBrain.product_id == product_id)
    ).scalars().first()


def get_truth(db: Session, product_id: uuid.UUID) -> ProductTruth | None:
    return db.execute(select(ProductTruth).where(ProductTruth.product_id == product_id)).scalar_one_or_none()


def generate_and_gate_variants(
    db: Session, *, content: Content, brand: BrandBrain | None, truth: ProductTruth | None,
    channels: list[str], cta_hint: str = "",
) -> list[ContentVariant]:
    """Generates variants for `content` via ContentAgent, then immediately
    runs each through the quality gate, setting READY or FAILED (§28)."""
    agent = ContentAgent(db, get_ai_provider())
    output = agent.generate_variants(idea=content.idea, brand=brand, channels=channels, cta_hint=cta_hint)
    if output is None:
        return []

    variants: list[ContentVariant] = []
    for variant_data in output.get("variants", []):
        variant = ContentVariant(
            content_id=content.id,
            channel=variant_data.get("channel", ""),
            body=variant_data.get("body", ""),
            cta=variant_data.get("cta", ""),
        )
        db.add(variant)
        db.flush()
        gate_result = run_quality_gate(db, variant=variant, content=content, brand=brand, truth=truth, ai_provider=get_ai_provider())
        if gate_result.passed:
            variant.status = ContentStatus.READY
            variant.quality_flags = {"warnings": gate_result.warnings}
        else:
            variant.status = ContentStatus.FAILED
            variant.quality_flags = {"blocking_reasons": gate_result.blocking_reasons}
        variants.append(variant)
    return variants
