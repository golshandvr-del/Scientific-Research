# -*- coding: utf-8 -*-
"""
S363 — بازداوریِ صادقانهٔ لایهٔ **S327 (Brooks Sell-Climax Exhaustion Reversal)**
با موتورِ RQS2 v2.4
==============================================================================

پیش‌ثبت: `results/S363_PREREGISTRATION_S327_V24_REJUDGE.md`
(commitِ جداگانه، **پیش از** اجرای این اسکریپت).

چرا این اسکریپت لازم است
------------------------
پنج کارتِ سایت لایهٔ `S327` را اجرا می‌کنند و نمرهٔ ادعاییِ آن (`RQS+ = 97.6`)
بالاترین نمرهٔ کلِ پروژه است. ولی `RQS+` سه سنجهٔ حاکمِ امروز را نداشت — `H3`
(مدلِ صفرِ اندازه‌گیری‌شده)، `H5` (جریمهٔ چندگانگی) و `H10` (مقاومتِ رژیمی) — و
مهم‌تر از آن، **موتورِ داوریِ آرشیو با `tp_pip = sl_pip` تغذیه شده بود** (در هر ۷
رکورد بیت‌به‌بیت برابر است) درحالی‌که هندسهٔ واقعیِ معامله‌ها نامتقارن است. پس
سربه‌سرِ ۵۰٪ فرض شده بود، نه سربه‌سرِ واقعیِ ۷۳–۷۹٪.

⇒ وضعیتِ `S327` زیرِ معیارِ حاکم **«آزموده‌نشده»** است، نه «پاس».

سه تصمیمِ مهندسیِ این اسکریپت
-----------------------------
**۱) منطقِ سیگنال از خودِ کدِ آرشیو `import` می‌شود، بازنویسی نمی‌شود.**
   `build_features` و `make_signals` عیناً از
   `strategies/s327_sell_climax_reversal_rqs.py` صدا زده می‌شوند. پس برابری با
   منطقِ ثبت‌شده **به‌حکمِ ساخت** تضمین است و نیازی به `parity_check` نیست. این
   انتخاب عمدی است: هر بازنویسی‌ای یک درجهٔ آزادیِ نو برای اشتباه می‌سازد.

**۲) جدولِ برآمدِ برداری با هندسهٔ *آرایه‌ای*.** براکتِ `S327` بر حسبِ `ATR` است،
   پس `sl_pip`/`tp_pip` آرایه‌اند نه اسکالر. معناشناسی عیناً از
   `se.simulate_trades` کپی شده، از جمله این جزئیاتِ حیاتی:
     · `sl_d = sl_pip[si] * pip` — نمایه‌گذاری با **کندلِ سیگنال** `si`، نه ورود.
     · ورود در `open[si+1]` با اسلیپیج.
     · ابهامِ هم‌زمانِ SL/TP در یک کندل ⇒ **باخت** (محافظه‌کارانه).
     · خروجِ زمانی روی `close`، و برچسبِ برد/باخت از **علامتِ `pnl_pip`**.
   یک `parity_table_vs_engine` روی هر کارت اثبات می‌کند `WR`ِ جدول با `WR`ِ موتور
   یکی است؛ اگر نبود، اسکریپت **می‌شکند** و داوری نمی‌کند.

**۳) دو p-value، و پاس نیازِ *هر دو*.** `p` پارامتریکِ موتور و `p` تجربیِ شمارشیِ
   `(1+#{≥obs})/(1+K)`. لایه نمی‌تواند از راهِ تفاوتِ دو خط‌کش خریده شود.

اجرا:
    python3 strategies/s363_s327_v24_rejudge.py --cards site   # ۵ کارتِ سایت
    python3 strategies/s363_s327_v24_rejudge.py --cards all    # هر کارتِ دارای داده
    python3 strategies/s363_s327_v24_rejudge.py --cards XAUUSD-M5
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                    # noqa: E402
from engine import rqs2 as R2                                            # noqa: E402
from strategies.s327_sell_climax_reversal_rqs import (                   # noqa: E402
    build_features, make_signals)

OUT = "results/_scan_S363"

# ───────────────── پارامترهای آماریِ پیش‌ثبت‌شده (بندِ ۶ پیش‌ثبت) ─────────────────
SEEDS = (23, 101, 777)
PERM_K = 2000
P_BAR = 0.001
SPLIT_FRAC = 0.60

# ─────────── گریدِ آرشیو، عیناً از s327_sell_climax_reversal_rqs.py::scan ───────────
G_KBODY = [1.6, 2.0, 2.5]
G_BRMIN = [0.0, 0.45, 0.6]
G_STREAK = [0, 2, 3]
G_RSI = [None, 42, 35, 30]
G_REGIME = [None, 'below', 'bb', 'trend']
G_SLTP = [(2.4, 0.8), (2.8, 1.0), (3.1, 1.15), (2.0, 0.7), (3.5, 1.3)]
G_HOLD = [16, 24, 48]

N_SIGNAL_COLUMNS = len(G_KBODY) * len(G_BRMIN) * len(G_STREAK) * len(G_RSI) * len(G_REGIME)
N_BRACKETS = len(G_SLTP) * len(G_HOLD)
N_TRIALS_HONEST = N_SIGNAL_COLUMNS * N_BRACKETS            # 432 × 15 = 6,480
N_TRIALS_M30 = N_TRIALS_HONEST + 72 * 32                   # + اسکنرِ دومِ s327b = 8,784
N_TRIALS_STRESS = N_TRIALS_HONEST * 8                      # ۸ ترکیبِ (دارایی×TF) = 51,840

# ── پیکربندیِ منجمدِ آرشیو (جدولِ §۳ سندِ S327) — هیچ‌کدام در این نشست جست‌وجو نشد ──
ARCHIVE_CFG = {
    'XAUUSD-M5':  dict(k_body=1.6, br_min=0.60, streak_n=2, rsi_lo=30, regime='trend',
                       sl_m=3.5, tp_m=1.30, hold=24),
    'XAUUSD-M15': dict(k_body=2.5, br_min=0.45, streak_n=3, rsi_lo=35, regime='trend',
                       sl_m=2.8, tp_m=1.00, hold=16),
    'XAUUSD-M30': dict(k_body=2.5, br_min=0.45, streak_n=2, rsi_lo=35, regime='trend',
                       sl_m=2.4, tp_m=1.00, hold=16),
    'XAUUSD-H1':  dict(k_body=1.6, br_min=0.60, streak_n=3, rsi_lo=42, regime='trend',
                       sl_m=2.8, tp_m=1.00, hold=48),
    'XAUUSD-H4':  dict(k_body=2.5, br_min=0.60, streak_n=0, rsi_lo=35, regime='trend',
                       sl_m=3.5, tp_m=1.30, hold=24),
    'EURUSD-M15': dict(k_body=2.0, br_min=0.60, streak_n=3, rsi_lo=30, regime='trend',
                       sl_m=3.1, tp_m=1.15, hold=16),
    'EURUSD-M30': dict(k_body=1.6, br_min=0.60, streak_n=2, rsi_lo=30, regime='trend',
                       sl_m=2.0, tp_m=0.70, hold=16),
}

SITE_CARDS = ["XAUUSD-M5", "XAUUSD-M30", "XAUUSD-H1", "XAUUSD-H4", "EURUSD-M30"]
ARCHIVE_ONLY_CARDS = ["XAUUSD-M15", "EURUSD-M15"]

# قانونِ MTF: هر کارتی که داده دارد. `XAUUSD-M1` داده ندارد ⇒ `NO_DATA`ِ صریح
# (حذفِ خاموش همان اشتباهِ رایجِ #۵ است).
CARDS_ALL = SITE_CARDS + ARCHIVE_ONLY_CARDS + [
    "XAUUSD-M1", "XAUUSD-D1", "XAUUSD-W1",
    "EURUSD-M1", "EURUSD-M5", "EURUSD-H1", "EURUSD-H4", "EURUSD-D1", "EURUSD-W1",
]

# قاعدهٔ مشتقِ پیش‌ثبت‌شده برای کارت‌های آزموده‌نشده (بندِ ۷ پیش‌ثبت): میانهٔ
# پارامترهای اندازه‌گیری‌شدهٔ خودِ آرشیو، بدونِ هیچ جست‌وجو ⇒ n_trials = 1.
DERIVED_CFG = dict(k_body=2.0, br_min=0.60, streak_n=2, rsi_lo=35, regime='trend',
                   sl_m=2.8, tp_m=1.00, hold=16)


# ══════════════════════ ۱. هندسهٔ ATR-محور (آرایه‌ای) ══════════════════════
def geometry(feat, asset, sl_m, tp_m):
    """آرایهٔ `sl_pip`/`tp_pip` بر حسبِ ATRِ همان کندلِ سیگنال — عیناً روشِ آرشیو."""
    pip = se.ASSETS[asset]['pip']
    atr = feat['atr']
    atr_pip = np.where(np.isfinite(atr) & (atr > 0), atr / pip, np.nan)
    sl = np.where(np.isfinite(atr_pip), sl_m * atr_pip, 1.0)
    tp = np.where(np.isfinite(atr_pip), tp_m * atr_pip, 1.0)
    return sl, tp, atr_pip


def signal_of(feat, cfg, asset):
    """سیگنالِ آرشیو + قیدِ اعتبارِ ATR (عیناً `valid_sig` در `scan`)."""
    _, _, atr_pip = geometry(feat, asset, cfg['sl_m'], cfg['tp_m'])
    sig = make_signals(feat, cfg['k_body'], cfg['br_min'], cfg['streak_n'],
                       cfg['rsi_lo'], cfg['regime'], feat['atr'], feat['c'])
    return sig & np.isfinite(atr_pip) & (atr_pip > 0)


# ══════════════════════════ ۲. جدولِ برآمدِ برداری ══════════════════════════
def outcome_table(df, asset, sl_arr, tp_arr, mh, side='long'):
    """برآمدِ یک ورود در **هر** کندل، با معناشناسیِ دقیقِ `se.simulate_trades`.

    تفاوتِ کلیدی با نسخهٔ S357: `sl_arr`/`tp_arr` **آرایه**‌اند و با **کندلِ
    سیگنال** نمایه‌گذاری می‌شوند (`sl_d = sl_pip[si]*pip`)، چون براکتِ S327
    ATR-محور است.

    خروجی: `res` (۱=برد، −۱=باخت، ۰=غیرقابلِ‌ورود) و `xbar` (کندلِ خروج).
    """
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = cfg['pip']
    spread = float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))

    sl_d = np.asarray(sl_arr, float) * pip
    tp_d = np.asarray(tp_arr, float) * pip

    eb = np.arange(n) + 1
    live = (eb < n) & np.isfinite(sl_d) & (sl_d > 0) & np.isfinite(tp_d)
    ebc = np.minimum(eb, n - 1)
    if side == 'long':
        fill = o[ebc] + slip * pip
        sl_price, tp_price = fill - sl_d, fill + tp_d
    else:
        fill = o[ebc] - slip * pip
        sl_price, tp_price = fill + sl_d, fill - tp_d

    res = np.zeros(n, dtype=np.int8)
    xbar = np.full(n, -1, dtype=np.int64)
    for j in range(mh):
        k = eb + j
        openslot = live & (res == 0) & (k < n)
        if not openslot.any():
            break
        kk = np.minimum(k, n - 1)
        if side == 'long':
            hit_sl = l[kk] <= sl_price
            hit_tp = h[kk] >= tp_price
        else:
            hit_sl = h[kk] >= sl_price
            hit_tp = l[kk] <= tp_price
        loss = openslot & hit_sl           # ابهامِ هم‌زمان ⇒ باخت
        win = openslot & hit_tp & ~hit_sl
        res[loss] = -1
        xbar[loss] = k[loss]
        res[win] = 1
        xbar[win] = k[win]

    kend = np.minimum(eb + mh, n)
    to = live & (res == 0) & (kend > eb)
    if to.any():
        last = c[np.maximum(kend - 1, 0)]
        if side == 'long':
            pnl = (last - slip * pip - fill) / pip - spread
        else:
            pnl = (fill - last - slip * pip) / pip - spread
        res[to] = np.where(pnl[to] > 0, 1, -1)
        xbar[to] = kend[to] - 1
    return res, xbar


def wr_of(picks, res, xbar):
    """WRِ یک مجموعهٔ ورود با قاعدهٔ ناهم‌پوشانیِ موتور (`entry_bar > busy_until`)."""
    wins = used = 0
    last_exit = -1
    for si in picks:
        if si + 1 <= last_exit or res[si] == 0:
            continue
        used += 1
        last_exit = xbar[si]
        if res[si] == 1:
            wins += 1
    return (100.0 * wins / used) if used else None


# ═════════════════════════ ۳. مدلِ صفر + p تجربی ═════════════════════════
def build_null(df, asset, k_sig, sl_arr, tp_arr, mh, k_perm, seed, side='long'):
    """مدلِ صفرِ **هم‌هندسه**: همان براکت، همان تعدادِ رویداد، زمان‌بندیِ تصادفی.

    ⚠️ قیدِ ضدِتقلبِ بندِ ۶ پیش‌ثبت: نول برای **همان** هندسه ساخته می‌شود. مقایسهٔ
    `WR`ِ یک هندسه با نولِ هندسهٔ دیگر مکانیکاً لیفتِ کاذب می‌سازد.
    """
    res, xbar = outcome_table(df, asset, sl_arr, tp_arr, mh, side=side)
    n = len(df)
    lo = min(300, max(0, n // 10))
    valid = np.arange(lo, max(lo + 1, n - mh - 2))
    valid = valid[res[valid] != 0]
    uncond = wr_of(valid, res, xbar)

    rng = np.random.default_rng(seed)
    draws = []
    k = min(k_sig, valid.size)
    for _ in range(k_perm):
        pick = np.sort(rng.choice(valid, size=k, replace=False))
        w = wr_of(pick, res, xbar)
        if w is not None:
            draws.append(w)
    draws = np.asarray(draws, dtype=float)
    side_null = dict(uncond_wr=uncond, perm_mean=float(draws.mean()),
                     perm_sd=float(draws.std(ddof=1)), perm_max=float(draws.max()),
                     perm_k=int(draws.size))
    zero = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=0)
    other = 'short' if side == 'long' else 'long'
    return {side: side_null, other: zero}, draws


def empirical_p(draws, wr_obs):
    """p یک‌طرفهٔ تجربی با برآوردگرِ محافظه‌کارانهٔ `(1+#{≥obs})/(1+K)`.

    عددِ `+1` استانداردِ مونت‌کارلو است (Davison & Hinkley 1997) و از گزارشِ
    `p = 0` که با نمونهٔ متناهی هرگز اثبات‌شدنی نیست جلوگیری می‌کند.
    """
    ge = int((draws >= wr_obs - 1e-12).sum())
    return (1.0 + ge) / (1.0 + len(draws)), ge


# ═════════════════════ ۴. اندازه‌گیریِ N_eff از خودِ گرید ═════════════════════
def measure_neff(feat, asset, verbose=True):
    """`N_eff` از ساختارِ همبستگیِ **۴۳۲ ستونِ سیگنالِ** گریدِ آرشیو.

    براکت‌ها (`sl_m×tp_m×hold`) سیگنال را عوض نمی‌کنند، پس ضربِ `× N_BRACKETS`
    **بدونِ** اندازه‌گیری اعمال می‌شود (محافظه‌کارانه: فرضِ استقلالِ کاملِ براکت‌ها).

    ⚠️ هیچ نمونه‌گیریِ سطری انجام نمی‌شود. روی سیگنالِ تُنُک، نمونه‌گیریِ سطری
    واریانسِ ستون‌ها را به صفر می‌برد و جریمهٔ چندگانگی را مصنوعاً حذف می‌کند —
    همان تلهٔ ثبت‌شده در `measure_neff` نشستِ S357.
    """
    _, _, atr_pip = geometry(feat, asset, 1.0, 1.0)
    ok = np.isfinite(atr_pip) & (atr_pip > 0)
    cols = []
    for k_body, br_min, streak_n, rsi_lo, regime in itertools.product(
            G_KBODY, G_BRMIN, G_STREAK, G_RSI, G_REGIME):
        s = make_signals(feat, k_body, br_min, streak_n, rsi_lo, regime,
                         feat['atr'], feat['c']) & ok
        cols.append(s)
    X = np.asarray(cols, dtype=np.float64).T          # (bars, 432)
    n_cols = X.shape[1]
    var = X.var(axis=0)
    keep = var > 1e-12
    m_used = int(keep.sum())
    if m_used < 2:
        m_eff = float(max(m_used, 1))
    else:
        m_eff = float(R2.effective_trials(X[:, keep]))
    n_eff = m_eff * N_BRACKETS
    if verbose:
        print(f"    N_eff: {n_cols} signal columns, {m_used} with variance, "
              f"m_eff={m_eff:.2f} × {N_BRACKETS} brackets = {n_eff:.1f}", flush=True)
    return n_eff, m_eff, n_cols, m_used


# ═══════════════════════════ ۵. اجرا برای یک کارت ═══════════════════════════
def resolve_cfg(card):
    if card in ARCHIVE_CFG:
        nt = N_TRIALS_M30 if card == 'XAUUSD-M30' else N_TRIALS_HONEST
        return dict(ARCHIVE_CFG[card]), 'ARCHIVE', nt, N_TRIALS_STRESS
    return dict(DERIVED_CFG), 'DERIVED', 1, 1


def run_card(card, do_neff=True, verbose=True):
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return dict(card=card, status='NO_DATA',
                    note=f'{path} does not exist in the repository')
    df = se.load_data(path)
    cfg, source, nt_honest, nt_stress = resolve_cfg(card)
    feat = build_features(df, asset)
    sl_arr, tp_arr, _ = geometry(feat, asset, cfg['sl_m'], cfg['tp_m'])
    sig = signal_of(feat, cfg, asset)
    n_sig = int(sig.sum())

    rr = cfg['tp_m'] / cfg['sl_m']
    reach_tp = (cfg['sl_m'] * rr) ** 2
    reach_sl = cfg['sl_m'] ** 2

    rec = dict(card=card, asset=asset, tf=tf, cfg_source=source, cfg=dict(cfg),
               bars=len(df), n_signals=n_sig, rr=round(rr, 4),
               # قانونِ دسترسی‌پذیریِ سد — docs/FINDING_BARRIER_REACHABILITY_LAW.md
               reachability=dict(hold=cfg['hold'],
                                 tp_bars_needed=round(reach_tp, 2),
                                 sl_bars_needed=round(reach_sl, 2),
                                 tp_reachable=bool(cfg['hold'] >= reach_tp),
                                 sl_reachable=bool(cfg['hold'] >= reach_sl)),
               seeds={})
    if verbose:
        print(f"\n=== {card} :: source={source} bars={len(df)} "
              f"sl={cfg['sl_m']}×ATR tp={cfg['tp_m']}×ATR RR={rr:.3f} "
              f"hold={cfg['hold']} | signals={n_sig}", flush=True)

    if n_sig < 5:
        rec['status'] = 'NO_SIGNAL'
        return rec

    zero = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, zero, sl_pip=sl_arr, tp_pip=tp_arr,
                            asset=asset, max_hold=cfg['hold'], allow_overlap=False)
    if tr is None or len(tr) < 5:
        rec['status'] = 'NO_TRADES'
        return rec
    n = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / n

    # اسکالرهای هندسه برای موتورِ داوری: میانهٔ **همان معاملاتِ واقعی**.
    # ⚠️ این همان نقطه‌ای است که آرشیو `tp_pip` را نداد و موتور `tp=sl` فرض کرد.
    sb = tr['signal_bar'].to_numpy(int)
    sl_med = float(np.median(sl_arr[sb]))
    tp_med = float(np.median(tp_arr[sb]))
    rec.update(status='JUDGED', n_trades=n, wr_obs=round(wr_obs, 3),
               sl_pip_median=round(sl_med, 3), tp_pip_median=round(tp_med, 3),
               rr_realised=round(tp_med / sl_med, 4))

    # سربه‌سرِ واقعی در برابرِ سربه‌سرِ ساختگیِ آرشیو (`tp=sl`)
    cost = float(se.ASSETS[asset]['spread_pip']) + 2.0 * float(se.ASSETS[asset].get('slip_pip', 0.0))
    be_true = R2.breakeven_wr_cost(sl_med, tp_med, cost)
    be_archive = R2.breakeven_wr_cost(sl_med, sl_med, cost)
    rec['breakeven'] = dict(cost_pip=cost,
                            be_true_pct=None if be_true is None else round(be_true, 3),
                            be_archive_assumed_pct=None if be_archive is None else round(be_archive, 3),
                            excess_true_pp=None if be_true is None else round(wr_obs - be_true, 3),
                            excess_archive_pp=None if be_archive is None else round(wr_obs - be_archive, 3))

    # اثباتِ اپل‌به‌اپل بودنِ جدولِ برآمد با موتور (پیش از استفاده در نول)
    res_chk, xb_chk = outcome_table(df, asset, sl_arr, tp_arr, cfg['hold'])
    wr_tbl = wr_of(np.flatnonzero(sig), res_chk, xb_chk)
    rec['parity_table_vs_engine'] = dict(
        wr_engine=round(wr_obs, 3),
        wr_table=None if wr_tbl is None else round(wr_tbl, 3))
    if wr_tbl is None or abs(wr_tbl - wr_obs) > 0.51:
        raise AssertionError(
            f"{card}: the vectorised outcome table disagrees with the engine "
            f"(WR {wr_tbl} vs {wr_obs}). Refusing to build a null model on a "
            f"table that does not reproduce the engine's own trades.")
    if verbose:
        print(f"    n_trades={n} WR={wr_obs:.2f}% (table {wr_tbl:.2f}%) "
              f"| be_true={be_true:.2f}% be_archive_assumed={be_archive:.2f}% "
              f"| excess_true={wr_obs - be_true:+.2f}pp", flush=True)

    n_eff = float(nt_honest)
    if do_neff and source == 'ARCHIVE':
        n_eff, m_eff, n_cols, m_used = measure_neff(feat, asset, verbose=verbose)
        rec['neff'] = dict(n_eff=round(n_eff, 1), m_eff_signal=round(m_eff, 2),
                           n_signal_columns=n_cols, m_with_variance=m_used,
                           method='exact_phi_correlation',
                           bracket_multiplier=N_BRACKETS)
    else:
        rec['neff'] = dict(n_eff=n_eff, note='derived card: no selection ⇒ N=1')

    close = df['close'].to_numpy(float)
    bar_time = df['time'].to_numpy()
    split_bar = int(len(df) * SPLIT_FRAC)
    labels = (('neff', n_eff), ('honest', nt_honest), ('stress', nt_stress))

    for seed in SEEDS:
        null, draws = build_null(df, asset, n_sig, sl_arr, tp_arr, cfg['hold'],
                                 PERM_K, seed)
        p_emp, n_ge = empirical_p(draws, wr_obs)
        out = {}
        for label, nt in labels:
            r = R2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                                bar_time=bar_time, close=close, null=null,
                                n_trials=int(round(nt)), split_bar=split_bar)
            out[label] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                              rank=r.get('rank'), gates=r.get('gates'),
                              metrics=r.get('metrics'), notes=r.get('notes'))
        m0 = out['neff']['metrics']
        out['null'] = {k: null['long'][k] for k in
                       ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')}
        out['p_empirical'] = round(p_emp, 6)
        out['n_draws_ge_obs'] = n_ge
        out['p_parametric_engine'] = m0.get('skill_p_perm')
        out['honest_accept'] = bool(out['neff']['verdict'] == 'ACCEPT'
                                    and out['honest']['verdict'] == 'ACCEPT'
                                    and p_emp <= P_BAR)
        rec['seeds'][str(seed)] = out
        if verbose:
            print(f"  seed={seed} K={out['null']['perm_k']} | uncond="
                  f"{out['null']['uncond_wr']:.2f}% perm_mean="
                  f"{out['null']['perm_mean']:.2f}% sd={out['null']['perm_sd']:.2f} "
                  f"| lift={m0.get('skill_lift_pp')}pp z={m0.get('skill_z')}", flush=True)
            for label, _ in labels:
                bad = [g for g, v in (out[label]['gates'] or {}).items() if v is not True]
                print(f"      {label:6s}: {out[label]['verdict']:11s} "
                      f"score={out[label]['score']} failing={bad or 'NONE'}", flush=True)
            print(f"      p_emp={p_emp:.6f} ({n_ge}/{out['null']['perm_k']} ≥ obs) "
                  f"p_param={out['p_parametric_engine']} "
                  f"HONEST_ACCEPT={out['honest_accept']}", flush=True)

    verds = {s: v['neff']['verdict'] for s, v in rec['seeds'].items()}
    rec['honest'] = dict(
        seed_stable=len(set(verds.values())) == 1,
        verdicts_neff=verds,
        verdicts_honest={s: v['honest']['verdict'] for s, v in rec['seeds'].items()},
        verdicts_stress={s: v['stress']['verdict'] for s, v in rec['seeds'].items()},
        all_seeds_honest_accept=all(v['honest_accept'] for v in rec['seeds'].values()),
        decision='ALIVE' if all(v['honest_accept'] for v in rec['seeds'].values())
                 else 'NOT_ALIVE_UNDER_FROZEN_CFG',
    )
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='site',
                    help="'site' | 'all' | 'archive' | یک کارت مثل XAUUSD-M5")
    ap.add_argument('--no-neff', action='store_true')
    args = ap.parse_args()

    if args.cards == 'site':
        cards = SITE_CARDS
    elif args.cards == 'archive':
        cards = SITE_CARDS + ARCHIVE_ONLY_CARDS
    elif args.cards == 'all':
        cards = CARDS_ALL
    else:
        cards = [c.strip() for c in args.cards.split(',') if c.strip()]

    os.makedirs(OUT, exist_ok=True)
    print("=" * 100)
    print("S363 — بازداوریِ S327 Sell-Climax Reversal با RQS2 v2.4 (P0: پیکربندیِ منجمد)")
    print(f"cards={cards}  SEEDS={SEEDS}  PERM_K={PERM_K}  P_BAR={P_BAR}")
    print(f"n_trials honest={N_TRIALS_HONEST} (M30={N_TRIALS_M30}) stress={N_TRIALS_STRESS}")
    print("=" * 100, flush=True)

    for card in cards:
        try:
            rec = run_card(card, do_neff=not args.no_neff)
        except Exception as exc:                       # noqa: BLE001
            rec = dict(card=card, status='ERROR', error=f"{type(exc).__name__}: {exc}")
            print(f"  !! {card}: {rec['error']}", flush=True)
        # قانونِ سوم (اندک اندک): هر کارت بی‌درنگ روی دیسک ذخیره می‌شود تا ریستِ
        # سندباکس کلِ پروسه را نبرد.
        with open(os.path.join(OUT, f"P0_{card}.json"), 'w') as fh:
            json.dump(rec, fh, indent=1, ensure_ascii=False, default=str)
        print(f"  → saved {OUT}/P0_{card}.json  status={rec.get('status')} "
              f"decision={(rec.get('honest') or {}).get('decision')}", flush=True)


if __name__ == '__main__':
    main()
