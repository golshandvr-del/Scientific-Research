# -*- coding: utf-8 -*-
"""
S341d — ممیزیِ همپوشانیِ اجباری برای لایه‌های ACCEPTِ S341 (XAU M5/M15/M30 LONG).
همپوشانی = اشتراکِ کندل‌های ورودِ S341 با کندل‌های ورودِ لایه‌های LONGِ موجودِ همان کارت،
سنجیده بر پایهٔ نزدیکیِ زمانی (پنجرهٔ ±tol کندل). خروجی: درصدِ همپوشانی هر لایهٔ موجود.

چون لایه‌های موجودِ پروژه در TS زندگی می‌کنند، اینجا هم‌ارزِ پایتونیِ ساده‌ی مفهومیِ آن‌ها را
به‌عنوانِ «رویدادِ ورود» بازتولید می‌کنیم (نه بیت‌به‌بیت، بلکه برای سنجشِ اشتراکِ زمانی):
  - S333 (pullback LONG): pullback به EMA در روندِ صعودی.
  - S335 (Reflex cycle LONG): کفِ چرخه.
  - S334 (MR fade SELL): جهتِ مخالف ⇒ همپوشانیِ ورودیِ صفر (short).
مهم‌تر از همه: چون S341 در **رژیمِ رنجِ سخت** (chop≥58/61.8, r2 پایین) فعال است و لایه‌های روندی
(S333/S335) در **رژیمِ روند** فعال‌اند، انتظارِ نظری همپوشانیِ نزدیک به صفر است. این را کمّی می‌کنیم.
"""
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib
from strategies.s341_brooks_swing_levels import _fractal_levels

ACCEPTED = {
    'XAUUSD-M5':  dict(tf='M5',  side='long', w=4, buf=0.05, sec=True, sl=180, tp=260, mh=48,
                       chop_min=61.8, r2_max=0.22, er_max=0.16),
    'XAUUSD-M15': dict(tf='M15', side='long', w=4, buf=0.15, sec=True, sl=280, tp=620, mh=40,
                       chop_min=61.8, r2_max=0.22, er_max=0.16),
    'XAUUSD-M30': dict(tf='M30', side='long', w=8, buf=0.15, sec=True, sl=380, tp=840, mh=18,
                       chop_min=58, r2_max=0.30, er_max=0.22),
}


def s341_entries(df, cfg):
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    atr = ib.atr_s(df, p=14).to_numpy()
    ch = ib.chop(df, p=14).to_numpy(); r2 = ib.r2(df, p=20).to_numpy()
    er = np.abs(ib.compute('er_lucas_11', df).to_numpy())
    reg = np.isfinite(ch) & np.isfinite(r2) & np.isfinite(er) & \
          (ch >= cfg['chop_min']) & (r2 <= cfg['r2_max']) & (er <= cfg['er_max'])
    last_sh, last_sl = _fractal_levels(h, l, cfg['w'])
    n = len(df); sig = np.zeros(n, bool); recent = []
    for i in range(cfg['w'] + 2, n):
        if not reg[i]:
            continue
        a = atr[i]
        if not (a > 0):
            continue
        buf = cfg['buf'] * a
        lvl = last_sl[i]
        if not np.isfinite(lvl):
            continue
        if (l[i] < lvl - buf) and (c[i] > lvl):
            recent = [x for x in recent if x >= i - 40]
            recent.append(i)
            if cfg['sec'] and len(recent) < 2:
                continue
            sig[i] = True
    return np.where(sig)[0]


def _ema(x, p):
    import pandas as pd
    return pd.Series(x).ewm(span=p, adjust=False).mean().to_numpy()


def trend_long_events(df):
    """پروکسیِ ورودهای LONGِ روندی (S333/S335-گونه): pullback به EMA در روندِ صعودی."""
    c = df['close'].to_numpy(float); l = df['low'].to_numpy(float)
    e20 = _ema(c, 20); e50 = _ema(c, 50)
    up = e20 > e50
    pull = (l <= e20) & (c > e20)  # لمسِ EMA و بازگشت
    ev = up & pull
    return np.where(ev)[0]


def overlap_pct(a_idx, b_idx, tol=2):
    """درصدِ ورودهای a که در ±tol کندلِ یک ورودِ b قرار دارند."""
    if len(a_idx) == 0:
        return 0.0, 0
    b = np.sort(b_idx)
    hit = 0
    for x in a_idx:
        pos = np.searchsorted(b, x)
        near = False
        for k in (pos - 1, pos):
            if 0 <= k < len(b) and abs(b[k] - x) <= tol:
                near = True; break
        if near:
            hit += 1
    return 100.0 * hit / len(a_idx), len(a_idx)


if __name__ == '__main__':
    for card, cfg in ACCEPTED.items():
        df = se.load_data(f"data/XAUUSD_{cfg['tf']}.csv")
        a = s341_entries(df, cfg)
        tl = trend_long_events(df)
        ov, na = overlap_pct(a, tl, tol=2)
        # همپوشانی با ورودهای شبانه/زمان‌محور (S139-گونه) — پروکسی: ساعتِ ۱ تا ۳ UTC
        hours = (df['dt'].dt.hour.to_numpy())
        night = np.where((hours >= 1) & (hours <= 3))[0]
        ovn, _ = overlap_pct(a, night, tol=0)
        print(f"{card}: S341 entries n={na} | overlap vs trend-LONG(EMA-pullback) = {ov:.1f}% | "
              f"overlap vs night-window = {ovn:.1f}%")
