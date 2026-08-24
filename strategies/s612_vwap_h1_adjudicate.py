# -*- coding: utf-8 -*-
"""
S612 — داوری رسمی RQS2 روی سرنخ H1 کشف‌شده در S611
=====================================================
پیش‌ثبت: results/S612_PREREG_VWAP_CONFLUENCE_H1_ADJUDICATION.md (کامیت 3d446376)
پیکربندی منجمد S153 (بیت‌به‌بیت): z>1.5 ∧ close>EMA200 ∧ کندل سبز ∧ range≥0.5×ATR14
cooldown=48 | SL=80 | TP=700 | be=6 | trail=6 | mh=48 | فقط LONG
داده: mt5_full XAUUSD H1 (۱۵.۶ سال). n_trials=250 (۲۰۰ دودمان + ۱۹ نگاه MTF +
۳۱ جریمهٔ انتخاب بهترین‌از۱۹). K_PERM=500, seed=20260821, split=70%.

دروازه‌های سلامت:
  A) هویت: n_trades باید دقیقاً 1070 باشد (برابر سطر MTF ثبت‌شده در S611).
  B) جدول-پیامد برداری باید بیت‌به‌بیت با موتور رسمی روی H1 مطابق باشد.
سپس: null جای‌گشتی K=500 (FIFO در هر جای‌گشت) + compute_rqs2 با ۵ ورودی اجباری.
تجزیهٔ رژیم pre/post 2023-09 + سالانه (شاهد، نه داوری).
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as SE
from engine.rqs2 import compute_rqs2
from s153_gold_vwap_confluence_momentum import daily_vwap_z, gen_signal

SEED = 20260821
K_PERM = 500
N_TRIALS = 250
EXPECT_N = 1070          # دروازهٔ هویت با سطر MTF
CFG = dict(z_entry=1.5, ema_trend=200, atr_mult=0.5, cooldown=48,
           sl=80.0, tp=700.0, be=6.0, trail=6.0, mh=48)
ASSET = 'XAUUSD_H1_S612'
SE.ASSETS[ASSET] = dict(file='data/mt5_full/XAUUSD_H1.csv', pip=0.10, contract=100.0,
                        pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)
PIP = 0.10
SPREAD = 3.3
OUT_DIR = os.path.join(ROOT, 'results', '_s612_vwap_h1')
os.makedirs(OUT_DIR, exist_ok=True)


def outcome_table_long(o, h, l, c):
    """آینهٔ دقیق se.simulate_trades برای long (اعتبارشده بیت‌به‌بیت در S611)."""
    n = len(o)
    sl_d, tp_d = CFG['sl'] * PIP, CFG['tp'] * PIP
    be_d, tr_d = CFG['be'] * PIP, CFG['trail'] * PIP
    m = n - 1
    fill = o[1:1 + m].astype(np.float64)
    cur_sl = fill - sl_d
    tp_price = fill + tp_d
    peak = np.zeros(m)
    exit_price = np.full(m, np.nan)
    exit_bar = np.full(m, -1, dtype=np.int64)
    active = np.ones(m, dtype=bool)
    sb_idx = np.arange(m)
    for off in range(0, CFG['mh']):
        j = sb_idx + 1 + off
        valid = active & (j < n)
        ran_out = active & ~(j < n)
        if ran_out.any():
            exit_bar[ran_out] = n - 1
            exit_price[ran_out] = c[n - 1]
            active[ran_out] = False
        if not valid.any():
            break
        jj = j[valid]
        hi, lo = h[jj], l[jj]
        cs = cur_sl[valid]
        tpp = tp_price[valid]
        hit_sl = lo <= cs
        hit_tp = hi >= tpp
        exit_now = hit_sl | hit_tp
        price_now = np.where(hit_sl, cs, tpp)
        idx_v = np.where(valid)[0]
        done = idx_v[exit_now]
        exit_bar[done] = jj[exit_now]
        exit_price[done] = price_now[exit_now]
        active[done] = False
        if off >= 1:
            alive = idx_v[~exit_now]
            if alive.size:
                ja = sb_idx[alive] + 1 + off
                favor = h[ja] - fill[alive]
                pk = np.maximum(peak[alive], favor)
                peak[alive] = pk
                ncs = cur_sl[alive]
                be_on = pk >= be_d
                ncs = np.where(be_on, np.maximum(ncs, fill[alive]), ncs)
                tr_on = pk > 0
                ncs = np.where(tr_on, np.maximum(ncs, fill[alive] + pk - tr_d), ncs)
                cur_sl[alive] = ncs
    rem = np.where(active)[0]
    if rem.size:
        eb = np.minimum(sb_idx[rem] + CFG['mh'], n - 1)
        exit_bar[rem] = eb
        exit_price[rem] = c[eb]
    pnl = (exit_price - fill) / PIP - SPREAD
    win = pnl > 0
    return exit_bar, pnl, win


def fifo_from_table(sig_bars, exit_bar, pnl, win):
    take_pnl, take_win, take_sb = [], [], []
    busy = -1
    for sb in sig_bars:
        eb = exit_bar[sb]
        if eb < 0:
            continue
        if sb + 1 <= busy:
            continue
        take_pnl.append(pnl[sb]); take_win.append(win[sb]); take_sb.append(sb)
        busy = eb
    return np.array(take_sb), np.array(take_pnl), np.array(take_win)


def main():
    t0 = time.time()
    from tools import s434_fast_data as fd
    d = fd.load_fast('XAUUSD', 'H1')
    print("src =", d['src'], "| bars =", d['n_bars'], "| span =", d['span_years'], flush=True)
    df = pd.DataFrame({k: d[k] for k in ['time', 'open', 'high', 'low', 'close', 'volume']})
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df = df.reset_index(drop=True)

    vwap, z = daily_vwap_z(df)
    ls, ss = gen_signal(df, z, CFG['z_entry'], CFG['ema_trend'],
                        CFG['atr_mult'], CFG['cooldown'])
    trd = SE.simulate_trades(df, ls, ss, CFG['sl'], CFG['tp'], ASSET,
                             max_hold=CFG['mh'], be_trigger_pip=CFG['be'],
                             trail_pip=CFG['trail'])
    n = len(df)
    wr = float((trd['outcome'] == 'win').mean() * 100)
    net = float(trd['pnl_pip'].sum())
    print(f"H1: n_trades={len(trd)} WR={wr:.2f}% net_pip={net:+.1f}", flush=True)

    # --- دروازهٔ A: هویت با سطر MTF
    if len(trd) != EXPECT_N:
        print(f"⛔ دروازهٔ هویت شکست: n={len(trd)} != {EXPECT_N} — توقف"); sys.exit(2)
    print("✓ A) هویت n=1070 تایید", flush=True)

    # --- دروازهٔ B: جدول بیت‌به‌بیت
    o, h, l, c = [df[k].values.astype(np.float64) for k in ['open', 'high', 'low', 'close']]
    eb_t, pnl_t, win_t = outcome_table_long(o, h, l, c)
    sig_bars = np.where(ls)[0]
    tsb, tpnl, twin = fifo_from_table(sig_bars, eb_t, pnl_t, win_t)
    ok = (len(tsb) == len(trd) and np.array_equal(tsb, trd['signal_bar'].values)
          and np.allclose(tpnl, trd['pnl_pip'].values, atol=1e-9))
    print("✓ B) table bit-exact:", ok, flush=True)
    if not ok:
        print("⛔ واگرایی جدول/موتور — توقف"); sys.exit(3)

    # --- null: uncond + جای‌گشتی K=500 با FIFO
    valid = eb_t >= 0
    uncond_wr = float(win_t[valid].mean() * 100)
    rng = np.random.default_rng(SEED)
    elig = np.where(valid)[0]
    n_sig = len(sig_bars)
    perm_wrs = np.empty(K_PERM)
    t2 = time.time()
    for k in range(K_PERM):
        pb = np.sort(rng.choice(elig, size=n_sig, replace=False))
        _, _, w = fifo_from_table(pb, eb_t, pnl_t, win_t)
        perm_wrs[k] = w.mean() * 100 if len(w) else np.nan
    print(f"null K={K_PERM} in {time.time()-t2:.1f}s | perm_mean={np.nanmean(perm_wrs):.2f} "
          f"sd={np.nanstd(perm_wrs, ddof=1):.3f} max={np.nanmax(perm_wrs):.2f} | "
          f"uncond={uncond_wr:.2f}", flush=True)

    null = {'long': dict(uncond_wr=uncond_wr,
                         perm_mean=float(np.nanmean(perm_wrs)),
                         perm_sd=float(np.nanstd(perm_wrs, ddof=1)),
                         perm_max=float(np.nanmax(perm_wrs)),
                         perm_k=K_PERM),
            'short': None}

    split_bar = int(n * 0.70)
    res = compute_rqs2(trd, ASSET, sl_pip=CFG['sl'], tp_pip=CFG['tp'],
                       bar_time=df['dt'].values, null=null, n_trials=N_TRIALS,
                       split_bar=split_bar, close=c)
    p_emp = float((np.sum(perm_wrs >= wr) + 1) / (K_PERM + 1))

    # --- تجزیهٔ رژیم (شاهد)
    trd2 = trd.assign(bar_dt=df['dt'].values[trd['signal_bar'].values])
    cut = pd.Timestamp('2023-09-01')
    pre = trd2[trd2['bar_dt'] < cut]
    post = trd2[trd2['bar_dt'] >= cut]
    regime = dict(
        pre=dict(n=int(len(pre)), wr=round(float((pre['outcome'] == 'win').mean() * 100), 2),
                 net_pip=round(float(pre['pnl_pip'].sum()), 1)),
        post=dict(n=int(len(post)), wr=round(float((post['outcome'] == 'win').mean() * 100), 2),
                  net_pip=round(float(post['pnl_pip'].sum()), 1)))
    yearly = {}
    for y, g in trd2.groupby(trd2['bar_dt'].dt.year):
        yearly[int(y)] = dict(n=int(len(g)),
                              wr=round(float((g['outcome'] == 'win').mean() * 100), 1),
                              net=round(float(g['pnl_pip'].sum()), 0))
    print("REGIME pre :", regime['pre'], flush=True)
    print("REGIME post:", regime['post'], flush=True)
    for y in sorted(yearly):
        print(f"  {y}: {yearly[y]}", flush=True)

    out = dict(seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS, cfg=CFG,
               src=d['src'], n_bars=int(n), span_years=d['span_years'],
               n_trades=int(len(trd)), wr=round(wr, 2), net_pip=round(net, 1),
               uncond_wr=round(uncond_wr, 2),
               perm_mean=round(float(np.nanmean(perm_wrs)), 3),
               perm_sd=round(float(np.nanstd(perm_wrs, ddof=1)), 4),
               perm_max=round(float(np.nanmax(perm_wrs)), 2),
               p_emp=p_emp, split_bar=split_bar,
               verdict=res['verdict'], rqs2_score=res['rqs2_score'],
               gates={k2: (None if v is None else bool(v)) for k2, v in res['gates'].items()},
               metrics={k2: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                        for k2, v in res['metrics'].items()
                        if isinstance(v, (int, float, str, bool, np.floating, np.integer))},
               notes=res['notes'], regime=regime, yearly=yearly)
    json.dump(out, open(os.path.join(OUT_DIR, 'h1_verdict.json'), 'w'),
              indent=1, ensure_ascii=False, default=str)
    trd2.to_csv(os.path.join(OUT_DIR, 'h1_trades.csv'), index=False)
    print("\n=== حکم موتور ===", flush=True)
    print("verdict:", res['verdict'], "| score:", res['rqs2_score'])
    print("gates:", res['gates'])
    print("notes:", res['notes'])
    print(f"\ntotal {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
