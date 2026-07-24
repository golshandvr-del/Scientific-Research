# -*- coding: utf-8 -*-
"""
S215_runner — اجرای افزایشیِ per-TF برای S215 (Trend Lines، فصلِ ۱۳).
هر تایم‌فریم جداگانه اجرا و بلافاصله در results/_s215_part_<TF>.json ذخیره می‌شود؛
پس اگر سندباکس ریست شد، فقط TF ناتمام دوباره اجرا می‌شود (حفظِ پیشرفت).

اجرا:  python3 strategies/s215_runner.py <TF>        # یک تایم‌فریم
       python3 strategies/s215_runner.py --merge     # ادغامِ همهٔ partها
"""
import os, sys, json
import numpy as np
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s215_brooks_trend_line as X

RESULTS = os.path.join(ROOT, 'results')

SL_TP = [(150, 300), (200, 400), (250, 500), (300, 450), (200, 300)]
MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24, 'H4': 16, 'D1': 10}
EMA = [(10, 30), (20, 50)]
K = [3, 5]
PEN = [0.3, 0.6, 1.0]
MAX_GAP = [40, 80]
SIDES = ['long', 'short']

ALL_TFS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1', 'XAUUSD_H4', 'XAUUSD_D1',
           'EURUSD_M1', 'EURUSD_M5', 'EURUSD_M15', 'EURUSD_M30']


def run_tf(tf):
    asset = tf.split('_')[0]; tag = tf.split('_')[1]
    mh = MH.get(tag, 48)
    df = S.lastn(S.load(tf), y=4)
    print(f"### {tf}  (n={len(df)}, mh={mh})", flush=True)
    rows = []
    for side in SIDES:
        for (ef, es) in EMA:
            for k in K:
                for pen in PEN:
                    for mg in MAX_GAP:
                        sig = X.trend_line_signals(df, side, ef, es, k, pen, mg)
                        if int(sig.sum()) < 30:
                            continue
                        for sl, tp in SL_TP:
                            r = X.evaluate(df, asset, sig, side, sl, tp, mh)
                            if r is None:
                                continue
                            row = dict(tf=tf, side=side, ema=f"{ef}/{es}", k=k, pen=pen,
                                       max_gap=mg, sl=sl, tp=tp, net=r['net'], wr=r['wr'],
                                       n=r['n'], pf=r['pf'], wf=r['wf'], wf_ok=r['wf_ok'],
                                       both_ok=r['both_ok'], accepted=r['accepted'])
                            rows.append(row)
                            if r['accepted']:
                                print(f"  \u2713 {side} ema{ef}/{es} k{k} pen{pen} gap{mg} "
                                      f"SL{sl}/TP{tp}: net=${r['net']:+,.0f} WR{r['wr']} "
                                      f"n{r['n']} PF{r['pf']} WF{[w[0] for w in r['wf']]}", flush=True)
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, f'_s215_part_{tf}.json')
    with open(out, 'w') as f:
        json.dump(rows, f, indent=1)
    acc = [r for r in rows if r['accepted']]
    print(f"  saved {out}: rows={len(rows)} accepted={len(acc)}", flush=True)
    return rows


def merge():
    all_rows = []
    for tf in ALL_TFS:
        p = os.path.join(RESULTS, f'_s215_part_{tf}.json')
        if os.path.exists(p):
            all_rows += json.load(open(p))
    with open(os.path.join(RESULTS, '_s215_trend_line.json'), 'w') as f:
        json.dump(all_rows, f, indent=1)
    acc = sorted([r for r in all_rows if r['accepted']], key=lambda r: -r['net'])
    print(f"MERGED rows={len(all_rows)} accepted={len(acc)}")
    for r in acc[:30]:
        print(f"  {r['tf']} {r['side']} ema{r['ema']} k{r['k']} pen{r['pen']} gap{r['max_gap']} "
              f"SL{r['sl']}/TP{r['tp']}: net=${r['net']:+,.0f} WR{r['wr']} n{r['n']}")
    return all_rows, acc


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else '--all'
    if arg == '--merge':
        merge()
    elif arg == '--all':
        for tf in ALL_TFS:
            run_tf(tf)
        merge()
    else:
        run_tf(arg)
