# -*- coding: utf-8 -*-
"""
S833 — لایه «قفلِ جهتیِ نسبتِ کاراییِ کافمن (ER-Lock Continuation)» XAUUSD-H1 — آزمون نهایی مسیر C
=====================================================================================================
پیش‌ثبت: results/S833_PREREG_ER_LOCK_CONT_HOLDOUT.md (کامیت 2be6b4e2 — قبل از این آزمون)
هندسه‌ی منجمد (هیچ عددی قابل تغییر نیست):
    ER(21) = |c_t − c_{t−21}| / Σ|Δc| (۲۱ کندلِ منتهی به t)
    رخداد = ER > 0.70 و ERِ کندلِ قبل ≤ 0.70 (عبورِ تازه)
    جهت  = علامتِ net (long اگر net>0، short اگر net<0) — cont، آینه‌ای کامل
    SL = 2.0×ATR34(EWMA) پیپ (clip 8..5000) ، TP = 1.3×SL ، hold=55
    no-overlap ، بدون trail/BE ، WARMUP=200 ، split_bar=54798 (2020-05-27)
فازها:
    --null  : نالِ جای‌گشتیِ جهت K=500 (seed=833833) روی کندل‌های سیگنالِ هولد‌اوت
    --judge : یک (۱) آزمون compute_rqs2 (n_trials=1) ⇒ S833_HOLDOUT_SPENT.lock
اجرا: python3 strategies/s833_er_lock_cont.py --null سپس --judge
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

OUT_DIR = 'results/_scan_S833'
SPLIT_IDX = 54798
W, TH = 21, 0.70
SLM, RR, HOLD = 2.0, 1.3, 55
WARMUP = 200
N_PERM = 500
SEED = 833833
PREREG = '2be6b4e2'


def build_features(df):
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(df)

    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr); atr[0] = tr[0]
    a = 1.0 / 34
    for i in range(1, n):
        atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']

    dc = np.abs(np.diff(c, prepend=c[0]))
    cs = np.cumsum(np.concatenate([[0.0], dc]))
    net = np.full(n, np.nan); net[W:] = c[W:] - c[:-W]
    noise = cs[W+1:] - cs[1:-W]
    er = np.full(n, np.nan); ok = noise > 0
    er[W:][ok] = np.abs(net[W:])[ok] / noise[ok]
    prev_er = np.concatenate([[np.nan], er[:-1]])
    x = (er > TH) & ~(prev_er > TH)
    x[:WARMUP] = False
    ls = x & (net > 0)
    ss = x & (net < 0)

    sl_pip = np.clip(atr_pip * SLM, 8, 5000)
    tp_pip = sl_pip * RR
    return ls, ss, sl_pip, tp_pip


def run_strategy(df, ls, ss, sl_pip, tp_pip):
    return se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                              asset='XAUUSD', max_hold=HOLD, allow_overlap=False)


def phase_null(df, ls, ss, sl_pip, tp_pip):
    tr = run_strategy(df, ls, ss, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX]
    sig_bars = hold['signal_bar'].values.astype(int)
    n = len(sig_bars)
    print(f'[null] holdout signal bars: n={n}', flush=True)
    rng = np.random.default_rng(SEED)
    wrs = []
    for kk in range(N_PERM):
        dirs = rng.integers(0, 2, size=n).astype(bool)
        lmask = np.zeros(len(df), bool); lmask[sig_bars[dirs]] = True
        smask = np.zeros(len(df), bool); smask[sig_bars[~dirs]] = True
        ptr = se.simulate_trades(df, lmask, smask, sl_pip=sl_pip, tp_pip=tp_pip,
                                 asset='XAUUSD', max_hold=HOLD, allow_overlap=False)
        if len(ptr) > 0:
            wrs.append(float((ptr['pnl_pip'].values > 0).mean() * 100))
        if (kk + 1) % 100 == 0:
            print(f'  [null] perm {kk+1}/{N_PERM}', flush=True)
    wrs = np.array(wrs)
    side = dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=int(len(wrs)))
    null = {'long': dict(side), 'short': dict(side)}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 's833_null_holdout.json'), 'w') as f:
        json.dump(null, f, indent=1)
    print(f'[null] mean={side["perm_mean"]:.2f}% sd={side["perm_sd"]:.2f} '
          f'max={side["perm_max"]:.2f}% k={side["perm_k"]}', flush=True)
    return null


def phase_judge(df, ls, ss, sl_pip, tp_pip):
    lock = os.path.join(OUT_DIR, 'S833_HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('⛔ هولد‌اوت S833 قبلاً مصرف شده — آزمون دوم ممنوع است (مسیر C).')
        return None
    with open(os.path.join(OUT_DIR, 's833_null_holdout.json')) as f:
        null = json.load(f)
    tr = run_strategy(df, ls, ss, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX].reset_index(drop=True)
    pnl = hold['pnl_pip'].values
    wr = float((pnl > 0).mean() * 100)
    w = pnl[pnl > 0].sum(); lo = -pnl[pnl < 0].sum()
    pf = float(w / lo) if lo > 0 else float('inf')
    nl = int((hold['direction'].values == 'long').sum())
    print(f'[judge] holdout trades={len(hold)} (L={nl} S={len(hold)-nl})  '
          f'WR={wr:.2f}%  PF={pf:.3f}  exp={pnl.mean():+.2f}pip  '
          f'perm_mean={null["long"]["perm_mean"]:.2f}%  '
          f'lift={wr - null["long"]["perm_mean"]:+.2f}pp', flush=True)
    med_sl = float(np.median(hold['sl_pip'].values))
    med_tp = med_sl * RR
    r = rqs2.compute_rqs2(
        hold, 'XAUUSD',
        sl_pip=med_sl, tp_pip=med_tp,
        bar_time=df['time'].values, null=null, n_trials=1,
        split_bar=SPLIT_IDX, close=df['close'].values)
    with open(lock, 'w') as f:
        f.write(f'S833 holdout spent — one test only (path C), prereg {PREREG}\n')
    res = dict(layer='S833', card='XAUUSD-H1', prereg=PREREG,
               geometry=dict(W=W, th=TH, slm=SLM, rr=RR, hold=HOLD),
               n_holdout=len(hold), n_long=nl, n_short=len(hold)-nl,
               wr_holdout=wr, pf_holdout=pf, exp_pip=float(pnl.mean()),
               verdict=r['verdict'], score=r['rqs2_score'], gates=r['gates'],
               notes=r.get('notes'))
    with open(os.path.join(OUT_DIR, 's833_judgment_h1.json'), 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--null', action='store_true')
    ap.add_argument('--judge', action='store_true')
    a = ap.parse_args()
    d = fd.load_fast('XAUUSD', 'H1')
    assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
    df = fd.as_dataframe(d)
    print('src:', d['src'])
    assert len(df) > SPLIT_IDX
    ls, ss, sl_pip, tp_pip = build_features(df)
    print(f'events: total L={int(ls.sum())} S={int(ss.sum())} | '
          f'explore L={int(ls[:SPLIT_IDX].sum())} S={int(ss[:SPLIT_IDX].sum())} | '
          f'holdout L={int(ls[SPLIT_IDX:].sum())} S={int(ss[SPLIT_IDX:].sum())}', flush=True)
    if a.null:
        phase_null(df, ls, ss, sl_pip, tp_pip)
    if a.judge:
        phase_judge(df, ls, ss, sl_pip, tp_pip)


if __name__ == '__main__':
    main()
