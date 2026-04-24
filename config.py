"""
Aboud Trading Bot OTC - Configuration v1.1
==========================================
نسخة معدّلة للعمل على أزواج OTC في Pocket Option
"""
import os
from datetime import timezone, timedelta

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ADMIN_USER_IDS = [int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip() and x.strip().isdigit()]

# ─── أزواج OTC في Pocket Option ───────────────────────────────────────────────
TRADING_PAIRS = ["EURUSD_otc", "GBPUSD_otc"]
PAIR_DISPLAY_NAMES = {
    "EURUSD_otc": "EUR/USD OTC",
    "GBPUSD_otc": "GBP/USD OTC",
}

# Trading Settings
TRADE_DURATION_MINUTES = 15
SIGNAL_COOLDOWN_MINUTES = 20
MAX_PENDING_TRADES = 5

# NO MORE CONFIRMATION DELAY
SIGNAL_CONFIRM_MIN_SECONDS = 0
SIGNAL_CONFIRM_MAX_SECONDS = 0
SIGNAL_CONFIRM_CHECK_INTERVAL = 15
SIGNAL_CONFIRM_DELAY_SECONDS = 0

# ─── إعدادات المؤشرات الفنية ──────────────────────────────────────────────────
EMA_FAST = 9
EMA_MID = 21
EMA_SLOW = 50
EMA_TREND = 200
RSI_PERIOD = 14
RSI_CALL_MIN = 55
RSI_PUT_MAX = 45
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 2.0
ADX_PERIOD = 14
ADX_MIN_THRESHOLD = 25
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# الحد الأدنى للإشارة
MIN_SIGNAL_SCORE = 6
STRONG_SIGNAL_SCORE = 8

# 24/7 - OTC متاح على مدار الساعة
TRADING_START_HOUR_UTC = 0
TRADING_END_HOUR_UTC = 24

BOT_UTC_OFFSET = int(os.getenv("BOT_UTC_OFFSET", "3"))
BOT_TIMEZONE = timezone(timedelta(hours=BOT_UTC_OFFSET))

DATABASE_PATH = os.getenv("DATABASE_PATH", "aboud_otc_trading.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "aboud_trading_secret_2024")
WEBHOOK_PORT = int(os.environ.get("PORT", "10000"))

DAILY_REPORT_HOUR_UTC = int(os.getenv("DAILY_REPORT_HOUR", "18"))
DAILY_REPORT_MINUTE = 0

RESULT_CANDLE_LOOKBACK_DAYS = int(os.getenv("RESULT_CANDLE_LOOKBACK_DAYS", "5"))
RESULT_FETCH_RETRY_SECONDS = int(os.getenv("RESULT_FETCH_RETRY_SECONDS", "6"))
RESULT_MAX_WAIT_AFTER_EXPIRY_SECONDS = int(os.getenv("RESULT_MAX_WAIT_AFTER_EXPIRY_SECONDS", "90"))
RESULT_CANDLE_BUFFER_SECONDS = int(os.getenv("RESULT_CANDLE_BUFFER_SECONDS", "4"))

SIGNALS_ENABLED = os.getenv("SIGNALS_ENABLED", "true").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ─── إعدادات Pocket Option API ────────────────────────────────────────────────
POCKET_OPTION_SSID = os.getenv("POCKET_OPTION_SSID", "")
POCKET_OPTION_IS_DEMO = os.getenv("POCKET_OPTION_IS_DEMO", "1") == "1"
POCKET_OPTION_CONNECT_TIMEOUT = int(os.getenv("POCKET_OPTION_CONNECT_TIMEOUT", "30"))
