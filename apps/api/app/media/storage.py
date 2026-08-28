"""
StorageProvider abstraction (§16, §40 free-first). Render's API filesystem
is ephemeral (wiped on redeploy), so anything generated (rendered video/
image files) has to live somewhere durable to survive until a human reviews
it, possibly days later. Two implementations: Supabase Storage (free-tier,
already the shared Postgres project for this app) and local disk (dev-only
fallback — see storage_local.py for why it must never be the active
provider in production).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class UploadResult:
    success: bool
    url: str = ""
    error: str = ""


class StorageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def upload(self, *, path: str, data: bytes, content_type: str) -> UploadResult:
        ...

    @abstractmethod
    def delete(self, *, path: str) -> None:
        ...
