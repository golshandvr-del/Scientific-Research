# -*- coding: utf-8 -*-
"""
S342 — اسکنِ پارامتریِ لبهٔ «MA-return پس از ≥N کندل دوری» (Brooks فصل ۱۸).
هدف: یافتنِ ترکیبِ per-TF که RQS+ ≥ ۸۰ بدهد. اعداد غیررند (اشتباه #۷)، از XAU M5 شروع.

بهینه‌سازی: اندیکاتورهای رژیم (r2/hurst) و MAها یک‌بار برای هر (kind,period) کش می‌شوند
تا اسکن روی داده‌های بزرگ (۲۰۰k کندل) در زمانِ معقول تمام شود.
اجرا:  python3 -m strategies.s342_scan XAUUSD M5
"""
import sys
import itertools
import numpy as np

from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs


# ---- نسخهٔ آرایه‌ایِ سریعِ منطقِ سیگنال (بدونِ محاسبهٔ مکررِ اندیکاتور) ----
def _run_above(c, ma):
    n = len(c); run = np.zeros(n, int); r = 0
    for i in range(n):
        if np.isfinite(ma[i]) and c[i] > ma[i]:
            r += 1
        else:
            r = 0
        run[i] = r
    return run


def _run_below(c, ma):
    n = len(c); run = np.zeros(n, int); r = 0
    for i in range(n):
        if np.isfinite(ma[i]) and c[i] < ma[i]:
            r += 1
        else:
            r = 0
        run[i] = r
    return run


def signals_fast(c, h, l, ma, run, reg, side, n_away, slope_lb):
    n = len(c); sig = np.zeros(n, bool)
    start = slope_lb + 2
    for i in range(start, n):
        if not reg[i]:
            continue
        mai = ma[i]; map = ma[i - slope_lb]
        if not (np.isfinite(mai) and np.isfinite(map)):
            continue
        if side == 'long':
            if mai <= map:            continue
            if run[i - 1] < n_away:   continue
            if l[i] <= mai and c[i - 1] > ma[i - 1]:
                sig[i] = True
        else:
            if mai >= map:            continue
            if run[i - 1] < n_away:   continue
            if h[i] >= mai and c[i - 1] < ma[i - 1]:
                sig[i] = True
    return sig


def scan(asset, tf, top=18):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    c = df['close'].to_numpy(float); h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    x = ib._c(df)
    print(f"# {asset} {tf} rows={len(df)}  (caching indicators...)")

    # کشِ MAها و runها
    ma_specs = [('ema', 21), ('ema', 34), ('ema', 55), ('sma', 34), ('sma', 55)]
    ma_cache = {}
    run_cache = {}
    for mk, mp in ma_specs:
        ma = (ib.ema_s(x, mp) if mk == 'ema' else ib.sma_s(x, mp)).to_numpy(float)
        ma_cache[(mk, mp)] = ma
        run_cache[('long', mk, mp)] = _run_above(c, ma)
        run_cache[('short', mk, mp)] = _run_below(c, ma)

    # کشِ رژیم‌ها
    r2_21 = ib.r2(df, p=21).to_numpy()
    hu_55 = ib.hurst(df, p=55).to_numpy()
    reg_cache = {
        'none':  np.ones(len(df), bool),
        'r220':  (r2_21 >= 0.20) & np.isfinite(r2_21),
        'r235':  (r2_21 >= 0.35) & np.isfinite(r2_21),
        'hu52':  (hu_55 >= 0.52) & np.isfinite(hu_55),
        'r235hu52': (r2_21 >= 0.35) & (hu_55 >= 0.52) & np.isfinite(r2_21) & np.isfinite(hu_55),
    }

    n_aways   = [8, 13, 21]
    slope_lbs = [3, 5, 8]
    sltps     = [(120, 240), (150, 300), (180, 360), (200, 340)]
    regs      = list(reg_cache.keys())
    print("# scanning...")

    results = []
    for (mk, mp) in ma_specs:
        ma = ma_cache[(mk, mp)]
        for side in ('long', 'short'):
            run = run_cache[(side, mk, mp)]
            for na, sl_lb, rkey in itertools.product(n_aways, slope_lbs, regs):
                reg = reg_cache[rkey]
                s = signals_fast(c, h, l, ma, run, reg, side, na, sl_lb)
                if s.sum() < 30:
                    continue
                long_sig = s if side == 'long' else np.zeros(len(df), bool)
                short_sig = s if side == 'short' else np.zeros(len(df), bool)
                for (slp, tpp) in sltps:
                    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=slp, tp_pip=tpp,
                                            asset=asset, max_hold=48, allow_overlap=False)
                    if len(tr) < 30:
                        continue
                    r = rqs.compute_rqs(tr, asset, sl_pip=slp, tp_pip=tpp)
                    m = r['metrics']
                    results.append((r['rqs_score'], r['verdict'], side, mk, mp, na, sl_lb,
                                    rkey, slp, tpp, m.get('n_trades', 0),
                                    m.get('win_rate', 0), m.get('profit_factor', 0),
                                    m.get('max_dd_pct', 0), m.get('max_consec_losses', 0),
                                    m.get('p_value', 1)))

    results.sort(key=lambda t: -t[0])
    print(f"# tested {len(results)} valid combos; TOP {top}:")
    for row in results[:top]:
        (rqsv, verd, side, mk, mp, na, sl_lb, rkey, slp, tpp,
         nt, wr, pf, dd, mcl, pv) = row
        print(f"RQS={rqsv:5.1f} {verd:6s} {side:5s} {mk}{mp} N={na} slope={sl_lb} "
              f"reg={rkey:9s} SL/TP={slp}/{tpp} | n={nt} WR={wr:.1f} "
              f"PF={pf:.2f} DD={dd:.1f} MCL={mcl} p={pv:.3f}")
    return results


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    scan(asset, tf)
