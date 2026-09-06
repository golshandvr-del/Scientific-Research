# -*- coding: utf-8 -*-
"""
S619 — Intra-Week CONTINUATION (Mon–Wed → Thursday same direction) — mirror of S614 — XAUUSD
===========================================================================================
پیش‌ثبت: results/S619_PREREG_INTRAWEEK_CONTINUATION_THU.md (کامیت 010899dc)

صفر بازنویسی: رویداد/گیت/شبیه‌ساز/نول عیناً از strategies/s614_intraweek_mr.py import می‌شوند.
تنها تفاوت: جهت = +sign(early_move)  (S614: −sign).

confirm: فقط نیمهٔ دوم (بکر — S614 هرگز آن را شبیه‌سازی نکرد). کارت اصلی M30 k=1.272.
         معیار: n>=60 ∧ net>0 ∧ lift >= 2.0×perm_sd. شکست ⇒ REJECT 0.
verdict: کل داده روی کارت اصلی + compute_rqs2 (n_trials=304، split_bar=n//2).
seed=20260906.
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)
from engine.rqs2 import compute_rqs2
from strategies import s614_intraweek_mr as S614   # noqa: E402

SEED = 20260906
K_PERM = 1000
N_TRIALS = 304
Z_CONFIRM = 2.0
MIN_N2 = 60
PIP = S614.PIP
GRID_TF = ['M30', 'H1']
GRID_K = [1.272, 2.058]
PRIMARY = ('M30', 1.272)
OUT_DIR = os.path.join(ROOT, 'results', '_s619_iwc')
os.makedirs(OUT_DIR, exist_ok=True)


def cont_dirs(ev):
    """جهت ادامه‌روی: +sign(early_move)."""
    return np.array([1 if e[1] > 0 else -1 for e in ev], dtype=int)


def run_card(d, atr, ev, k_atr, rng):
    dirs = cont_dirs(ev)
    pnl, win, ebs, sds, ok = S614.simulate(d, ev, k_atr, atr, dirs=dirs)
    perm, uncond = S614.coin_null(d, ev, k_atr, atr, rng)   # همان رویدادها، همان هندسه
    nn = int(ok.sum())
    wr = float(win[ok].mean() * 100) if nn else np.nan
    net = float(pnl[ok].sum()) if nn else np.nan
    pm, ps = float(np.nanmean(perm)), float(np.nanstd(perm, ddof=1))
    ref = max(uncond, pm)
    lift = wr - ref
    z = lift / ps if ps > 0 else np.nan
    isL = dirs[ok] == 1
    wrL = float(win[ok][isL].mean() * 100) if isL.any() else np.nan
    wrS = float(win[ok][~isL].mean() * 100) if (~isL).any() else np.nan
    return dict(n=nn, n_long=int(isL.sum()), n_short=int((~isL).sum()),
                wr=round(wr, 2), wr_long_arm=round(wrL, 2), wr_short_arm=round(wrS, 2),
                net_pip=round(net, 1), uncond=round(uncond, 2), perm_mean=round(pm, 2),
                perm_sd=round(ps, 3), perm_max=round(float(np.nanmax(perm)), 2),
                ref=round(ref, 2), lift=round(lift, 2), z=round(z, 2)), (pnl, win, ebs, sds, ok, dirs)


def phase_confirm():
    print("=== S619 مرحلهٔ تأیید: فقط نیمهٔ دوم (بکر) — ۴ کارت، ادعا فقط از M30 k=1.272 ===", flush=True)
    rng = np.random.default_rng(SEED)
    rows = []
    for tf in GRID_TF:
        d = S614.load_tf(tf)
        n = d['n_bars']; half = n // 2
        atr = S614.wilder_atr34(d['high'], d['low'], d['close'])
        ev_all = S614.build_week_events(d)
        ev_gated = S614.gate_events(ev_all)             # گیت علّی روی کل تاریخ (میانهٔ ۵۲ هفتهٔ قبل)
        ev2 = [e for e in ev_gated if e[2] >= half]     # فقط رویدادهای نیمهٔ دوم
        print(f"[{tf}] bars={n} half_bar={half} ({pd.to_datetime(d['time'][half], unit='s')}) "
              f"gated_total={len(ev_gated)} half2={len(ev2)} src={os.path.basename(d['src'])}", flush=True)
        for k_atr in GRID_K:
            st, _ = run_card(d, atr, ev2, k_atr, rng)
            st.update(tf=tf, k=k_atr, primary=bool((tf, k_atr) == PRIMARY))
            rows.append(st)
            print(f"  k={k_atr}: n={st['n']} (L{st['n_long']}/S{st['n_short']}) WR={st['wr']} "
                  f"[L{st['wr_long_arm']}/S{st['wr_short_arm']}] net={st['net_pip']:+.0f} | "
                  f"coin u={st['uncond']} pm={st['perm_mean']} sd={st['perm_sd']} | "
                  f"lift={st['lift']:+.2f}pp z={st['z']}{'  <== PRIMARY' if st['primary'] else ''}", flush=True)
    json.dump(rows, open(os.path.join(OUT_DIR, 'confirm_half2.json'), 'w'), indent=1)
    p = [r for r in rows if r['primary']][0]
    need = Z_CONFIRM * p['perm_sd']
    passed = bool(p['n'] >= MIN_N2 and p['net_pip'] > 0 and p['lift'] >= need)
    dec = dict(primary=p, rule=f"n>={MIN_N2} AND net>0 AND lift>={Z_CONFIRM}*perm_sd", need_lift=round(need, 2),
               confirm_pass=passed, verdict=None if passed else 'REJECT', score=None if passed else 0)
    json.dump(dec, open(os.path.join(OUT_DIR, 'decision.json'), 'w'), indent=1)
    if passed:
        print(f"\n✅ تأیید روی نیمهٔ بکر گذشت (lift={p['lift']} >= {need:.2f}) → مرحلهٔ حکم", flush=True)
    else:
        print(f"\n⛔ تأیید شکست (lift={p['lift']} vs need {need:.2f}, n={p['n']}, net={p['net_pip']}) — REJECT 0.", flush=True)


def phase_verdict():
    dec = json.load(open(os.path.join(OUT_DIR, 'decision.json')))
    if not dec.get('confirm_pass'):
        print("⛔ طبق decision.json مجاز به حکم نیستیم."); sys.exit(2)
    tf, k_atr = PRIMARY
    print(f"=== S619 مرحلهٔ حکم: کل داده — {tf} k={k_atr} — compute_rqs2 n_trials={N_TRIALS} ===", flush=True)
    rng = np.random.default_rng(SEED + 1)
    d = S614.load_tf(tf)
    n = d['n_bars']; half = n // 2
    atr = S614.wilder_atr34(d['high'], d['low'], d['close'])
    ev = S614.gate_events(S614.build_week_events(d))
    st, (pnl, win, ebs, sds, ok, dirs) = run_card(d, atr, ev, k_atr, rng)
    ev = [e for e, s in zip(ev, ok) if s]
    pnl, win, ebs, dirs = pnl[ok], win[ok], ebs[ok], dirs[ok]
    print(f"FULL: n={st['n']} WR={st['wr']} net={st['net_pip']:+.1f} | coin u={st['uncond']} pm={st['perm_mean']} "
          f"sd={st['perm_sd']} max={st['perm_max']} | lift={st['lift']:+.2f} z={st['z']}", flush=True)
    dt = pd.to_datetime(d['time'], unit='s')
    sig = np.array([e[2] for e in ev], dtype=np.int64)
    sl_pip_med = float(np.nanmedian(k_atr * atr[sig]) / PIP)
    trd = pd.DataFrame(dict(signal_bar=sig, entry_bar=sig + 1, exit_bar=ebs, pnl_pip=pnl,
                            outcome=np.where(win, 'win', 'loss'),
                            side=np.where(dirs == 1, 'long', 'short')))
    nl = dict(uncond_wr=st['uncond'], perm_mean=st['perm_mean'], perm_sd=st['perm_sd'],
              perm_max=st['perm_max'], perm_k=K_PERM)
    null = {'long': nl, 'short': nl}
    res = compute_rqs2(trd, 'XAUUSD', sl_pip=sl_pip_med, tp_pip=sl_pip_med,
                       bar_time=dt.values, null=null, n_trials=N_TRIALS,
                       split_bar=half, close=d['close'])
    # halves + regime
    h1m = sig < half
    halves = dict(first=dict(n=int(h1m.sum()), wr=round(float(win[h1m].mean() * 100), 2), net=round(float(pnl[h1m].sum()), 1)),
                  second=dict(n=int((~h1m).sum()), wr=round(float(win[~h1m].mean() * 100), 2), net=round(float(pnl[~h1m].sum()), 1)))
    trd2 = trd.assign(bar_dt=dt.values[sig])
    yearly = {int(y): dict(n=int(len(g)), wr=round(float((g['outcome'] == 'win').mean() * 100), 1), net=round(float(g['pnl_pip'].sum()), 0))
              for y, g in trd2.groupby(trd2['bar_dt'].dt.year)}
    out = dict(seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS, tf=tf, k_atr=k_atr, sl_pip_med=round(sl_pip_med, 1),
               stats=st, halves=halves, yearly=yearly, rqs2=res)
    json.dump(out, open(os.path.join(OUT_DIR, 'verdict.json'), 'w'), indent=1, default=str)
    trd2.to_csv(os.path.join(OUT_DIR, 'trades.csv'), index=False)
    print("HALVES:", halves, flush=True)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str), flush=True)


if __name__ == '__main__':
    phase = sys.argv[1] if len(sys.argv) > 1 else 'confirm'
    phase_confirm() if phase == 'confirm' else phase_verdict()
