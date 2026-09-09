# -*- coding: utf-8 -*-
"""
S610 — Gold/DXY decoupling — H8/D1 — LONG only — drift-conditioned null — XAUUSD
=================================================================================
پیش‌ثبت: results/S610_PREREG_DECOUPLING_H8D1_LONG_CONDITIONED.md (کامیت b5768c93)

رویداد (بار TF طلا با زمان بسته T): z_g = r_g/sd34_prev ≥ 1 ∧ z_d ≥ 1 (z_d از بازدهٔ تجمعی DXY-H1 در پنجرهٔ بار)
درون فضای درفت‌مثبت: close[t-1] > close[t-1-LB]  (LB=90 برای H8، 30 برای D1)
هندسه منجمد S526: SL=1.5×median(ATR100 کل تاریخ)، TP=1.5×SL، hold 16 (H8)/6 (D1)، FIFO.
نول شرطی: uncond = هر بار درفت‌مثبت (stride 1)؛ perm = K نمونه به اندازهٔ n از فضای درفت‌مثبت.
confirm: نیمهٔ دوم فضای رویداد، کارت H8: n>=40 ∧ net>0 ∧ lift>=2 sd. verdict: compute_rqs2 n_trials=622.
داده: طلا data/mt5_full (کامل ۱۵.۶y؛ assert)، DXY data/DXY_H1.csv (2019-12+).
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)
from engine.rqs2 import compute_rqs2

SEED = 20260907
K_PERM = 1000
N_TRIALS = 622
Z_EVT = 1.0
W_SD = 34
PIP = 0.10
SPREAD = 3.3
RR = 1.5
SL_MULT = 1.5
CARDS = {'H8': dict(lb=90, hold=16, hours=8), 'D1': dict(lb=30, hold=6, hours=24)}
PRIMARY = 'H8'
OUT_DIR = os.path.join(ROOT, 'results', '_s610_decoup')
os.makedirs(OUT_DIR, exist_ok=True)


def load_gold(tf):
    from tools import s434_fast_data as fd
    d = fd.load_fast('XAUUSD', tf)
    assert 'mt5_full' in d['src'], d['src']
    return d


def load_dxy():
    x = pd.read_csv(os.path.join(ROOT, 'data', 'DXY_H1.csv')).sort_values('time').drop_duplicates('time')
    return x['time'].values.astype(np.int64), x['close'].values.astype(float)


def wilder_atr(h, l, c, p=100):
    n = len(c); tr = np.empty(n); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = np.full(n, np.nan)
    if n <= p: return atr
    atr[p] = tr[1:p + 1].mean(); a = atr[p]
    for i in range(p + 1, n):
        a = (a * (p - 1) + tr[i]) / p; atr[i] = a
    return atr


def causal_z(r):
    s = pd.Series(r)
    sd_prev = s.rolling(W_SD).std(ddof=1).shift(1).values
    with np.errstate(invalid='ignore', divide='ignore'):
        return r / sd_prev


def dxy_window_z(g_time, g_hours, dt, dc):
    """بازدهٔ تجمعی DXY در پنجرهٔ [T-hours, T] هر بار طلا (T = بسته = open+hours)؛ z با sd34 پنجره‌های قبلی (غیرهم‌پوشان)."""
    T = g_time + g_hours * 3600
    # آخرین close DXY با time+3600 <= T  (بار H1 با زمان open t بسته می‌شود در t+3600)
    close_t = dt + 3600
    iT = np.searchsorted(close_t, T, side='right') - 1
    i0 = np.searchsorted(close_t, T - g_hours * 3600, side='right') - 1
    r = np.full(len(g_time), np.nan)
    ok = (iT > i0) & (i0 >= 0)
    r[ok] = np.log(dc[iT[ok]] / dc[i0[ok]])
    return causal_z(r), ok


def build(tf):
    cfg = CARDS[tf]
    d = load_gold(tf)
    o, h, l, c, t = d['open'], d['high'], d['low'], d['close'], d['time']
    n = len(c)
    rg = np.full(n, np.nan); rg[1:] = np.diff(np.log(c))
    zg = causal_z(rg)
    dt, dc = load_dxy()
    zd, okd = dxy_window_z(t, cfg['hours'], dt, dc)
    lb = cfg['lb']
    drift = np.zeros(n, dtype=bool)
    drift[lb + 1:] = c[lb:-1] > c[:-lb - 1]           # close[t-1] > close[t-1-lb]
    atr = wilder_atr(h, l, c, 100)
    sl_abs = SL_MULT * float(np.nanmedian(atr))       # منجمد S526: median ATR100 کل تاریخ
    dxy_span = (t >= dt[0]) & (t + cfg['hours'] * 3600 <= dt[-1] + 3600)
    evt = drift & okd & dxy_span & (zg >= Z_EVT) & (zd >= Z_EVT)
    evt[-2:] = False
    space = drift & dxy_span; space[-2:] = False
    return d, dict(evt=np.where(evt)[0], space=np.where(space)[0], sl_abs=sl_abs, atr_med=float(np.nanmedian(atr)),
                   n_bars=n, span_years=d['span_years'], src=d['src'])


def simulate(d, sigs, sl_abs, hold):
    """LONG، ورود open[s+1]، SL/TP ثابت، تقدم SL، FIFO (allow_overlap=False)، close در hold."""
    o, h, l, c = d['open'], d['high'], d['low'], d['close']; n = len(c)
    tp_abs = RR * sl_abs
    rows = []; busy_until = -1
    for s in sigs:
        e = s + 1
        if e >= n or e <= busy_until: continue
        entry = o[e]; sl = entry - sl_abs; tp = entry + tp_abs
        last = min(e + hold, n - 1); ex = last; px = c[last]
        for b in range(e, last + 1):
            if l[b] <= sl: ex, px = b, sl; break
            if h[b] >= tp: ex, px = b, tp; break
        pnl = (px - entry) / PIP - SPREAD
        rows.append((s, e, ex, pnl, 'win' if pnl > 0 else 'loss'))
        busy_until = ex
    return rows


def cond_null(d, space, n_sig, sl_abs, hold, rng, k):
    unc = simulate(d, space, sl_abs, hold)                    # stride 1 روی همهٔ فضای درفت‌مثبت
    uncond = 100.0 * np.mean([r[4] == 'win' for r in unc]) if unc else np.nan
    wrs = []
    for _ in range(k):
        pos = np.sort(rng.choice(space, size=min(n_sig, len(space)), replace=False))
        tr = simulate(d, pos, sl_abs, hold)
        if len(tr) >= min(20, max(5, n_sig // 2)): wrs.append(100.0 * np.mean([r[4] == 'win' for r in tr]))
    a = np.asarray(wrs)
    return dict(uncond_wr=float(uncond), uncond_n=len(unc), perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                perm_max=float(a.max()), perm_k=int(len(a)))


def card_stats(rows, nl):
    n = len(rows); w = np.array([r[4] == 'win' for r in rows]); p = np.array([r[3] for r in rows])
    wr = 100.0 * w.mean(); ref = max(nl['uncond_wr'], nl['perm_mean']); lift = wr - ref
    return dict(n=n, wr=round(wr, 2), net_pip=round(float(p.sum()), 1), pf=round(float(p[p > 0].sum() / max(1e-9, -p[p < 0].sum())), 3),
                **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in nl.items()},
                ref=round(ref, 2), lift=round(lift, 2), z=round(lift / nl['perm_sd'], 2) if nl['perm_sd'] > 0 else None)


def phase_confirm():
    t0 = time.time(); rng = np.random.default_rng(SEED)
    out = {}
    for tf in CARDS:
        d, B = build(tf)
        evt, space = B['evt'], B['space']
        half = len(evt) // 2
        evt2 = evt[half:]; split_bar = int(evt[half])
        space2 = space[space >= split_bar]
        rows = simulate(d, evt2, B['sl_abs'], CARDS[tf]['hold'])
        print(f"[{tf}] bars={B['n_bars']} span={B['span_years']:.2f}y src={os.path.basename(B['src'])} | events total={len(evt)} "
              f"(P3 120-300 -> {'OK' if 120 <= len(evt) <= 300 else 'OUT'}) half2={len(evt2)} from {pd.to_datetime(d['time'][split_bar], unit='s')} | "
              f"space2={len(space2)} | SL={B['sl_abs']/PIP:.1f}pip TP={RR*B['sl_abs']/PIP:.1f}pip", flush=True)
        nl = cond_null(d, space2, len(rows), B['sl_abs'], CARDS[tf]['hold'], rng, 500)
        st = card_stats(rows, nl); st.update(tf=tf, split_bar=split_bar, n_events_total=int(len(evt)), primary=(tf == PRIMARY))
        out[tf] = st
        print(f"  half2: n={st['n']} WR={st['wr']} net={st['net_pip']:+.0f} PF={st['pf']} | cond-null uncond={st['uncond_wr']} "
              f"pm={st['perm_mean']} sd={st['perm_sd']} max={st['perm_max']} | lift={st['lift']:+.2f} z={st['z']}", flush=True)
    json.dump(out, open(os.path.join(OUT_DIR, 'confirm_half2.json'), 'w'), indent=1)
    p = out[PRIMARY]; need = 2.0 * p['perm_sd']
    passed = bool(p['n'] >= 40 and p['net_pip'] > 0 and p['lift'] >= need)
    dec = dict(primary=p, rule='n>=40 AND net>0 AND lift>=2.0*perm_sd', need_lift=round(need, 2), confirm_pass=passed,
               verdict=None if passed else 'REJECT', score=None if passed else 0, elapsed_s=round(time.time() - t0, 1))
    json.dump(dec, open(os.path.join(OUT_DIR, 'decision.json'), 'w'), indent=1)
    print(("\n✅ تأیید گذشت → مرحلهٔ حکم" if passed else f"\n⛔ تأیید شکست (lift={p['lift']} vs need {need:.2f}, n={p['n']}, net={p['net_pip']}) — REJECT 0."), flush=True)


def phase_verdict():
    dec = json.load(open(os.path.join(OUT_DIR, 'decision.json')))
    if not dec.get('confirm_pass'): print("⛔ مجاز نیست."); sys.exit(2)
    rng = np.random.default_rng(SEED + 1)
    for tf in CARDS:
        d, B = build(tf)
        evt, space = B['evt'], B['space']; hold = CARDS[tf]['hold']
        rows = simulate(d, evt, B['sl_abs'], hold)
        nl = cond_null(d, space, len(rows), B['sl_abs'], hold, rng, K_PERM)
        st = card_stats(rows, nl)
        split_bar = int(evt[len(evt) // 2])
        sl_pip = B['sl_abs'] / PIP
        trd = pd.DataFrame(dict(signal_bar=[r[0] for r in rows], entry_bar=[r[1] for r in rows], exit_bar=[r[2] for r in rows],
                                pnl_pip=[r[3] for r in rows], outcome=[r[4] for r in rows], sl_pip=sl_pip, direction='long'))
        null = {'long': {k: nl[k] for k in ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')},
                'short': {k: nl[k] for k in ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')}}
        dt = pd.to_datetime(d['time'], unit='s')
        res = compute_rqs2(trd, 'XAUUSD', sl_pip=sl_pip, tp_pip=RR * sl_pip, bar_time=dt.values, null=null,
                           n_trials=N_TRIALS, split_bar=split_bar, close=d['close'])
        print(f"\n=== {tf} FULL: n={st['n']} WR={st['wr']} net={st['net_pip']:+.0f} PF={st['pf']} lift={st['lift']:+.2f} z={st['z']} | "
              f"verdict={res['verdict']} score={res['rqs2_score']} gates={res['gates']}", flush=True)
        json.dump(dict(tf=tf, stats=st, sl_pip=sl_pip, tp_pip=RR * sl_pip, split_bar=split_bar, n_trials=N_TRIALS, rqs2=res),
                  open(os.path.join(OUT_DIR, f'verdict_{tf}.json'), 'w'), indent=1, default=str)
        trd.assign(bar_dt=dt.values[trd['signal_bar'].values]).to_csv(os.path.join(OUT_DIR, f'trades_{tf}.csv'), index=False)


if __name__ == '__main__':
    (phase_confirm if (sys.argv[1] if len(sys.argv) > 1 else 'confirm') == 'confirm' else phase_verdict)()
