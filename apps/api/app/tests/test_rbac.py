"""VIEWER cannot write; MEMBER+ can (§6, §67, §81)."""
from app.tests.conftest import get_default_workspace, register_user


def _add_viewer_to_org(client, owner_headers: dict, org_id: str) -> dict:
    viewer = register_user(client)
    resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers=owner_headers,
        json={"email": viewer["email"], "role": "viewer"},
    )
    assert resp.status_code == 201, resp.text
    return viewer


def test_viewer_cannot_create_product(client):
    owner = register_user(client)
    org_id = client.get("/api/v1/organizations", headers=owner["headers"]).json()[0]["id"]
    workspace_id = get_default_workspace(client, owner["headers"])
    viewer = _add_viewer_to_org(client, owner["headers"], org_id)

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/products",
        headers=viewer["headers"],
        json={"name": "Viewer Attempted Product"},
    )
    assert resp.status_code == 403


def test_viewer_can_read_products(client):
    owner = register_user(client)
    org_id = client.get("/api/v1/organizations", headers=owner["headers"]).json()[0]["id"]
    workspace_id = get_default_workspace(client, owner["headers"])
    viewer = _add_viewer_to_org(client, owner["headers"], org_id)

    resp = client.get(f"/api/v1/workspaces/{workspace_id}/products", headers=viewer["headers"])
    assert resp.status_code == 200


def test_viewer_cannot_delete_product(client):
    owner = register_user(client)
    org_id = client.get("/api/v1/organizations", headers=owner["headers"]).json()[0]["id"]
    workspace_id = get_default_workspace(client, owner["headers"])
    product = client.post(
        f"/api/v1/workspaces/{workspace_id}/products", headers=owner["headers"], json={"name": "Owner Product"}
    ).json()
    viewer = _add_viewer_to_org(client, owner["headers"], org_id)

    resp = client.delete(f"/api/v1/workspaces/{workspace_id}/products/{product['id']}", headers=viewer["headers"])
    assert resp.status_code == 403


def test_member_can_create_but_not_delete_product(client):
    owner = register_user(client)
    org_id = client.get("/api/v1/organizations", headers=owner["headers"]).json()[0]["id"]
    workspace_id = get_default_workspace(client, owner["headers"])

    member = register_user(client)
    resp = client.post(
        f"/api/v1/organizations/{org_id}/members", headers=owner["headers"], json={"email": member["email"], "role": "member"}
    )
    assert resp.status_code == 201

    create_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/products", headers=member["headers"], json={"name": "Member Product"}
    )
    assert create_resp.status_code == 201

    delete_resp = client.delete(
        f"/api/v1/workspaces/{workspace_id}/products/{create_resp.json()['id']}", headers=member["headers"]
    )
    assert delete_resp.status_code == 403  # delete requires ADMIN+
