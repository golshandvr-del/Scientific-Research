#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S420 — Capitulation + Deceleration Swing (مأموریت ۳) · RQS2 v2.6
==================================================================
پیش‌ثبت: results/S420_PREREGISTRATION_CapitulationDecel.md (کامیت 05c6137b + ضمیمهٔ 72988742)

طرح (مسیر C معکوس):
  • پنجرهٔ کشف/تیون : 2020-01-01 → پایانِ داده (دادهٔ سوختهٔ فازهای ۱–۲۰)
  • پنجرهٔ تأیید بکر: ابتدای داده → 2019-12-31 (هرگز دیده‌نشده) — دقیقاً یک اجرا

قاعدهٔ سیگنال (روی روزهای معاملاتی ساخته‌شده از کندل‌های intraday):
  ret_5d < 0  ∧  vol_5d ≥ چارکِ q علّی  ∧  |ret_امروز| ≤ d × mean(|ret| دو روزِ قبل)
  ⇒ LONG در openِ اولین کندلِ روزِ بعد؛ خروجِ فقط-زمانی پس از hold روزِ معاملاتی؛
  بدونِ استاپِ قیمتی (براکتِ مجازیِ 5000 پیپ — هرگزفعال‌نشونده، راستی‌آزمایی می‌شود).

فضای کشف (تثبیت‌شده): q ∈ {0.70, 0.75} × d ∈ {1.25, 1.50} × hold ∈ {8, 10} = ۸ ترکیب
⇒ n_trials = 8

اجرا:
  python3 strategies/s420_capitulation_decel.py scan            # فقط پنجرهٔ کشف
  python3 strategies/s420_capitulation_decel.py lock q=.. d=.. hold=..   # قفلِ رسپی
  python3 strategies/s420_capitulation_decel.py confirm         # یک‌بار، پنجرهٔ بکر
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as rq                   # noqa: E402

# ------------------------------- ثابت‌های پیش‌ثبت -------------------------------
ASSET = 'XAUUSD'
DATA = 'data/XAUUSD_H1.csv'
SPLIT_UTC = pd.Timestamp('2020-01-01 00:00:00')   # مرزِ کشف/تأیید — تثبیت‌شده
W = 5                                             # پنجرهٔ روند/vol (ثابت)
VIRTUAL_BRACKET_PIP = 5000.0                      # ±۵۰۰$/oz — هرگزفعال‌نشونده
MIN_BARS_PER_DAY = 10                             # روزِ معتبرِ H1
GAP_MINUTES = 30                                  # anchorِ روزِ معاملاتی (نه hour==1!)
GRID_Q = (0.70, 0.75)
GRID_D = (1.25, 1.50)
GRID_HOLD = (8, 10)
N_TRIALS = len(GRID_Q) * len(GRID_D) * len(GRID_HOLD)   # = 8
NULL_K = 500
NULL_SEED = 42042
OUT_DIR = 'results/_scan_S420'
LOCK_PATH = os.path.join(OUT_DIR, 'S420_LOCKED_CONFIG.json')


# ------------------------------ روزهای معاملاتی ------------------------------
def build_trading_days(df):
    """تفکیکِ کندل‌های H1 به روزهای معاملاتی با anchorِ شکافِ زمانی > GAP_MINUTES.

    ❌ hour==1 هاردکد نمی‌شود (وقفهٔ XAUUSD در DSTِ مارسِ NY جابه‌جا می‌شود؛
    EURUSD اصلاً وقفه ندارد — آنجا شکافِ آخرِهفته روزها را می‌بُرد و درونِ هفته
    مرزِ تغییرِ تاریخِ UTC ملاک است).
    """
    t = df['time'].values.astype(np.int64)
    gap = np.diff(t)
    new_day = np.zeros(len(df), dtype=bool)
    new_day[0] = True
    # شروعِ روزِ جدید: شکاف > GAP_MINUTES یا تغییرِ تاریخِ UTC (برای بازارهای بی‌وقفه)
    dates = df['dt'].dt.date.values
    new_day[1:] = (gap > GAP_MINUTES * 60) | (dates[1:] != dates[:-1])
    day_id = np.cumsum(new_day) - 1

    days = []
    for did in range(day_id.max() + 1):
        idx = np.where(day_id == did)[0]
        if len(idx) < MIN_BARS_PER_DAY:
            continue
        days.append(dict(
            first_bar=int(idx[0]), last_bar=int(idx[-1]),
            n_bars=int(len(idx)),
            close=float(df['close'].values[idx[-1]]),
            date=df['dt'].iloc[idx[0]],
        ))
    return days


