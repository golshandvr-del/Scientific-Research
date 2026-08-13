#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S400 — گپِ بازگشاییِ روزِ معاملاتی XAUUSD (Mission 1, بازهٔ S400–S409)
======================================================================
پیش‌ثبت: results/S400_PREREG_GAP_OPEN_XAU.md  (مسیرِ C — commit پیش از هر عدد)
داور:    RQS2 v2.6 (engine/rqs2.py)

سیگنال: بارِ اولِ روزِ معاملاتی (وقفهٔ زمانیِ ≥1800s بین دو بار = مرزِ روز؛
هیچ ساعتی hardcode نمی‌شود — تلهٔ DST). اگر گپِ بازگشایی منفی و |gap| بزرگ‌تر
از آستانهٔ *شناور* باشد ⇒ LONG در open همان بار.

فضای پارامتر (قفل‌شده در پیش‌ثبت — ۷۲ ترکیب):
  آستانه‌ها (۹): T-Q{60,70,80}   صدکِ غلتانِ |gap| روی ۲۵۰ روزِ قبل
                 T-QW{60,70,80}  همان صدک، تفکیکِ دوشنبه/غیر‌دوشنبه
                 T-ATR{.10,.15,.20} ضریبِ ATR(14) روزانهٔ دیروز
  خروج‌ها (۴):   X-BAR           کلوزِ همان بار (SL حفاظتی = 1×ATRd)
                 X-FILL k∈{1.0,1.5}  TP=کلوزِ دیروز، SL=k×|gap|، تا پایانِ روز
                 X-LOW           شکستِ کفِ ساعتِ اول، تا پایانِ روز
  فیلترها (۲):   F-NONE / F-DOW (حذفِ بدترین روزِ هفتهٔ منفیِ نیمهٔ اول)

قراردادهای شبیه‌ساز (کپیِ عینِ engine/scalp_engine.py::simulate_trades):
  - ورود = open بارِ بعدِ سیگنال (اینجا: خودِ بارِ اولِ روز؛ سیگنال روی بارِ آخرِ دیروز)
  - در هر بار TP/SL چک می‌شود؛ برخوردِ همزمانِ TP∧SL در یک بار = باخت (بدترین حالت)
  - خروجِ استاپ = خودِ سطحِ استاپ (بدونِ مدل‌سازیِ gap-through — عینِ موتور)
  - pnl_pip = حرکتِ قیمت/pip − spread(3.3) ؛ برچسبِ win/loss از علامتِ pnl
حالت‌ها:
  python3 strategies/s400_gap_open.py parity   ← ممیزیِ برابری X-BAR با موتور
  python3 strategies/s400_gap_open.py tune M15 ← تنظیم فقط روی نیمهٔ اول
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se

SEED = 400
SPREAD_PIP = 3.3          # ASSETS['XAUUSD'] — $0.33/oz
PIP = 0.1
DAY_BREAK_SEC = 1800      # مرزِ روز = وقفهٔ ≥۳۰ دقیقه (ضد-DST، قفل در پیش‌ثبت)
ROLL_DAYS = 250           # پنجرهٔ صدکِ غلتان (پیش‌ثبت)
MIN_ROLL_OBS = 60         # warmup: کمتر از این مشاهده ⇒ روز معامله نمی‌شود
SPLIT_BAR = {'M15': 75000, 'M30': 90691, 'H1': 45475}  # قفل در پیش‌ثبت

CKPT = os.path.join(os.path.dirname(__file__), '..', 'results', '_s400_tune_ckpt_{tf}.json')


# ─────────────────────────── ساختارِ روزها ───────────────────────────

