import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from shared.nlp.gemini_parser import (
    GeminiQuotaExceeded,
    parse_expense,
    parse_expense_from_receipt_image,
)
from shared.services.expense_service import add_expense, delete_expense
from shared.utils.formatters import format_currency, format_expense_confirmation
from shared.middleware.auth import require_registered
from shared.middleware.rate_limit import rate_limited

logger = logging.getLogger(__name__)

# Callback data prefix for undo actions
_UNDO_PREFIX = "undo:"


def _undo_keyboard(expense_id: str) -> InlineKeyboardMarkup:
    """Return an inline keyboard with a single Undo button."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ Batalkan", callback_data=f"{_UNDO_PREFIX}{expense_id}")]]
    )


def _quota_error_message(e: GeminiQuotaExceeded) -> str:
    extra = (
        f"\n\nCoba lagi dalam ~{e.retry_after_seconds} detik ya."
        if e.retry_after_seconds
        else "\n\nCoba lagi beberapa saat lagi ya."
    )
    return (
        "😅 Waduh, otakku lagi overload nih!"
        + extra
        + "\n\nSementara itu, kamu bisa catat dulu di Notes terus masukin nanti."
    )

@require_registered
@rate_limited
async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        parsed = parse_expense(text)
    except GeminiQuotaExceeded as e:
        await update.message.reply_text(_quota_error_message(e))
        return

    if not parsed or parsed["amount"] <= 0:
        await update.message.reply_text(
            "❓ Maaf, aku tidak bisa memahami pengeluaran itu.\n\n"
            "Coba format seperti:\n"
            "`makan siang 35rb`\n"
            "`bayar listrik 250000`",
            parse_mode="Markdown",
        )
        return

    try:
        row = add_expense(
            user_id=user_id,
            amount=parsed["amount"],
            category_name=parsed["category"],
            note=parsed["note"],
            expense_date=parsed["date"],
        )
        expense_id = row.get("id")
        msg = format_expense_confirmation(
            amount=parsed["amount"],
            category=parsed["category"],
            note=parsed["note"],
        )
        # Attach undo button only if we got a valid id back
        markup = _undo_keyboard(expense_id) if expense_id else None
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error saving expense: {e}")
        await update.message.reply_text(
            "⚠️ Gagal menyimpan pengeluaran. Coba lagi ya!"
        )


@require_registered
@rate_limited
async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    message = update.message
    if not message or not message.photo:
        return

    caption = (message.caption or "").strip()

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        photo = message.photo[-1]  # highest resolution
        tg_file = await context.bot.get_file(photo.file_id)
        data = await tg_file.download_as_bytearray()
        parsed = parse_expense_from_receipt_image(
            bytes(data), mime_type="image/jpeg", caption=caption
        )
    except GeminiQuotaExceeded as e:
        await message.reply_text(_quota_error_message(e))
        return
    except Exception as e:
        logger.error("Error downloading/parsing receipt photo: %s", e, exc_info=True)
        parsed = None

    if not parsed or parsed.get("amount", 0) <= 0:
        await message.reply_text(
            "❓ Maaf, aku belum bisa membaca struk itu.\n\n"
            "Coba kirim foto yang lebih jelas (tidak blur, rata, terang), atau ketik manual seperti:\n"
            "`makan siang 35rb`",
            parse_mode="Markdown",
        )
        return

    try:
        row = add_expense(
            user_id=user_id,
            amount=parsed["amount"],
            category_name=parsed["category"],
            note=parsed["note"],
            expense_date=parsed["date"],
        )
        expense_id = row.get("id")
        msg = format_expense_confirmation(
            amount=parsed["amount"],
            category=parsed["category"],
            note=parsed["note"],
        )
        markup = _undo_keyboard(expense_id) if expense_id else None
        await message.reply_text(msg, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error("Error saving receipt expense: %s", e, exc_info=True)
        await message.reply_text("⚠️ Gagal menyimpan pengeluaran. Coba lagi ya!")


async def handle_undo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the ↩️ Batalkan inline button press."""
    query = update.callback_query
    await query.answer()  # dismiss the loading spinner on the button

    if not query.data or not query.data.startswith(_UNDO_PREFIX):
        return

    user_id = str(update.effective_user.id)
    expense_id = query.data[len(_UNDO_PREFIX):]

    try:
        deleted = delete_expense(expense_id=expense_id, user_id=user_id)
    except Exception as e:
        logger.error("Error deleting expense %s: %s", expense_id, e, exc_info=True)
        await query.edit_message_text(
            query.message.text + "\n\n⚠️ Gagal membatalkan. Coba lagi ya!",
            parse_mode="Markdown",
        )
        return

    if deleted:
        # Edit the original confirmation message — remove the undo button and add a note
        original = query.message.text or ""
        await query.edit_message_text(
            original + "\n\n~~Dibatalkan~~",
            parse_mode="Markdown",
        )
    else:
        # Already deleted or belongs to another user
        await query.edit_message_text(
            (query.message.text or "") + "\n\n⚠️ Transaksi tidak ditemukan atau sudah dibatalkan.",
            parse_mode="Markdown",
        )