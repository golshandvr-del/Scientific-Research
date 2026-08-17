# -*- coding: utf-8 -*-
"""
S531 — احیای S355 با دروازهٔ رژیم · مسیر C · XAUUSD-M5
================================================================================
پیش‌ثبت: results/S531_PREREG_S355_RegimeGate_PathC.md (commit 2c10ca31 — قبل از اجرا)

دو فاز با CLI جدا تا نظمِ مسیر C **اجباری** باشد، نه اختیاری:

  search  : هر ۲۰ ترکیبِ خانوادهٔ منجمدِ S351 فقط روی bar < 544787 (نیمهٔ اول).
            انتخاب: بیشینهٔ t-آماره، مشروط به n>=30 و حذفِ >=20% معاملات.
            برنده در results/_s531/LOCKED.json قفل می‌شود. holdout دیده نمی‌شود.
  verdict : فقط اگر LOCKED.json موجود باشد. برندهٔ قفل‌شده روی کل داده +
            compute_rqs2 با split_bar=544787 و n_trials=20. **یک بار.**
            اگر verdict.json از قبل هست ⇒ توقف (هیچ اجرای دومی مجاز نیست).

اجرا:
  PYTHONPATH=. python3 strategies/s531_s355_regime_gate.py search
  PYTHONPATH=. python3 strategies/s531_s355_regime_gate.py verdict
"""
from __future__ import annotations

import json
import os
import sys
import time as _time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'strategies')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                        # noqa: E402
from engine.rqs2 import compute_rqs2, format_rqs2            # noqa: E402
import s333_s79_pullback_revival as s333                     # noqa: E402
from strategies.s351_lpsb import lpsb_signals                # noqa: E402
from strategies.s351_verdict import CENTRAL                  # noqa: E402
from strategies import bank_filters as bf                    # noqa: E402

DATA = os.path.join(ROOT, 'data', 'mt5_full', 'XAUUSD_M5.csv')
CARD_KEY = 'XAUUSD_M5'
ASSET = 'XAUUSD'
WARMUP = 200
SPLIT_BAR = 544787          # قفل‌شده در پیش‌ثبت
N_TRIALS = 20               # کلِ فضای جست‌وجو
N_PERM = 500
SEED = 20260814             # قفل‌شده در پیش‌ثبت
MIN_N = 30                  # قید ۱ پیش‌ثبت
MIN_REMOVAL = 0.20          # قید ۲ پیش‌ثبت — گاردِ عملِ همانی
OUT = os.path.join(ROOT, 'results', '_s531')

# خانوادهٔ منجمد — عیناً strategies/s351_filter.py::FILTERS (رونویسی از منبع،
# نه بازسازی از حافظه: مقادیر با فایل منبع تطبیق داده شد)
FILTERS = {
    'hurst55': (lambda df: bf.hurst(df, period=55),
                (0.50, 0.52, 0.55, 0.58, 0.618), '>='),
    'r2_34':   (lambda df: bf.r2(df, period=34),
                (0.236, 0.382, 0.5, 0.618, 0.786), '>='),
    'er_21':   (lambda df: bf.kaufman_er(df, period=21),
                (0.20, 0.30, 0.382, 0.5, 0.618), '>='),
    'chop_21': (lambda df: bf.chop(df, period=21),
                (61.8, 50.0, 45.0, 38.2, 30.0), '<='),
}


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return float((t['pnl_pip'].to_numpy() > 0).mean() * 100.0)


def load_full() -> pd.DataFrame:
    df = se.load_data(DATA)
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    t0, t1 = df['dt'].iloc[0], df['dt'].iloc[-1]
    span_y = (t1 - t0).days / 365.25
    print(f'[S531 داده] {DATA}\n[S531 داده] ردیف={len(df):,} · '
          f'{t0.date()} → {t1.date()} · {span_y:.2f} سال', flush=True)
    if span_y < 14.0:
        raise SystemExit('⛔ بازهٔ داده < ۱۴ سال ⇒ دادهٔ کامل نیست. توقف.')
    return df


def geometry() -> tuple[float, float, int]:
    cfg = s333.BEST_CFG[CARD_KEY]
    return float(cfg['sl']), float(cfg['tp']), int(cfg['mh'])


