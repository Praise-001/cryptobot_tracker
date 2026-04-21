"""
Crypto Profit Telegram Bot (multi-coin)
---------------------------------------
Tracks profit/loss on a fixed USD hold across multiple cryptocurrencies.

Commands:
  /start                        - Welcome & command reference
  /coins                        - Tap-to-select which coins to track
  /setentry <SYMBOL> <price>    - Set entry price for a coin (e.g. /setentry BTC 65000)
  /setinterval <minutes>        - Start scheduled updates
  /status                       - Combined profit/loss snapshot right now
  /portfolio                    - Show tracked coins and their entry prices
  /stop                         - Stop scheduled updates
"""

import os
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------- Config ----------
HOLD_USD = 10.0  # Hold balance per coin (USD)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Curated list of popular coins: {symbol: (coingecko_id, display_name)}
SUPPORTED_COINS = {
    "BTC":   ("bitcoin",          "Bitcoin"),
    "ETH":   ("ethereum",         "Ethereum"),
    "SOL":   ("solana",           "Solana"),
    "BNB":   ("binancecoin",      "BNB"),
    "XRP":   ("ripple",           "XRP"),
    "DOGE":  ("dogecoin",         "Dogecoin"),
    "ADA":   ("cardano",          "Cardano"),
    "AVAX":  ("avalanche-2",      "Avalanche"),
    "LINK":  ("chainlink",        "Chainlink"),
    "DOT":   ("polkadot",         "Polkadot"),
    "POL":   ("polygon-ecosystem-token", "Polygon"),
    "SHIB":  ("shiba-inu",        "Shiba Inu"),
    "TRX":   ("tron",             "TRON"),
    "LTC":   ("litecoin",         "Litecoin"),
    "BCH":   ("bitcoin-cash",     "Bitcoin Cash"),
    "NEAR":  ("near",             "NEAR Protocol"),
    "ATOM":  ("cosmos",           "Cosmos"),
    "TON":   ("the-open-network", "Toncoin"),
    "APT":   ("aptos",            "Aptos"),
    "ARB":   ("arbitrum",         "Arbitrum"),
}

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------- Price fetching ----------
async def get_prices(symbols: list) -> dict:
    """Fetch current USD prices for the given symbols. Returns {SYMBOL: price}."""
    if not symbols:
        return {}
    ids = [SUPPORTED_COINS[s][0] for s in symbols if s in SUPPORTED_COINS]
    params = {"ids": ",".join(ids), "vs_currencies": "usd"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(COINGECKO_URL, params=params)
        r.raise_for_status()
        data = r.json()

    result = {}
    for symbol in symbols:
        coin_id = SUPPORTED_COINS[symbol][0]
        if coin_id in data and "usd" in data[coin_id]:
            result[symbol] = float(data[coin_id]["usd"])
    return result


# ---------- Formatting ----------
def format_status(tracked, entries, prices) -> str:
    """Build the combined status message across all tracked coins."""
    lines = ["*📊 Portfolio Update*\n"]
    total_profit = 0.0
    total_hold = 0.0
    valid_rows = 0

    for symbol in sorted(tracked):
        if symbol not in prices:
            lines.append(f"⚠️ *{symbol}* — price unavailable")
            continue
        entry = entries.get(symbol)
        current = prices[symbol]

        if entry is None:
            lines.append(
                f"• *{symbol}* `${current:,.4f}`  _(no entry — /setentry {symbol} <price>)_"
            )
            continue

        coin_amount = HOLD_USD / entry
        current_value = coin_amount * current
        profit = current_value - HOLD_USD
        pct = (profit / HOLD_USD) * 100
        emoji = "🟢" if profit >= 0 else "🔴"
        sign = "+" if profit >= 0 else ""
        total_profit += profit
        total_hold += HOLD_USD
        valid_rows += 1

        lines.append(
            f"{emoji} *{symbol}*  `${current:,.4f}`\n"
            f"    entry `${entry:,.4f}` → P/L *{sign}${profit:,.4f}* ({sign}{pct:.2f}%)"
        )

    if valid_rows > 1:
        total_pct = (total_profit / total_hold) * 100 if total_hold else 0
        sign = "+" if total_profit >= 0 else ""
        lines.append(
            f"\n*Total* across {valid_rows} coins: "
            f"*{sign}${total_profit:,.4f}* ({sign}{total_pct:.2f}%)"
        )

    return "\n".join(lines)


# ---------- Keyboard ----------
def build_coins_keyboard(selected) -> InlineKeyboardMarkup:
    """Build 2-column inline keyboard of coins with checkmarks on selected ones."""
    buttons = []
    symbols = list(SUPPORTED_COINS.keys())
    for i in range(0, len(symbols), 2):
        row = []
        for symbol in symbols[i:i + 2]:
            mark = "✅" if symbol in selected else "⬜"
            row.append(InlineKeyboardButton(
                f"{mark} {symbol}", callback_data=f"toggle:{symbol}"
            ))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Done ✓", callback_data="done")])
    return InlineKeyboardMarkup(buttons)


# ---------- Command handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Crypto Profit Bot*\n\n"
        "Track P/L on a $10 hold per coin across the top cryptocurrencies.\n\n"
        "*Get started:*\n"
        "1. /coins — pick coins to track\n"
        "2. `/setentry BTC 65000` — set entry price for each\n"
        "3. `/setinterval 15` — start scheduled updates\n"
        "4. /status — check anytime\n\n"
        "*Other:*\n"
        "• /portfolio — review your tracked coins\n"
        "• /stop — cancel scheduled updates",
        parse_mode="Markdown",
    )


