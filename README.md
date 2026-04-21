<div align="center">

# Crypto Profit Bot

**A lightweight Telegram bot that tracks profit and loss on a fixed USD hold across 20 of the most popular cryptocurrencies, with scheduled updates delivered straight to your chat.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21.6-26A5E4?logo=telegram&logoColor=white)](https://python-telegram-bot.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](#license)
[![Deploy: Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/)
[![Price data: CoinGecko](https://img.shields.io/badge/Prices-CoinGecko-8DC63F?logo=coingecko&logoColor=white)](https://www.coingecko.com/en/api)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Supported Coins](#supported-coins)
- [How It Works](#how-it-works)
- [Commands](#commands)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Overview

**Crypto Profit Bot** is a minimal, self-hosted Telegram bot written in Python. Given a fixed USD hold per coin and a user-defined entry price, it calculates live unrealised profit or loss across a personalised portfolio of cryptocurrencies and delivers combined updates on a schedule the user controls.

It is designed for personal use — a private side-project companion for anyone who wants passive visibility into small crypto positions without opening an exchange app.

## Features

- 🪙 **Track up to 20 popular coins** with tap-to-select inline keyboards
- 📈 **Per-coin P&L** plus a combined portfolio total in every update
- ⏱️ **Configurable update interval** set via chat command
- 💬 **On-demand status checks** with `/status`
- 🔓 **No API key required** — uses the public [CoinGecko](https://www.coingecko.com/en/api) endpoint
- 🔐 **Token kept in environment variables**, never hardcoded in source
- ☁️ **Deploy-ready** for Railway, Render, Fly.io, or any VPS
- 🪶 **Single-file implementation** — easy to audit and extend

## Supported Coins

| Symbol | Name          | Symbol | Name          |
| ------ | ------------- | ------ | ------------- |
| BTC    | Bitcoin       | SHIB   | Shiba Inu     |
| ETH    | Ethereum      | TRX    | TRON          |
| SOL    | Solana        | LTC    | Litecoin      |
| BNB    | BNB           | BCH    | Bitcoin Cash  |
| XRP    | XRP           | NEAR   | NEAR Protocol |
| DOGE   | Dogecoin      | ATOM   | Cosmos        |
| ADA    | Cardano       | TON    | Toncoin       |
| AVAX   | Avalanche     | APT    | Aptos         |
| LINK   | Chainlink     | ARB    | Arbitrum      |
| DOT    | Polkadot      | POL    | Polygon       |

## How It Works

For each tracked coin, the bot treats the hold as a fixed USD amount (default: `$10.00`) converted to that coin at the user's declared entry price, then values it at the current market price:

```
coin_amount   = hold_usd / entry_price
current_value = coin_amount × current_price
profit        = current_value − hold_usd
pct_change    = profit / hold_usd × 100
```

Prices are polled from CoinGecko's public `simple/price` endpoint in a single batched request per update. Scheduling is handled by [`python-telegram-bot`](https://python-telegram-bot.org/)'s built-in `JobQueue`, which runs the update job per chat on the interval the user sets.

## Commands

| Command                          | Description                                              | Example                |
| -------------------------------- | -------------------------------------------------------- | ---------------------- |
| `/start`                         | Display the welcome message and command reference        | `/start`               |
| `/coins`                         | Tap-to-select which coins to track                       | `/coins`               |
| `/setentry <SYMBOL> <price>`     | Set the entry price in USD for a coin                    | `/setentry BTC 65000`  |
| `/setinterval <min>`             | Start (or restart) scheduled updates every _n_ minutes   | `/setinterval 15`      |
| `/status`                        | Fetch the combined profit/loss on demand                 | `/status`              |
| `/portfolio`                     | Show tracked coins and their entry prices                | `/portfolio`           |
| `/stop`                          | Cancel scheduled updates for the current chat            | `/stop`                |

## Prerequisites

- **Python 3.10 or newer**
- A **Telegram bot token** from [@BotFather](https://t.me/BotFather)
- **git** (optional — required for cloning and deployment workflows)

## Quick Start

### 1. Create a Telegram bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to name your bot.
3. Copy the token BotFather provides. It looks like `1234567890:AA...` — treat it as a password.

### 2. Clone and install

```bash
git clone https://github.com/<your-username>/btc-profit-bot.git
cd btc-profit-bot
pip install -r requirements.txt
```

### 3. Run locally

**macOS / Linux**
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
python btc_profit_bot.py
```

**Windows (PowerShell)**
```powershell
$env:TELEGRAM_BOT_TOKEN="your_token_here"
python btc_profit_bot.py
```

You should see:

```
INFO - Bot is running. Press Ctrl+C to stop.
```

### 4. Use it in Telegram

Open the bot you created, then:

```
/start
/coins                    ← tap the coins you want to track
/setentry BTC 65000       ← set entry price for each
/setentry ETH 3500
/setinterval 15           ← every 15 minutes
/status
```

You'll start receiving combined portfolio updates in the chat at the configured interval.

## Configuration

| Setting             | Where               | Default    | Description                                           |
| ------------------- | ------------------- | ---------- | ----------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`| Environment var     | _required_ | Token from @BotFather                                 |
| `HOLD_USD`          | `btc_profit_bot.py` | `10.0`     | Hold amount (USD) per coin used in all P&L maths      |

To change the hold amount, edit the constant near the top of `btc_profit_bot.py`:

```python
HOLD_USD = 10.0  # change this
```

Note that `HOLD_USD` applies per coin — tracking 3 coins with a $10 hold each is equivalent to a $30 total notional portfolio.

## Deployment

The bot is a long-running polling process. It will run on any host that can keep a Python process alive. Railway is the recommended path for a zero-configuration deploy.

### Deploy to Railway

1. Push this repository to your GitHub account.
2. Sign in to [Railway](https://railway.app/) and choose **New Project → Deploy from GitHub repo**.
3. Under **Variables**, add:
   - `TELEGRAM_BOT_TOKEN` — your BotFather token
4. Under **Settings → Start Command**, set:
   ```
   python btc_profit_bot.py
   ```
5. Deploy. Monitor the **Deployments** log until you see `Bot is running.`

### Other platforms

The same pattern works for Render, Fly.io, a Raspberry Pi, or any VPS — the only requirements are Python 3.10+, the dependencies from `requirements.txt`, and the `TELEGRAM_BOT_TOKEN` environment variable.

## Project Structure

```
btc-profit-bot/
├── btc_profit_bot.py    # Main bot application
├── requirements.txt     # Python dependencies
├── README.md            # Project documentation
├── LICENSE              # MIT License
└── .gitignore           # Files excluded from version control
```

## Troubleshooting

**`ModuleNotFoundError: No module named 'telegram'`**
The package is installed in a different Python interpreter than the one running the script. Use `python -m pip install -r requirements.txt`, or on Windows with multiple Pythons: `py -3.11 -m pip install -r requirements.txt` followed by `py -3.11 btc_profit_bot.py`.

**`telegram.error.InvalidToken: The token ... was rejected by the server.`**
The token is missing, malformed, or has been revoked. A valid token has the form `<digits>:<alphanumeric>`. Generate a fresh one via `/token` in BotFather.

**Bot runs but doesn't respond in Telegram**
You must send `/start` to the bot from your Telegram account at least once so it can reply to you. Telegram bots cannot initiate conversations.

**A coin shows "price unavailable"**
CoinGecko may have briefly rate-limited the request, or the coin's ID changed upstream. The bot skips unavailable coins and continues with the rest; if it persists for a specific coin, open an issue.

**Entry prices forgotten after restart**
State is held in memory for simplicity. Resend `/setentry` for each coin after a restart, or see the roadmap item on persistence below.

## Roadmap

- [ ] SQLite persistence for tracked coins and entry prices (survive restarts)
- [ ] Threshold alerts (`/alert BTC +5%` — notify only when P&L crosses a band)
- [ ] Custom hold amount per coin (`/sethold BTC 50`)
- [ ] `/history` command with a sparkline chart
- [ ] Dockerfile and one-click deploy buttons

## Contributing

Issues and pull requests are welcome. For substantial changes, please open an issue first to discuss the proposed direction.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a pull request

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

## Acknowledgements

- [python-telegram-bot](https://python-telegram-bot.org/) — Telegram Bot API wrapper
- [CoinGecko API](https://www.coingecko.com/en/api) — free, keyless cryptocurrency price data
- [httpx](https://www.python-httpx.org/) — modern async HTTP client for Python

---

<div align="center">
<sub>Built for personal use. Not financial advice.</sub>
</div>
