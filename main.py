"""
Aboud Trading Bot OTC - Main v1.0
===================================
نسخة معدّلة للعمل على أزواج OTC في Pocket Option.

التغييرات الرئيسية عن النسخة الأصلية:
- أزواج OTC: EURUSD_otc و GBPUSD_otc
- مصدر البيانات: Pocket Option WebSocket API (عبر SSID)
- التحليل التلقائي: يعمل داخلياً بدلاً من TradingView
- نتائج الصفقات: من Pocket Option API مباشرة
- OTC متاح 24/7 (لا قيود على أوقات التداول)
- إضافة خدمة التحليل الفني التلقائي (analysis_service)

طريقة الاستخدام:
1. ضع POCKET_OPTION_SSID في ملف .env
2. شغّل البوت: python main.py
"""
import asyncio
import logging
import threading
import json
import time
import os
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

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AboudTradingOTC")

app = Flask(__name__)
signal_manager = None
telegram_sender = None
loop = None
bot_ready = False


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
        "bot": "Aboud Trading OTC v1.0",
        "ready": bot_ready,
        "pg": bool(DATABASE_URL),
        "pocket_option": po_connected,
        "pairs": TRADING_PAIRS,
        "time": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    استقبال الإشارات.
    يقبل:
    - إشارات من التحليل الداخلي (analysis_service)
    - إشارات من TradingView (للتوافق مع النسخة الأصلية)
    - نتائج الصفقات (action=RESULT)
    """
    try:
        if not bot_ready or not signal_manager or not loop:
            logger.warning("Webhook received but bot not ready yet")
            return jsonify({"status": "not_ready", "message": "Bot is starting up"}), 503

        data = None
        raw_body = request.get_data(as_text=True)
        logger.info("Webhook raw body: %s", raw_body[:500])

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
            else:
                logger.error("Cannot parse webhook body: %s", raw_body[:200])
                return jsonify({"error": "Bad format"}), 400

        secret = data.get("secret", "")
        if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
            logger.warning("Webhook unauthorized: wrong secret")
            return jsonify({"error": "Unauthorized"}), 401

        logger.info(
            "Webhook received: pair=%s dir=%s action=%s score=%s",
            data.get("pair") or data.get("ticker"),
            data.get("direction"),
            data.get("action"),
            data.get("signal_score"),
        )

        try:
            fut = asyncio.run_coroutine_threadsafe(
                signal_manager.process_webhook_signal(data), loop
            )
            res = fut.result(timeout=25)
            logger.info("Webhook result: %s", res)
            return jsonify(res), 200
        except asyncio.TimeoutError:
            logger.error("Webhook processing timed out after 25s")
            return jsonify({"status": "timeout"}), 504
        except Exception as e:
            logger.error("Webhook processing error: %s", e, exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    except Exception as e:
        logger.error("Webhook handler crash: %s", e, exc_info=True)
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


# ─── Bot Functions ─────────────────────────────────────────────────────────────

def _should_send_startup():
    """التحقق من إرسال رسالة البدء مؤخراً (cooldown 6 ساعات)."""
    try:
        last = get_setting("last_startup", "")
        if last:
            elapsed = time.time() - float(last)
            if elapsed < 21600:
                logger.info(f"Startup msg skipped ({elapsed:.0f}s ago)")
                return False
        set_setting("last_startup", str(time.time()))
        return True
    except Exception as e:
        logger.warning(f"Startup check err: {e}")
        return True


async def send_daily_report():
    """إرسال التقرير اليومي."""
    try:
        await telegram_sender.send_daily_report(get_daily_stats(), get_today_trades())
    except Exception as e:
        logger.error(f"Daily report err: {e}", exc_info=True)


async def keep_alive_ping():
    """Ping للحفاظ على الخدمة نشطة."""
    try:
        import aiohttp
        service_url = os.getenv("RENDER_EXTERNAL_URL", f"http://localhost:{WEBHOOK_PORT}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{service_url}/") as resp:
                logger.debug("Keep-alive ping: %s", resp.status)
    except Exception as e:
        logger.debug("Keep-alive ping failed (non-critical): %s", e)


async def run_bot():
    global signal_manager, telegram_sender, loop, bot_ready
    loop = asyncio.get_event_loop()

    # تهيئة قاعدة البيانات
    init_db()
    logger.info(f"DB: {'PostgreSQL (PERMANENT)' if DATABASE_URL else 'SQLite (LOCAL)'}")

    # تهيئة خدمات البوت
    telegram_sender = TelegramSender()
    signal_manager = SignalManager(telegram_sender)

    # استعادة الصفقات المعلقة بعد إعادة التشغيل
    try:
        recovered = await signal_manager.recover_pending_trades()
        if recovered:
            logger.info("♻️  Recovered %d in-flight trade(s) after restart", recovered)
    except Exception as e:
        logger.warning("Recovery step failed (non-critical): %s", e)

    # تهيئة بوت التيليغرام
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.bot_data["signal_manager"] = signal_manager
    setup_admin_handlers(application)

    # الجدولة
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_report, "cron",
        hour=DAILY_REPORT_HOUR_UTC, minute=DAILY_REPORT_MINUTE,
        timezone="UTC",
    )
    scheduler.add_job(keep_alive_ping, "interval", minutes=13, id="keep_alive")
    scheduler.start()

    # بدء بوت التيليغرام
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    # تشغيل خدمة التحليل التلقائي لأزواج OTC
    analysis_task = None
    if POCKET_OPTION_SSID:
        try:
            from analysis_service import analysis_service
            analysis_task = asyncio.create_task(analysis_service.run())
            logger.info("🚀 خدمة التحليل التلقائي لـ OTC بدأت")
        except Exception as e:
            logger.warning("⚠️ فشل تشغيل خدمة التحليل: %s", e)
    else:
        logger.warning(
            "⚠️ POCKET_OPTION_SSID غير مضبوط - التحليل التلقائي معطّل.\n"
            "   البوت سيستقبل الإشارات فقط عبر webhook."
        )

    bot_ready = True

    logger.info("=" * 55)
    logger.info("  Aboud Trading Bot OTC v1.0")
    logger.info(f"  DB: {'PostgreSQL' if DATABASE_URL else 'SQLite'}")
    logger.info(f"  Pairs: {', '.join(TRADING_PAIRS)}")
    logger.info(f"  Min Score: {MIN_SIGNAL_SCORE}/7")
    logger.info(f"  Source: Pocket Option API")
    logger.info(f"  Analysis: {'AUTO (Pocket Option)' if POCKET_OPTION_SSID else 'WEBHOOK ONLY'}")
    logger.info("=" * 55)

    if _should_send_startup():
        pairs_display = " | ".join([PAIR_DISPLAY_NAMES.get(p, p) for p in TRADING_PAIRS])
        po_status = "✅ متصل" if POCKET_OPTION_SSID else "⚠️ يحتاج SSID"
        await telegram_sender.send_text(
            f"🟢 <b>Aboud Trading Bot OTC v1.0</b>\n\n"
            f"📊 {pairs_display}\n"
            f"⏱ 15 دقيقة | 🕐 UTC+{BOT_UTC_OFFSET}\n"
            f"🎯 الحد الأدنى للإشارة: {MIN_SIGNAL_SCORE}/7\n"
            f"💾 DB: {'☁️ PostgreSQL' if DATABASE_URL else '📁 SQLite'}\n"
            f"🔌 Pocket Option: {po_status}\n"
            f"🔄 التحليل: {'تلقائي 24/7' if POCKET_OPTION_SSID else 'webhook فقط'}\n"
            f"✅ البوت يعمل الآن!",
        )

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        bot_ready = False
        if analysis_task and not analysis_task.done():
            analysis_task.cancel()
            try:
                await analysis_task
            except asyncio.CancelledError:
                pass

        try:
            from analysis_service import analysis_service
            await analysis_service.close()
        except Exception:
            pass

        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await telegram_sender.close()
        await price_service.close()
        scheduler.shutdown()


def run_flask():
    app.run(host="0.0.0.0", port=WEBHOOK_PORT, debug=False, use_reloader=False)


def main():
    # تشغيل Flask في خيط منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on port %s", WEBHOOK_PORT)

    # تشغيل البوت (يحجب)
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
