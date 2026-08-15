# -*- coding: utf-8 -*-
"""
s560_adjudicate.py — داورِ S560 (گپ-بازگشایی XAUUSD) — مسیر C

پیش‌ثبت: results/S560_PREREG_GAPOPEN_XAUUSD_MISSION1.md (commit 0f0eab53)

دو فاز:
  lock  — فقط نیمهٔ اول: بازوی منتخبِ هر TF (از جدول‌های results/_s560_explore/)
          + هندسهٔ داده-محور، مقایسهٔ دو واریانت هندسهٔ پیش‌ثبت‌شده روی موتور
          رسمی، و **قفل** در JSON. (BUG-GEOMDRIFT: داور از همین فایل می‌خواند.)
  judge — یک بار و فقط یک بار: کل داده + null اختصاصی (perm_k>=500) +
          compute_rqs2 با هر پنج ورودی لازم + split_bar = مرز 2018-10-20 (H7).

گاردهای ارثی: BUG-PERMK · BUG-NULLUNCOND · BUG-SCOREKEY (نگاشت عیناً از
s437_adjudicate کپی شد) · BUG-PIPGUESS (pip از موتور) · قید ۲ (n<30 حکم ندارد)
· BUG-BRKTHRESH (مرز روز مقیاس‌پذیر با TF — از s560_gapopen_explore وارد می‌شود).

اجرا:
  python3 tools/s560_adjudicate.py lock  M5
  python3 tools/s560_adjudicate.py judge M5
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2 import compute_rqs2, n_required_for_h3    # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402
from tools.s560_gapopen_explore import (                   # noqa: E402
    day_breaks, causal_neg_gap_quantile, SPLIT_UTC)

N_TRIALS = 400        # پیش‌ثبت §۴ — سقف صادقانهٔ فضای جست‌وجو
N_PERM = 500          # H3 الزام: K>=500
SEED = 20260813
OUT = os.path.join(ROOT, 'results', '_s560_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')

# بازوی منتخبِ هر TF از اکتشاف نیمهٔ اول (results/_s560_explore/<TF>.json —
# بالاترین t با n>=100). اینجا فقط «نامزد» است؛ قفلِ نهایی پس از فاز lock.
BEST = {
    'M1':  dict(q=80, sw=True, hold=4),
    'M5':  dict(q=80, sw=True, hold=1),
    'M15': dict(q=70, sw=True, hold=1),
    'M30': dict(q=80, sw=True, hold=1),
    'H1':  dict(q=80, sw=True, hold=2),
}


def _pip(asset: str) -> float:
    spec = getattr(se, 'ASSETS', {}).get(asset, {})
    p = spec.get('pip') or spec.get('pip_size')
    if p is None:
        raise RuntimeError('pip not readable from engine')  # BUG-PIPGUESS
    return float(p)


def build(tf: str):
    """داده + ماسک سیگنال (روی *آخرین کندل روز قبل* — ورود موتور در open کندل
    اول روز؛ گپ در لحظهٔ ورود مشاهده‌پذیر است، نه آینده‌نگر)."""
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    t, o, c = d['time'], d['open'], d['close']
    n = len(t)
    import calendar
    split_ts = calendar.timegm((2018, 10, 20, 0, 0, 0))
    split_bar = int(np.searchsorted(t, split_ts))

    brk = day_breaks(t, tf)              # i = آخرین کندل روز
    brk = brk[brk + 1 < n]
    gaps = o[brk + 1] - c[brk]
    weekend = (t[brk + 1] - t[brk]) > 86400

    cfg = BEST[tf]
    thr = causal_neg_gap_quantile(gaps, cfg['q'], weekend, cfg['sw'])
    cond = (gaps < 0) & ~np.isnan(thr) & (np.abs(gaps) > thr)
    mask = np.zeros(n, bool)
    mask[brk[cond]] = True               # موتور در o[brk+1] وارد می‌شود
    return d, df, mask, split_bar, cfg


def geometry_variants(d, mask, hold, asset, split_bar):
    """دو واریانت هندسهٔ پیش‌ثبت‌شده — چندک‌ها فقط از نیمهٔ اول.

    V-BRK: TP=q60(MFE) · SL=q30(MAE)  (قاعدهٔ ارثی S437، بدون جاروب)
    V-TIME: خروج زمانی خالص؛ براکتِ متقارنِ نادر-فعال SL=TP=q98(|MFE|∪|MAE|)
            (تا موتور SL/TP معتبر داشته باشد ولی عملاً زمان حاکم بماند —
            سازگار با کشف دم‌های ۱۱۸× و «استاپ قیمتی مخرب است»)
    """
    pip = _pip(asset)
    h, l, o = d['high'], d['low'], d['open']
    n = len(o)
    idx = np.flatnonzero(mask)
    idx = idx[idx + 1 + hold < min(split_bar, n)]   # فقط نیمهٔ اول
    mfes, maes = [], []
    for i in idx:
        e = i + 1                                    # کندل ورود
        j1 = min(e + hold, n)
        entry = o[e]
        mfes.append((h[e:j1].max() - entry) / pip)
        maes.append((entry - l[e:j1].min()) / pip)
    mfes, maes = np.array(mfes), np.array(maes)
    tp_b = round(float(np.percentile(mfes, 60)), 1)
    sl_b = round(float(np.percentile(maes, 30)), 1)
    wide = round(float(np.percentile(np.concatenate([mfes, maes]), 98)), 1)
    return {
        'V-BRK':  dict(sl=max(sl_b, 1.0), tp=max(tp_b, 1.0), mh=hold,
                       rule='TP=q60(MFE)·SL=q30(MAE) [first half]'),
        'V-TIME': dict(sl=wide, tp=wide, mh=hold,
                       rule='SL=TP=q98(|MFE|∪|MAE|) [first half] — time exit'),
    }


def first_half_t(tr, split_bar):
    m = tr[tr['exit_bar'] < split_bar]
    p = m['pnl_pip'].values.astype(float)
    if len(p) < 30:
        return None, len(p)
    se_ = p.std(ddof=1) / np.sqrt(len(p))
    return (float(p.mean() / se_) if se_ > 0 else 0.0), len(p)


def phase_lock(tf: str):
    d, df, mask, split_bar, cfg = build(tf)
    print(f"src={d['src']}  signals={int(mask.sum())}  split_bar={split_bar}")
    variants = geometry_variants(d, mask, cfg['hold'], 'XAUUSD', split_bar)
    scored = {}
    for name, g in variants.items():
        z = np.zeros(len(df), bool)
        tr = se.simulate_trades(df, mask, z, g['sl'], g['tp'], 'XAUUSD',
                                max_hold=g['mh'], allow_overlap=False)
        t_fh, n_fh = first_half_t(tr, split_bar)
        wr_fh = None
        if n_fh >= 30:
            m = tr[tr['exit_bar'] < split_bar]
            wr_fh = round(float((m['pnl_pip'] > 0).mean() * 100), 2)
        scored[name] = dict(**g, t_first_half=t_fh, n_first_half=n_fh,
                            wr_first_half=wr_fh)
        print(f"  {name}: sl={g['sl']} tp={g['tp']} mh={g['mh']} "
              f"→ نیمهٔ اول t={t_fh} n={n_fh} WR={wr_fh}")
    # انتخاب: t نیمهٔ اول بالاتر (فقط دادهٔ مجازِ مسیر C)
    pick = max((k for k in scored if scored[k]['t_first_half'] is not None),
               key=lambda k: scored[k]['t_first_half'], default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = {}
    if os.path.exists(LOCK_PATH):
        lock = json.load(open(LOCK_PATH))
    lock[tf] = dict(cfg=cfg, variants=scored, picked=pick,
                    split_bar=int(split_bar), split_utc=SPLIT_UTC,
                    src=d['src'], n_signals=int(mask.sum()))
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """نال اختصاصی همین بازو/هندسه — عیناً الگوی s437 (گارد ②)."""
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
    tu = se.simulate_trades(df, um, z, sl, tp, 'XAUUSD', max_hold=mh,
                            allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if len(tu) else None
    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, 'XAUUSD', max_hold=mh,
                               allow_overlap=False)
        if len(t):
            perm.append(100.0 * float((t['pnl_pip'].values > 0).mean()))
    pa = np.array(perm, float)
    return {'long': dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=int(pa.size)),           # گارد ① BUG-PERMK
            'short': {}}


def phase_judge(tf: str):
    lock = json.load(open(LOCK_PATH))
    if tf not in lock or not lock[tf].get('picked'):
        raise SystemExit(f'{tf} قفل نشده — اول فاز lock')
    L = lock[tf]
    g = L['variants'][L['picked']]
    sl, tp, mh = float(g['sl']), float(g['tp']), int(g['mh'])
    d, df, mask, split_bar, cfg = build(tf)
    assert L['n_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT: ماسک ناهمسان با قفل'

    # غربال توان (توصیهٔ ۴ گزارش S437) — قبل از خرج نال
    z0 = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z0, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n_tr = len(tr)
    print(f"src={d['src']}  arm={L['picked']} sl={sl} tp={tp} mh={mh} n={n_tr}")
    if n_tr < 30:
        res_out = dict(tf=tf, error=f'n<30 (n={n_tr})', invalid=True)
    else:
        null = null_for(df, mask, sl, tp, mh)
        res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                           bar_time=df['time'].values,
                           close=df['close'].values,
                           null=null, n_trials=N_TRIALS, split_bar=split_bar,
                           initial_capital=10000.0, allow_overlap=False)
        gt = res.get('gates') or {}
        m = res.get('metrics') or {}
        lift = m.get('skill_lift_pp')
        p0 = (null['long']['uncond_wr'] or 50.0) / 100.0
        n_need = n_required_for_h3(lift, p0) if lift else float('inf')
        res_out = {
            'tf': tf, 'arm': L['picked'],
            'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                             rr=round(tp / sl, 3), rule=g['rule']),
            'cfg': cfg, 'n_signals': int(mask.sum()),
            'verdict': res.get('verdict'),
            'rqs2_score': res.get('rqs2_score'),
            'gates': {k: gt.get(k) for k in sorted(gt)},
            'failed_gates': sorted(k for k, v in gt.items() if v is False),
            'unknown_gates': sorted(k for k, v in gt.items() if v is None),
            'null': null['long'], 'n_trials': N_TRIALS,
            'n_required_for_h3': (None if n_need == float('inf')
                                  else round(float(n_need), 1)),
            'split_bar': split_bar, 'split_utc': SPLIT_UTC, 'src': d['src'],
            'metrics': {k: m.get(k) for k in (
                'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
                'profit_factor', 'net_profit', 'max_dd_pct',
                'max_consec_losses', 'mcl_allowed', 'recovery_factor',
                'skill_lift_pp', 'skill_z', 'null_ref_wr',
                'breakeven_wr_cost', 'rr', 'top_win_share', 'z_obs',
                'z_luck_bound', 'z_margin', 'skill_p_perm', 'p_emp',
                'p_adj_bonferroni', 'perm_k', 'perm_max')},
            'notes': [str(x) for x in (res.get('notes') or [])],
        }
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'judge_{tf}.json')
    json.dump(res_out, open(path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: res_out.get(k) for k in
                      ('verdict', 'rqs2_score', 'failed_gates',
                       'unknown_gates', 'n_required_for_h3')},
                     ensure_ascii=False))
    mm = res_out.get('metrics') or {}
    print(f"WR={mm.get('win_rate')} lift={mm.get('skill_lift_pp')} "
          f"z={mm.get('skill_z')} p_perm={mm.get('skill_p_perm')} "
          f"perm_k={(res_out.get('null') or {}).get('perm_k')}")
    print(f"saved → {path}")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    (phase_lock if phase == 'lock' else phase_judge)(tf)
