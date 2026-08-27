"""Stored integration credentials must be encrypted at rest and must never
appear in an audit log entry (§5, §71)."""
from app.core.security import CredentialCipher


def test_credential_roundtrip():
    cipher = CredentialCipher()
    secret = "super-secret-oauth-token-value"
    encrypted = cipher.encrypt(secret)
    assert secret not in encrypted
    assert cipher.decrypt(encrypted) == secret


def test_connect_integration_audit_log_never_contains_credential_payload(client):
    from app.tests.conftest import get_default_workspace, register_user

    owner = register_user(client)
    workspace_id = get_default_workspace(client, owner["headers"])

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/integrations/searxng/connect",
        headers=owner["headers"],
        json={"credential_payload": {"api_key": "THIS_MUST_NEVER_BE_LOGGED"}},
    )
    assert resp.status_code == 200

    org_id = client.get("/api/v1/organizations", headers=owner["headers"]).json()[0]["id"]
    logs_resp = client.get(f"/api/v1/workspaces/{workspace_id}/audit-logs", headers=owner["headers"])
    assert logs_resp.status_code == 200
    body = logs_resp.text
    assert "THIS_MUST_NEVER_BE_LOGGED" not in body
