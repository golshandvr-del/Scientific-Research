# -*- coding: utf-8 -*-
"""
S783 — آزمون تأییدی یگانه روی hold-out (مسیر C اصلاح‌شده)
==========================================================
پیکربندی منجمد از پیش‌ثبت (results/S783_PREREG_er_lucas18_h1.md،
commit 8d07bc64) — هیچ پارامتری قابل تغییر نیست.

state = (er_lucas_18 >= 0.53) AND sign(close - close[18])
سیگنال رویدادی: state-entry (True پس از False)، هر جهت جدا.
XAUUSD-H1، SL=1.53×ATRmed(34)، TP=1.91×ATRmed(34)، max_hold=72، تک‌پوزیشن.
hold-out: time >= 1661990400 (2022-09-01) — نخستین و تنها لمس.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from engine import rqs2 as R
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s783')
os.makedirs(OUT, exist_ok=True)

# ── منجمد (از PREREG 8d07bc64) ──
ASSET, TF = 'XAUUSD', 'H1'
ER_IND, ER_W, THR = 'er_lucas_18', 18, 0.53
SL_ATR, TP_ATR, HOLD_HOURS = 1.53, 1.91, 72
HOLDOUT_EPOCH = 1_661_990_400
N_TRIALS, SEED, K = 1, 783, 1000


def atr_pips(df, period=34):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(period).mean().values) / 0.10)


def state_entry(s):
    s = np.asarray(s, bool)
    p = np.roll(s, 1); p[0] = True
    return s & ~p


def uncond_wr(df, side, sl, tp, mh, stride):
    n = len(df); sig = np.zeros(n, bool); sig[300::stride] = True
    e = np.zeros(n, bool)
    a = (sig, e) if side == 'long' else (e, sig)
    tr = se.simulate_trades(df, a[0], a[1], sl_pip=sl, tp_pip=tp, asset=ASSET,
                            max_hold=mh, allow_overlap=False)
    return (100.0 * float((tr['pnl_pip'] > 0).mean()), len(tr)) if len(tr) else (None, 0)


def perm_baseline(df, side, n_sig, sl, tp, mh, k, seed):
    rng = np.random.default_rng(seed)
    n = len(df); lo, hi = 300, n - 2
    e = np.zeros(n, bool)
    wrs = []
    for i in range(k):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        sig = np.zeros(n, bool); sig[pos] = True
        a = (sig, e) if side == 'long' else (e, sig)
        tr = se.simulate_trades(df, a[0], a[1], sl_pip=sl, tp_pip=tp, asset=ASSET,
                                max_hold=mh, allow_overlap=False)
        if len(tr) >= 30:
            wrs.append(100.0 * float((tr['pnl_pip'] > 0).mean()))
        if (i + 1) % 200 == 0:
            print(f'    perm[{side}] {i+1}/{k}', flush=True)
    a = np.asarray(wrs, float)
    return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()),
                min=float(a.min()), p95=float(np.percentile(a, 95)), k=int(len(a)))


def main():
    t0 = time.time()
    d = fd.load_fast(ASSET, TF)
    dfF = fd.as_dataframe(d)
    df = dfF.loc[dfF['time'].values >= HOLDOUT_EPOCH].reset_index(drop=True)
    print(f'src={d["src"]}')
    print(f'hold-out: {len(df)} bars '
          f'({pd.to_datetime(df["time"].iloc[0], unit="s")} .. '
          f'{pd.to_datetime(df["time"].iloc[-1], unit="s")})', flush=True)

    ap = atr_pips(df)
    sl = round(SL_ATR * ap, 1); tp = round(TP_ATR * ap, 1)
    mh = fd.hold_bars_for(TF, HOLD_HOURS)
    print(f'ATRmed={ap:.1f}  SL={sl}  TP={tp}  max_hold={mh}', flush=True)

    er = np.nan_to_num(np.asarray(ib.compute(ER_IND, df), float))
    c = df['close'].values.astype(float)
    net = c - np.roll(c, ER_W); net[:ER_W] = 0.0
    up = state_entry((er >= THR) & (net > 0))
    dn = state_entry((er >= THR) & (net < 0))
    n_sig_long, n_sig_short = int(up.sum()), int(dn.sum())
    print(f'signals: long={n_sig_long} short={n_sig_short}', flush=True)

    tr = se.simulate_trades(df, up, dn, sl_pip=sl, tp_pip=tp, asset=ASSET,
                            max_hold=mh, allow_overlap=False)
    n = len(tr)
    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
    be = 100.0 * sl / (sl + tp)
    print(f'\nLAYER: n={n} wr={wr:.2f}% be={be:.2f}% lift={wr-be:+.2f}pp '
          f'net={tr["pnl_pip"].sum():+.0f}pip', flush=True)
    for side in ('long', 'short'):
        t = tr[tr['direction'] == side]
        if len(t):
            print(f'  {side}: n={len(t)} wr={100.0*(t["pnl_pip"]>0).mean():.2f}% '
                  f'net={t["pnl_pip"].sum():+.0f}', flush=True)

    nm_path = f'{OUT}/null_model.json'
    if os.path.exists(nm_path):
        null = json.load(open(nm_path))['null']
        print('null model loaded (built once)', flush=True)
    else:
        null, detail = {}, {}
        for side, n_sig in (('long', n_sig_long), ('short', n_sig_short)):
            print(f'\n=== null[{side}]: uncond ===', flush=True)
            rows = []
            for stride in (1, 3, 7):
                w, cnt = uncond_wr(df, side, sl, tp, mh, stride)
                rows.append((stride, w, cnt))
                print(f'  stride={stride}: n={cnt} wr={w:.2f}%', flush=True)
            u = max(r[1] for r in rows if r[1] is not None)
            print(f'=== null[{side}]: perm k={K} n_sig={n_sig} ===', flush=True)
            p = perm_baseline(df, side, n_sig, sl, tp, mh, K, SEED)
            print(f'  perm[{side}]: mean={p["mean"]:.2f} sd={p["sd"]:.2f} '
                  f'max={p["max"]:.2f} k={p["k"]}', flush=True)
            null[side] = dict(uncond_wr=u, perm_mean=p['mean'], perm_sd=p['sd'],
                              perm_max=p['max'], perm_k=p['k'])
            detail[side] = dict(uncond=rows, perm=p)
        json.dump(dict(card=f'{ASSET}_{TF}', seed=SEED, k=K, sl_pip=sl, tp_pip=tp,
                       n_sig_long=n_sig_long, n_sig_short=n_sig_short,
                       detail=detail, null=null),
                  open(nm_path, 'w'), ensure_ascii=False)
        print(f'null saved -> {nm_path}', flush=True)

    split_bar = int(0.70 * len(df))
    res = R.compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                         bar_time=df['time'].values, null=null,
                         n_trials=N_TRIALS, split_bar=split_bar,
                         close=df['close'].values)
    print()
    print(R.format_rqs2('S783_ErLucas18_XAUUSD_H1', res))
    json.dump(res, open(f'{OUT}/XAUUSD_H1_rqs2.json', 'w'),
              ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/XAUUSD_H1_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/XAUUSD_H1_rqs2.json + trades.csv')
    print(f'elapsed: {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
