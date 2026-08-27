import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.content_agent import ContentAgent
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import ContentStatus, OrgRole
from app.db.models.product import BrandBrain
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.schemas.content import ContentIdeaCreateRequest, ContentResponse, ContentVariantUpdateRequest
from app.schemas.product import BrandBrainRequest, BrandBrainResponse

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["content"])


@router.get("/brand-brain", response_model=BrandBrainResponse | None)
def get_brand_brain(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID | None = None,
):
    stmt = select(BrandBrain).where(BrandBrain.workspace_id == ctx.workspace_id)
    stmt = stmt.where(BrandBrain.product_id == product_id) if product_id else stmt.where(BrandBrain.product_id.is_(None))
    return db.execute(stmt).scalars().first()


@router.put("/brand-brain", response_model=BrandBrainResponse)
def upsert_brand_brain(
    payload: BrandBrainRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID | None = None,
):
    stmt = select(BrandBrain).where(BrandBrain.workspace_id == ctx.workspace_id)
    stmt = stmt.where(BrandBrain.product_id == product_id) if product_id else stmt.where(BrandBrain.product_id.is_(None))
    brand = db.execute(stmt).scalars().first()
    if brand is None:
        brand = BrandBrain(workspace_id=ctx.workspace_id, product_id=product_id)
        db.add(brand)
    for field, value in payload.model_dump().items():
        setattr(brand, field, value)
    db.commit()
    db.refresh(brand)
    return brand


@router.get("/content", response_model=list[ContentResponse])
def list_content(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    status: ContentStatus | None = None,
):
    stmt = select(Content).where(Content.workspace_id == ctx.workspace_id)
    if status:
        stmt = stmt.where(Content.status == status)
    return db.execute(stmt.order_by(Content.created_at.desc())).scalars().all()


@router.post("/content/generate", response_model=ContentResponse)
def generate_content(
    payload: ContentIdeaCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    brand = db.execute(
        select(BrandBrain).where(BrandBrain.workspace_id == ctx.workspace_id, BrandBrain.product_id == payload.product_id)
    ).scalars().first()

    content = Content(
        workspace_id=ctx.workspace_id,
        product_id=payload.product_id,
        idea=payload.idea,
        status=ContentStatus.DRAFT,
        source_idea_id=payload.source_idea_id,
    )
    db.add(content)
    db.flush()

    agent = ContentAgent(db, get_ai_provider())
    output = agent.generate_variants(idea=payload.idea, brand=brand, channels=payload.channels)
    if output is None:
        raise HTTPException(status_code=503, detail="AI provider unavailable or returned an unparseable response.")

    for variant_data in output.get("variants", []):
        db.add(
            ContentVariant(
                content_id=content.id,
                channel=variant_data.get("channel", ""),
                body=variant_data.get("body", ""),
                status=ContentStatus.DRAFT,
            )
        )
    db.commit()
    db.refresh(content)
    _ = content.variants  # load relationship before returning
    return content


@router.patch("/content/variants/{variant_id}", response_model=None)
def update_variant(
    variant_id: uuid.UUID,
    payload: ContentVariantUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    import datetime as dt

    variant = db.get(ContentVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Content variant not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    if payload.status == ContentStatus.APPROVED:
        variant.approved_by = ctx.user.id
        variant.approved_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(variant)
    return {
        "id": str(variant.id),
        "content_id": str(variant.content_id),
        "channel": variant.channel,
        "body": variant.body,
        "status": variant.status.value,
    }
