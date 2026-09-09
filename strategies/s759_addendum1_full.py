# -*- coding: utf-8 -*-
"""S759 — ADDENDUM 1: داوری استاندارد پروژه (معاملات کل داده + split_bar)

پیش‌ثبت الحاقیه: results/S759_PREREG_ADDENDUM_1_H6_PIPELINE_FIX.md
قاعده/L/ρ/هندسه: عیناً از results/s759/<TF>.json (برندهٔ کشف) — صفر تغییر.
تفاوت: معاملات کل داده به موتور داده می‌شود، split_bar=split (H7=نیمهٔ دوم)،
نول بی‌قید لانگ روی استخر کل داده. n_trials=3.

اجرا:  python3 strategies/s759_addendum1_full.py <TF>
خروجی: results/s759_addendum1/<TF>.json
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as R2                   # noqa: E402
from strategies import s758_swing_structure as S8   # noqa: E402
from strategies import s759_informed_structure as S9  # noqa: E402

N_TRIALS = 3
SEED = 75959
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'results', 's759_addendum1')


def main(tf):
    os.makedirs(OUT_DIR, exist_ok=True)
    src_card = os.path.join(ROOT, 'results', 's759', f'{tf}.json')
    orig = json.load(open(src_card))
    out_file = os.path.join(OUT_DIR, f'{tf}.json')
    print(f'\n{"=" * 78}\n=== S759 ADDENDUM-1 (full-data adjudication) :: XAUUSD-{tf} ===',
          flush=True)
    if not orig.get('winner'):
        out = dict(card=f'S759A1-XAUUSD-{tf}', tf=tf, verdict=orig.get('verdict'),
                   note='no discovery winner in original card; nothing to adjudicate')
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1)
        print(out['note'], flush=True)
        return
    L = int(orig['winner']['L'])

    df, src = S9.load_tf(tf)
    assert 'mt5_full' in src
    n_bars = len(df)
    split = int(n_bars * S9.SPLIT_FRAC)
    warmup = max(S9.ATR_P * 4, 400)
    atr_arr = S9.atr_pips(df)
    sl_arr = S9.SL_K * atr_arr
    tp_arr = S9.RR * sl_arr
    ok = np.isfinite(sl_arr) & (sl_arr > 0)
    med_sl = float(np.nanmedian(sl_arr[ok]))
    med_tp = float(np.nanmedian(tp_arr[ok]))
    zero = np.zeros(n_bars, bool)

    g, u = S9.informed_long(df, L, atr_arr)
    g[:warmup] = False
    tr = se.simulate_trades(df, g, zero, sl_arr, tp_arr, S9.ASSET,
                            max_hold=S9.MAX_HOLD, allow_overlap=False)
    n_tr = 0 if tr is None else len(tr)
    n_first = int((tr['entry_bar'].values < split).sum()) if n_tr else 0
    print(f'src={src} bars={n_bars:,} L={L} trades full={n_tr} '
          f'(first-half={n_first}, second-half={n_tr - n_first})', flush=True)
    out = dict(card=f'S759A1-XAUUSD-{tf}', asset=S9.ASSET, tf=tf, src=src,
               bars=n_bars, L=L, split_bar=split, n_trials=N_TRIALS,
               protocol='project-standard: full-data trades + split_bar (S965/S770)',
               frozen=orig['frozen'], n_trades_full=n_tr,
               n_first_half=n_first, n_second_half=n_tr - n_first)
    if n_tr == 0:
        out['verdict'] = 'UNPROVEN'
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
                  default=float)
        return

    S8.SEED = SEED
    null = S8.build_null(df, g, zero, sl_arr, tp_arr, warmup, n_bars,
                         K=S9.PERM_K, seed=SEED)
    if null:
        nd = null['long']
        print(f'   null[long]: uncond={nd["uncond_wr"]} perm_mean={nd["perm_mean"]} '
              f'perm_sd={nd["perm_sd"]} k={nd["perm_k"]}', flush=True)

    r = R2.compute_rqs2(tr, S9.ASSET, n_trials=N_TRIALS,
                        sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=df['time'].values, null=null,
                        split_bar=split,
                        close=df['close'].values.astype(np.float64))
    print(R2.format_rqs2(f'S759A1-{tf} FULL', r), flush=True)
    for nt in r.get('notes', []):
        print('  ·', nt, flush=True)
    out.update(null=null, med_sl_pip=med_sl, med_tp_pip=med_tp,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'),
               original_holdout_verdict=orig.get('verdict'),
               original_holdout_score=orig.get('rqs2_score'))
    json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
              default=float)
    print(f'[checkpoint] {out_file}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'H4')
