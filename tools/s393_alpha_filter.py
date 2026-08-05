# -*- coding: utf-8 -*-
"""S393 — **فیلترِ دومِ آلفا-افزا** برای `cci20_xup_135 @ XAUUSD_H1`.

چرا این ابزار
-------------
نامزد ۱۰ از ۱۱ دروازه را پاس می‌کند و تنها `H5` (قضیهٔ استراتژیِ کاذب) را
رد می‌کند با فاصلهٔ ۰.۳۳۰ واحدِ z. سه محور بسته شده است:
* S390 — هندسه (۲۸ سلول): افت تعمیر نشد.
* S391 — فیلترِ تک‌شرطی (۱۳ سلول): ساعتِ ۷–۱۷ افت را به ۶.۶۳٪ رساند ✅.
* S392 — مشترک (۱۰ سلول): **هیچ بهبودی**؛ قانونِ رقیق‌شدن روی محورِ هندسه.

S392 ثابت کرد `z ∝ alpha·√n` ⇒ خریدنِ n هرگز جواب نمی‌دهد (سود جذری،
زیان خطی). تنها محورِ باز: **بالا بردنِ آلفا**.

قیدِ دوگانه (محاسبه‌شده در پیش‌ثبتِ S393، پیش از اجرا)
---------------------------------------------------
    se = 1.6559 | alpha_required = z_bar·se = 6.737 | alpha_now = 5.96
    DEFICIT = +0.777 ؛ و با نگه‌داشتِ ρ:  alpha_req = 6.737/√ρ
⇒ نه فیلترِ سخت‌گیر (ρ کوچک ⇒ سقف نجومی)، نه فیلترِ بی‌اثر.
   **ناحیهٔ زنده:** ρ ≥ ۰.۸۰ همراه با جهشِ آلفایِ ≥ ۱.۶ واحد.
   قیدِ همزمان: افت باید زیرِ ۸.۰٪ بماند (فعلاً ۶.۶۳ ⇒ حاشیهٔ ۱.۳۷).

تستِ توأمِ ابطال‌پذیری (افزودهٔ روش‌شناختیِ این گام)
--------------------------------------------------
فیلترهای `donch55_pos_lt_*` **جهتِ مخالفِ** `donch55_pos_gt_*` هستند.
اگر اثر واقعی باشد، جهتِ مخالف باید آلفا را **کم** کند. اگر **هر دو جهت**
آلفا را بالا ببرند، یافته مصنوعی است و رد می‌شود — بی‌توجه به z آن.
گام‌های قبل این تست را نداشتند.

محافظِ صحت (از S391)
--------------------
خطِ مبنا روی زیرمجموعهٔ `hour∈[7,17] AND filter` بازساخته می‌شود. بدونِ این،
اثرِ فیلتر «مهارت» ثبت می‌شود — همان تله‌ای که فیلترهای ER/ADX را لو داد
(آلفایشان منفی شد در حالی که lift مثبت بود).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R  # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s393')
os.makedirs(OUT, exist_ok=True)

CARD, RULE, ASSET = 'XAUUSD_H1', 'cci20_xup_135', 'XAUUSD'
COST_PIP = 3.3
SEED, K_PERM, STRIDES = 20260805, 2000, (1, 3, 7)

# قفل‌شده — هندسه (S390) و فیلترِ اول (S391)
SL_K, RR = 1.5, 2.2
HOUR_LO, HOUR_HI = 7, 17

N_TRIALS = 23913          # ۲۳٬۸۹۷ + ۱۶
DD_MAX = 8.0
ALPHA_REQ_BASE = 6.737    # در n=۸۶۱ ؛ با ρ ⇒ /√ρ


def _cci(df, p=20):
    tp = (df['high'] + df['low'] + df['close']).astype(float) / 3.0
    ma = tp.rolling(p).mean()
    md = (tp - ma).abs().rolling(p).mean()
    return (tp - ma) / (0.015 * md.replace(0.0, np.nan))


def _ema(s, p):
    return pd.Series(s).astype(float).ewm(span=p, adjust=False).mean()


def build_filters(df):
    """۱۵ فیلتر + شاهد. مقادیر عمداً غیررند (اشتباهِ رایجِ ۷)."""
    n = len(df)
    c20 = _cci(df, 20)
    excess = (c20 - 135.0).to_numpy()          # H-INT شدتِ عبور
    slope = (c20 - c20.shift(1)).to_numpy()    # H-INT سرعتِ عبور

    hh = df['high'].astype(float).rolling(55).max()
    ll = df['low'].astype(float).rolling(55).min()
    pos = ((df['close'].astype(float) - ll) /
           (hh - ll).replace(0.0, np.nan)).to_numpy()   # H-LOC

    cl = df['close'].astype(float)
    e89 = (cl - _ema(cl, 89)).to_numpy()
    e144 = (cl - _ema(cl, 144)).to_numpy()               # H-MTF
    m34 = (cl - cl.shift(34)).to_numpy()
    m55 = (cl - cl.shift(55)).to_numpy()

    def gt(a, t):
        return np.nan_to_num(a, nan=-1e18) > t

    def lt(a, t):
        return np.nan_to_num(a, nan=+1e18) < t

    out = [('none', np.ones(n, dtype=bool))]
    for t in (7, 19, 34):
        out.append((f'cci_excess_gt_{t}', gt(excess, t)))
    for t in (23, 41, 67):
        out.append((f'cci_slope_gt_{t}', gt(slope, t)))
    for t in (0.62, 0.78, 0.91):
        out.append((f'donch55_pos_gt_{t}', gt(pos, t)))
    for t in (0.55, 0.72):                      # جهتِ مخالف — تستِ توأم
        out.append((f'donch55_pos_lt_{t}', lt(pos, t)))
    out.append(('above_ema89', gt(e89, 0.0)))
    out.append(('above_ema144', gt(e144, 0.0)))
    out.append(('mom34_up', gt(m34, 0.0)))
    out.append(('mom55_up', gt(m55, 0.0)))
    return out


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_cell(L, NM, df, sig_base, hmask, fname, fmask,
             atr_med, ps, span, n_base):
    keep = np.asarray(hmask).astype(bool) & np.asarray(fmask).astype(bool)
    sig = np.asarray(sig_base).astype(bool) & keep
    n_sig = int(sig.sum())

    sl_abs = atr_med * SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * RR
    tr = L.simulate_trades(df, pd.Series(sig, index=df.index),
                           sl_abs, RR, True, ps)
    n = len(tr)
    rho = (n / n_base) if n_base else None
    base = dict(card=CARD, rule=RULE, filt=fname, sl_k=SL_K, rr=RR,
                hour_lo=HOUR_LO, hour_hi=HOUR_HI,
                span_years=round(span, 2), n_signals=n_sig, n_trades=n,
                retention=round(rho, 4) if rho else None,
                sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2))
    if n < 300:
        base['verdict'] = 'TOO_FEW_TRADES'
        return base

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)

    # ── مدلِ صفر روی همان زیرمجموعه (محافظِ S391) ─────────────────────
    _bk = L.RR
    try:
        L.RR = RR
        sub = df.loc[keep].reset_index(drop=True)
        unc = max(NM.uncond_baseline(L, sub, sl_abs, ps, s)[0] or -1e9
                  for s in STRIDES)
        perm = NM.perm_baseline(L, sub, sl_abs, ps, n_sig,
                                k=K_PERM, seed=SEED)
    finally:
        L.RR = _bk

    null = {'long': dict(uncond_wr=unc, perm_mean=perm['mean'],
                         perm_sd=perm['sd'], perm_max=perm['max'],
                         perm_k=perm['k']),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=df['time'].to_numpy(),
                         close=df['close'].to_numpy(float),
                         null=null, n_trials=N_TRIALS,
                         split_bar=int(0.70 * len(df)))
    g = res.get('gates') or {}
    wins = int((tr['outcome'] == 'win').sum())
    alpha = wr - unc
    areq = ALPHA_REQ_BASE / np.sqrt(rho) if rho else None
    base.update(
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        per_year=round(n / span, 1),
        uncond_wr=round(unc, 2), alpha=round(alpha, 2),
        alpha_required=round(float(areq), 2) if areq else None,
        alpha_margin=round(float(alpha - areq), 2) if areq else None,
        perm_max=round(perm['max'], 2),
        gap_to_perm_max=round(wr - perm['max'], 2),
        z_obs=round(R.binom_z(wins, n, unc / 100.0), 3),
        z_bar=round(R.expected_max_z(N_TRIALS), 4),
        rqs2=res.get('rqs2_score'), verdict=res.get('verdict'),
        gates=g, n_gates_fail=sum(1 for v in g.values() if v is False),
        failed_gates=sorted(k for k, v in g.items() if v is False))
    for k in ('profit_factor', 'net_profit', 'skill_z', 'max_dd_pct',
              'expectancy_pip', 'max_consec_losses'):
        base[k] = res.get(k)
    base['all_gates'] = bool(base['n_gates_fail'] == 0)
    return base


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    bank = dict(RB.build_rules())
    zbar = R.expected_max_z(N_TRIALS)

    print(f'S393 alpha-filter | {RULE} @ {CARD} | LOCKED sl_k={SL_K} '
          f'rr={RR} hour=[{HOUR_LO},{HOUR_HI}]')
    print(f'n_trials={N_TRIALS} z_bar={zbar:.4f} K={K_PERM} '
          f'alpha_req(rho=1)={ALPHA_REQ_BASE} dd_max={DD_MAX}')
    print()

    df = L.load(CARD)
    ps = L.pip_size(ASSET)
    atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    sig_base = np.asarray(bank[RULE](df)).astype(bool)
    hr = df['dt'].dt.hour.to_numpy()
    hmask = (hr >= HOUR_LO) & (hr <= HOUR_HI)

    filters = build_filters(df)
    print(f'bars={len(df)} span={span:.2f}y filters={len(filters)}')
    print()
    print('%-22s %5s %5s %6s %7s %7s %7s %7s %6s %6s %s' % (
        'filter', 'n', 'rho', 'wr', 'unc', 'alpha', 'a_req', 'z_obs',
        'dd', 'pf', 'fails'))
    print('-' * 118)

    n_base = 861
    for fname, fmask in filters:
        fn = os.path.join(OUT, f'{fname}.json')
        if os.path.exists(fn):
            r = json.load(open(fn))
        else:
            r = run_cell(L, NM, df, sig_base, hmask, fname, fmask,
                         atr_med, ps, span, n_base)
            json.dump(r, open(fn, 'w'), indent=1)
        if r.get('verdict') == 'TOO_FEW_TRADES':
            print('%-22s %5d TOO_FEW (rho=%.3f)' % (
                fname, r['n_trades'], r['retention'] or 0))
            continue
        print('%-22s %5d %5.3f %6.2f %7.2f %+7.2f %7.2f %7.3f %6.2f '
              '%6.3f %s' % (
                  fname, r['n_trades'], r['retention'] or 0, r['wr'],
                  r['uncond_wr'], r['alpha'], r['alpha_required'] or 0,
                  r['z_obs'], r.get('max_dd_pct') or 0,
                  r.get('profit_factor') or 0,
                  ','.join(r['failed_gates']) or 'ALL-PASS'))
    print()
    print('done.')


if __name__ == '__main__':
    main()
