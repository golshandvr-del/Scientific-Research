# -*- coding: utf-8 -*-
"""
s336_scan_tpsl_adaptive.py — TP/SL تطبیقی (ATR) + بهترین جفت‌فیلترها
====================================================================
درسِ نهاییِ اسکن‌ها: بهترین جفت‌فیلترِ شورت به PF=۰.۹۲ رسید (نزدیکِ breakeven ولی
هنوز منفی). breakeven-WR با spread=۳.۳ برای TP50/SL40 ≈ ۴۸.۱٪ است و ما ۴۷.۵٪
گرفتیم — «مویی» کم داریم. طبق «قانونِ شاید هیچ‌چیز ثابت نیست»، TP/SL را از حالتِ
ثابت به تطبیقیِ ATR می‌بریم و شبکه‌ی گسترده‌ای از نسبت‌ها را می‌آزماییم تا
ببینیم آیا هیچ پیکربندی‌ای PF>1.10 با n≥120 می‌سازد یا این لایه واقعاً مرده است.
"""
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib


def run(asset='XAUUSD', tf='M5', min_n=120):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    n = len(df)
    crsi = ib.compute('crsi', df).values
    base = np.r_[False, (crsi[:-1] >= 82) & (crsi[1:] < 82)]

    def s(nm):
        return np.nan_to_num(ib.compute(nm, df).shift(1).values, nan=0.0)
    entropy = ib.compute('entropy', df).shift(1).values
    efi = ib.compute('efi', df).shift(1).values
    chop = ib.compute('chop', df).shift(1).values
    skew = ib.compute('skew', df).shift(1).values

    filt_A = np.nan_to_num((entropy < 2.4), nan=False).astype(bool) & \
             np.nan_to_num((efi < 0), nan=False).astype(bool)
    filt_B = np.nan_to_num((chop > 60), nan=False).astype(bool) & \
             np.nan_to_num((skew < 0), nan=False).astype(bool)

    def evaluate(mask, tp, sl):
        sig = base & mask
        tr = se.simulate_trades(df, np.zeros(n, bool), sig, sl, tp, asset, 24, False)
        if len(tr) < min_n:
            return None
        wr = (tr['outcome'] == 'win').mean() * 100
        wins = tr.loc[tr.pnl_pip > 0, 'pnl_pip'].sum()
        loss = -tr.loc[tr.pnl_pip <= 0, 'pnl_pip'].sum()
        pf = wins / loss if loss > 0 else 9.99
        return len(tr), wr, pf, tr['pnl_pip'].sum()

    print(f"=== TP/SL SWEEP {asset}/{tf} crsi_dn82 SHORT min_n={min_n} ===")
    # نسبت‌های غیررندِ TP/SL (pip). breakeven پایین‌تر با TP بزرگ‌تر
    grid = [(60, 40), (72, 45), (89, 55), (100, 55), (110, 60), (120, 70),
            (144, 80), (55, 40), (72, 55), (89, 72), (100, 72), (55, 34)]
    for label, filt in [('entropy<2.4&efi<0', filt_A), ('chop>60&skew<0', filt_B)]:
        print(f"\n--- filter: {label} (base_n={int((base&filt).sum())}) ---")
        print(f"{'TP/SL':>10s} {'n':>5s} {'WR':>5s} {'PF':>5s} {'net(pip)':>9s} {'be-WR':>6s}")
        for tp, sl in grid:
            r = evaluate(filt, tp, sl)
            if r is None:
                continue
            be = (sl + 3.3) / (tp + sl) * 100
            flag = ' <==' if r[2] > 1.05 else (' ~' if r[2] > 1.0 else '')
            print(f"   TP{tp}/SL{sl:<3d} {r[0]:>5d} {r[1]:>5.1f} {r[2]:>5.2f} {r[3]:>9.0f} "
                  f"{be:>5.1f}%{flag}")


if __name__ == '__main__':
    run('XAUUSD', 'M5')
