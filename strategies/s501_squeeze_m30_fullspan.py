# -*- coding: utf-8 -*-
"""
S501 — احیای بیمار S225 (Squeeze-Breakout طلا، XAUUSD-M30) با گسترش n به تاریخچهٔ کامل
=======================================================================================
پیش‌ثبت: results/S501_PREREG_SQUEEZE_M30_FULLSPAN_REVIVAL.md (commit 3db1443a — قبل از این اجرا)

قانون منجمد (صفر پارامتر جدید):
  سیگنال = base_s91_squeeze (import مستقیم از s225) · LONG-only
  خروج   = SL=200 / TP=200 pip · max_hold=48 · allow_overlap=False
داور: engine.rqs2.compute_rqs2 v2.6 — یک فراخوان روی کل ۲۰۱۱→۲۰۲۶.
پادزهر پیش‌ثبت‌شده: lift زیرگروه W0 (بکر، ۲۰۱۱→۲۰۲۲/۰۷/۱۶) ≤ 0 ⇒ self-REJECT.
گام‌ها به‌ترتیب و با ذخیرهٔ افزایشی در results/_scan_S501/ اجرا می‌شوند.
"""
import os, sys, json, warnings
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

import strategies.s220_wr60_booster as B          # load/last_n_years (spread=3.3 هم اینجا ست می‌شود)
from strategies.s225_s91_squeeze_wr60 import base_s91_squeeze
from strategies.s354_improve_long import build_null_canonical
import engine.scalp_engine as se
import engine.rqs2 as rqs2

SEED = 20260813
K_PERM = 2000
N_TRIALS = 97
SPLIT_FRAC = 0.60
SL_PIP, TP_PIP, MAX_HOLD = 200.0, 200.0, 48
ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_scan_S501')
os.makedirs(OUT, exist_ok=True)


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=float)
    print(f"  💾 {name}", flush=True)


def run_rule(df):
    """قانون منجمد S501 روی df — خروجی: (entries, trades)."""
    sig = base_s91_squeeze(df)
    ent = np.zeros(len(df), bool)
    ent[1:] = sig[:-1]                      # ورود کندلِ بعدِ سیگنال (مطابق بازتولید پیش‌ثبت)
    tr = se.simulate_trades(df, ent, np.zeros(len(df), bool), SL_PIP, TP_PIP,
                            ASSET, MAX_HOLD, allow_overlap=False)
    return sig, ent, tr


def main():
    print('=' * 80)
    print('S501 — Squeeze-Breakout XAUUSD-M30 full-span revival (prereg 3db1443a)')
    print('=' * 80, flush=True)

    df = B.load('XAUUSD_M30')               # کل ۲۰۱۱→۲۰۲۶
    dt_all = df['dt']
    print(f"data: {len(df):,} bars | {dt_all.min()} -> {dt_all.max()}", flush=True)

    # --- گام ۱: دروازهٔ بازتولید لنگر (پنجرهٔ ۴سالهٔ S225) --------------------
    w1_start = dt_all.max() - pd.DateOffset(years=4)
    d4 = df[df['dt'] >= w1_start].reset_index(drop=True)
    _, _, tr4 = run_rule(d4)
    n4 = len(tr4); wr4 = 100.0 * float(np.mean(tr4['pnl_pip'] > 0)) if n4 else 0.0
    ok_repro = (abs(n4 - 294) <= 0.10 * 294) and (abs(wr4 - 58.16) <= 2.0)
    save('repro_anchor.json', {'n': n4, 'wr': wr4, 'target_n': 294,
                               'target_wr': 58.16, 'ok': ok_repro})
    print(f"[1] anchor repro: n={n4} wr={wr4:.2f}  -> {'OK' if ok_repro else 'FAIL'}", flush=True)
    if not ok_repro:
        print('STOP: anchor reproduction failed (prereg §5).')
        return

    # --- گام ۲: اجرای قانون منجمد روی کل بازه --------------------------------
    sig, ent, tr = run_rule(df)
    n = len(tr); wr = 100.0 * float(np.mean(tr['pnl_pip'] > 0))
    print(f"[2] full span: signals={int(sig.sum())} trades={n} WR={wr:.2f}", flush=True)

    # --- گام ۳: پادزهر W0 (پیش‌ثبت §4) — زیرگروه بکر ۲۰۱۱→۲۰۲۲/۰۷ ------------
    entry_dt = dt_all.to_numpy()[tr['entry_bar'].to_numpy(int)]
    w0_mask = entry_dt < np.datetime64(w1_start)
    tr0 = tr[w0_mask]
    n0 = len(tr0); wr0 = 100.0 * float(np.mean(tr0['pnl_pip'] > 0)) if n0 else 0.0
    # null مخصوص W0 برای lift زیرگروه: جایگشت زمانی روی همان زیر-پنجره
    df0 = df[df['dt'] < w1_start].reset_index(drop=True)
    sig0 = base_s91_squeeze(df0)
    null0 = build_null_canonical(df0, sig0, SL_PIP, TP_PIP, MAX_HOLD,
                                 n_perm=500, seed=23)
    ref0 = null0['long']['uncond_wr']
    lift0 = wr0 - ref0
    save('w0_antidote.json', {'n0': n0, 'wr0': wr0, 'ref0': ref0, 'lift0_pp': lift0,
                              'self_reject': bool(lift0 <= 0)})
    print(f"[3] W0 virgin subgroup: n={n0} WR={wr0:.2f} ref={ref0:.2f} lift={lift0:+.2f}pp",
          flush=True)
    if lift0 <= 0:
        print('SELF-REJECT per prereg §4: W0 lift <= 0.')
        return

    # --- گام ۴: null کانونی کل بازه + قضاوت v2.6 ------------------------------
    null = build_null_canonical(df, sig, SL_PIP, TP_PIP, MAX_HOLD,
                                n_perm=K_PERM, seed=23)
    save('null_full.json', {'long': null['long']})
    print(f"[4] null: uncond_wr={null['long']['uncond_wr']:.2f} "
          f"perm_sd={null['long']['perm_sd']:.2f}", flush=True)

    # holdout: ۴۰٪ آخر بر حسب زمان ورود
    q = np.quantile(entry_dt.astype('datetime64[s]').astype(np.int64), SPLIT_FRAC)
    holdout = entry_dt.astype('datetime64[s]').astype(np.int64) >= q

    np.random.seed(SEED)
    verdict = rqs2.compute_rqs2(
        tr, ASSET, sl_pip=SL_PIP, tp_pip=TP_PIP,
        bar_time=dt_all, null=null, close=df['close'],
        holdout_mask=holdout, n_trials=N_TRIALS, allow_overlap=False)

    m = verdict['metrics']; g = verdict['gates']
    save('verdict.json', verdict)
    gates_str = ' '.join(f"H{i}:{'✓' if g.get('H%d' % i) else '✗'}" for i in range(11))
    print(f"S501 | {verdict['verdict']} RQS2={verdict['rqs2_score']:.1f} | "
          f"n={m.get('n_trades')} WR={m.get('win_rate')} lift={m.get('skill_lift_pp')} "
          f"z={m.get('skill_z')} PF={m.get('profit_factor')} | {gates_str}", flush=True)


if __name__ == '__main__':
    main()
