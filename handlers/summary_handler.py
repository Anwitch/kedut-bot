import logging
from telegram import Update
from telegram.ext import ContextTypes
from shared.services.summary_service import get_weekly_summary, get_monthly_summary
from shared.middleware.auth import require_registered
from shared.middleware.rate_limit import rate_limited

logger = logging.getLogger(__name__)


@require_registered
@rate_limited
async def handle_weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    summary = get_weekly_summary(user_id)
    await update.message.reply_text(summary, parse_mode="Markdown")


@require_registered
@rate_limited
async def handle_monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    summary = get_monthly_summary(user_id)
    await update.message.reply_text(summary, parse_mode="Markdown")