def daily_features(days):
    """بازده‌های log روزانه + روند/vol پنجرهٔ W (همه علّی)."""
    closes = np.array([d['close'] for d in days])
    rets = np.zeros(len(days))
    rets[1:] = np.log(closes[1:] / closes[:-1])
    trend = np.full(len(days), np.nan)
    vol = np.full(len(days), np.nan)
    for i in range(W, len(days)):
        w = rets[i - W + 1:i + 1]
        trend[i] = w.sum()
        vol[i] = w.std()
    return rets, trend, vol


def signal_days(days, rets, trend, vol, q, d):
    """اندیسِ روزهایی که سیگنال می‌دهند (سیگنال روی خودِ روزِ i؛ ورود روزِ i+1).

    آستانهٔ q **علّی**: چارک روی توزیعِ vol[W..i-1] — هیچ نگاهِ رو به جلو ندارد.
    تاریخچه از ابتدای *همان* پنجره ساخته می‌شود (ضدِ نشتِ اطلاعات بینِ پنجره‌ها).
    """
    sig = []
    for i in range(W + 2, len(days) - 1):          # i+1 باید وجود داشته باشد
        hist = vol[W:i]
        hist = hist[np.isfinite(hist)]
        if len(hist) < 60:                          # حداقلِ تاریخچه برای چارکِ معنادار
            continue
        thr = np.quantile(hist, q)
        if not (np.isfinite(trend[i]) and np.isfinite(vol[i])):
            continue
        decel = abs(rets[i]) <= d * np.mean(np.abs(rets[i - 2:i]))
        if trend[i] < 0 and vol[i] >= thr and decel:
            sig.append(i)
    return sig


# ------------------------------- اجرای معاملات -------------------------------
def run_trades(df, days, sig_idx, hold):
    """اجرای رسمی: برای هر سیگنال، یک فراخوانیِ simulate_trades با max_hold دقیقِ
    خودش (تعدادِ کندل تا آخرین کندلِ روزِ entry_day+hold−1). صفِ بی‌همپوشانی
    بیرونِ موتور با همان قاعدهٔ busy_until.
    """
    all_tr = []
    busy_until = -1
    for i in sig_idx:
        sig_bar = days[i]['last_bar']              # موتور در openِ کندلِ بعد وارد می‌شود
        entry_day = i + 1
        entry_bar = days[entry_day]['first_bar']
        if entry_bar != sig_bar + 1:
            # بینِ آخرین کندلِ روزِ سیگنال و اولین کندلِ روزِ بعد، کندلِ ناقص/روزِ
            # حذف‌شده وجود دارد ⇒ ورود دقیقاً همان openِ روزِ بعد نیست؛ برای صداقتِ
            # اجرا، سیگنال را روی کندلِ قبل از entry_bar می‌گذاریم.
            sig_bar = entry_bar - 1
        if entry_bar <= busy_until:
            continue                                # قاعدهٔ بی‌همپوشانی
        exit_day = min(entry_day + hold - 1, len(days) - 1)
        max_hold = days[exit_day]['last_bar'] - entry_bar + 1
        if max_hold < 1:
            continue
        ls = np.zeros(len(df), dtype=bool)
        ls[sig_bar] = True
        ss = np.zeros(len(df), dtype=bool)
        tr = se.simulate_trades(df, ls, ss, VIRTUAL_BRACKET_PIP, VIRTUAL_BRACKET_PIP,
                                ASSET, max_hold=max_hold, allow_overlap=False)
        if len(tr) == 0:
            continue
        row = tr.iloc[0]
        busy_until = int(row['exit_bar'])
        all_tr.append(tr)
    if not all_tr:
        return pd.DataFrame()
    return pd.concat(all_tr, ignore_index=True)


def verify_no_bracket_hits(trades, df):
    """راستی‌آزماییِ پیش‌ثبت: هیچ معامله‌ای نباید با SL/TP بسته شده باشد.
    معیار: exit_price باید دقیقاً closeِ exit_bar باشد (مسیرِ time-exit موتور)."""
    c = df['close'].values
    hits = 0
    for _, r in trades.iterrows():
        if abs(float(r['exit_price']) - float(c[int(r['exit_bar'])])) > 1e-9:
            hits += 1
    return hits


