"""
Content Quality / Anti-Spam Gate (§28-29). Mirrors product_truth_validator.py's
two-layer shape exactly: a deterministic, free, always-run layer first, then
an AI layer that only runs if there's something to check against. Runs
right after generation (gates READY) and again defensively in
content_executor.py immediately before publish.
"""
import datetime as dt
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.product_truth_validator import ProductTruthValidator
from app.db.models.content import Content, ContentVariant
from app.db.models.product import BrandBrain
from app.db.models.visibility import ProductTruth
from app.providers.ai.base import AIProvider
from app.research.evidence import content_hash

_PLATFORM_LENGTH_LIMITS: dict[str, int] = {
    "x": 280,
    "instagram": 2200,
    "linkedin": 3000,
    "facebook": 5000,
    "reddit": 10000,
}

# Claims that are risky enough to fabricate that we require them to be
# explicitly present in the founder-approved claims/proof points before
# allowing them through — never invent security certifications, absolute
# customer counts, or performance guarantees (§5, §11).
_FABRICATION_PATTERNS = [
    "soc 2", "soc2", "iso 27001", "iso27001", "hipaa compliant", "gdpr certified",
    "pci dss", "penetration tested", "certified secure",
    "trusted by", "used by thousands", "fortune 500", "99.99% uptime", "100% accurate",
]

_SHINGLE_SIZE = 5
_NEAR_DUP_THRESHOLD = 0.6
_DEDUP_WINDOW_DAYS = 30


@dataclass
class QualityGateResult:
    passed: bool
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _shingles(text: str, k: int = _SHINGLE_SIZE) -> set[str]:
    words = _normalize(text).split()
    if not words:
        return set()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _recent_variants(db: Session, *, workspace_id: uuid.UUID, channel: str, exclude_id: uuid.UUID | None) -> list[ContentVariant]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=_DEDUP_WINDOW_DAYS)
    stmt = (
        select(ContentVariant)
        .join(Content, Content.id == ContentVariant.content_id)
        .where(Content.workspace_id == workspace_id, ContentVariant.channel == channel, ContentVariant.created_at >= cutoff)
    )
    if exclude_id is not None:
        stmt = stmt.where(ContentVariant.id != exclude_id)
    return db.execute(stmt).scalars().all()


def _run_deterministic_checks(
    db: Session, *, variant: ContentVariant, content: Content, brand: BrandBrain | None
) -> QualityGateResult:
    reasons: list[str] = []
    warnings: list[str] = []
    body = variant.body or ""
    body_hash = content_hash(_normalize(body))
    shingles = _shingles(body)

    for existing in _recent_variants(db, workspace_id=content.workspace_id, channel=variant.channel, exclude_id=variant.id):
        if not existing.body:
            continue
        if content_hash(_normalize(existing.body)) == body_hash:
            reasons.append(f"Exact duplicate of a {variant.channel} post published/queued in the last {_DEDUP_WINDOW_DAYS} days")
            break
        similarity = _jaccard(shingles, _shingles(existing.body))
        if similarity >= _NEAR_DUP_THRESHOLD:
            reasons.append(f"Near-duplicate ({similarity:.0%} similar) of a recent {variant.channel} post")
            break

    limit = _PLATFORM_LENGTH_LIMITS.get(variant.channel)
    if limit and len(body) > limit:
        reasons.append(f"Exceeds {variant.channel}'s {limit}-character limit ({len(body)} chars)")

    if brand:
        body_lower = body.lower()
        for word in brand.words_to_avoid or []:
            if word.strip() and word.strip().lower() in body_lower:
                reasons.append(f"Contains a brand-forbidden word: '{word}'")

        approved_text = " ".join((brand.claims or []) + (brand.proof_points or [])).lower()
        for pattern in _FABRICATION_PATTERNS:
            if pattern in body_lower and pattern not in approved_text:
                reasons.append(f"Contains an unsupported claim not in approved facts: '{pattern}'")

    if not body.strip():
        reasons.append("Empty body")

    return QualityGateResult(passed=not reasons, blocking_reasons=reasons, warnings=warnings)


def run_quality_gate(
    db: Session,
    *,
    variant: ContentVariant,
    content: Content,
    brand: BrandBrain | None,
    truth: ProductTruth | None,
    ai_provider: AIProvider | None = None,
) -> QualityGateResult:
    deterministic = _run_deterministic_checks(db, variant=variant, content=content, brand=brand)
    if not deterministic.passed:
        return deterministic

    if truth is None or ai_provider is None:
        # No Product Truth configured (Visibility module not set up) or no
        # AI provider passed — the gate degrades to the deterministic layer
        # only, so Content works standalone.
        return deterministic

    validator = ProductTruthValidator(db, ai_provider)
    result = validator.validate(proposed_text=variant.body, truth=truth, workspace_id=content.workspace_id)
    if not result.allowed:
        return QualityGateResult(passed=False, blocking_reasons=[result.reason or "Failed product truth validation"], warnings=deterministic.warnings)

    return QualityGateResult(passed=True, blocking_reasons=[], warnings=deterministic.warnings)
