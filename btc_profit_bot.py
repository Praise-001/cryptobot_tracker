"""
Crypto Profit Telegram Bot
--------------------------
Track profit/loss on multiple popular coins with per-coin intervals.

Commands:
  /start   - Show help
  /coins   - Pick a coin to track (interactive buttons)
  /status  - See all your tracked positions
  /sethold - Set your USD hold amount
  /stop    - Stop notifications
  /cancel  - Cancel current operation
"""

import os
import time
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ---------- Config ----------
COINS = {
    "BTC":  {"name": "Bitcoin",   "emoji": "₿",  "binance": "BTCUSDT"},
    "ETH":  {"name": "Ethereum",  "emoji": "Ξ",  "binance": "ETHUSDT"},
    "SOL":  {"name": "Solana",    "emoji": "◎",  "binance": "SOLUSDT"},
    "BNB":  {"name": "BNB",       "emoji": "🟡", "binance": "BNBUSDT"},
    "XRP":  {"name": "XRP",       "emoji": "💧", "binance": "XRPUSDT"},
    "DOGE": {"name": "Dogecoin",  "emoji": "🐕", "binance": "DOGEUSDT"},
    "ADA":  {"name": "Cardano",   "emoji": "🔵", "binance": "ADAUSDT"},
    "AVAX": {"name": "Avalanche", "emoji": "🔺", "binance": "AVAXUSDT"},
    "SHIB": {"name": "Shiba Inu", "emoji": "🐶", "binance": "SHIBUSDT"},
    "PEPE": {"name": "Pepe",      "emoji": "🐸", "binance": "PEPEUSDT"},
    "WIF":  {"name": "dogwifhat", "emoji": "🎩", "binance": "WIFUSDT"},
    "BONK": {"name": "Bonk",      "emoji": "🔨", "binance": "BONKUSDT"},
    "SUI":  {"name": "Sui",       "emoji": "💎", "binance": "SUIUSDT"},
    "TON":  {"name": "Toncoin",   "emoji": "💎", "binance": "TONUSDT"},
}
DEFAULT_HOLD_USD = 10.0
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ConversationHandler states
CHOOSING_COIN, ENTERING_PRICE, CHOOSING_INTERVAL = range(3)
SETHOLD_MENU, ENTERING_CUSTOM_HOLD = range(3, 5)


# ---------- Helpers ----------
_price_cache: dict[str, tuple[float, float]] = {}  # symbol → (price, timestamp)


async def get_coin_price(symbol: str) -> float:
    cached = _price_cache.get(symbol)
    if cached and time.time() - cached[1] < 60:
        return cached[0]
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(BINANCE_URL, params={"symbol": COINS[symbol]["binance"]})
        r.raise_for_status()
        price = float(r.json()["price"])
    _price_cache[symbol] = (price, time.time())
    return price


def format_status(symbol: str, entry_price: float, current_price: float, hold_usd: float) -> str:
    coin = COINS[symbol]
    amount = hold_usd / entry_price
    current_value = amount * current_price
    profit = current_value - hold_usd
    pct = (profit / hold_usd) * 100
    emoji = "🟢" if profit >= 0 else "🔴"
    sign = "+" if profit >= 0 else ""
    return (
        f"{emoji} *{coin['emoji']} {coin['name']} ({symbol})*\n"
        f"Entry: `${entry_price:,.4f}` | Now: `${current_price:,.4f}`\n"
        f"Hold: `${hold_usd:.2f}` → `${current_value:.4f}`\n"
        f"P/L: *{sign}${profit:,.4f}* ({sign}{pct:.2f}%)"
    )


def coin_keyboard() -> InlineKeyboardMarkup:
    symbols = list(COINS.keys())
    rows = []
    for i in range(0, len(symbols), 2):
        row = [
            InlineKeyboardButton(
                f"{COINS[sym]['emoji']} {sym}",
                callback_data=f"coin_{sym}",
            )
            for sym in symbols[i:i + 2]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def interval_keyboard() -> InlineKeyboardMarkup:
    options = [("1 min", 1), ("5 min", 5), ("15 min", 15), ("30 min", 30), ("1 hour", 60)]
    rows = []
    for i in range(0, len(options), 2):
        row = [
            InlineKeyboardButton(label, callback_data=f"interval_{mins}")
            for label, mins in options[i:i + 2]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def hold_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("$10", callback_data="hold_10"),
            InlineKeyboardButton("$50", callback_data="hold_50"),
            InlineKeyboardButton("$100", callback_data="hold_100"),
        ],
        [
            InlineKeyboardButton("$500", callback_data="hold_500"),
            InlineKeyboardButton("✏️ Custom", callback_data="hold_custom"),
        ],
    ])


