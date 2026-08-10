# -*- coding: utf-8 -*-
"""
s434_lowvol_adjudicate.py — داوریِ کاملِ RQS2 v2.6 برای **بازویِ کم‌نوسان**
================================================================================

طبقِ پیش‌ثبتِ گامِ ۶۴ (`results/S434_PREREG_LOWVOL_ARM_ADJUDICATION.md`).

چرا فایلِ **جداگانه** و نه ویرایشِ داورِ گامِ ۲۵:
    نامزدِ قفل‌شدهٔ گامِ ۲۴ حکمِ نهایی گرفته (`REJECT · RQS2 = ۱۸.۷`). دست‌زدن به
    `CAND` در `s434_adjudicate.py` یعنی بازنویسیِ نامزدی که حکمش صادر شده — عیناً
    همان «جانشین‌کردنِ ترکیبِ زیباتر پس از دیدنِ حکم» که در گامِ ۲۴ ممنوع کردم.
    این فایل داورِ اصلی را **وارد** می‌کند و فقط یک ماسکِ اضافه روی سیگنالش می‌زند.

چرا `n_trials = ۱۲۹۹` و نه ۱۲۹۶:
    جاروبِ اصلی ۱۲۹۶ + سه بازوی کوانتایلِ گامِ ۶۲ = ۱۲۹۹. اسکنِ ۴۰۱ اندیکاتور
    **صفر** اضافه می‌کند چون بک‌تست نبود، فقط AUC. کم‌شمردن = اشتباهِ رایجِ ۸.

سه محافظ که از گران‌ترین درس‌های این مأموریت آمده‌اند:
    1. `natr` با `shift(1)` — فیلتر فقط اطلاعاتِ تا `signal_bar` را می‌بیند.
    2. آستانه از **کوانتایلِ خودِ سیگنال‌ها** گرفته می‌شود نه از کلِ سری، چون
       کوانتایلِ کلِ سری شاملِ کندل‌هایی است که هرگز سیگنال نمی‌دهند و آستانه را
       به جای بی‌ربطی می‌برد.
       ⚠️ ولی این آستانه از **کلِ تاریخ** حساب می‌شود که یک نگاهِ خفیف به آینده
       است. در §گزارش صریحاً افشا می‌شود و نسخهٔ **گسترشی** (expanding) هم
       سنجیده می‌شود تا معلوم شود اثرش چقدر است.
    3. مدلِ صفرِ **اختصاصیِ هر بازو** با ۴۰ جای‌گشت — نه قرض‌گرفته (تلهٔ ۱ گامِ ۳۳)،
       و خطِ مبنای بی‌قید **با** تریلینگ/BE (درسِ `BUG-NULLUNCOND` گامِ ۳۷).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.rqs2 import compute_rqs2                       # noqa: E402
from engine import scalp_engine as se                      # noqa: E402
from engine import indicator_bank as ib                    # noqa: E402
import tools.s434_fast_data as fd                          # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s434_lowvol')

# 🔒 حسابداریِ صادقانهٔ آزمون‌ها — پیش‌ثبتِ گامِ ۶۴
N_TRIALS = 1299
N_PERM = 40
SEED = 7
UNC_CAP = 50_000        # درسِ گامِ ۴۶


def _load_adj():
    spec = importlib.util.spec_from_file_location(
        'adj', os.path.join(ROOT, 'tools', 's434_adjudicate.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _wr(tr):
    if tr is None or len(tr) == 0:
        return None
    p = tr['pnl_pip'].values
    return float(100.0 * (p > 0).sum() / len(p))


def build_arm(adj, asset: str, tf: str, keep_frac: float,
              expanding: bool = False):
    """ماسکِ سیگنالِ بازویِ کم‌نوسان + هندسهٔ به‌ارث‌رسیده از نامزدِ قفل‌شده."""
    run = adj.run_candidate(asset, tf)
    d, df = run['d'], run['df']
    n = len(df)

    base = fd.session_open_signal(d, adj.CAND['hours'], adj.CAND['sig_mode'])
    reg = adj.regime_mask(d, adj.CAND['regime_kind'],
                          adj.CAND['regime_days'], tf)
    sig_full = base & reg

    natr = np.asarray(ib.compute('natr', df), dtype=float)
    natr_lag = np.concatenate([[np.nan], natr[:-1]])       # محافظِ ۱: shift(1)

    idx = np.flatnonzero(sig_full)
    vals = natr_lag[idx]

    if expanding:
        # نسخهٔ بدونِ هیچ نگاهِ آینده: آستانهٔ هر سیگنال فقط از سیگنال‌های
        # **قبلی** حساب می‌شود. ۵۰ سیگنالِ اول گرم‌کردن‌اند و رد می‌شوند.
        keep = np.zeros(len(idx), bool)
        for i in range(50, len(idx)):
            hist = vals[:i]
            hist = hist[np.isfinite(hist)]
            if len(hist) < 30 or not np.isfinite(vals[i]):
                continue
            keep[i] = vals[i] <= np.quantile(hist, keep_frac)
    else:
        thr = np.nanquantile(vals, keep_frac)
        keep = np.isfinite(vals) & (vals <= thr)

    sig = np.zeros(n, bool)
    sig[idx[keep]] = True
    return run, sig, d, df


def adjudicate_arm(adj, asset: str, tf: str, keep_frac: float,
                   expanding: bool = False, oos_frac: float = 0.30) -> dict:
    t0 = time.time()
    run, sig, d, df = build_arm(adj, asset, tf, keep_frac, expanding)
    sl, tp, mh = run['sl'], run['tp'], run['max_hold']
    tl, be = run['trail'], run['be_trigger']
    n = len(df)
    z0 = np.zeros(n, bool)

    tr = se.simulate_trades(df, sig, z0, sl, tp, asset, max_hold=mh,
                            allow_overlap=False, be_trigger_pip=be,
                            trail_pip=tl)
    if tr is None or len(tr) < 30:
        return {'asset': asset, 'tf': tf, 'keep_frac': keep_frac,
                'expanding': expanding,
                'error': f'n={0 if tr is None else len(tr)} < 30'}

    # ── مدلِ صفرِ اختصاصیِ همین بازو ──────────────────────────────────────
    valid = np.zeros(n, bool)
    valid[250:n - mh - 1] = True
    vidx = np.flatnonzero(valid)

    unc_mask = valid
    if int(valid.sum()) > UNC_CAP:
        rng_u = np.random.default_rng(SEED + 101)
        pick = rng_u.choice(vidx, size=UNC_CAP, replace=False)
        unc_mask = np.zeros(n, bool)
        unc_mask[pick] = True
    tr_unc = se.simulate_trades(df, unc_mask, z0, sl, tp, asset, max_hold=mh,
                                allow_overlap=True, be_trigger_pip=be,
                                trail_pip=tl)          # درسِ BUG-NULLUNCOND
    wr_unc = _wr(tr_unc)

    k = min(int(sig.sum()), len(vidx))                 # تلهٔ ۱: k همین بازو
    rng = np.random.default_rng(SEED)
    ws = []
    for _ in range(N_PERM):
        pm = np.zeros(n, bool)
        pm[rng.choice(vidx, size=k, replace=False)] = True
        w = _wr(se.simulate_trades(df, pm, z0, sl, tp, asset, max_hold=mh,
                                   allow_overlap=False, be_trigger_pip=be,
                                   trail_pip=tl))
        if w is not None:
            ws.append(w)
    pa = np.array(ws, float)
    null = {'long': {'uncond_wr': wr_unc,
                     'perm_mean': float(pa.mean()) if pa.size else None,
                     'perm_sd': float(pa.std(ddof=1)) if pa.size > 1 else None,
                     'perm_max': float(pa.max()) if pa.size else None,
                     'perm_k': int(k)},
            'short': {}}

    split_bar = int(n * (1.0 - oos_frac))
    res = compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                       bar_time=d['time'], close=d['close'],
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)

    m = res.get('metrics') or {}
    g = res.get('gates') or {}
    out = {
        'asset': asset, 'tf': tf,
        'arm': f'lowvol natr keep_bottom_{int(keep_frac * 100)}pct'
               + (' [EXPANDING]' if expanding else ' [full-history threshold]'),
        'keep_frac': keep_frac, 'expanding': expanding,
        'n_trials_declared': N_TRIALS,
        'geometry': {'sl_pip': sl, 'tp_pip': tp, 'ratio': round(tp / sl, 4),
                     'trail': tl, 'be': be, 'max_hold': mh},
        'n_signals': int(sig.sum()),
        'null': null['long'],
        'verdict': res.get('verdict'), 'rqs2_score': res.get('rqs2_score'),
        'gates': {kk: g.get(kk) for kk in sorted(g)},
        'failed_gates': sorted(kk for kk, v in g.items() if v is False),
        'unknown_gates': sorted(kk for kk, v in g.items() if v is None),
        'metrics': {kk: m.get(kk) for kk in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'expectancy_at_2x_cost')},
        'notes': [str(x) for x in (res.get('notes') or [])][:8],
        'secs': round(time.time() - t0, 1),
    }
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tf', default='M30')
    ap.add_argument('--keeps', default='0.75,0.50')
    ap.add_argument('--expanding', action='store_true')
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    adj = _load_adj()
    print(f'[داوریِ بازویِ کم‌نوسان] {a.asset}-{a.tf} · '
          f'n_trials={N_TRIALS} · {N_PERM} جای‌گشت/بازو')
    print(f'  سدها: H3 lift ≥ 4.0pp و z ≥ 3.09 | H5: z ≥ 3.329')
    sys.stdout.flush()

    for kf in [float(x) for x in a.keeps.split(',') if x.strip()]:
        try:
            out = adjudicate_arm(adj, a.asset, a.tf, kf, a.expanding)
        except Exception as e:                              # noqa: BLE001
            print(f'  !! keep={kf}: {type(e).__name__}: {e}')
            sys.stdout.flush()
            continue
        tag = f'{int(kf * 100)}pct' + ('_exp' if a.expanding else '')
        fp = os.path.join(OUT_DIR, f'lowvol_{a.asset}_{a.tf}_{tag}.json')
        with open(fp, 'w', encoding='utf-8') as f:          # 🔒 قانونِ سوم
            json.dump(out, f, ensure_ascii=False, indent=1)
        if 'error' in out:
            print(f'  [keep {kf}] {out["error"]}')
            sys.stdout.flush()
            continue
        m = out['metrics']
        print(f'\n═══ keep_bottom_{int(kf * 100)}% '
              f'{"[EXPANDING]" if a.expanding else ""} ═══ ({out["secs"]}s)')
        print(f'  حکم = {out["verdict"]}   RQS2 = {out["rqs2_score"]}')
        print(f'  n={m["n_trades"]} WR={m["win_rate"]}% PF={m["profit_factor"]}')
        print(f'  lift={m["skill_lift_pp"]}pp z={m["skill_z"]} '
              f'null_ref={m["null_ref_wr"]}')
        print(f'  maxDD={m["max_dd_pct"]}% MCL={m["max_consec_losses"]}/'
              f'{m["mcl_allowed"]} rec={m["recovery_factor"]}')
        print(f'  افتاده: {out["failed_gates"] or "هیچ ✅"}  '
              f'نامعلوم: {out["unknown_gates"] or "هیچ"}')
        sys.stdout.flush()
    print('\n[done]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
