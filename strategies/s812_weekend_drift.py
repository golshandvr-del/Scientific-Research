"""
s812_weekend_drift.py — لایه‌ی S812: دریفت تقویمی آخرهفته (XAUUSD-M1)
=====================================================================

پیش‌ثبت: results/S812_PREREG_WEEKEND_CALENDAR_DRIFT_HOLDOUT.md (کامیت 96462d44)
مسیر C: جست‌وجوی ۱۶ بازو فقط نیمه‌ی اول؛ دروازه‌ی صداقتی (max_z≥1.90 و
lift≥8pp و expectancy>0)؛ سپس یک آزمون هولد‌اوت با n_trials=1 و قفل.

فازها:
  --search : ۱۶ بازو روی نیمه‌ی اول → results/_s812/search_first_half.json
  --null   : null اندازه‌گیری‌شده K=500 روی نیمه‌ی دوم (فقط پس از عبور دروازه)
  --judge  : یک آزمون نهایی + HOLDOUT_SPENT.lock

forward-safety: رخداد = اولین کندل واجد شرط پنجره؛ سیگنال روی همان کندل؛
موتور در open کندل بعد پر می‌کند. ADR21/vol_ref فقط از روزهای کاملِ قبل.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUTDIR = os.path.join(ROOT, 'results', '_s812')
SPLIT_EPOCH = 1546300800  # 2019-01-01 UTC
SEED = 813
K_PERM = 500
GEOM_K = 1.618          # SL = TP = 1.618 * ADR21 (pip), floor 30
SL_FLOOR = 30.0
QV_Q = 0.80
QV_WIN = 250
QV_MIN = 60

WINDOWS = {
    'FRI_DAY': dict(wd=4, hh=0,  mh=1320),
    'FRI_PM':  dict(wd=4, hh=12, mh=600),
    'WKND':    dict(wd=4, hh=21, mh=420),
    'MON_DAY': dict(wd=0, hh=0,  mh=1320),
}
ARMS = [(w, d, f) for w in WINDOWS for d in ('LONG', 'SHORT')
        for f in ('none', 'qv80')]  # 16


def build_daily(t, h, l):  # noqa: E741
    """روزهای کامل (به تقویم سرور) + دامنه‌ی روزانه — اکیداً علّی در مصرف."""
    day = t // 86400
    dser = pd.DataFrame({'day': day, 'h': h, 'l': l})
    g = dser.groupby('day')
    agg = g.agg(hi=('h', 'max'), lo=('l', 'min'))
    agg['range'] = agg['hi'] - agg['lo']
    return agg  # index=day number


def causal_maps(agg):
    """برای هر روز d: ADR21 و vol_ref و آستانه‌ی qv از روزهای < d."""
    days = agg.index.values
    rng_ = agg['range'].values
    adr21 = pd.Series(rng_).rolling(21).mean().shift(1).values
    vref = pd.Series(rng_).rolling(14).mean().shift(1).values
    qv_thr = (pd.Series(vref).rolling(QV_WIN, min_periods=QV_MIN)
              .quantile(QV_Q).shift(1).values)
    return (dict(zip(days, adr21)), dict(zip(days, vref)),
            dict(zip(days, qv_thr)))


def find_events(t):
    """برای هر پنجره: ایندکس اولین کندلِ واجد شرط در هر روزِ مربوط."""
    tt = pd.to_datetime(t, unit='s')
    wd = tt.weekday.values
    hh = tt.hour.values
    day = t // 86400
    ev = {}
    for wname, cfg in WINDOWS.items():
        m = (wd == cfg['wd']) & (hh >= cfg['hh'])
        idx = np.where(m)[0]
        if len(idx) == 0:
            ev[wname] = np.array([], np.int64)
            continue
        d = day[idx]
        first = np.ones(len(idx), bool)
        first[1:] = d[1:] != d[:-1]
        ev[wname] = idx[first]
    return ev


def arm_signals(events, n, day, adr_map, vref_map, qv_map, window,
                direction, filt):
    """سیگنال + آرایه‌ی sl_pip برای یک بازو. رخدادهای بدون ADR معتبر حذف."""
    ls = np.zeros(n, bool)
    ss = np.zeros(n, bool)
    slp = np.full(n, np.nan)
    kept = 0
    for i in events[window]:
        d = day[i]
        adr = adr_map.get(d, np.nan)
        if not np.isfinite(adr) or adr <= 0:
            continue
        if filt == 'qv80':
            vr = vref_map.get(d, np.nan)
            qt = qv_map.get(d, np.nan)
            if not np.isfinite(vr) or not np.isfinite(qt) or vr > qt:
                continue
        sl = max(SL_FLOOR, GEOM_K * adr / 0.1)  # pip
        if direction == 'LONG':
            ls[i] = True
        else:
            ss[i] = True
        slp[i] = sl
        kept += 1
    return ls, ss, slp, kept


def run_arm(df, ls, ss, slp, mh):
    sl_arr = np.where(np.isfinite(slp), slp, SL_FLOOR)
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                            asset='XAUUSD', max_hold=mh, allow_overlap=False)
    return tr


def stats_of(tr):
    if tr is None or len(tr) == 0:
        return dict(n=0)
    wr = float((tr['outcome'].values == 'win').mean() * 100)
    pnl = float(tr['pnl_pip'].sum())
    return dict(n=int(len(tr)), wr=round(wr, 3),
                pnl_pip=round(pnl, 1),
                exp_pip=round(pnl / len(tr), 3))


def phase_search(df, ev, day, adr_map, vref_map, qv_map, rng):
    first = df['time'].values < SPLIT_EPOCH
    n = len(df)
    rows = []
    for (w, dr, f) in ARMS:
        ls, ss, slp, kept = arm_signals(ev, n, day, adr_map, vref_map,
                                        qv_map, w, dr, f)
        ls &= first
        ss &= first
        mh = WINDOWS[w]['mh']
        tr = run_arm(df, ls, ss, slp, mh)
        st = stats_of(tr)
        if st['n'] < 30:
            rows.append(dict(window=w, dir=dr, filt=f, **st,
                             note='too few'))
            print(f'{w:8s} {dr:5s} {f:5s} n={st["n"]} too few', flush=True)
            continue
        # null کوچک نیمه‌ی اول (K=60) برای z جست‌وجو — فقط رتبه‌بندی
        sig = ls | ss
        perms = []
        for _ in range(60):
            flip = rng.random(n) < 0.5
            pls = sig & flip
            pss = sig & ~flip
            ptr = run_arm(df, pls, pss, slp, mh)
            if ptr is not None and len(ptr):
                perms.append(float((ptr['outcome'].values == 'win').mean()
                                   * 100))
        pm = float(np.mean(perms))
        psd = max(float(np.std(perms, ddof=1)), 1e-9)
        lift = st['wr'] - pm
        z = lift / psd if psd > 0 else 0.0
        # z مقیاس‌شده به SE دوجمله‌ای (perm_sd خودش SE توزیع WR جای‌گشت است)
        rows.append(dict(window=w, dir=dr, filt=f, **st,
                         perm_mean=round(pm, 3), perm_sd=round(psd, 4),
                         lift_pp=round(lift, 3), z=round(z, 2)))
        print(f'{w:8s} {dr:5s} {f:5s} n={st["n"]:4d} wr={st["wr"]:6.2f} '
              f'lift={lift:+6.2f} z={z:+5.2f} exp={st["exp_pip"]:+7.2f}',
              flush=True)
    json.dump(rows, open(os.path.join(OUTDIR, 'search_first_half.json'),
                         'w'), indent=1)
    # دروازه‌ی صداقتی
    live = [r for r in rows if 'z' in r]
    best = max(live, key=lambda r: r['z']) if live else None
    gate = dict(max_z=best['z'] if best else None,
                need_z=round(rqs2.expected_max_z(16), 3),
                lift=best['lift_pp'] if best else None, need_lift=8.0,
                exp=best['exp_pip'] if best else None)
    gate['passed'] = bool(best and best['z'] >= gate['need_z']
                          and best['lift_pp'] >= 8.0 and best['exp_pip'] > 0)
    out = dict(best=best, honesty_gate=gate)
    json.dump(out, open(os.path.join(OUTDIR, 'winner.json'), 'w'), indent=1)
    print('HONESTY GATE:', gate, flush=True)


def load_winner():
    return json.load(open(os.path.join(OUTDIR, 'winner.json')))


def phase_null(df, ev, day, adr_map, vref_map, qv_map, rng):
    w = load_winner()
    if not w['honesty_gate']['passed']:
        print('gate NOT passed — null skipped'); return
    b = w['best']
    n = len(df)
    second = df['time'].values >= SPLIT_EPOCH
    ls, ss, slp, _ = arm_signals(ev, n, day, adr_map, vref_map, qv_map,
                                 b['window'], b['dir'], b['filt'])
    sig = (ls | ss) & second
    mh = WINDOWS[b['window']]['mh']
    # uncond: همه‌ی رخدادها یک‌جهته
    out = {}
    for side in ('long', 'short'):
        l0 = sig if side == 'long' else np.zeros(n, bool)
        s0 = sig if side == 'short' else np.zeros(n, bool)
        tru = run_arm(df, l0, s0, slp, mh)
        uncond = float((tru['outcome'].values == 'win').mean() * 100)
        out[side] = dict(uncond_wr=round(uncond, 4))
    perms_l, perms_s = [], []
    for k in range(K_PERM):
        flip = rng.random(n) < 0.5
        pls = sig & flip
        pss = sig & ~flip
        ptr = run_arm(df, pls, pss, slp, mh)
        if ptr is None or len(ptr) == 0:
            continue
        oc = ptr['outcome'].values == 'win'
        isl = ptr['direction'].values == 'long'
        if isl.sum():
            perms_l.append(float(oc[isl].mean() * 100))
        if (~isl).sum():
            perms_s.append(float(oc[~isl].mean() * 100))
        if (k + 1) % 100 == 0:
            print(f'perm {k+1}/{K_PERM}', flush=True)
    for side, arr in (('long', perms_l), ('short', perms_s)):
        a = np.array(arr)
        out[side].update(perm_mean=round(float(a.mean()), 4),
                         perm_sd=round(float(a.std(ddof=1)), 4),
                         perm_max=round(float(a.max()), 4),
                         perm_k=int(len(a)))
    json.dump(out, open(os.path.join(OUTDIR, 'null_holdout.json'), 'w'),
              indent=1)
    print('null saved:', out, flush=True)


def phase_judge(df, ev, day, adr_map, vref_map, qv_map):
    lock = os.path.join(OUTDIR, 'HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('HOLDOUT ALREADY SPENT — abort'); return
    w = load_winner()
    if not w['honesty_gate']['passed']:
        print('gate NOT passed — judge forbidden'); return
    b = w['best']
    null = json.load(open(os.path.join(OUTDIR, 'null_holdout.json')))
    n = len(df)
    second = df['time'].values >= SPLIT_EPOCH
    ls, ss, slp, _ = arm_signals(ev, n, day, adr_map, vref_map, qv_map,
                                 b['window'], b['dir'], b['filt'])
    ls &= second
    ss &= second
    mh = WINDOWS[b['window']]['mh']
    tr = run_arm(df, ls, ss, slp, mh)
    print(f'[judge] holdout trades: {len(tr)}', flush=True)
    med_sl = float(np.nanmedian(slp[np.isfinite(slp)]))
    split_bar = int(np.searchsorted(df['time'].values, SPLIT_EPOCH))
    r = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=med_sl, tp_pip=med_sl,
                          bar_time=df['time'].values, null=null,
                          n_trials=1, split_bar=split_bar,
                          close=df['close'].values)
    json.dump(dict(winner=b, verdict=r['verdict'], score=r['rqs2_score'],
                   full=r),
              open(os.path.join(OUTDIR, 'judgment_m1.json'), 'w'),
              indent=1, default=str)
    open(lock, 'w').write('holdout spent — one test only (path C)')
    print('VERDICT:', r['verdict'], 'SCORE:', r['rqs2_score'], flush=True)
    try:
        print(rqs2.format_rqs2('S812-M1', r))
    except Exception as e:
        print('format_rqs2 skipped:', e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--search', action='store_true')
    ap.add_argument('--null', action='store_true')
    ap.add_argument('--judge', action='store_true')
    a = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    d = fd.load_fast('XAUUSD', 'M1')
    print('src:', d['src'], flush=True)
    assert 'mt5_full' in d['src'], 'E-16 trap: non-canonical data!'
    df = fd.as_dataframe(d)
    t = df['time'].values.astype(np.int64)
    agg = build_daily(t, df['high'].values, df['low'].values)
    adr_map, vref_map, qv_map = causal_maps(agg)
    ev = find_events(t)
    day = t // 86400
    print({k: len(v) for k, v in ev.items()}, flush=True)
    rng = np.random.default_rng(SEED)
    if a.search:
        phase_search(df, ev, day, adr_map, vref_map, qv_map, rng)
    if a.null:
        phase_null(df, ev, day, adr_map, vref_map, qv_map, rng)
    if a.judge:
        phase_judge(df, ev, day, adr_map, vref_map, qv_map)


if __name__ == '__main__':
    main()
