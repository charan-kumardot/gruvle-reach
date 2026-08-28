"""
Supabase Storage — free-tier, S3-compatible, already part of the shared
Supabase project this app uses for Postgres. Talks to the plain REST API
over httpx (already a dependency) — no new SDK. The bucket is expected to
be public-read (created once, out of band) so a stored video/image can be
linked directly from ContentVariant.media_refs without a signed-URL dance.
"""
import httpx

from app.media.storage import StorageProvider, UploadResult


class SupabaseStorageProvider(StorageProvider):
    name = "supabase_storage"

    def __init__(self, supabase_url: str, service_role_key: str, bucket: str):
        self._base_url = supabase_url.rstrip("/")
        self._key = service_role_key
        self._bucket = bucket

    def configured(self) -> bool:
        return bool(self._base_url and self._key)

    def upload(self, *, path: str, data: bytes, content_type: str) -> UploadResult:
        if not self.configured():
            return UploadResult(success=False, error="Supabase Storage is not configured")
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{path}"
        try:
            resp = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "apikey": self._key,
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=data,
                timeout=60,
            )
            if resp.status_code >= 400:
                return UploadResult(success=False, error=f"Supabase Storage error {resp.status_code}: {resp.text[:300]}")
            public_url = f"{self._base_url}/storage/v1/object/public/{self._bucket}/{path}"
            return UploadResult(success=True, url=public_url)
        except httpx.HTTPError as exc:
            return UploadResult(success=False, error=str(exc))

    def delete(self, *, path: str) -> None:
        if not self.configured():
            return
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{path}"
        try:
            httpx.delete(url, headers={"Authorization": f"Bearer {self._key}", "apikey": self._key}, timeout=20)
        except httpx.HTTPError:
            pass  # best-effort cleanup, never block the caller on a delete failure
