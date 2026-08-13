# -*- coding: utf-8 -*-
"""
S510 — احیای هندسهٔ RR>1 روی کارت‌های پایینِ طلا (M1/M5/M15) با قانونِ منجمدِ S382
================================================================================
پیش‌ثبت: `results/S510_PREREG_RR_GEOMETRY_LOWTF_WPR.md` (کامیتِ جداگانه، قبل از
هر عدد). داور: `engine/rqs2.py` v2.6. دارایی: فقط XAUUSD (استثنای صریحِ کاربر
برای EURUSD).

چه چیزی منجمد است (صفر جستجوی قانون)
--------------------------------------------------------------------------------
قانونِ ورود عیناً از `strategies/s382_williamsr_momentum.py` (ACCEPT):
  * سیگنال = **رویدادِ** عبورِ Williams %R به بالای −13.0 (کراس، نه حالت)
  * جهت = LONG فقط · فیلتر = هیچ
  * SL = SL_K × median(ATR(100)) — ⚠️ median فقط از **پنجرهٔ اکتشاف** (۶۰٪ نخست)
    تا حتی همان نشتِ خفیفِ فول-سمپلِ S382 هم اینجا نباشد.
  * معناشناسیِ شبیه‌ساز: ورود در close کندلِ سیگنال، اولویتِ SL در کندلِ مبهم،
    قیدِ عدمِ همپوشانی، حذفِ معاملهٔ بازِ پایانِ داده — عیناً S382.

چه چیزی حرکت می‌کند — فقط هندسه + دو گونهٔ معنایی (پیش‌ثبت‌شده)
--------------------------------------------------------------------------------
  * RR_GRID  = (1.0, 1.272, 1.618, 2.058, 2.618, 3.236)   ← 1.0 فقط شاهد
  * SL_K_GRID = (0.618, 1.0, 1.272, 1.618, 2.058)
  * گونهٔ V1 (بومی): دورهٔ %R = ۱۴ کندلِ خودِ کارت
  * گونهٔ V2 (تقویم-معادل ۱۴×H4 = ۳۳۶۰ دقیقه): M1=3360, M5=672, M15=224
    (درسِ معناشناختیِ s434: پورتِ فرمول بدونِ حفظِ معنا = جا زدنِ لایهٔ دیگر)

مسئلهٔ مهندسی و راه‌حلش — شبیه‌سازِ numba + آزمونِ برابری
--------------------------------------------------------------------------------
شبیه‌سازِ حلقه-پایتونیِ S382 روی M1 (۵M کندل) برای ۲۰۰۰ جایگشتِ مدلِ صفر
غیرممکن است. این ماژول همان معناشناسی را در numba پیاده می‌کند و **قبل از هر
استفاده** با `--stage parity` برابریِ معامله-به-معامله با شبیه‌سازِ اصلیِ S382
را اثبات می‌کند (انضباطِ ضدِ باگِ «دو نسخهٔ ناهمگام»). اگر parity رد شود،
هیچ مرحلهٔ دیگری اجرا نمی‌شود.

مراحل (قانونِ اندک‌اندک — هر مرحله checkpoint خودش را می‌نویسد)
--------------------------------------------------------------------------------
  --stage parity                 : اثباتِ برابریِ شبیه‌سازها (روی M15)
  --stage sweep  --card M1|M5|M15: جاروبِ ۳۰×۲ هندسه روی ۶۰٪ نخست + قاعدهٔ انتخاب
  --stage null   --card ...      : مدلِ صفرِ اندازه‌گیری‌شده برای برندهٔ کارت
  --stage adjudicate --card ...  : **یک** داوریِ رسمی per کارت (n_trials=180)

قاعدهٔ انتخابِ پیش‌ثبت‌شده (تغییر پس از دیدنِ خروجی = تقلب):
  (الف) n≥30 در اکتشاف؛ (ب) RR>1.0؛ (ج) TP>2c؛
  (د) امیدِ خالص (پس از هزینهٔ 3.3pip) در هر دو نیمهٔ اکتشاف مثبت.
  سپس argmax امیدِ خالصِ اکتشاف؛ بینِ دو گونهٔ یک کارت، گونهٔ با امیدِ بالاتر.
"""
import sys
import os
import json
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R                                        # noqa: E402
from tools.s434_fast_data import load_fast                          # noqa: E402

OUT = 'results/_scan_S510'

