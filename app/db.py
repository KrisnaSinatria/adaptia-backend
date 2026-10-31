from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings
from app.errors import ApiError


@lru_cache
def get_db() -> Client:
    # Service role: frontend tidak pernah bicara langsung ke Supabase, RLS menutup akses lain.
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise ApiError(503, "db_unconfigured", "SUPABASE_URL atau SUPABASE_SERVICE_ROLE_KEY belum diisi.")
    return create_client(s.supabase_url, s.supabase_service_role_key)
