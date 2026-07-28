# -*- coding: utf-8 -*-
"""
s336_scan_allbank.py — اسکنِ کلِ جعبه‌ابزار (۴۰۰+ اندیکاتور) به‌عنوان فیلتر
=========================================================================
درس تا اینجا: تریگرِ افراط + فیلترِ رژیمِ آشنا (hurst/chop/r2) یا n را می‌کُشد یا
edge را کافی مثبت نمی‌کند. طبق User Note («۴۰۰ اندیکاتور را تست کن») این‌بار
*همه‌ی* بانک را به‌صورت خودکار به‌عنوان فیلتر امتحان می‌کنیم و آن‌هایی را
می‌یابیم که PF>1.05 را با n بالا (پُرمعامله) حفظ می‌کنند.

روش (کارآمد): سیگنالِ خامِ تریگر یک‌بار؛ برای هر اندیکاتور دو جهتِ آستانه
(بالای صدک۶۰ و پایینِ صدک۴۰) را به‌عنوان ماسک تست می‌کنیم. معیارِ رتبه: PF×log(n).
"""
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib
from strategies.s336_diag_triggers import build_triggers


def scan(asset='XAUUSD', tf='M5', trigger='crsi_cross_dn82', tp=50, sl=40, min_n=300):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    n = len(df)
    trig = build_triggers(df)
    base = trig[trigger]
    print(f"=== ALL-BANK SCAN {asset}/{tf} trigger={trigger} raw_n={int(base.sum())} "
          f"TP{tp}/SL{sl} min_n={min_n} ===")

    # baseline بدون فیلتر
    def evaluate(mask):
        sig = base & mask
        tr = se.simulate_trades(df, np.zeros(n, bool), sig, sl, tp, asset, 24, False)
        if len(tr) < min_n:
            return None
        wins = tr.loc[tr.pnl_pip > 0, 'pnl_pip'].sum()
        loss = -tr.loc[tr.pnl_pip <= 0, 'pnl_pip'].sum()
        pf = wins / loss if loss > 0 else 9.99
        wr = (tr['outcome'] == 'win').mean() * 100
        return len(tr), wr, pf, tr['pnl_pip'].sum()

    b = evaluate(np.ones(n, bool))
    print(f"baseline: n={b[0]} WR={b[1]:.1f} PF={b[2]:.2f} net={b[3]:.0f}pip\n")

    # همهٔ اندیکاتورها
    allnames = []
    for cat in ['momentum', 'volatility', 'cycle', 'statistical', 'trend', 'volume', 'pattern']:
        allnames += ib.by_category(cat)
    allnames = sorted(set(allnames))

    results = []
    for nm in allnames:
        try:
            s = ib.compute(nm, df).shift(1)
            v = s.values
            if np.isnan(v).mean() > 0.5:
                continue
            hi = np.nanquantile(v, 0.60)
            lo = np.nanquantile(v, 0.40)
            if not np.isfinite(hi) or not np.isfinite(lo) or hi == lo:
                continue
            for direction, mask in [(f'{nm}>p60', v > hi), (f'{nm}<p40', v < lo)]:
                r = evaluate(mask)
                if r is None:
                    continue
                ntr, wr, pf, net = r
                score = pf * np.log(ntr)
                results.append((score, direction, ntr, wr, pf, net))
        except Exception:
            continue

    results.sort(reverse=True)
    print(f"{'filter':22s} {'n_tr':>6s} {'WR':>5s} {'PF':>5s} {'net(pip)':>9s} {'score':>6s}")
    for r in results[:25]:
        print(f"{r[1]:22s} {r[2]:>6d} {r[3]:>5.1f} {r[4]:>5.2f} {r[5]:>9.0f} {r[0]:>6.2f}")


if __name__ == '__main__':
    import sys
    trig = sys.argv[1] if len(sys.argv) > 1 else 'crsi_cross_dn82'
    scan('XAUUSD', 'M5', trigger=trig)
