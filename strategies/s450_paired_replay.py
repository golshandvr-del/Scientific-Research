# -*- coding: utf-8 -*-
"""
s450_paired_replay.py — S450 · بازپخشِ جفتیِ قاعدهٔ «کفِ ساعتِ اول» (M1)
================================================================================
چرا این فایل؟ هارنسِ اولیه (s450_mgmt_first_hour_low.py) نشان داد Wrapper
سرراست، جمعیتِ معاملات را عوض می‌کند (خروجِ زود ⇒ ورودِ مجددِ همان روز:
297→900 معامله در M30) ⇒ دیگر «همان معاملات با/بدونِ قاعده» نیست و اثرِ
قاعده با اثرِ ورودهای جدید مخلوط می‌شود. متنِ مأموریت صریح است: قاعده باید
روی «معاملاتِ لایه‌های زنده» تست شود.

روشِ درست (این فایل): بازپخشِ جفتی —
  ۱) معاملاتِ پایه با شبیه‌سازِ رسمی تولید می‌شوند (بدونِ قاعده).
  ۲) هر معاملهٔ پایه کندل‌به‌کندل بازپخش می‌شود؛ اگر قاعده زودتر از خروجِ
     پایه فعال شود، خروج در open کندلِ بعد با فرمولِ هزینهٔ رسمیِ شبیه‌ساز
     (net_move = raw − cost_price؛ pnl بر ۱ لات = net_move × contract).
  ۳) جمعیت ثابت می‌ماند (جفت‌به‌جفت) ⇒ اثرِ خالصِ قاعده جدا می‌شود.

ترتیبِ اولویت‌ها عیناً مطابقِ حلقهٔ شبیه‌ساز (engine/trade_simulator.py):
  در گامِ i: اول SL/TP کندلِ i+1 (اولویتِ مدیریتِ ریسک) ⇒ اگر خروجِ پایه
  در i+1 با sl/tp/sl_gap/tp_gap باشد، بر قاعده مقدم است. سپس CLOSE قاعده
  در open[i+1] ⇒ بر max_hold/strategy_close همان کندل مقدم است.

قاعدهٔ پیش‌ثبت‌شده (S450، فقط LONG): اگر close[i] < کفِ ساعتِ اولِ روزِ جاری
(روز = گپ>۳۰ دقیقه؛ ساعتِ اول کامل‌شده) ⇒ CLOSE در open[i+1].

اجرا: python3 strategies/s450_paired_replay.py [TF...]
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
from strategies.s450_mgmt_first_hour_low import (
    BEST, day_id_and_first_hour_low)


def paired_replay(tr_base, df, tf, spec, side='LONG'):
    """
    برمی‌گرداند: DataFrame همان معاملات با ستون‌های جدید:
      pnl_mgmt (بر ۱ لات)، exit_bar_mgmt، exit_reason_mgmt، changed(bool)
    """
    o = df['open'].values
    c = df['close'].values
    _, fhl = day_id_and_first_hour_low(df, tf)
    cost = spec['cost_price']
    contract = spec['contract']

    rows = []
    for t in tr_base.itertuples(index=False):
        eb = int(t.entry_bar)
        xb = int(t.exit_bar)
        entry = float(t.entry_price)
        # پیش‌فرض: عینِ خروجِ پایه
        pnl_m = float(t.pnl_usd)
        xb_m = xb
        reason_m = t.exit_reason
        changed = False
        if side == 'LONG':
            # کندل‌های بسته‌شده در حینِ پوزیشن: i از eb تا xb-1
            for i in range(eb, xb):
                # تقدمِ SL/TP خودِ کندلِ i+1: اگر خروجِ پایه در i+1 با sl/tp است،
                # شبیه‌ساز آن را قبل از advice اجرا می‌کند ⇒ قاعده نمی‌رسد.
                if i + 1 == xb and t.exit_reason in ('sl', 'tp', 'sl_gap', 'tp_gap'):
                    break
                f = fhl[i]
                if np.isfinite(f) and c[i] < f:
                    exit_px = o[i + 1]
                    raw = exit_px - entry
                    net = raw - cost
                    pnl_m = net * contract
                    xb_m = i + 1
                    reason_m = 'fhl_exit'
                    changed = True
                    break
        rows.append(dict(entry_bar=eb, exit_bar=xb, exit_bar_mgmt=xb_m,
                         pnl_base=float(t.pnl_usd), pnl_mgmt=pnl_m,
                         exit_reason_base=t.exit_reason,
                         exit_reason_mgmt=reason_m, changed=changed,
                         bars_held_base=xb - eb, bars_held_mgmt=xb_m - eb))
    return pd.DataFrame(rows)


def metrics(pnl):
    pnl = np.asarray(pnl, dtype=float)
    if len(pnl) == 0:
        return dict(n=0)
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(eq)
    maxdd = float(np.max(peak - eq))
    gw = pnl[pnl > 0].sum()
    gl = -pnl[pnl < 0].sum()
    return dict(n=int(len(pnl)), total=round(float(pnl.sum()), 1),
                avg=round(float(pnl.mean()), 2),
                sd=round(float(pnl.std(ddof=1)), 2) if len(pnl) > 1 else 0.0,
                worst=round(float(pnl.min()), 1), best=round(float(pnl.max()), 1),
                maxDD=round(maxdd, 1),
                pf=round(float(gw / gl), 3) if gl > 0 else float('inf'),
                wr=round(float((pnl > 0).mean() * 100), 1))


def judge(base, mgmt):
    """داوریِ پیش‌ثبت‌شده §4 (بدونِ بندِ نیمه‌ها که جدا چک می‌شود)."""
    if base['n'] == 0:
        return dict(verdict='NO-TRADES')
    profit_ok = mgmt['avg'] >= 0.95 * base['avg'] if base['avg'] > 0 else mgmt['avg'] >= base['avg']
    improves = {
        'sd': mgmt['sd'] < base['sd'],
        'worst': abs(mgmt['worst']) < abs(base['worst']),
        'maxDD': mgmt['maxDD'] < base['maxDD'],
    }
    worsens_gt5 = {
        'sd': mgmt['sd'] > 1.05 * base['sd'],
        'worst': abs(mgmt['worst']) > 1.05 * abs(base['worst']),
        'maxDD': mgmt['maxDD'] > 1.05 * base['maxDD'],
    }
    risk_ok = (sum(improves.values()) >= 2) and (not any(worsens_gt5.values()))
    return dict(profit_ok=bool(profit_ok), improves=improves,
                worsens_gt5=worsens_gt5, risk_ok=bool(risk_ok),
                verdict='PASS' if (profit_ok and risk_ok) else 'FAIL')


def run_tf(tf):
    kw = BEST[tf]
    df = TS.load_data(f'XAUUSD_{tf}')
    spec = TS.asset_spec('XAUUSD')
    warmup = max(220, 200 + 20)
    base = S312_MidMonth_Long(**kw)
    tr_base, _ = TS.simulate(df, base, 'XAUUSD', tf=tf, warmup=warmup,
                             max_bars_hold=kw['max_hold'])
    pr = paired_replay(tr_base, df, tf, spec)

    mid = len(df) // 2
    h1 = pr[pr['entry_bar'] < mid]
    h2 = pr[pr['entry_bar'] >= mid]

    out = dict(
        strategy='S312_MidMonth_Long', tf=tf, params=kw,
        rule='S450 first-hour-low LONG exit (M1) — paired replay',
        n_trades=int(len(pr)), n_changed=int(pr['changed'].sum()),
        baseline=metrics(pr['pnl_base']),
        treatment=metrics(pr['pnl_mgmt']),
        judge_full=judge(metrics(pr['pnl_base']), metrics(pr['pnl_mgmt'])),
        halves=dict(
            h1=dict(base=metrics(h1['pnl_base']), mgmt=metrics(h1['pnl_mgmt']),
                    judge=judge(metrics(h1['pnl_base']), metrics(h1['pnl_mgmt']))),
            h2=dict(base=metrics(h2['pnl_base']), mgmt=metrics(h2['pnl_mgmt']),
                    judge=judge(metrics(h2['pnl_base']), metrics(h2['pnl_mgmt'])))),
        changed_detail=dict(
            avg_pnl_base_of_changed=round(float(pr.loc[pr['changed'], 'pnl_base'].mean()), 2)
            if pr['changed'].any() else None,
            avg_pnl_mgmt_of_changed=round(float(pr.loc[pr['changed'], 'pnl_mgmt'].mean()), 2)
            if pr['changed'].any() else None,
            avg_bars_saved=round(float((pr.loc[pr['changed'], 'bars_held_base']
                                        - pr.loc[pr['changed'], 'bars_held_mgmt']).mean()), 1)
            if pr['changed'].any() else None,
        ),
    )
    os.makedirs(os.path.join(ROOT, 'research', 'mgmt'), exist_ok=True)
    path = os.path.join(ROOT, 'research', 'mgmt', f'S450_paired_S312_{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n===== S450 paired · S312 · XAUUSD_{tf} =====")
    print(f"trades={out['n_trades']}  changed by rule={out['n_changed']}")
    print("BASE :", out['baseline'])
    print("MGMT :", out['treatment'])
    print("JUDGE:", out['judge_full'])
    print("H1   :", out['halves']['h1']['judge'])
    print("H2   :", out['halves']['h2']['judge'])
    print("changed detail:", out['changed_detail'])
    print("saved:", path)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else ['M30', 'M15', 'H1']
    for tf in tfs:
        run_tf(tf)
