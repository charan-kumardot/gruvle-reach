import io
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.audit import AuditLog
from app.db.models.company import Company
from app.db.models.enums import OrgRole
from app.db.models.investor import Investor
from app.db.models.opportunity import Opportunity
from app.db.models.tenancy import Workspace
from app.db.session import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["settings"])


@router.get("/audit-logs")
def list_audit_logs(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 100,
):
    rows = db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == ctx.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 500))
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "user_id": str(r.user_id) if r.user_id else None,
            "metadata": r.audit_metadata,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


_EXPORTABLE = {"companies": Company, "investors": Investor, "opportunities": Opportunity}


@router.get("/export/{entity}")
def export_entity(
    entity: str,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    format: str = "json",
):
    model = _EXPORTABLE.get(entity)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown exportable entity '{entity}'. Options: {list(_EXPORTABLE)}")

    stmt = select(model)
    if hasattr(model, "workspace_id"):
        stmt = stmt.where(model.workspace_id == ctx.workspace_id)
    rows = db.execute(stmt).scalars().all()

    columns = [c.name for c in model.__table__.columns]
    records = [{col: _jsonable(getattr(row, col)) for col in columns} for row in rows]

    if format == "csv":
        import csv

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in record.items()})
        return Response(content=buf.getvalue(), media_type="text/csv")

    return Response(content=json.dumps(records, default=str), media_type="application/json")


def _jsonable(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


@router.delete("/data/{entity}/{entity_id}", status_code=204)
def delete_entity(
    entity: str,
    entity_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Generic workspace-scoped hard delete for the Security Center's data controls (§73)."""
    model = _EXPORTABLE.get(entity)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown entity '{entity}'")
    row = db.get(model, entity_id)
    if row is None or (hasattr(row, "workspace_id") and row.workspace_id != ctx.workspace_id):
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
