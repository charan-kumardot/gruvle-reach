import uuid

from sqlalchemy.orm import Session

from app.db.models.audit import AuditLog


def record_audit(
    db: Session,
    *,
    organization_id: uuid.UUID,
    action: str,
    workspace_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    resource_type: str = "",
    resource_id: str = "",
    metadata: dict | None = None,
    ip_address: str = "",
) -> None:
    """Append an audit log row. Callers must ensure `metadata` never contains
    secret values (API keys, tokens, passwords)."""
    db.add(
        AuditLog(
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            audit_metadata=metadata or {},
            ip_address=ip_address,
        )
    )
