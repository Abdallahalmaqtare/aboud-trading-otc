import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv("ADMIN_USER_IDS", "").split(",") if id.strip()]

# Pocket Option Configuration
POCKET_OPTION_SSID = os.getenv("POCKET_OPTION_SSID")
POCKET_OPTION_IS_DEMO = os.getenv("POCKET_OPTION_IS_DEMO", "1") == "1"

# Webhook Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "aboud_trading_secret_2024")
WEBHOOK_PORT = int(os.environ.get("PORT", 10000))

# Trading Configuration
TRADING_PAIRS = ["EURUSD_otc", "GBPUSD_otc"]
PAIR_DISPLAY_NAMES = {
    "EURUSD_otc": "EUR/USD OTC",
    "GBPUSD_otc": "GBP/USD OTC"
}
MIN_SIGNAL_SCORE = 6
BOT_UTC_OFFSET = int(os.getenv("BOT_UTC_OFFSET", "3"))

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Report Configuration
DAILY_REPORT_HOUR_UTC = int(os.getenv("DAILY_REPORT_HOUR", "18"))
DAILY_REPORT_MINUTE = 0

DEBUG = os.getenv("DEBUG", "False").lower() == "true"
