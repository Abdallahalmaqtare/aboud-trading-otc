"""
Aboud Trading Bot OTC - Main v1.6 (Final Render Fix)
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
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
logger = logging.getLogger("AboudTrading")
app = Flask(__name__)

class BotState:
    ready = False
    telegram_active = False
    po_active = False
    error = None

state = BotState()

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "bot": "Aboud Trading OTC v1.6",
        "ready": state.ready,
        "telegram": state.telegram_active,
        "error": state.error,
        "time": datetime.now(timezone.utc).isoformat(),
    })

def start_bot_background():
    """وظيفة تشغيل البوت في الخلفية"""
    async def run():
        try:
            logger.info("🚀 بدء تشغيل v1.6...")
            init_db()
            
            sender = TelegramSender()
            manager = SignalManager(sender)
            
            # إعداد التيليغرام
            application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            application.bot_data["signal_manager"] = manager
            setup_admin_handlers(application)
            
            await application.initialize()
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            state.telegram_active = True
            
            # تشغيل التحليل
            if POCKET_OPTION_SSID:
                from analysis_service import analysis_service
                asyncio.create_task(analysis_service.run())
            
            state.ready = True
            logger.info("✅ v1.6 يعمل الآن!")
            await sender.send_text("🟢 <b>البوت يعمل الآن بنجاح v1.6</b>")
            
            while True: await asyncio.sleep(3600)
        except Exception as e:
            state.error = str(e)
            logger.error(f"❌ خطأ حرج: {e}")

    # إنشاء حلقة أحداث جديدة لهذا الخيط
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())

# بدء البوت فور تشغيل الملف
thread = threading.Thread(target=start_bot_background, daemon=True)
thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
