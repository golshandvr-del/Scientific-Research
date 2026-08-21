# -*- coding: utf-8 -*-
"""
S532 — احیای S355 با هندسهٔ مقیاس‌شده به ATR · مسیر C · XAUUSD-M5
================================================================================
پیش‌ثبت: results/S532_PREREG_S355_ATRScaledGeometry_PathC.md (commit 60176ea7 —
قبل از هر محاسبه). بلوک من: S530–S539.

فرضیهٔ H_geom: شکست pre-2023 لایهٔ S355 عدم‌تطابق هندسی است نه رژیم —
براکت ثابت 120/120pip در دورهٔ کم‌نوسان لمس نمی‌شود (۷۲.۶٪ خروج max_hold).
هندسه: SL_pip[i] = TP_pip[i] = k · ATR14_pip[i] در کندل سیگنال (علّی).
RR=1.0 منجمد (قانون بودجه) · max_hold=96 منجمد (درس S360: یک تغییر در یک آزمون).

دو فاز با CLI جدا (عین s531):
  search  : k ∈ {2.0, 3.3, 5.5, 9.0} فقط روی bar < 544787.
            انتخاب: بیشینهٔ t مشروط به n>=30 و سهم max_hold<=40% (پیش‌بینی P1).
            گارد عمل-همانی: برندهٔ k=5.5 با میانهٔ SL در ±15٪ 120pip ⇒ مرگ.
            قفل در results/_s532/LOCKED.json. holdout هرگز شبیه‌سازی نمی‌شود.
  verdict : فقط با LOCKED.json؛ compute_rqs2 با split_bar=544787 و
            n_trials=25 (تجمعی: S530=1 + S531=20 + S532=4). **یک بار.**

اجرا:
  PYTHONPATH=. python3 strategies/s532_s355_atr_geometry.py search
  PYTHONPATH=. python3 strategies/s532_s355_atr_geometry.py verdict
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
SPLIT_BAR = 544787          # منجمد در پیش‌ثبت (همان S531)
N_TRIALS = 25               # تجمعی صادقانه: S530(1)+S531(20)+S532(4)
N_PERM = 500
SEED = 20260816             # منجمد در پیش‌ثبت
MIN_N = 30
MAX_MAXHOLD_SHARE = 0.40    # پیش‌بینی مکانیکی P1
K_GRID = (2.0, 3.3, 5.5, 9.0)   # خانوادهٔ بسته — ۴ عضو
ATR_P = 14
MH = 96                     # منجمد از آرشیو S355 — تغییر نمی‌کند
ARCHIVE_SL = 120.0          # برای گارد عمل-همانی
OUT = os.path.join(ROOT, 'results', '_s532')


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return float((t['pnl_pip'].to_numpy() > 0).mean() * 100.0)


def tstat(pnl: np.ndarray) -> float:
    if len(pnl) < 2:
        return float('-inf')
    sd = pnl.std(ddof=1)
    if sd == 0:
        return float('-inf')
    return float(pnl.mean() / (sd / np.sqrt(len(pnl))))


def load_full() -> pd.DataFrame:
    df = se.load_data(DATA)
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    t0, t1 = df['dt'].iloc[0], df['dt'].iloc[-1]
    span_y = (t1 - t0).days / 365.25
    print(f'[S532 داده] {DATA}\n[S532 داده] ردیف={len(df):,} · '
          f'{t0.date()} → {t1.date()} · {span_y:.2f} سال', flush=True)
    if span_y < 14.0:
        raise SystemExit('⛔ بازهٔ داده < ۱۴ سال ⇒ دادهٔ کامل نیست. توقف.')
    return df


def s355_mask(df: pd.DataFrame) -> np.ndarray:
    """قاعدهٔ منجمد S355 — عیناً همان S530/S531، بدون هیچ تغییری."""
    base = s333.build_layer(df, s333.BEST_CFG[CARD_KEY])
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    return np.asarray(base, bool) & (np.asarray(state) == -1)


def atr_pip(df: pd.DataFrame) -> np.ndarray:
    """ATR14 در کندل i (علّی — از دادهٔ تا i) بر حسب pip (pip=0.1$)."""
    a = np.asarray(bf.atr_series(df, period=ATR_P), float)
    return a / se.ASSETS[ASSET]['pip']


def maxhold_share(tr: pd.DataFrame) -> float:
    """سهم معاملاتی که با timeout بسته شدند: bars_held>=MH و |pnl|<0.95·SL."""
    if len(tr) == 0:
        return float('nan')
    bh = tr['bars_held'].to_numpy(float)
    pnl = np.abs(tr['pnl_pip'].to_numpy(float))
    slp = tr['sl_pip'].to_numpy(float)
    to = (bh >= MH) & (pnl < 0.95 * slp)
    return float(to.mean())


def breakeven_cost(med_sl: float) -> float:
    """سربه‌سر هزینه‌دار با RR=1: (SL+c)/(2·SL) — با اسپرد 3.3pip."""
    return (med_sl + 3.3) / (2.0 * med_sl) * 100.0


def sim_k(df, mask, apip, k):
    """شبیه‌سازی با براکت شناور k·ATR؛ کندل با ATR نامعتبر غیرقابل‌ورود است."""
    valid = np.isfinite(apip) & (apip > 0)
    m = mask & valid
    br = np.where(valid, k * apip, 0.0)   # sl_d<=0 در موتور ⇒ ورود رد می‌شود
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, m, z, br, br, ASSET,
                            max_hold=MH, allow_overlap=False)
    return tr, m


def phase_search() -> int:
    os.makedirs(OUT, exist_ok=True)
    lock_fp = os.path.join(OUT, 'LOCKED.json')
    if os.path.exists(lock_fp):
        raise SystemExit(f'⛔ {lock_fp} از قبل هست — جست‌وجوی دوم ممنوع (مسیر C).')

    df_full = load_full()
    # کل محاسبه فقط روی نیمهٔ اول — حتی اندیکاتورها نیمهٔ دوم را نمی‌بینند
    df = df_full.iloc[:SPLIT_BAR].reset_index(drop=True)
    print(f'[S532 جست‌وجو] فقط نیمهٔ اول: {len(df):,} کندل · '
          f'{df["dt"].iloc[-1].date()} آخرین روزِ دیده‌شده', flush=True)

    mask = s355_mask(df)
    apip = atr_pip(df)
    print(f'[S532] سیگنال‌های خام نیمهٔ اول: {int(mask.sum())} · '
          f'میانهٔ ATR14={np.nanmedian(apip):.1f}pip', flush=True)

    rows = []
    for k in K_GRID:
        t0 = _time.time()
        tr, _ = sim_k(df, mask, apip, k)
        n = len(tr)
        pnl = tr['pnl_pip'].to_numpy(float) if n else np.array([])
        med_sl = float(np.median(tr['sl_pip'])) if n else float('nan')
        mh_sh = maxhold_share(tr)
        wr = _wr(tr)
        be = breakeven_cost(med_sl) if n else float('nan')
        # گارد عمل-همانی (§۴ پیش‌ثبت): k=5.5 با میانهٔ SL در ±15٪ 120pip
        identity = bool(k == 5.5 and n and abs(med_sl - ARCHIVE_SL) <= 0.15 * ARCHIVE_SL)
        eligible = bool(n >= MIN_N and np.isfinite(mh_sh)
                        and mh_sh <= MAX_MAXHOLD_SHARE and not identity)
        row = dict(k=k, n=n, wr=wr, net_pip=float(pnl.sum()) if n else 0.0,
                   t=round(tstat(pnl), 4) if n >= 2 else None,
                   med_sl_pip=round(med_sl, 2) if n else None,
                   maxhold_share=round(mh_sh, 4) if n else None,
                   breakeven_cost=round(be, 2) if n else None,
                   identity_guard=identity, eligible=eligible)
        rows.append(row)
        print(f'  k={k}: n={n} WR={wr and round(wr,2)}% medSL={row["med_sl_pip"]} '
              f'mhSh={row["maxhold_share"]} be={row["breakeven_cost"]} '
              f't={row["t"]} {"IDENTITY!" if identity else ""} '
              f'{"✓" if eligible else "·"} ({_time.time()-t0:.0f}s)', flush=True)

    with open(os.path.join(OUT, 'search_grid.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    elig = [r for r in rows if r['eligible'] and r['t'] is not None]
    if not elig:
        print('[S532] ⛔ هیچ k واجد شرایط نیست ⇒ قانون توقف: مرگ صادقانه. '
              'holdout باز نمی‌شود.', flush=True)
        with open(os.path.join(OUT, 'STOPPED_DEAD.json'), 'w', encoding='utf-8') as f:
            json.dump({'reason': 'no k passed n>=30 AND maxhold<=40% AND identity guard',
                       'grid': rows}, f, ensure_ascii=False, indent=1)
        return 3

    win = max(elig, key=lambda r: r['t'])
    # قانون توقف دوم: WR نیمهٔ اول باید > سربه‌سر هزینه‌دار همان k باشد
    if win['wr'] is None or win['wr'] <= win['breakeven_cost']:
        print(f'[S532] ⛔ برنده k={win["k"]} با WR={win["wr"]:.2f}% <= '
              f'سربه‌سر {win["breakeven_cost"]:.2f}% ⇒ مرگ صادقانه.', flush=True)
        with open(os.path.join(OUT, 'STOPPED_DEAD.json'), 'w', encoding='utf-8') as f:
            json.dump({'reason': 'best first-half WR <= cost breakeven',
                       'winner': win, 'grid': rows}, f, ensure_ascii=False, indent=1)
        return 3

    with open(lock_fp, 'w', encoding='utf-8') as f:
        json.dump({'winner': win, 'locked_at': _time.strftime('%F %T'),
                   'split_bar': SPLIT_BAR, 'seed': SEED, 'n_trials': N_TRIALS,
                   'mh': MH, 'atr_p': ATR_P}, f, ensure_ascii=False, indent=1)
    print(f'[S532 قفل] برنده: k={win["k"]} · n={win["n"]} · t={win["t"]} · '
          f'WR={win["wr"]:.2f}% ⇒ LOCKED.json', flush=True)
    return 0


def null_for(df, mask, apip, k, n_perm=N_PERM, seed=SEED):
    """الگوی s437/s531 — با همان هندسهٔ شناور k·ATR (صفر اندازه‌گیری‌شده)."""
    n = len(df)
    valid_atr = np.isfinite(apip) & (apip > 0)
    br = np.where(valid_atr, k * apip, 0.0)
    z = np.zeros(n, bool)
    valid = np.zeros(n, bool)
    valid[250:n - MH - 1] = True
    valid &= valid_atr
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool)
    um[pick] = True
    tu = se.simulate_trades(df, um, z, br, br, ASSET, max_hold=MH,
                            allow_overlap=True)
    wr_unc = _wr(tu)
    print(f'[S532 نال] بی‌شرط: n={len(tu)} WR={wr_unc:.2f}%', flush=True)
    kk = int(mask.sum())
    perm = []
    for i in range(n_perm):
        p = rng.choice(vidx, size=min(kk, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        w = _wr(se.simulate_trades(df, pm, z, br, br, ASSET, max_hold=MH,
                                   allow_overlap=False))
        if w is not None:
            perm.append(w)
        if (i + 1) % 100 == 0:
            print(f'[S532 نال] {i+1}/{n_perm}', flush=True)
    pa = np.array(perm, float)
    return {'long': dict(uncond_wr=wr_unc, perm_mean=float(pa.mean()),
                         perm_sd=float(pa.std(ddof=1)),
                         perm_max=float(pa.max()), perm_k=int(pa.size)),
            'short': {}}


def phase_verdict() -> int:
    lock_fp = os.path.join(OUT, 'LOCKED.json')
    verdict_fp = os.path.join(OUT, 'verdict.json')
    if not os.path.exists(lock_fp):
        raise SystemExit('⛔ LOCKED.json نیست — اول فاز search.')
    if os.path.exists(verdict_fp):
        raise SystemExit('⛔ verdict.json از قبل هست — اجرای دوم ممنوع (مسیر C).')
    lock = json.load(open(lock_fp))
    k = float(lock['winner']['k'])
    print(f'[S532 آزمون] k قفل‌شده: {k}', flush=True)

    df = load_full()
    mask = s355_mask(df)
    apip = atr_pip(df)
    tr, m = sim_k(df, mask, apip, k)
    med_sl = float(np.median(tr['sl_pip']))
    mh_sh = maxhold_share(tr)
    print(f'[S532 آزمون] n={len(tr)} · WR={_wr(tr):.2f}% · '
          f'net={tr["pnl_pip"].sum():.1f}pip · medSL={med_sl:.1f}pip · '
          f'mhShare={mh_sh:.1%}', flush=True)

    # زیرپنجره‌ها برای گزارش (اطلاعی، نه گزینشی)
    bt = pd.to_numeric(df['time']).to_numpy()
    et = bt[tr['entry_bar'].to_numpy(int)]
    RECENT = 1695076500
    sub = {}
    for name, sel in (('pre2023', et < RECENT), ('recent', et >= RECENT)):
        s = tr[sel]
        sub[name] = dict(n=int(len(s)), wr=_wr(s),
                         net_pip=float(s['pnl_pip'].sum()) if len(s) else 0.0,
                         maxhold_share=round(maxhold_share(s), 4) if len(s) else None)
    print(f'[S532 زیرپنجره] {json.dumps(sub, ensure_ascii=False)}', flush=True)

    null = null_for(df, m, apip, k)
    res = compute_rqs2(tr, ASSET, sl_pip=med_sl, tp_pip=med_sl,
                       bar_time=bt, close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=SPLIT_BAR,
                       initial_capital=10000.0, allow_overlap=False)
    print(format_rqs2('S532 ', res), flush=True)

    g = res.get('gates') or {}
    mtr = res.get('metrics') or {}
    out = {
        'prereg': 'results/S532_PREREG_S355_ATRScaledGeometry_PathC.md',
        'locked': lock,
        'rule': f'S355 frozen mask + floating bracket SL=TP={k}*ATR14, mh=96',
        'data': {'path': DATA, 'rows': int(len(df))},
        'geometry': {'k': k, 'atr_p': ATR_P, 'med_sl_pip': round(med_sl, 2),
                     'rr': 1.0, 'mh': MH},
        'maxhold_share_full': round(mh_sh, 4),
        'subwindows': sub,
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {kk2: g.get(kk2) for kk2 in sorted(g)},
        'failed_gates': sorted(kk2 for kk2, v in g.items() if v is False),
        'null': null['long'],
        'n_trials': N_TRIALS, 'seed': SEED, 'split_bar': SPLIT_BAR,
        'metrics': {kk2: mtr.get(kk2) for kk2 in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'recovery_factor', 'skill_lift_pp', 'skill_z', 'null_ref_wr',
            'breakeven_wr_cost', 'rr', 'top_win_share', 'skill_p_perm',
            'p_emp', 'p_adj_bonferroni', 'perm_k', 'perm_max')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }
    with open(verdict_fp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[S532] ذخیره شد: results/_s532/verdict.json', flush=True)
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('search', 'verdict'):
        raise SystemExit('usage: s532_s355_atr_geometry.py {search|verdict}')
    raise SystemExit(phase_search() if sys.argv[1] == 'search'
                     else phase_verdict())
