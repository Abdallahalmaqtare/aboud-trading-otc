"""
Aboud Trading Bot OTC - Pocket Option Service v1.0
====================================================
خدمة الاتصال بـ Pocket Option عبر WebSocket API
- جلب بيانات الشموع لأزواج OTC
- التحليل الفني باستخدام المؤشرات القوية
- إرسال الإشارات عبر webhook

الاتصال يتطلب SSID من المتصفح:
42["auth",{"session":"...","isDemo":1,"uid":...,"platform":1}]
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import aiohttp
import pandas as pd
import numpy as np

from config import (
    POCKET_OPTION_SSID,
    POCKET_OPTION_IS_DEMO,
    POCKET_OPTION_CONNECT_TIMEOUT,
    TRADING_PAIRS,
    EMA_FAST, EMA_MID, EMA_SLOW, EMA_TREND,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER,
    ADX_PERIOD, ADX_MIN_THRESHOLD,
    MIN_SIGNAL_SCORE,
    DEBUG,
)

logger = logging.getLogger(__name__)

# ─── ثوابت Pocket Option WebSocket ────────────────────────────────────────────
PO_WS_REGIONS = [
    "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-us.po.market/socket.io/?EIO=4&transport=websocket",
]

# مدة الشمعة بالثواني (15 دقيقة = 900 ثانية)
CANDLE_PERIOD_SECONDS = 900

# عدد الشموع المطلوبة للتحليل
CANDLES_COUNT = 200


class PocketOptionService:
    """
    خدمة الاتصال بـ Pocket Option عبر WebSocket.
    تجلب بيانات الشموع وتحلّلها باستخدام المؤشرات الفنية.
    """

    def __init__(self):
        self.ssid = POCKET_OPTION_SSID
        self.is_demo = POCKET_OPTION_IS_DEMO
        self._ws = None
        self._session = None
        self._connected = False
        self._candles_cache: Dict[str, List[Dict]] = {}
        self._last_fetch: Dict[str, float] = {}
        self._cache_ttl = 60  # ثانية

    # ─────────────────────────────────────────────────────────────────────────
    # الاتصال والمصادقة
    # ─────────────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """الاتصال بـ Pocket Option WebSocket."""
        if not self.ssid:
            logger.error("❌ POCKET_OPTION_SSID غير مضبوط في متغيرات البيئة")
            return False

        for region_url in PO_WS_REGIONS:
            try:
                logger.info("🔌 محاولة الاتصال بـ %s", region_url)
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=POCKET_OPTION_CONNECT_TIMEOUT)
                )
                self._ws = await self._session.ws_connect(
                    region_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Origin": "https://pocketoption.com",
                    },
                    heartbeat=20,
                )

                # انتظار رسالة الترحيب
                msg = await asyncio.wait_for(self._ws.receive(), timeout=10)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    logger.debug("PO WS init: %s", msg.data[:100])

                # إرسال المصادقة
                await self._ws.send_str(self.ssid)
                logger.info("✅ تم إرسال SSID للمصادقة")

                # انتظار تأكيد المصادقة
                auth_ok = await self._wait_for_auth()
                if auth_ok:
                    self._connected = True
                    logger.info("✅ تم الاتصال بـ Pocket Option بنجاح")
                    return True
                else:
                    logger.warning("⚠️ فشل المصادقة مع %s", region_url)
                    await self._close_connection()

            except asyncio.TimeoutError:
                logger.warning("⏰ انتهت مهلة الاتصال مع %s", region_url)
                await self._close_connection()
            except Exception as e:
                logger.warning("❌ خطأ في الاتصال مع %s: %s", region_url, e)
                await self._close_connection()

        logger.error("❌ فشل الاتصال بجميع مناطق Pocket Option")
        return False

    async def _wait_for_auth(self, timeout: float = 15) -> bool:
        """انتظار تأكيد المصادقة."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(self._ws.receive(), timeout=5)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.data
                    logger.debug("PO auth response: %s", data[:200])
                    # رسالة المصادقة الناجحة تحتوي على "isSuccessful":true
                    if '"isSuccessful":true' in data or '"authorized":true' in data:
                        return True
                    # أو رسالة ping/pong
                    if data.startswith("2") or data.startswith("3"):
                        continue
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    return False
            except asyncio.TimeoutError:
                break
        return False

    async def _close_connection(self):
        """إغلاق الاتصال."""
        try:
            if self._ws and not self._ws.closed:
                await self._ws.close()
        except Exception:
            pass
        try:
            if self._session and not self._session.closed:
                await self._session.close()
        except Exception:
            pass
        self._ws = None
        self._session = None
        self._connected = False

    async def disconnect(self):
        """قطع الاتصال."""
        await self._close_connection()
        logger.info("🔌 تم قطع الاتصال بـ Pocket Option")

    # ─────────────────────────────────────────────────────────────────────────
    # جلب بيانات الشموع
    # ─────────────────────────────────────────────────────────────────────────

    async def get_candles(self, asset: str, count: int = CANDLES_COUNT) -> Optional[pd.DataFrame]:
        """
        جلب بيانات الشموع لزوج OTC من Pocket Option.

        Args:
            asset: اسم الزوج (مثل: EURUSD_otc)
            count: عدد الشموع المطلوبة

        Returns:
            DataFrame يحتوي على: open, high, low, close, volume, time
        """
        # التحقق من الكاش
        now = time.time()
        if asset in self._candles_cache and asset in self._last_fetch:
            if now - self._last_fetch[asset] < self._cache_ttl:
                logger.debug("📦 استخدام الكاش لـ %s", asset)
                return self._candles_cache[asset]

        if not self._connected:
            logger.warning("⚠️ غير متصل بـ Pocket Option، محاولة الاتصال...")
            connected = await self.connect()
            if not connected:
                return None

        try:
            # طلب بيانات الشموع
            end_time = int(time.time())
            start_time = end_time - (CANDLE_PERIOD_SECONDS * count)

            request = json.dumps([
                "sendMessage",
                {
                    "asset": asset,
                    "period": CANDLE_PERIOD_SECONDS,
                    "time": end_time,
                    "index": 0,
                    "count": count,
                    "name": "candles",
                    "offset": 0,
                }
            ])

            await self._ws.send_str(f"42{request}")
            logger.debug("📤 طلب شموع %s", asset)

            # انتظار البيانات
            candles_data = await self._receive_candles(asset, timeout=15)
            if not candles_data:
                logger.warning("⚠️ لم يتم استلام بيانات الشموع لـ %s", asset)
                return None

            df = self._candles_to_dataframe(candles_data)
            if df is not None and not df.empty:
                self._candles_cache[asset] = df
                self._last_fetch[asset] = now
                logger.info("✅ تم جلب %d شمعة لـ %s", len(df), asset)

            return df

        except Exception as e:
            logger.error("❌ خطأ في جلب الشموع لـ %s: %s", asset, e)
            self._connected = False
            return None

    async def _receive_candles(self, asset: str, timeout: float = 15) -> Optional[List[Dict]]:
        """استقبال بيانات الشموع من WebSocket."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                msg = await asyncio.wait_for(self._ws.receive(), timeout=min(remaining, 5))

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.data
                    # تجاهل رسائل ping/pong
                    if data in ("2", "3") or data.startswith("40") or data.startswith("41"):
                        if data == "2":
                            await self._ws.send_str("3")
                        continue

                    # البحث عن بيانات الشموع
                    if '"candles"' in data or '"data"' in data:
                        try:
                            # إزالة البادئة 42 من Socket.IO
                            if data.startswith("42"):
                                parsed = json.loads(data[2:])
                                if isinstance(parsed, list) and len(parsed) > 1:
                                    payload = parsed[1]
                                    if isinstance(payload, dict):
                                        candles = payload.get("candles") or payload.get("data")
                                        if candles:
                                            return candles
                        except (json.JSONDecodeError, IndexError, KeyError) as e:
                            logger.debug("تجاهل رسالة غير صالحة: %s", e)
                            continue

                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    logger.warning("⚠️ انقطع الاتصال أثناء استقبال الشموع")
                    self._connected = False
                    break

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("❌ خطأ في استقبال الشموع: %s", e)
                break

        return None

    def _candles_to_dataframe(self, candles: List[Dict]) -> Optional[pd.DataFrame]:
        """تحويل بيانات الشموع إلى DataFrame."""
        if not candles:
            return None

        try:
            records = []
            for c in candles:
                if isinstance(c, dict):
                    records.append({
                        "time": c.get("time", c.get("t", 0)),
                        "open": float(c.get("open", c.get("o", 0))),
                        "high": float(c.get("high", c.get("h", 0))),
                        "low": float(c.get("low", c.get("l", 0))),
                        "close": float(c.get("close", c.get("c", 0))),
                        "volume": float(c.get("volume", c.get("v", 0))),
                    })
                elif isinstance(c, (list, tuple)) and len(c) >= 5:
                    records.append({
                        "time": c[0],
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "volume": float(c[5]) if len(c) > 5 else 0,
                    })

            if not records:
                return None

            df = pd.DataFrame(records)
            df = df.sort_values("time").reset_index(drop=True)
            df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
            return df

        except Exception as e:
            logger.error("❌ خطأ في تحويل الشموع: %s", e)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # التحليل الفني - المؤشرات القوية
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """حساب المتوسط المتحرك الأسي EMA."""
        return series.ewm(span=period, adjust=False).mean()

    def calculate_macd(self, close: pd.Series) -> tuple:
        """حساب MACD."""
        ema_fast = self.calculate_ema(close, MACD_FAST)
        ema_slow = self.calculate_ema(close, MACD_SLOW)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, MACD_SIGNAL)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def calculate_supertrend(self, df: pd.DataFrame) -> pd.Series:
        """حساب Supertrend."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # ATR
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.ewm(span=SUPERTREND_PERIOD, adjust=False).mean()

        hl2 = (high + low) / 2
        upper_band = hl2 + (SUPERTREND_MULTIPLIER * atr)
        lower_band = hl2 - (SUPERTREND_MULTIPLIER * atr)

        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)

        for i in range(1, len(df)):
            # Lower band
            if lower_band.iloc[i] > lower_band.iloc[i-1] or close.iloc[i-1] < lower_band.iloc[i-1]:
                final_lower = lower_band.iloc[i]
            else:
                final_lower = lower_band.iloc[i-1]

            # Upper band
            if upper_band.iloc[i] < upper_band.iloc[i-1] or close.iloc[i-1] > upper_band.iloc[i-1]:
                final_upper = upper_band.iloc[i]
            else:
                final_upper = upper_band.iloc[i-1]

            # Direction
            if i == 1:
                direction.iloc[i] = 1
            elif supertrend.iloc[i-1] == upper_band.iloc[i-1]:
                direction.iloc[i] = 1 if close.iloc[i] > final_upper else -1
            else:
                direction.iloc[i] = -1 if close.iloc[i] < final_lower else 1

            supertrend.iloc[i] = final_lower if direction.iloc[i] == 1 else final_upper

        return direction

    def calculate_adx(self, df: pd.DataFrame) -> tuple:
        """حساب ADX و DI+ و DI-."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index)

        # Smoothed values
        atr_smooth = tr.ewm(span=ADX_PERIOD, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(span=ADX_PERIOD, adjust=False).mean() / atr_smooth)
        minus_di = 100 * (minus_dm.ewm(span=ADX_PERIOD, adjust=False).mean() / atr_smooth)

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        adx = dx.ewm(span=ADX_PERIOD, adjust=False).mean()

        return adx, plus_di, minus_di

    def calculate_roc(self, close: pd.Series, period: int = 9) -> pd.Series:
        """حساب Rate of Change (ROC)."""
        return ((close - close.shift(period)) / close.shift(period)) * 100

    def analyze(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        التحليل الفني الكامل على آخر شمعة.
        يعيد إشارة CALL أو PUT مع النقاط، أو None إذا لم تكن هناك إشارة.
        """
        if df is None or len(df) < max(EMA_TREND, 50) + 10:
            logger.warning("⚠️ بيانات غير كافية للتحليل")
            return None

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # ─── حساب المؤشرات ────────────────────────────────────────────────
        ema_fast = self.calculate_ema(close, EMA_FAST)
        ema_mid = self.calculate_ema(close, EMA_MID)
        ema_slow = self.calculate_ema(close, EMA_SLOW)
        ema_trend = self.calculate_ema(close, EMA_TREND)

        macd_line, signal_line, histogram = self.calculate_macd(close)
        st_direction = self.calculate_supertrend(df)
        adx, plus_di, minus_di = self.calculate_adx(df)
        roc = self.calculate_roc(close)

        # حجم التداول
        vol_sma = volume.rolling(window=20).mean()

        # آخر قيم
        i = -1
        c = close.iloc[i]
        ef = ema_fast.iloc[i]
        em = ema_mid.iloc[i]
        es = ema_slow.iloc[i]
        et = ema_trend.iloc[i]
        hist = histogram.iloc[i]
        hist_prev = histogram.iloc[i-1]
        st_dir = st_direction.iloc[i]
        adx_val = adx.iloc[i]
        pdi = plus_di.iloc[i]
        mdi = minus_di.iloc[i]
        roc_val = roc.iloc[i]
        vol_now = volume.iloc[i]
        vol_avg = vol_sma.iloc[i]

        # موضع الإغلاق في النطاق
        candle_range = high.iloc[i] - low.iloc[i]
        close_pos = (c - low.iloc[i]) / candle_range if candle_range > 0 else 0.5

        # ─── تسجيل النقاط ─────────────────────────────────────────────────
        # CALL
        score_ema_call = 1 if ef > em > es else 0
        score_trend_call = 1 if c > et else 0
        score_macd_call = 1 if hist > 0 and hist > hist_prev else 0
        score_st_call = 1 if st_dir > 0 else 0
        score_adx_call = 1 if adx_val >= ADX_MIN_THRESHOLD and pdi > mdi else 0
        score_vol_call = 1 if vol_now > vol_avg * 1.2 and c > df["open"].iloc[i] else 0
        score_close_call = 1 if close_pos >= 0.7 else 0

        # PUT
        score_ema_put = 1 if ef < em < es else 0
        score_trend_put = 1 if c < et else 0
        score_macd_put = 1 if hist < 0 and hist < hist_prev else 0
        score_st_put = 1 if st_dir < 0 else 0
        score_adx_put = 1 if adx_val >= ADX_MIN_THRESHOLD and mdi > pdi else 0
        score_vol_put = 1 if vol_now > vol_avg * 1.2 and c < df["open"].iloc[i] else 0
        score_close_put = 1 if close_pos <= 0.3 else 0

        call_score = (score_ema_call + score_trend_call + score_macd_call +
                      score_st_call + score_adx_call + score_vol_call + score_close_call)
        put_score = (score_ema_put + score_trend_put + score_macd_put +
                     score_st_put + score_adx_put + score_vol_put + score_close_put)

        # ─── البوابات الإلزامية ────────────────────────────────────────────
        adx_ok_call = adx_val >= ADX_MIN_THRESHOLD and pdi > mdi
        adx_ok_put = adx_val >= ADX_MIN_THRESHOLD and mdi > pdi
        roc_ok_call = roc_val >= 0.05
        roc_ok_put = roc_val <= -0.05

        gate_call = call_score >= MIN_SIGNAL_SCORE and adx_ok_call and roc_ok_call
        gate_put = put_score >= MIN_SIGNAL_SCORE and adx_ok_put and roc_ok_put

        indicators = {
            "ema_fast": round(ef, 5),
            "ema_mid": round(em, 5),
            "ema_slow": round(es, 5),
            "ema200": round(et, 5),
            "macd_hist": round(hist, 6),
            "supertrend": "UP" if st_dir > 0 else "DOWN",
            "adx": round(adx_val, 2),
            "plus_di": round(pdi, 2),
            "minus_di": round(mdi, 2),
            "roc": round(roc_val, 4),
            "volume": round(vol_now, 2),
            "vol_avg": round(vol_avg, 2),
            "close_pos": round(close_pos, 3),
        }

        if gate_call:
            return {
                "direction": "CALL",
                "signal_score": call_score,
                "indicators": indicators,
                "close_price": round(c, 5),
            }
        elif gate_put:
            return {
                "direction": "PUT",
                "signal_score": put_score,
                "indicators": indicators,
                "close_price": round(c, 5),
            }

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # جلب سعر الشمعة لتحديد نتيجة الصفقة
    # ─────────────────────────────────────────────────────────────────────────

    async def get_trade_candle(self, asset: str, entry_time: datetime) -> Optional[Dict]:
        """
        جلب شمعة الـ 15 دقيقة المحددة لتحديد نتيجة الصفقة.

        Returns:
            {"entry_price": float, "exit_price": float, "source": "pocket_option"}
        """
        df = await self.get_candles(asset, count=10)
        if df is None or df.empty:
            return None

        # البحث عن الشمعة المطابقة لوقت الدخول
        entry_ts = int(entry_time.timestamp())
        for _, row in df.iterrows():
            candle_ts = int(row["time"])
            if abs(candle_ts - entry_ts) <= 60:
                return {
                    "entry_price": float(row["open"]),
                    "exit_price": float(row["close"]),
                    "source": "pocket_option",
                    "candle_start": datetime.fromtimestamp(candle_ts, tz=timezone.utc).isoformat(),
                }

        logger.warning("⚠️ لم يتم العثور على شمعة لـ %s عند %s", asset, entry_time)
        return None

    async def get_current_price(self, asset: str) -> Optional[float]:
        """جلب السعر الحالي للزوج."""
        df = await self.get_candles(asset, count=5)
        if df is not None and not df.empty:
            return float(df["close"].iloc[-1])
        return None


# مثيل عالمي
pocket_option_service = PocketOptionService()
