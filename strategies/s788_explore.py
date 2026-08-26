# -*- coding: utf-8 -*-
"""
S788 — فاز اکتشاف: عبور افت-از-قلهٔ نرمال‌شده (Drawdown-Threshold Crossing)
============================================================================
کشف فقط روی ۶۰٪ نخست دادهٔ کامل ۱۵.۶ ساله؛ ۴۰٪ پایانی لمس نمی‌شود.
انضباط: هیچ نامزدی بدون z_alpha >= 3.09 به داوری نمی‌رود (درس S780-S787).
در صورت یافتن نامزد، داوری روی کل داده با split_bar=60% (الگوی S602/S770/S800/S950).

فرضیه: رویداد گسستهٔ «افت از قلهٔ غلتان W-کندلی برای اولین بار از آستانهٔ
T×ATR عبور می‌کند» (یک‌بار در هر گردش؛ ریست با قلهٔ جدید) در H8/H12/D1 طلا
جهت‌دار است — یا بازگشت به روند گاوی (rev=long) یا ادامهٔ آبشار (cont=short).
خانوادهٔ drawdown-crossing هرگز در پروژه آزموده نشده (grep تأیید شد).

خانوادهٔ کامل پیش‌اعلام: 3TF × 2W × 3T × 2mode × 2k_sl × 2RR = 144 عضو.
"""
import os, sys, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s788')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
TFS = ['H8', 'H12', 'D1']
PEAK_WINS = [89, 144]                      # پنجرهٔ قلهٔ غلتان (فیبوناچی)
THRESHOLDS = [4.181, 6.765, 10.946]        # آستانهٔ افت بر حسب ×ATR89 (لوکاس/فیبو-گونه)
MODES = ['rev', 'cont']                    # rev=long بازگشت، cont=short ادامهٔ آبشار
K_SLS = [1.618, 2.058]
RRS = [1.0, 1.272]
MAX_HOLD = 21
DISC_FRAC = 0.60
PIP = 0.10


def causal_atr(df, period=89):
    """ATR علّی بر حسب قیمت (نه پیپ)؛ shift(1)."""
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(period).mean().shift(1).values


def dd_cross_events(df, W, T, atr):
    """رویداد: افت از قلهٔ غلتان W برای اولین بار از T×ATR عبور می‌کند.
    یک‌بار در هر گردش؛ ریست وقتی قلهٔ جدید ثبت شود (dd به صفر برگردد)."""
    c = df['close'].values
    peak = pd.Series(c).rolling(W).max().shift(1).values
    dd = peak - c                       # افت بر حسب قیمت
    thr = T * atr
    n = len(c)
    ev = np.zeros(n, dtype=bool)
    armed = True
    for i in range(n):
        if not np.isfinite(dd[i]) or not np.isfinite(thr[i]):
            continue
        if dd[i] <= 0:                  # قلهٔ جدید → مسلح شدن دوباره
            armed = True
        elif armed and dd[i] >= thr[i]:
            ev[i] = True
            armed = False
    return ev


def simulate(df, ev_idx, side, k_sl, rr, atr_pips, max_hold):
    """شبیه‌سازی intrabar محافظه‌کارانه (SL مقدم در برخورد همزمان)."""
    o, h, l, c = (df['open'].values, df['high'].values,
                  df['low'].values, df['close'].values)
    spread = 3.3 * PIP
    outs, nets, times = [], [], []
    n = len(c)
    for i in ev_idx:
        if i + 1 >= n or not np.isfinite(atr_pips[i]):
            continue
        sl_p = k_sl * atr_pips[i] * PIP
        tp_p = rr * sl_p
        if side == 'long':
            entry = o[i + 1] + spread
            sl, tp = entry - sl_p, entry + tp_p
        else:
            entry = o[i + 1]
            sl, tp = entry + sl_p + spread, entry - tp_p + spread
        res = None
        j_end = min(i + 1 + max_hold, n)
        for j in range(i + 1, j_end):
            if side == 'long':
                if l[j] <= sl: res = -sl_p; break
                if h[j] >= tp: res = +tp_p; break
            else:
                if h[j] + spread >= sl: res = -sl_p; break
                if l[j] + spread <= tp: res = +tp_p; break
        if res is None:
            res = (c[j_end - 1] - entry) if side == 'long' else (entry - c[j_end - 1] - spread)
        outs.append(1 if res > 0 else 0)
        nets.append(res / PIP)          # پیپ
        times.append(df['time'].values[i])
    return np.array(outs), np.array(nets), np.array(times)


