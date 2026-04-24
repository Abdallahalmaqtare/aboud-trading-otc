"""
Aboud Trading Bot OTC - Pocket Option Service v1.7
====================================================
نسخة مطورة تدعم sessionToken والمصادقة المرنة
"""
import asyncio
import json
import logging
import time
import aiohttp
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from config import *

logger = logging.getLogger("PocketOptionService")

# ─── ثوابت Pocket Option WebSocket ────────────────────────────────────────────
PO_WS_REGIONS = [
    "wss://api-l.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket",
]

# مدة الشمعة بالثواني (15 دقيقة = 900 ثانية)
CANDLE_PERIOD_SECONDS = 900
CANDLES_COUNT = 200

class PocketOptionService:
    def __init__(self):
        self.auth_message = POCKET_OPTION_SSID
        self._ws = None
        self._session = None
        self._connected = False
        self._authenticated = False
        self.last_candles = {}

    async def connect(self) -> bool:
        if not self.auth_message:
            logger.error("❌ POCKET_OPTION_SSID غير مضبوط")
            return False

        for region_url in PO_WS_REGIONS:
            try:
                logger.info(f"🔌 محاولة الاتصال بـ {region_url}")
                self._session = aiohttp.ClientSession()
                self._ws = await self._session.ws_connect(region_url, heartbeat=25)
                self._connected = True
                
                # بدء معالج الرسائل في الخلفية
                asyncio.create_task(self._message_handler())
                
                # إرسال المصادقة
                await self._send_auth()
                
                # انتظار المصادقة (10 ثواني)
                start_time = time.time()
                while time.time() - start_time < 10:
                    if self._authenticated:
                        logger.info("✅ تم الاتصال والمصادقة بنجاح")
                        return True
                    await asyncio.sleep(0.5)
                
                logger.warning(f"⚠️ فشل المصادقة مع {region_url}")
                await self.disconnect()
            except Exception as e:
                logger.error(f"❌ خطأ في الاتصال مع {region_url}: {e}")
                await self.disconnect()
        
        return False

    async def _send_auth(self):
        """إرسال رسالة المصادقة بالتنسيق الصحيح"""
        msg = self.auth_message.strip()
        
        # إذا كانت الرسالة تبدأ بـ 42، نرسلها كما هي
        if msg.startswith('42'):
            await self._ws.send_str(msg)
        # إذا كانت sessionToken أو SSID فقط، نقوم بتركيبها
        else:
            # التحقق إذا كانت sessionToken
            if len(msg) > 20: 
                key = "sessionToken" if "sessionToken" in msg or not msg.isalnum() else "session"
                auth_payload = f'42["auth", {{"{key}": "{msg}", "isDemo": 1, "uid": 0, "platform": 1}}]'
                await self._ws.send_str(auth_payload)
            else:
                logger.error("❌ كود المصادقة غير صالح أو قصير جداً")

    async def _message_handler(self):
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.data
                    if data.startswith('2'): # Ping
                        await self._ws.send_str('3')
                    elif data.startswith('42'):
                        try:
                            parsed = json.loads(data[2:])
                            event = parsed[0]
                            payload = parsed[1]
                            
                            if event == "success_auth" or (isinstance(payload, dict) and payload.get("authorized")):
                                self._authenticated = True
                            elif event == "candles" or event == "load_candles":
                                asset = payload.get("asset")
                                candles = payload.get("candles") or payload.get("data")
                                if asset and candles:
                                    self.last_candles[asset] = candles
                        except: pass
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except: pass
        self._connected = False
        self._authenticated = False

    async def disconnect(self):
        self._connected = False
        self._authenticated = False
        try:
            if self._ws: await self._ws.close()
            if self._session: await self._session.close()
        except: pass

    async def get_candles(self, asset: str, count: int = CANDLES_COUNT) -> Optional[pd.DataFrame]:
        if not self._authenticated:
            if not await self.connect(): return None

        try:
            # طلب الشموع
            req = f'42["get_candles", {{"asset": "{asset}", "period": {CANDLE_PERIOD_SECONDS}, "count": {count}}}]'
            await self._ws.send_str(req)
            
            # انتظار البيانات
            start_time = time.time()
            while time.time() - start_time < 8:
                if asset in self.last_candles:
                    data = self.last_candles.pop(asset)
                    return self._to_df(data)
                await asyncio.sleep(0.5)
        except:
            self._authenticated = False
        return None

    def _to_df(self, candles):
        try:
            df = pd.DataFrame(candles)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except: return None

pocket_option_service = PocketOptionService()
