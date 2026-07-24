# -*- coding: utf-8 -*-
"""
RQS+ Audit (Price-Action #2) — S172 (Two-Legs), S173 (Market Inertia SHORT),
S186 (Close-Strength). بازتولید با پارامترهای مستندِ finalize + RQS+.
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


def main():
    print("="*120)
    print("RQS+ AUDIT #2 — S172 / S173 / S186 (۶ گیت، veto). G0=WR≥60٪ & n≥30")
    print("="*120)
    results = {}
    df = load('XAUUSD', 'M15')
    z = np.zeros(len(df), bool)

    # S173 Market Inertia SHORT — ema20/50 adx>28 lb20 SL250/TP375 mh48
    try:
        from s173_brooks_market_inertia import inertia_signals
        sig = inertia_signals(df, 20, 50, 28, 20, 'short')
        sig = pd.Series(sig).shift(1).fillna(False).to_numpy()
        results['S173_MarketInertia_SHORT'] = score('S173_MarketInertia_SHORT', df, z, sig,
                                                    250, 375, 48, 'XAUUSD')
    except Exception as e:
        print(f"S173 | ERROR: {e}"); results['S173_MarketInertia_SHORT'] = {'verdict': f'ERROR: {e}'}

    # S172 Two-Legs reversal LONG — k5 tol0.001 lb30 SL250/TP375 mh48
    try:
        from s172_brooks_two_legs import two_leg_reversal_signals
        sig = two_leg_reversal_signals(df, 5, 0.001, 30, 'long')
        sig = pd.Series(sig).shift(1).fillna(False).to_numpy()
        results['S172_TwoLegs_LONG'] = score('S172_TwoLegs_LONG', df, sig, z,
                                             250, 375, 48, 'XAUUSD')
    except Exception as e:
        print(f"S172 | ERROR: {e}"); results['S172_TwoLegs_LONG'] = {'verdict': f'ERROR: {e}'}

    # S186 Close-Strength LONG — ema20/50 br0.5 cp0.6 lb (نمونهٔ مستند)
    try:
        from s186_brooks_close_strength import close_strength_signals
        sig = close_strength_signals(df, 'long', 0.5, 0.6, 20, 20, 50)
        sig = pd.Series(sig).shift(1).fillna(False).to_numpy()
        results['S186_CloseStrength_LONG'] = score('S186_CloseStrength_LONG', df, sig, z,
                                                   200, 300, 96, 'XAUUSD')
    except Exception as e:
        print(f"S186 | ERROR: {e}"); results['S186_CloseStrength_LONG'] = {'verdict': f'ERROR: {e}'}

    out = os.path.join(ROOT, 'results', '_rqs_audit_priceaction2.json')
    with open(out, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nنتایج ذخیره شد: {out}")


if __name__ == '__main__':
    main()