async def coins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    selected = context.chat_data.setdefault("tracked", set())
    await update.message.reply_text(
        "Tap to toggle coins. Press *Done* when finished.",
        reply_markup=build_coins_keyboard(selected),
        parse_mode="Markdown",
    )


async def on_coin_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    selected = context.chat_data.setdefault("tracked", set())

    if data == "done":
        if not selected:
            await query.edit_message_text("No coins selected. Send /coins to try again.")
            return
        coin_list = ", ".join(sorted(selected))
        await query.edit_message_text(
            f"✅ Tracking: *{coin_list}*\n\n"
            f"Next: set an entry price for each, e.g. `/setentry BTC 65000`",
            parse_mode="Markdown",
        )
        return

    if data.startswith("toggle:"):
        symbol = data.split(":", 1)[1]
        if symbol in selected:
            selected.remove(symbol)
        else:
            selected.add(symbol)
        await query.edit_message_reply_markup(
            reply_markup=build_coins_keyboard(selected)
        )


async def set_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 2:
        await update.message.reply_text(
            "Usage: `/setentry SYMBOL PRICE`\nExample: `/setentry BTC 65000`",
            parse_mode="Markdown",
        )
        return

    symbol = context.args[0].upper()
    if symbol not in SUPPORTED_COINS:
        supported = ", ".join(SUPPORTED_COINS.keys())
        await update.message.reply_text(
            f"❌ `{symbol}` not supported.\n\nAvailable: {supported}",
            parse_mode="Markdown",
        )
        return

    try:
        price = float(context.args[1])
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid price. Example: `/setentry BTC 65000`",
            parse_mode="Markdown",
        )
        return

    entries = context.chat_data.setdefault("entries", {})
    entries[symbol] = price

    # Auto-add to tracked list if not already there
    tracked = context.chat_data.setdefault("tracked", set())
    tracked.add(symbol)

    await update.message.reply_text(
        f"✅ {symbol} entry price set to ${price:,.4f}"
    )


async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tracked = context.chat_data.get("tracked", set())
    entries = context.chat_data.get("entries", {})

    if not tracked:
        await update.message.reply_text("No coins tracked yet. Send /coins to pick some.")
        return

    lines = ["*Your portfolio:*\n"]
    for symbol in sorted(tracked):
        entry = entries.get(symbol)
        if entry is None:
            lines.append(f"• *{symbol}* — no entry set")
        else:
            lines.append(f"• *{symbol}* — entry `${entry:,.4f}`")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


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

    tracked = context.chat_data.get("tracked", set())
    if not tracked:
        await update.message.reply_text("⚠️ Pick coins first with /coins.")
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
        data={"chat_data_ref": context.chat_data},
    )
    await update.message.reply_text(f"✅ Updates every {minutes} minute(s).")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tracked = context.chat_data.get("tracked", set())
    entries = context.chat_data.get("entries", {})

    if not tracked:
        await update.message.reply_text("No coins tracked. Send /coins to pick some.")
        return

    try:
        prices = await get_prices(list(tracked))
    except Exception as e:
        logger.exception("Price fetch failed")
        await update.message.reply_text(f"⚠️ Could not fetch prices: {e}")
        return

    await update.message.reply_text(
        format_status(tracked, entries, prices), parse_mode="Markdown"
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
    chat_data = job.data["chat_data_ref"]
    tracked = chat_data.get("tracked", set())
    entries = chat_data.get("entries", {})

    if not tracked:
        return

    try:
        prices = await get_prices(list(tracked))
    except Exception as e:
        logger.exception("Scheduled price fetch failed")
        await context.bot.send_message(
            chat_id=job.chat_id, text=f"⚠️ Price fetch failed: {e}"
        )
        return

    await context.bot.send_message(
        chat_id=job.chat_id,
        text=format_status(tracked, entries, prices),
        parse_mode="Markdown",
    )


# ---------- Main ----------
def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "❌ TELEGRAM_BOT_TOKEN environment variable is not set."
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("coins", coins))
    app.add_handler(CommandHandler("setentry", set_entry))
    app.add_handler(CommandHandler("setinterval", set_interval))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("portfolio", portfolio))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(on_coin_button))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
