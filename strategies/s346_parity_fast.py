# -*- coding: utf-8 -*-
"""
S346 — تستِ برابریِ «موتورِ سریعِ برداری» با «موتورِ اصلیِ پروژه»
================================================================================
چرا این فایل حیاتی است؟
اکتشافِ فضای بزرگ (هزاران ترکیبِ فیلتر) با `s346_fast.barrier_outcomes` انجام
می‌شود. اگر آن موتور حتی یک اختلافِ ریزِ سیستماتیک با `scalp_engine.simulate_trades`
داشته باشد، تمامِ نتایجِ اکتشاف بی‌اعتبار است. پس **قبل از هر اکتشافی** اثبات
می‌کنیم که دو موتور روی معاملهٔ به معاملهٔ یکسان، pnl_pip یکسان می‌دهند.

روشِ اثبات:
  ۱. موتورِ اصلی را با `allow_overlap=True` اجرا می‌کنیم (چون موتورِ سریع همهٔ
     رویدادها را می‌سنجد و صفِ اشغال ندارد).
  ۲. روی `signal_bar` جوین می‌کنیم و اختلافِ pnl_pip، exit_bar و برچسبِ برد را
     معامله‌به‌معامله می‌سنجیم.
  ۳. شرطِ قبولی: max|Δpnl_pip| < 1e-9 و ۱۰۰٪ تطابقِ exit_bar و outcome.

توجه: موتورِ سریع BE/trailing ندارد (عمدی)؛ پس تست با be_trigger_pip=None و
trail_pip=None انجام می‌شود — همان حالتی که در اکتشاف استفاده می‌کنیم.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from strategies.s346_adaptive_channel import build_signals
from strategies.s346_fast import barrier_outcomes, select_non_overlap


CASES = [
    # (asset, file, mode, p, mult, er_thr, sl_k, tp_k, max_hold)
    ('XAUUSD', 'data/XAUUSD_M15.csv', 'fade',     21, 1.618, 0.236, 2.058, 2.058, 21),
    ('XAUUSD', 'data/XAUUSD_M15.csv', 'breakout', 13, 2.058, 0.309, 1.618, 2.618, 13),
    ('XAUUSD', 'data/XAUUSD_H1.csv',  'fade',     34, 1.272, 0.191, 1.272, 3.236, 34),
    ('EURUSD', 'data/EURUSD_M15.csv', 'breakout', 21, 1.618, 0.236, 1.618, 1.618, 21),
    ('EURUSD', 'data/EURUSD_M30.csv', 'fade',     55, 2.058, 0.146, 2.058, 1.272, 16),
]


def run_case(asset, path, mode, p, mult, er_thr, sl_k, tp_k, max_hold, nbars=40000):
    cfg = se.ASSETS[asset]
    pip = cfg['pip']
    df = se.load_data(path)
    if nbars and len(df) > nbars:
        df = df.iloc[-nbars:].reset_index(drop=True)

    ls, ss, slp, tpp, ch = build_signals(
        df, mode=mode, p=p, mult=mult, er_thr=er_thr,
        sl_k=sl_k, tp_k=tp_k, pip=pip)

    # --- موتورِ اصلی (مرجعِ حقیقت) ---
    tr = se.simulate_trades(df, ls, ss, slp, tpp, asset,
                            max_hold=max_hold, allow_overlap=True)
    if len(tr) == 0:
        print(f"  [skip] {asset} {mode} p={p}: no trades")
        return True

    # --- موتورِ سریع ---
    sig_idx = np.where(ls | ss)[0]
    is_long = ls[sig_idx]
    sl_dist = slp[sig_idx] * pip
    tp_dist = tpp[sig_idx] * pip
    ok_sl = sl_dist > 0
    sig_idx, is_long = sig_idx[ok_sl], is_long[ok_sl]
    sl_dist, tp_dist = sl_dist[ok_sl], tp_dist[ok_sl]

    fo = barrier_outcomes(df, sig_idx, is_long, sl_dist, tp_dist, max_hold,
                          pip, cfg['spread_pip'], cfg['slip_pip'])

    # --- جوین روی signal_bar ---
    ref = {int(r.signal_bar): (float(r.pnl_pip), int(r.exit_bar), r.outcome)
           for r in tr.itertuples()}
    fast_sig = fo['sig_idx']
    n_cmp = 0
    max_dpnl = 0.0
    bad_exit = 0
    bad_out = 0
    for k in range(len(fast_sig)):
        sb = int(fast_sig[k])
        if sb not in ref:
            continue
        rp, rex, rout = ref[sb]
        fp = float(fo['pnl_pip'][k])
        fex = int(fo['entry_bar'][k] + fo['exit_off'][k])
        fout = 'win' if fo['win'][k] else 'loss'
        max_dpnl = max(max_dpnl, abs(rp - fp))
        bad_exit += (rex != fex)
        bad_out += (rout != fout)
        n_cmp += 1

    ok = (max_dpnl < 1e-9) and bad_exit == 0 and bad_out == 0
    tag = 'PASS' if ok else '**FAIL**'
    print(f"  {tag} {asset:6s} {mode:8s} p={p:2d} mh={max_hold:2d} | "
          f"ref_n={len(tr):5d} fast_n={len(fast_sig):5d} cmp={n_cmp:5d} | "
          f"max|dpnl|={max_dpnl:.2e} exit_mismatch={bad_exit} out_mismatch={bad_out}")
    return ok


def run_case_noverlap(asset, path, mode, p, mult, er_thr, sl_k, tp_k, max_hold,
                      nbars=40000):
    """
    آزمونِ برابریِ دوم و مهم‌تر: بازتولیدِ **صفِ بی‌همپوشانی**.
    موتورِ اصلی با allow_overlap=False کدام رویدادها را معامله می‌کند؟
    `select_non_overlap` باید *دقیقاً* همان مجموعهٔ signal_bar را بدهد.
    """
    cfg = se.ASSETS[asset]
    pip = cfg['pip']
    df = se.load_data(path)
    if nbars and len(df) > nbars:
        df = df.iloc[-nbars:].reset_index(drop=True)

    ls, ss, slp, tpp, ch = build_signals(
        df, mode=mode, p=p, mult=mult, er_thr=er_thr,
        sl_k=sl_k, tp_k=tp_k, pip=pip)

    tr = se.simulate_trades(df, ls, ss, slp, tpp, asset,
                            max_hold=max_hold, allow_overlap=False)
    if len(tr) == 0:
        print(f"  [skip] {asset} {mode} p={p}: no trades")
        return True

    sig = np.where(ls | ss)[0]
    is_long = ls[sig]
    sl_d, tp_d = slp[sig] * pip, tpp[sig] * pip
    ok = sl_d > 0
    sig, is_long, sl_d, tp_d = sig[ok], is_long[ok], sl_d[ok], tp_d[ok]
    fo = barrier_outcomes(df, sig, is_long, sl_d, tp_d, max_hold,
                          pip, cfg['spread_pip'], cfg['slip_pip'])
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])

    ref_bars = set(int(x) for x in tr['signal_bar'].values)
    fast_bars = set(int(x) for x in fo['sig_idx'][keep])
    # رویدادهای انتهای داده که موتورِ سریع حذف می‌کند را از مقایسه کنار می‌گذاریم
    horizon = int(fo['sig_idx'].max()) if len(fo['sig_idx']) else 0
    ref_bars = set(b for b in ref_bars if b <= horizon)

    only_ref = ref_bars - fast_bars
    only_fast = fast_bars - ref_bars
    ok = (len(only_ref) == 0 and len(only_fast) == 0)
    # سودِ خالصِ pip دو مسیر هم باید یکی باشد
    ref_sum = float(tr[tr['signal_bar'] <= horizon]['pnl_pip'].sum())
    fast_sum = float(fo['pnl_pip'][keep].sum())
    dsum = abs(ref_sum - fast_sum)
    ok = ok and dsum < 1e-6
    tag = 'PASS' if ok else '**FAIL**'
    print(f"  {tag} {asset:6s} {mode:8s} p={p:2d} QUEUE | ref_n={len(ref_bars):5d} "
          f"fast_n={len(fast_bars):5d} only_ref={len(only_ref)} only_fast={len(only_fast)} "
          f"| Σpnl ref={ref_sum:12.4f} fast={fast_sum:12.4f} d={dsum:.2e}")
    return ok


def run():
    print("=== S346 parity: fast vectorized barrier engine  vs  scalp_engine ===")
    all_ok = True
    for c in CASES:
        all_ok &= run_case(*c)
    print("--- queue parity (allow_overlap=False reproduction) ---")
    for c in CASES:
        all_ok &= run_case_noverlap(*c)
    print("=== RESULT:", "ALL PASS — fast engine is trustworthy for exploration"
          if all_ok else "FAILURE — do NOT use fast engine", "===")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(run())