# --------------------------------- مدلِ صفر ---------------------------------
def build_null(df, days, n_entries, hold, lo_day, hi_day, K=NULL_K, seed=NULL_SEED):
    """جای‌گشتِ زمانی: n ورودِ LONG در روزهای تصادفیِ [lo_day, hi_day)، همان hold،
    همان هزینه، همان صفِ بی‌همپوشانی. مسیرِ سریعِ pnl (پیش‌ثبت، ضمیمهٔ بندِ ۳):
      pnl_pip = (close_exit − open_entry)/pip − spread  (slip=0 برای XAUUSD)
    که *هم‌ارزِ دقیقِ* مسیرِ time-exit موتور است (روی معاملاتِ واقعی تست می‌شود).
    """
    cfg = se.ASSETS[ASSET]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    o = df['open'].values
    c = df['close'].values
    rng = np.random.default_rng(seed)
    candidates = np.arange(lo_day, hi_day - hold - 1)
    wrs = []
    for _ in range(K):
        picks = np.sort(rng.choice(candidates, size=min(n_entries * 3, len(candidates)),
                                   replace=False))
        wins = tot = 0
        busy = -1
        for i in picks:
            if tot >= n_entries:
                break
            eb = days[i + 1]['first_bar']
            if eb <= busy:
                continue
            xd = min(i + 1 + hold - 1, len(days) - 1)
            xb = days[xd]['last_bar']
            fill = o[eb] + slip * pip
            pnl = (c[xb] - slip * pip - fill) / pip - spread
            wins += int(pnl > 0)
            tot += 1
            busy = xb
        if tot > 0:
            wrs.append(wins / tot * 100.0)
    wrs = np.array(wrs)
    side = dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=len(wrs))
    return {'long': side, 'short': dict(side)}


# --------------------------------- پنجره‌ها ---------------------------------
def windows(days):
    """(lo, hi) اندیسِ روز برای پنجرهٔ کشف و تأیید."""
    split_day = next(i for i, d in enumerate(days) if d['date'] >= SPLIT_UTC)
    return dict(confirm=(0, split_day), discover=(split_day, len(days)))


def run_combo(df, days, rets, trend, vol, q, d, hold, lo, hi):
    sig = [i for i in signal_days(days, rets, trend, vol, q, d) if lo <= i < hi - hold - 1]
    trades = run_trades(df, days, sig, hold)
    if len(trades) == 0:
        return None, trades
    pnl = trades['pnl_pip'].values
    n = len(trades)
    wr = float((pnl > 0).mean() * 100)
    exp = float(pnl.mean())
    t = exp / (pnl.std(ddof=1) / np.sqrt(n)) if n > 2 and pnl.std(ddof=1) > 0 else 0.0
    return dict(q=q, d=d, hold=hold, n=n, wr=wr, exp_pip=exp, t=float(t),
                net_pip=float(pnl.sum())), trades


# ----------------------------------- CLI -----------------------------------
def cmd_scan():
    """جست‌وجوی ۸-ترکیبی — فقط پنجرهٔ کشف. انتخاب طبقِ بندِ ۴.۱ پیش‌ثبت."""
    df = se.load_data(DATA)
    days = build_trading_days(df)
    rets, trend, vol = daily_features(days)
    lo, hi = windows(days)['discover']
    print(f"[scan] discover window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    cfg = se.ASSETS[ASSET]
    rows = []
    for q in GRID_Q:
        for d in GRID_D:
            for hold in GRID_HOLD:
                r, trades = run_combo(df, days, rets, trend, vol, q, d, hold, lo, hi)
                if r is None:
                    print(f"  q={q} d={d} hold={hold}: no trades")
                    continue
                # WR نال ~۵۰٪ نیست الزاماً؛ برای lift·√n از مبنای تقریبیِ ۵۰ در scan
                # استفاده نمی‌کنیم — مبنای واقعی فقط در confirm ساخته می‌شود.
                # معیارِ انتخابِ پیش‌ثبت: بیشینهٔ (wr−50)·√n مشروط exp>0, n≥30.
                r['lift_sqrt_n_proxy'] = (r['wr'] - 50.0) * np.sqrt(r['n'])
                hits = verify_no_bracket_hits(trades, df)
                r['bracket_hits'] = hits
                rows.append(r)
                print(f"  q={q} d={d} hold={hold}: n={r['n']:3d} WR={r['wr']:5.1f}% "
                      f"exp={r['exp_pip']:+7.1f}pip t={r['t']:+5.2f} "
                      f"net={r['net_pip']:+9.0f}pip proxy={r['lift_sqrt_n_proxy']:+6.1f} "
                      f"bracket_hits={hits}")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'S420_scan_discover.json')
    with open(out, 'w') as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    print(f"[scan] saved → {out}")


