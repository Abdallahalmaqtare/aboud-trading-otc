"""
Aboud Trading Bot OTC - Analysis Service v1.0
=============================================
خدمة التحليل الفني التلقائي لأزواج OTC.
تعمل بشكل مستقل وترسل إشارات عبر webhook إلى البوت الرئيسي.

المؤشرات المستخدمة (نفس المشروع الأصلي):
1. EMA alignment (9 > 21 > 50)
2. EMA200 trend filter
3. MACD histogram momentum
4. Supertrend
5. ADX (بوابة إلزامية)
6. Volume confirmation
7. Strong close position
8. ROC momentum (بوابة إلزامية)
"""

import asyncio
import logging
import time
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import aiohttp

from config import (
    TRADING_PAIRS,
    TRADE_DURATION_MINUTES,
    SIGNAL_COOLDOWN_MINUTES,
    WEBHOOK_SECRET,
    WEBHOOK_PORT,
    DEBUG,
    PAIR_DISPLAY_NAMES,
)
from pocket_option_service import pocket_option_service

logger = logging.getLogger(__name__)

# فترة التحليل (ثانية) - كل 60 ثانية
ANALYSIS_INTERVAL = 60

# عنوان webhook الداخلي
WEBHOOK_URL = f"http://localhost:{WEBHOOK_PORT}/webhook"


class AnalysisService:
    """
    خدمة التحليل الفني التلقائي.
    تحلّل أزواج OTC وترسل الإشارات إلى البوت الرئيسي.
    """

    def __init__(self):
        self._running = False
        self._last_signal: Dict[str, float] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def close(self):
        """إغلاق الخدمة."""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        await pocket_option_service.disconnect()

    # ─────────────────────────────────────────────────────────────────────────
    # الحلقة الرئيسية للتحليل
    # ─────────────────────────────────────────────────────────────────────────

    async def run(self):
        """تشغيل حلقة التحليل الفني."""
        self._running = True
        logger.info("🚀 بدء خدمة التحليل الفني لأزواج OTC")

        # الاتصال بـ Pocket Option
        connected = await pocket_option_service.connect()
        if not connected:
            logger.error("❌ فشل الاتصال بـ Pocket Option - لن يعمل التحليل التلقائي")
            logger.info("ℹ️  سيستمر البوت في استقبال إشارات TradingView عبر webhook")
            return

        while self._running:
            try:
                await self._analyze_all_pairs()
                await asyncio.sleep(ANALYSIS_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("❌ خطأ في حلقة التحليل: %s", e, exc_info=True)
                await asyncio.sleep(30)

        logger.info("⏹ توقفت خدمة التحليل الفني")

    async def _analyze_all_pairs(self):
        """تحليل جميع الأزواج."""
        for pair in TRADING_PAIRS:
            try:
                await self._analyze_pair(pair)
                await asyncio.sleep(2)  # فاصل بين الأزواج
            except Exception as e:
                logger.error("❌ خطأ في تحليل %s: %s", pair, e)

    async def _analyze_pair(self, pair: str):
        """تحليل زوج واحد وإرسال الإشارة إذا توفرت."""
        # التحقق من cooldown
        now = time.time()
        last = self._last_signal.get(pair, 0)
        if now - last < SIGNAL_COOLDOWN_MINUTES * 60:
            remaining = int((SIGNAL_COOLDOWN_MINUTES * 60 - (now - last)) / 60)
            logger.debug("⏳ %s في فترة الانتظار (%d دقيقة متبقية)", pair, remaining)
            return

        # جلب بيانات الشموع
        df = await pocket_option_service.get_candles(pair)
        if df is None or df.empty:
            logger.warning("⚠️ لا توجد بيانات لـ %s", pair)
            return

        # التحليل الفني
        signal = pocket_option_service.analyze(df)
        if not signal:
            logger.debug("⚪ لا توجد إشارة لـ %s", pair)
            return

        # حساب وقت الدخول (بداية الشمعة التالية)
        last_candle_time = int(df["time"].iloc[-1])
        next_candle_time = last_candle_time + 900  # +15 دقيقة
        entry_time_dt = datetime.fromtimestamp(next_candle_time, tz=timezone.utc)

        display_name = PAIR_DISPLAY_NAMES.get(pair, pair)
        logger.info(
            "🎯 إشارة %s: %s %s (نقاط: %d/7) دخول: %s",
            display_name,
            signal["direction"],
            pair,
            signal["signal_score"],
            entry_time_dt.strftime("%H:%M"),
        )

        # إرسال الإشارة عبر webhook
        sent = await self._send_webhook_signal(pair, signal, entry_time_dt)
        if sent:
            self._last_signal[pair] = now

    async def _send_webhook_signal(
        self,
        pair: str,
        signal: Dict[str, Any],
        entry_time: datetime,
    ) -> bool:
        """إرسال إشارة عبر webhook إلى البوت الرئيسي."""
        payload = {
            "secret": WEBHOOK_SECRET,
            "pair": pair,
            "direction": signal["direction"],
            "action": "SIGNAL",
            "signal_score": signal["signal_score"],
            "target_entry_time": int(entry_time.timestamp()),
            "signal_time": int(time.time()),
            "signal_close": signal.get("close_price", 0),
            "indicators": signal.get("indicators", {}),
        }

        try:
            session = await self._get_session()
            async with session.post(WEBHOOK_URL, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info("✅ تم إرسال الإشارة: %s", result.get("status"))
                    return True
                else:
                    logger.warning("⚠️ فشل إرسال الإشارة: HTTP %d", resp.status)
                    return False
        except Exception as e:
            logger.error("❌ خطأ في إرسال الإشارة عبر webhook: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # إرسال نتيجة الصفقة
    # ─────────────────────────────────────────────────────────────────────────

    async def send_trade_result(
        self,
        pair: str,
        entry_time: datetime,
        entry_price: float,
        exit_price: float,
    ) -> bool:
        """إرسال نتيجة الصفقة عبر webhook."""
        payload = {
            "secret": WEBHOOK_SECRET,
            "pair": pair,
            "action": "RESULT",
            "entry_price": entry_price,
            "exit_price": exit_price,
            "ticker": pair,
        }

        try:
            session = await self._get_session()
            async with session.post(WEBHOOK_URL, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info("✅ تم إرسال النتيجة: %s", result.get("status"))
                    return True
                else:
                    logger.warning("⚠️ فشل إرسال النتيجة: HTTP %d", resp.status)
                    return False
        except Exception as e:
            logger.error("❌ خطأ في إرسال النتيجة: %s", e)
            return False


# مثيل عالمي
analysis_service = AnalysisService()
