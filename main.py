"""
Aboud Trading Bot OTC - Main v1.7 (Final Connection Fix)
============================================================
نسخة مطورة تدعم المصادقة المرنة وإعادة الاتصال التلقائي وتوافق Flask 3.0+
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
    po_active = False
    error = None

state = BotState()

@app.route("/", methods=["GET"])
def health():
    try:
        from pocket_option_service import pocket_option_service
        state.po_active = pocket_option_service._authenticated
    except: pass
    return jsonify({
        "bot": "Aboud Trading OTC v1.7",
        "ready": state.ready,
        "telegram": state.telegram_active,
        "pocket_option": state.po_active,
        "error": state.error,
        "time": datetime.now(timezone.utc).isoformat(),
    })

def start_bot_background():
    async def run():
        try:
            logger.info("🚀 بدء تشغيل v1.7...")
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
                # محاولة الاتصال الأولى بـ Pocket Option
                from pocket_option_service import pocket_option_service
                await pocket_option_service.connect()
                
                asyncio.create_task(analysis_service.run())
            
            state.ready = True
            logger.info("✅ v1.7 يعمل الآن!")
            await sender.send_text("🟢 <b>تم تشغيل البوت بنجاح v1.7</b>\nتم تحديث محرك الاتصال ليدعم المصادقة المرنة.")
            
            while True: await asyncio.sleep(3600)
        except Exception as e:
            state.error = str(e)
            logger.error(f"❌ خطأ حرج: {e}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())

# بدء البوت فور تشغيل الملف لضمان التوافق مع Gunicorn
thread = threading.Thread(target=start_bot_background, daemon=True)
thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
