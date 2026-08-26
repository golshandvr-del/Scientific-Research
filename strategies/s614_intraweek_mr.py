# -*- coding: utf-8 -*-
"""
S614 — Intra-Week Mean Reversion (Mon–Wed → Thursday counter) — XAUUSD
=======================================================================
پیش‌ثبت: results/S614_PREREG_INTRAWEEK_MEANREVERSION_THU.md (کامیت 82beda81)

رویداد منجمد:
  early_move = close(آخرین کندل چهارشنبه) − open(اولین کندل دوشنبه) همان هفته.
  گیت: |early_move| >= میانهٔ علّی |early_move| در ۵۲ هفتهٔ قبل (min 26).
  ورود: open کندلِ بعد از اولین کندل پنجشنبه؛ جهت = −sign(early_move).
  خروج V-TIME: SL=TP=k×ATR34(Wilder علّی در کندل سیگنال)؛ اگر نخورد ⇒
  close آخرین کندل پنجشنبهٔ همان هفته. تقدم SL. spread=3.3.

فاز explore: گرید قفل ۴ نقطه {M30,H1}×{1.272,2.058} فقط نیمهٔ اول.
  برنده: بیشترین z بین n>=100 ∧ net>0. پیش‌شرط توان: lift >= 3.72×sd.
فاز verdict: تک‌لمس کل داده روی برنده + compute_rqs2 (n_trials=300).
null: جای‌گشت جهت (سکهٔ منصف) K=1000 روی همان رویدادها/هندسه، seed=20260825.
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from engine.rqs2 import compute_rqs2

SEED = 20260825
K_PERM = 1000
N_TRIALS = 300
Z_LUCK = 3.72
PIP = 0.10
SPREAD = 3.3
GRID_TF = ['M30', 'H1']
GRID_K = [1.272, 2.058]
OUT_DIR = os.path.join(ROOT, 'results', '_s614_iwmr')
os.makedirs(OUT_DIR, exist_ok=True)


def wilder_atr34(h, l, c):
    n = len(c)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                np.abs(h[1:] - c[:-1]),
                                np.abs(l[1:] - c[:-1])])
    atr = np.full(n, np.nan)
    p = 34
    if n <= p:
        return atr
    atr[p] = tr[1:p + 1].mean()
    a = atr[p]
    for i in range(p + 1, n):
        a = (a * (p - 1) + tr[i]) / p
        atr[i] = a
    return atr


def load_tf(tf):
    from tools import s434_fast_data as fd
    return fd.load_fast('XAUUSD', tf)


def build_week_events(d):
    """برای هر هفتهٔ دوشنبه‌مبنا: early_move، اندیس سیگنال (اولین کندل پنجشنبه)،
    آخرین کندل پنجشنبه (پایان پنجره). فقط هفته‌هایی که Mon,Wed,Thu همه موجودند."""
    t = d['time']; dow = d['dow']
    day = t // 86400
    week = (day + 3) // 7          # دوشنبه‌مبنا
    o, c = d['open'], d['close']
    n = len(t)
    ev = []                        # (week, early_move, sig_bar, end_bar)
    # اندیس‌های مرزی هر هفته
    uniq, starts = np.unique(week, return_index=True)
    for wi, w in enumerate(uniq):
        i0 = starts[wi]
        i1 = starts[wi + 1] if wi + 1 < len(uniq) else n
        dws = dow[i0:i1]
        idx = np.arange(i0, i1)
        mon = idx[dws == 0]
        wed = idx[dws == 2]
        thu = idx[dws == 3]
        if len(mon) == 0 or len(wed) == 0 or len(thu) == 0:
            continue
        em = c[wed[-1]] - o[mon[0]]
        sig = thu[0]
        end = thu[-1]
        if sig + 1 >= n or end <= sig:
            continue
        ev.append((w, em, sig, end))
    return ev


def gate_events(ev):
    """گیت میانهٔ علّی ۵۲ هفته‌ای روی |early_move| (min 26)."""
    out = []
    hist = []
    for w, em, sig, end in ev:
        a = abs(em)
        if len(hist) >= 26:
            med = float(np.median(hist[-52:]))
            if a >= med and em != 0:
                out.append((w, em, sig, end))
        hist.append(a)
    return out


def simulate(d, events, k_atr, atr, dirs=None):
    """V-TIME: ورود open[sig+1]، جهت از dirs (پیش‌فرض −sign(em))؛
    SL=TP=k×ATR34[sig]؛ اسکن sig+1..end با تقدم SL؛ وگرنه close[end]."""
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    n = len(o)
    m = len(events)
    pnl = np.full(m, np.nan)
    win = np.zeros(m, dtype=bool)
    ebs = np.full(m, -1, dtype=np.int64)
    sds = np.empty(m, dtype=object)
    for q, (w, em, sig, end) in enumerate(events):
        if sig + 1 >= n or not np.isfinite(atr[sig]) or atr[sig] <= 0:
            continue
        side = dirs[q] if dirs is not None else (-1 if em > 0 else 1)
        fill = o[sig + 1]
        dlt = k_atr * atr[sig]
        if side == 1:
            slp, tpp = fill - dlt, fill + dlt
        else:
            slp, tpp = fill + dlt, fill - dlt
        ep = np.nan; eb = end
        for j in range(sig + 1, end + 1):
            if side == 1:
                if l[j] <= slp:
                    ep = slp; eb = j; break
                if h[j] >= tpp:
                    ep = tpp; eb = j; break
            else:
                if h[j] >= slp:
                    ep = slp; eb = j; break
                if l[j] <= tpp:
                    ep = tpp; eb = j; break
        if not np.isfinite(ep):
            ep = c[end]; eb = end
        raw = (ep - fill) / PIP
        pnl[q] = (raw if side == 1 else -raw) - SPREAD
        win[q] = pnl[q] > 0
        ebs[q] = eb
        sds[q] = 'long' if side == 1 else 'short'
    ok = np.isfinite(pnl)
    return pnl, win, ebs, sds, ok


def coin_null(d, events, k_atr, atr, rng):
    """null جهت-جای‌گشتی: K بار جهت هر معامله = سکهٔ منصف؛ همان رویدادها/هندسه."""
    m = len(events)
    perm_wrs = np.empty(K_PERM)
    # برای سرعت: پیامد هر رویداد در هر دو جهت را یک‌بار حساب کن
    pnl_L, win_L, _, _, okL = simulate(d, events, k_atr, atr,
                                       dirs=np.ones(m, dtype=int))
    pnl_S, win_S, _, _, okS = simulate(d, events, k_atr, atr,
                                       dirs=-np.ones(m, dtype=int))
    ok = okL & okS
    wL, wS = win_L[ok], win_S[ok]
    mm = int(ok.sum())
    for kk in range(K_PERM):
        pick = rng.integers(0, 2, size=mm).astype(bool)
        wr = np.where(pick, wL, wS).mean() * 100
        perm_wrs[kk] = wr
    uncond_coin = float((wL.mean() + wS.mean()) / 2 * 100)
    return perm_wrs, uncond_coin


def phase_explore():
    print("=== S614 فاز ۱: گرید قفل ۴ نقطه — فقط نیمهٔ اول ===", flush=True)
    rng = np.random.default_rng(SEED)
    rows = []
    for tf in GRID_TF:
        d = load_tf(tf)
        n = d['n_bars']
        half = n // 2
        atr = wilder_atr34(d['high'], d['low'], d['close'])
        ev_all = build_week_events(d)
        ev_all = [e for e in ev_all if e[2] < half]
        ev = gate_events(ev_all)
        print(f"[{tf}] bars={n} weeks(h1)={len(ev_all)} gated={len(ev)} src={os.path.basename(d['src'])}", flush=True)
        for k_atr in GRID_K:
            pnl, win, _, _, ok = simulate(d, ev, k_atr, atr)
            nn = int(ok.sum())
            wr = float(win[ok].mean() * 100) if nn else np.nan
            net = float(pnl[ok].sum()) if nn else np.nan
            perm, uncond = coin_null(d, ev, k_atr, atr, rng)
            pm, ps = float(np.nanmean(perm)), float(np.nanstd(perm, ddof=1))
            ref = max(uncond, pm)
            lift = wr - ref
            z = lift / ps if ps > 0 else np.nan
            rows.append(dict(tf=tf, k=k_atr, n=nn, wr=round(wr, 2), net_pip=round(net, 1),
                             uncond=round(uncond, 2), perm_mean=round(pm, 2),
                             perm_sd=round(ps, 3), lift=round(lift, 2), z=round(z, 2)))
            print(f"  k={k_atr}: n={nn} WR={wr:.2f} net={net:+.0f} | coin u={uncond:.2f} "
                  f"pm={pm:.2f} sd={ps:.3f} | lift={lift:+.2f}pp z={z:.2f}", flush=True)
    json.dump(rows, open(os.path.join(OUT_DIR, 'grid_first_half.json'), 'w'), indent=1)
    elig = [r for r in rows if r['n'] >= 100 and r['net_pip'] > 0]
    if not elig:
        print("\n⛔ مرگ شرافتمندانه: هیچ نقطه‌ای n>=100 ∧ net>0 — هولد‌اوت بکر.", flush=True)
        json.dump(dict(death='no_eligible_point'), open(os.path.join(OUT_DIR, 'decision.json'), 'w'))
        return
    winner = max(elig, key=lambda r: r['z'])
    need = Z_LUCK * winner['perm_sd']
    ok_power = winner['lift'] >= need
    print(f"\nبرنده: {winner['tf']} k={winner['k']} z={winner['z']} lift={winner['lift']}pp | "
          f"توان لازم {need:.2f}pp => {'PASS' if ok_power else 'FAIL'}", flush=True)
    json.dump(dict(winner=winner, need_lift=round(need, 2), power_pass=bool(ok_power)),
              open(os.path.join(OUT_DIR, 'decision.json'), 'w'), indent=1)
    if not ok_power:
        print("⛔ پیش‌شرط توان شکست — مرگ شرافتمندانه، هولد‌اوت بکر.", flush=True)


def phase_verdict():
    dec = json.load(open(os.path.join(OUT_DIR, 'decision.json')))
    if 'winner' not in dec or not dec.get('power_pass'):
        print("⛔ طبق decision.json مجاز به هولد‌اوت نیستیم."); sys.exit(2)
    w = dec['winner']
    tf, k_atr = w['tf'], w['k']
    print(f"=== S614 فاز ۲: تک‌لمس کل داده — {tf} k={k_atr} ===", flush=True)
    rng = np.random.default_rng(SEED + 1)
    d = load_tf(tf)
    n = d['n_bars']
    atr = wilder_atr34(d['high'], d['low'], d['close'])
    ev = gate_events(build_week_events(d))
    pnl, win, ebs, sds, ok = simulate(d, ev, k_atr, atr)
    ev = [e for e, s in zip(ev, ok) if s]
    pnl, win, ebs = pnl[ok], win[ok], ebs[ok]
    sds = np.array([s for s, s2 in zip(sds, ok) if s2], dtype=object)
    wr = float(win.mean() * 100)
    net = float(pnl.sum())
    print(f"FULL: n={len(ev)} WR={wr:.2f} net={net:+.1f}", flush=True)
    perm, uncond = coin_null(d, ev, k_atr, atr, rng)
    pm, ps = float(np.nanmean(perm)), float(np.nanstd(perm, ddof=1))
    print(f"null: coin u={uncond:.2f} pm={pm:.2f} sd={ps:.3f} max={np.nanmax(perm):.2f}", flush=True)

    dt = pd.to_datetime(d['time'], unit='s')
    sig = np.array([e[2] for e in ev], dtype=np.int64)
    sl_pip_med = float(np.nanmedian(k_atr * atr[sig]) / PIP)
    trd = pd.DataFrame(dict(signal_bar=sig, entry_bar=sig + 1, exit_bar=ebs,
                            pnl_pip=pnl, outcome=np.where(win, 'win', 'loss'),
                            side=sds))
    nl = dict(uncond_wr=uncond, perm_mean=pm, perm_sd=ps,
              perm_max=float(np.nanmax(perm)), perm_k=K_PERM)
    null = {'long': nl, 'short': nl}
    split_bar = int(n * 0.70)
    res = compute_rqs2(trd, 'XAUUSD', sl_pip=sl_pip_med, tp_pip=sl_pip_med,
                       bar_time=dt.values, null=null, n_trials=N_TRIALS,
                       split_bar=split_bar, close=d['close'])
    trd2 = trd.assign(bar_dt=dt.values[sig])
    cut = pd.Timestamp('2023-09-01')
    pre, post = trd2[trd2['bar_dt'] < cut], trd2[trd2['bar_dt'] >= cut]
    regime = dict(pre=dict(n=int(len(pre)), wr=round(float((pre['outcome'] == 'win').mean() * 100), 2),
                           net=round(float(pre['pnl_pip'].sum()), 1)),
                  post=dict(n=int(len(post)), wr=round(float((post['outcome'] == 'win').mean() * 100), 2),
                            net=round(float(post['pnl_pip'].sum()), 1)))
    print("REGIME:", regime, flush=True)
    out = dict(seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS, tf=tf, k_atr=k_atr,
               sl_pip_med=round(sl_pip_med, 1), n=int(len(ev)), wr=round(wr, 2),
               net_pip=round(net, 1), uncond=round(uncond, 2), perm_mean=round(pm, 3),
               perm_sd=round(ps, 4), split_bar=split_bar,
               verdict=res['verdict'], rqs2_score=res['rqs2_score'],
               gates={k2: (None if v is None else bool(v)) for k2, v in res['gates'].items()},
               notes=res['notes'], regime=regime)
    json.dump(out, open(os.path.join(OUT_DIR, 'verdict.json'), 'w'), indent=1,
              ensure_ascii=False, default=str)
    trd2.to_csv(os.path.join(OUT_DIR, 'trades.csv'), index=False)
    print("\n=== حکم موتور ===")
    print("verdict:", res['verdict'], "| score:", res['rqs2_score'])
    print("gates:", res['gates'])
    print("notes:", res['notes'])


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'explore'
    t0 = time.time()
    if mode == 'explore':
        phase_explore()
    else:
        phase_verdict()
    print(f"\ntotal {time.time()-t0:.0f}s")