def cancel_coin_job(context: ContextTypes.DEFAULT_TYPE, chat_id: int, symbol: str) -> None:
    for job in context.job_queue.get_jobs_by_name(f"{chat_id}_{symbol}"):
        job.schedule_removal()


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Crypto Profit Bot*\n\n"
        "Track your P/L across multiple coins with automatic updates.\n\n"
        "• /coins — Pick a coin to track\n"
        "• /status — See all your positions\n"
        "• /sethold — Set your USD hold amount\n"
        "• /stop — Stop notifications\n"
        "• /cancel — Cancel current operation",
        parse_mode="Markdown",
    )


# ---------- /coins ConversationHandler ----------
async def coins_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📊 *Pick a coin to track:*",
        reply_markup=coin_keyboard(),
        parse_mode="Markdown",
    )
    return CHOOSING_COIN


async def coin_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    symbol = query.data.split("_", 1)[1]
    context.chat_data["pending_coin"] = symbol
    coin = COINS[symbol]
    await query.edit_message_text(
        f"💰 Enter your *{coin['emoji']} {symbol}* entry price in USD:",
        parse_mode="Markdown",
    )
    return ENTERING_PRICE


async def price_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = float(update.message.text.replace(",", "").replace("$", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Please enter a positive number:")
        return ENTERING_PRICE

    context.chat_data["pending_price"] = price
    symbol = context.chat_data["pending_coin"]
    await update.message.reply_text(
        f"⏱ How often should I send *{symbol}* updates?",
        reply_markup=interval_keyboard(),
        parse_mode="Markdown",
    )
    return CHOOSING_INTERVAL


async def interval_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    minutes = int(query.data.split("_", 1)[1])
    symbol = context.chat_data.pop("pending_coin")
    entry_price = context.chat_data.pop("pending_price")
    coin = COINS[symbol]
    chat_id = query.message.chat_id
    hold_usd = context.chat_data.get("hold_usd", DEFAULT_HOLD_USD)

    positions = context.chat_data.setdefault("positions", {})
    positions[symbol] = {"entry_price": entry_price, "interval": minutes}

    cancel_coin_job(context, chat_id, symbol)
    context.job_queue.run_repeating(
        send_update,
        interval=minutes * 60,
        first=0,
        chat_id=chat_id,
        name=f"{chat_id}_{symbol}",
        data={"symbol": symbol, "entry_price": entry_price},
    )

    interval_label = f"{minutes} min" if minutes < 60 else "1 hour"
    await query.edit_message_text(
        f"✅ Tracking *{coin['emoji']} {symbol}* at `${entry_price:,.4f}`\n"
        f"Updates every *{interval_label}* | Hold: *${hold_usd:.2f}*",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ---------- /sethold ConversationHandler ----------
async def sethold_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    hold = context.chat_data.get("hold_usd", DEFAULT_HOLD_USD)
    await update.message.reply_text(
        f"💵 Current hold: *${hold:.2f}*\nChoose a new amount:",
        reply_markup=hold_keyboard(),
        parse_mode="Markdown",
    )
    return SETHOLD_MENU


async def hold_preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    amount = float(query.data.split("_", 1)[1])
    context.chat_data["hold_usd"] = amount
    await query.edit_message_text(f"✅ Hold amount set to *${amount:.2f}*", parse_mode="Markdown")
    return ConversationHandler.END


async def hold_custom_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ Enter your custom hold amount in USD:")
    return ENTERING_CUSTOM_HOLD


async def custom_hold_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.replace(",", "").replace("$", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Enter a positive number:")
        return ENTERING_CUSTOM_HOLD
    context.chat_data["hold_usd"] = amount
    await update.message.reply_text(f"✅ Hold amount set to *${amount:.2f}*", parse_mode="Markdown")
    return ConversationHandler.END


# ---------- Shared cancel fallback ----------
async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.chat_data.pop("pending_coin", None)
    context.chat_data.pop("pending_price", None)
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


# ---------- /status ----------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    positions = context.chat_data.get("positions", {})
    if not positions:
        await update.message.reply_text("No coins tracked yet. Use /coins to start.")
        return

    hold_usd = context.chat_data.get("hold_usd", DEFAULT_HOLD_USD)
    for symbol, pos in positions.items():
        try:
            price = await get_coin_price(symbol)
        except Exception as e:
            await update.message.reply_text(f"⚠️ Could not fetch {symbol} price: {e}")
            continue
        text = format_status(symbol, pos["entry_price"], price, hold_usd)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"❌ Untrack {symbol}", callback_data=f"untrack_{symbol}")
        ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ---------- /stop ----------
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    positions = context.chat_data.get("positions", {})
    if not positions:
        await update.message.reply_text("No active notifications.")
        return

    buttons = [[InlineKeyboardButton("🛑 Stop All", callback_data="stop_all")]]
    for symbol in positions:
        coin = COINS[symbol]
        buttons.append([
            InlineKeyboardButton(f"Stop {coin['emoji']} {symbol}", callback_data=f"stop_{symbol}")
        ])
    await update.message.reply_text(
        "Which notifications would you like to stop?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------- Callback handlers ----------
async def untrack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    symbol = query.data.split("_", 1)[1]
    positions = context.chat_data.get("positions", {})
    if symbol not in positions:
        await query.edit_message_text(f"{symbol} is not being tracked.")
        return
    cancel_coin_job(context, query.message.chat_id, symbol)
    del positions[symbol]
    coin = COINS[symbol]
    await query.edit_message_text(
        f"✅ Stopped tracking *{coin['emoji']} {symbol}*", parse_mode="Markdown"
    )


async def stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    positions = context.chat_data.get("positions", {})

    if query.data == "stop_all":
        for symbol in list(positions.keys()):
            cancel_coin_job(context, chat_id, symbol)
        positions.clear()
        await query.edit_message_text("🛑 All notifications stopped.")
    else:
        symbol = query.data.split("_", 1)[1]
        cancel_coin_job(context, chat_id, symbol)
        positions.pop(symbol, None)
        coin = COINS[symbol]
        await query.edit_message_text(
            f"🛑 Stopped *{coin['emoji']} {symbol}* notifications.", parse_mode="Markdown"
        )


# ---------- Scheduled job ----------
async def send_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    symbol = job.data["symbol"]
    entry_price = job.data["entry_price"]
    hold_usd = context.chat_data.get("hold_usd", DEFAULT_HOLD_USD)
    try:
        price = await get_coin_price(symbol)
    except Exception as e:
        logger.exception("Scheduled price fetch failed for %s", symbol)
        await context.bot.send_message(
            chat_id=job.chat_id, text=f"⚠️ Could not fetch {symbol} price: {e}"
        )
        return
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=format_status(symbol, entry_price, price, hold_usd),
        parse_mode="Markdown",
    )


# ---------- Error handler ----------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception", exc_info=context.error)


# ---------- Main ----------
def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise SystemExit("❌ Set TELEGRAM_BOT_TOKEN env var or edit BOT_TOKEN in the code.")

    app = Application.builder().token(BOT_TOKEN).build()

    common_fallbacks = [
        CommandHandler("cancel", cancel_conv),
        CommandHandler("start", start),
        CommandHandler("status", status),
        CommandHandler("stop", stop_command),
    ]

    coins_conv = ConversationHandler(
        entry_points=[CommandHandler("coins", coins_start)],
        states={
            CHOOSING_COIN: [CallbackQueryHandler(coin_chosen, pattern="^coin_")],
            ENTERING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_entered)],
            CHOOSING_INTERVAL: [CallbackQueryHandler(interval_chosen, pattern="^interval_")],
        },
        fallbacks=common_fallbacks + [CommandHandler("sethold", sethold_start)],
        allow_reentry=True,
    )

    hold_conv = ConversationHandler(
        entry_points=[CommandHandler("sethold", sethold_start)],
        states={
            SETHOLD_MENU: [
                CallbackQueryHandler(hold_preset_chosen, pattern=r"^hold_\d"),
                CallbackQueryHandler(hold_custom_prompt, pattern="^hold_custom$"),
            ],
            ENTERING_CUSTOM_HOLD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_hold_entered)
            ],
        },
        fallbacks=common_fallbacks + [CommandHandler("coins", coins_start)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(coins_conv)
    app.add_handler(hold_conv)
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(untrack_callback, pattern="^untrack_"))
    app.add_handler(CallbackQueryHandler(stop_callback, pattern="^stop_"))
    app.add_error_handler(error_handler)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