# ---------------------- ثابت‌های پیش‌ثبت‌شده (قفل) ----------------------
SEED = 20260812
K_PERM = 2000
SPLIT_FRAC = 0.60
N_TRIALS = 180                     # 6 RR × 5 SL_K × 2 گونه × 3 کارت
WILLR_THR = -13.0                  # منجمد از S382
ATR_P = 100                        # منجمد از S382
RR_GRID = (1.0, 1.272, 1.618, 2.058, 2.618, 3.236)
SL_K_GRID = (0.618, 1.0, 1.272, 1.618, 2.058)
MIN_N_DISC = 30
PIP = 0.10                         # se.ASSETS['XAUUSD']
COST_PIP = 3.3                     # spread 3.3 + slip 0 (کالیبراسیونِ حساب)

# دورهٔ %R به تفکیکِ (کارت، گونه) — پیش‌ثبت‌شده
WPR_PERIODS = {
    'M1':  {'V1': 14, 'V2': 3360},
    'M5':  {'V1': 14, 'V2': 672},
    'M15': {'V1': 14, 'V2': 224},
}


# ============================ داده و اندیکاتور ============================

def load_card(tf):
    """دادهٔ کاملِ ۱۵.۶ سالهٔ mt5_full با کشِ باینری. محافظِ BUG-DATASETDRIFT:
    مسیر/تعدادسطر/بازه چاپ می‌شود."""
    d = load_fast('XAUUSD', tf)
    print(f"[DATA] src={d['src']}  n_bars={d['n_bars']}  "
          f"span={d['first_utc']} .. {d['last_utc']}  ({d['span_years']}y)")
    return d


def willr_np(high, low, close, p):
    """Williams %R وکتوری — همان فرمولِ S382 (rolling max/min)."""
    s_h = pd.Series(high).rolling(p).max().to_numpy()
    s_l = pd.Series(low).rolling(p).min().to_numpy()
    rng = s_h - s_l
    with np.errstate(invalid='ignore', divide='ignore'):
        w = -100.0 * (s_h - close) / np.where(rng == 0.0, np.nan, rng)
    return w


def atr_np(high, low, close, p=ATR_P):
    """ATR با ewm(alpha=1/p) — عیناً S382."""
    pc = np.empty_like(close)
    pc[0] = np.nan
    pc[1:] = close[:-1]
    tr = np.nanmax(np.stack([high - low,
                             np.abs(high - pc),
                             np.abs(low - pc)]), axis=0)
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def cross_signals(w, thr=WILLR_THR):
    """رویدادِ عبور به بالای آستانه — کراس، نه حالت (عیناً S382)."""
    prev = np.empty_like(w)
    prev[0] = np.nan
    prev[1:] = w[:-1]
    return (prev <= thr) & (w > thr)


# ===================== شبیه‌سازِ numba (هم‌معنای S382) =====================
# معناشناسی: entry=close[e]؛ پیمایش از e+1؛ SL مقدم در کندلِ مبهم؛
# non-overlap (سیگنالِ قبل از پایانِ معاملهٔ فعال دور ریخته می‌شود)؛
# معاملهٔ بازِ انتهای داده حذف. خروجی: آرایه‌های entry_bar/exit_bar/win.
from numba import njit                                              # noqa: E402


@njit(cache=True)
def _sim_core(high, low, close, sig_idx, sl_abs, tp_abs):
    n = high.shape[0]
    m = sig_idx.shape[0]
    eb = np.empty(m, dtype=np.int64)
    xb = np.empty(m, dtype=np.int64)
    wn = np.empty(m, dtype=np.int8)
    cnt = 0
    i = 0                       # اولین اندیسِ مجاز برای ورودِ بعدی
    ptr = 0
    while ptr < m:
        e = sig_idx[ptr]
        if e < i or e + 1 >= n:
            ptr += 1
            continue
        entry = close[e]
        sl_lvl = entry - sl_abs
        tp_lvl = entry + tp_abs
        j = e + 1
        hit = 0                 # 0=هیچ، 1=SL، 2=TP
        while j < n:
            if low[j] <= sl_lvl:        # SL مقدم — بدبینانه‌ترین فرض
                hit = 1
                break
            if high[j] >= tp_lvl:
                hit = 2
                break
            j += 1
        if hit == 0:
            break               # معاملهٔ باز در پایانِ داده ⇒ حذف و توقف
        eb[cnt] = e
        xb[cnt] = j
        wn[cnt] = 1 if hit == 2 else 0
        cnt += 1
        i = j + 1
        while ptr < m and sig_idx[ptr] < i:
            ptr += 1
    return eb[:cnt], xb[:cnt], wn[:cnt]


