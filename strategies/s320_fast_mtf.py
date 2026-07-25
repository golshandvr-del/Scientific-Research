# -*- coding: utf-8 -*-
"""
S320 — اسکنِ سریعِ هدفمندِ مولتی-TF برای احیای S01 (BB+RSI Mean-Reversion).

بهینه‌سازیِ سرعت (پاسخ به کندیِ موتورِ رویداد-محور روی داده‌های بزرگ):
  1. گریدِ کوچکِ هدفمند (حول ناحیهٔ امیدوارکنندهٔ کشف‌شده روی M5:
     rsi≈[25/80], adx<20، sl/tp نامتقارن) — نه گریدِ کورِ ۷۷۷۶‌تایی.
  2. featureها یک‌بار کش می‌شوند.
  3. غربالِ سبکِ برداری (n/WR/PF) و فقط بهترین‌ها به RQS+ کامل می‌روند.

اجرا:  python3 strategies/s320_fast_mtf.py XAUUSD M15 [max_seconds]
هر TF جداگانه اجرا می‌شود تا از timeout پرهیز شود؛ گزارشِ مرحله‌به‌مرحله.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs

TF_FILE = {'M5':'data/{a}_M5.csv','M15':'data/{a}_M15.csv','M30':'data/{a}_M30.csv',
           'H1':'data/{a}_H1.csv','H4':'data/{a}_H4.csv'}

# گریدِ هدفمندِ کوچک — «شناور» ولی متمرکز حولِ ناحیهٔ امیدوارکننده
GRID = dict(
    bp=[20], mult=[2.0, 2.4],
    rp=[14], rsi_lo=[22, 27], rsi_hi=[73, 78],
    ap=[14], adx_gate=[18, 22, 27],
    sp=[40], slope_tol=[0.35],
    sl_mult=[1.0, 1.3, 1.6], tp_mult=[1.4, 2.0, 2.6],
    max_hold=[48],
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
    n = len(trades)
    if n == 0:
        return 0, 0, 0, 0
    pnl = trades['pnl_pip'].values
    wins = (pnl > 0).sum()
    wr = wins / n * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 999
    return n, wr, pf, pnl.sum()


def main():
    import itertools
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M15'
    max_sec = float(sys.argv[3]) if len(sys.argv) > 3 else 500.0
    df = se.load_data(TF_FILE[tf].format(a=asset))
    feats = build_features(df)
    keys = list(GRID.keys())
    total = 1
    for k in keys: total *= len(GRID[k])
    print(f"[{asset} {tf}] rows={len(df)}  grid={total}  {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}", flush=True)

    t0 = time.time()
    shortlist = []
    tested = 0
    for combo in itertools.product(*[GRID[k] for k in keys]):
        cfg = dict(zip(keys, combo))
        ls, ss, sl, tp = make_signals(feats, cfg, asset)
        trades = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=cfg['max_hold'], allow_overlap=False)
        tested += 1
        n, wr, pf, net = lite_stats(trades)
        sig = ls | ss
        med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
        shortlist.append((pf, wr, n, net, cfg, trades, med_tp))
        print(f"  [{tested}/{total}] n={n:4d} WR={wr:4.1f} PF={pf:.2f} net_pip={net:6.0f} "
              f"| m{cfg['mult']} rsi[{cfg['rsi_lo']}/{cfg['rsi_hi']}] adx<{cfg['adx_gate']} "
              f"sl{cfg['sl_mult']}tp{cfg['tp_mult']}", flush=True)

    print(f"\ntested={tested} elapsed={time.time()-t0:.0f}s", flush=True)
    # RQS کامل روی کاندیداهایی که n کافی و PF>=1.1 دارند (تا حداکثر ۲۰ تا)
    cand = [x for x in shortlist if x[2] >= rqs.N_FLOOR and x[0] >= 1.05]
    cand.sort(key=lambda x: x[0], reverse=True)
    print(f"full-RQS on {min(len(cand),20)} candidates:")
    results = []
    for pf, wr, n, net, cfg, trades, med_tp in cand[:20]:
        r = rqs.compute_rqs(trades, asset, sl_pip=float(np.median(trades['sl_pip'])), tp_pip=med_tp)
        results.append((r['rqs_score'], r['passed'], cfg, r['metrics'], r['gates']))
    results.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print("=" * 110)
    for score, passed, cfg, m, gates in results:
        gl = ''.join('1' if gates[g] else '0' for g in ['G0','G1','G2','G3','G4','G5'])
        print(f"RQS={score:5.1f} {'PASS' if passed else 'FAIL'} G[{gl}] "
              f"n={m['n_trades']:4d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} wf={m['wf_nets']} half={m['half_nets']} | "
              f"m{cfg['mult']} rsi[{cfg['rsi_lo']}/{cfg['rsi_hi']}] adx<{cfg['adx_gate']} "
              f"sl{cfg['sl_mult']}tp{cfg['tp_mult']}")
    if not results:
        print("NO CANDIDATE with n>=floor & PF>=1.05")


if __name__ == '__main__':
    main()
