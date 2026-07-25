# -*- coding: utf-8 -*-
"""
S320 — احیای S01 (BB+RSI Mean-Reversion) با فیلترِ رژیم + «همه چیز شناور»
================================================================================
هدف: احیای لایهٔ سوختهٔ S01 (RQS=47) تا RQS+ ≥ 80.

تز (نبوغ + تفکر خطی/غیرخطی):
  L28/L29 پروژه نشان داد لایه‌های روند-محور در «رژیم رنج» می‌میرند. پس یک لایهٔ
  mean-reversion باید دقیقاً در همان رژیمِ رنج (که آن‌ها می‌میرند) زنده باشد و
  مکملِ پرتفوی شود. S01 خام در روندِ صعودی خودکشی می‌کند (SHORTها استاپ می‌خورند).

  اصلاحات (قانونِ «همه چیز شناور» — پارامترها از اعداد رند آزاد):
    1. گیتِ رژیم: فقط وقتی ADX < adx_gate (بازارِ بی‌روند/رنج) معامله کن.
    2. گیتِ جهت-همسو: فیلترِ شیبِ میان‌مدت مانع از فروش در میکرو-روندِ صعودی و
       خرید در میکرو-روندِ نزولی.
    3. آستانه‌های شناور + TP/SL نامتقارن — grid-search (نه اعداد رند).
    4. کارایی: featureها یک‌بار کش می‌شوند؛ غربالِ سبک (WR/PF/n) قبل از RQS کامل.

اجرا: python3 strategies/s320_bb_rsi_regime_revival.py XAUUSD M5 [max_seconds]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import itertools

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs

TF_FILE = {
    'M5':  'data/{a}_M5.csv', 'M15': 'data/{a}_M15.csv',
    'M30': 'data/{a}_M30.csv', 'H1':  'data/{a}_H1.csv', 'H4':  'data/{a}_H4.csv',
}

# فضای جستجوی «شناور» — عمداً اعداد غیر-رند هم آزموده می‌شوند
GRID = dict(
    bp=[20, 30], mult=[1.8, 2.2],
    rp=[9, 14], rsi_lo=[20, 25, 30], rsi_hi=[70, 75, 80],
    ap=[14], adx_gate=[16, 20, 25],
    sp=[40], slope_tol=[0.20, 0.50],
    sl_mult=[1.0, 1.4, 1.8], tp_mult=[1.4, 2.0, 2.8],
    max_hold=[36, 72],
)


def build_features(df):
    close = df['close']
    feats = {}
    for bp in set(GRID['bp']):
        for mult in set(GRID['mult']):
            lo, mid, up = ind.bollinger(close, bp, mult)
            feats[f'bb_lo_{bp}_{mult}'] = lo.values
            feats[f'bb_up_{bp}_{mult}'] = up.values
    for rp in set(GRID['rp']):
        feats[f'rsi_{rp}'] = ind.rsi(close, rp).values
    for ap in set(GRID['ap']):
        adx_, _, _ = ind.adx(df, ap)
        feats[f'adx_{ap}'] = adx_.values
    for sp in set(GRID['sp']):
        feats[f'slope_{sp}'] = ind.rolling_slope(close, sp).values
    feats['atr_14'] = ind.atr(df, 14).values
    feats['close'] = close.values
    return feats


def make_signals(feats, cfg, asset):
    close = feats['close']
    lo = feats[f'bb_lo_{cfg["bp"]}_{cfg["mult"]}']
    up = feats[f'bb_up_{cfg["bp"]}_{cfg["mult"]}']
    rsi_ = feats[f'rsi_{cfg["rp"]}']
    adx_ = feats[f'adx_{cfg["ap"]}']
    slope = feats[f'slope_{cfg["sp"]}']
    atr_ = feats['atr_14']

    range_regime = adx_ < cfg['adx_gate']
    long_raw = (close < lo) & (rsi_ < cfg['rsi_lo'])
    short_raw = (close > up) & (rsi_ > cfg['rsi_hi'])
    st = cfg['slope_tol']
    long_ok = long_raw & range_regime & (slope > -st)
    short_ok = short_raw & range_regime & (slope < st)
    long_sig = np.nan_to_num(long_ok, nan=0).astype(bool)
    short_sig = np.nan_to_num(short_ok, nan=0).astype(bool)

    pip = se.ASSETS[asset]['pip']
    atr_pip = atr_ / pip
    sl_pip = np.clip(np.nan_to_num(cfg['sl_mult'] * atr_pip, nan=0.0), 5.0, None)
    tp_pip = np.clip(np.nan_to_num(cfg['tp_mult'] * atr_pip, nan=0.0), 5.0, None)
    return long_sig, short_sig, sl_pip, tp_pip


def lite_stats(trades):
    """غربالِ سبک بدونِ walk-forward: n, WR, PF, net(pip)."""
    n = len(trades)
    if n == 0:
        return 0, 0, 0, 0
    pnl = trades['pnl_pip'].values
    wins = (pnl > 0).sum()
    wr = wins / n * 100
    gp = pnl[pnl > 0].sum()
    gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 999
    return n, wr, pf, pnl.sum()


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    max_sec = float(sys.argv[3]) if len(sys.argv) > 3 else 520.0
    path = TF_FILE[tf].format(a=asset)
    df = se.load_data(path)
    print(f"[{asset} {tf}] rows={len(df)}  {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}")

    feats = build_features(df)
    keys = list(GRID.keys())
    total = 1
    for k in keys:
        total *= len(GRID[k])
    print(f"grid size = {total}")

    t0 = time.time()
    shortlist = []   # کاندیداهای غربالِ سبک
    tested = 0
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > max_sec * 0.55:
            print(f"[time] coarse screen stopped at {tested}")
            break
        cfg = dict(zip(keys, combo))
        ls, ss, sl, tp = make_signals(feats, cfg, asset)
        trades = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                    max_hold=cfg['max_hold'], allow_overlap=False)
        tested += 1
        n, wr, pf, net = lite_stats(trades)
        if n >= rqs.N_FLOOR and wr >= 58 and pf >= 1.25:
            sig = ls | ss
            med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
            shortlist.append((pf, wr, n, cfg, trades, med_tp))

    shortlist.sort(key=lambda x: x[0], reverse=True)
    print(f"tested={tested}  shortlist={len(shortlist)}  (elapsed {time.time()-t0:.0f}s)")

    # مرحلهٔ دوم: RQS کامل روی shortlist
    results = []
    for pf, wr, n, cfg, trades, med_tp in shortlist:
        if time.time() - t0 > max_sec:
            print("[time] full-RQS stopped")
            break
        r = rqs.compute_rqs(trades, asset,
                            sl_pip=float(np.median(trades['sl_pip'])), tp_pip=med_tp)
        results.append((r['rqs_score'], r['passed'], cfg, r['metrics'], r['gates']))

    results.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print("=" * 105)
    for score, passed, cfg, m, gates in results[:20]:
        gl = ''.join('1' if gates[g] else '0' for g in ['G0','G1','G2','G3','G4','G5'])
        print(f"RQS={score:5.1f} {'PASS' if passed else 'FAIL'} G[{gl}] "
              f"n={m['n_trades']:4d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} wf={m['wf_nets']} | bp{cfg['bp']} m{cfg['mult']} "
              f"rsi{cfg['rp']}[{cfg['rsi_lo']}/{cfg['rsi_hi']}] adx<{cfg['adx_gate']} "
              f"sl{cfg['sl_mult']}tp{cfg['tp_mult']} mh{cfg['max_hold']} st{cfg['slope_tol']}")
    if not results:
        print("NO CANDIDATE PASSED LITE SCREEN (WR>=58 & PF>=1.25)")


if __name__ == '__main__':
    main()
