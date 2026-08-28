"""Product screenshot upload endpoint — content-type validation and the
happy path storing a real file via StorageProvider and updating
VideoBrandKit.product_screenshot_url."""
from app.tests.conftest import get_default_workspace, register_user


def _tiny_png_bytes() -> bytes:
    # A minimal valid 1x1 PNG.
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc0c0c0040001056901180a3fb1000000"
        "0049454e44ae426082"
    )


def test_rejects_unsupported_content_type(client):
    owner = register_user(client)
    workspace_id = get_default_workspace(client, owner["headers"])
    product = client.post(
        f"/api/v1/workspaces/{workspace_id}/products", headers=owner["headers"], json={"name": "Test Product"}
    ).json()

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/videos/brand-kit/screenshot?product_id={product['id']}",
        headers=owner["headers"],
        files={"file": ("screenshot.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 400


def test_uploads_screenshot_and_updates_brand_kit(client):
    owner = register_user(client)
    workspace_id = get_default_workspace(client, owner["headers"])
    product = client.post(
        f"/api/v1/workspaces/{workspace_id}/products", headers=owner["headers"], json={"name": "Test Product"}
    ).json()

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/videos/brand-kit/screenshot?product_id={product['id']}",
        headers=owner["headers"],
        files={"file": ("screenshot.png", _tiny_png_bytes(), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["product_screenshot_url"]

    brand_kit = client.get(
        f"/api/v1/workspaces/{workspace_id}/videos/brand-kit?product_id={product['id']}", headers=owner["headers"]
    ).json()
    assert brand_kit["product_screenshot_url"] == body["product_screenshot_url"]
