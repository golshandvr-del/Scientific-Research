# -*- coding: utf-8 -*-
"""S759 — Informed Structure Break (شکست ساختاری داو × کندل مطلع، فقط لانگ)

پیش‌ثبت: results/S759_PREREG_INFORMED_STRUCTURE_BREAK.md (کامیت aa6d720e — قبل از هر آزمون)

رویداد: سیگنال لانگ S758 (HL → شکست close از سقف میانی، کیفیت پا 1×ATR89)
  ∧ ρ[t] = (close−open)/(high−low) ≥ 0.618 (گیت منجمد S965/S1520).
LONG-only. خانواده L ∈ {3,5,8}. هندسه: SL=1.45×ATR89، TP=1.618×SL، hold=55.
پروتکل: مسیر C، n_trials=2 (S758+S759). نول: بی‌قیدِ همان‌براکت لانگ + K=500.
P1 (نیمهٔ اول): lift گیت‌شده > lift بی‌گیت برای L برنده.

اجرا:  python3 strategies/s759_informed_structure.py <TF>
خروجی: results/s759/<TF>.json
"""
import gc
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as R2                   # noqa: E402
from strategies import s758_swing_structure as S8   # noqa: E402

ASSET = 'XAUUSD'
PIP = se.ASSETS[ASSET]['pip']

FAMILY_L = (3, 5, 8)
RHO_MIN = 0.618
SL_K = S8.SL_K
ATR_P = S8.ATR_P
RR = S8.RR
MAX_HOLD = S8.MAX_HOLD
SPLIT_FRAC = 0.50
INNER_H7 = 0.60
PERM_K = 500
N_TRIALS = 2
SEED = 75959

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 's759')

load_tf = S8.load_tf
atr_pips = S8.atr_pips
crit = S8.crit


def rho(df):
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    rng_ = h - l
    with np.errstate(invalid='ignore', divide='ignore'):
        r = np.where(rng_ > 0, (c - o) / rng_, 0.0)
    return r


def informed_long(df, L, atr_arr):
    """لانگ S758 ∧ ρ ≥ 0.618. بازگشت: (gated, ungated) هر دو فقط لانگ."""
    ls, _ = S8.structure_signals(df, L, atr_arr)
    r = rho(df)
    gated = ls & (r >= RHO_MIN)
    return gated, ls


def build_null_long(df, ls, sl_arr, tp_arr, lo, hi, K=PERM_K, seed=SEED):
    """همان build_null S758 اما فقط سمت لانگ معنادار است (شورت n=0 → وزن صفر)."""
    ss = np.zeros(len(df), bool)
    S8.SEED = seed
    null = S8.build_null(df, ls, ss, sl_arr, tp_arr, lo, hi, K=K, seed=seed)
    return null


def _stats(tr):
    n = 0 if tr is None else len(tr)
    wr = float((tr['pnl_pip'] > 0).mean() * 100) if n else None
    net = float(tr['pnl_pip'].sum()) if n else None
    return n, wr, net


def _dump(out, out_file):
    json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
              default=float)


