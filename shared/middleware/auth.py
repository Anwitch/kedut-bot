from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from shared.services.user_service import is_registered

def require_registered(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not is_registered(user_id):
            # Check if this is a query callback
            if update.callback_query:
                await update.callback_query.answer(
                    "👋 Hai! Anda belum terdaftar. Ketuk /start untuk mulai.", 
                    show_alert=True
                )
            elif update.message:
                await update.message.reply_text(
                    "👋 Hai! Untuk mulai pakai Montrac, ketuk /start dulu ya."
                )
            return
        return await func(update, context)
    return wrapper
