"""
Local disk storage — DEV-ONLY. Render's API filesystem is ephemeral (wiped
on every redeploy/restart), so anything written here does not survive
production deploys. This provider exists purely so local development works
with zero external setup; the factory picks it only when Supabase Storage
isn't configured, and logs a loud warning if that happens outside
development so the gap is visible, not silent.
"""
import logging
from pathlib import Path

from app.core.config import get_settings
from app.media.storage import StorageProvider, UploadResult

logger = logging.getLogger(__name__)

_MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent / "media_files"


class LocalDiskStorageProvider(StorageProvider):
    name = "local_disk"

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        settings = get_settings()
        if settings.app_env != "development":
            logger.warning(
                "LocalDiskStorageProvider is active outside development (APP_ENV=%s) — "
                "generated media will NOT survive a redeploy. Configure SUPABASE_URL/"
                "SUPABASE_SERVICE_ROLE_KEY to use durable storage.",
                settings.app_env,
            )

    def configured(self) -> bool:
        return True  # always available — the dev-only fallback of last resort

    def upload(self, *, path: str, data: bytes, content_type: str) -> UploadResult:
        target = _MEDIA_ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return UploadResult(success=True, url=f"{self._base_url}/media/{path}")

    def delete(self, *, path: str) -> None:
        target = _MEDIA_ROOT / path
        if target.exists():
            target.unlink()
