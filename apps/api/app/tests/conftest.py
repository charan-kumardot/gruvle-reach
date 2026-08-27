import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.main import app

# Tests run against the same database configured in .env (DATABASE_URL).
# They create their own uniquely-named organizations/users and clean up
# after themselves, so they're safe to run against a shared dev database —
# but never point this at a production database.


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_user(client: TestClient, *, email: str | None = None, org_name: str | None = None) -> dict:
    email = email or f"test-{uuid.uuid4().hex[:10]}@example.com"
    org_name = org_name or f"Test Org {uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpassword123", "full_name": "Test User", "organization_name": org_name},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


def get_default_workspace(client: TestClient, headers: dict) -> str:
    orgs = client.get("/api/v1/organizations", headers=headers).json()
    org_id = orgs[0]["id"]
    workspaces = client.get(f"/api/v1/organizations/{org_id}/workspaces", headers=headers).json()
    return workspaces[0]["id"]


@pytest.fixture(autouse=True, scope="session")
def _sanity_check_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
