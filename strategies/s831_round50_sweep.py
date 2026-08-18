# -*- coding: utf-8 -*-
"""
S831 — لایه‌ی «جاروی ناکام سطح رند $50» XAUUSD-H1 — آزمون نهایی مسیر C
========================================================================
پیش‌ثبت: results/S831_PREREG_ROUND50_SWEEP_SHORT_HOLDOUT.md (کامیت c33617d9)
هندسه‌ی فریزشده (هیچ عددی قابل تغییر نیست):
    رخداد: prev_close < L ، high >= L ، close < L  با L = round(prev_close/50)*50 — فقط short
    SL = 1.4 × ATR34(EWMA) پیپ (clip 8..5000) ، TP = 6.0 × SL ، hold = 21
    allow_overlap=False ، warmup=600 ، split_bar=54798 (2020-05-27)
فازها:
    --null  : صفر جای‌گشتی K=500 (seed=831831) روی کندل‌های ورود هولد‌اوت، جهت تصادفی
    --judge : یک (۱) آزمون روی نیمه‌ی محافظت‌شده با compute_rqs2 (n_trials=1)
              پس از اجرا S831_HOLDOUT_SPENT.lock نوشته می‌شود.
اجرا: python3 strategies/s831_round50_sweep.py --null سپس --judge
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

OUT_DIR = 'results/_scan_S831'
SPLIT_IDX = 54798
G = 50.0
SLM, RR, HOLD = 1.4, 6.0, 21
WARMUP = 600
N_PERM = 500
SEED = 831831


def build_features(df):
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    lev = np.round(prev_c / G) * G
    ss = (prev_c < lev) & (h >= lev) & (c < lev)
    ss[:WARMUP] = False
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr); atr[0] = tr[0]
    a = 1.0 / 34
    for i in range(1, len(tr)):
        atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']
    sl_pip = np.clip(atr_pip * SLM, 8, 5000)
    tp_pip = sl_pip * RR
    return ss, sl_pip, tp_pip


def run_strategy(df, ss, sl_pip, tp_pip):
    z0 = np.zeros(len(df), bool)
    return se.simulate_trades(df, z0, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                              asset='XAUUSD', max_hold=HOLD, allow_overlap=False)


def phase_null(df, ss, sl_pip, tp_pip):
    tr = run_strategy(df, ss, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX]
    entry_bars = hold['entry_bar'].values.astype(int)
    n = len(entry_bars)
    print(f'[null] holdout entry bars: n={n}', flush=True)
    rng = np.random.default_rng(SEED)
    wrs = []
    for kk in range(N_PERM):
        dirs = rng.integers(0, 2, size=n).astype(bool)   # True=long
        lmask = np.zeros(len(df), bool); lmask[entry_bars[dirs]] = True
        smask = np.zeros(len(df), bool); smask[entry_bars[~dirs]] = True
        ptr = se.simulate_trades(df, lmask, smask, sl_pip=sl_pip, tp_pip=tp_pip,
                                 asset='XAUUSD', max_hold=HOLD, allow_overlap=False)
        if len(ptr) > 0:
            wrs.append(float((ptr['pnl_pip'].values > 0).mean() * 100))
        if (kk + 1) % 50 == 0:
            print(f'  [null] perm {kk+1}/{N_PERM}', flush=True)
    wrs = np.array(wrs)
    side = dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=int(len(wrs)))
    null = {'long': dict(side), 'short': dict(side)}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 's831_null_holdout.json'), 'w') as f:
        json.dump(null, f, indent=1)
    print(f'[null] mean={side["perm_mean"]:.2f}% sd={side["perm_sd"]:.2f} '
          f'max={side["perm_max"]:.2f}% k={side["perm_k"]}', flush=True)
    return null


def phase_judge(df, ss, sl_pip, tp_pip):
    lock = os.path.join(OUT_DIR, 'S831_HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('⛔ هولد‌اوت S831 قبلاً مصرف شده — آزمون دوم ممنوع است (مسیر C).')
        return None
    with open(os.path.join(OUT_DIR, 's831_null_holdout.json')) as f:
        null = json.load(f)
    tr = run_strategy(df, ss, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX].reset_index(drop=True)
    pnl = hold['pnl_pip'].values
    wr = float((pnl > 0).mean() * 100)
    w = pnl[pnl > 0].sum(); lo = -pnl[pnl < 0].sum()
    pf = float(w / lo) if lo > 0 else float('inf')
    print(f'[judge] holdout trades={len(hold)}  WR={wr:.2f}%  PF={pf:.3f}  '
          f'exp={pnl.mean():+.2f}pip  '
          f'perm_mean={null["short"]["perm_mean"]:.2f}%  '
          f'lift={wr - null["short"]["perm_mean"]:+.2f}pp', flush=True)
    med_sl = float(np.median(hold['sl_pip'].values))
    med_tp = med_sl * RR
    r = rqs2.compute_rqs2(
        hold, 'XAUUSD',
        sl_pip=med_sl, tp_pip=med_tp,
        bar_time=df['time'].values, null=null, n_trials=1,
        split_bar=SPLIT_IDX, close=df['close'].values)
    with open(lock, 'w') as f:
        f.write('S831 holdout spent — one test only (path C), prereg c33617d9\n')
    res = dict(layer='S831', card='XAUUSD-H1', prereg='c33617d9',
               geometry=dict(G=G, slm=SLM, rr=RR, hold=HOLD),
               n_holdout=len(hold), wr_holdout=wr, pf_holdout=pf,
               exp_pip=float(pnl.mean()),
               verdict=r['verdict'], score=r['rqs2_score'], gates=r['gates'],
               notes=r.get('notes'))
    with open(os.path.join(OUT_DIR, 's831_judgment_h1.json'), 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--null', action='store_true')
    ap.add_argument('--judge', action='store_true')
    a = ap.parse_args()
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d)
    print('src:', d['src'])
    assert len(df) > SPLIT_IDX
    ss, sl_pip, tp_pip = build_features(df)
    print(f'events total={int(ss.sum())}  '
          f'explore={int(ss[:SPLIT_IDX].sum())}  holdout={int(ss[SPLIT_IDX:].sum())}')
    if a.null:
        phase_null(df, ss, sl_pip, tp_pip)
    if a.judge:
        phase_judge(df, ss, sl_pip, tp_pip)


if __name__ == '__main__':
    main()
