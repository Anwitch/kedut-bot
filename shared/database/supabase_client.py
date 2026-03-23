import logging

from supabase import create_client, Client
from shared.config import settings

_client: Client | None = None

logger = logging.getLogger(__name__)


def get_supabase() -> Client:
    global _client
    if _client is None:
        key = settings.SUPABASE_ANON_KEY or ""
        logger.info(
            "Initializing Supabase client url=%s key_len=%d key_dots=%d key_has_ellipsis=%s",
            settings.SUPABASE_URL,
            len(key),
            key.count("."),
            ("..." in key),
        )
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _client
