# -*- coding: utf-8 -*-
"""S1582 — شکستِ ساختاریِ داو (S758 خام، L=5 منجمد از results/s759/H4.json) × گیتِ حجمِ هم‌اسلات RVOL_slot≥1.0 (S589)

پیش‌ثبت: results/S1582_PREREG_VOLUME_CONFIRMED_STRUCTURE_BREAK.md (کامیت 2c31aea1، قبل از این کد)
هارنس: کپیِ عینیِ strategies/s759_addendum1_full.py (معاملات کل داده + split_bar=0.5، نول S8.build_null)؛
تنها تغییر: سیگنال = S758 خام × RVOL (به‌جای S758 × ρ).
بازوها: gated (داوری) | ungated (S758 خام، P1) | counter (RVOL<1، P2) | rho (=S759، مقایسهٔ گزارشی P4)
اجرا: python3 strategies/s1582_structure_break_volume.py <TF> [gated|ungated|counter|rho] [--stress]
فقط اکتشاف — هیچ استقراری.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as R2                   # noqa: E402
from strategies import s758_swing_structure as S8   # noqa: E402
from strategies import s759_informed_structure as S9  # noqa: E402

N_TRIALS = 3
SEED = 1582
RVOL_THR, SLOT_WIN, SLOT_MINP = 1.0, 30, 20
OUT_DIR = os.path.join(ROOT, 'results', '_s1582')
GEOM_SRC = os.path.join(ROOT, 'results', 's759', 'H4.json')   # BUG-GEOMDRIFT: L از آرتیفکت


def rvol_slot(df):
    v = df['volume'].astype(float)
    hour = pd.to_datetime(df['time'], unit='s').dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    return (v / ref.replace(0, np.nan)).to_numpy(float)


def main(tf, mode='gated', stress=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    L = int(json.load(open(GEOM_SRC))['winner']['L'])
    n_trials = 50 if stress else N_TRIALS
    tag = f'{tf}_{mode}{"_stress50" if stress else ""}'
    out_file = os.path.join(OUT_DIR, f'{tag}.json')
    print(f'\n=== S1582 StructureBreak×Volume :: XAUUSD-{tf} [{mode}] L={L} n_trials={n_trials} ===', flush=True)

    df, src = S9.load_tf(tf)
    assert 'mt5_full' in src, f'BUG-DATASETDRIFT src={src}'
    assert 'volume' in df.columns, 'BUG-NOVOLUME'
    t = pd.to_datetime(df['time'], unit='s')
    span = (t.iloc[-1] - t.iloc[0]).days / 365.25
    assert span > 12.0, f'BUG-DATASETDRIFT span={span:.2f}y'
    n_bars = len(df)
    split = int(n_bars * S9.SPLIT_FRAC)
    warmup = max(S9.ATR_P * 4, 400)
    atr_arr = S9.atr_pips(df)
    sl_arr = S9.SL_K * atr_arr
    tp_arr = S9.RR * sl_arr
    ok = np.isfinite(sl_arr) & (sl_arr > 0)
    med_sl = float(np.nanmedian(sl_arr[ok])); med_tp = float(np.nanmedian(tp_arr[ok]))
    zero = np.zeros(n_bars, bool)

    ls, _ = S8.structure_signals(df, L, atr_arr)          # S758 خام (لانگ)
    rv = rvol_slot(df)
    okv = np.isfinite(rv)
    base = ls & okv
    base[:warmup] = False
    n_ev = int(base.sum()); n_pass = int((base & (rv >= RVOL_THR)).sum())
    if mode == 'gated':
        g = base & (rv >= RVOL_THR)
    elif mode == 'counter':
        g = base & (rv < RVOL_THR)
    elif mode == 'rho':
        g = base & (S9.rho(df) >= S9.RHO_MIN)
    else:
        g = base.copy()
    tr = se.simulate_trades(df, g, zero, sl_arr, tp_arr, S9.ASSET,
                            max_hold=S9.MAX_HOLD, allow_overlap=False)
    n_tr = 0 if tr is None else len(tr)
    p3 = dict(n_events=n_ev, n_pass=n_pass, pass_rate=round(100.0 * n_pass / n_ev, 1) if n_ev else None,
              rvol_median_at_events=round(float(np.nanmedian(rv[base])), 3) if n_ev else None)
    print(f'src={src} bars={n_bars:,} span={span:.2f}y | events={n_ev} pass={n_pass} '
          f'({p3["pass_rate"]}%) rvol_med={p3["rvol_median_at_events"]} | sig={int(g.sum())} trades={n_tr}', flush=True)
    out = dict(card=f'S1582-XAUUSD-{tf}', mode=mode, asset=S9.ASSET, tf=tf, src=src, bars=n_bars,
               span_years=round(span, 2), L=L, split_bar=split, n_trials=n_trials, stress=stress,
               frozen=dict(L=L, rvol_thr=RVOL_THR, slot_win=SLOT_WIN, leg_k=S8.LEG_K, sl_k=S9.SL_K,
                           atr_p=S9.ATR_P, rr=S9.RR, hold=S9.MAX_HOLD, side='LONG-only'),
               p3_passrate=p3, n_trades=n_tr,
               entry_bars=[int(x) for x in tr['entry_bar'].values] if n_tr else [])
    if n_tr < 30:
        out['verdict'] = 'NO-TRADES' if n_tr == 0 else 'MEASUREMENT-LIMITED'
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1, default=float)
        print(out['verdict'], flush=True); return
    p = tr['pnl_pip'].to_numpy(float)
    out['raw'] = dict(wr=round(100 * float((p > 0).mean()), 2), e_pip=round(float(p.mean()), 2),
                      net_pip=round(float(p.sum()), 1))
    S8.SEED = SEED
    null = S8.build_null(df, g, zero, sl_arr, tp_arr, warmup, n_bars, K=S9.PERM_K, seed=SEED)
    r = R2.compute_rqs2(tr, S9.ASSET, n_trials=n_trials, sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=df['time'].values, null=null, split_bar=split,
                        close=df['close'].values.astype(np.float64))
    print(R2.format_rqs2(f'S1582-{tf}-{mode}', r), flush=True)
    for nt in r.get('notes', []):
        print('  ·', nt, flush=True)
    out.update(null=null, med_sl_pip=med_sl, med_tp_pip=med_tp, verdict=r.get('verdict'),
               rqs2_score=r.get('rqs2_score'), gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1, default=float)
    print(f'[checkpoint] {out_file}', flush=True)


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if x != '--stress']
    main(a[0] if a else 'H4', a[1] if len(a) > 1 else 'gated', '--stress' in sys.argv)
