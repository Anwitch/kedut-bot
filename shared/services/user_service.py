from shared.database.supabase_client import get_supabase

def register_user(user_id: str, username: str, first_name: str) -> None:
    db = get_supabase()
    db.table("users").upsert({
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
    }, on_conflict="user_id").execute()

def is_registered(user_id: str) -> bool:
    db = get_supabase()
    res = db.table("users").select("user_id").eq("user_id", user_id).eq("is_active", True).execute()
    return bool(res.data)
