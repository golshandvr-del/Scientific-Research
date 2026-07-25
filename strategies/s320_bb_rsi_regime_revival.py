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
    2. گیتِ جهت-همسو: در رنج، هر دو جهت مجاز؛ اما فیلترِ شیبِ میان‌مدت مانع از
       فروش در میکرو-روندِ صعودی و خرید در میکرو-روندِ نزولی می‌شود.
    3. آستانه‌های شناور: BB(period, mult)، RSI(period)، آستانه‌های اشباع، ADXگیت،
       و TP/SL نامتقارن — همه grid-search می‌شوند (نه اعداد رند).

اجرا: python3 strategies/s320_bb_rsi_regime_revival.py XAUUSD M5
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import itertools

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs

TF_FILE = {
    'M5':  'data/{a}_M5.csv',
    'M15': 'data/{a}_M15.csv',
    'M30': 'data/{a}_M30.csv',
    'H1':  'data/{a}_H1.csv',
    'H4':  'data/{a}_H4.csv',
}


def build_features(df):
    close = df['close']
    feats = {}
    for bp in (14, 20, 30):
        for mult in (1.8, 2.0, 2.4):
            lo, mid, up = ind.bollinger(close, bp, mult)
            feats[f'bb_lo_{bp}_{mult}'] = lo
            feats[f'bb_up_{bp}_{mult}'] = up
    for rp in (9, 14, 21):
        feats[f'rsi_{rp}'] = ind.rsi(close, rp)
    for ap in (14, 20):
        adx_, pdi, mdi = ind.adx(df, ap)
        feats[f'adx_{ap}'] = adx_
    for sp in (30, 50):
        feats[f'slope_{sp}'] = ind.rolling_slope(close, sp)
    for atrp in (14,):
        feats[f'atr_{atrp}'] = ind.atr(df, atrp)
    return feats


def run_config(df, feats, cfg, asset):
    close = df['close'].values
    lo = feats[f'bb_lo_{cfg["bp"]}_{cfg["mult"]}'].values
    up = feats[f'bb_up_{cfg["bp"]}_{cfg["mult"]}'].values
    rsi_ = feats[f'rsi_{cfg["rp"]}'].values
    adx_ = feats[f'adx_{cfg["ap"]}'].values
    slope = feats[f'slope_{cfg["sp"]}'].values
    atr_ = feats['atr_14'].values

    # گیتِ رژیمِ رنج: ADX پایین = بی‌روند
    range_regime = adx_ < cfg['adx_gate']

    # سیگنالِ MR پایه
    long_raw = (close < lo) & (rsi_ < cfg['rsi_lo'])
    short_raw = (close > up) & (rsi_ > cfg['rsi_hi'])

    # فیلترِ شیبِ همسو: در رنج، مانع از فروش در میکرو-روندِ صعودی و خرید در نزولی
    # slope نرمال‌شده؛ آستانهٔ کوچکِ شناور
    st = cfg['slope_tol']
    long_ok = long_raw & range_regime & (slope > -st)   # نخر اگر شیب به‌شدت نزولی
    short_ok = short_raw & range_regime & (slope < st)   # نفروش اگر شیب به‌شدت صعودی

    long_sig = np.nan_to_num(long_ok, nan=0).astype(bool)
    short_sig = np.nan_to_num(short_ok, nan=0).astype(bool)

    # TP/SL بر حسبِ pip از ATR (شناور، نامتقارن مجاز)
    pip = se.ASSETS[asset]['pip']
    atr_pip = atr_ / pip
    sl_pip = np.nan_to_num(cfg['sl_mult'] * atr_pip, nan=0.0)
    tp_pip = np.nan_to_num(cfg['tp_mult'] * atr_pip, nan=0.0)
    # کف‌گذاری امن
    sl_pip = np.clip(sl_pip, 5.0, None)
    tp_pip = np.clip(tp_pip, 5.0, None)

    trades = se.simulate_trades(
        df, long_sig, short_sig, sl_pip, tp_pip, asset,
        max_hold=cfg['max_hold'], allow_overlap=False,
    )
    # median TP بر مبنای barهای سیگنال (برای محاسبهٔ breakeven در RQS)
    sig_mask = long_sig | short_sig
    med_tp = float(np.median(tp_pip[sig_mask])) if sig_mask.any() else float(np.median(tp_pip))
    return trades, med_tp


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    path = TF_FILE[tf].format(a=asset)
    df = se.load_data(path)
    print(f"[{asset} {tf}] rows={len(df)}  {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}")

    feats = build_features(df)

    # فضای جستجوی «شناور» — عمداً اعداد غیر-رند هم آزموده می‌شوند
    grid = dict(
        bp=[14, 20, 30],
        mult=[1.8, 2.0, 2.4],
        rp=[9, 14, 21],
        rsi_lo=[22, 27, 32],
        rsi_hi=[68, 73, 78],
        ap=[14, 20],
        adx_gate=[18, 22, 26],
        sp=[30, 50],
        slope_tol=[0.15, 0.40],
        sl_mult=[1.2, 1.6],
        tp_mult=[1.0, 1.5, 2.2],
        max_hold=[24, 48],
    )
    keys = list(grid.keys())
    best = []
    total = 1
    for k in keys:
        total *= len(grid[k])
    print(f"grid size = {total}")

    tested = 0
    for combo in itertools.product(*[grid[k] for k in keys]):
        cfg = dict(zip(keys, combo))
        # قیدِ منطقی: نسبتِ RR معنادار
        trades, med_tp = run_config(df, feats, cfg, asset)
        tested += 1
        if trades is None or len(trades) < rqs.N_FLOOR:
            continue
        r = rqs.compute_rqs(trades, asset,
                            sl_pip=float(np.median(trades['sl_pip'])),
                            tp_pip=med_tp)
        m = r['metrics']
        # فقط کاندیداهای امیدوارکننده را نگه دار (برای سرعت)
        if m['win_rate'] >= 55 and m['profit_factor'] >= 1.15:
            best.append((r['rqs_score'], r['passed'], cfg, m, r['gates']))

    best.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f"\ntested={tested}  promising={len(best)}")
    print("=" * 100)
    for score, passed, cfg, m, gates in best[:15]:
        gl = ''.join('1' if gates[g] else '0' for g in ['G0','G1','G2','G3','G4','G5'])
        print(f"RQS={score:5.1f} {'PASS' if passed else 'FAIL'} G[{gl}] "
              f"n={m['n_trades']:4d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} | bp{cfg['bp']} m{cfg['mult']} rsi{cfg['rp']}"
              f"[{cfg['rsi_lo']}/{cfg['rsi_hi']}] adx{cfg['ap']}<{cfg['adx_gate']} "
              f"sl{cfg['sl_mult']}tp{cfg['tp_mult']} mh{cfg['max_hold']}")


if __name__ == '__main__':
    main()
