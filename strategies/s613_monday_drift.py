# -*- coding: utf-8 -*-
"""
S613 — Monday DOW Drift (دودمان S140) — داوری full-data زیر RQS2
=================================================================
پیش‌ثبت: results/S613_PREREG_MONDAY_DOW_DRIFT_FULLDATA.md (کامیت 5caa6be4)

فاز ۱ (این اسکریپت با آرگومان explore): گریدِ قفلِ ۶ نقطه فقط روی نیمهٔ اول.
  رویداد منجمد: dow=0 ∧ hour==18 ⇒ LONG در open کندل بعد؛ حداکثر ۱ معامله/دوشنبه.
  هندسه: V-TIME متقارن SL=TP=k×ATR34(Wilder علّی) ؛ اگر نخورد ⇒ خروج close
  آخرین کندلِ پوششِ پنجره (پایان = ساعت ۲۲ همان روز).
  قانون برنده (قفل): بیشترین z در برابر null شرطی، بین نقاط n>=150 ∧ net>0.
  پیش‌شرط توان: lift >= z_luck(600)*sd_null وگرنه مرگ شرافتمندانه (هولد‌اوت بکر).

فاز ۲ (آرگومان verdict): تک‌لمس نیمهٔ دوم — فقط نقطهٔ برنده، یک compute_rqs2.
null (قانون S612): جای‌گشت K=1000 — هر دوشنبه با یک روزِ کاری غیر‌دوشنبهٔ همان
هفته (سه‌شنبه..جمعه) در همان اسلات ساعت-۱۸ و همان هندسه جایگزین می‌شود.
seed=20260823. n_trials=600. spread=3.3 pip.
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from engine.rqs2 import compute_rqs2

SEED = 20260823
K_PERM = 1000
N_TRIALS = 600
Z_LUCK = 3.91           # یک‌طرفه برای 600 آزمون
PIP = 0.10
SPREAD = 3.3
HOUR_EV = 18
HOUR_END = 22
GRID_TF = ['M15', 'M30', 'H1']
GRID_K = [1.272, 2.058]
OUT_DIR = os.path.join(ROOT, 'results', '_s613_monday')
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
    d = fd.load_fast('XAUUSD', tf)
    return d


def event_bars(d, i0, i1):
    """کندل‌های سیگنال: dow=0 ∧ hour==HOUR_EV ∧ اولین کندلِ آن ساعت در آن روز؛
    یک رویداد به‌ازای هر دوشنبه. بازه [i0, i1)."""
    dow = d['dow']; hour = d['hour']; t = d['time']
    day = t // 86400
    mask = (dow == 0) & (hour == HOUR_EV)
    idx = np.where(mask)[0]
    idx = idx[(idx >= i0) & (idx < i1)]
    # اولین کندل ساعت-18 هر روز
    keep = []
    seen = set()
    for i in idx:
        dy = day[i]
        if dy in seen:
            continue
        seen.add(dy)
        keep.append(i)
    return np.array(keep, dtype=np.int64)


def weekday_slots(d, i0, i1):
    """اسلات‌های شاهد: اولین کندل ساعت-18 هر روزِ کاری (dow 0..4)، بازه [i0,i1).
    خروجی: dict day->index و آرایهٔ (index, dow, week)."""
    dow = d['dow']; hour = d['hour']; t = d['time']
    day = t // 86400
    mask = (dow <= 4) & (hour == HOUR_EV)
    idx = np.where(mask)[0]
    idx = idx[(idx >= i0) & (idx < i1)]
    keep = []
    seen = set()
    for i in idx:
        dy = day[i]
        if dy in seen:
            continue
        seen.add(dy)
        keep.append(i)
    keep = np.array(keep, dtype=np.int64)
    # هفتهٔ ISO تقریبی: (day+3)//7 (دوشنبه‌محور: epoch 1970-01-01 پنجشنبه بود، dow پایتونی Mon=0)
    wk = (day[keep] + 3) // 7
    return keep, dow[keep], wk


def simulate_events(d, ev_idx, k_atr, atr):
    """V-TIME: ورود open[i+1]؛ SL=TP=k×ATR34[i]؛ اسکن i+1..end_bar با تقدم SL؛
    وگرنه خروج close[end_bar]. end_bar = آخرین کندل با day==day[i] ∧ hour<=HOUR_END.
    خروجی: pnl_pip آرایه، win آرایه، exit_bar."""
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    t = d['time']; day = t // 86400; hour = d['hour']
    n = len(o)
    pnl = np.full(len(ev_idx), np.nan)
    win = np.zeros(len(ev_idx), dtype=bool)
    ebs = np.full(len(ev_idx), -1, dtype=np.int64)
    for q, i in enumerate(ev_idx):
        if i + 1 >= n or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        fill = o[i + 1]
        dlt = k_atr * atr[i]
        slp, tpp = fill - dlt, fill + dlt
        dy = day[i]
        # end_bar: آخرین j با day==dy و hour<=HOUR_END (حداقل i+1)
        j = i + 1
        end_bar = i + 1
        while j < n and day[j] == dy and hour[j] <= HOUR_END:
            end_bar = j
            j += 1
        ep = np.nan; eb = end_bar
        for j in range(i + 1, end_bar + 1):
            if l[j] <= slp:          # تقدم SL
                ep = slp; eb = j; break
            if h[j] >= tpp:
                ep = tpp; eb = j; break
        if not np.isfinite(ep):
            ep = c[end_bar]; eb = end_bar
        pnl[q] = (ep - fill) / PIP - SPREAD
        win[q] = pnl[q] > 0
        ebs[q] = eb
    ok = np.isfinite(pnl)
    return pnl, win, ebs, ok


def null_for_card(d, atr, k_atr, i0, i1, mon_events, rng):
    """null شرطی: جای‌گشت K — هر دوشنبه با روزِ کاری غیر‌دوشنبهٔ همان هفته جایگزین.
    خروجی: perm_wrs، uncond_wr (همهٔ اسلات‌های غیر‌دوشنبه)."""
    slots, sdow, swk = weekday_slots(d, i0, i1)
    # pnl همهٔ اسلات‌ها را یک‌بار حساب کن
    pnl_all, win_all, _, ok_all = simulate_events(d, slots, k_atr, atr)
    non_mon = (sdow != 0) & ok_all
    uncond_wr = float(win_all[non_mon].mean() * 100) if non_mon.sum() else np.nan
    # نگاشت هفته -> اندیس‌های اسلات غیر‌دوشنبهٔ سالم
    from collections import defaultdict
    wk_map = defaultdict(list)
    for s in range(len(slots)):
        if non_mon[s]:
            wk_map[swk[s]].append(s)
    # هفته‌های دوشنبه‌های واقعی
    day = d['time'] // 86400
    mon_wk = (day[mon_events] + 3) // 7
    perm_wrs = np.empty(K_PERM)
    for kk in range(K_PERM):
        wins = []
        for w in mon_wk:
            cand = wk_map.get(w)
            if not cand:
                continue
            s = cand[rng.integers(0, len(cand))]
            wins.append(win_all[s])
        perm_wrs[kk] = np.mean(wins) * 100 if wins else np.nan
    return perm_wrs, uncond_wr


def phase_explore():
    print("=== S613 فاز ۱: گرید قفل ۶ نقطه — فقط نیمهٔ اول ===", flush=True)
    rng = np.random.default_rng(SEED)
    rows = []
    for tf in GRID_TF:
        d = load_tf(tf)
        n = d['n_bars']
        half = n // 2
        atr = wilder_atr34(d['high'], d['low'], d['close'])
        ev = event_bars(d, 0, half)
        print(f"[{tf}] bars={n} half={half} mondays(h1)={len(ev)} src={os.path.basename(d['src'])}", flush=True)
        for k_atr in GRID_K:
            pnl, win, _, ok = simulate_events(d, ev, k_atr, atr)
            m = ok
            nn = int(m.sum())
            wr = float(win[m].mean() * 100) if nn else np.nan
            net = float(pnl[m].sum()) if nn else np.nan
            perm, uncond = null_for_card(d, atr, k_atr, 0, half, ev[m], rng)
            pm, ps = float(np.nanmean(perm)), float(np.nanstd(perm, ddof=1))
            ref = max(uncond, pm)
            lift = wr - ref
            z = lift / ps if ps > 0 else np.nan
            rows.append(dict(tf=tf, k=k_atr, n=nn, wr=round(wr, 2), net_pip=round(net, 1),
                             uncond=round(uncond, 2), perm_mean=round(pm, 2),
                             perm_sd=round(ps, 3), lift=round(lift, 2), z=round(z, 2)))
            print(f"  k={k_atr}: n={nn} WR={wr:.2f} net={net:+.0f} | null u={uncond:.2f} "
                  f"pm={pm:.2f} sd={ps:.3f} | lift={lift:+.2f}pp z={z:.2f}", flush=True)
    json.dump(rows, open(os.path.join(OUT_DIR, 'grid_first_half.json'), 'w'), indent=1)
    # قانون برنده
    elig = [r for r in rows if r['n'] >= 150 and r['net_pip'] > 0]
    if not elig:
        print("\n⛔ مرگ شرافتمندانه: هیچ نقطه‌ای n>=150 ∧ net>0 — هولد‌اوت بکر می‌ماند.", flush=True)
        json.dump(dict(death='no_eligible_point'), open(os.path.join(OUT_DIR, 'decision.json'), 'w'))
        return
    winner = max(elig, key=lambda r: r['z'])
    need = Z_LUCK * winner['perm_sd']
    ok_power = winner['lift'] >= need
    print(f"\nبرنده: {winner['tf']} k={winner['k']} z={winner['z']} lift={winner['lift']}pp | "
          f"لازم برای توان: {need:.2f}pp => {'PASS' if ok_power else 'FAIL'}", flush=True)
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
    print(f"=== S613 فاز ۲: تک‌لمس — کل داده روی برنده {tf} k={k_atr} ===", flush=True)
    rng = np.random.default_rng(SEED + 1)
    d = load_tf(tf)
    n = d['n_bars']
    atr = wilder_atr34(d['high'], d['low'], d['close'])
    ev = event_bars(d, 0, n)
    pnl, win, ebs, ok = simulate_events(d, ev, k_atr, atr)
    ev, pnl, win, ebs = ev[ok], pnl[ok], win[ok], ebs[ok]
    wr = float(win.mean() * 100)
    net = float(pnl.sum())
    print(f"FULL: n={len(ev)} WR={wr:.2f} net={net:+.1f} pip", flush=True)
    perm, uncond = null_for_card(d, atr, k_atr, 0, n, ev, rng)
    pm, ps = float(np.nanmean(perm)), float(np.nanstd(perm, ddof=1))
    print(f"null: uncond={uncond:.2f} perm_mean={pm:.2f} sd={ps:.3f} max={np.nanmax(perm):.2f}", flush=True)

    # DataFrame معاملات با قرارداد موتور برای compute_rqs2
    dt = pd.to_datetime(d['time'], unit='s')
    sl_pip_med = float(np.nanmedian(k_atr * atr[ev]) / PIP)
    trd = pd.DataFrame(dict(
        signal_bar=ev, entry_bar=ev + 1, exit_bar=ebs,
        pnl_pip=pnl, outcome=np.where(win, 'win', 'loss'),
        side='long'))
    null = {'long': dict(uncond_wr=uncond, perm_mean=pm, perm_sd=ps,
                         perm_max=float(np.nanmax(perm)), perm_k=K_PERM),
            'short': None}
    split_bar = int(n * 0.70)
    res = compute_rqs2(trd, 'XAUUSD', sl_pip=sl_pip_med, tp_pip=sl_pip_med,
                       bar_time=dt.values, null=null, n_trials=N_TRIALS,
                       split_bar=split_bar, close=d['close'])
    # رژیم
    trd2 = trd.assign(bar_dt=dt.values[ev])
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