def cmd_lock(q, d, hold):
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = dict(strategy='S420_CapitulationDecel', asset=ASSET, data=DATA,
               W=W, q=q, d=d, hold=hold, direction='long_only',
               bracket_pip=VIRTUAL_BRACKET_PIP, n_trials=N_TRIALS,
               split_utc=str(SPLIT_UTC), confirm_window='data_start→2019-12-31',
               discover_window='2020-01-01→data_end',
               prereg='results/S420_PREREGISTRATION_CapitulationDecel.md')
    with open(LOCK_PATH, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    print(f"[lock] config frozen → {LOCK_PATH}")
    print(json.dumps(cfg, indent=1, ensure_ascii=False))


def cmd_confirm():
    """اجرای یگانهٔ RQS2 روی پنجرهٔ بکر — فقط با کانفیگِ قفل‌شده."""
    with open(LOCK_PATH) as f:
        cfg = json.load(f)
    q, d, hold = cfg['q'], cfg['d'], cfg['hold']
    df = se.load_data(DATA)
    days = build_trading_days(df)
    rets, trend, vol = daily_features(days)
    lo, hi = windows(days)['confirm']
    print(f"[confirm] VIRGIN window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    print(f"[confirm] locked config: q={q} d={d} hold={hold}")
    r, trades = run_combo(df, days, rets, trend, vol, q, d, hold, lo, hi)
    if r is None:
        print("[confirm] NO TRADES — verdict is INCOMPLETE/REJECT by n")
        return
    hits = verify_no_bracket_hits(trades, df)
    print(f"[confirm] n={r['n']} WR={r['wr']:.1f}% exp={r['exp_pip']:+.1f}pip "
          f"t={r['t']:+.2f} net={r['net_pip']:+.0f}pip bracket_hits={hits}")
    assert hits == 0, "bracket was hit — prereg verification FAILED"

    # مدلِ صفر روی *همان* پنجرهٔ بکر
    null = build_null(df, days, r['n'], hold, lo, hi)
    print(f"[confirm] null: mean={null['long']['perm_mean']:.2f}% "
          f"sd={null['long']['perm_sd']:.2f} max={null['long']['perm_max']:.2f} "
          f"k={null['long']['perm_k']}")

    # H7: تقسیمِ درون-پنجره‌ایِ ۶۰/۴۰ روی خودِ پنجرهٔ بکر (زمانی)
    split_bar = days[lo + int((hi - lo) * 0.60)]['first_bar']

    res = rq.compute_rqs2(
        trades, ASSET,
        sl_pip=VIRTUAL_BRACKET_PIP, tp_pip=VIRTUAL_BRACKET_PIP,
        bar_time=df['time'].values, null=null, n_trials=N_TRIALS,
        split_bar=split_bar, close=df['close'].values,
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'S420_confirm_virgin_rqs2.json')

    def _clean(x):
        if isinstance(x, dict):
            return {k: _clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [_clean(v) for v in x]
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, (np.bool_,)):
            return bool(x)
        return x

    with open(out, 'w') as f:
        json.dump(_clean(dict(result=res, headline=r, null=null)), f,
                  indent=1, ensure_ascii=False)
    print(f"[confirm] verdict = {res['verdict']}  score = {res['rqs2_score']}")
    print(f"[confirm] gates: {res['gates']}")
    print(f"[confirm] saved → {out}")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    if mode == 'scan':
        cmd_scan()
    elif mode == 'lock':
        kv = dict(a.split('=') for a in sys.argv[2:])
        cmd_lock(float(kv['q']), float(kv['d']), int(kv['hold']))
    elif mode == 'confirm':
        cmd_confirm()
    else:
        raise SystemExit(f"unknown mode {mode!r}")
