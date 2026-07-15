"""
اکتشاف: بررسی edge با استفاده از VWAP روزانه (session-anchored) + رژیم روند + ساعت.
هدف: کشف اینکه آیا ترکیب فاصله از VWAP + جهت روند + پنجره ساعتی درست، یک
edge جهت‌دار واقعی می‌سازد یا نه — قبل از اینکه استراتژی کامل بنویسیم.

نکته‌ی متدولوژیک (درس استراتژی ۱۳): اینجا P(win) را با ورود در OPEN کندل بعدی
حساب می‌کنیم (نه close همان کندل) تا از تله‌ی look-ahead درون‌کندلی پرهیز شود.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
import indicators as ind

df = pd.read_csv('data/XAUUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s')
df['hour'] = df['dt'].dt.hour
df['date'] = df['dt'].dt.date

close = df['close']; high = df['high']; low = df['low']; openp = df['open']
vol = df['volume']

# --- VWAP لنگرشده به هر روز (session-anchored daily VWAP) ---
tp = (high + low + close) / 3.0            # typical price
pv = tp * vol
df['cum_pv'] = pv.groupby(df['date']).cumsum()
df['cum_v']  = vol.groupby(df['date']).cumsum()
df['vwap'] = df['cum_pv'] / df['cum_v']

atr = ind.atr(df, 14)
ema50 = ind.ema(close, 50)
ema200 = ind.ema(close, 200)
rsi14 = ind.rsi(close, 14)
adx14, pdi, mdi = ind.adx(df, 14)

df['atr'] = atr; df['ema50'] = ema50; df['ema200'] = ema200
df['rsi14'] = rsi14; df['adx'] = adx14

# فاصله‌ی نرمال‌شده از VWAP بر حسب ATR
df['vwap_dist_atr'] = (close - df['vwap']) / atr
# فاصله از EMA50 بر حسب ATR (برای snapback)
df['ema50_dist_atr'] = (close - ema50) / atr

o = openp.values; h = high.values; l = low.values; c = close.values
n = len(df)

def p_win(mask, direction, tp_mult, sl_mult, max_hold=48, spread=0.20):
    """احتمال رسیدن به TP قبل از SL با ورود در OPEN کندل بعدی."""
    atrv = atr.values
    idx = np.where(mask.values)[0]
    wins = 0; total = 0
    for si in idx:
        eb = si + 1
        if eb >= n: continue
        a = atrv[si]
        if not np.isfinite(a) or a <= 0: continue
        if direction == 'long':
            fill = o[eb] + spread
            slp = fill - sl_mult*a; tpp = fill + tp_mult*a
        else:
            fill = o[eb] - spread
            slp = fill + sl_mult*a; tpp = fill - tp_mult*a
        res = None
        for j in range(eb, min(eb+max_hold, n)):
            if direction == 'long':
                hs = l[j] <= slp; ht = h[j] >= tpp
            else:
                hs = h[j] >= slp; ht = l[j] <= tpp
            if hs and ht: res='loss'; break
            elif ht: res='win'; break
            elif hs: res='loss'; break
        if res is None:
            continue  # صرف‌نظر از معاملات بی‌نتیجه در اکتشاف
        total += 1
        if res=='win': wins += 1
    return (wins/total*100 if total else 0), total

# baseline
print("=== BASELINE (بدون فیلتر، long، TP1/SL1) ===")
base = pd.Series(True, index=df.index)
base.iloc[:300] = False
wr, tot = p_win(base, 'long', 1.0, 1.0)
print(f"baseline long TP1/SL1: WR={wr:.2f}% n={tot}")

print("\n=== اثر پنجره ساعتی (long، روند صعودی close>ema50>ema200، TP1/SL1) ===")
uptrend = (close > ema50) & (ema50 > ema200)
for h0, h1 in [(0,6),(6,12),(7,11),(12,17),(13,17),(13,16),(15,18),(19,23),(20,23)]:
    m = uptrend & (df['hour']>=h0) & (df['hour']<h1) & base
    wr, tot = p_win(m, 'long', 1.0, 1.0)
    print(f"  hour[{h0:02d}-{h1:02d}) uptrend: WR={wr:.2f}% n={tot}")

print("\n=== VWAP snapback: long وقتی قیمت زیر VWAP در روند صعودی (mean-reversion in trend) ===")
for dist in [-0.5, -1.0, -1.5]:
    m = uptrend & (df['vwap_dist_atr'] < dist) & base
    wr, tot = p_win(m, 'long', 1.0, 1.0)
    print(f"  close<VWAP-{abs(dist)}ATR uptrend: WR={wr:.2f}% n={tot}")

print("\n=== EMA50 snapback: long وقتی قیمت زیر EMA50 اما روند بلندمدت صعودی ===")
for dist in [-0.5, -1.0, -1.5]:
    m = (close < ema50) & (ema50 > ema200) & (df['ema50_dist_atr'] < dist) & base
    wr, tot = p_win(m, 'long', 1.0, 1.0)
    print(f"  close<EMA50-{abs(dist)}ATR & ema50>ema200: WR={wr:.2f}% n={tot}")

print("\n=== ترکیب: snapback زیر VWAP + روند + پنجره فعال (13-17 یا 19-23) ===")
for h0,h1 in [(13,17),(19,23),(12,23)]:
    for dist in [-0.3,-0.7,-1.0]:
        m = uptrend & (df['vwap_dist_atr'] < dist) & (df['hour']>=h0) & (df['hour']<h1) & base
        wr, tot = p_win(m,'long',1.0,1.0)
        print(f"  h[{h0}-{h1}) close<VWAP-{abs(dist)}ATR uptrend: WR={wr:.2f}% n={tot}")
