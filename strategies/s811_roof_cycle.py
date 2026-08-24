"""
s811_roof_cycle.py — لایه‌ی S811: تریگر چرخه‌ای Roofing اهلرز + مجوز رژیم hurst
================================================================================

پیش‌ثبت: results/S811_PREREG_ROOF_CYCLE_HOLDOUT.md (کامیت 40d70bc7 — پیش از هر آزمون)
مسیر چندگانگی: C. برش: 2019-01-01 (epoch 1546300800).

سه فاز مجزا (الگوی موفق S810):
  --search : ۷۲ ترکیب قفل‌شده فقط روی نیمه‌ی اول. غربال جای‌گشتی K=12.
  --null   : صفر سنجیده K=500 برای برنده، روی رخدادهای واجد نیمه‌ی دوم.
  --judge  : یک (۱) آزمون هولد‌اوت با rqs2.compute_rqs2؛ سپس قفل.

بند صداقتی پیش‌ثبت (بند ۷): اگر max_z نیمه‌ی اول < expected_max_z(72)≈2.44
باشد، هولد‌اوت سوزانده نمی‌شود و لایه با غربال MTF بسته می‌شود.

forward-safety: رخداد = تغییر علامت roof بین t-1 و t؛ سیگنال روی t؛ موتور
در open کندل t+1 پر می‌کند. roof و hurst فقط از داده‌ی گذشته محاسبه می‌شوند
(فیلترهای علّی — بدون look-ahead ذاتی).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from engine import indicator_bank as ib       # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s811')
os.makedirs(OUT_DIR, exist_ok=True)

SPLIT_EPOCH = 1546300800
SEED = 811
N_PERM = 500

# ---- فضای قفل‌شده (عیناً از پیش‌ثبت) ----
LOGICS    = ['cycle', 'anti']
GATES     = ['none', 'h50', 'h40']       # بدون دروازه / hurst<0.5 / hurst<0.4
SL_PIPS   = [15, 30, 50]
RRS       = [1.0, 1.5]
MAX_HOLDS = [60, 240]
EXPECTED_MAX_Z_72 = 2.44                  # بند صداقتی


def load():
    d = fd.load_fast('XAUUSD', 'M1')
    df = fd.as_dataframe(d)
    return d, df


def compute_features(df):
    cache = os.path.join(OUT_DIR, 'features_m1.npz')
    if os.path.exists(cache):
        z = np.load(cache)
        return z['roof'], z['hurst']
    roof = np.asarray(ib.compute('roof', df), dtype=np.float64)
    hurst = np.asarray(ib.compute('hurst', df), dtype=np.float64)
    np.savez_compressed(cache, roof=roof, hurst=hurst)
    return roof, hurst


def cross_events(roof):
    n = len(roof)
    up = np.zeros(n, bool)
    dn = np.zeros(n, bool)
    up[1:] = (roof[1:] > 0) & (roof[:-1] <= 0)
    dn[1:] = (roof[1:] < 0) & (roof[:-1] >= 0)
    return up, dn


def gate_mask(hurst, gate):
    if gate == 'none':
        return np.ones(len(hurst), bool)
    thr = 0.5 if gate == 'h50' else 0.4
    return np.nan_to_num(hurst, nan=1.0) < thr


def build_signals(up, dn, gm, logic, half_mask=None):
    if logic == 'cycle':
        ls, ss = up & gm, dn & gm
    else:
        ls, ss = dn & gm, up & gm
    if half_mask is not None:
        ls, ss = ls & half_mask, ss & half_mask
    return ls, ss


def wr_pct(tr):
    if tr is None or len(tr) == 0:
        return None
    return float((tr['outcome'].values == 'win').mean() * 100.0)


# ============================ فاز ۱: جست‌وجو ============================

def phase_search(df, roof, hurst):
    rng = np.random.default_rng(SEED)
    t = df['time'].values
    first = t < SPLIT_EPOCH
    up, dn = cross_events(roof)
    rows, cid = [], 0
    out_json = os.path.join(OUT_DIR, 'search_first_half.json')
    if os.path.exists(out_json):
        rows = json.load(open(out_json))
    done = {r['combo'] for r in rows}
    for logic in LOGICS:
        for gate in GATES:
            gm = gate_mask(hurst, gate)
            ls_all, ss_all = build_signals(up, dn, gm, logic, first)
            for sl in SL_PIPS:
                for rr in RRS:
                    tp = sl * rr
                    for mh in MAX_HOLDS:
                        cid += 1
                        if cid in done:
                            continue
                        tr = se.simulate_trades(df, ls_all, ss_all,
                                                sl_pip=sl, tp_pip=tp,
                                                asset='XAUUSD', max_hold=mh,
                                                allow_overlap=False)
                        n = 0 if tr is None else len(tr)
                        w = wr_pct(tr)
                        lift = z = None
                        if n >= 500 and w is not None:
                            # غربال جای‌گشتی ارزان: جهت تصادفی روی همان کندل‌های سیگنال
                            sig = ls_all | ss_all
                            perms = []
                            for _ in range(12):
                                flip = rng.random(len(df)) < 0.5
                                ptr = se.simulate_trades(
                                    df, sig & flip, sig & ~flip,
                                    sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                    max_hold=mh, allow_overlap=False)
                                pw = wr_pct(ptr)
                                if pw is not None:
                                    perms.append(pw)
                            if len(perms) >= 8:
                                pm = float(np.mean(perms))
                                psd = float(np.std(perms) + 1e-9)
                                lift = w - pm
                                z = lift / psd
                        pnl = float(tr['pnl_pip'].sum()) if n else 0.0
                        rows.append(dict(combo=cid, logic=logic, gate=gate,
                                         sl=sl, rr=rr, tp=tp, mh=mh, n=n,
                                         wr=w, lift=lift, z=z,
                                         pnl_pip=round(pnl, 1)))
                        print(f'  [{cid}/72] {logic}/{gate} SL={sl} RR={rr} '
                              f'mh={mh} n={n} wr={w and round(w,2)} '
                              f'lift={lift and round(lift,2)} z={z and round(z,2)}',
                              flush=True)
                        with open(out_json, 'w') as f:
                            json.dump(rows, f, indent=1)
    cand = [r for r in rows if r['z'] is not None and r['lift'] and r['lift'] > 0]
    # در تساوی z: دروازه‌ی ساده‌تر (none قبل از h50 قبل از h40) — کم‌پارامتر می‌بَرد
    order = {'none': 0, 'h50': 1, 'h40': 2}
    cand.sort(key=lambda r: (-r['z'], order[r['gate']]))
    winner = cand[0] if cand else None
    max_z = max((r['z'] for r in rows if r['z'] is not None), default=None)
    summary = dict(winner=winner, max_z=max_z,
                   expected_max_z_72=EXPECTED_MAX_Z_72,
                   honesty_gate_passed=(max_z is not None and max_z >= EXPECTED_MAX_Z_72))
    with open(os.path.join(OUT_DIR, 'winner.json'), 'w') as f:
        json.dump(summary, f, indent=1)
    print('[search] SUMMARY:', json.dumps(summary, indent=1))
    return summary


# ============================ فاز ۲: صفر سنجیده ============================

def phase_null(df, roof, hurst, winner):
    rng = np.random.default_rng(SEED + 1)
    t = df['time'].values
    second = t >= SPLIT_EPOCH
    up, dn = cross_events(roof)
    gm = gate_mask(hurst, winner['gate'])
    ls, ss = build_signals(up, dn, gm, winner['logic'], second)
    sl, tp, mh = winner['sl'], winner['tp'], winner['mh']

    # لایه‌ی واقعی روی نیمه‌ی دوم — برای n به‌ازای هر سمت (پس از فشردگی allow_overlap)
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp,
                            asset='XAUUSD', max_hold=mh, allow_overlap=False)
    n_long = int((tr['direction'].values == 'long').sum())
    n_short = int((tr['direction'].values == 'short').sum())
    print(f'[null] layer trades on holdout: long={n_long} short={n_short}')

    sig = ls | ss
    sig_idx = np.where(sig)[0]
    z0 = np.zeros(len(df), bool)
    out = {}
    for side, n_side in (('long', n_long), ('short', n_short)):
        one = np.zeros(len(df), bool); one[sig_idx] = True
        utr = se.simulate_trades(df, one if side == 'long' else z0,
                                 z0 if side == 'long' else one,
                                 sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                 max_hold=mh, allow_overlap=False)
        uncond = wr_pct(utr)
        perms = []
        for k in range(N_PERM):
            flip = rng.random(len(df)) < 0.5
            ptr = se.simulate_trades(df, sig & flip, sig & ~flip,
                                     sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                     max_hold=mh, allow_overlap=False)
            if ptr is not None and len(ptr):
                dmask = ptr['direction'].values == side
                if dmask.sum() > 0:
                    perms.append(float((ptr['outcome'].values[dmask] == 'win').mean() * 100))
            if (k + 1) % 50 == 0:
                print(f'  [null:{side}] perm {k+1}/{N_PERM}', flush=True)
        out[side] = dict(uncond_wr=uncond,
                         perm_mean=float(np.mean(perms)) if perms else None,
                         perm_sd=float(np.std(perms)) if perms else None,
                         perm_max=float(np.max(perms)) if perms else None,
                         perm_k=len(perms))
        print(f'[null] {side}: {out[side]}')
    with open(os.path.join(OUT_DIR, 'null_holdout.json'), 'w') as f:
        json.dump(out, f, indent=1)
    return out


# ============================ فاز ۳: داوری ============================

def phase_judge(df, roof, hurst, winner, null):
    lock = os.path.join(OUT_DIR, 'HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('⛔ هولد‌اوت مصرف شده — آزمون دوم ممنوع (مسیر C).')
        return None
    split_idx = int(np.searchsorted(df['time'].values, SPLIT_EPOCH))
    up, dn = cross_events(roof)
    gm = gate_mask(hurst, winner['gate'])
    second = df['time'].values >= SPLIT_EPOCH
    ls, ss = build_signals(up, dn, gm, winner['logic'], second)
    tr = se.simulate_trades(df, ls, ss, sl_pip=winner['sl'], tp_pip=winner['tp'],
                            asset='XAUUSD', max_hold=winner['mh'],
                            allow_overlap=False)
    hold = tr[tr['entry_bar'].values >= split_idx].reset_index(drop=True)
    print(f'[judge] holdout trades: {len(hold)} (total {len(tr)})')
    r = rqs2.compute_rqs2(
        hold, 'XAUUSD',
        sl_pip=winner['sl'], tp_pip=winner['tp'],
        bar_time=df['time'].values, null=null, n_trials=1,
        split_bar=split_idx, close=df['close'].values)
    with open(lock, 'w') as f:
        f.write('holdout spent — one test only (path C)\n')
    res = dict(winner=winner, verdict=r['verdict'], score=r['rqs2_score'],
               gates=r['gates'], metrics=r['metrics'], notes=r['notes'])
    with open(os.path.join(OUT_DIR, 'judgment_m1.json'), 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print('VERDICT:', r['verdict'], 'SCORE:', r['rqs2_score'])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--search', action='store_true')
    ap.add_argument('--null', action='store_true')
    ap.add_argument('--judge', action='store_true')
    a = ap.parse_args()

    d, df = load()
    print('src:', d['src'])
    roof, hurst = compute_features(df)
    print(f'features ready: roof[{len(roof)}], hurst[{len(hurst)}]')

    if a.search:
        phase_search(df, roof, hurst)
    if a.null or a.judge:
        summary = json.load(open(os.path.join(OUT_DIR, 'winner.json')))
        if not summary.get('honesty_gate_passed'):
            print('⛔ بند صداقتی: max_z نیمه‌ی اول زیر آستانه‌ی نویز است — '
                  'هولد‌اوت سوزانده نمی‌شود. لایه با غربال MTF بسته می‌شود.')
            return
        winner = summary['winner']
        if a.null:
            phase_null(df, roof, hurst, winner)
        if a.judge:
            null = json.load(open(os.path.join(OUT_DIR, 'null_holdout.json')))
            phase_judge(df, roof, hurst, winner, null)


if __name__ == '__main__':
    main()