def build_days(df):
    """تفکیکِ روزهای معاملاتی با لنگرِ وقفهٔ زمانی. خروجی: لیستِ dict روزها."""
    t = df['time'].values.astype('int64')
    o = df['open'].values; h = df['high'].values
    l = df['low'].values;  c = df['close'].values
    gaps_t = np.diff(t)
    brk = np.where(gaps_t >= DAY_BREAK_SEC)[0]   # بارِ i ⇒ بارِ i+1 اولِ روز است
    starts = np.concatenate(([0], brk + 1))
    ends = np.concatenate((brk, [len(df) - 1]))  # آخرین بارِ هر روز
    days = []
    dts = pd.to_datetime(df['dt'].values)
    for k in range(1, len(starts)):              # روزِ صفر prev_close ندارد
        fb, le = int(starts[k]), int(ends[k])
        pc = c[fb - 1]
        # پایانِ «ساعتِ اول»: بارهایی که openشان < t[fb]+3600
        fh_end = fb
        while fh_end + 1 <= le and t[fh_end + 1] < t[fb] + 3600:
            fh_end += 1
        days.append({
            'fb': fb, 'last': le, 'fh_end': fh_end,
            'prev_close': float(pc),
            'gap': float(o[fb] - pc),
            'weekend': bool(t[fb] - t[fb - 1] > 100000),
            'dow': int(dts[fb].dayofweek),
            'day_open': float(o[fb]), 'day_high': float(h[fb:le + 1].max()),
            'day_low': float(l[fb:le + 1].min()), 'day_close': float(c[le]),
        })
    return days


def daily_atr(days, period=14):
    """ATR(14) از OHLC روزانه؛ atr[k] = ATR تا پایانِ روزِ k (برای روزِ k+1 علّی است)."""
    n = len(days)
    tr = np.full(n, np.nan)
    for k in range(n):
        d = days[k]
        if k == 0:
            tr[k] = d['day_high'] - d['day_low']
        else:
            pc = days[k - 1]['day_close']
            tr[k] = max(d['day_high'] - d['day_low'],
                        abs(d['day_high'] - pc), abs(d['day_low'] - pc))
    atr = np.full(n, np.nan)
    for k in range(period - 1, n):
        atr[k] = tr[k - period + 1:k + 1].mean()
    return atr


