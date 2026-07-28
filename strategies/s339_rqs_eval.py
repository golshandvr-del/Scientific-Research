# -*- coding: utf-8 -*-
"""
s339_rqs_eval.py — سنجشِ RQS+ کامل برای لایهٔ `r2_low × zscore_high` (long)

از S338c، جفتِ `r2_fib_89(lt) × zscore_fib_233(gt)` گاردِ k-fold را رد کرد (REAL, 4/5).
حالا آن را به یک لایهٔ واقعی تبدیل و RQS+ کامل (۶ گیت) می‌گیریم.

آزمون‌ها:
  A) آستانهٔ تثبیت‌شده + جستجوی TP/SL غیررند (شبکهٔ ATR-mult).
  B) گزارشِ کاملِ RQS+ برای بهترین پیکربندی.
  C) holdout نهایی: آخرین ۲۰٪ داده هرگز در تیونینگ استفاده نشود.
"""
import sys
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def atr_series_pips(df, asset):
    return (ib.compute('atr_fib_13', df) / se.ASSETS[asset]['pip'])


def build_signals(df, th_r2, th_z, r2_name='r2_fib_89', z_name='zscore_fib_233'):
    r2 = ib.compute(r2_name, df).shift(1).values
    z = ib.compute(z_name, df).shift(1).values
    long_sig = (r2 < th_r2) & (z > th_z)
    long_sig = np.nan_to_num(long_sig, nan=0).astype(bool)
    short_sig = np.zeros(len(df), dtype=bool)
    return long_sig, short_sig


def eval_config(df, asset, long_sig, short_sig, sl_pip, tp_pip, max_hold=24):
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, asset,
                            max_hold=max_hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy()
    tr['tp_pip'] = float(tp_pip) if np.isscalar(tp_pip) else tp_pip
    res = rqs.compute_rqs(tr, asset, sl_pip, tp_pip)
    n = len(tr)
    wr = (tr['pnl_pip'] > 0).mean() * 100
    gross_win = tr.loc[tr['pnl_pip'] > 0, 'pnl_pip'].sum()
    gross_loss = -tr.loc[tr['pnl_pip'] < 0, 'pnl_pip'].sum()
    pf = gross_win / gross_loss if gross_loss > 0 else 99
    return dict(n=n, wr=wr, pf=pf, res=res, trades=tr)


