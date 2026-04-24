"""
Aboud Trading Bot OTC - Pocket Option Service v1.8
====================================================
نسخة مطورة تدعم التنقل الذكي بين المناطق (Smart Region Selection)
مثالية للعمل من منطقة Frankfurt
"""
import asyncio
import json
import logging
import time
import aiohttp
import pandas as pd
from typing import Optional, List, Dict
from config import *

logger = logging.getLogger("PocketOptionService")

# مناطق الاتصال مرتبة حسب الأفضلية لمنطقة Frankfurt
PO_WS_REGIONS = [
    "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-msk.po.market/socket.io/?EIO=4&transport=websocket",
]

CANDLE_PERIOD_SECONDS = 900
CANDLES_COUNT = 200

class PocketOptionService:
    def __init__(self):
        self.auth_message = POCKET_OPTION_SSID
        self._ws = None
        self._session = None
        self._authenticated = False
        self.last_candles = {}
        self.current_region_index = 0

    async def connect(self) -> bool:
        if not self.auth_message:
            logger.error("❌ POCKET_OPTION_SSID غير مضبوط")
            return False

        # محاولة الاتصال بالمناطق المتاحة بالتتابع
        for _ in range(len(PO_WS_REGIONS)):
            region_url = PO_WS_REGIONS[self.current_region_index]
            try:
                logger.info(f"🔌 محاولة الاتصال بالمنطقة: {region_url}")
                self._session = aiohttp.ClientSession()
                self._ws = await self._session.ws_connect(region_url, heartbeat=25, timeout=30)
                
                asyncio.create_task(self._message_handler())
                await self._send_auth()
                
                # انتظار المصادقة
                start_time = time.time()
                while time.time() - start_time < 12:
                    if self._authenticated:
                        logger.info(f"✅ متصل بنجاح عبر المنطقة: {region_url}")
                        return True
                    await asyncio.sleep(0.5)
                
                logger.warning(f"⚠️ فشل المصادقة مع {region_url}، جاري تجربة منطقة أخرى...")
                await self.disconnect()
            except Exception as e:
                logger.error(f"❌ خطأ في {region_url}: {e}")
                await self.disconnect()
            
            # الانتقال للمنطقة التالية في القائمة
            self.current_region_index = (self.current_region_index + 1) % len(PO_WS_REGIONS)
        
        return False

    async def _send_auth(self):
        msg = self.auth_message.strip()
        if msg.startswith('42'):
            await self._ws.send_str(msg)
        else:
            # معالجة ذكية للـ SSID أو sessionToken
            key = "sessionToken" if len(msg) > 30 and not msg.isalnum() else "session"
            auth_payload = f'42["auth", {{"{key}": "{msg}", "isDemo": 1, "uid": 0, "platform": 1}}]'
            await self._ws.send_str(auth_payload)

    async def _message_handler(self):
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.data
                    if data.startswith('2'):
                        await self._ws.send_str('3')
                    elif data.startswith('42'):
                        try:
                            parsed = json.loads(data[2:])
                            event = parsed[0]
                            payload = parsed[1]
                            if event == "success_auth" or (isinstance(payload, dict) and payload.get("authorized")):
                                self._authenticated = True
                            elif event in ["candles", "load_candles"]:
                                asset = payload.get("asset")
                                candles = payload.get("candles") or payload.get("data")
                                if asset and candles:
                                    self.last_candles[asset] = candles
                        except: pass
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except: pass
        self._authenticated = False

    async def disconnect(self):
        self._authenticated = False
        try:
            if self._ws: await self._ws.close()
            if self._session: await self._session.close()
        except: pass

    async def get_candles(self, asset: str, count: int = CANDLES_COUNT) -> Optional[pd.DataFrame]:
        if not self._authenticated:
            if not await self.connect(): return None
        try:
            req = f'42["get_candles", {{"asset": "{asset}", "period": {CANDLE_PERIOD_SECONDS}, "count": {count}}}]'
            await self._ws.send_str(req)
            start_time = time.time()
            while time.time() - start_time < 10:
                if asset in self.last_candles:
                    return self._to_df(self.last_candles.pop(asset))
                await asyncio.sleep(0.5)
        except: self._authenticated = False
        return None

    def _to_df(self, candles):
        try:
            df = pd.DataFrame(candles)
            if 'time' in df.columns: df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except: return None

pocket_option_service = PocketOptionService()
