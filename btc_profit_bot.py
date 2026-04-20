"""
BTC Profit Telegram Bot
-----------------------
Tracks profit/loss on a $10 BTC hold and sends periodic updates.

Commands:
  /start              - Start the bot
  /setentry <price>   - Set your BTC entry price (e.g., /setentry 65000)
  /setinterval <min>  - How often to send updates (e.g., /setinterval 15)
  /status             - Get current profit/loss right now
  /stop               - Stop auto-notifications
"""

import os
import logging
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ---------- Config ----------
HOLD_USD = 10.0  # Your hold balance in USD
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=usd"
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------- Price fetching ----------
async def get_btc_price() -> float:
    """Fetch current BTC price in USD from CoinGecko."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(COINGECKO_URL)
        r.raise_for_status()
        return float(r.json()["bitcoin"]["usd"])


def format_status(entry_price: float, current_price: float) -> str:
    """Build the status message."""
    btc_amount = HOLD_USD / entry_price
    current_value = btc_amount * current_price
    profit = current_value - HOLD_USD
    pct = (profit / HOLD_USD) * 100
    emoji = "🟢" if profit >= 0 else "🔴"
    sign = "+" if profit >= 0 else ""

    return (
        f"{emoji} *BTC Profit Update*\n\n"
        f"Entry price:    `${entry_price:,.2f}`\n"
        f"Current price:  `${current_price:,.2f}`\n"
        f"Hold:           `${HOLD_USD:.2f}` ({btc_amount:.8f} BTC)\n"
        f"Current value:  `${current_value:,.4f}`\n"
        f"Profit/Loss:    *{sign}${profit:,.4f}* ({sign}{pct:.2f}%)"
    )


# ---------- Command handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 BTC Profit Bot ready.\n\n"
        "1) Set your entry price:  /setentry 65000\n"
        "2) Set update interval:   /setinterval 15  (minutes)\n"
        "3) Check anytime:         /status\n"
        "4) Stop updates:          /stop"
    )


async def set_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /setentry 65000")
        return
    try:
        price = float(context.args[0])
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Example: /setentry 65000")
        return

    context.chat_data["entry_price"] = price
    await update.message.reply_text(f"✅ Entry price set to ${price:,.2f}")


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /setinterval 15  (minutes)")
        return
    try:
        minutes = int(context.args[0])
        if minutes < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Interval must be an integer ≥ 1 (minutes).")
        return

    entry = context.chat_data.get("entry_price")
    if entry is None:
        await update.message.reply_text("⚠️ Set your entry price first: /setentry 65000")
        return

    chat_id = update.effective_chat.id

    # Remove any existing job for this chat
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()

    context.job_queue.run_repeating(
        send_update,
        interval=minutes * 60,
        first=0,
        chat_id=chat_id,
        name=str(chat_id),
        data={"entry_price": entry},
    )
    await update.message.reply_text(
        f"✅ You'll receive updates every {minutes} minute(s)."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    entry = context.chat_data.get("entry_price")
    if entry is None:
        await update.message.reply_text("⚠️ Set your entry price first: /setentry 65000")
        return
    try:
        price = await get_btc_price()
    except Exception as e:
        logger.exception("Price fetch failed")
        await update.message.reply_text(f"⚠️ Could not fetch BTC price: {e}")
        return
    await update.message.reply_text(
        format_status(entry, price), parse_mode="Markdown"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if not jobs:
        await update.message.reply_text("No active updates to stop.")
        return
    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("🛑 Auto-updates stopped.")


# ---------- Scheduled job ----------
async def send_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    entry = job.data["entry_price"]
    try:
        price = await get_btc_price()
    except Exception as e:
        logger.exception("Scheduled price fetch failed")
        await context.bot.send_message(
            chat_id=job.chat_id, text=f"⚠️ Price fetch failed: {e}"
        )
        return
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=format_status(entry, price),
        parse_mode="Markdown",
    )


# ---------- Main ----------
def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise SystemExit(
            "❌ Set TELEGRAM_BOT_TOKEN env var or edit BOT_TOKEN in the code."
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setentry", set_entry))
    app.add_handler(CommandHandler("setinterval", set_interval))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
