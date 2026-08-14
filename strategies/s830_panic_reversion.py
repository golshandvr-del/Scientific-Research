# -*- coding: utf-8 -*-
"""
S830 — لایه‌ی «بازگشت پس از وحشت فروش» XAUUSD-H1 — آزمون نهایی مسیر C
=======================================================================
پیش‌ثبت: results/S830_PREREG_PANIC_REVERSION_H1_HOLDOUT.md (کامیت 96ddad63)
هندسه‌ی فریزشده (هیچ عددی قابل تغییر نیست):
    رخداد: z8 < -2.5 (بازده تجمعی ۸ کندل / σ_EWMA(λ=0.97)·√8) ، فقط long
    SL = 2.6 × ATR34(EWMA) پیپ (clip 8..5000) ، TP = 1.6 × SL ، hold=21
    allow_overlap=False ، warmup=600 ، split_bar=54798 (2020-05-27)
فازها:
    --null  : صفر جای‌گشتی K=500 روی «همان کندل‌های ورود هولد‌اوت» با جهت تصادفی
    --judge : یک (۱) آزمون روی نیمه‌ی محافظت‌شده با compute_rqs2 (n_trials=1)
              پس از اجرا HOLDOUT_SPENT.lock نوشته می‌شود — آزمون دوم ممنوع.
اجرا: python3 strategies/s830_panic_reversion.py --null --judge
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

OUT_DIR = 'results/_scan_S830'
SPLIT_IDX = 54798          # پیش‌ثبت‌شده — 60.0% ، 2020-05-27 01:00 UTC
W, KTHR = 8, 2.5
SLM, RR, HOLD = 2.6, 1.6, 21
WARMUP = 600
N_PERM = 500
SEED = 830830


def build_features(df):
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    r = np.concatenate([[0.0], np.diff(np.log(c))])
    lam = 0.97
    sig2 = np.empty_like(r); sig2[0] = np.var(r[:500])
    for i in range(1, len(r)):
        sig2[i] = lam * sig2[i-1] + (1 - lam) * r[i]*r[i]
    sig = np.sqrt(np.maximum(sig2, 1e-18))
    cs = np.cumsum(r)
    cum = np.concatenate([[np.nan]*W, cs[W:] - cs[:-W]])[:len(r)]
    zW = cum / (sig * np.sqrt(W))
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr); atr[0] = tr[0]
    a = 1.0 / 34
    for i in range(1, len(tr)):
        atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']
    sl_pip = np.clip(atr_pip * SLM, 8, 5000)
    tp_pip = sl_pip * RR                      # قید TP >= SL برقرار (RR=1.6)
    ls = zW < -KTHR
    ls[:WARMUP] = False
    return ls, sl_pip, tp_pip


def run_strategy(df, ls, sl_pip, tp_pip):
    z0 = np.zeros(len(df), bool)
    return se.simulate_trades(df, ls, z0, sl_pip=sl_pip, tp_pip=tp_pip,
                              asset='XAUUSD', max_hold=HOLD, allow_overlap=False)


def phase_null(df, ls, sl_pip, tp_pip):
    """صفر جای‌گشتی: همان کندل‌های ورودِ معاملات هولد‌اوت، جهت تصادفی 50/50،
    همان هندسه. K=500. ساختار خروجی مطابق null_from_s346."""
    tr = run_strategy(df, ls, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX]
    entry_bars = hold['entry_bar'].values.astype(int)
    n = len(entry_bars)
    print(f'[null] holdout entry bars: n={n}', flush=True)
    rng = np.random.default_rng(SEED)
    z0 = np.zeros(len(df), bool)
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
    with open(os.path.join(OUT_DIR, 's830_null_holdout.json'), 'w') as f:
        json.dump(null, f, indent=1)
    print(f'[null] mean={side["perm_mean"]:.2f}% sd={side["perm_sd"]:.2f} '
          f'max={side["perm_max"]:.2f}% k={side["perm_k"]}', flush=True)
    return null


def phase_judge(df, ls, sl_pip, tp_pip):
    lock = os.path.join(OUT_DIR, 'S830_HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('⛔ هولد‌اوت S830 قبلاً مصرف شده — آزمون دوم ممنوع است (مسیر C).')
        return None
    with open(os.path.join(OUT_DIR, 's830_null_holdout.json')) as f:
        null = json.load(f)
    tr = run_strategy(df, ls, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX].reset_index(drop=True)
    wr = float((hold['pnl_pip'].values > 0).mean() * 100)
    print(f'[judge] holdout trades={len(hold)}  WR={wr:.2f}%  '
          f'perm_mean={null["long"]["perm_mean"]:.2f}%  '
          f'lift={wr - null["long"]["perm_mean"]:+.2f}pp', flush=True)
    # compute_rqs2 برای گیت هندسه اسکالر می‌خواهد؛ میانه‌ی براکت‌های واقعی هولد‌اوت
    med_sl = float(np.median(hold['sl_pip'].values))
    med_tp = med_sl * RR
    r = rqs2.compute_rqs2(
        hold, 'XAUUSD',
        sl_pip=med_sl, tp_pip=med_tp,
        bar_time=df['time'].values, null=null, n_trials=1,
        split_bar=SPLIT_IDX, close=df['close'].values)
    with open(lock, 'w') as f:
        f.write('S830 holdout spent — one test only (path C), prereg 96ddad63\n')
    res = dict(layer='S830', card='XAUUSD-H1', prereg='96ddad63',
               geometry=dict(W=W, k=KTHR, slm=SLM, rr=RR, hold=HOLD),
               n_holdout=len(hold), wr_holdout=wr,
               verdict=r['verdict'], score=r['rqs2_score'], gates=r['gates'],
               notes=r.get('notes'))
    with open(os.path.join(OUT_DIR, 's830_judgment_h1.json'), 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print(rqs2.format_rqs2(r))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--null', action='store_true')
    ap.add_argument('--judge', action='store_true')
    a = ap.parse_args()
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d)
    print('src:', d['src'])
    assert len(df) > SPLIT_IDX, 'داده کوتاه‌تر از برش پیش‌ثبت‌شده!'
    ls, sl_pip, tp_pip = build_features(df)
    print(f'events total={int(ls.sum())}  '
          f'explore={int(ls[:SPLIT_IDX].sum())}  holdout={int(ls[SPLIT_IDX:].sum())}')
    if a.null:
        phase_null(df, ls, sl_pip, tp_pip)
    if a.judge:
        phase_judge(df, ls, sl_pip, tp_pip)


if __name__ == '__main__':
    main()
