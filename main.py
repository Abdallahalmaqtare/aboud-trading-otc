"""
Aboud Trading Bot OTC - Main v1.9 (Fixed Connection Attribute)
============================================================
"""
import asyncio, logging, threading, json, time, os, sys
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from telegram.ext import Application
from config import *
from database import *
from signal_manager import SignalManager
from telegram_sender import TelegramSender
from admin_bot import setup_admin_handlers

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", stream=sys.stdout, force=True)
logger = logging.getLogger("AboudTrading")
app = Flask(__name__)

class BotState:
    ready = False
    telegram_active = False
    error = None

state = BotState()

@app.route("/", methods=["GET"])
def health():
    po_status = False
    try:
        from pocket_option_service import pocket_option_service
        # تم التصحيح هنا لاستخدام المتغير الصحيح
        po_status = getattr(pocket_option_service, "_authenticated", False)
    except: pass
    return jsonify({
        "bot": "Aboud Trading OTC v1.9",
        "ready": state.ready,
        "telegram": state.telegram_active,
        "pocket_option": po_status,
        "error": state.error,
        "time": datetime.now(timezone.utc).isoformat(),
    })

def start_bot_background():
    async def run():
        try:
            logger.info("🚀 بدء تشغيل v1.9...")
            init_db()
            
            sender = TelegramSender()
            manager = SignalManager(sender)
            
            application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            application.bot_data["signal_manager"] = manager
            setup_admin_handlers(application)
            
            await application.initialize()
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            state.telegram_active = True
            
            if POCKET_OPTION_SSID:
                from pocket_option_service import pocket_option_service
                await pocket_option_service.connect()
                
                from analysis_service import analysis_service
                asyncio.create_task(analysis_service.run())
            
            state.ready = True
            logger.info("✅ v1.9 جاهز!")
            await sender.send_text("🟢 <b>تم تشغيل البوت بنجاح v1.9</b>")
            
            while True: await asyncio.sleep(3600)
        except Exception as e:
            state.error = str(e)
            logger.error(f"❌ خطأ حرج: {e}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())

thread = threading.Thread(target=start_bot_background, daemon=True)
thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