def main(tf):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_file = os.path.join(OUT_DIR, f'{tf}.json')
    print(f'\n{"=" * 78}\n=== S759 InformedStructure :: XAUUSD-{tf} ===', flush=True)

    df, src = load_tf(tf)
    n_bars = len(df)
    print(f'src={src}  bars={n_bars:,}', flush=True)
    out = dict(card=f'S759-XAUUSD-{tf}', asset=ASSET, tf=tf, src=src,
               bars=n_bars,
               frozen=dict(family_L=list(FAMILY_L), rho_min=RHO_MIN,
                           leg_k=S8.LEG_K, sl_k=SL_K, atr_p=ATR_P, rr=RR,
                           hold=MAX_HOLD, side='LONG-only', n_trials=N_TRIALS,
                           null='uncond same-bracket long + perm K=500'),
               protocol='C_holdout_prereg_S759')

    warmup = max(ATR_P * 4, 400)
    if n_bars < warmup + 200:
        out['verdict'] = 'INCOMPLETE'
        out['note'] = 'TOO_SHORT'
        _dump(out, out_file)
        print('TOO_SHORT — INCOMPLETE', flush=True)
        return

    split = int(n_bars * SPLIT_FRAC)
    atr_arr = atr_pips(df)
    sl_arr = SL_K * atr_arr
    tp_arr = RR * sl_arr
    ok_geo = np.isfinite(sl_arr) & (sl_arr > 0)
    med_sl = float(np.nanmedian(sl_arr[ok_geo])) if ok_geo.any() else None
    med_tp = float(np.nanmedian(tp_arr[ok_geo])) if ok_geo.any() else None
    zero = np.zeros(n_bars, bool)

    # ---------- کشف: نیمهٔ اول ----------
    print(f'-- discovery: bars [0,{split}) --', flush=True)
    df_d = df.iloc[:split].reset_index(drop=True)
    z_d = zero[:split]
    disc = []
    for L in FAMILY_L:
        g, u = informed_long(df_d, L, atr_arr[:split])
        g[:warmup] = False
        u[:warmup] = False
        tr_g = se.simulate_trades(df_d, g, z_d, sl_arr[:split], tp_arr[:split],
                                  ASSET, max_hold=MAX_HOLD, allow_overlap=False)
        tr_u = se.simulate_trades(df_d, u, z_d, sl_arr[:split], tp_arr[:split],
                                  ASSET, max_hold=MAX_HOLD, allow_overlap=False)
        ng, wrg, netg = _stats(tr_g)
        nu, wru, netu = _stats(tr_u)
        cval = crit(tr_g)
        pass_rate = (int(g.sum()) / int(u.sum()) * 100.0) if u.sum() else None
        disc.append(dict(L=L, n=ng, wr=wrg, net_pip=netg, crit=cval,
                         ungated_n=nu, ungated_wr=wru, ungated_net=netu,
                         gate_pass_rate_pct=pass_rate,
                         n_sig_gated=int(g.sum()), n_sig_ungated=int(u.sum())))
        print(f'   L={L:<3} gated n={ng:>5} wr={wrg} | ungated n={nu:>5} '
              f'wr={wru} | pass={pass_rate} crit={cval:.2f}', flush=True)
        del g, u, tr_g, tr_u
        gc.collect()
    del df_d
    gc.collect()
    out['discovery'] = disc

    valid = [d for d in disc if d['crit'] > -1e8 and d['n'] >= 30]
    if not valid:
        out['verdict'] = 'UNPROVEN'
        out['note'] = 'discovery: no config with n>=30'
        _dump(out, out_file)
        print('UNPROVEN — no viable discovery config', flush=True)
        return
    win = max(valid, key=lambda d: d['crit'])
    # P1: نیمهٔ اول — WR گیت‌شده در برابر بی‌گیت (همان نول ⇒ تفاضل WR = تفاضل lift)
    p1 = None
    if win['wr'] is not None and win['ungated_wr'] is not None:
        p1 = dict(gated_wr=win['wr'], ungated_wr=win['ungated_wr'],
                  delta_pp=round(win['wr'] - win['ungated_wr'], 2),
                  passed=bool(win['wr'] > win['ungated_wr']))
    print(f'-- winner: L={win["L"]} crit={win["crit"]:.2f} | P1={p1} --',
          flush=True)
    out['winner'] = dict(L=win['L'], crit=win['crit'])
    out['P1_first_half'] = p1

    # ---------- یک آزمون واحد روی holdout ----------
    g, u = informed_long(df, win['L'], atr_arr)
    g[:split] = False
    u[:split] = False
    tr = se.simulate_trades(df, g, zero, sl_arr, tp_arr, ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
    n_tr, wr_h, net_h = _stats(tr)
    pass_h = (int(g.sum()) / int(u.sum()) * 100.0) if u.sum() else None
    print(f'-- holdout: bars [{split},{n_bars}) sig gated/ungated='
          f'{int(g.sum())}/{int(u.sum())} (pass {pass_h}) trades={n_tr} --',
          flush=True)
    if n_tr == 0:
        out['verdict'] = 'UNPROVEN'
        out['note'] = 'holdout produced no trades'
        _dump(out, out_file)
        return
    print(f'   WR={wr_h:.2f}%  net={net_h:.1f} pip', flush=True)

    null = build_null_long(df, g, sl_arr, tp_arr, split, n_bars)
    if null is None:
        print('   WARN: null unavailable — H3 UNKNOWN', flush=True)
    else:
        nd = null['long']
        print(f'   null[long]: uncond={nd["uncond_wr"]} '
              f'perm_mean={nd["perm_mean"]} perm_sd={nd["perm_sd"]} '
              f'k={nd["perm_k"]}', flush=True)

    inner_split = split + int((n_bars - split) * INNER_H7)
    r = R2.compute_rqs2(tr, ASSET, n_trials=N_TRIALS,
                        sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=df['time'].values, null=null,
                        split_bar=inner_split,
                        close=df['close'].values.astype(np.float64))
    print(R2.format_rqs2(f'S759-{tf} HOLDOUT-C', r), flush=True)
    for nt in r.get('notes', []):
        print('  ·', nt, flush=True)

    out.update(n_holdout_trades=n_tr, holdout_wr=round(wr_h, 2),
               holdout_net_pip=round(net_h, 1),
               n_sig_gated=int(g.sum()), n_sig_ungated=int(u.sum()),
               gate_pass_rate_holdout_pct=pass_h,
               med_sl_pip=med_sl, med_tp_pip=med_tp,
               null=null, inner_split=inner_split, n_trials=N_TRIALS,
               perm_k=PERM_K,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    _dump(out, out_file)
    print(f'[checkpoint] {out_file}', flush=True)
    print('NOTE: protocol C — holdout must NOT be re-tested.', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'M1')
