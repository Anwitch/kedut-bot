import logging
from shared.database.supabase_client import get_supabase

logger = logging.getLogger(__name__)

def register_user(user_id: str, username: str, first_name: str) -> None:
    try:
        db = get_supabase()
        db.table("users").upsert({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
        }, on_conflict="user_id").execute()
    except Exception as e:
        logger.error("Failed to register user %s: %s", user_id, e)

_registered_cache: set[str] = set()

def is_registered(user_id: str) -> bool:
    if user_id in _registered_cache:
        return True
    
    db = get_supabase()
    res = db.table("users").select("user_id").eq("user_id", user_id).eq("is_active", True).execute()
    
    if res.data:
        _registered_cache.add(user_id)
        return True
    return False
