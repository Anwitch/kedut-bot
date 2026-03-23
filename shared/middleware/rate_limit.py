from functools import wraps
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from shared.database.supabase_client import get_supabase

MAX_REQUESTS = 5       # max request per window
WINDOW_MINUTES = 1      # per berapa menit

def rate_limited(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        now = datetime.now(timezone.utc)
        window = now.replace(second=0, microsecond=0) - timedelta(
            minutes=now.minute % WINDOW_MINUTES
        )

        db = get_supabase()
        res = db.table("rate_limits") \
            .select("request_count") \
            .eq("user_id", user_id) \
            .eq("window_start", window.isoformat()) \
            .execute()

        if res.data:
            count = res.data[0]["request_count"]
            if count >= MAX_REQUESTS:
                if update.callback_query:
                    await update.callback_query.answer(
                        "😅 Terlalu banyak request. Coba lagi dalam 1 menit ya.", 
                        show_alert=True
                    )
                elif update.message:
                    await update.message.reply_text(
                        "😅 Wah, kamu lagi ngebut banget nih!\n\n"
                        "Tenang dulu sebentar, coba lagi dalam 1 menit ya. 🙏"
                    )
                return
            # Increment
            db.table("rate_limits") \
                .update({"request_count": count + 1}) \
                .eq("user_id", user_id) \
                .eq("window_start", window.isoformat()) \
                .execute()
        else:
            # Window baru
            db.table("rate_limits").insert({
                "user_id": user_id,
                "window_start": window.isoformat(),
                "request_count": 1,
            }).execute()

        return await func(update, context)
    return wrapper