def thresholds_for_day(days, atr, k, family, q_or_k):
    """آستانهٔ θ برای روزِ k — فقط از دادهٔ روزهای < k (علّی)."""
    if family == 'ATR':
        a = atr[k - 1] if k >= 1 else np.nan
        return q_or_k * a if np.isfinite(a) else np.nan
    if family == 'Q':
        lo = max(0, k - ROLL_DAYS)
        past = [abs(days[j]['gap']) for j in range(lo, k)]
        if len(past) < MIN_ROLL_OBS:
            return np.nan
        return float(np.percentile(past, q_or_k))
    if family == 'QW':
        want_wk = days[k]['weekend']
        lo = max(0, k - 2 * ROLL_DAYS)
        past = [abs(days[j]['gap']) for j in range(lo, k)
                if days[j]['weekend'] == want_wk]
        min_obs = MIN_ROLL_OBS if not want_wk else max(12, MIN_ROLL_OBS // 5)
        if len(past) < min_obs:
            return np.nan
        return float(np.percentile(past, q_or_k))
    raise ValueError(family)


# ─────────────────────────── شبیه‌سازِ event-driven ───────────────────────────

def sim_trade(arrays, day, atr_d, arm, k_sl=1.0):
    """یک معاملهٔ LONG از open بارِ اولِ روز. قراردادها = عینِ موتور."""
    o, h, l, c = arrays
    fb, last, fh_end = day['fb'], day['last'], day['fh_end']
    entry = o[fb]
    agap = abs(day['gap'])

    if arm == 'X-BAR':
        if not np.isfinite(atr_d) or atr_d <= 0:
            return None
        sl_price = entry - 1.0 * atr_d
        tp_price = np.inf
        end = fb + 1                       # فقط بارِ ورود (max_hold=1)
    elif arm == 'X-FILL':
        if agap <= 0:
            return None
        sl_price = entry - k_sl * agap
        tp_price = day['prev_close']       # پُرشدنِ گپ
        end = last + 1
    elif arm == 'X-LOW':
        if not np.isfinite(atr_d) or atr_d <= 0:
            return None
        sl_price = entry - 1.0 * atr_d     # حفاظتی در ساعتِ اول
        tp_price = np.inf
        end = last + 1
    else:
        raise ValueError(arm)

    outcome_price, exit_bar = None, None
    cur_sl = sl_price
    for j in range(fb, end):
        if arm == 'X-LOW' and j == fh_end + 1:
            # بعد از اتمامِ ساعتِ اول: استاپ = کفِ ساعتِ اول (علّی)
            fhl = l[fb:fh_end + 1].min()
            cur_sl = max(cur_sl, fhl)
        hit_sl = l[j] <= cur_sl
        hit_tp = np.isfinite(tp_price) and h[j] >= tp_price
        if hit_sl and hit_tp:
            outcome_price, exit_bar = cur_sl, j; break   # ابهام ⇒ بدترین
        elif hit_tp:
            outcome_price, exit_bar = tp_price, j; break
        elif hit_sl:
            outcome_price, exit_bar = cur_sl, j; break
    if outcome_price is None:
        exit_bar = end - 1
        outcome_price = c[exit_bar]

    pnl_pip = (outcome_price - entry) / PIP - SPREAD_PIP
    return {
        'signal_bar': fb - 1, 'entry_bar': fb, 'exit_bar': int(exit_bar),
        'direction': 'long', 'entry_price': float(entry),
        'exit_price': float(outcome_price),
        'outcome': 'win' if pnl_pip > 0 else 'loss',
        'pnl_pip': float(pnl_pip),
        'sl_pip': float((entry - sl_price) / PIP),
        'tp_pip': float((tp_price - entry) / PIP) if np.isfinite(tp_price) else float('nan'),
        'bars_held': int(exit_bar - fb),
        'dow': day['dow'], 'weekend': day['weekend'],
    }


# ─────────────────────────── فضای ترکیب‌ها ───────────────────────────

def combo_space():
    thr = ([('Q', q) for q in (60, 70, 80)] +
           [('QW', q) for q in (60, 70, 80)] +
           [('ATR', k) for k in (0.10, 0.15, 0.20)])
    arms = [('X-BAR', None), ('X-FILL', 1.0), ('X-FILL', 1.5), ('X-LOW', None)]
    return [(f, p, a, k) for (f, p) in thr for (a, k) in arms]   # 9×4=36؛ ×۲فیلتر=۷۲


def run_combo(arrays, days, atr, fam, par, arm, k_sl, lo_bar=None, hi_bar=None):
    """اجرای یک ترکیب. [lo_bar, hi_bar) بازهٔ مجازِ entry_bar."""
    trades = []
    for k, d in enumerate(days):
        if lo_bar is not None and d['fb'] < lo_bar:
            continue
        if hi_bar is not None and d['fb'] >= hi_bar:
            continue
        if not (d['gap'] < 0):
            continue                       # فقط gap-DOWN (پیش‌ثبت)
        th = thresholds_for_day(days, atr, k, fam, par)
        if not np.isfinite(th) or abs(d['gap']) <= th:
            continue
        atr_prev = atr[k - 1] if k >= 1 else np.nan
        tr = sim_trade(arrays, d, atr_prev, arm, k_sl if k_sl else 1.0)
        if tr is not None:
            trades.append(tr)
    return pd.DataFrame(trades)


def stats(tr):
    if len(tr) == 0:
        return dict(n=0, wr=np.nan, avg_doz=np.nan, net_doz=np.nan, pf=np.nan, t=np.nan)
    p = tr['pnl_pip'].values
    doz = p * PIP                          # دلار/اونس — قابلِ مقایسه با فاز۱۲
    wr = float((p > 0).mean())
    gp = doz[doz > 0].sum(); gl = -doz[doz <= 0].sum()
    pf = float(gp / gl) if gl > 0 else float('inf')
    sd = doz.std(ddof=1) if len(doz) > 1 else 0.0
    t = float(doz.mean() / (sd / np.sqrt(len(doz)))) if sd > 0 else 0.0
    return dict(n=int(len(tr)), wr=round(wr, 4), avg_doz=round(float(doz.mean()), 4),
                net_doz=round(float(doz.sum()), 2), pf=round(pf, 3), t=round(t, 3))


# ─────────────────────────── حالت‌ها ───────────────────────────

def mode_parity():
    """ممیزیِ برابری: X-BAR (آستانهٔ Q70) — شبیه‌سازِ من در برابرِ موتور. (پیش‌ثبت §۴.۳.۶)"""
    df = se.load_data('data/XAUUSD_M15.csv')
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    days = build_days(df)
    atr = daily_atr(days)
    mine = run_combo(arrays, days, atr, 'Q', 70, 'X-BAR', None, hi_bar=SPLIT_BAR['M15'])

    n = len(df)
    long_sig = np.zeros(n, bool)
    sl_arr = np.full(n, np.nan)
    for k, d in enumerate(days):
        if d['fb'] >= SPLIT_BAR['M15'] or not (d['gap'] < 0):
            continue
        th = thresholds_for_day(days, atr, k, 'Q', 70)
        if not np.isfinite(th) or abs(d['gap']) <= th:
            continue
        a = atr[k - 1] if k >= 1 else np.nan
        if not np.isfinite(a) or a <= 0:
            continue
        long_sig[d['fb'] - 1] = True
        sl_arr[d['fb'] - 1] = 1.0 * a / PIP
    eng = se.simulate_trades(df, long_sig, np.zeros(n, bool),
                             sl_pip=sl_arr, tp_pip=np.full(n, 1e9),
                             asset='XAUUSD', max_hold=1)
    print(f"mine n={len(mine)}  engine n={len(eng)}")
    if len(mine) != len(eng):
        print("❌ COUNT MISMATCH"); return 1
    a = mine.reset_index(drop=True); b = eng.reset_index(drop=True)
    eq_bar = (a['entry_bar'].values == b['entry_bar'].values).all() and \
             (a['exit_bar'].values == b['exit_bar'].values).all()
    dpnl = float(np.abs(a['pnl_pip'].values - b['pnl_pip'].values).max())
    print(f"bars identical: {eq_bar} · max |Δpnl_pip| = {dpnl:.10f}")
    ok = eq_bar and dpnl < 1e-9
    print("✅ PARITY OK" if ok else "❌ PARITY FAIL")
    return 0 if ok else 1


def mode_tune(tf='M15'):
    """تنظیم فقط روی نیمهٔ اول (entry_bar < split). ۷۲ ترکیب + چک‌پوینتِ JSON."""
    df = se.load_data(f'data/XAUUSD_{tf}.csv')
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    days = build_days(df)
    atr = daily_atr(days)
    split = SPLIT_BAR[tf]
    rows = []
    for (fam, par, arm, k_sl) in combo_space():
        base = run_combo(arrays, days, atr, fam, par, arm, k_sl, hi_bar=split)
        s0 = stats(base); s0.update(fam=fam, par=par, arm=arm, k_sl=k_sl, filt='NONE')
        rows.append(s0)
        drop, s1 = None, dict(n=0, wr=np.nan, avg_doz=np.nan, net_doz=np.nan, pf=np.nan, t=np.nan)
        if len(base) > 0:
            bydow = base.groupby('dow')['pnl_pip'].mean()
            if (bydow < 0).any():
                drop = int(bydow.idxmin())
                s1 = stats(base[base['dow'] != drop])
        s1.update(fam=fam, par=par, arm=arm, k_sl=k_sl, filt=f'DOW!={drop}')
        rows.append(s1)
    out = pd.DataFrame(rows)
    out.to_json(CKPT.format(tf=tf), orient='records', indent=1)
    ok = out[(out['n'] >= 100) & (out['pf'] > 1)]
    print(f"=== S400 tune {tf} (first half only, {len(out)} combos) ===")
    cols = ['fam', 'par', 'arm', 'k_sl', 'filt', 'n', 'wr', 'avg_doz', 'net_doz', 'pf', 't']
    print(out.sort_values('t', ascending=False)[cols].head(15).to_string(index=False))
    if len(ok) == 0:
        print("\n❌ NO COMBO QUALIFIES (n>=100 & PF>1) ⇒ prereg: REJECT بدونِ بازکردنِ holdout")
    else:
        w = ok.sort_values(['t', 'n'], ascending=False).iloc[0]
        print(f"\n🏆 WINNER (prereg rule): {w['fam']}{w['par']} · {w['arm']}"
              f" k_sl={w['k_sl']} · {w['filt']} · n={w['n']} t={w['t']} pf={w['pf']} wr={w['wr']}")
    return 0


def mode_verdict(tf='M15'):
    """آزمونِ رسمیِ یک‌بارهٔ RQS2 v2.6 — برندهٔ قفل‌شدهٔ فازِ تنظیم:
    QW60 · X-BAR · بدونِ فیلتر. کلِ داده + split_bar (الگوی استانداردِ repo:
    H7 نیمهٔ دوم را جدا می‌سنجد). null = ورودِ بی‌قید در *هر* بارِ اولِ روز با
    همان هندسه، K=500، seed=400 (پیش‌ثبت §۵)."""
    from engine import rqs2
    WIN_FAM, WIN_PAR, WIN_ARM, WIN_KSL = 'QW', 60, 'X-BAR', None   # قفل از step 4

    df = se.load_data(f'data/XAUUSD_{tf}.csv')
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    o, h, l, c = arrays
    days = build_days(df)
    atr = daily_atr(days)
    split = SPLIT_BAR[tf]
    bar_time = df['dt'].values
    close = c.astype('float64')

    # ---- معاملاتِ استراتژی روی کلِ داده ----
    strat = run_combo(arrays, days, atr, WIN_FAM, WIN_PAR, WIN_ARM, WIN_KSL)
    n_str = len(strat)
    print(f"strategy trades (full span) n={n_str} · holdout n="
          f"{int((strat['entry_bar'] >= split).sum())}", flush=True)

    # ---- استخرِ null: ورودِ بی‌قید در هر بارِ اولِ روزِ معتبر (بدونِ شرطِ گپ) ----
    pool = []
    for k, d in enumerate(days):
        a = atr[k - 1] if k >= 1 else np.nan
        if not np.isfinite(a) or a <= 0:
            continue
        tr = sim_trade(arrays, d, a, 'X-BAR')
        if tr is not None:
            pool.append(tr['pnl_pip'])
    pool = np.asarray(pool, dtype='float64')
    uncond_wr = float((pool > 0).mean() * 100.0)
    print(f"null pool = {len(pool)} unconditional first-bar longs · uncond_wr={uncond_wr:.2f}%", flush=True)

    rng = np.random.default_rng(SEED)
    K = 500
    wrs = np.empty(K)
    for i in range(K):
        pick = rng.choice(len(pool), size=n_str, replace=False)
        wrs[i] = (pool[pick] > 0).mean() * 100.0
    null = {'long': dict(uncond_wr=uncond_wr,
                         perm_mean=float(wrs.mean()), perm_sd=float(wrs.std(ddof=1)),
                         perm_max=float(wrs.max()), perm_k=int(K)),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    print(f"perm(K={K}): mean={wrs.mean():.2f} sd={wrs.std(ddof=1):.3f} max={wrs.max():.2f}", flush=True)

    # ---- tp_pip اندازه‌گیری‌شده: سقفِ عملیِ hold = میانهٔ (high−open) بارِ اولِ
    #      *بی‌قید* (نه انتخاب‌شده ⇒ ضدِ self-serving) ----
    fe = [(h[d['fb']] - o[d['fb']]) / PIP for d in days]
    tp_meas = float(np.median(fe))
    print(f"measured tp_pip (median uncond first-bar favorable excursion) = {tp_meas:.1f} pip", flush=True)

    r = rqs2.compute_rqs2(strat, 'XAUUSD',
                          sl_pip=float(np.median(strat['sl_pip'].values)),
                          tp_pip=tp_meas, bar_time=bar_time, null=null,
                          n_trials=72, split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S400 {tf} QW60/X-BAR', r), flush=True)
    outp = os.path.join(os.path.dirname(__file__), '..', 'results',
                        f'_s400_verdict_{tf}.json')
    with open(outp, 'w') as f:
        json.dump(r, f, indent=1, default=str)
    print(f"saved → {outp}", flush=True)
    return 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'tune'
    if mode == 'parity':
        sys.exit(mode_parity())
    elif mode == 'tune':
        sys.exit(mode_tune(sys.argv[2] if len(sys.argv) > 2 else 'M15'))
    elif mode == 'verdict':
        sys.exit(mode_verdict(sys.argv[2] if len(sys.argv) > 2 else 'M15'))
    else:
        print(__doc__); sys.exit(2)
