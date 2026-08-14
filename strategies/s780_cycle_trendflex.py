# -*- coding: utf-8 -*-
"""
S780 — آزمون تأییدی یگانه روی نیمهٔ دوم (hold-out، مسیر C)
============================================================
⚠️ این اسکریپت نخستین و یگانه لمسِ نیمهٔ دوم داده است.
پیکربندی از commit پیش‌ثبت (results/S780_PREREG_cycle_trendflex_m30.md)
منجمد است — هیچ پارامتری اینجا قابل تغییر نیست.

مراحل (همه در یک اجرا، تا نیمهٔ دوم فقط یک بار لمس شود):
  ۱. شبیه‌سازی لایه روی نیمهٔ دوم با شبیه‌ساز رسمی.
  ۲. ساخت مدل پوچ اندازه‌گیری‌شده (بی‌قید + جای‌گشت K=1000، بذر 780) با
     همان شبیه‌ساز و همان قید عدم‌هم‌پوشانی — ذخیره یک‌باره در JSON.
  ۳. صدور حکم فقط توسط engine.rqs2.compute_rqs2 (هرگز دست‌نویس نه).
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
                   'results', '_s780')
os.makedirs(OUT, exist_ok=True)

# ── پیکربندی منجمد (از پیش‌ثبت — تغییرناپذیر) ────────────────────────────
ASSET = 'XAUUSD'
TF = 'M30'
IND = 'trendflex'
THR = 1.83
SL_ATR = 2.23
TP_ATR = 2.68
HOLD_HOURS = 72
SPLIT_EPOCH = 1_541_749_500   # مرز نیمه‌ها؛ آزمون روی time >= این مقدار
N_TRIALS = 1                  # مسیر C: یک لمس، یک آزمون
SEED = 780
K = 1000


def atr_pips(df, period=34):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(period).mean().values) / 0.10)


def event_cross(x, thr):
    x = np.asarray(x, dtype=float)
    p = np.roll(x, 1); p[0] = np.nan
    up = (p < thr) & (x >= thr) & np.isfinite(p)
    dn = (p > -thr) & (x <= -thr) & np.isfinite(p)
    return up, dn


def side_stats(tr, side):
    t = tr[tr['direction'] == side]
    if len(t) == 0:
        return dict(n=0, wr=None)
    return dict(n=int(len(t)), wr=100.0 * float((t['pnl_pip'] > 0).mean()))


def uncond_wr(df, side, sl_pip, tp_pip, max_hold, stride):
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    sig[200::stride] = True
    empty = np.zeros(n, dtype=bool)
    if side == 'long':
        tr = se.simulate_trades(df, sig, empty, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=ASSET, max_hold=max_hold, allow_overlap=False)
    else:
        tr = se.simulate_trades(df, empty, sig, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=ASSET, max_hold=max_hold, allow_overlap=False)
    if len(tr) == 0:
        return None, 0
    return 100.0 * float((tr['pnl_pip'] > 0).mean()), int(len(tr))


def perm_baseline(df, side, n_sig, sl_pip, tp_pip, max_hold, k, seed):
    """جای‌گشت زمانی: همان تعداد سیگنالِ خام در مکان‌های تصادفی، همان قیدها."""
    rng = np.random.default_rng(seed)
    n = len(df)
    lo, hi = 200, n - 2
    empty = np.zeros(n, dtype=bool)
    wrs = []
    for i in range(k):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        sig = np.zeros(n, dtype=bool); sig[pos] = True
        if side == 'long':
            tr = se.simulate_trades(df, sig, empty, sl_pip=sl_pip, tp_pip=tp_pip,
                                    asset=ASSET, max_hold=max_hold, allow_overlap=False)
        else:
            tr = se.simulate_trades(df, empty, sig, sl_pip=sl_pip, tp_pip=tp_pip,
                                    asset=ASSET, max_hold=max_hold, allow_overlap=False)
        if len(tr) >= 30:
            wrs.append(100.0 * float((tr['pnl_pip'] > 0).mean()))
        if (i + 1) % 100 == 0:
            print(f'    perm[{side}] {i+1}/{k}', flush=True)
    a = np.asarray(wrs, float)
    return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)),
                max=float(a.max()), min=float(a.min()),
                p95=float(np.percentile(a, 95)), k=int(len(a)))


def main():
    t0 = time.time()
    d = fd.load_fast(ASSET, TF)
    df_full = fd.as_dataframe(d)
    df = df_full.loc[df_full['time'].values >= SPLIT_EPOCH].reset_index(drop=True)
    print(f'src={d["src"]}')
    print(f'second half: {len(df)} bars '
          f'({pd.to_datetime(df["time"].iloc[0], unit="s")} .. '
          f'{pd.to_datetime(df["time"].iloc[-1], unit="s")})', flush=True)

    # هندسه طبق فرمول ثابت پیش‌ثبت: ATRmed(34) روی نیمهٔ آزمون
    ap = atr_pips(df)
    sl_pip = round(SL_ATR * ap, 1)
    tp_pip = round(TP_ATR * ap, 1)
    max_hold = fd.hold_bars_for(TF, HOLD_HOURS)
    print(f'ATRmed={ap:.1f}pip  SL={sl_pip}  TP={tp_pip}  max_hold={max_hold}', flush=True)

    # ── ۱) لایه ──
    v = np.asarray(ib.compute(IND, df), dtype=float)
    up, dn = event_cross(v, THR)
    n_sig_long, n_sig_short = int(up.sum()), int(dn.sum())
    tr = se.simulate_trades(df, up, dn, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset=ASSET, max_hold=max_hold, allow_overlap=False)
    n = len(tr)
    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
    be = 100.0 * sl_pip / (sl_pip + tp_pip)
    print(f'\nLAYER: n={n} wr={wr:.2f}% be(geo)={be:.2f}% lift={wr-be:+.2f}pp '
          f'net={tr["pnl_pip"].sum():+.0f}pip', flush=True)
    print(f'  long: {side_stats(tr,"long")}  short: {side_stats(tr,"short")}', flush=True)

    # ── ۲) مدل پوچ اندازه‌گیری‌شده ──
    nm_path = f'{OUT}/null_model.json'
    if os.path.exists(nm_path):
        print('null model exists — loading (built once, reused)', flush=True)
        null = json.load(open(nm_path))['null']
    else:
        null = {}
        payload_extra = {}
        for side, n_sig in (('long', n_sig_long), ('short', n_sig_short)):
            print(f'\n=== null[{side}]: uncond baselines ===', flush=True)
            rows = []
            for stride in (1, 3, 7):
                w, cnt = uncond_wr(df, side, sl_pip, tp_pip, max_hold, stride)
                rows.append((stride, w, cnt))
                print(f'  stride={stride}: n={cnt} wr={w:.2f}%', flush=True)
            u = max(r[1] for r in rows if r[1] is not None)
            print(f'  hardest uncond[{side}] = {u:.2f}%', flush=True)
            print(f'=== null[{side}]: permutation k={K} n_sig={n_sig} ===', flush=True)
            p = perm_baseline(df, side, n_sig, sl_pip, tp_pip, max_hold, K, SEED)
            print(f'  perm[{side}]: mean={p["mean"]:.2f} sd={p["sd"]:.2f} '
                  f'max={p["max"]:.2f} k={p["k"]}', flush=True)
            null[side] = dict(uncond_wr=u, perm_mean=p['mean'], perm_sd=p['sd'],
                              perm_max=p['max'], perm_k=p['k'])
            payload_extra[side] = dict(uncond=rows, perm=p)
        with open(nm_path, 'w') as f:
            json.dump(dict(card=f'{ASSET}_{TF}', seed=SEED, k=K,
                           sl_pip=sl_pip, tp_pip=tp_pip,
                           n_sig_long=n_sig_long, n_sig_short=n_sig_short,
                           detail=payload_extra, null=null),
                      f, ensure_ascii=False)
        print(f'null saved -> {nm_path}', flush=True)

    # ── ۳) حکم رسمی ──
    split_bar = int(0.70 * len(df))
    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=df['time'].values, null=null,
                         n_trials=N_TRIALS, split_bar=split_bar,
                         close=df['close'].values)
    print()
    print(R.format_rqs2('S780_CycleTrendflex_XAUUSD_M30', res))
    with open(f'{OUT}/XAUUSD_M30_rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/XAUUSD_M30_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/XAUUSD_M30_rqs2.json + trades.csv')
    print(f'elapsed: {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
