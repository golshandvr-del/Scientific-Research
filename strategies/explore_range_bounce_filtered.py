"""
اکتشافِ فاز ۲ — رنج‌بونسِ *فیلترشده* (کیفیتِ برگشت) — User Note (نکتهٔ دوم).

یافتهٔ فاز ۱ (explore_range_bounce.py): رنج‌بونسِ خام روی لبهٔ Donchian دقیقاً روی
نرخِ سربه‌سر می‌نشیند (WR≈BE) — edge نازک است (تأییدِ دوبارهٔ درسِ L29). تنها نقطهٔ
کمی مثبت: LONG با TP=1.0/SL=1.5 (WR≈61٪ در برابر BE=60٪) هم‌راستا با drift صعودیِ طلا.

فرضیهٔ فاز ۲: برگشت وقتی edge دارد که لبه با «نشانهٔ خستگی/رد» تأیید شود، نه صرفِ
لمسِ کورِ لبه. سه فیلتر را جدا و ترکیبی می‌سنجیم:

  F1) RSI اشباع: LONG وقتی RSI<35 نزدیکِ کف؛ SHORT وقتی RSI>65 نزدیکِ سقف.
  F2) کندلِ ردی (rejection/pin): سایهٔ بلند در جهتِ لبه (بازار لبه را رد کرد).
  F3) بازگشتِ داخل‌کانالی: close دوباره داخلِ کانال بسته شد (نه شکستِ ادامه‌دار).

معیار: نرخِ برد با first-touch TP/SL (ATR-based) + میانگینِ R خالص (net بعد از اسپرد).
هدفِ نهاییِ پروژه = سودِ خالص، پس expectancy مهم‌تر از WR است.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data(); n = len(df)
c = df['close'].values; h = df['high'].values; l = df['low'].values; o = df['open'].values
atr = ind.atr(df, 14).values
adx_series, _, _ = ind.adx(df, 14); adx = adx_series.values
rsi = ind.rsi(df['close'], 14).values
SPREAD = 0.20
print(f"داده: {n} کندل XAUUSD M15")

ADX_TH = 22
DON = 32
EDGE_FRAC = 0.20
HORIZON = 24

hh = pd.Series(h).rolling(DON).max().shift(1).values
ll = pd.Series(l).rolling(DON).min().shift(1).values
width = hh - ll
range_regime = (adx < ADX_TH) & ~np.isnan(hh) & (width > 0)
dist_low = (c - ll) / width
dist_high = (hh - c) / width

# فیلترها -------------------------------------------------------------------
# F2: کندلِ ردِ کف (pin پایین) = سایهٔ پایینِ بلند و close نزدیکِ high کندل
lower_wick = (np.minimum(o, c) - l)
upper_wick = (h - np.maximum(o, c))
body = np.abs(c - o) + 1e-9
pin_up = lower_wick > 1.2 * body      # ردِ کف → سیگنالِ LONG
pin_down = upper_wick > 1.2 * body    # ردِ سقف → سیگنالِ SHORT

def simulate(sig_idx, is_long, tp_m, sl_m):
    """first-touch؛ برمی‌گرداند (WR, exp_R_net, n). exp بر حسبِ R خالص با اسپرد."""
    wins = 0; tot = 0; sumR = 0.0
    for i in sig_idx:
        eb = i + 1
        if eb + HORIZON >= n:
            continue
        a = atr[i]
        if not (a > 0):
            continue
        entry = c[i]
        tp = tp_m * a; sl = sl_m * a
        hit = None
        for j in range(eb, eb + HORIZON):
            hi = h[j]; lo = l[j]
            if is_long:
                tp_hit = hi >= entry + tp; sl_hit = lo <= entry - sl
            else:
                tp_hit = lo <= entry - tp; sl_hit = hi >= entry + sl
            if tp_hit and sl_hit: hit = 'sl'; break
            if tp_hit: hit = 'tp'; break
            if sl_hit: hit = 'sl'; break
        if hit is None:
            continue
        tot += 1
        if hit == 'tp':
            wins += 1
            sumR += tp_m - SPREAD / a     # R خالص = TP − اسپرد (بر حسبِ ATR)
        else:
            sumR += -(sl_m + SPREAD / a)
    wr = wins / tot * 100 if tot else 0
    exp = sumR / tot if tot else 0
    return wr, exp, tot

configs = [('خام', None), ('F1 RSI', 'rsi'), ('F2 pin', 'pin'), ('F1+F2', 'both')]
TP_M, SL_M = 1.0, 1.5
BE = SL_M / (TP_M + SL_M) * 100
print(f"\nDON={DON} ADX<{ADX_TH} TP={TP_M}×/SL={SL_M}× (BE={BE:.0f}%) اسپرد={SPREAD}$")
print("=" * 68)
for name, filt in configs:
    if filt == 'rsi':
        lmask = range_regime & (dist_low < EDGE_FRAC) & (rsi < 35)
        smask = range_regime & (dist_high < EDGE_FRAC) & (rsi > 65)
    elif filt == 'pin':
        lmask = range_regime & (dist_low < EDGE_FRAC) & pin_up
        smask = range_regime & (dist_high < EDGE_FRAC) & pin_down
    elif filt == 'both':
        lmask = range_regime & (dist_low < EDGE_FRAC) & (rsi < 35) & pin_up
        smask = range_regime & (dist_high < EDGE_FRAC) & (rsi > 65) & pin_down
    else:
        lmask = range_regime & (dist_low < EDGE_FRAC)
        smask = range_regime & (dist_high < EDGE_FRAC)
    lw, le, ln = simulate(np.where(lmask)[0], True, TP_M, SL_M)
    sw, se, sn = simulate(np.where(smask)[0], False, TP_M, SL_M)
    print(f"{name:8s}: LONG WR={lw:.1f}% expR={le:+.3f} n={ln:5d} | "
          f"SHORT WR={sw:.1f}% expR={se:+.3f} n={sn:5d}")