def s355_mask(df: pd.DataFrame) -> np.ndarray:
    base = s333.build_layer(df, s333.BEST_CFG[CARD_KEY])
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    return np.asarray(base, bool) & (np.asarray(state) == -1)


def keep_mask(vals: np.ndarray, thr: float, direction: str) -> np.ndarray:
    v = np.asarray(vals, float)
    ok = ~np.isnan(v)
    if direction == '>=':
        return ok & (v >= thr)
    return ok & (v <= thr)


def tstat(pnl: np.ndarray) -> float:
    if len(pnl) < 2:
        return float('-inf')
    sd = pnl.std(ddof=1)
    if sd == 0:
        return float('-inf')
    return float(pnl.mean() / (sd / np.sqrt(len(pnl))))


def phase_search() -> int:
    """فاز جست‌وجو — **فقط نیمهٔ اول**. holdout هرگز شبیه‌سازی نمی‌شود."""
    os.makedirs(OUT, exist_ok=True)
    lock_fp = os.path.join(OUT, 'LOCKED.json')
    if os.path.exists(lock_fp):
        raise SystemExit(f'⛔ {lock_fp} از قبل هست — جست‌وجوی دوم ممنوع (مسیر C).')

    df_full = load_full()
    sl, tp, mh = geometry()
    # ⚠️ برش *بعد از* محاسبهٔ ماسک نیست — کلِ محاسبه فقط روی نیمهٔ اول انجام
    # می‌شود تا حتی اندیکاتورها هم نیمهٔ دوم را نبینند.
    df = df_full.iloc[:SPLIT_BAR].reset_index(drop=True)
    print(f'[S531 جست‌وجو] فقط نیمهٔ اول: {len(df):,} کندل · '
          f'{df["dt"].iloc[-1].date()} آخرین روزِ دیده‌شده', flush=True)

    mask = s355_mask(df)
    z = np.zeros(len(df), bool)
    tr_base = se.simulate_trades(df, mask, z, sl, tp, ASSET,
                                 max_hold=mh, allow_overlap=False)
    n_base = len(tr_base)
    print(f'[S531 پایه] نیمهٔ اول بدونِ فیلتر: n={n_base} · '
          f'WR={_wr(tr_base):.2f}% · net={tr_base["pnl_pip"].sum():.1f}pip',
          flush=True)

    sig_bars = tr_base['signal_bar'].to_numpy(int)
    rows = []
    for fname, (fn, thrs, direction) in FILTERS.items():
        t0 = _time.time()
        vals = fn(df)
        print(f'[S531] {fname} محاسبه شد ({_time.time()-t0:.0f}s)', flush=True)
        for thr in thrs:
            km = keep_mask(vals, thr, direction)
            # فیلتر روی کندلِ سیگنالِ معامله اعمال می‌شود — همان معناشناسیِ
            # دروازهٔ ورود در سایت (لحظهٔ سیگنال، نه لحظهٔ fill)
            keep = km[sig_bars]
            sub = tr_base[keep]
            n = len(sub)
            removal = 1.0 - n / max(n_base, 1)
            pnl = sub['pnl_pip'].to_numpy(float)
            row = dict(filter=fname, thr=thr, n=n,
                       removal=round(removal, 4),
                       wr=_wr(sub), net_pip=float(pnl.sum()) if n else 0.0,
                       t=round(tstat(pnl), 4) if n >= 2 else None,
                       eligible=bool(n >= MIN_N and removal >= MIN_REMOVAL))
            rows.append(row)
            print(f'  {fname}@{thr}: n={n} rm={removal:.0%} '
                  f'WR={row["wr"] and round(row["wr"],1)} t={row["t"]} '
                  f'{"✓" if row["eligible"] else "·"}', flush=True)

    with open(os.path.join(OUT, 'search_grid.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    elig = [r for r in rows if r['eligible'] and r['t'] is not None]
    if not elig:
        print('[S531] ⛔ هیچ ترکیبی قیدها را پاس نکرد ⇒ قانونِ توقف: مرگِ صادقانه. '
              'holdout باز نمی‌شود.', flush=True)
        with open(os.path.join(OUT, 'STOPPED_DEAD.json'), 'w') as f:
            json.dump({'reason': 'no combo passed n>=30 AND removal>=20%'}, f)
        return 3

    win = max(elig, key=lambda r: r['t'])
    with open(lock_fp, 'w', encoding='utf-8') as f:
        json.dump({'winner': win, 'locked_at': _time.strftime('%F %T'),
                   'split_bar': SPLIT_BAR, 'seed': SEED,
                   'n_trials': N_TRIALS}, f, ensure_ascii=False, indent=1)
    print(f'[S531 قفل] برنده: {win["filter"]}@{win["thr"]} · n={win["n"]} · '
          f't={win["t"]} · WR={win["wr"]:.1f}% ⇒ LOCKED.json', flush=True)
    return 0


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """عیناً الگوی s437_adjudicate.null_for."""
    n = len(df)
    z = np.zeros(n, bool)
    valid = np.zeros(n, bool)
    valid[250:n - mh - 1] = True
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
    for i in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        w = _wr(se.simulate_trades(df, pm, z, sl, tp, ASSET, max_hold=mh,
                                   allow_overlap=False))
        if w is not None:
            perm.append(w)
        if (i + 1) % 100 == 0:
            print(f'[S531 نال] {i+1}/{n_perm}', flush=True)
    pa = np.array(perm, float)
    return {'long': dict(uncond_wr=wr_unc, perm_mean=float(pa.mean()),
                         perm_sd=float(pa.std(ddof=1)),
                         perm_max=float(pa.max()), perm_k=int(pa.size)),
            'short': {}}


def phase_verdict() -> int:
    """فاز آزمون — یک بار، فقط با پیکربندی قفل‌شده."""
    lock_fp = os.path.join(OUT, 'LOCKED.json')
    verdict_fp = os.path.join(OUT, 'verdict.json')
    if not os.path.exists(lock_fp):
        raise SystemExit('⛔ LOCKED.json نیست — اول فاز search.')
    if os.path.exists(verdict_fp):
        raise SystemExit('⛔ verdict.json از قبل هست — اجرای دوم ممنوع (مسیر C).')
    lock = json.load(open(lock_fp))
    win = lock['winner']
    print(f'[S531 آزمون] برندهٔ قفل‌شده: {win["filter"]}@{win["thr"]}', flush=True)

    df = load_full()
    sl, tp, mh = geometry()
    mask_base = s355_mask(df)
    fn, _, direction = FILTERS[win['filter']]
    vals = fn(df)
    mask = mask_base & keep_mask(vals, win['thr'], direction)
    n_sig = int(mask.sum())
    print(f'[S531 آزمون] سیگنال‌های فیلترشده: {n_sig}', flush=True)

    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    print(f'[S531 آزمون] n={len(tr)} · WR={_wr(tr):.2f}% · '
          f'net={tr["pnl_pip"].sum():.1f}pip', flush=True)

    null = null_for(df, mask, sl, tp, mh)
    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=SPLIT_BAR,
                       initial_capital=10000.0, allow_overlap=False)
    print(format_rqs2('S531 ', res), flush=True)

    g = res.get('gates') or {}
    m = res.get('metrics') or {}
    out = {
        'prereg': 'results/S531_PREREG_S355_RegimeGate_PathC.md',
        'locked': lock,
        'rule': f'S355 & {win["filter"]} {FILTERS[win["filter"]][2]} {win["thr"]}',
        'data': {'path': DATA, 'rows': int(len(df))},
        'geometry': {'sl': sl, 'tp': tp, 'mh': mh},
        'n_signals': n_sig,
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': sorted(k for k, v in g.items() if v is False),
        'null': null['long'],
        'n_trials': N_TRIALS, 'seed': SEED, 'split_bar': SPLIT_BAR,
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'recovery_factor', 'skill_lift_pp', 'skill_z', 'null_ref_wr',
            'breakeven_wr_cost', 'rr', 'top_win_share', 'skill_p_perm',
            'p_emp', 'p_adj_bonferroni', 'perm_k', 'perm_max')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }
    with open(verdict_fp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[S531] ذخیره شد: results/_s531/verdict.json', flush=True)
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('search', 'verdict'):
        raise SystemExit('usage: s531_s355_regime_gate.py {search|verdict}')
    raise SystemExit(phase_search() if sys.argv[1] == 'search'
                     else phase_verdict())
