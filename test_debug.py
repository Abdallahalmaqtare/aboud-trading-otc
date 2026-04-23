"""اختبار تشخيصي للمؤشرات."""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '.')

from pocket_option_service import PocketOptionService
from config import EMA_FAST, EMA_MID, EMA_SLOW, EMA_TREND, ADX_MIN_THRESHOLD, MIN_SIGNAL_SCORE

svc = PocketOptionService()

np.random.seed(42)
n = 250
price = 1.0800

prices = [price]
for i in range(n - 1):
    drift = 0.0003
    noise = np.random.normal(0, 0.0001)
    prices.append(prices[-1] * (1 + drift + noise))

df = pd.DataFrame({
    'time': list(range(n)),
    'open': prices,
    'close': [p * (1 + np.random.normal(0, 0.00005)) for p in prices],
    'high': [p * (1 + abs(np.random.normal(0, 0.0002))) for p in prices],
    'low': [p * (1 - abs(np.random.normal(0, 0.0002))) for p in prices],
    'volume': np.random.uniform(500, 2000, n),
})
df['high'] = df[['open', 'close', 'high']].max(axis=1)
df['low'] = df[['open', 'close', 'low']].min(axis=1)

close = df['close']
high = df['high']
low = df['low']
volume = df['volume']

ema_fast = svc.calculate_ema(close, EMA_FAST)
ema_mid = svc.calculate_ema(close, EMA_MID)
ema_slow = svc.calculate_ema(close, EMA_SLOW)
ema_trend = svc.calculate_ema(close, EMA_TREND)
macd_line, signal_line, histogram = svc.calculate_macd(close)
st_direction = svc.calculate_supertrend(df)
adx, plus_di, minus_di = svc.calculate_adx(df)
roc = svc.calculate_roc(close)
vol_sma = volume.rolling(window=20).mean()

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

candle_range = high.iloc[i] - low.iloc[i]
close_pos = (c - low.iloc[i]) / candle_range if candle_range > 0 else 0.5

print("=" * 50)
print("تشخيص المؤشرات - آخر شمعة")
print("=" * 50)
print(f"السعر: {c:.5f}")
print(f"EMA Fast ({EMA_FAST}): {ef:.5f}")
print(f"EMA Mid ({EMA_MID}): {em:.5f}")
print(f"EMA Slow ({EMA_SLOW}): {es:.5f}")
print(f"EMA Trend ({EMA_TREND}): {et:.5f}")
print()
print(f"EMA alignment CALL (ef>em>es): {ef > em > es}")
print(f"Price above EMA200: {c > et}")
print(f"MACD hist: {hist:.6f} (prev: {hist_prev:.6f})")
print(f"MACD bullish: {hist > 0 and hist > hist_prev}")
print(f"Supertrend direction: {st_dir} ({'UP' if st_dir > 0 else 'DOWN'})")
print(f"ADX: {adx_val:.2f} (min: {ADX_MIN_THRESHOLD})")
print(f"+DI: {pdi:.2f} | -DI: {mdi:.2f}")
print(f"ADX OK for CALL: {adx_val >= ADX_MIN_THRESHOLD and pdi > mdi}")
print(f"ROC: {roc_val:.4f}")
print(f"ROC OK for CALL: {roc_val >= 0.05}")
print(f"Volume: {vol_now:.0f} | Avg: {vol_avg:.0f}")
print(f"Volume confirmation: {vol_now > vol_avg * 1.2 and c > df['open'].iloc[i]}")
print(f"Close position: {close_pos:.3f}")
print()

score_ema = 1 if ef > em > es else 0
score_trend = 1 if c > et else 0
score_macd = 1 if hist > 0 and hist > hist_prev else 0
score_st = 1 if st_dir > 0 else 0
score_adx = 1 if adx_val >= ADX_MIN_THRESHOLD and pdi > mdi else 0
score_vol = 1 if vol_now > vol_avg * 1.2 and c > df['open'].iloc[i] else 0
score_close = 1 if close_pos >= 0.7 else 0

call_score = score_ema + score_trend + score_macd + score_st + score_adx + score_vol + score_close
print(f"نقاط CALL: {call_score}/7")
print(f"  EMA alignment: {score_ema}")
print(f"  Trend filter: {score_trend}")
print(f"  MACD: {score_macd}")
print(f"  Supertrend: {score_st}")
print(f"  ADX: {score_adx}")
print(f"  Volume: {score_vol}")
print(f"  Close pos: {score_close}")
print()
print(f"الحد الأدنى: {MIN_SIGNAL_SCORE}/7")
adx_gate = adx_val >= ADX_MIN_THRESHOLD and pdi > mdi
roc_gate = roc_val >= 0.05
print(f"بوابة ADX: {adx_gate}")
print(f"بوابة ROC: {roc_gate}")
print()
if call_score >= MIN_SIGNAL_SCORE and adx_gate and roc_gate:
    print("✅ إشارة CALL ستُرسل!")
else:
    print("⚪ لا إشارة - الأسباب:")
    if call_score < MIN_SIGNAL_SCORE:
        print(f"   - النقاط ({call_score}) أقل من الحد الأدنى ({MIN_SIGNAL_SCORE})")
    if not adx_gate:
        print(f"   - ADX ({adx_val:.1f}) أو DI لا يستوفي الشرط")
    if not roc_gate:
        print(f"   - ROC ({roc_val:.4f}) أقل من 0.05")
