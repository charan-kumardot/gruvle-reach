"""Evidence ledger helpers (§44). Every claim the system asserts about a
company, investor, trigger, or opportunity should be backed by a row here."""
import datetime as dt
import hashlib
import uuid

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
