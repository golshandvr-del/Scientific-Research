# -*- coding: utf-8 -*-
"""
s451_paired_s344.py — S451 · آینهٔ SHORT قاعدهٔ M1 روی S344 (M15 SHORT)
================================================================================
پیش‌ثبت (results/S450_PREREG_MGMT_RULES_PROTOCOL.md §2، ردیفِ S451):
  «قرینهٔ SHORT: خروج در شکستِ سقفِ ساعتِ اول — اثباتِ مستقل، تقارن مفت
  فرض نمی‌شود.» (هشدارِ اختصاصیِ MISSION_5: M1 فقط برای LONG اثبات شده؛
  بازار متقارن نیست.)

قاعده: اگر در پوزیشنِ SHORT هستیم و close[i] > سقفِ ساعتِ اولِ روزِ جاری
⇒ خروج در open[i+1]. لنگرِ روز = گپ > (TF+30) دقیقه (لنگرِ اصلاح‌شدهٔ S450).

بیمار: S344 Brooks trend-from-open first-pullback · XAUUSD-M15 · SHORT
بازتولیدِ پایه = عینِ خطِ لولهٔ ACCEPT (s344_overlap_validate.LAYERS[0]):
  sig = trend_from_open_signals(n_open=4, f=0.20, pull=0.62, spk=0.20) & r2h
  tr  = se.simulate_trades(short, sl=220, tp=340, max_hold=32, no-overlap)

نکتهٔ ظریف: در M15 «ساعتِ اول» = ۴ کندل = عینِ opening-range خودِ لایه
(n_open=4). ورودِ SHORT پس از breakout رو به پایین رخ می‌دهد؛ بازگشتِ قیمت
به بالای سقفِ ساعتِ اول یعنی نفیِ کاملِ ساختارِ روزِ نزولی — همان منطقِ
Brooks (نفیِ premise ⇒ خروج). این تفسیر پیش از دیدنِ نتیجه ثبت می‌شود.

بازپخشِ جفتی در فضای pip (سازگار با scalp_engine):
  - fill ورودِ SHORT (slip طلا=0) = open[entry_bar]؛ خروجِ قاعده:
    pnl = (fill − open[i+1])/pip − spread  (عینِ فرمولِ خروجِ زمانیِ موتور)
  - تقدمِ SL/TP کندلِ خروجِ پایه حفظ می‌شود (اولویتِ مدیریتِ ریسک).

اجرا: python3 strategies/s451_paired_s344.py
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicator_bank as ib
from strategies.s344_brooks_trend_from_open import trend_from_open_signals, load_tf
from strategies.s450_mgmt_first_hour_low import (
    FIRST_HOUR_BARS, TF_MINUTES, GAP_EXTRA_MIN)
from strategies.s450_paired_replay import metrics, judge

# پیکربندیِ منجمدِ ACCEPT (عیناً از s344_overlap_validate.LAYERS[0])
CFG = dict(asset="XAUUSD", tf="M15", side="short",
           n_open=4, f_range=0.20, pull_max=0.62, min_spike=0.20,
           sl=220, tp=340, maxhold=32)


def first_hour_high(df, tf):
    """قرینهٔ day_id_and_first_hour_low: سقفِ ساعتِ اول، سببی، لنگرِ گپ>TF+30."""
    n = len(df)
    t = df['dt'].values.astype('datetime64[s]').astype(np.int64)
    high = df['high'].values
    nbars = FIRST_HOUR_BARS[tf]
    gap_thresh = (TF_MINUTES[tf] + GAP_EXTRA_MIN) * 60
    fhh = np.full(n, np.nan)
    bar_in_day = 0
    cur = -np.inf
    for i in range(n):
        if i > 0 and (t[i] - t[i - 1]) > gap_thresh:
            bar_in_day = 0
            cur = -np.inf
        if bar_in_day < nbars:
            cur = max(cur, high[i])
        if bar_in_day >= nbars - 1:
            fhh[i] = cur
        bar_in_day += 1
    return fhh


def reproduce_baseline():
    df = load_tf(CFG['asset'], CFG['tf'])
    a = ib.r2(df, p=34).to_numpy()
    b = ib.hurst(df, p=55).to_numpy()
    reg = (a >= 0.30) & (b >= 0.52) & np.isfinite(a) & np.isfinite(b)
    sig = trend_from_open_signals(df, CFG['tf'], CFG['side'],
                                  n_open=CFG['n_open'], f_range=CFG['f_range'],
                                  pull_max=CFG['pull_max'],
                                  min_spike_frac=CFG['min_spike']) & reg
    tr = se.simulate_trades(df, np.zeros(len(df), bool), sig,
                            CFG['sl'], CFG['tp'], CFG['asset'],
                            max_hold=CFG['maxhold'], allow_overlap=False)
    return df, tr


def paired_replay(tr, df):
    cfg = se.ASSETS[CFG['asset']]
    pip = cfg['pip']; spread = cfg['spread_pip']; slip = cfg['slip_pip']
    o = df['open'].values.astype(float)
    c = df['close'].values.astype(float)
    fhh = first_hour_high(df, CFG['tf'])

    rows = []
    for t in tr.itertuples(index=False):
        eb = int(t.entry_bar); xb = int(t.exit_bar)
        fill = float(t.entry_price)
        sl_price = fill + float(t.sl_pip) * pip          # SHORT
        tp_price = fill - CFG['tp'] * pip
        xp = float(t.exit_price)
        if abs(xp - sl_price) < 1e-9:
            reason_b = 'sl'
        elif abs(xp - tp_price) < 1e-9:
            reason_b = 'tp'
        else:
            reason_b = 'time'

        pnl_m = float(t.pnl_pip); xb_m = xb
        reason_m = reason_b; changed = False
        for i in range(eb, xb):
            if i + 1 == xb and reason_b in ('sl', 'tp'):
                break  # تقدمِ SL/TP
            f = fhh[i]
            if np.isfinite(f) and c[i] > f:
                exit_fill = o[i + 1] + slip * pip
                pnl_m = (fill - exit_fill) / pip - spread
                xb_m = i + 1; reason_m = 'fhh_exit'; changed = True
                break
        rows.append(dict(entry_bar=eb, exit_bar=xb, exit_bar_mgmt=xb_m,
                         pnl_base=float(t.pnl_pip), pnl_mgmt=pnl_m,
                         reason_base=reason_b, reason_mgmt=reason_m,
                         changed=changed,
                         bars_held_base=xb - eb, bars_held_mgmt=xb_m - eb))
    return pd.DataFrame(rows)


def main():
    df, tr = reproduce_baseline()
    wr = (tr['pnl_pip'] > 0).mean() * 100
    print(f"baseline reproduced: n={len(tr)} wr={wr:.2f}% "
          f"(ACCEPT doc: n=92, WR=64.13%)")
    pv = se.ASSETS[CFG['asset']]['pip_value']
    pr = paired_replay(tr, df)
    pr['usd_base'] = pr['pnl_base'] * pv
    pr['usd_mgmt'] = pr['pnl_mgmt'] * pv

    mid = len(df) // 2
    h1 = pr[pr['entry_bar'] < mid]; h2 = pr[pr['entry_bar'] >= mid]
    out = dict(
        strategy='S344_BrooksTrendFromOpen', card='XAUUSD-M15', side='SHORT',
        params=CFG,
        rule='S451 first-hour-HIGH SHORT exit (independent mirror of M1)',
        n_trades=int(len(pr)), n_changed=int(pr['changed'].sum()),
        baseline=metrics(pr['usd_base']), treatment=metrics(pr['usd_mgmt']),
        judge_full=judge(metrics(pr['usd_base']), metrics(pr['usd_mgmt'])),
        halves=dict(
            h1=dict(base=metrics(h1['usd_base']), mgmt=metrics(h1['usd_mgmt']),
                    judge=judge(metrics(h1['usd_base']), metrics(h1['usd_mgmt']))),
            h2=dict(base=metrics(h2['usd_base']), mgmt=metrics(h2['usd_mgmt']),
                    judge=judge(metrics(h2['usd_base']), metrics(h2['usd_mgmt'])))),
        changed_detail=dict(
            avg_base_of_changed=round(float(pr.loc[pr['changed'], 'usd_base'].mean()), 2)
            if pr['changed'].any() else None,
            avg_mgmt_of_changed=round(float(pr.loc[pr['changed'], 'usd_mgmt'].mean()), 2)
            if pr['changed'].any() else None,
            avg_bars_saved=round(float((pr.loc[pr['changed'], 'bars_held_base']
                                        - pr.loc[pr['changed'], 'bars_held_mgmt']).mean()), 1)
            if pr['changed'].any() else None),
    )
    os.makedirs(os.path.join(ROOT, 'research', 'mgmt'), exist_ok=True)
    path = os.path.join(ROOT, 'research', 'mgmt', 'S451_paired_S344_M15.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n===== S451 paired · S344 · XAUUSD_M15 SHORT =====")
    print(f"trades={out['n_trades']}  changed={out['n_changed']}")
    print("BASE :", out['baseline'])
    print("MGMT :", out['treatment'])
    print("JUDGE:", out['judge_full'])
    print("H1   :", out['halves']['h1']['judge'])
    print("H2   :", out['halves']['h2']['judge'])
    print("changed detail:", out['changed_detail'])
    print("saved:", path)


if __name__ == '__main__':
    main()
