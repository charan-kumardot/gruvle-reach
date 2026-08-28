import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.icp_agent import ICPAgent
from app.agents.product_understanding_agent import ProductUnderstandingAgent
from app.agents.research_orchestrator import run_autonomous_discovery
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.enums import ICPStatus, OrgRole
from app.db.models.product import ICPProfile, Product, ProductProfile
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.search.factory import get_search_provider
from app.schemas.growth import ResearchRunResponse
from app.schemas.product import (
    ICPProfileResponse,
    ICPUpdateRequest,
    ProductCreateRequest,
    ProductProfileResponse,
    ProductResponse,
    ProductUpdateRequest,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def list_products(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(Product).where(Product.workspace_id == ctx.workspace_id)).scalars().all()


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    product = Product(workspace_id=ctx.workspace_id, **payload.model_dump())
    db.add(product)
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="product_created", resource_type="product", resource_id=str(product.id),
    )
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="product_deleted", resource_type="product", resource_id=str(product_id),
    )
    db.commit()


@router.post("/{product_id}/understand", response_model=ProductProfileResponse)
def run_product_understanding(
    product_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")

    agent = ProductUnderstandingAgent(db, get_ai_provider())
    output = agent.run(product)
    if output is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider unavailable or returned an unparseable response. Check your AI_PROVIDER configuration (Ollama must be running locally by default).",
        )

    profile = ProductProfile(
        product_id=product.id,
        product_category=output.get("product_category", ""),
        primary_problem=output.get("primary_problem", ""),
        primary_buyer=output.get("primary_buyer", ""),
        secondary_buyers=output.get("secondary_buyers", []),
        target_industries=output.get("target_industries", []),
        use_cases=output.get("use_cases", []),
        competitive_categories=output.get("competitive_categories", []),
        keywords=output.get("keywords", []),
        search_queries=output.get("search_queries", []),
        raw_ai_output=output,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{product_id}/profile", response_model=ProductProfileResponse | None)
def get_latest_profile(product_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")
    return db.execute(
        select(ProductProfile).where(ProductProfile.product_id == product_id).order_by(ProductProfile.created_at.desc())
    ).scalars().first()


@router.post("/{product_id}/icp/generate", response_model=list[ICPProfileResponse])
def generate_icp(
    product_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")
    profile = db.execute(
        select(ProductProfile).where(ProductProfile.product_id == product_id).order_by(ProductProfile.created_at.desc())
    ).scalars().first()

    agent = ICPAgent(db, get_ai_provider())
    output = agent.run(product, profile)
    if output is None or "icps" not in output:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI provider unavailable or returned an unparseable response.")

    created = []
    for icp_data in output["icps"]:
        icp = ICPProfile(
            product_id=product.id,
            name=icp_data.get("name", "Untitled ICP"),
            criteria=icp_data.get("criteria", {}),
            score=float(icp_data.get("score", 0)),
            factors=icp_data.get("factors", {}),
            status=ICPStatus.AI_HYPOTHESIS,
            created_by="ai",
        )
        db.add(icp)
        created.append(icp)
    db.commit()
    for icp in created:
        db.refresh(icp)
    return created


@router.get("/{product_id}/icp", response_model=list[ICPProfileResponse])
def list_icp_profiles(product_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")
    return db.execute(select(ICPProfile).where(ICPProfile.product_id == product_id).order_by(ICPProfile.score.desc())).scalars().all()


@router.patch("/{product_id}/icp/{icp_id}", response_model=ICPProfileResponse)
def update_icp(
    product_id: uuid.UUID,
    icp_id: uuid.UUID,
    payload: ICPUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    icp = db.get(ICPProfile, icp_id)
    if icp is None or icp.product_id != product_id:
        raise HTTPException(status_code=404, detail="ICP not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(icp, field, value)
    if payload.status == ICPStatus.FOUNDER_CONFIRMED:
        icp.created_by = "founder" if icp.created_by == "ai" else icp.created_by
    db.commit()
    db.refresh(icp)
    return icp


@router.post("/{product_id}/autonomous-discovery", response_model=ResearchRunResponse)
def autonomous_discovery(
    product_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Zero-input discovery (§6, §8): no search query required — derives
    everything from the product itself (reusing/creating product
    understanding + ICP as needed) and discovers candidate companies."""
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")

    run = run_autonomous_discovery(
        db, workspace_id=ctx.workspace_id, product=product,
        ai_provider=get_ai_provider(), search_provider=get_search_provider(),
    )
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="autonomous_discovery_run", resource_type="research_run", resource_id=str(run.id),
        metadata={"status": run.status},
    )
    db.commit()
    db.refresh(run)
    return run
