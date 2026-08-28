"""Evidence ledger helpers (§44). Every claim the system asserts about a
company, investor, trigger, or opportunity should be backed by a row here."""
import datetime as dt
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.enums import EvidenceStatus
from app.db.models.research import Evidence


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def record_evidence(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    claim: str,
    source_url: str,
    evidence_snippet: str = "",
    source_type: str = "webpage",
    confidence: float = 0.5,
    status: EvidenceStatus = EvidenceStatus.HYPOTHESIS,
    related_entity_type: str = "",
    related_entity_id: uuid.UUID | None = None,
) -> Evidence:
    row = Evidence(
        workspace_id=workspace_id,
        claim=claim,
        evidence_snippet=evidence_snippet[:2000],
        source_url=source_url,
        source_type=source_type,
        confidence=confidence,
        status=status,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        retrieved_at=dt.datetime.now(dt.timezone.utc),
        content_hash=content_hash(evidence_snippet or claim),
    )
    db.add(row)
    db.flush()
    return row


def recent_evidence_exists(db: Session, *, workspace_id: uuid.UUID, source_url: str, max_age_days: int = 7) -> bool:
    """Research memory (§23): skip re-fetching a URL this workspace already
    has recent evidence for, rather than re-researching the same thing on
    every discovery run. Scoped per-workspace (matching Evidence's own
    scoping) — a global cross-workspace cache is a further extension."""
    if not source_url:
        return False
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=max_age_days)
    existing = db.execute(
        select(Evidence.id).where(
            Evidence.workspace_id == workspace_id,
            Evidence.source_url == source_url,
            Evidence.retrieved_at >= cutoff,
        )
    ).scalar_one_or_none()
    return existing is not None
