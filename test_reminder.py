# bot/test_reminder.py
import asyncio
import sys
import os

# Allow sibling imports when running from bot/ directory
sys.path.insert(0, os.path.dirname(__file__))

from telegram import Bot
from shared.config import settings
from reminder_job import build_reminder_message

async def test_send():
    settings.validate()
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    chat_id = "8574864656"
    
    print(f"Mengirim pesan test ke Telegram ID: {chat_id}...")
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=build_reminder_message("Andrie"),
            parse_mode="HTML"
        )
        print("[SUCCESS] Pesan berhasil terkirim! Cek Telegram kamu sekarang.")
    except Exception as e:
        print(f"[ERROR] Gagal mengirim pesan: {e}")

if __name__ == "__main__":
    asyncio.run(test_send())
