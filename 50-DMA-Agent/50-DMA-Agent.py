import os
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv

# ── Load credentials from .env file (never hardcode these) ──────────────
load_dotenv()

GOOGLE_SHEET_NAME    = os.getenv("GOOGLE_SHEET_NAME", "My Holdings")
TICKER_COLUMN        = "Ticker"
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID")
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON", "service_account.json")
SMA_PERIOD           = 50
ALLOWED_CHAT_IDS     = {int(TELEGRAM_CHAT_ID)}
LAST_RUN_FILE        = os.path.join(os.path.dirname(__file__), "last_run.txt")
# ────────────────────────────────────────────────────────────────────────


def get_tickers_from_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=scopes)
    gc      = gspread.authorize(creds)
    sheet   = gc.open(GOOGLE_SHEET_NAME).sheet1
    records = sheet.get_all_records()
    return [row[TICKER_COLUMN].strip() for row in records if row.get(TICKER_COLUMN)]


def compute_signal(ticker: str):
    """
    Returns crossover signal ('BUY', 'SELL', or None) plus price/sma/pct_diff.
    Always uses the last completed trading day — safe to run anytime.
    """
    df = yf.download(ticker, period=f"{SMA_PERIOD + 10}d", interval="1d",
                     progress=False, auto_adjust=True)
    df = df[df.index.dayofweek < 5]  # remove weekends
    df = df.dropna()

    if df is None or len(df) < SMA_PERIOD + 2:
        return None, None, None, None

    closes = df["Close"].squeeze()
    sma50  = closes.rolling(SMA_PERIOD).mean()

    price_today = float(closes.iloc[-1])
    price_prev  = float(closes.iloc[-2])
    sma_today   = float(sma50.iloc[-1])
    sma_prev    = float(sma50.iloc[-2])
    pct_diff    = ((price_today / sma_today) - 1) * 100

    if pd.isna(price_today) or pd.isna(sma_today):
        return None, None, None, None

    if price_prev < sma_prev and price_today >= sma_today:
        return "BUY", price_today, sma_today, pct_diff
    elif price_prev > sma_prev and price_today <= sma_today:
        return "SELL", price_today, sma_today, pct_diff
    return None, price_today, sma_today, pct_diff


def send_telegram(message: str):
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    resp    = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def get_last_run_date():
    try:
        with open(LAST_RUN_FILE, "r") as f:
            return date.fromisoformat(f.read().strip())
    except:
        return None


def save_last_run_date():
    with open(LAST_RUN_FILE, "w") as f:
        f.write(date.today().isoformat())


def run_daily():
    """Runs every weekday — sends Telegram message whether or not signals fire."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Running daily 50 DMA check...")

    tickers = get_tickers_from_sheet()
    print(f"  Found {len(tickers)} tickers: {tickers}")

    signals = []
    for ticker in tickers:
        signal, price, sma, pct = compute_signal(ticker)
        if signal:
            signals.append((ticker, signal, price, sma, pct))
            print(f"  {ticker}: {signal} | price={price:.2f}, 50DMA={sma:.2f} ({pct:+.1f}%)")
        else:
            print(f"  {ticker}: no signal | price={price:.2f}, 50DMA={sma:.2f} ({pct:+.1f}%)")

    if not signals:
        message = (
            f"📊 *50 DMA Daily Report* — {datetime.now().strftime('%d %b %Y')}\n\n"
            f"✅ All clear — no crossovers today across {len(tickers)} stocks."
        )
        send_telegram(message)
        print("  No signals. Sent all-clear message.")
        return

    lines = [f"📊 *50 DMA Alert* — {datetime.now().strftime('%d %b %Y')}\n"]
    for ticker, signal, price, sma, pct in signals:
        emoji = "🟢" if signal == "BUY" else "🔴"
        lines.append(
            f"{emoji} *{ticker}* — *{signal}*\n"
            f"   Price: `{price:.2f}` | 50 DMA: `{sma:.2f}` ({pct:+.1f}%)"
        )

    send_telegram("\n".join(lines))
    print(f"  Telegram alert sent for {len(signals)} ticker(s).")


def run_weekly():
    """Runs every Sunday — sends full portfolio summary vs 50 DMA."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Running weekly 50 DMA summary...")

    tickers = get_tickers_from_sheet()
    above, below, errors = [], [], []

    for ticker in tickers:
        _, price, sma, pct = compute_signal(ticker)
        if price is None:
            errors.append(ticker)
        elif price >= sma:
            above.append((ticker, price, sma, pct))
        else:
            below.append((ticker, price, sma, pct))

    above.sort(key=lambda x: x[3], reverse=True)
    below.sort(key=lambda x: x[3])

    lines = [f"📋 *Weekly 50 DMA Summary* — {datetime.now().strftime('%d %b %Y')}\n"]

    lines.append(f"🟢 *Above 50 DMA ({len(above)} stocks)*")
    for ticker, price, sma, pct in above:
        lines.append(f"   `{ticker:<15}` price `{price:.2f}` | {pct:+.1f}% above DMA")
    if not above:
        lines.append("   None")

    lines.append(f"\n🔴 *Below 50 DMA ({len(below)} stocks)*")
    for ticker, price, sma, pct in below:
        lines.append(f"   `{ticker:<15}` price `{price:.2f}` | {pct:+.1f}% below DMA")
    if not below:
        lines.append("   None")

    if errors:
        lines.append(f"\n⚠️ *Could not fetch data*: {', '.join(errors)}")

    lines.append(f"\n_{len(above)} above · {len(below)} below · {len(tickers)} total_")

    send_telegram("\n".join(lines))
    print(f"  Weekly summary sent. {len(above)} above, {len(below)} below.")


def run_test():
    """Test mode — confirms Telegram and Google Sheets are connected."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Running test mode...")
    tickers = get_tickers_from_sheet()
    message = (
        f"✅ *Test Successful* — {datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
        f"Google Sheets: connected ✓\n"
        f"Tickers found: {len(tickers)}\n"
        f"Telegram: connected ✓"
    )
    send_telegram(message)
    print("  Test message sent.")


if __name__ == "__main__":
    import sys
    today = datetime.now().weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_test()
    elif today == 5:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Saturday — market closed. Skipping.")
    elif today == 6:
        run_weekly()
    else:
        last_run = get_last_run_date()
        if last_run == date.today():
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Already ran today. Skipping.")
        else:
            run_daily()
            save_last_run_date()
