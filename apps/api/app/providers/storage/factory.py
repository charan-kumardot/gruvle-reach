from functools import lru_cache

from app.core.config import Settings, get_settings
from app.media.storage import StorageProvider
from app.media.storage_local import LocalDiskStorageProvider
from app.media.storage_supabase import SupabaseStorageProvider


def build_storage_provider(settings: Settings) -> StorageProvider:
    supabase = SupabaseStorageProvider(settings.supabase_url, settings.supabase_service_role_key, settings.supabase_storage_bucket)
    if supabase.configured():
        return supabase
    return LocalDiskStorageProvider(settings.api_base_url)


@lru_cache
def get_storage_provider() -> StorageProvider:
    return build_storage_provider(get_settings())