def gates_str(res):
    g = res.get('gates', {})
    return ''.join('1' if g.get(k) else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def run(asset='XAUUSD', tf='M5'):
    print(f"\n=== S339 RQS+ EVAL {asset}/{tf} — r2_low × zscore_high (long) ===", flush=True)
    df = load(asset, tf)
    n_all = len(df)
    # holdout: آخرین ۲۰٪ کنار گذاشته می‌شود برای تستِ نهایی
    cut = int(n_all * 0.8)
    df_tune = df.iloc[:cut].reset_index(drop=True)
    df_hold = df.iloc[cut:].reset_index(drop=True)
    print(f"n_all={n_all}  tune=0..{cut}  holdout={cut}..{n_all}", flush=True)

    atrp_tune = float(np.nanmedian(atr_series_pips(df_tune, asset)))
    print(f"ATR median (tune) = {atrp_tune:.1f} pip\n", flush=True)

    # شبکهٔ آستانه (غیررند، حولِ مقادیرِ k-fold) و TP/SL (ضریبِ ATR غیررند)
    th_r2_grid = [0.03, 0.04, 0.05, 0.06]
    th_z_grid = [1.8, 2.0, 2.2]
    # TP/SL: ضرایبِ ATR — شاملِ متقارن و نامتقارنِ واقعی (نه تقلبِ TP<SL)
    tpsl_grid = [
        (1.5, 1.5), (1.5, 2.0), (1.5, 2.5), (2.0, 2.0),
        (2.0, 3.0), (1.0, 1.5), (2.5, 2.5), (1.5, 3.0),
    ]  # (sl_mult, tp_mult)

    print(f"{'th_r2':>6} {'th_z':>5} {'sl':>5} {'tp':>5} {'n':>5} {'/day':>5} "
          f"{'WR%':>6} {'PF':>5} {'RQS+':>6} {'gates':>7}", flush=True)
    print("-" * 68, flush=True)
    days_tune = cut / {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24, 'H4': 6, 'D1': 1}[tf]
    best = None
    for th_r2 in th_r2_grid:
        for th_z in th_z_grid:
            ls, ss = build_signals(df_tune, th_r2, th_z)
            if ls.sum() < 30:
                continue
            for sl_m, tp_m in tpsl_grid:
                sl = atrp_tune * sl_m
                tp = atrp_tune * tp_m
                r = eval_config(df_tune, asset, ls, ss, sl, tp)
                if r is None or r['n'] < 30:
                    continue
                rq = r['res'].get('rqs_score', 0)
                gs = gates_str(r['res'])
                perday = r['n'] / days_tune
                marker = ''
                # امتیازدهی: اولویت با RQS+ بالا، بعد WR
                sc = rq * 1000 + r['wr']
                if best is None or sc > best['sc']:
                    best = dict(sc=sc, th_r2=th_r2, th_z=th_z, sl=sl, tp=tp,
                                sl_m=sl_m, tp_m=tp_m, r=r, gs=gs, rq=rq, perday=perday)
                    marker = ' *'
                if rq > 0 or r['wr'] >= 55:
                    print(f"{th_r2:>6.2f} {th_z:>5.1f} {sl:>5.0f} {tp:>5.0f} {r['n']:>5} "
                          f"{perday:>5.2f} {r['wr']:>6.1f} {r['pf']:>5.2f} {rq:>6.1f} {gs:>7}{marker}", flush=True)

    if best is None:
        print("\nهیچ پیکربندیِ معتبری یافت نشد."); return
    print(f"\n=== بهترین (tune): th_r2={best['th_r2']} th_z={best['th_z']} "
          f"SL={best['sl']:.0f} TP={best['tp']:.0f} RQS+={best['rq']:.1f} WR={best['r']['wr']:.1f}% "
          f"n={best['r']['n']} /day={best['perday']:.2f} gates={best['gs']} ===", flush=True)

    # === HOLDOUT نهایی ===
    print("\n--- HOLDOUT (آخرین ۲۰٪، هرگز تیون نشده) ---", flush=True)
    ls_h, ss_h = build_signals(df_hold, best['th_r2'], best['th_z'])
    atrp_h = float(np.nanmedian(atr_series_pips(df_hold, asset)))
    sl_h = atrp_h * best['sl_m']; tp_h = atrp_h * best['tp_m']
    rh = eval_config(df_hold, asset, ls_h, ss_h, sl_h, tp_h)
    if rh is None or rh['n'] < 10:
        print(f"holdout n خیلی کم ({rh['n'] if rh else 0}) — نتیجه‌گیری محتاطانه.")
    else:
        print(f"holdout: n={rh['n']} WR={rh['wr']:.1f}% PF={rh['pf']:.2f} "
              f"RQS+={rh['res'].get('rqs_score',0):.1f} gates={gates_str(rh['res'])}", flush=True)
    # گزارشِ کاملِ گیت‌های بهترین پیکربندی روی کلِ داده
    print("\n--- RQS+ کامل روی کلِ داده (best config) ---", flush=True)
    ls_a, ss_a = build_signals(df, best['th_r2'], best['th_z'])
    atrp_a = float(np.nanmedian(atr_series_pips(df, asset)))
    ra = eval_config(df, asset, ls_a, ss_a, atrp_a*best['sl_m'], atrp_a*best['tp_m'])
    if ra:
        import json
        print(f"n={ra['n']} WR={ra['wr']:.1f}% PF={ra['pf']:.2f}")
        print("gates:", ra['res'].get('gates'))
        print("metrics:", json.dumps(ra['res'].get('metrics', {}), ensure_ascii=False, default=str)[:500])
        print("rqs_score:", ra['res'].get('rqs_score'))


if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD',
        sys.argv[2] if len(sys.argv) > 2 else 'M5')