def simulate(d, sig_idx, sl_abs, rr):
    """پوششِ شبیه‌ساز: خروجی DataFrame سازگار با rqs2 (LONG فقط)."""
    tp_abs = max(rr * sl_abs, sl_abs)          # سپرِ اشتباهِ #۸: TP هرگز < SL
    eb, xb, wn = _sim_core(d['high'], d['low'], d['close'],
                           np.asarray(sig_idx, np.int64),
                           float(sl_abs), float(tp_abs))
    sl_pip = sl_abs / PIP
    tp_pip = tp_abs / PIP
    pnl = np.where(wn == 1, tp_pip, -sl_pip)
    return pd.DataFrame(dict(
        entry_bar=eb, exit_bar=xb,
        outcome=np.where(wn == 1, 'win', 'loss'),
        pnl_pip=pnl, sl_pip=sl_pip, tp_pip=tp_pip, direction='long'))


# ============================ مراحل ============================

def stage_parity():
    """اثباتِ برابری معامله-به-معامله با شبیه‌سازِ اصلیِ S382 روی M15.

    چرا M15: کوچک‌ترین کارتِ هدف ⇒ شبیه‌سازِ پایتونیِ کند هم تمام می‌شود.
    پیکربندیِ آزمون = خودِ پیکربندیِ منجمدِ S382 (p=14, SL_K=1.5, RR=1.5)
    + یک پیکربندیِ دومِ متفاوت (p=224, SL_K=0.618, RR=3.236) تا برابری در
    گوشهٔ دیگرِ فضا هم اثبات شود.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        '_s382', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              's382_williamsr_momentum.py'))
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)

    d = load_card('M15')
    df = pd.DataFrame({k: d[k] for k in ('time', 'open', 'high', 'low', 'close')})

    ok_all = True
    for (p, sl_k, rr) in ((14, 1.5, 1.5), (224, 0.618, 3.236)):
        w = willr_np(d['high'], d['low'], d['close'], p)
        sig_bool = cross_signals(w)
        split = int(SPLIT_FRAC * d['n_bars'])
        a = atr_np(d['high'], d['low'], d['close'])
        sl_abs = float(np.nanmedian(a[:split])) * sl_k

        # مرجع: شبیه‌سازِ اصلیِ S382 (پایتونِ خالص)
        sig_series = pd.Series(sig_bool)
        tr_ref = L.simulate_trades(df, sig_series, sl_abs, rr, True, PIP)
        # نامزد: شبیه‌سازِ numba
        tr_new = simulate(d, np.flatnonzero(sig_bool), sl_abs, rr)

        same = (len(tr_ref) == len(tr_new)
                and np.array_equal(tr_ref['entry_bar'].to_numpy(),
                                   tr_new['entry_bar'].to_numpy())
                and np.array_equal(tr_ref['exit_bar'].to_numpy(),
                                   tr_new['exit_bar'].to_numpy())
                and list(tr_ref['outcome']) == list(tr_new['outcome']))
        print(f'[PARITY] p={p} sl_k={sl_k} rr={rr}: '
              f'ref n={len(tr_ref)}  numba n={len(tr_new)}  '
              f'{"IDENTICAL ✓" if same else "MISMATCH ✗"}')
        ok_all = ok_all and same

    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/parity.json', 'w') as f:
        json.dump({'parity_ok': bool(ok_all)}, f)
    if not ok_all:
        raise SystemExit('PARITY FAILED — هیچ مرحلهٔ دیگری مجاز نیست')
    print('[PARITY] PASSED — شبیه‌سازِ numba هم‌معنای S382 است')


def stage_sweep(tf):
    """جاروبِ ۳۰ هندسه × ۲ گونه، فقط روی ۶۰٪ نخست + قاعدهٔ انتخابِ پیش‌ثبت‌شده."""
    d = load_card(tf)
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    a = atr_np(d['high'], d['low'], d['close'])
    med_atr_disc = float(np.nanmedian(a[:split]))
    print(f'[SWEEP {tf}] split_bar={split}  median_ATR100(disc)={med_atr_disc:.4f}')

    results = []
    for variant, p in WPR_PERIODS[tf].items():
        w = willr_np(d['high'], d['low'], d['close'], p)
        sig_bool = cross_signals(w)
        warm = max(p, ATR_P) + 10
        sig_bool[:warm] = False
        # ⛔ اکتشاف فقط ۶۰٪ نخست: سیگنال‌های بعد از split دیده نمی‌شوند
        sig_disc = np.flatnonzero(sig_bool[:split])
        print(f'  [{variant}] p={p}  raw_signals(disc)={len(sig_disc)}')

        # داده‌ی بریده تا مرزِ split — تا شبیه‌ساز هرگز آن‌سوی مرز را نبیند
        d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
        half = split // 2

        for sl_k in SL_K_GRID:
            sl_abs = med_atr_disc * sl_k
            for rr in RR_GRID:
                tr = simulate(d_disc, sig_disc, sl_abs, rr)
                nt = len(tr)
                row = dict(variant=variant, p=p, sl_k=sl_k, rr=rr,
                           sl_pip=round(sl_abs / PIP, 2),
                           tp_pip=round(max(rr, 1.0) * sl_abs / PIP, 2),
                           n=nt)
                if nt > 0:
                    pnl = tr['pnl_pip'].to_numpy()
                    e1_mask = tr['entry_bar'].to_numpy() < half
                    exp_net = float(pnl.mean()) - COST_PIP
                    e1 = float(pnl[e1_mask].mean()) - COST_PIP if e1_mask.any() else np.nan
                    e2 = float(pnl[~e1_mask].mean()) - COST_PIP if (~e1_mask).any() else np.nan
                    wr = float((tr['outcome'] == 'win').mean() * 100)
                    row.update(exp_net=round(exp_net, 3), exp_h1=round(e1, 3),
                               exp_h2=round(e2, 3), wr=round(wr, 2))
                    # قاعدهٔ انتخاب (الف..د)
                    row['candidate'] = bool(
                        nt >= MIN_N_DISC and rr > 1.0
                        and row['tp_pip'] > 2 * COST_PIP
                        and np.isfinite(e1) and np.isfinite(e2)
                        and e1 > 0 and e2 > 0)
                else:
                    row.update(exp_net=None, exp_h1=None, exp_h2=None,
                               wr=None, candidate=False)
                results.append(row)

    cands = [r for r in results if r['candidate']]
    winner = max(cands, key=lambda r: r['exp_net']) if cands else None
    os.makedirs(OUT, exist_ok=True)
    payload = dict(card=f'XAUUSD_{tf}', split_bar=split,
                   med_atr_disc=med_atr_disc, seed=SEED,
                   n_combos=len(results), n_candidates=len(cands),
                   winner=winner, grid=results)
    with open(f'{OUT}/{tf}_sweep.json', 'w') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f'[SWEEP {tf}] combos={len(results)}  candidates={len(cands)}')
    if winner:
        print(f'[SWEEP {tf}] WINNER: {winner["variant"]} p={winner["p"]} '
              f'sl_k={winner["sl_k"]} rr={winner["rr"]}  n={winner["n"]}  '
              f'exp_net={winner["exp_net"]}pip  wr={winner["wr"]}%')
    else:
        print(f'[SWEEP {tf}] NO CANDIDATE — طبق پیش‌ثبت، این کارت بدونِ داوری '
              f'REJECT-by-rule ثبت می‌شود')
    print(f'saved -> {OUT}/{tf}_sweep.json')


def _winner(tf):
    with open(f'{OUT}/{tf}_sweep.json') as f:
        s = json.load(f)
    if not s.get('winner'):
        raise SystemExit(f'{tf}: برنده‌ای در sweep نیست — این مرحله موضوعیت ندارد')
    return s


def stage_null(tf):
    """مدلِ صفرِ اندازه‌گیری‌شده برای برندهٔ کارت — روی **کل** نمونه.

    دو مبنا (عیناً پروتکلِ S382): ① WR بی‌قید (stride 1,3,7؛ سخت‌ترین)
    ② جایگشتِ زمان‌بندیِ همان تعدادِ سیگنالِ خام، K=2000، بذرِ ثابت.
    """
    s = _winner(tf)
    wcfg = s['winner']
    d = load_card(tf)
    n = d['n_bars']
    split = s['split_bar']
    a = atr_np(d['high'], d['low'], d['close'])
    sl_abs = float(s['med_atr_disc']) * wcfg['sl_k']       # منجمد از اکتشاف
    rr = wcfg['rr']
    p = wcfg['p']

    w = willr_np(d['high'], d['low'], d['close'], p)
    sig_bool = cross_signals(w)
    warm = max(p, ATR_P) + 10
    sig_bool[:warm] = False
    sig_idx = np.flatnonzero(sig_bool)
    n_sig = len(sig_idx)

    tr = simulate(d, sig_idx, sl_abs, rr)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f'[NULL {tf}] winner p={p} sl_k={wcfg["sl_k"]} rr={rr}  '
          f'n_sig={n_sig}  n_trades={len(tr)}  wr={obs_wr:.2f}%')

    # مبنای ①: ورودِ بی‌قید
    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(warm, n - 2, stride, dtype=np.int64)
        t0 = simulate(d, idx, sl_abs, rr)
        wr0 = 100.0 * float((t0['outcome'] == 'win').mean()) if len(t0) else None
        uncond_rows.append((stride, wr0, len(t0)))
        print(f'  uncond stride={stride}: n={len(t0)}  wr={wr0:.2f}%')
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)

    # مبنای ②: جایگشتِ زمانی
    rng = np.random.default_rng(SEED)
    space = np.arange(warm, n - 2, dtype=np.int64)
    wrs = []
    for k in range(K_PERM):
        pos = np.sort(rng.choice(space, size=min(n_sig, len(space)), replace=False))
        tp_ = simulate(d, pos, sl_abs, rr)
        if len(tp_) >= 30:
            wrs.append(100.0 * float((tp_['outcome'] == 'win').mean()))
        if (k + 1) % 250 == 0:
            print(f'  perm {k+1}/{K_PERM} ...', flush=True)
    arr = np.asarray(wrs, float)
    perm = dict(mean=float(arr.mean()), sd=float(arr.std(ddof=1)),
                max=float(arr.max()), p95=float(np.percentile(arr, 95)),
                k=int(len(arr)))
    z = (obs_wr - perm['mean']) / perm['sd'] if perm['sd'] > 0 else float('nan')
    print(f'  perm: mean={perm["mean"]:.2f} sd={perm["sd"]:.2f} '
          f'max={perm["max"]:.2f} k={perm["k"]}  ->  observed z={z:.2f}')

    null = {'long': dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
                         perm_sd=perm['sd'], perm_max=perm['max'],
                         perm_k=perm['k']),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    with open(f'{OUT}/{tf}_null.json', 'w') as f:
        json.dump(dict(card=f'XAUUSD_{tf}', winner=wcfg, obs_wr=obs_wr,
                       n_trades=len(tr), n_signals=n_sig, sl_abs=sl_abs,
                       uncond=uncond_rows, perm=perm, null=null,
                       seed=SEED, k=K_PERM, z_preview=z), f, ensure_ascii=False)
    print(f'saved -> {OUT}/{tf}_null.json')


def stage_adjudicate(tf):
    """**یک** داوریِ رسمیِ per کارت با rqs2 v2.6 — n_trials=180 (کل خانواده)."""
    s = _winner(tf)
    wcfg = s['winner']
    with open(f'{OUT}/{tf}_null.json') as f:
        nm = json.load(f)
    d = load_card(tf)
    split = s['split_bar']
    sl_abs = float(nm['sl_abs'])
    p, rr = wcfg['p'], wcfg['rr']

    w = willr_np(d['high'], d['low'], d['close'], p)
    sig_bool = cross_signals(w)
    warm = max(p, ATR_P) + 10
    sig_bool[:warm] = False
    tr = simulate(d, np.flatnonzero(sig_bool), sl_abs, rr)

    sl_pip = sl_abs / PIP
    tp_pip = max(rr, 1.0) * sl_abs / PIP
    # assert صریح بر فیلدهایی که به آن‌ها تکیه می‌کنم (انضباطِ ضدِ سکوتِ موتور)
    for col in ('pnl_pip', 'outcome', 'sl_pip', 'entry_bar', 'exit_bar', 'direction'):
        assert col in tr.columns, f'missing column {col}'

    res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=d['time'], close=d['close'],
                         null=nm['null'], n_trials=N_TRIALS, split_bar=split)
    print(R.format_rqs2(f'S510_{tf}_{wcfg["variant"]}_p{p}_slk{wcfg["sl_k"]}_rr{rr}', res))
    with open(f'{OUT}/{tf}_rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/{tf}_trades.csv', index=False)
    print(f'saved -> {OUT}/{tf}_rqs2.json + {tf}_trades.csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True,
                    choices=['parity', 'sweep', 'null', 'adjudicate'])
    ap.add_argument('--card', choices=['M1', 'M5', 'M15'])
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.stage == 'parity':
        stage_parity()
    else:
        if not args.card:
            raise SystemExit('--card لازم است')
        {'sweep': stage_sweep, 'null': stage_null,
         'adjudicate': stage_adjudicate}[args.stage](args.card)
