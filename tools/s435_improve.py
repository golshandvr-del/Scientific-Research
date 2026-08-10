# -*- coding: utf-8 -*-
"""
s435_improve.py — داوریِ **بازوهای بهبودِ** `I1` و `I2` (پیش‌ثبتِ گامِ ۹۰)

چرا این فایل جدا از `s435_adjudicate.py` است
---------------------------------------------
داورِ قبلی هندسه را از `cov.CAND` می‌خواند و **ثابت** است. بازوی `I2`
هندسه را عوض می‌کند، پس اگر همان فایل را دست‌کاری می‌کردم، حکم‌های گامِ ۸۸
دیگر با کدِ مخزن بازتولیدپذیر نبودند — یعنی سندِ منتشرشده و ابزارِ تولیدش
از هم جدا می‌افتادند. فایلِ جدا این را حفظ می‌کند.

بازوها — دقیقاً همان دو تا که در گامِ ۹۰ قفل شدند
--------------------------------------------------
  `I1`  سیگنالِ SoS **بدونِ** فیلترِ ATR · هندسهٔ اصلی (SL=250, TP=750, MH=96)
  `I2`  همان سیگنال · هندسهٔ هم‌تراز با افق (SL=250, TP=p75(MFE), MH=96)

⚠️ محافظ‌های ضدِ خطاهای شناخته‌شدهٔ این مأموریت
-------------------------------------------------
* `BUG-NULLUNCOND` (گامِ ۳۷): خطِ مبنا **با همان هندسهٔ همان بازو** اجرا
  می‌شود. چون `I1` و `I2` هندسهٔ متفاوت دارند، هرکدام مدلِ صفرِ **خودش**
  را می‌گیرد. قرض‌گرفتنِ مدلِ صفرِ `I1` برای `I2` یعنی مقایسهٔ سیب و پرتقال.
* `BUG-PERMK` (گامِ ۸۷): `perm_k` = **تعدادِ جای‌گشت‌ها** (`pa.size`)، نه
  اندازهٔ نمونه. موتور با `PERM_K_MIN=500` مقایسه‌اش می‌کند.
* `BUG-PIPGUESS` (گامِ ۹۱): هر ثابتی که در موتور زندگی می‌کند، **از موتور
  خوانده می‌شود** — اینجا `pip` از `se.ASSETS`، نه از حافظهٔ من.
* تلهٔ ۱ (گامِ ۳۳): مدلِ صفرِ **اختصاصیِ هر بازو** با اندازهٔ نمونهٔ همان بازو.
* `n_trials = 292` — افزایشی و **علیهِ خودم**: ۲۶۷ (S202) + ۲۰ (جاروبِ
  S204) + ۳ (بازوهای گامِ ۸۵) + ۲ (`I1`,`I2`). سد: z ≥ √(2 ln 292) ≈ ۳.۳۷.

اجرا:
    cd /home/user/webapp && PYTHONPATH=. python3 tools/s435_improve.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as se            # noqa: E402
from engine.rqs2 import compute_rqs2             # noqa: E402
import tools.s435_coverage_union as cov          # noqa: E402

OUT = 'results/_s435_improve'

# 🔒 پیش‌ثبتِ گامِ ۹۰ — افزایشی و علیهِ خودم
N_TRIALS = 292
N_PERM = 500
SEED = 7
ASSET = 'XAUUSD'


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def derive_i2_target(df, sig) -> dict:
    """`TP` بازوی `I2` را از **خودِ داده** می‌گیرد — نه از یک شبکهٔ اعداد.

    تعریف: چندکِ ۷۵٪ِ حداکثرِ سودِ محقق‌نشده (MFE) در پنجرهٔ `max_hold`.
    یعنی عددی که ۷۵٪ سیگنال‌ها به آن می‌رسند، در برابرِ `TP=750` که فقط
    ~۱۰٪ به آن می‌رسند.

    ⚠️ `pip` از موتور خوانده می‌شود (`BUG-PIPGUESS`, گامِ ۹۱).
    ⚠️ قیدِ سختِ پیش‌ثبت‌شده: اگر `TP < SL` شد، بازو **لغو** می‌شود، چون
       آن‌وقت WR با کوچک‌کردنِ هدف خریده می‌شود = اشتباهِ رایجِ ۸.
    """
    pip = se.ASSETS[ASSET]['pip']
    mh = cov.CAND['max_hold']
    sl = cov.CAND['sl']
    hi = df['high'].to_numpy()
    lo = df['low'].to_numpy()
    op = df['open'].to_numpy()
    n = len(df)
    mfe, mae = [], []
    for i in np.flatnonzero(sig):
        if i + 1 + mh >= n:
            continue
        e = op[i + 1]
        mfe.append((hi[i + 1:i + 1 + mh].max() - e) / pip)
        mae.append((e - lo[i + 1:i + 1 + mh].min()) / pip)
    mfe = np.asarray(mfe, float)
    mae = np.asarray(mae, float)
    tp = float(np.percentile(mfe, 75))
    return {
        'pip_read_from_engine': pip,
        'n_signals_with_full_window': int(mfe.size),
        'mfe_pct': {f'p{q}': round(float(np.percentile(mfe, q)), 1)
                    for q in (50, 60, 70, 75, 80, 90)},
        'mae_pct': {f'p{q}': round(float(np.percentile(mae, q)), 1)
                    for q in (50, 75, 90)},
        'tp_pip': round(tp, 1),
        'sl_pip': sl,
        'rr': round(tp / sl, 3),
        'constraint_tp_ge_sl': bool(tp >= sl),
        'reach_old_tp_pct': round(100.0 * float((mfe >= cov.CAND['tp']).mean()), 1),
        'reach_new_tp_pct': round(100.0 * float((mfe >= tp).mean()), 1),
    }


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """مدلِ صفرِ **اختصاصیِ همین بازو با همین هندسه**.

    چرا هندسه اینجا پارامتر است و از `CAND` خوانده نمی‌شود: `I2` هندسهٔ
    متفاوتی دارد و مدلِ صفرش باید با **همان** `tp` ساخته شود. اگر مدلِ صفر
    با `tp=750` ساخته شود و بازو با `tp=395` اجرا، لیفت مقایسهٔ دو چیزِ
    متفاوت است و z بی‌معنا — همان `BUG-NULLUNCOND` در لباسِ نو.
    """
    n = len(df)
    z = np.zeros(n, bool)
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)

    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool)
    um[pick] = True
    tu = se.simulate_trades(df, um, z, sl, tp, ASSET, max_hold=mh,
                            allow_overlap=True)
    wr_unc = _wr(tu)

    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, ASSET, max_hold=mh,
                               allow_overlap=False)
        w = _wr(t)
        if w is not None:
            perm.append(w)
    pa = np.array(perm, float) if perm else np.array([])
    return {'long': dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=int(pa.size)),   # 🔴 تعدادِ جای‌گشت — BUG-PERMK
            'short': {}}


def adjudicate(df, mask, label, sl, tp, mh, oos_frac=0.30, extra=None):
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return {'arm': label, 'error': 'no trades'}

    null = null_for(df, mask, sl, tp, mh)
    split_bar = int(len(df) * (1.0 - oos_frac))
    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)
    g = res.get('gates') or {}
    m = res.get('metrics') or {}
    out = {
        'arm': label,
        'geometry': {'sl_pip': sl, 'tp_pip': tp, 'max_hold': mh,
                     'rr': round(tp / sl, 3)},
        'n_signals': int(mask.sum()),
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': sorted(k for k, v in g.items() if v is False),
        'unknown_gates': sorted(k for k, v in g.items() if v is None),
        'null': null['long'],
        'n_trials': N_TRIALS,
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }
    if extra:
        out['derivation'] = extra
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='I1,I2')
    a = ap.parse_args()

    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    df = cov.load_h1()
    sig = cov.sos_edge(df)                       # ⛔ بدونِ فیلترِ ATR
    sl, mh = cov.CAND['sl'], cov.CAND['max_hold']

    print(f"[S435 بهبود] XAUUSD-H1 · n_trials={N_TRIALS} · "
          f"{N_PERM} جای‌گشت/بازو · سد z≈{np.sqrt(2*np.log(N_TRIALS)):.2f}")
    print(f"  سیگنالِ SoS بدونِ ATR: {int(sig.sum())} کندل\n")

    plan = {}
    if 'I1' in a.arms:
        plan['I1'] = (cov.CAND['tp'], None)
    if 'I2' in a.arms:
        d = derive_i2_target(df, sig)
        if not d['constraint_tp_ge_sl']:
            print(f"  ⛔ I2 لغو شد: TP={d['tp_pip']} < SL={d['sl_pip']} "
                  f"⇒ قانونِ حفظِ بودجه اجازه نمی‌دهد")
            with open(os.path.join(ROOT, OUT, 'I2_CANCELLED.json'), 'w',
                      encoding='utf-8') as f:
                json.dump({'cancelled': True, 'reason':
                           'TP<SL violates budget-preservation rule',
                           'derivation': d}, f, ensure_ascii=False, indent=1)
        else:
            plan['I2'] = (d['tp_pip'], d)

    for lbl, (tp, extra) in plan.items():
        out = adjudicate(df, sig, lbl, sl, tp, mh, extra=extra)
        p = os.path.join(ROOT, OUT, f'arm_{lbl}.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        m = out.get('metrics') or {}
        print(f"  ═══ [{lbl}] {out.get('verdict')} · "
              f"RQS2={out.get('rqs2_score')} · TP={tp}")
        print(f"      n={m.get('n_trades')} WR={m.get('win_rate')} "
              f"lift={m.get('skill_lift_pp')} z={m.get('skill_z')} "
              f"PF={m.get('profit_factor')}")
        print(f"      افتاده={out.get('failed_gates')} "
              f"نامعلوم={out.get('unknown_gates')}")

    print('\n[done]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
