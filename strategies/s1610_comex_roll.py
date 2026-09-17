# -*- coding: utf-8 -*-
"""
S1610 — COMEX GC roll-window drift (First Notice Day anchor) — XAUUSD — research only, site untouched
====================================================================================================
پیش‌ثبت: results/S1610_PREREG_COMEX_ROLL_WINDOW_DRIFT.md (کامیت 68f134ad)

تقویم: ماه پیش‌تحویل ∈ {1,3,5,7,9,11}؛ tdl = روزهای معاملاتی باقی تا آخر ماه (0=آخرین=FND-eve؛ FND خودش اولین روز ماه تحویل).
  بازوی A (SHORT): سیگنال = آخرین بار روز tdl=5 → ورود open بار بعد (روز tdl=4)… اسکن تا آخرین بار روز tdl=0.
    [پیش‌ثبت: پنجرهٔ A = tdl∈{5..1}؛ پیاده‌سازی: سیگنال آخرین بار روز tdl=6 ⇒ ورود اول روز tdl=5، اسکن تا پایان روز tdl=1.]
  بازوی B (LONG): سیگنال = آخرین بار روز tdl=1 (پیش‌ثبت «FND-eve»؛ ورود اول روز tdl=0)… اسکن ۵ روز معاملاتی.
    [توضیح: پیش‌ثبت §۳ پنجرهٔ B را «ورود اولین بار روز TD0 ماه پیش‌تحویل» نوشت = روز tdl=0. عیناً.]
هندسه: SL=TP=k×ATR34(Wilder، تا بار سیگنال)، k∈{1.272,2.058}، تقدم SL، وگرنه close پایان پنجره. pnl_pip=move/PIP−3.3.
کارت‌ها: {H4,D1}×{k}×{A,B} = ۸. اکتشاف فقط نیمهٔ اول پنجره‌ها (۴۷). واجد: n>=40 ∧ net>0 ∧ lift>=2.05×perm_sd.
نول: سکهٔ منصف روی همان رویدادها/هندسه، K=500 (explore) / 1000 (verdict)، SEED=20260908. n_trials=50.
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)
from engine.rqs2 import compute_rqs2

SEED = 20260908
N_TRIALS = 50
Z_LUCK = 2.05
PIP = 0.10
SPREAD = 3.3
PRE_MONTHS = {1, 3, 5, 7, 9, 11}
GRID_TF = ['H4', 'D1']
GRID_K = [1.272, 2.058]
ARMS = ['A_short', 'B_long']
PRIMARY = ('B_long', 'H4', 1.272)
OUT_DIR = os.path.join(ROOT, 'results', '_s1610_roll')
os.makedirs(OUT_DIR, exist_ok=True)


def load(tf):
    from tools import s434_fast_data as fd
    d = fd.load_fast('XAUUSD', tf)
    assert 'mt5_full' in d['src'], d['src']
    assert d['span_years'] > 15, d['span_years']
    return d


def wilder_atr34(h, l, c):
    n = len(c); tr = np.empty(n); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = np.full(n, np.nan); p = 34
    atr[p] = tr[1:p + 1].mean(); a = atr[p]
    for i in range(p + 1, n):
        a = (a * (p - 1) + tr[i]) / p; atr[i] = a
    return atr


def trading_days(d):
    """برچسب روز معاملاتی = تاریخ سرور؛ برمی‌گرداند day_id هر بار و جدول روزها (date, first_bar, last_bar, ym, tdl)."""
    t = pd.to_datetime(d['time'], unit='s')
    dates = t.normalize().values
    uniq, first = np.unique(dates, return_index=True)
    order = np.argsort(first); uniq, first = uniq[order], first[order]
    last = np.r_[first[1:] - 1, len(dates) - 1]
    days = pd.DataFrame(dict(date=pd.to_datetime(uniq), first_bar=first, last_bar=last))
    days['ym'] = days.date.dt.year * 100 + days.date.dt.month
    days['month'] = days.date.dt.month
    days['tdl'] = days.groupby('ym').cumcount(ascending=False)
    return days


def roll_events(days):
    """برای هر ماه پیش‌تحویل: (sigA, endA, sigB, endB) بر حسب اندیس بار."""
    ev = []
    for ym, g in days.groupby('ym', sort=True):
        if g.month.iloc[0] not in PRE_MONTHS or len(g) < 8:
            continue
        g = g.sort_values('tdl', ascending=False)
        by = {int(r.tdl): r for r in g.itertuples()}
        if not all(k in by for k in (6, 5, 1, 0)):
            continue
        sigA, endA = int(by[6].last_bar), int(by[1].last_bar)
        sigB = int(by[1].last_bar)
        # پایان B: ۵ روز معاملاتی پس از روز tdl=0
        pos0 = days.index.get_loc(by[0].Index)
        if pos0 + 5 >= len(days):
            continue
        endB = int(days.iloc[pos0 + 5].last_bar)
        ev.append(dict(ym=int(ym), sigA=sigA, endA=endA, sigB=sigB, endB=endB))
    return ev


def outcome(d, atr, sig, end, side, k):
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    e = sig + 1
    if e >= len(c) or end <= sig or np.isnan(atr[sig]) or atr[sig] <= 0:
        return None
    entry = o[e]; dist = k * atr[sig]
    sl, tp = (entry - dist, entry + dist) if side > 0 else (entry + dist, entry - dist)
    for b in range(e, end + 1):
        if side > 0:
            if l[b] <= sl: return (0, (sl - entry) / PIP - SPREAD, b)
            if h[b] >= tp: return (1, (tp - entry) / PIP - SPREAD, b)
        else:
            if h[b] >= sl: return (0, (entry - sl) / PIP - SPREAD, b)
            if l[b] <= tp: return (1, (entry - tp) / PIP - SPREAD, b)
    px = c[end]; pnl = ((px - entry) if side > 0 else (entry - px)) / PIP - SPREAD
    return (1 if pnl > 0 else 0, pnl, end)


def eval_card(d, atr, events, arm, k):
    rows = []
    for ev in events:
        sig, end = (ev['sigA'], ev['endA']) if arm == 'A_short' else (ev['sigB'], ev['endB'])
        side = -1 if arm == 'A_short' else 1
        oL = outcome(d, atr, sig, end, +1, k); oS = outcome(d, atr, sig, end, -1, k)
        if oL is None or oS is None: continue
        me = oL if side > 0 else oS
        rows.append(dict(ym=ev['ym'], sig=sig, entry=sig + 1, exit=me[2], win=me[0], pnl=me[1],
                         wL=oL[0], wS=oS[0], side=side, t=int(d['time'][sig])))
    return rows


def coin_null(rows, K, seed):
    wl = np.array([r['wL'] for r in rows], float); ws = np.array([r['wS'] for r in rows], float)
    rng = np.random.default_rng(seed); m = len(rows); wrs = np.empty(K)
    for i in range(K):
        pick = rng.integers(0, 2, m); wrs[i] = 100 * np.where(pick == 1, wl, ws).mean()
    return dict(uncond_wr=float(100 * np.r_[wl, ws].mean()), perm_mean=float(wrs.mean()),
                perm_sd=float(wrs.std(ddof=1)), perm_max=float(wrs.max()), perm_k=K)


def stats(rows, nl):
    w = np.array([r['win'] for r in rows]); p = np.array([r['pnl'] for r in rows])
    wr = 100 * w.mean(); ref = max(nl['uncond_wr'], nl['perm_mean']); lift = wr - ref
    return dict(n=len(rows), wr=round(wr, 2), net_pip=round(float(p.sum()), 1),
                pf=round(float(p[p > 0].sum() / max(1e-9, -p[p < 0].sum())), 3),
                **{k: round(v, 3) if isinstance(v, float) else v for k, v in nl.items()},
                ref=round(ref, 2), lift=round(lift, 2), z=round(lift / nl['perm_sd'], 2) if nl['perm_sd'] > 0 else None)


def phase_explore():
    t0 = time.time(); grid = []
    for tf in GRID_TF:
        d = load(tf); atr = wilder_atr34(d['high'], d['low'], d['close'])
        days = trading_days(d); ev = roll_events(days)
        half = len(ev) // 2; ev1 = ev[:half]
        print(f"[{tf}] bars={d['n_bars']} span={d['span_years']:.2f}y src={os.path.basename(d['src'])} | "
              f"roll windows={len(ev)} (pre-count 94) first-half={len(ev1)} last-first-half ym={ev1[-1]['ym']}", flush=True)
        if tf == 'D1':
            json.dump(dict(n_windows=len(ev), first_half=len(ev1), windows=ev), open(os.path.join(OUT_DIR, 'calendar_check.json'), 'w'), indent=1)
        for arm in ARMS:
            for k in GRID_K:
                rows = eval_card(d, atr, ev1, arm, k)
                if not rows: grid.append(dict(tf=tf, arm=arm, k=k, n=0)); continue
                nl = coin_null(rows, 500, SEED + hash((tf, arm, k)) % 9973)
                st = stats(rows, nl); st.update(tf=tf, arm=arm, k=k, primary=((arm, tf, k) == PRIMARY),
                                                eligible=bool(st['n'] >= 40 and st['net_pip'] > 0 and st['lift'] >= Z_LUCK * nl['perm_sd']))
                grid.append(st)
                print(f"  {arm:8s} {tf} k={k}: n={st['n']} WR={st['wr']} net={st['net_pip']:+.0f} PF={st['pf']} | "
                      f"coin ref={st['ref']} sd={st['perm_sd']} | lift={st['lift']:+.2f} z={st['z']} elig={st['eligible']}"
                      f"{'  <== PRIMARY' if st['primary'] else ''}", flush=True)
    json.dump(grid, open(os.path.join(OUT_DIR, 'grid_first_half.json'), 'w'), indent=1)
    elig = [g for g in grid if g.get('eligible')]
    if not elig:
        dec = dict(decision='death', reason='no_eligible_point', rule=f'n>=40 AND net>0 AND lift>={Z_LUCK}*perm_sd',
                   verdict='REJECT', score=0, holdout='VIRGIN', elapsed_s=round(time.time() - t0, 1))
        print("⛔ مرگ شرافتمندانه: هیچ نقطه‌ای واجد نشد — هولد‌اوت بکر.", flush=True)
    else:
        best = max(elig, key=lambda g: g['z'])
        dec = dict(decision='proceed', winner=dict(tf=best['tf'], arm=best['arm'], k=best['k']), best=best, elapsed_s=round(time.time() - t0, 1))
        print(f"✅ برنده: {best['arm']} {best['tf']} k={best['k']} z={best['z']} → verdict", flush=True)
    json.dump(dec, open(os.path.join(OUT_DIR, 'decision.json'), 'w'), indent=1)


def phase_verdict():
    dec = json.load(open(os.path.join(OUT_DIR, 'decision.json')))
    assert dec['decision'] == 'proceed'
    tf, arm, k = dec['winner']['tf'], dec['winner']['arm'], dec['winner']['k']
    d = load(tf); atr = wilder_atr34(d['high'], d['low'], d['close'])
    ev = roll_events(trading_days(d)); rows = eval_card(d, atr, ev, arm, k)
    nl = coin_null(rows, 1000, SEED); st = stats(rows, nl)
    sig = np.array([r['sig'] for r in rows]); sl_pip = float(np.nanmedian(k * atr[sig]) / PIP)
    trd = pd.DataFrame(dict(signal_bar=sig, entry_bar=[r['entry'] for r in rows], exit_bar=[r['exit'] for r in rows],
                            pnl_pip=[r['pnl'] for r in rows], outcome=['win' if r['win'] else 'loss' for r in rows],
                            sl_pip=sl_pip, direction='long' if arm == 'B_long' else 'short'))
    nlc = {kk: nl[kk] for kk in ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')}
    dt = pd.to_datetime(d['time'], unit='s'); split_bar = int(ev[len(ev) // 2]['sigB'])
    res = compute_rqs2(trd, 'XAUUSD', sl_pip=sl_pip, tp_pip=sl_pip, bar_time=dt.values, null={'long': nlc, 'short': nlc},
                       n_trials=N_TRIALS, split_bar=split_bar, close=d['close'])
    print(f"FULL {arm} {tf} k={k}: n={st['n']} WR={st['wr']} net={st['net_pip']:+.0f} lift={st['lift']:+.2f} z={st['z']} | "
          f"verdict={res['verdict']} score={res['rqs2_score']} gates={res['gates']}", flush=True)
    json.dump(dict(tf=tf, arm=arm, k=k, stats=st, sl_pip=sl_pip, split_bar=split_bar, n_trials=N_TRIALS, rqs2=res),
              open(os.path.join(OUT_DIR, 'verdict.json'), 'w'), indent=1, default=str)
    trd.assign(bar_dt=dt.values[sig]).to_csv(os.path.join(OUT_DIR, 'trades.csv'), index=False)


if __name__ == '__main__':
    (phase_explore if (sys.argv[1] if len(sys.argv) > 1 else 'explore') == 'explore' else phase_verdict)()
