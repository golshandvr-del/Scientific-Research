# -*- coding: utf-8 -*-
"""
s152_eurusd_hour14_short.py — «EURUSD Hour-14 (NY-Open) Short Drift»
====================================================================
فرضیهٔ علمی (درسِ زنجیرهٔ s149→s150→s151):
  سه چرخهٔ قیمتیِ یورو (trend/mean-rev در M15/M30/H4) همگی رد شدند. درسِ صریح:
  «تنها لبه‌های سوددهِ یورو تقویمی/سشنی‌اند، نه قیمتی» (تأیید با S73 و S143 موجود).

  پس این‌بار مستقیم سراغِ بُعدِ **سشنی/ساعتِ روز** رفتیم. تشخیصِ t-statِ ساعت‌به‌ساعت:
    hour01 (باز شدنِ لندن): t=+9.97، در هر ۹ سال مثبت — اما احتمالاً با S73 (ساعت۰) همبسته.
    **hour14 (باز شدنِ نیویورک): t=−4.33، در ۷ از ۹ سال منفی** ⇒ کاندیدای SHORTِ متعامد.
    hour23: لبه در سال‌های اخیر محو شد ⇒ رد.

  چرا hour14 SHORT جذاب است؟
  (۱) چون SHORT است، ذاتاً با همهٔ لایه‌های long موجود (طلا+یورو) متعامد ⇒ افزایشی.
  (۲) توضیحِ اقتصادی: در باز شدنِ سشنِ نیویورک (۱۴ UTC) اغلب تقاضای دلار (فروشِ EUR)
      از سویِ جریانِ سفارشِ آمریکایی بالا می‌رود ⇒ فشارِ نزولی بر EURUSD.

منطق: در کندل‌هایی که ساعتشان ۱۴ UTC است ⇒ SHORT. خروج با SL/TP/hold.
موتور: engine/scalp_engine (کالیبرهٔ واقعیِ EURUSD).
قانونِ ۱: فقط سودِ خالص (XAUUSD+EURUSD). WR ملاک نیست.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from engine.scalp_engine import ASSETS, load_data, simulate_trades, run_capital

ASSET = 'EURUSD'
PIP = ASSETS[ASSET]['pip']


def load_eur():
    return load_data(ASSETS[ASSET]['file'])


def gen_hour_short(df, hours, cooldown):
    """SHORT در کندل‌هایی که ساعتشان در مجموعهٔ hours است."""
    hh = df['dt'].dt.hour.values
    N = len(df)
    long_sig = np.zeros(N, dtype=bool)
    short_sig = np.zeros(N, dtype=bool)
    last = -10**9
    for i in range(2, N - 1):
        if i - last < cooldown:
            continue
        if hh[i] in hours:
            short_sig[i] = True
            last = i
    return long_sig, short_sig


def net_of(cap):
    if cap is None:
        return 0.0
    stats = cap[0] if isinstance(cap, tuple) else cap
    return float(stats.get('net_profit', 0.0)) if isinstance(stats, dict) else 0.0


def evalgates(df, ls, ss, sl, tp, be, trail, mh):
    N = len(df)
    trd = simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=mh,
                          be_trigger_pip=be, trail_pip=trail)
    if len(trd) < 30:
        return None
    sb = trd['signal_bar'].values
    mid = N // 2
    def cn(mask):
        sub = trd[mask]
        if len(sub) == 0:
            return 0.0
        return net_of(run_capital(sub.reset_index(drop=True), ASSET))
    total = net_of(run_capital(trd, ASSET))
    h1 = cn(sb < mid); h2 = cn(sb >= mid)
    edges = [int(N * j / 4) for j in range(5)]
    folds = [cn((sb >= edges[j]) & (sb < edges[j + 1])) for j in range(4)]
    return dict(total=total, h1=h1, h2=h2, folds=folds, n=len(trd), trd=trd)


def per_year(trd):
    """سودِ خالصِ سالانه (برای بررسیِ پایداری)."""
    out = {}
    yrs = pd.to_datetime(trd['dt']).dt.year if 'dt' in trd else None
    return out


if __name__ == '__main__':
    print("=== s152 — EURUSD Hour-14 (NY-Open) Short Drift ===")
    df = load_eur()
    print(f"داده: {len(df)} کندلِ M15  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})\n")

    best = None
    winners = []
    combos = 0
    # مجموعه‌های ساعتِ کاندیدا حولِ باز شدنِ نیویورک (۱۴ UTC)
    hour_sets = [
        frozenset([14]),
        frozenset([14, 15]),
        frozenset([13, 14]),
        frozenset([14, 15, 16]),
    ]
    for hours in hour_sets:
        for cd in [1, 2, 4]:
            ls, ss = gen_hour_short(df, hours, cd)
            if int(ss.sum()) < 30:
                continue
            for sl, tp, be, trail, mh in [
                (20, 40, None, None, 8),
                (30, 60, 15, 12, 16),
                (40, 100, 20, 18, 32),
                (50, 150, 25, 22, 48),
                (25, 25, None, None, 4),   # scalp سریع
            ]:
                combos += 1
                r = evalgates(df, ls, ss, sl, tp, be, trail, mh)
                if r is None:
                    continue
                both = r['h1'] > 0 and r['h2'] > 0
                wf = all(f > 0 for f in r['folds'])
                hs = ','.join(str(h) for h in sorted(hours))
                if r['total'] > 0 and both:
                    tag = f"h[{hs}] cd{cd} SL{sl}/TP{tp}/be{be}/tr{trail}/mh{mh}"
                    winners.append((r['total'], wf, both, tag, r))
                if best is None or r['total'] > best[0]:
                    best = (r['total'], hs, cd, sl, tp, be, trail, mh, both, wf, r)
    print(f"ترکیب‌های آزموده‌شده: {combos}\n")

    print("--- بهترین ترکیب (بیشترین سودِ خالص) ---")
    if best:
        (tot, hs, cd, sl, tp, be, tr, mh, both, wf, r) = best
        print(f"h[{hs}] cd{cd} SL{sl}/TP{tp}/be{be}/tr{tr}/mh{mh}")
        print(f"  net={tot:+.0f}$ n={r['n']} h1={r['h1']:+.0f} h2={r['h2']:+.0f} "
              f"both={'Y' if both else 'N'} wf={'Y' if wf else 'N'} "
              f"WF=[{','.join(f'{f:+.0f}' for f in r['folds'])}]")

    print(f"\n--- ترکیب‌های both-halves مثبت: {len(winners)} ---")
    winners.sort(reverse=True)
    for tot, wf, both, tag, r in winners[:15]:
        flag = "✅✅ (WF کامل)" if wf else "✅ (WF ناقص)"
        print(f"  net={tot:+8.0f}$ n={r['n']:4d} {flag}  {tag}  "
              f"WF=[{','.join(f'{f:+.0f}' for f in r['folds'])}]")
    if not winners:
        print("  هیچ ترکیبِ both-halves مثبتی یافت نشد.")
