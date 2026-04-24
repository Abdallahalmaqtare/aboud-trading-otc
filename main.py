"""
Aboud Trading Bot OTC - Main v1.5 (Fixed for Flask 3.0+)
============================================================
"""
import asyncio, logging, threading, json, time, os, sys
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from config import *
from database import *
from signal_manager import SignalManager
from telegram_sender import TelegramSender
from price_service import price_service
from admin_bot import setup_admin_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", stream=sys.stdout, force=True)
logger = logging.getLogger("AboudTrading")
app = Flask(__name__)

class BotState:
    signal_manager = None
    telegram_sender = None
    loop = None
    ready = False
    telegram_active = False
    po_active = False
    error = None

state = BotState()

@app.route("/", methods=["GET"])
def health():
    try:
        from pocket_option_service import pocket_option_service
        state.po_active = pocket_option_service._connected
    except: pass
    return jsonify({
        "bot": "Aboud Trading OTC v1.5",
        "ready": state.ready,
        "telegram": state.telegram_active,
        "pocket_option": state.po_active,
        "error": state.error,
        "time": datetime.now(timezone.utc).isoformat(),
    })

async def start_bot_logic():
    logger.info("🚀 بدء تهيئة v1.5...")
    state.loop = asyncio.get_event_loop()
    try:
        init_db()
        state.telegram_sender = TelegramSender()
        state.signal_manager = SignalManager(state.telegram_sender)
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        application.bot_data["signal_manager"] = state.signal_manager
        setup_admin_handlers(application)
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        state.telegram_active = True
        
        if POCKET_OPTION_SSID:
            from analysis_service import analysis_service
            asyncio.create_task(analysis_service.run())
        
        state.ready = True
        logger.info("✅ v1.5 جاهز!")
        await state.telegram_sender.send_text("🟢 <b>تم تشغيل البوت بنجاح v1.5</b>")
        while True: await asyncio.sleep(3600)
    except Exception as e:
        state.error = str(e)
        logger.error(f"❌ خطأ: {e}")

def main():
    # بدء خيط البوت مباشرة عند تشغيل main
    threading.Thread(target=lambda: asyncio.run(start_bot_logic()), daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
