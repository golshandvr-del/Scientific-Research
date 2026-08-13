# -*- coding: utf-8 -*-
"""
S530 — داوریِ تأییدیِ تمام‌تاریخیِ (۱۵.۶ سال) لایهٔ زندهٔ S355 · XAUUSD-M5
================================================================================
پیش‌ثبت: results/S530_PREREGISTRATION_S355_FullHistory_Adjudication.md
         (commit 442f2e0c — قبل از این فایل و قبل از هر اجرا)

قاعدهٔ منجمد (صفر جست‌وجو):
    mask = s333.build_layer(df, BEST_CFG['XAUUSD_M5']) & (lpsb_state == -1)
    هندسه از خودِ BEST_CFG خوانده می‌شود (sl/tp/mh) — درسِ BUG-CFGKEYS.

داده: data/mt5_full/XAUUSD_M5.csv — دادهٔ حاکمِ ۱۵.۶ سال (الزامِ صریحِ کاربر).
گاردِ BUG-DATASETDRIFT: مسیر/تعدادِ ردیف/بازهٔ تاریخ چاپ می‌شود؛
    بازه < ۱۴ سال ⇒ توقفِ صریح.

آزمونِ تأییدی ⇒ n_trials = 1 (طبقِ پیش‌ثبت). نال: عیناً الگوی
tools/s437_adjudicate.null_for (نالِ اندازه‌گیری‌شده با همان هندسه، K=500).

خروجی: results/_s530/full_adjudication.json  +  چاپِ خلاصه.
همچنین زیرتحلیلِ ازپیش‌اعلام‌شده: معاملاتِ پنجرهٔ اخیر (از epoch 1695076500،
شروعِ دادهٔ قدیمِ ۲.۸ ساله) جدا شمارش می‌شوند تا سه حکمِ پیش‌ثبت
(CONFIRMED-FULL / REGIME-ONLY / BURNED) قابلِ صدور باشد.

اجرا:  cd /home/user/webapp && PYTHONPATH=. python3 strategies/s530_s355_fullhistory_adjudicate.py
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

DATA = os.path.join(ROOT, 'data', 'mt5_full', 'XAUUSD_M5.csv')
CARD_KEY = 'XAUUSD_M5'
ASSET = 'XAUUSD'
WARMUP = 200          # عیناً s436/s437
N_TRIALS = 1          # آزمونِ تأییدیِ پیش‌ثبت‌شده — هیچ جاروبی نیست
N_PERM = 500          # کفِ الزامیِ H3 در v2.6
SEED = 20260813       # قفل‌شده در پیش‌ثبت
RECENT_EPOCH = 1695076500   # شروعِ data/XAUUSD_M5.csv قدیم (پنجرهٔ ACCEPT اصلی)
OUT = os.path.join(ROOT, 'results', '_s530')


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return float((t['pnl_pip'].to_numpy() > 0).mean() * 100.0)


def load_full() -> pd.DataFrame:
    """گاردِ BUG-DATASETDRIFT — هویتِ داده چاپ و راستی‌آزمایی می‌شود."""
    df = se.load_data(DATA)
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    t0, t1 = df['dt'].iloc[0], df['dt'].iloc[-1]
    span_y = (t1 - t0).days / 365.25
    print(f'[S530 داده] {DATA}')
    print(f'[S530 داده] ردیف={len(df):,} · {t0.date()} → {t1.date()} · '
          f'{span_y:.2f} سال', flush=True)
    if span_y < 14.0:
        raise SystemExit('⛔ بازهٔ داده < ۱۴ سال ⇒ این دادهٔ کامل نیست. توقف.')
    return df


def s355_cfg() -> dict:
    best = getattr(s333, 'BEST_CFG', None)
    if not isinstance(best, dict) or CARD_KEY not in best:
        raise RuntimeError(f'BEST_CFG[{CARD_KEY}] یافت نشد')
    return best[CARD_KEY]


def s355_mask(df: pd.DataFrame) -> np.ndarray:
    cfg = s355_cfg()
    base = s333.build_layer(df, cfg)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    return np.asarray(base, bool) & (np.asarray(state) == -1)


def geometry() -> tuple[float, float, int]:
    """کلیدها sl/tp/mh — از منبع خوانده می‌شود (BUG-CFGKEYS)."""
    cfg = s355_cfg()
    miss = [k for k in ('sl', 'tp', 'mh') if cfg.get(k) is None]
    if miss:
        raise RuntimeError(f'کلیدهای {miss} در BEST_CFG نیستند: {sorted(cfg)}')
    return float(cfg['sl']), float(cfg['tp']), int(cfg['mh'])


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """عیناً tools/s437_adjudicate.null_for — نالِ اندازه‌گیری‌شده."""
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
    print(f'[S530 نال] بی‌قید: {len(tu)} معامله · WR={wr_unc:.2f}%', flush=True)

    k = int(mask.sum())
    perm = []
    t0 = _time.time()
    for i in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, ASSET, max_hold=mh,
                               allow_overlap=False)
        w = _wr(t)
        if w is not None:
            perm.append(w)
        if (i + 1) % 50 == 0:
            print(f'[S530 نال] جایگشت {i+1}/{n_perm} · '
                  f'{_time.time()-t0:.0f}s', flush=True)
    pa = np.array(perm, float) if perm else np.array([])
    return {'long': dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=int(pa.size)),
            'short': {}}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    df = load_full()
    sl, tp, mh = geometry()
    print(f'[S530 هندسه] sl={sl} tp={tp} mh={mh} (از BEST_CFG)', flush=True)

    mask = s355_mask(df)
    n_sig = int(mask.sum())
    print(f'[S530 سیگنال] {n_sig} کندلِ سیگنال', flush=True)
    if n_sig == 0:
        raise SystemExit('⛔ صفر سیگنال ⇒ شکستِ اندازه‌گیری (نه حکم).')

    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    print(f'[S530 معاملات] n={len(tr)} · WR={_wr(tr):.2f}% · '
          f'net={tr["pnl_pip"].sum():.1f}pip', flush=True)

    # چک‌پوینتِ میانی — قانونِ اندک‌اندک
    tr_json = {'n': int(len(tr)), 'wr': _wr(tr),
               'net_pip': float(tr['pnl_pip'].sum())}
    with open(os.path.join(OUT, 'trades_summary.json'), 'w') as f:
        json.dump(tr_json, f, indent=1)

    null = null_for(df, mask, sl, tp, mh)

    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS,
                       initial_capital=10000.0, allow_overlap=False)
    print(format_rqs2('S530/S355-FULL ', res), flush=True)

    # ── زیرتحلیلِ ازپیش‌اعلام‌شده: پنجرهٔ اخیر (فقط توصیفی) ──────────────
    # خروجیِ simulate_trades ستونِ زمان ندارد؛ ستونِ واقعی (خوانده‌شده از
    # engine/scalp_engine.py خطِ ۲۴۸) `entry_bar` است ⇒ نگاشت به df['time'].
    bar_time = pd.to_numeric(df['time']).to_numpy()
    et = bar_time[tr['entry_bar'].to_numpy(int)]
    rec = tr[et >= RECENT_EPOCH]
    old = tr[et < RECENT_EPOCH]
    sub = {
        'recent': {'n': int(len(rec)), 'wr': _wr(rec),
                   'net_pip': float(rec['pnl_pip'].sum()) if len(rec) else 0.0},
        'pre2023': {'n': int(len(old)), 'wr': _wr(old),
                    'net_pip': float(old['pnl_pip'].sum()) if len(old) else 0.0},
    }
    print(f'[S530 زیرتحلیل] اخیر: n={sub["recent"]["n"]} '
          f'WR={sub["recent"]["wr"]} · قبل۲۰۲۳: n={sub["pre2023"]["n"]} '
          f'WR={sub["pre2023"]["wr"]}', flush=True)

    g = res.get('gates') or {}
    m = res.get('metrics') or {}
    out = {
        'prereg': 'results/S530_PREREGISTRATION_S355_FullHistory_Adjudication.md',
        'prereg_commit': '442f2e0c',
        'data': {'path': DATA, 'rows': int(len(df)),
                 'first': str(df['dt'].iloc[0]), 'last': str(df['dt'].iloc[-1])},
        'rule': 'S355 frozen: s333.build_layer(BEST_CFG[XAUUSD_M5]) & lpsb_state==-1',
        'geometry': {'sl': sl, 'tp': tp, 'mh': mh},
        'n_signals': n_sig,
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': sorted(k for k, v in g.items() if v is False),
        'null': null['long'],
        'n_trials': N_TRIALS,
        'seed': SEED,
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'recovery_factor', 'skill_lift_pp', 'skill_z', 'null_ref_wr',
            'breakeven_wr_cost', 'rr', 'top_win_share', 'skill_p_perm',
            'p_emp', 'perm_k', 'perm_max')},
        'subwindow': sub,
        'notes': [str(x) for x in (res.get('notes') or [])],
    }
    with open(os.path.join(OUT, 'full_adjudication.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'[S530] ذخیره شد: results/_s530/full_adjudication.json', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
