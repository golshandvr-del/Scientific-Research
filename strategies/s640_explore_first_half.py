# -*- coding: utf-8 -*-
"""
S640 — KamaRegimeCross — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
====================================================================
قانونِ مسیرِ C: جست‌وجو آزاد روی نیمهٔ اول؛ نیمهٔ دوم تا آزمونِ نهایی لمس نمی‌شود.
این اسکریپت *هرگز* به df.iloc[half:] دست نمی‌زند.

مفهوم:
  LONG  = close از KAMA(10,2,30) به بالا عبور کند و شیبِ KAMA مثبت باشد
  SHORT = آینهٔ کامل (عبور به پایین + شیبِ منفی)
هندسه: SL = k × ATR(100) میانه (نیمهٔ اول)، TP = SL (RR=1.0 — هرگز TP<SL)
پارامترهای آزاد در اکتشاف: k ∈ {1.5, 3.0, 4.5} و slope_len ∈ {1, 3}
(در آزمونِ نهایی فقط «یک» سلولِ پیش‌ثبت‌شده اجرا می‌شود.)

خروجی: results/_s640_explore/<TF>.json  — طبق قانونِ اندک‌اندک، هر TF بلافاصله ذخیره.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s640_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1  # XAUUSD: 1 pip = 0.1 $/oz  (اسپرد 0.33$ = 3.3 pip)
TFS = ['M1','M2','M3','M4','M5','M6','M10','M12','M15','M20','M30',
       'H1','H2','H3','H4','H6','H8','H12','D1','W1','MN1']
K_GRID = [1.5, 3.0, 4.5]
SLOPE_GRID = [1, 3]
MAX_HOLD = 64

def atr_pips_median(df):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(100).mean()
    return float(np.nanmedian(atr.values)) / PIP

def wr_pf(tr):
    if tr is None or len(tr) == 0:
        return 0, 0.0, 0.0
    pnl = tr['pnl_pip'].values
    n = len(pnl)
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    wr = 100.0 * len(wins) / n
    pf = float(wins.sum() / max(1e-9, -losses.sum())) if len(losses) else float('inf')
    return n, wr, pf

def run_tf(tf):
    t0 = time.time()
    try:
        d = fd.load_fast('XAUUSD', tf)
    except Exception as e:
        return {'tf': tf, 'error': f'load: {e}'}
    df_all = fd.as_dataframe(d)
    half = len(df_all) // 2
    df = df_all.iloc[:half].reset_index(drop=True)   # ← فقط نیمهٔ اول
    if len(df) < 3000:
        note = 'n_bars_first_half<3000 — اکتشاف کم‌توان'
    else:
        note = ''
    kama = ib.compute('kama', df).values
    close = df['close'].values
    prev_c = np.roll(close, 1); prev_c[0] = close[0]
    prev_k = np.roll(kama, 1);  prev_k[0] = kama[0]
    sl_base = atr_pips_median(df)
    cells = []
    for slope_len in SLOPE_GRID:
        k_sh = np.roll(kama, slope_len); k_sh[:slope_len] = kama[:slope_len]
        slope_up = kama > k_sh
        slope_dn = kama < k_sh
        cross_up = (prev_c <= prev_k) & (close > kama)
        cross_dn = (prev_c >= prev_k) & (close < kama)
        long_sig  = cross_up & slope_up
        short_sig = cross_dn & slope_dn
        for k in K_GRID:
            sl = max(1.0, round(k * sl_base, 1)); tp = sl  # RR=1.0
            tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                    asset='XAUUSD', max_hold=MAX_HOLD, allow_overlap=False)
            n, wr, pf = wr_pf(tr)
            # خریدارِ کور با همان هندسه (نولِ هم‌هندسه — درسِ S385)
            all_long = np.ones(len(df), dtype=bool)
            trb = se.simulate_trades(df, all_long, ~all_long, sl_pip=sl, tp_pip=tp,
                                     asset='XAUUSD', max_hold=MAX_HOLD, allow_overlap=False)
            nb, wrb, _ = wr_pf(trb)
            # per-side
            trL = se.simulate_trades(df, long_sig, np.zeros(len(df), bool), sl_pip=sl, tp_pip=tp,
                                     asset='XAUUSD', max_hold=MAX_HOLD, allow_overlap=False)
            trS = se.simulate_trades(df, np.zeros(len(df), bool), short_sig, sl_pip=sl, tp_pip=tp,
                                     asset='XAUUSD', max_hold=MAX_HOLD, allow_overlap=False)
            nL, wrL, _ = wr_pf(trL); nS, wrS, _ = wr_pf(trS)
            lift = wr - wrb
            z = lift / (100.0 * np.sqrt(max(wrb,1)/100*(1-max(wrb,1)/100) / max(n,1))) if n else 0.0
            cost_to_sl = 100.0 * 3.3 / sl
            cells.append({'slope_len': slope_len, 'k': k, 'sl_pip': sl, 'tp_pip': tp,
                          'n': n, 'wr': round(wr,2), 'pf': round(pf,3),
                          'wr_blind': round(wrb,2), 'n_blind': nb,
                          'lift_pp': round(lift,2), 'z_naive': round(z,2),
                          'lift_sqrt_n': round(lift*np.sqrt(max(n,0)),1),
                          'nL': nL, 'wrL': round(wrL,2), 'nS': nS, 'wrS': round(wrS,2),
                          'cost_to_sl_pct': round(cost_to_sl,1)})
    return {'tf': tf, 'n_bars_first_half': int(half), 'sl_base_atr_pip': round(sl_base,1),
            'note': note, 'elapsed_s': round(time.time()-t0,1), 'cells': cells}

if __name__ == '__main__':
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        res = run_tf(tf)
        with open(os.path.join(OUT, f'{tf}.json'), 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        best = max(res.get('cells', []), key=lambda c: c['lift_sqrt_n'], default=None)
        print(f"[S640-explore] {tf} done in {res.get('elapsed_s','?')}s | "
              f"best lift·√n = {best['lift_sqrt_n'] if best else 'NA'}", flush=True)
    print('[S640-explore] ALL DONE', flush=True)
