# -*- coding: utf-8 -*-
"""
S611 — بازداوریِ S153 (Daily-VWAP Confluence Momentum) روی دادهٔ کاملِ ۱۵.۶ ساله
================================================================================
پیش‌ثبت: results/S611_PREREG_VWAP_CONFLUENCE_FULLDATA_REJUDGE.md (کامیت 7de1abe1)
پیکربندیِ منجمد (صفر پارامتر جدید): z>1.5 ∧ close>EMA200 ∧ کندل سبز ∧ range≥0.5×ATR14
cooldown=48 | SL=80 | TP=700 | be=6 | trail=6 | mh=48 | فقط LONG | overlap ممنوع
داور: engine/rqs2.compute_rqs2 با هر ۵ ورودی اجباری. n_trials=200, K_PERM=500,
seed=20260819, split_bar=70%.

مراحل:
  A) دروازهٔ سلامت: بازتولید اعداد بایگانی روی دادهٔ کوتاه data/XAUUSD_M5.csv
     (انتظار: n=2221). عدم بازتولید ⇒ توقف.
  B) اعتبارسنجی جدول-پیامد برداری در برابر موتور رسمی (بیت‌به‌بیت روی سیگنال‌های
     واقعی). واگرایی ⇒ توقف (سابقهٔ S811).
  C) داوری full-data: سیگنال‌ها + معاملات با موتور رسمی؛ null جای‌گشتی K=500 با
     جدول معتبرشده؛ compute_rqs2.
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

SEED = 20260819
K_PERM = 500
N_TRIALS = 200
CFG = dict(z_entry=1.5, ema_trend=200, atr_mult=0.5, cooldown=48,
           sl=80.0, tp=700.0, be=6.0, trail=6.0, mh=48)
ASSET = 'XAUUSD_M5'
SE.ASSETS[ASSET] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                        pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)
PIP = 0.10
SPREAD = 3.3
OUT_DIR = os.path.join(ROOT, 'results', '_s611_vwap')
os.makedirs(OUT_DIR, exist_ok=True)


# ----------------------------------------------------------------------------
# جدول-پیامدِ برداری (آینهٔ دقیقِ se.simulate_trades برای long، slip=0)
# ----------------------------------------------------------------------------
def outcome_table_long(o, h, l, c, sl_pip, tp_pip, be_pip, trail_pip, mh):
    """برای هر کندلِ سیگنالِ فرضی sb، پیامدِ معاملهٔ لانگ با ورود در open[sb+1].
    خروجی: exit_bar[sb], pnl_pip[sb], win[sb] (NaN/-1 برای sbهای نامعتبر).
    منطق دقیقاً آینهٔ se.simulate_trades است:
      - چکِ خروج با cur_sl از کندلِ قبل؛ هر دو خورد ⇒ loss (بدترین)
      - trailing/BE فقط از کندلِ بعد از ورود به‌روز می‌شود
      - timeout ⇒ close آخرین کندلِ پنجره
      - pnl = (exit-fill)/pip - spread ؛ win = pnl>0
    """
    n = len(o)
    sl_d, tp_d = sl_pip * PIP, tp_pip * PIP
    be_d, tr_d = be_pip * PIP, trail_pip * PIP
    # sb معتبر: entry=sb+1 < n
    m = n - 1  # sb در [0, m)
    fill = o[1:1 + m].astype(np.float64)          # ورود = open[sb+1]
    sl0 = fill - sl_d
    tp_price = fill + tp_d
    cur_sl = sl0.copy()
    peak = np.zeros(m)
    exit_price = np.full(m, np.nan)
    exit_bar = np.full(m, -1, dtype=np.int64)
    active = np.ones(m, dtype=bool)
    sb_idx = np.arange(m)
    for off in range(0, CFG['mh']):
        j = sb_idx + 1 + off               # کندل جاری هر معامله
        valid = active & (j < n)
        # معاملاتی که پنجره‌شان قبل از mh به انتهای داده می‌رسد: timeout در n-1
        ran_out = active & ~ (j < n)
        if ran_out.any():
            eb = np.minimum(sb_idx[ran_out] + CFG['mh'], n - 1)
            # end-1 = n-1 در این حالت
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
        # هر دو ⇒ loss (بدترین)؛ tp تنها ⇒ win؛ sl تنها ⇒ loss
        exit_now = hit_sl | hit_tp
        price_now = np.where(hit_sl, cs, tpp)     # اگر هر دو، cs (loss) مقدم
        idx_v = np.where(valid)[0]
        done = idx_v[exit_now]
        exit_bar[done] = jj[exit_now]
        exit_price[done] = price_now[exit_now]
        active[done] = False
        # به‌روزرسانی trailing/BE فقط اگر off>=1 (کندل ورود نه)
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
    # باقی‌مانده: timeout در end-1 = sb+mh (چون sb+mh<n برایشان)
    rem = np.where(active)[0]
    if rem.size:
        eb = np.minimum(sb_idx[rem] + CFG['mh'], n - 1)
        exit_bar[rem] = eb
        exit_price[rem] = c[eb]
    pnl = (exit_price - fill) / PIP - SPREAD
    win = pnl > 0
    return exit_bar, pnl, win


def fifo_from_table(sig_bars, exit_bar, pnl, win):
    """اعمالِ قانونِ بدونِ هم‌پوشانی (آینهٔ busy_until موتور)."""
    take_pnl, take_win, take_sb, take_eb = [], [], [], []
    busy = -1
    for sb in sig_bars:
        eb = exit_bar[sb]
        if eb < 0:
            continue
        if sb + 1 <= busy:
            continue
        take_pnl.append(pnl[sb]); take_win.append(win[sb])
        take_sb.append(sb); take_eb.append(eb)
        busy = eb
    return (np.array(take_sb), np.array(take_eb),
            np.array(take_pnl), np.array(take_win))


def build_df(d):
    df = pd.DataFrame({k: d[k] for k in ['time', 'open', 'high', 'low', 'close', 'volume']})
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def run_layer(df):
    vwap, z = daily_vwap_z(df)
    ls, ss = gen_signal(df, z, CFG['z_entry'], CFG['ema_trend'],
                        CFG['atr_mult'], CFG['cooldown'])
    trd = SE.simulate_trades(df, ls, ss, CFG['sl'], CFG['tp'], ASSET,
                             max_hold=CFG['mh'], be_trigger_pip=CFG['be'],
                             trail_pip=CFG['trail'])
    return ls, trd


def main():
    t0 = time.time()
    # ------------------------------------------------------------------ A
    print("=== A) دروازهٔ سلامت: دادهٔ کوتاه (بایگانی) ===", flush=True)
    df_s = SE.load_data(os.path.join(ROOT, 'data', 'XAUUSD_M5.csv'))
    ls_s, trd_s = run_layer(df_s)
    st_s, _ = SE.run_capital(trd_s, ASSET, risk_pct=0.5, compounding=True)
    repro = dict(n=len(trd_s), wr=round(float((trd_s['outcome'] == 'win').mean() * 100), 2),
                 net=round(float(st_s['net_profit']), 0), pf=round(float(st_s.get('profit_factor', 0)), 3),
                 archive_expect=dict(n=2221, net=14135))
    print("SHORT-DATA:", repro, flush=True)
    json.dump(repro, open(os.path.join(OUT_DIR, 'repro_short.json'), 'w'), indent=1)
    if abs(len(trd_s) - 2221) > 0:
        print("⛔ بازتولید n شکست خورد — توقف طبق پیش‌ثبت"); sys.exit(2)

    # ------------------------------------------------------------------ B
    print("=== B) اعتبارسنجی جدول-پیامد در برابر موتور (روی دادهٔ کوتاه) ===", flush=True)
    o, h, l, c = [df_s[k].values.astype(np.float64) for k in ['open', 'high', 'low', 'close']]
    eb_t, pnl_t, win_t = outcome_table_long(o, h, l, c, CFG['sl'], CFG['tp'],
                                            CFG['be'], CFG['trail'], CFG['mh'])
    sig_bars = np.where(ls_s)[0]
    tsb, teb, tpnl, twin = fifo_from_table(sig_bars, eb_t, pnl_t, win_t)
    eng_sb = trd_s['signal_bar'].values
    eng_pnl = trd_s['pnl_pip'].values
    ok_n = len(tsb) == len(eng_sb)
    ok_sb = ok_n and np.array_equal(tsb, eng_sb)
    ok_pnl = ok_sb and np.allclose(tpnl, eng_pnl, atol=1e-9)
    print(f"table n={len(tsb)} engine n={len(eng_sb)} | sb match={ok_sb} pnl match={ok_pnl}", flush=True)
    if not (ok_n and ok_sb and ok_pnl):
        d = np.where(tsb[:min(len(tsb),len(eng_sb))] != eng_sb[:min(len(tsb),len(eng_sb))])[0][:5] if ok_n else []
        print("⛔ واگرایی جدول/موتور — توقف (سابقهٔ S811)", d); sys.exit(3)

    # ------------------------------------------------------------------ C
    print("=== C) داوری full-data ===", flush=True)
    from tools import s434_fast_data as fd
    d = fd.load_fast('XAUUSD', 'M5')
    print("src =", d['src'], "| bars =", d['n_bars'], "| span =", d['span_years'], flush=True)
    df = build_df(d)
    ls, trd = run_layer(df)
    n = len(df)
    wr = float((trd['outcome'] == 'win').mean() * 100)
    print(f"FULL: n_trades={len(trd)} WR={wr:.2f}% net_pip={trd['pnl_pip'].sum():+.0f}", flush=True)

    o, h, l, c = [df[k].values.astype(np.float64) for k in ['open', 'high', 'low', 'close']]
    t1 = time.time()
    eb_t, pnl_t, win_t = outcome_table_long(o, h, l, c, CFG['sl'], CFG['tp'],
                                            CFG['be'], CFG['trail'], CFG['mh'])
    print(f"outcome table built in {time.time()-t1:.1f}s", flush=True)

    # اعتبارسنجی دوم روی full (همان معیار بیت‌به‌بیت)
    sig_bars = np.where(ls)[0]
    tsb, teb, tpnl, twin = fifo_from_table(sig_bars, eb_t, pnl_t, win_t)
    ok = (len(tsb) == len(trd) and np.array_equal(tsb, trd['signal_bar'].values)
          and np.allclose(tpnl, trd['pnl_pip'].values, atol=1e-9))
    print("full-data table validation:", ok, flush=True)
    if not ok:
        print("⛔ واگرایی روی full — توقف"); sys.exit(3)

    # uncond_wr: پیامدِ همهٔ کندل‌های معتبر (بدون FIFO — WR بی‌قیدِ هندسه)
    valid = eb_t >= 0
    uncond_wr = float(win_t[valid].mean() * 100)

    # null جای‌گشتی: K=500، هر بار همان تعدادِ سیگنالِ خام، سپس FIFO
    rng = np.random.default_rng(SEED)
    n_sig = len(sig_bars)
    perm_wrs = np.empty(K_PERM)
    t2 = time.time()
    elig = np.where(valid)[0]
    for k in range(K_PERM):
        pb = np.sort(rng.choice(elig, size=n_sig, replace=False))
        _, _, _, w = fifo_from_table(pb, eb_t, pnl_t, win_t)
        perm_wrs[k] = w.mean() * 100 if len(w) else np.nan
    print(f"null K={K_PERM} built in {time.time()-t2:.1f}s | "
          f"perm_mean={np.nanmean(perm_wrs):.2f} sd={np.nanstd(perm_wrs):.3f} "
          f"max={np.nanmax(perm_wrs):.2f} | uncond={uncond_wr:.2f}", flush=True)

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
    # p_emp برای گزارش
    obs_wr = wr
    p_emp = float((np.sum(perm_wrs >= obs_wr) + 1) / (K_PERM + 1))

    out = dict(seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS, cfg=CFG,
               src=d['src'], n_bars=int(n), span_years=d['span_years'],
               n_trades=int(len(trd)), wr=round(obs_wr, 2),
               net_pip=round(float(trd['pnl_pip'].sum()), 1),
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
               notes=res['notes'])
    json.dump(out, open(os.path.join(OUT_DIR, 'full_verdict.json'), 'w'),
              indent=1, ensure_ascii=False, default=str)
    print("\n=== حکم موتور ===", flush=True)
    print("verdict:", res['verdict'], "| score:", res['rqs2_score'])
    print("gates:", res['gates'])
    print("notes:", res['notes'])
    # ذخیرهٔ معاملات برای ممیزی هم‌پوشانی/رژیم
    trd.assign(bar_dt=df['dt'].values[trd['signal_bar'].values]).to_csv(
        os.path.join(OUT_DIR, 'full_trades.csv'), index=False)
    print(f"\ntotal {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
