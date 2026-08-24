# -*- coding: utf-8 -*-
"""
S832 — لایه «شکست متقارن رنج آسیا + همراستایی روند EMA300» XAUUSD-H1 — آزمون نهایی مسیر C
==========================================================================================
پیش‌ثبت: results/S832_PREREG_ASIA_BREAKOUT_TREND_HOLDOUT.md (کامیت 0d4af129)
هندسه‌ی فریزشده (هیچ عددی قابل تغییر نیست):
    رنج آسیا = high/low ساعات سرور 0..6 (حداقل ۵ کندل)؛ رویداد = اولین close
    بیرون رنج در ساعات 7..16 (یک معامله/روز)؛ فیلتر روند: long فقط c>EMA300،
    short فقط c<EMA300 (آینه‌ای کامل).
    SL = 2.1×ATR34(EWMA) پیپ (clip 8..5000) ، TP = 6×SL ، trail = 0.7×medATR_explore
    hold = 55 ، allow_overlap=False ، warmup=600 ، split_bar=54798 (2020-05-27)
فازها:
    --null  : صفر جای‌گشتی K=500 (seed=832832) روی کندل‌های ورود هولد‌اوت، جهت تصادفی،
              با همان هندسه‌ی کامل (شامل trail)
    --judge : یک (۱) آزمون compute_rqs2 (n_trials=1) ⇒ S832_HOLDOUT_SPENT.lock
اجرا: python3 strategies/s832_asia_breakout_trend.py --null سپس --judge
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

OUT_DIR = 'results/_scan_S832'
SPLIT_IDX = 54798
SLM, RR, HOLD = 2.1, 6.0, 55
EMA_SPAN = 300
TRAIL_F = 0.7
WARMUP = 600
N_PERM = 500
SEED = 832832


def build_features(df):
    t = df['time'].values.astype(np.int64)
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    hour = (t // 3600) % 24
    day = t // 86400
    n = len(df)

    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr); atr[0] = tr[0]
    a = 1.0 / 34
    for i in range(1, n):
        atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']

    ema = np.empty_like(c); ema[0] = c[0]
    kk = 2.0 / (EMA_SPAN + 1)
    for i in range(1, n):
        ema[i] = ema[i-1] + kk * (c[i] - ema[i-1])
    above = c > ema

    rhi = np.full(n, np.nan); rlo = np.full(n, np.nan)
    for dd in np.unique(day):
        m = (day == dd) & (hour <= 6)
        if m.sum() < 5:
            continue
        md = (day == dd) & (hour >= 7)
        rhi[md] = h[m].max(); rlo[md] = l[m].min()

    in_win = (hour >= 7) & (hour <= 16)
    brk_up = in_win & np.isfinite(rhi) & (c > rhi)
    brk_dn = in_win & np.isfinite(rlo) & (c < rlo)
    first = np.zeros(n, bool)
    seen = set()
    for i in range(n):
        if (brk_up[i] or brk_dn[i]) and day[i] not in seen:
            first[i] = True
            seen.add(day[i])
    ls = first & brk_up & above
    ss = first & brk_dn & ~brk_up & ~above
    ls[:WARMUP] = False; ss[:WARMUP] = False

    sl_pip = np.clip(atr_pip * SLM, 8, 5000)
    tp_pip = sl_pip * RR
    # trail منجمد: 0.7 × میانه‌ی ATRِ «پنجره‌ی اکتشاف» (مطابق پیش‌ثبت — بدون نگاه به هولد‌اوت)
    med_atr_explore = float(np.median(atr_pip[WARMUP:SPLIT_IDX]))
    trail = float(med_atr_explore * TRAIL_F)
    return ls, ss, sl_pip, tp_pip, trail


def run_strategy(df, ls, ss, sl_pip, tp_pip, trail):
    return se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                              asset='XAUUSD', max_hold=HOLD,
                              allow_overlap=False, trail_pip=trail)


def phase_null(df, ls, ss, sl_pip, tp_pip, trail):
    tr = run_strategy(df, ls, ss, sl_pip, tp_pip, trail)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX]
    # کندل سیگنال واقعی (entry = signal+1 در موتور)
    sig_bars = hold['signal_bar'].values.astype(int)
    n = len(sig_bars)
    print(f'[null] holdout signal bars: n={n}', flush=True)
    rng = np.random.default_rng(SEED)
    wrs = []
    for kk in range(N_PERM):
        dirs = rng.integers(0, 2, size=n).astype(bool)   # True=long
        lmask = np.zeros(len(df), bool); lmask[sig_bars[dirs]] = True
        smask = np.zeros(len(df), bool); smask[sig_bars[~dirs]] = True
        ptr = se.simulate_trades(df, lmask, smask, sl_pip=sl_pip, tp_pip=tp_pip,
                                 asset='XAUUSD', max_hold=HOLD,
                                 allow_overlap=False, trail_pip=trail)
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
    with open(os.path.join(OUT_DIR, 's832_null_holdout.json'), 'w') as f:
        json.dump(null, f, indent=1)
    print(f'[null] mean={side["perm_mean"]:.2f}% sd={side["perm_sd"]:.2f} '
          f'max={side["perm_max"]:.2f}% k={side["perm_k"]}', flush=True)
    return null


def phase_judge(df, ls, ss, sl_pip, tp_pip, trail):
    lock = os.path.join(OUT_DIR, 'S832_HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('⛔ هولد‌اوت S832 قبلاً مصرف شده — آزمون دوم ممنوع است (مسیر C).')
        return None
    with open(os.path.join(OUT_DIR, 's832_null_holdout.json')) as f:
        null = json.load(f)
    tr = run_strategy(df, ls, ss, sl_pip, tp_pip, trail)
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
        f.write('S832 holdout spent — one test only (path C), prereg 0d4af129\n')
    res = dict(layer='S832', card='XAUUSD-H1', prereg='0d4af129',
               geometry=dict(slm=SLM, rr=RR, hold=HOLD, ema=EMA_SPAN,
                             trail_f=TRAIL_F, trail_pip=trail),
               n_holdout=len(hold), n_long=nl, n_short=len(hold)-nl,
               wr_holdout=wr, pf_holdout=pf, exp_pip=float(pnl.mean()),
               verdict=r['verdict'], score=r['rqs2_score'], gates=r['gates'],
               notes=r.get('notes'))
    with open(os.path.join(OUT_DIR, 's832_judgment_h1.json'), 'w') as f:
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
    ls, ss, sl_pip, tp_pip, trail = build_features(df)
    print(f'events: total L={int(ls.sum())} S={int(ss.sum())} | '
          f'explore L={int(ls[:SPLIT_IDX].sum())} S={int(ss[:SPLIT_IDX].sum())} | '
          f'holdout L={int(ls[SPLIT_IDX:].sum())} S={int(ss[SPLIT_IDX:].sum())} | '
          f'trail={trail:.1f}pip', flush=True)
    if a.null:
        phase_null(df, ls, ss, sl_pip, tp_pip, trail)
    if a.judge:
        phase_judge(df, ls, ss, sl_pip, tp_pip, trail)


if __name__ == '__main__':
    main()
