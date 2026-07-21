# -*- coding: utf-8 -*-
"""
s148_ma_pullback_both.py — استراتژیِ «MA-Pullback دوطرفه» (الگوی بصریِ ۱+۲)
============================================================================
کشفِ بصری (دفترچهٔ مشاهدات، الگوی ۱+۲):
  در روندِ صعودی، قیمت مکرراً به MA20/MA50 پولبک می‌کند و صعود را ادامه می‌دهد؛
  در روندِ نزولی، قرینهٔ آن رخ می‌دهد (رالی به MA رد می‌شود و ریزش ادامه می‌یابد).
  این پرتکرارترین الگوی مشاهده‌شده در همهٔ تایم‌فریم‌ها بود (D1/H4/H1/M15).

منطقِ ورود:
  رژیم = علامتِ (EMA_fast − EMA_slow).
  • رژیمِ صعودی (fast>slow): منتظرِ پولبک به EMA_fast می‌مانیم؛ وقتی قیمت EMA_fast را
    لمس می‌کند (low≤EMA_fast) و سپس کندلِ صعودیِ تأیید بسته می‌شود ⇒ LONG.
  • رژیمِ نزولی (fast<slow): وقتی قیمت EMA_fast را از پایین لمس می‌کند
    (high≥EMA_fast) و کندلِ نزولیِ تأیید بسته می‌شود ⇒ SHORT.

هزینهٔ واقعیِ حساب کاربر (market_spec): ۳.۳ pip اسپرد، بدونِ کمیسیون؛ CONTRACT=100.
خروج: SL/TP/BE/trailing مبتنی بر ATR (مثلِ بقیهٔ لایه‌ها).

قانونِ شمارهٔ ۱: معیار فقط **سودِ خالص** (XAUUSD + EURUSD). WR ملاک نیست.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from strategies.s147_vshape_dipbuy import (
    load, atr_np, backtest_trail, ev, wf_folds, per_year,
    PIP, CONTRACT, COST_PRICE, COMMISSION, _ema,
)


def gen_ma_pullback(df, ema_fast=20, ema_slow=50, cooldown=6, touch_atr=0.25,
                    atr_arr=None, direction='both'):
    """سیگنالِ MA-pullback دوطرفه.

    direction: 'both' | 'long' | 'short'
    touch_atr: نزدیکیِ لازم به EMA_fast برحسبِ ATR برای «لمسِ» پولبک.
    خروجی: آرایهٔ sig با مقادیرِ +1 (long) / -1 (short) / 0.
    """
    o = df['open'].values; c = df['close'].values
    h = df['high'].values; l = df['low'].values
    n = len(df)
    ef = _ema(c, ema_fast)
    es = _ema(c, ema_slow)
    if atr_arr is None:
        atr_arr = atr_np(df, 14)
    sig = np.zeros(n, dtype=np.int8)
    last = -10**9
    start = ema_slow + 2
    for i in range(start, n - 1):
        if i - last < cooldown:
            continue
        a = atr_arr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        up_regime = ef[i] > es[i]
        dn_regime = ef[i] < es[i]
        near = touch_atr * a
        # --- LONG: روندِ صعودی + پولبک به EMA_fast + کندلِ تأییدِ صعودی ---
        if up_regime and direction in ('both', 'long'):
            touched = l[i] <= ef[i] + near          # قیمت به میانگین پولبک کرد
            above = c[i] > es[i]                     # هنوز بالای میانگینِ کند (روند حفظ)
            confirm = c[i] > o[i]                    # کندلِ صعودیِ تأیید
            if touched and above and confirm:
                sig[i] = 1; last = i; continue
        # --- SHORT: روندِ نزولی + رالی به EMA_fast + کندلِ تأییدِ نزولی ---
        if dn_regime and direction in ('both', 'short'):
            touched = h[i] >= ef[i] - near
            below = c[i] < es[i]
            confirm = c[i] < o[i]
            if touched and below and confirm:
                sig[i] = -1; last = i; continue
    return sig


def backtest_both(df, sig, atr_arr, sl_mult, tp_mult, be_trig, trail_mult, max_hold):
    """پشتیبانِ سیگنالِ دوطرفه: long و short را جداگانه شبیه‌سازی و ادغام می‌کند.

    backtest_trail فرض می‌کند sig∈{0,1} برای long؛ برای short با قرینه‌سازیِ قیمت
    از همان موتور استفاده می‌کنیم (mirror trick) تا حسابداری یکسان بماند.
    """
    # LONG
    sig_l = (sig == 1).astype(np.int8)
    trd_l, sld_l = backtest_trail(df, sig_l, atr_arr, sl_mult, tp_mult,
                                  be_trig, trail_mult, max_hold)
    trd_l = trd_l.copy(); trd_l['dir'] = 1
    # SHORT via mirror: قیمت را حولِ یک ثابت قرینه می‌کنیم تا long روی آینه = short واقعی
    mir = df.copy()
    pivot = df['close'].iloc[0] * 2.0
    for col in ('open', 'close'):
        mir[col] = pivot - df[col]
    # high/low جابه‌جا و قرینه می‌شوند
    mir['high'] = pivot - df['low']
    mir['low'] = pivot - df['high']
    sig_s = (sig == -1).astype(np.int8)
    trd_s, sld_s = backtest_trail(mir, sig_s, atr_arr, sl_mult, tp_mult,
                                  be_trig, trail_mult, max_hold)
    trd_s = trd_s.copy(); trd_s['dir'] = -1
    # ادغام و مرتب‌سازی بر اساسِ signal_bar
    trd = pd.concat([trd_l, trd_s], ignore_index=True)
    sld = np.concatenate([sld_l, sld_s]) if len(sld_l) or len(sld_s) else np.array([])
    order = np.argsort(trd['signal_bar'].values)
    trd = trd.iloc[order].reset_index(drop=True)
    sld = sld[order]
    return trd, sld


def run(direction='both', ema_fast=20, ema_slow=50, cooldown=6, touch_atr=0.25,
        sl_mult=2.0, tp_mult=6.0, be_trig=1.5, trail_mult=3.0, max_hold=96,
        tf='M15', verbose=True):
    df = load('XAUUSD', tf)
    atr = atr_np(df, 14)
    n = len(df); mid = n // 2
    sig = gen_ma_pullback(df, ema_fast, ema_slow, cooldown, touch_atr, atr, direction)
    trd, sld = backtest_both(df, sig, atr, sl_mult, tp_mult, be_trig, trail_mult, max_hold)
    s = ev(trd, sld)
    if s is None:
        if verbose:
            print(f"{direction}: no trades")
        return None
    m1 = trd['signal_bar'] < mid
    h1 = ev(trd[m1].reset_index(drop=True), sld[m1.values]) if m1.sum() else None
    h2 = ev(trd[~m1].reset_index(drop=True), sld[(~m1).values]) if (~m1).sum() else None
    folds = wf_folds(trd, sld, n)
    py = per_year(df, trd, sld)
    if verbose:
        both_ok = (h1 and h2 and h1['net_profit'] > 0 and h2['net_profit'] > 0)
        wf_ok = all(f > 0 for f in folds)
        flag = "✅✅" if (both_ok and wf_ok) else ("✅" if both_ok else "")
        print(f"{direction:5s} ef{ema_fast} SL{sl_mult}/TP{tp_mult}/tr{trail_mult}/mh{max_hold}: "
              f"net={s['net_profit']:+.0f}$ n={s['n_trades']} WR={s['win_rate']:.0f}% "
              f"PF={s['profit_factor']:.2f} DD={s['max_dd_pct']:.0f}% "
              f"h1={h1['net_profit'] if h1 else 0:+.0f} h2={h2['net_profit'] if h2 else 0:+.0f} "
              f"WF=[{','.join(f'{f:+.0f}' for f in folds)}] {flag}")
    return dict(stats=s, h1=h1, h2=h2, folds=folds, per_year=py, trd=trd, sld=sld)


if __name__ == '__main__':
    print("=== s148 — MA-Pullback دوطرفه (الگوی بصریِ ۱+۲) ===")
    print(f"COST_PRICE={COST_PRICE:.2f}$/oz ({COST_PRICE*CONTRACT:.0f}$/لات)  comm={COMMISSION}")

    print("\n--- اکتشافِ اولیه: هر جهت جداگانه، پارامترِ پایه ---")
    for d in ('long', 'short', 'both'):
        run(direction=d, sl_mult=2.0, tp_mult=6.0, trail_mult=3.0, max_hold=96)
