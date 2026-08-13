# -*- coding: utf-8 -*-
"""
s450_mgmt_first_hour_low.py — S450 (مأموریت ۵ · مدیریت معامله)
================================================================================
قاعدهٔ پیش‌ثبت‌شده (results/S450_PREREG_MGMT_RULES_PROTOCOL.md §2):
  «خروجِ LONG در شکستِ کفِ ساعتِ اولِ روزِ معاملاتی» — مادهٔ خام M1
  (فاز 15-C2/16-D: sd −51٪، بدترین روز −$505→−$87، سود دست‌نخورده).

روش: بک‌تستِ مقایسه‌ایِ با/بدونِ قاعده روی لایه‌های ACCEPT زندهٔ LONG
با شبیه‌سازِ رویدادمحورِ رسمی (engine/trade_simulator.py):
  baseline  = استراتژیِ لایه، عیناً با پارامترهای ACCEPT
  treatment = همان استراتژی + Wrapper مدیریتی که فقط پس از ورودِ LONG
              فعال است: اگر close کندلِ i < کفِ ساعتِ اولِ روزِ جاری ⇒ CLOSE
              (اجرا روی open کندلِ i+1 — بدونِ look-ahead).

تعریفِ «روزِ معاملاتی» و «ساعتِ اول» (پیش‌ثبت §3 — ضدِ خطای DST):
  - مرزِ روز = گپِ زمانی > ۳۰ دقیقه بین دو کندلِ متوالی (XAUUSD).
  - ساعتِ اول = کندل‌های ۶۰ دقیقهٔ نخست: M15→4، M30→2، H1→1.
  - تا کامل‌شدنِ ساعتِ اولِ روزِ جاری، قاعده خاموش است (سببیت).
  - مرزِ مسئولیت: قاعده SL/TP لحظهٔ ورود را تغییر نمی‌دهد؛ فقط یک
    خروجِ ساختاریِ اضافه پس از ورود است.

اجرا: python3 strategies/s450_mgmt_first_hour_low.py [TF]
      TF ∈ {M30, M15, H1} (پیش‌فرض: هر سه به‌ترتیب M30, M15, H1)
خروجی: JSON خلاصه در research/mgmt/S450_<TF>.json + چاپِ مقایسه.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from strategies.sim_strategies import S312_MidMonth_Long

# پارامترهای ACCEPT (عیناً از strategies/s312_finalize.py::BEST)
BEST = {
    'M15': dict(sl_pip=295, tp_pip=295, max_hold=48, quality_filter=True),
    'M30': dict(sl_pip=295, tp_pip=295, max_hold=36, quality_filter=True),
    'H1':  dict(sl_pip=395, tp_pip=395, max_hold=24, quality_filter=True),
}
FIRST_HOUR_BARS = {'M15': 4, 'M30': 2, 'H1': 1}
TF_MINUTES = {'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240}
# مرزِ روزِ XAUUSD (اصلاحِ باگِ TF-وابسته — کشفِ اجرای اول):
#   فاصلهٔ عادیِ دو کندل = خودِ TF؛ وقفهٔ روزانهٔ بروکر ~۶۰ دقیقه ⇒
#   گپِ مرزِ روز در داده: M15→75، M30→90، H1→120 دقیقه (آخر هفته ~3000).
#   قانونِ خامِ «گپ>۳۰» برای H1 هر کندل را روزِ جدید می‌کرد (قاعده هرگز فعال
#   نمی‌شد) و در M30 گپِ تک‌کندلِ جاافتاده (60min، ۳۹۸ مورد) را مرزِ روزِ کاذب
#   می‌کرد. تعمیمِ صحیحِ همان لنگر: گپ > (TF + ۳۰) دقیقه.
GAP_EXTRA_MIN = 30


# ---------------------------------------------------------------- day anchor
def day_id_and_first_hour_low(df, tf):
    """
    برمی‌گرداند: (day_id[i], fhl[i]) برای هر کندل.
    fhl[i] = کفِ ساعتِ اولِ روزِ جاری، فقط وقتی ساعتِ اول *کامل* شده
    (اندیسِ درون-روزِ کندل >= N)؛ در غیرِ این صورت NaN (قاعده خاموش).
    کاملاً سببی: fhl[i] فقط از کندل‌های <= i همان روز ساخته می‌شود.
    """
    n = len(df)
    t = df['dt'].values.astype('datetime64[s]').astype(np.int64)
    low = df['low'].values
    nbars = FIRST_HOUR_BARS[tf]
    gap_thresh_sec = (TF_MINUTES[tf] + GAP_EXTRA_MIN) * 60

    day_id = np.zeros(n, dtype=np.int64)
    fhl = np.full(n, np.nan)
    cur_day = 0
    bar_in_day = 0
    cur_fhl = np.inf
    for i in range(n):
        if i > 0 and (t[i] - t[i - 1]) > gap_thresh_sec:
            cur_day += 1
            bar_in_day = 0
            cur_fhl = np.inf
        if bar_in_day < nbars:
            cur_fhl = min(cur_fhl, low[i])
        day_id[i] = cur_day
        # قاعده فقط بعد از بسته‌شدنِ آخرین کندلِ ساعتِ اول فعال است:
        if bar_in_day >= nbars - 1:
            fhl[i] = cur_fhl
        # توجه: در خودِ کندلِ آخرِ ساعتِ اول هم fhl معتبر است چون کندل بسته شده
        # و تصمیم روی open کندلِ بعد اجرا می‌شود.
        bar_in_day += 1
    return day_id, fhl


# ---------------------------------------------------------------- wrapper
class MgmtFirstHourLowExit:
    """Wrapper مدیریتی: پایه دست‌نخورده + خروجِ LONG زیرِ کفِ ساعتِ اول."""

    def __init__(self, base, tf):
        self.base = base
        self.tf = tf
        self._fhl = None

    def advise(self, ctx):
        if self._fhl is None:
            _, self._fhl = day_id_and_first_hour_low(ctx.df, self.tf)
        i = ctx.i
        if ctx.in_position() and ctx.position['side'] == 'LONG':
            f = self._fhl[i]
            # فقط اگر ورود قبل از این کندل بوده (پس از ورود، نه در لحظهٔ ورود)
            if np.isfinite(f) and ctx.df['close'].values[i] < f \
                    and ctx.position['entry_bar'] <= i:
                return {'action': 'CLOSE'}
        return self.base.advise(ctx)


# ---------------------------------------------------------------- metrics
def metrics(tr):
    if tr is None or len(tr) == 0:
        return dict(n=0)
    pnl = tr['pnl_usd'].values  # به‌ازای ۱ لات
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(eq)
    maxdd = float(np.max(peak - eq)) if len(eq) else 0.0
    gross_w = pnl[pnl > 0].sum()
    gross_l = -pnl[pnl < 0].sum()
    return dict(
        n=int(len(pnl)),
        total=round(float(pnl.sum()), 1),
        avg=round(float(pnl.mean()), 2),
        sd=round(float(pnl.std(ddof=1)), 2) if len(pnl) > 1 else 0.0,
        worst=round(float(pnl.min()), 1),
        best=round(float(pnl.max()), 1),
        maxDD=round(maxdd, 1),
        pf=round(float(gross_w / gross_l), 3) if gross_l > 0 else float('inf'),
        wr=round(float((pnl > 0).mean() * 100), 1),
    )


def halves(tr, df):
    """تقسیم بر اساسِ نیمهٔ زمانیِ *داده* (نه نیمهٔ معاملات) — پایداری."""
    if tr is None or len(tr) == 0:
        return dict(h1=dict(n=0), h2=dict(n=0))
    mid_bar = len(df) // 2
    h1 = tr[tr['entry_bar'] < mid_bar]
    h2 = tr[tr['entry_bar'] >= mid_bar]
    return dict(h1=metrics(h1), h2=metrics(h2))


def run_tf(tf):
    kw = BEST[tf]
    df = TS.load_data(f'XAUUSD_{tf}')
    warmup = max(220, 200 + 20)

    base = S312_MidMonth_Long(**kw)
    tr_base, _ = TS.simulate(df, base, 'XAUUSD', tf=tf, warmup=warmup,
                             max_bars_hold=kw['max_hold'])

    treat = MgmtFirstHourLowExit(S312_MidMonth_Long(**kw), tf)
    tr_mgmt, _ = TS.simulate(df, treat, 'XAUUSD', tf=tf, warmup=warmup,
                             max_bars_hold=kw['max_hold'])

    out = dict(
        strategy='S312_MidMonth_Long', tf=tf, params=kw,
        rule='S450 first-hour-low LONG exit (M1)',
        baseline=metrics(tr_base),
        treatment=metrics(tr_mgmt),
        baseline_halves=halves(tr_base, df),
        treatment_halves=halves(tr_mgmt, df),
        exit_reasons_treatment=tr_mgmt['exit_reason'].value_counts().to_dict()
        if len(tr_mgmt) else {},
        exit_reasons_baseline=tr_base['exit_reason'].value_counts().to_dict()
        if len(tr_base) else {},
    )
    os.makedirs(os.path.join(ROOT, 'research', 'mgmt'), exist_ok=True)
    path = os.path.join(ROOT, 'research', 'mgmt', f'S450_S312_{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n===== S450 · S312 · XAUUSD_{tf} =====")
    print("BASE :", out['baseline'])
    print("MGMT :", out['treatment'])
    print("BASE halves:", out['baseline_halves'])
    print("MGMT halves:", out['treatment_halves'])
    print("exit reasons mgmt:", out['exit_reasons_treatment'])
    print("saved:", path)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else ['M30', 'M15', 'H1']
    for tf in tfs:
        run_tf(tf)
