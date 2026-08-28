import dataclasses
import datetime as dt
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.core.security import get_cipher
from app.db.models.enums import IntegrationProviderType, IntegrationStatus, OrgRole
from app.db.models.integration import Integration, IntegrationCredential
from app.db.session import get_db
from app.providers.email.factory import get_email_provider
from app.providers.git.github_provider import GitHubProvider
from app.providers.search.factory import get_search_provider
from app.providers.social.factory import get_social_providers
from app.schemas.integration import IntegrationCatalogEntry, IntegrationResponse

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations", tags=["integrations"])


@router.get("/catalog", response_model=list[IntegrationCatalogEntry])
def get_catalog(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    settings = get_settings()
    connected_rows = {
        r.provider_name: r
        for r in db.execute(select(Integration).where(Integration.workspace_id == ctx.workspace_id)).scalars().all()
    }

    entries: list[IntegrationCatalogEntry] = []

    search = get_search_provider()
    entries.append(
        IntegrationCatalogEntry(
            provider_name=search.name, provider_type=IntegrationProviderType.SEARCH,
            configured=search.configured(), connected=search.configured(), capabilities={"search": True},
        )
    )

    email = get_email_provider()
    row = connected_rows.get(email.name)
    entries.append(
        IntegrationCatalogEntry(
            provider_name=email.name, provider_type=IntegrationProviderType.EMAIL,
            configured=email.configured(), connected=bool(row and row.status == IntegrationStatus.CONNECTED),
            capabilities={"send": email.configured()},
        )
    )

    for name, provider in get_social_providers(settings).items():
        caps = provider.capabilities()
        row = connected_rows.get(name)
        entries.append(
            IntegrationCatalogEntry(
                provider_name=name, provider_type=IntegrationProviderType.SOCIAL,
                configured=provider.configured(), connected=bool(row and row.status == IntegrationStatus.CONNECTED),
                capabilities=dataclasses.asdict(caps), notes=caps.notes,
            )
        )

    github_row = connected_rows.get("github")
    entries.append(
        IntegrationCatalogEntry(
            provider_name="github", provider_type=IntegrationProviderType.GIT,
            configured=True,  # PAT-based — always available to connect, no deployment-level env var needed
            connected=bool(github_row and github_row.status == IntegrationStatus.CONNECTED),
            capabilities={"read_repository": True, "create_branch": True, "create_pull_request": True, "merge": False, "deploy": False},
            notes="Connect with a fine-grained Personal Access Token (repo contents + pull requests, read+write). Reach never merges a PR or deploys.",
        )
    )

    return entries


@router.get("", response_model=list[IntegrationResponse])
def list_integrations(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(Integration).where(Integration.workspace_id == ctx.workspace_id)).scalars().all()


@router.get("/{provider_name}/authorize-url")
def get_authorize_url(
    provider_name: str,
    redirect_uri: str,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
):
    providers = get_social_providers()
    provider = providers.get(provider_name)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown social provider")
    if not provider.configured():
        raise HTTPException(
            status_code=400,
            detail=f"{provider_name} is not configured on this deployment. Set its OAuth client ID/secret in .env to enable connecting.",
        )
    state = str(uuid.uuid4())
    url = provider.authorize_url(state=state, redirect_uri=redirect_uri)
    return {"authorize_url": url, "state": state}


class ConnectRequest(BaseModel):
    credential_payload: dict = {}
    scopes: list[str] = []


@router.post("/{provider_name}/connect", response_model=IntegrationResponse)
def connect_integration(
    provider_name: str,
    payload: ConnectRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    settings = get_settings()
    all_known = {p.name for p in get_social_providers(settings).values()} | {get_email_provider().name, get_search_provider().name, "github"}
    if provider_name not in all_known:
        raise HTTPException(status_code=404, detail="Unknown provider")

    provider_type = IntegrationProviderType.SOCIAL
    if provider_name in (get_email_provider().name,):
        provider_type = IntegrationProviderType.EMAIL
    elif provider_name in (get_search_provider().name,):
        provider_type = IntegrationProviderType.SEARCH
    elif provider_name == "github":
        provider_type = IntegrationProviderType.GIT
        pat = payload.credential_payload.get("pat", "")
        candidate = GitHubProvider(token=pat)
        if not candidate.configured():
            raise HTTPException(status_code=400, detail="A Personal Access Token is required")
        try:
            candidate.list_repositories()  # validates the token actually works before we store it
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Could not authenticate with GitHub: {exc}") from exc

    row = db.execute(
        select(Integration).where(Integration.workspace_id == ctx.workspace_id, Integration.provider_name == provider_name)
    ).scalar_one_or_none()
    if row is None:
        row = Integration(workspace_id=ctx.workspace_id, provider_type=provider_type, provider_name=provider_name)
        db.add(row)
        db.flush()

    row.status = IntegrationStatus.CONNECTED
    row.connected_by = ctx.user.id
    row.connected_at = dt.datetime.now(dt.timezone.utc)
    row.scopes = payload.scopes

    if payload.credential_payload:
        cipher = get_cipher()
        encrypted = cipher.encrypt(json.dumps(payload.credential_payload))
        cred = db.execute(select(IntegrationCredential).where(IntegrationCredential.integration_id == row.id)).scalar_one_or_none()
        if cred is None:
            cred = IntegrationCredential(integration_id=row.id, encrypted_payload=encrypted)
            db.add(cred)
        else:
            cred.encrypted_payload = encrypted

    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="integration_connect", resource_type="integration", resource_id=str(row.id),
        metadata={"provider_name": provider_name},  # never the credential payload itself
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/{provider_name}/disconnect", response_model=IntegrationResponse)
def disconnect_integration(
    provider_name: str,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    row = db.execute(
        select(Integration).where(Integration.workspace_id == ctx.workspace_id, Integration.provider_name == provider_name)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not connected")

    creds = db.execute(select(IntegrationCredential).where(IntegrationCredential.integration_id == row.id)).scalars().all()
    for cred in creds:
        db.delete(cred)

    row.status = IntegrationStatus.DISCONNECTED
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="integration_disconnect", resource_type="integration", resource_id=str(row.id),
        metadata={"provider_name": provider_name},
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/github/repositories")
def list_github_repositories(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    from app.providers.git.factory import get_git_provider_for_workspace

    git_provider = get_git_provider_for_workspace(db, ctx.workspace_id)
    if not git_provider.configured():
        raise HTTPException(status_code=400, detail="GitHub is not connected for this workspace")
    repos = git_provider.list_repositories()
    return [
        {"owner": r.owner, "name": r.name, "default_branch": r.default_branch, "private": r.private, "html_url": r.html_url}
        for r in repos
    ]
