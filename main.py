"""
Aboud Trading Bot OTC - Main v1.3 (Ultra-Stable for Render)
============================================================
نسخة محسنة بالكامل لضمان التشغيل المستقر على Render.com.

v1.3 - الإصلاحات الحاسمة:
- استخدام نظام Background Tasks لبدء البوت بعد تشغيل Flask.
- تحسين معالجة أخطاء الاتصال بـ Telegram و Pocket Option.
- نظام Logs مفصل لتشخيص أي خلل في متغيرات البيئة.
"""
import asyncio
import logging
import threading
import json
import time
import os
import sys
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from config import (
    TELEGRAM_BOT_TOKEN, WEBHOOK_SECRET, WEBHOOK_PORT,
    DAILY_REPORT_HOUR_UTC, DAILY_REPORT_MINUTE,
    BOT_UTC_OFFSET, DEBUG, DATABASE_URL,
    MIN_SIGNAL_SCORE, TRADING_PAIRS, PAIR_DISPLAY_NAMES,
    POCKET_OPTION_SSID,
)
from database import (
    init_db, get_daily_stats, get_today_trades,
    is_signals_enabled, get_setting, set_setting,
)
from signal_manager import SignalManager
from telegram_sender import TelegramSender
from price_service import price_service
from admin_bot import setup_admin_handlers

# إعداد السجلات بشكل مكثف للتشخيص
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("AboudTrading")

app = Flask(__name__)

# الحالة العالمية
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
    except:
        pass
    
    return jsonify({
        "bot": "Aboud Trading OTC v1.3",
        "ready": state.ready,
        "telegram": state.telegram_active,
        "pocket_option": state.po_active,
        "error": state.error,
        "time": datetime.now(timezone.utc).isoformat(),
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    if not state.ready:
        return jsonify({"status": "starting"}), 503
    
    data = request.get_json(silent=True) or {}
    secret = data.get("secret", "")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    
    if state.loop and state.signal_manager:
        asyncio.run_coroutine_threadsafe(
            state.signal_manager.process_webhook_signal(data), state.loop
        )
        return jsonify({"status": "received"}), 200
    return jsonify({"status": "error"}), 500

async def start_bot_logic():
    logger.info("🚀 بدء تهيئة منطق البوت...")
    state.loop = asyncio.get_event_loop()
    
    try:
        # 1. قاعدة البيانات
        init_db()
        logger.info("✅ قاعدة البيانات جاهزة")
        
        # 2. الخدمات
        state.telegram_sender = TelegramSender()
        state.signal_manager = SignalManager(state.telegram_sender)
        
        # 3. التيليغرام
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN missing!")
            
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        application.bot_data["signal_manager"] = state.signal_manager
        setup_admin_handlers(application)
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        state.telegram_active = True
        logger.info("✅ بوت التيليغرام نشط")
        
        # 4. الجدولة
        scheduler = AsyncIOScheduler()
        scheduler.add_job(lambda: asyncio.create_task(state.telegram_sender.send_daily_report(get_daily_stats(), get_today_trades())), 
                          "cron", hour=DAILY_REPORT_HOUR_UTC, minute=DAILY_REPORT_MINUTE)
        scheduler.start()
        
        # 5. التحليل التلقائي
        if POCKET_OPTION_SSID:
            from analysis_service import analysis_service
            asyncio.create_task(analysis_service.run())
            logger.info("🚀 خدمة التحليل بدأت")
        
        state.ready = True
        logger.info("✨ البوت جاهز تماماً v1.3")
        
        # رسالة ترحيب
        await state.telegram_sender.send_text("🟢 <b>تم تشغيل البوت بنجاح v1.3</b>\nجاهز لاستقبال الأوامر والتحليل.")
        
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        state.error = str(e)
        logger.error(f"❌ فشل بدء البوت: {e}", exc_info=True)

def run_async_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot_logic())

@app.before_first_request
def activate_bot():
    # هذا سيعمل عند أول طلب (أو عند بدء Flask في بعض البيئات)
    pass

def main():
    logger.info("--- بدء تشغيل Aboud Trading OTC v1.3 ---")
    
    # بدء خيط البوت
    t = threading.Thread(target=run_async_loop, daemon=True)
    t.start()
    
    # تشغيل Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