def uncond_wr(df, side, k_sl, rr, atr_pips, max_hold):
    """WR غیرشرطی هم‌هندسه؛ بیشینه روی strideهای 1/3/7."""
    n = len(df)
    best = 0.0
    for stride in (1, 3, 7):
        idx = np.arange(100, n - max_hold - 2, stride)
        outs, _, _ = simulate(df, idx, side, k_sl, rr, atr_pips, max_hold)
        if len(outs) > 100:
            best = max(best, 100.0 * outs.mean())
    return best


def main():
    rows = []
    data = {}
    for tf in TFS:
        d = fd.load_fast(ASSET, tf)
        assert 'mt5_full' in d['src'], f"E-16 trap: {d['src']}"
        df = fd.as_dataframe(d)
        cut = int(len(df) * DISC_FRAC)
        data[tf] = df.iloc[:cut].reset_index(drop=True)
        print(f"{tf}: full={len(df)} disc={cut} src=mt5_full", flush=True)

    # WR غیرشرطی کش‌شده به‌ازای (tf, side, k_sl, rr)
    ucache = {}
    for tf, W, T, mode, k_sl, rr in itertools.product(
            TFS, PEAK_WINS, THRESHOLDS, MODES, K_SLS, RRS):
        df = data[tf]
        atr = causal_atr(df, 89)
        atr_pips = atr / PIP
        ev = dd_cross_events(df, W, T, atr)
        ev_idx = np.where(ev)[0]
        side = 'long' if mode == 'rev' else 'short'
        outs, nets, _ = simulate(df, ev_idx, side, k_sl, rr, atr_pips, MAX_HOLD)
        n = len(outs)
        if n < 30:
            rows.append(dict(tf=tf, W=W, T=T, mode=mode, k_sl=k_sl, rr=rr,
                             n=n, wr=np.nan, p0=np.nan, alpha=np.nan,
                             z=np.nan, net=np.nan))
            continue
        key = (tf, side, k_sl, rr)
        if key not in ucache:
            ucache[key] = uncond_wr(df, side, k_sl, rr, atr_pips, MAX_HOLD)
        p0 = ucache[key]
        wr = 100.0 * outs.mean()
        alpha = wr - p0
        p0f = max(min(p0 / 100.0, 0.999), 0.001)
        z = (alpha / 100.0) * np.sqrt(n) / np.sqrt(p0f * (1 - p0f))
        rows.append(dict(tf=tf, W=W, T=T, mode=mode, k_sl=k_sl, rr=rr,
                         n=n, wr=round(wr, 2), p0=round(p0, 2),
                         alpha=round(alpha, 2), z=round(z, 2),
                         net=round(nets.sum(), 0)))
        print(f"{tf} W={W} T={T} {mode} k={k_sl} rr={rr}: "
              f"n={n} wr={wr:.1f} p0={p0:.1f} a={alpha:+.2f} z={z:+.2f} "
              f"net={nets.sum():+.0f}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, 'explore_discovery.csv'), index=False)
    ok = out.dropna(subset=['z']).sort_values('z', ascending=False)
    print("\n=== TOP 10 by z ===")
    print(ok.head(10).to_string(index=False))
    print(f"\nfamily members this round: {len(rows)}")


if __name__ == '__main__':
    main()
