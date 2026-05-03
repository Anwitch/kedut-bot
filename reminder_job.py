# bot/reminder_job.py
import asyncio
import sys
import os
import logging
from datetime import datetime, timezone, timedelta

# Allow sibling imports when running from bot/ directory
sys.path.insert(0, os.path.dirname(__file__))

from telegram import Bot
from telegram.error import Forbidden, TelegramError
from shared.config import settings
from shared.database.supabase_client import get_supabase

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def build_reminder_message(name: str) -> str:
    first_name = name.split()[0] if name else "Kak"
    return f"""Malam {first_name}! 🌙

Sepertinya hari ini kamu belum mencatat pengeluaran apa pun di Kedut. 
Jangan sampai ada yang terlewat ya agar laporannya tetap akurat! 📊

Yuk catat sekarang, ketik aja langsung:
👉 <code>makan malam 25rb</code>
atau
👉 <code>bensin 50.000</code>"""


async def run_reminder():
    settings.validate()
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    db = get_supabase()

    # Get today's date in WIB (UTC+7)
    tz_wib = timezone(timedelta(hours=7))
    today_wib = datetime.now(tz_wib).strftime('%Y-%m-%d')
    
    logger.info(f"Mulai proses reminder untuk tanggal: {today_wib}")

    # 1. Fetch all transactions for today to see who has been active
    try:
        tx_res = db.table("transactions").select("user_id").eq("transaction_date", today_wib).execute()
        active_user_ids = {tx["user_id"] for tx in tx_res.data}
    except Exception as e:
        logger.error(f"Gagal mengambil data transaksi: {e}")
        return

    # 2. Fetch all profiles
    try:
        prof_res = db.table("profiles").select("id, full_name, telegram_id").execute()
        profiles = prof_res.data
    except Exception as e:
        logger.error(f"Gagal mengambil data profiles: {e}")
        return

    success = 0
    failed = 0
    blocked = 0
    skipped_active = 0
    skipped_no_tele = 0

    for prof in profiles:
        user_id = prof.get("id")
        telegram_id = prof.get("telegram_id")
        full_name = prof.get("full_name") or ""

        # Skip if no telegram account linked
        if not telegram_id or str(telegram_id).strip() == "":
            skipped_no_tele += 1
            continue

        # Skip if user has already logged a transaction today
        if user_id in active_user_ids:
            skipped_active += 1
            continue

        # Send reminder
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=build_reminder_message(full_name),
                parse_mode="HTML"
            )
            logger.info(f"✅ Reminder terkirim ke {full_name} ({telegram_id})")
            success += 1
        except Forbidden:
            logger.warning(f"🚫 Diblokir oleh {full_name} ({telegram_id})")
            blocked += 1
        except TelegramError as e:
            logger.error(f"❌ Gagal kirim ke {full_name} ({telegram_id}): {e}")
            failed += 1
        except Exception as e:
            logger.error(f"⚠️ Error tak terduga untuk {full_name}: {e}")
            failed += 1

        # Sleep to avoid hitting Telegram API rate limits (30 messages per second)
        await asyncio.sleep(0.1)

    logger.info("=== Selesai Reminder ===")
    logger.info(f"✅ Berhasil: {success}")
    logger.info(f"🚫 Diblokir: {blocked}")
    logger.info(f"❌ Gagal: {failed}")
    logger.info(f"⏭️ Di-skip (Sudah aktif): {skipped_active}")
    logger.info(f"⏭️ Di-skip (Bukan user Tele): {skipped_no_tele}")


if __name__ == "__main__":
    asyncio.run(run_reminder())
