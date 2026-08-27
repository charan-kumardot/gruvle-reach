"""Tenant A must never be able to read or write Tenant B's data (§81)."""
from app.tests.conftest import get_default_workspace, register_user


def test_outsider_cannot_list_products_in_foreign_workspace(client):
    owner = register_user(client)
    workspace_id = get_default_workspace(client, owner["headers"])
    client.post(
        f"/api/v1/workspaces/{workspace_id}/products",
        headers=owner["headers"],
        json={"name": "Secret Product", "description": "should not leak"},
    )

    outsider = register_user(client)
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/products", headers=outsider["headers"])

    # Must not confirm the workspace's existence to a non-member — 404, not 403.
    assert resp.status_code == 404


def test_outsider_cannot_create_product_in_foreign_workspace(client):
    owner = register_user(client)
    workspace_id = get_default_workspace(client, owner["headers"])

    outsider = register_user(client)
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/products",
        headers=outsider["headers"],
        json={"name": "Injected Product"},
    )
    assert resp.status_code == 404


def test_outsider_cannot_read_specific_product_by_id(client):
    owner = register_user(client)
    workspace_id = get_default_workspace(client, owner["headers"])
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/products",
        headers=owner["headers"],
        json={"name": "Owner's Product"},
    ).json()

    outsider = register_user(client)
    outsider_workspace_id = get_default_workspace(client, outsider["headers"])

    # Even referencing the foreign product_id through the outsider's own
    # (valid, owned) workspace must not resolve it.
    resp = client.get(
        f"/api/v1/workspaces/{outsider_workspace_id}/products/{created['id']}",
        headers=outsider["headers"],
    )
    assert resp.status_code == 404


def test_unauthenticated_request_is_rejected(client):
    owner = register_user(client)
    workspace_id = get_default_workspace(client, owner["headers"])
    resp = client.get(f"/api/v1/workspaces/{workspace_id}/products")
    assert resp.status_code == 401
