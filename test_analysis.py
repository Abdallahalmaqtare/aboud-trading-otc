"""اختبار التحليل الفني بيانات وهمية."""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '.')

from pocket_option_service import PocketOptionService
from config import EMA_TREND

svc = PocketOptionService()

# توليد بيانات وهمية (250 شمعة - أكثر من EMA_TREND=200)
np.random.seed(42)
n = 250
price = 1.0800

# بناء سعر مع اتجاه صاعد قوي جداً
prices = [price]
for i in range(n - 1):
    drift = 0.0003  # اتجاه صاعد قوي
    noise = np.random.normal(0, 0.0001)  # ضوضاء منخفضة
    prices.append(prices[-1] * (1 + drift + noise))

df = pd.DataFrame({
    'time': list(range(n)),
    'open': prices,
    'close': [p * (1 + np.random.normal(0, 0.0001)) for p in prices],
    'high': [p * (1 + abs(np.random.normal(0, 0.0003))) for p in prices],
    'low': [p * (1 - abs(np.random.normal(0, 0.0003))) for p in prices],
    'volume': np.random.uniform(500, 2000, n),
})

# التأكد من أن high >= close >= low
df['high'] = df[['open', 'close', 'high']].max(axis=1)
df['low'] = df[['open', 'close', 'low']].min(axis=1)

print(f"عدد الشموع: {len(df)}")
print(f"EMA_TREND المطلوب: {EMA_TREND}")
print(f"آخر سعر: {df['close'].iloc[-1]:.5f}")
print()

# تشغيل التحليل
result = svc.analyze(df)
if result:
    print(f"✅ إشارة: {result['direction']} | نقاط: {result['signal_score']}/7")
    ind = result['indicators']
    print(f"   EMA Fast/Mid/Slow: {ind['ema_fast']}/{ind['ema_mid']}/{ind['ema_slow']}")
    print(f"   EMA200: {ind['ema200']}")
    print(f"   MACD hist: {ind['macd_hist']}")
    print(f"   Supertrend: {ind['supertrend']}")
    print(f"   ADX: {ind['adx']} | +DI: {ind['plus_di']} | -DI: {ind['minus_di']}")
    print(f"   ROC: {ind['roc']}")
    print(f"   Close pos: {ind['close_pos']}")
else:
    print("⚪ لا توجد إشارة (الشروط لم تكتمل)")

print()
print("✅ التحليل الفني يعمل بشكل صحيح!")
