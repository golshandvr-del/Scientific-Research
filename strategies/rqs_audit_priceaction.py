# -*- coding: utf-8 -*-
"""
RQS+ Audit (Price-Action) — ممیزیِ لایه‌های price-action فعالِ سایت طبقِ RQS+
================================================================================
لایه‌ها: S168 (High-2), S171 (Signs-of-Strength), S172 (Two-Legs),
         S173 (Market Inertia SHORT), S185 (1-2-3), S186 (Close-Strength).
هرکدام با پارامترهای مستندش بازتولید و RQS+ روی trades محاسبه می‌شود.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs

se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load(pair, tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', f'{pair}_{tf}.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def score(name, df, ls, shs, sl, tp, mh, asset):
    t = se.simulate_trades(df, ls, shs, sl, tp, asset, max_hold=mh, allow_overlap=False)
    if t is None or len(t) == 0:
        print(f"{name:28s} | NO TRADES"); return {'verdict': 'REJECT (no trades)'}
    t = t.copy(); t['sl_pip'] = float(sl); t['tp_pip'] = float(tp)
    r = rqs.compute_rqs(t, asset, sl_pip=sl, tp_pip=tp)
    print(rqs.format_report(name, r)); return r


# ---------- S171 Signs of Strength (WIN32 THR2 SL300 TP450 MH96, XAU long) ----------
def s171_sig(df):
    from s171_brooks_signs_of_strength_filter import signs_of_strength_bull
    sos = signs_of_strength_bull(df, ema_period=20, win=32)
    strong = sos['score'] >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


# ---------- S168 Brooks High-2 (EMA fast/slow, XAU long) ----------
def s168_sig(df):
    from s168_brooks_high2_low2 import count_high2_low2
    long_evt, short_evt = count_high2_low2(df, 20, 50)
    return pd.Series(long_evt).shift(1).fillna(False).to_numpy()


def main():
    print("="*120)
    print("RQS+ AUDIT — لایه‌های price-action فعالِ سایت (۶ گیت، veto). G0=WR≥60٪ & n≥30")
    print("="*120)
    results = {}
    df = load('XAUUSD', 'M15')

    # S171
    try:
        results['S171_SignsOfStrength'] = score('S171_SignsOfStrength', df, s171_sig(df),
                                                np.zeros(len(df), bool), 300, 450, 96, 'XAUUSD')
    except Exception as e:
        print(f"S171 | ERROR: {e}"); results['S171_SignsOfStrength'] = {'verdict': f'ERROR: {e}'}

    # S168
    try:
        results['S168_BrooksHigh2'] = score('S168_BrooksHigh2', df, s168_sig(df),
                                            np.zeros(len(df), bool), 150, 300, 96, 'XAUUSD')
    except Exception as e:
        print(f"S168 | ERROR: {e}"); results['S168_BrooksHigh2'] = {'verdict': f'ERROR: {e}'}

    out = os.path.join(ROOT, 'results', '_rqs_audit_priceaction.json')
    with open(out, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nنتایج ذخیره شد: {out}")


if __name__ == '__main__':
    main()
