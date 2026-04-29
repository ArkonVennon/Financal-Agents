# 50 DMA Stock Alert Agent 📈

An automated Python agent that monitors your stock portfolio against the 50-day Moving Average (50 DMA) and sends you Telegram alerts when a crossover signal is detected.

## What it does

- Reads your stock holdings from a Google Sheet
- Fetches daily price data from Yahoo Finance (free, no API key needed)
- Detects BUY/SELL crossover signals based on the 50 DMA strategy
- Sends a Telegram message when a signal fires
- Sends a full weekly portfolio summary every Sunday
- Skips weekends automatically (markets closed)
- Catches up automatically if the scheduled run was missed

## Signals explained

| Signal | Condition |
|--------|-----------|
| 🟢 BUY  | Price crosses **above** the 50 DMA |
| 🔴 SELL | Price crosses **below** the 50 DMA |

## Example Telegram messages

**Daily alert:**
```
📊 50 DMA Alert — 24 Mar 2026

🟢 TATACAP.NS — BUY
   Price: 326.75 | 50 DMA: 318.20 (+2.7%)

🔴 KPITTECH.NS — SELL
   Price: 665.00 | 50 DMA: 889.38 (-25.2%)
```

**Sunday summary:**
```
📋 Weekly 50 DMA Summary — 29 Mar 2026

🟢 Above 50 DMA (10 stocks)
   TATACAP.NS      price 326.75 | +2.7% above DMA
   ...

🔴 Below 50 DMA (7 stocks)
   KPITTECH.NS     price 665.00 | -25.2% below DMA
   ...

10 above · 7 below · 17 total
```

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/50-DMA-agent.git
cd 50-DMA-agent
```

### 2. Install dependencies
```bash
pip install yfinance gspread google-auth requests pandas
```

### 3. Google Sheets setup
- Go to [Google Cloud Console](https://console.cloud.google.com)
- Create a new project
- Enable **Google Sheets API** and **Google Drive API**
- Create a **Service Account** → download the JSON key
- Share your Google Sheet with the service account email

Your sheet should have one column called `Ticker`:

| Ticker |
|--------|
| RELIANCE.NS |
| TCS.NS |
| INFY.NS |

> For Indian stocks append `.NS` (NSE) or `.BO` (BSE). US stocks are just `AAPL`, `GOOGL` etc.

### 4. Telegram bot setup
- Message `@BotFather` on Telegram → `/newbot`
- Copy the bot token
- Message your bot once, then visit:
  `https://api.telegram.org/bot<TOKEN>/getUpdates`
- Copy the `id` field inside `chat` — that's your chat ID

### 5. Configure agent.py
```python
GOOGLE_SHEET_NAME    = "My Holdings"        # your sheet name
TICKER_COLUMN        = "Ticker"             # column header
TELEGRAM_BOT_TOKEN   = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID     = "YOUR_CHAT_ID"
SERVICE_ACCOUNT_JSON = "service_account.json"
SMA_PERIOD           = 50
```

### 6. Schedule it (Mac)
```bash
EDITOR=nano crontab -e
```
Add this line (runs every weekday at 11 PM):
```bash
0 23 * * 1-5 /usr/local/bin/python3 /path/to/50-DMA-agent.py >> /path/to/agent.log 2>&1
```

## Running manually
```bash
# Normal run
python3 50-DMA-agent.py

# Test mode (sends a test Telegram message)
python3 50-DMA-agent.py test

# Force weekly summary
python3 50-DMA-agent.py weekly
```

## Project structure
```
50-DMA-agent/
├── 50-DMA-agent.py          # main agent script
├── requirements.txt        # dependencies
├── .gitignore              # keeps credentials safe
└── README.md
```

## Security
- Never commit `service_account.json` to GitHub — it is in `.gitignore`
- The Telegram bot only messages your personal chat ID
- No credentials are hardcoded — all configurable at the top of the script

## Disclaimer
This tool is for informational purposes only and does not constitute financial advice. Always do your own research before making investment decisions.
