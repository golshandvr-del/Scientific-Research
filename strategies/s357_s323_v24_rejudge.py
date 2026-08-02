# -*- coding: utf-8 -*-
"""
S357 — بازداوریِ لایهٔ `S323` (S/R Pullback + Golden Window) با موتورِ **RQS2 v2.4**
================================================================================

چرا این نشست S323 را انتخاب کرد
--------------------------------
غربالِ `results/RQS2_SITE_TRIAGE_v24.md` هر ۳۳ جفتِ (کارت، لایه) روی سایت را روی دو
دروازهٔ کشنده سنجید. `S323` روی کارتِ `XAUUSD-M30` صدرنشین شد:

    z = 4.10σ   ·   n = 140 (بزرگ‌ترینِ کلِ موجودی)   ·   RR = 0.619 ✓   ·   lift = +16.08pp

و قیدِ دومی که غربال کشف کرد انتخاب را قطعی کرد: `H7` دستِ‌کم ۱۵ معاملهٔ holdout می‌خواهد،
پس نامزدهای `z`-قویِ کم‌نمونه (`S328` با n=41، `S334` با n=45) **حسابیاً** از پیش مرده‌اند.
تنها `S323 M30` هم `z` را دارد هم نمونه را.

⚠️ کشفِ حیاتیِ پیش از داوری: «لایهٔ بک‌تست‌شده» ≠ «لایهٔ مستقر»
----------------------------------------------------------------
مقایسهٔ `strategies/s323_s11_sr_pullback_revival.py` با `web_tool/src/revived_strategies.ts`
(تابعِ `computeS323`، خطوطِ ۷۳۵–۷۹۰) سه واگراییِ **ماهوی** نشان داد:

| شرط | پایتونِ بک‌تست‌شده | **TSِ مستقر (آنچه کاربر می‌گیرد)** |
|---|---|---|
| روند | `close > EMA50` **و** `EMA50 > EMA200` | فقط `close > EMA200` |
| شیبِ EMA50 | `ema_slope ≥ slope_min` — فیلترِ فعال | **اصلاً محاسبه نمی‌شود** (`slopeMin` در cfg هست ولی خوانده نمی‌شود) |
| سطحِ S/R | `structure.pivots(left=6, right=6)` + خوشه‌بندیِ `sr_levels(tol, expiry=1500)` | pivotِ خام `L=20` دوطرفه، lookback ۱۲۰ کندل، **بدونِ** خوشه‌بندی |

TS **شل‌تر** است ⇒ سیگنالِ بیشتر ⇒ به‌احتمالِ زیاد WRِ پایین‌تر. یعنی عددِ بایگانی
(`WR=77.1٪`, `n=140`) متعلق به نسخه‌ای است که **روی سایت نیست**.

بنابراین این اسکریپت **هر دو** را می‌سازد و هر دو را داوری می‌کند:

  · `deployed`   — پورتِ verbatimِ منطقِ TS به پایتون  ⇒ **این حکمِ حاکم است**
  · `backtested` — منطقِ اصلیِ پایتون                  ⇒ فقط برای سنجشِ اندازهٔ واگرایی

اگر `deployed` بیفتد ولی `backtested` پاس شود، تشخیص «رانشِ پورت» است نه «مرگِ لایه»،
و درمانش هم‌ترازکردنِ TS با پایتون است — که خودش یک **بهبود** به‌معنای قانونِ دوم است.

قانونِ اولِ پروژه (MTF)
------------------------
هر تایم‌فریمِ موجود جداگانه آزموده و جداگانه گزارش می‌شود. XAUUSD دادهٔ M1 ندارد، پس از
`XAUUSD-M5` شروع می‌شود و تا `EURUSD-H4` ادامه می‌یابد. نتیجهٔ هر کارت **بلافاصله** روی
دیسک نوشته می‌شود (قانونِ سوم: اندک‌اندک — سندباکس ناپایدار است و یک‌بار همین نشست ریست شد).

اجرا:
    python3 strategies/s357_s323_v24_rejudge.py                 # همهٔ کارت‌ها
    python3 strategies/s357_s323_v24_rejudge.py --cards XAUUSD-M30
    python3 strategies/s357_s323_v24_rejudge.py --variant deployed --k 5000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, '.')

import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs2 as R2

import warnings
warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════════════════════════════════
# ثابت‌های پیش‌ثبت‌شده (هم‌راستا با `s356_v24_rejudge.py` تا احکام قابلِ‌مقایسه بمانند)
# ═══════════════════════════════════════════════════════════════════════════
PERM_K = 2000          # سدِ v2.4 حداقل ۵۰۰ می‌خواهد؛ ۲۰۰۰ برای تفکیکِ p تا 0.0005
SEEDS = (23, 101, 777)
P_BAR = 0.001
OUT_DIR = 'results/_s357_s323_v24'

# `n_trials` — اندازهٔ فضای جست‌وجویی که S323 واقعاً پیمود.
# از `GRID` در `s323_s11_sr_pullback_revival.py` + `s323c_sr_pullback_mtf.py`:
#   near_max 3 × room_min 2 × rsi_max 3 × slope_min 2 × adx_min 2 × golden 2
#   × sl_mult 3 × tp_mult 3  →  با قیدِ tp<sl حدودِ ۴۳۲ ترکیب × ۲ max_hold ≈ ۸۶۴
# گریدِ دومِ MTF: 2×2×2×2×4×2×3×3 = ۱۱۵۲ با قیدِ tp<sl ≈ ۷۶۸ × ۲ mh ≈ ۱۵۳۶
# مجموعِ صادقانه ≈ ۲۴۰۰. عددِ محافظه‌کارانه‌تر برای تنش: ۴۸۰۰.
N_TRIALS_HONEST = 2400
N_TRIALS_STRESS = 4800


# ═══════════════════════════════════════════════════════════════════════════
# پیکربندیِ **مستقر** — verbatim از `web_tool/src/revived_strategies.ts:730-732`
# ═══════════════════════════════════════════════════════════════════════════
DEPLOYED_CFG = {
    'XAUUSD-M15': dict(nearMax=0.85, roomMin=1.3, rsiMax=55, slopeMin=0.0, adxMin=22,
                       golden=True, hLo=19, hHi=23, slMult=1.8, tpMult=1.5,
                       maxHold=96, pivotLen=20),
    'XAUUSD-M30': dict(nearMax=0.85, roomMin=1.3, rsiMax=55, slopeMin=0.0, adxMin=22,
                       golden=True, hLo=19, hHi=23, slMult=2.1, tpMult=1.3,
                       maxHold=48, pivotLen=20),
    'XAUUSD-H1':  dict(nearMax=0.55, roomMin=1.3, rsiMax=55, slopeMin=0.0, adxMin=30,
                       golden=True, hLo=19, hHi=23, slMult=1.8, tpMult=1.7,
                       maxHold=36, pivotLen=20),
}

# کارت‌هایی که پیکربندیِ مستقر ندارند: طبقِ قانونِ MTF باید آزموده شوند، پس
# پیکربندیِ کارتِ «هم‌خانوادهٔ نزدیک» به‌عنوان نقطهٔ شروع استفاده می‌شود و
# `maxHold` متناسبِ همان TF بازتعریف می‌گردد (اجتنابِ صریح از اشتباهِ رایج #۶).
TF_FALLBACK = {
    'M1':  ('XAUUSD-M15', 240),
    'M5':  ('XAUUSD-M15', 192),
    'M15': ('XAUUSD-M15', 96),
    'M30': ('XAUUSD-M30', 48),
    'H1':  ('XAUUSD-H1', 36),
    'H4':  ('XAUUSD-H1', 14),
    'D1':  ('XAUUSD-H1', 8),
}

ALL_CARDS = [
    'XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1', 'XAUUSD-H4', 'XAUUSD-D1',
    'EURUSD-M1', 'EURUSD-M5', 'EURUSD-M15', 'EURUSD-M30', 'EURUSD-H1', 'EURUSD-H4',
]


def cfg_for(card: str) -> dict:
    """پیکربندیِ مستقر اگر هست، وگرنه هم‌خانوادهٔ نزدیک با maxHoldِ متناسبِ TF."""
    if card in DEPLOYED_CFG:
        return dict(DEPLOYED_CFG[card], _source='deployed')
    tf = card.split('-')[1]
    src, mh = TF_FALLBACK[tf]
    return dict(DEPLOYED_CFG[src], maxHold=mh, _source=f'inherited:{src}')


# ═══════════════════════════════════════════════════════════════════════════
# پورتِ **verbatim** منطقِ TS  (`computeS323`, revived_strategies.ts:735-790)
# ═══════════════════════════════════════════════════════════════════════════
def signals_deployed(df: pd.DataFrame, cfg: dict) -> np.ndarray:
    """بازتولیدِ بیت‌به‌بیتِ شرطِ `active` در `computeS323`.

    نکاتِ وفاداری که عمداً حفظ شده‌اند (هرکدام یک تفاوتِ واقعی می‌سازند):
      · روند فقط `close > EMA200` است — **بدونِ** قیدِ `EMA50` که پایتون دارد.
      · هیچ فیلترِ شیبی اعمال نمی‌شود — `slopeMin` در cfg هست ولی TS نمی‌خواندش.
      · pivot خامِ `L`-دوطرفه است با شرطِ **غیراکید** (`>=` / `<=`) دقیقاً مثلِ
        `.every(v => v >= low[k])`، و پنجرهٔ جست‌وجو فقط ۱۲۰ کندلِ اخیر.
      · شرطِ `k + L > i` در TS یعنی pivot باید **کاملاً تأییدشده** باشد ⇒ forward-safe.
      · `nearOk` در TS `<=` است و `roomOk` هم `>=` (پایتون `<` و `>` اکید دارد).
    """
    high = df['high'].values.astype(float)
    low = df['low'].values.astype(float)
    close = df['close'].values.astype(float)
    n = len(df)

    atr14 = ind.atr(df, 14).values
    e200 = ind.ema(df['close'], 200).values
    adx_arr, _, _ = ind.adx(df, 14)
    adx_arr = adx_arr.values
    rsi14 = ind.rsi(df['close'], 14).values
    hour = df['dt'].dt.hour.values

    L = int(cfg['pivotLen'])

    # pivotهای تأییدشده — یک‌بار برای کلِ سری (TS در هر فراخوان دوباره می‌سازد،
    # ولی نتیجه یکسان است چون شرطِ `k+L > i` تضمین می‌کند pivot فقط بعد از
    # تأییدِ کاملِ سمتِ راست دیده شود).
    win = 2 * L + 1
    roll_min = pd.Series(low).rolling(win, center=True).min().to_numpy()
    roll_max = pd.Series(high).rolling(win, center=True).max().to_numpy()
    is_low = np.zeros(n, bool)
    is_high = np.zeros(n, bool)
    idx = np.arange(n)
    m = (idx >= L) & (idx < n - L)
    is_low[m] = low[m] <= roll_min[m]      # `.every(v => v >= low[k])` ⇒ غیراکید
    is_high[m] = high[m] >= roll_max[m]

    lows_idx = np.where(is_low)[0]
    highs_idx = np.where(is_high)[0]

    sig = np.zeros(n, bool)
    for i in range(260, n):
        av = atr14[i]
        if not (av > 0) or not np.isfinite(rsi14[i]) or not np.isfinite(e200[i]):
            continue
        price = close[i]
        if not (price > e200[i]):
            continue
        av_adx = adx_arr[i]
        if not (np.isfinite(av_adx) and av_adx >= cfg['adxMin']):
            continue
        if cfg['golden'] and not (cfg['hLo'] <= hour[i] <= cfg['hHi']):
            continue
        if not (rsi14[i] <= cfg['rsiMax']):
            continue

        lo_bound = max(0, i - 120)
        # حمایت: بزرگ‌ترین pivot-lowِ زیرِ قیمت در پنجره
        cand = lows_idx[(lows_idx >= max(lo_bound, L)) & (lows_idx <= i - L - 1)]
        support = -np.inf
        if cand.size:
            vals = low[cand]
            vals = vals[vals < price]
            if vals.size:
                support = float(vals.max())
        # مقاومت: کوچک‌ترین pivot-highِ بالای قیمت در پنجره
        candh = highs_idx[(highs_idx >= max(lo_bound, L)) & (highs_idx <= i - L - 1)]
        resistance = np.inf
        if candh.size:
            valsh = high[candh]
            valsh = valsh[valsh > price]
            if valsh.size:
                resistance = float(valsh.min())

        near = (price - support) / av if np.isfinite(support) else np.inf
        room = (resistance - price) / av if np.isfinite(resistance) else np.inf
        if near <= cfg['nearMax'] and room >= cfg['roomMin']:
            sig[i] = True
    return sig


# ═══════════════════════════════════════════════════════════════════════════
# منطقِ اصلیِ پایتون (برای سنجشِ اندازهٔ واگرایی)
# ═══════════════════════════════════════════════════════════════════════════
def signals_backtested(df: pd.DataFrame, asset: str, cfg: dict) -> np.ndarray:
    from engine import structure as st
    tol = 0.0008 if asset == 'EURUSD' else 0.0015
    piv = st.pivots(df, left=6, right=6)
    sr = st.sr_levels(df, piv, tol=tol, expiry=1500)
    atr = ind.atr(df, 14).values
    a = np.where(atr > 0, atr, np.nan)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    rsi14 = ind.rsi(df['close'], 14).values
    adx_arr, _, _ = ind.adx(df, 14)
    adx_arr = np.nan_to_num(adx_arr.values, nan=0.0)
    close = df['close'].values
    hour = df['dt'].dt.hour.values
    sup = sr['support'].values
    res_lvl = sr['resistance'].values

    dist_sup = np.nan_to_num((close - sup) / a, nan=99.0)
    room = np.nan_to_num((res_lvl - close) / a, nan=-99.0)
    slope = np.full(len(df), np.nan)
    slope[10:] = (ema50[10:] - ema50[:-10]) / a[10:]
    slope = np.nan_to_num(slope, nan=0.0)

    up = (close > ema50) & (ema50 > ema200)
    near = (dist_sup > 0) & (dist_sup < cfg['nearMax'])
    room_ok = room > cfg['roomMin']
    rsi_ok = rsi14 < cfg['rsiMax']
    slope_ok = slope >= cfg['slopeMin']
    adx_ok = adx_arr >= cfg['adxMin']
    gold = ((hour >= cfg['hLo']) & (hour <= cfg['hHi'])) if cfg['golden'] \
        else np.ones(len(df), bool)
    sig = up & near & room_ok & rsi_ok & slope_ok & adx_ok & gold
    sig[:300] = False
    return sig


# ═══════════════════════════════════════════════════════════════════════════
# مدلِ صفرِ اندازه‌گیری‌شده (هم‌سان با `s356_v24_rejudge.py` تا احکام قابلِ‌مقایسه بمانند)
# ═══════════════════════════════════════════════════════════════════════════
def outcome_table(df, asset, sl_pip, tp_pip, mh):
    """برآمدِ «همان براکت اگر روی کندلِ بعدِ هر کندل باز شود».

    قراردادِ اجرا بیت‌به‌بیت با `simulate_trades` یکی است — از جمله اینکه اگر یک
    کندل هر دو سطح را لمس کند **باخت** ثبت شود (محافظه‌کارانه). همین قرارداد
    عیناً روی مبنا و روی لایه اعمال می‌شود تا مقایسه منصفانه بماند.
    """
    o = df['open'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = cfg['pip']
    cost = cfg['spread_pip'] + 2 * cfg.get('slip_pip', 0.0)
    sl_d, tp_d = sl_pip * pip, tp_pip * pip

    eb = np.arange(n) + 1
    live = eb < n
    ent = np.where(live, o[np.minimum(eb, n - 1)], np.nan)
    res = np.zeros(n, dtype=np.int8)
    xbar = np.full(n, -1, dtype=np.int64)

    for j in range(mh):
        k = eb + j
        slot = live & (res == 0) & (k < n)
        if not slot.any():
            break
        kk = np.minimum(k, n - 1)
        lo_hit = slot & (l[kk] <= ent - sl_d)
        hi_hit = slot & (~lo_hit) & (h[kk] >= ent + tp_d)
        res[lo_hit] = -1
        xbar[lo_hit] = k[lo_hit]
        res[hi_hit] = 1
        xbar[hi_hit] = k[hi_hit]

    kend = np.minimum(eb + mh, n)
    to = live & (res == 0) & (kend > eb)
    if to.any():
        last = c[np.maximum(kend - 1, 0)]
        won = ((last - ent) / pip - cost) > 0
        res[to] = np.where(won[to], 1, -1)
        xbar[to] = kend[to] - 1
    return res, xbar


def wr_of(picks, res, xbar):
    wins = used = 0
    last_exit = -1
    for si in picks:
        if si <= last_exit or res[si] == 0:
            continue
        used += 1
        last_exit = xbar[si]
        if res[si] == 1:
            wins += 1
    return (100.0 * wins / used) if used else None


def build_null(df, asset, sig, sl, tp, mh, k_perm, seed):
    res, xbar = outcome_table(df, asset, sl, tp, mh)
    n = len(df)
    valid = np.arange(260, max(261, n - mh - 2))
    valid = valid[res[valid] != 0]
    k = int(np.asarray(sig).sum())
    uncond = wr_of(valid, res, xbar)

    rng = np.random.default_rng(seed)
    draws = np.empty(k_perm, dtype=float)
    got = 0
    for _ in range(k_perm):
        pick = np.sort(rng.choice(valid, size=min(k, valid.size), replace=False))
        w = wr_of(pick, res, xbar)
        if w is not None:
            draws[got] = w
            got += 1
    draws = draws[:got]
    long_null = dict(uncond_wr=uncond, perm_mean=float(draws.mean()),
                     perm_sd=float(draws.std(ddof=1)), perm_max=float(draws.max()),
                     perm_k=int(got))
    zero = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=0)
    return {'long': long_null, 'short': zero}, draws


def empirical_p(draws, wr_obs):
    """p تجربیِ یک‌طرفه با برآوردگرِ محافظه‌کارانهٔ `(1+#{≥obs})/(1+K)`."""
    ge = int((draws >= wr_obs - 1e-12).sum())
    return (1.0 + ge) / (1.0 + len(draws)), ge


# ═══════════════════════════════════════════════════════════════════════════
def run_card(card, variant, k_perm, verbose=True):
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return dict(card=card, variant=variant, status='NO_DATA')

    df = se.load_data(path)
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    cfg = cfg_for(card)

    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    atr_pip_med = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['slMult'] * atr_pip_med, 1)
    tp = round(cfg['tpMult'] * atr_pip_med, 1)
    mh = int(cfg['maxHold'])

    t0 = time.time()
    if variant == 'deployed':
        sig = signals_deployed(df, cfg)
    else:
        sig = signals_backtested(df, asset, cfg)
    n_sig = int(sig.sum())

    if verbose:
        print(f"\n=== {card} [{variant}] cfg={cfg['_source']} :: "
              f"SL={sl}pip TP={tp}pip RR={tp/sl:.3f} mh={mh} "
              f"bars={len(df)} signals={n_sig}  ({time.time()-t0:.0f}s)", flush=True)

    base = dict(card=card, asset=asset, tf=tf, variant=variant,
                cfg={k: v for k, v in cfg.items()},
                sl_pip=sl, tp_pip=tp, rr=round(tp / sl, 4), maxhold=mh,
                bars=len(df), n_signals=n_sig)

    if n_sig < 5:
        return dict(base, status='NO_SIGNAL')

    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 5:
        return dict(base, status='NO_TRADES', n_trades=0 if tr is None else len(tr))

    n = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / n
    close = df['close'].values.astype(float)
    bar_time = df['time'].values
    split_bar = int(len(df) * 0.60)

    rec = dict(base, status='JUDGED', n_trades=n, wr_obs=round(wr_obs, 2), seeds={})

    for seed in SEEDS:
        null, draws = build_null(df, asset, sig, sl, tp, mh, k_perm, seed)
        p_emp, n_ge = empirical_p(draws, wr_obs)
        out = {}
        for label, nt in (('honest', N_TRIALS_HONEST), ('stress', N_TRIALS_STRESS)):
            r = R2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp, bar_time=bar_time,
                                close=close, null=null, n_trials=nt,
                                split_bar=split_bar)
            out[label] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                              gates=r.get('gates'), metrics=r.get('metrics'),
                              notes=r.get('notes'))
        m0 = out['honest']['metrics']
        out['null'] = {k: null['long'][k] for k in
                       ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')}
        out['p_empirical'] = round(p_emp, 6)
        out['n_draws_ge_obs'] = n_ge
        out['honest_accept'] = bool(out['honest']['verdict'] == 'ACCEPT' and p_emp <= P_BAR)
        rec['seeds'][str(seed)] = out
        if verbose:
            g = out['honest']['gates']
            gl = ''.join('1' if g.get(k) else ('?' if g.get(k) is None else '0')
                         for k in R2.GATE_NAMES)
            print(f"  seed={seed} K={out['null']['perm_k']} | n={n} WR={wr_obs:.2f} "
                  f"null={out['null']['uncond_wr']:.2f}/{out['null']['perm_mean']:.2f} "
                  f"lift={m0.get('skill_lift_pp')} z={m0.get('skill_z')} "
                  f"p_emp={p_emp:.6f} ({n_ge}/{out['null']['perm_k']}) | "
                  f"{out['honest']['verdict']} score={out['honest']['score']} "
                  f"G[{gl}]", flush=True)

    rec['all_seeds_accept'] = all(v['honest_accept'] for v in rec['seeds'].values())
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default=','.join(ALL_CARDS))
    ap.add_argument('--variant', default='both', choices=['deployed', 'backtested', 'both'])
    ap.add_argument('--k', type=int, default=PERM_K)
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    cards = [c.strip() for c in a.cards.split(',') if c.strip()]
    variants = ['deployed', 'backtested'] if a.variant == 'both' else [a.variant]

    print(f"S357 — بازداوریِ S323 با RQS2 v2.4 | cards={len(cards)} "
          f"variants={variants} K={a.k} seeds={SEEDS}", flush=True)

    for card in cards:
        for variant in variants:
            try:
                rec = run_card(card, variant, a.k)
            except Exception as e:  # noqa: BLE001
                rec = dict(card=card, variant=variant, status='ERROR', error=repr(e))
                print(f"  !! {card}[{variant}] ERROR {e!r}", flush=True)
            # ⭐ قانونِ سوم (اندک‌اندک): هر کارت بلافاصله روی دیسک
            fp = os.path.join(OUT_DIR, f"{card}_{variant}.json")
            with open(fp, 'w', encoding='utf-8') as fh:
                json.dump(rec, fh, ensure_ascii=False, indent=1, default=str)
            print(f"  → wrote {fp}", flush=True)

    print("\nDONE", flush=True)


if __name__ == '__main__':
    main()
