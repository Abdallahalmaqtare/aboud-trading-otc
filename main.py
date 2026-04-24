"""
Aboud Trading Bot OTC - Main v1.2 (Render-Optimized)
======================================================
نسخة معدّلة للعمل على أزواج OTC في Pocket Option.

v1.2 - إصلاحات Render:
- فصل Flask عن asyncio بشكل صحيح
- تشغيل Telegram Bot في خيط منفصل
- ضمان استجابة الأوامر فوراً
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

# إعداد السجلات
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("AboudTradingOTC")

# ─── Global State ──────────────────────────────────────────────────────────────

app = Flask(__name__)
signal_manager = None
telegram_sender = None
bot_loop = None
bot_ready = False
application = None
bot_thread = None


# ─── Flask Routes ─────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    """نقطة فحص الصحة."""
    try:
        from pocket_option_service import pocket_option_service
        po_connected = pocket_option_service._connected
    except Exception:
        po_connected = False

    return jsonify({
        "status": "ok",
        "bot": "Aboud Trading OTC v1.2",
        "ready": bot_ready,
        "telegram": application is not None,
        "pg": bool(DATABASE_URL),
        "pocket_option": po_connected,
        "pairs": TRADING_PAIRS,
        "time": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """استقبال الإشارات."""
    try:
        if not bot_ready or not signal_manager or not bot_loop:
            logger.warning("Webhook received but bot not ready yet")
            return jsonify({"status": "not_ready"}), 503

        data = None
        raw_body = request.get_data(as_text=True)
        logger.debug("Webhook raw body: %s", raw_body[:200])

        try:
            data = json.loads(raw_body)
        except (json.JSONDecodeError, TypeError):
            pass

        if not data:
            data = request.get_json(force=True, silent=True)

        if not data:
            parts = raw_body.strip().split(",")
            if len(parts) >= 2:
                data = {
                    "pair": parts[0].strip(),
                    "direction": parts[1].strip(),
                    "action": parts[2].strip() if len(parts) > 2 else "SIGNAL",
                }

        if not data:
            return jsonify({"error": "Bad format"}), 400

        secret = data.get("secret", "")
        if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

        logger.info("Webhook: pair=%s dir=%s", data.get("pair"), data.get("direction"))

        try:
            fut = asyncio.run_coroutine_threadsafe(
                signal_manager.process_webhook_signal(data), bot_loop
            )
            res = fut.result(timeout=25)
            return jsonify(res), 200
        except Exception as e:
            logger.error("Webhook error: %s", e)
            return jsonify({"status": "error"}), 500

    except Exception as e:
        logger.error("Webhook crash: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/webhook/test", methods=["GET", "POST"])
def webhook_test():
    return jsonify({"status": "ok", "ready": bot_ready})


@app.route("/connection", methods=["GET"])
def connection_status():
    """حالة الاتصال بـ Pocket Option."""
    try:
        from pocket_option_service import pocket_option_service
        connected = pocket_option_service._connected
        return jsonify({
            "connected": connected,
            "pairs": TRADING_PAIRS,
            "ssid_configured": bool(POCKET_OPTION_SSID),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Bot Async Functions ──────────────────────────────────────────────────────

async def send_daily_report():
    """إرسال التقرير اليومي."""
    try:
        await telegram_sender.send_daily_report(get_daily_stats(), get_today_trades())
    except Exception as e:
        logger.error(f"Daily report err: {e}")


async def keep_alive_ping():
    """Ping للحفاظ على الخدمة نشطة."""
    try:
        import aiohttp
        service_url = os.getenv("RENDER_EXTERNAL_URL", f"http://localhost:{WEBHOOK_PORT}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{service_url}/") as resp:
                logger.debug("Keep-alive: %s", resp.status)
    except Exception as e:
        logger.debug("Keep-alive failed: %s", e)


async def run_telegram_bot():
    """تشغيل بوت التيليغرام (في حلقة asyncio منفصلة)."""
    global application, bot_ready, signal_manager, telegram_sender

    logger.info("🔄 بدء تهيئة بوت التيليغرام...")

    try:
        # تهيئة قاعدة البيانات
        init_db()
        logger.info("✅ قاعدة البيانات جاهزة")

        # تهيئة الخدمات
        telegram_sender = TelegramSender()
        signal_manager = SignalManager(telegram_sender)
        logger.info("✅ الخدمات جاهزة")

        # استعادة الصفقات المعلقة
        try:
            recovered = await signal_manager.recover_pending_trades()
            if recovered:
                logger.info("♻️ استعادة %d صفقة", recovered)
        except Exception as e:
            logger.warning("استعادة الصفقات: %s", e)

        # إنشاء تطبيق التيليغرام
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        application.bot_data["signal_manager"] = signal_manager
        setup_admin_handlers(application)
        logger.info("✅ تم إعداد معالجات الأوامر")

        # إعداد الجدولة
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            send_daily_report, "cron",
            hour=DAILY_REPORT_HOUR_UTC, minute=DAILY_REPORT_MINUTE,
            timezone="UTC",
        )
        scheduler.add_job(keep_alive_ping, "interval", minutes=13, id="keep_alive")
        scheduler.start()
        logger.info("✅ الجدولة جاهزة")

        # بدء بوت التيليغرام
        logger.info("🔄 بدء بوت التيليغرام...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            timeout=30,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30,
        )
        logger.info("✅ بوت التيليغرام يعمل")

        # تشغيل خدمة التحليل
        analysis_task = None
        if POCKET_OPTION_SSID:
            try:
                from analysis_service import analysis_service
                analysis_task = asyncio.create_task(analysis_service.run())
                logger.info("🚀 خدمة التحليل التلقائي بدأت")
            except Exception as e:
                logger.warning("خدمة التحليل: %s", e)

        # إرسال رسالة البدء
        bot_ready = True
        logger.info("=" * 60)
        logger.info("  🟢 Aboud Trading Bot OTC v1.2 - READY!")
        logger.info(f"  Pairs: {', '.join(TRADING_PAIRS)}")
        logger.info(f"  Telegram: ✅ ACTIVE")
        logger.info("=" * 60)

        try:
            last = get_setting("last_startup", "")
            if not last or (time.time() - float(last)) > 21600:
                pairs_display = " | ".join([PAIR_DISPLAY_NAMES.get(p, p) for p in TRADING_PAIRS])
                po_status = "✅ متصل" if POCKET_OPTION_SSID else "⚠️ يحتاج SSID"
                await telegram_sender.send_text(
                    f"🟢 <b>Aboud Trading Bot OTC v1.2</b>\n\n"
                    f"📊 {pairs_display}\n"
                    f"⏱ 15 دقيقة | 🕐 UTC+{BOT_UTC_OFFSET}\n"
                    f"🎯 الحد الأدنى للإشارة: {MIN_SIGNAL_SCORE}/7\n"
                    f"💾 DB: {'☁️ PostgreSQL' if DATABASE_URL else '📁 SQLite'}\n"
                    f"🔌 Pocket Option: {po_status}\n"
                    f"✅ البوت يعمل الآن!",
                )
                set_setting("last_startup", str(time.time()))
        except Exception as e:
            logger.error(f"رسالة البدء: {e}")

        # حلقة الانتظار
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("🛑 إيقاف البوت...")
        finally:
            bot_ready = False
            if analysis_task and not analysis_task.done():
                analysis_task.cancel()
            try:
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
            except Exception:
                pass
            try:
                await telegram_sender.close()
            except Exception:
                pass
            scheduler.shutdown()

    except Exception as e:
        logger.error(f"❌ خطأ حرج في بوت التيليغرام: {e}", exc_info=True)
        bot_ready = False


def start_bot_thread():
    """بدء بوت التيليغرام في خيط منفصل."""
    global bot_loop, bot_thread

    def run_bot_loop():
        global bot_loop
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        try:
            bot_loop.run_until_complete(run_telegram_bot())
        except Exception as e:
            logger.error(f"Bot thread error: {e}", exc_info=True)
        finally:
            bot_loop.close()

    bot_thread = threading.Thread(target=run_bot_loop, daemon=True, name="BotThread")
    bot_thread.start()
    logger.info("✅ خيط البوت بدأ")

    # انتظر قليلاً حتى يكون البوت جاهزاً
    time.sleep(3)


def main():
    """نقطة الدخول الرئيسية."""
    logger.info("=" * 60)
    logger.info("  Aboud Trading Bot OTC v1.2 (Render-Optimized)")
    logger.info("  Starting up...")
    logger.info("=" * 60)

    # بدء خيط البوت
    start_bot_thread()

    # تشغيل Flask في الخيط الرئيسي
    logger.info(f"🌐 بدء Flask على المنفذ {WEBHOOK_PORT}...")
    app.run(
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
