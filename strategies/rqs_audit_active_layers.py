# -*- coding: utf-8 -*-
"""
RQS+ Audit — ممیزیِ همهٔ لایه‌های فعالِ سایت طبقِ معیارِ RQS+ (۶ گیت، veto)
================================================================================
سندِ مرجع: docs/RQS_ROBUST_QUALITY_SCORE.md

هر لایهٔ فعال (طبقِ README + web_tool/src/router.ts + eurusd_router.ts) با پارامترهای
مستندش بازتولید می‌شود و RQS+ روی خروجیِ trades محاسبه می‌گردد.

هدف: تعیینِ اینکه کدام لایه گیتِ سختِ جدید (به‌ویژه G0=WR≥۶۰٪) را پاس می‌کند.
"""
import os, sys, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import rqs

DATA = lambda p, tf: os.path.join(ROOT, 'data', f'{p}_{tf}.csv')

# هزینهٔ واقعیِ حساب (طبقِ مشخصاتِ دمو)
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load(pair, tf):
    df = pd.read_csv(DATA(pair, tf))
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['dt'] = dt
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def add_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank'] - days['cnt'] - 1
    m = dict(zip(days['date'], days['from_end']))
    df['from_end'] = df['date'].map(m).astype(int)
    df['dom_rank'] = df['date'].map(dict(zip(days['date'], days['rank']))).astype(int)
    return df


def sim_and_rqs(df, long_sig, short_sig, sl, tp, mh, asset):
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy()
    tr['sl_pip'] = float(sl)
    tr['tp_pip'] = float(tp)
    return rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)


# ============ تعریفِ لایه‌های فعال (سیگنال + پارامترهای مستند) ============

def layer_S139_overnight(df):
    """XAUUSD Overnight Drift — long روی ساعت 22,23 UTC. SL/TP نمونهٔ مستند."""
    sig = np.isin(df['hour'].values, [22, 23])
    long_sig = pd.Series(sig).shift(1).fillna(False).to_numpy()
    return long_sig, np.zeros(len(df), bool), 150, 300, 16


def layer_S141_turnofmonth(df):
    """XAUUSD Turn-of-Month — long، اول ماه (from_end نزدیک شروع => dom_rank<=2)."""
    df = add_from_end(df)
    sig = (df['dom_rank'].values <= 2) & np.isin(df['hour'].values, list(range(7, 16)))
    long_sig = pd.Series(sig).shift(1).fillna(False).to_numpy()
    return long_sig, np.zeros(len(df), bool), 150, 300, 16


def layer_S144_endofmonth(df):
    """XAUUSD End-of-Month Pre-End — long، 6-8 روز مانده به پایان."""
    df = add_from_end(df)
    sig = np.isin(df['from_end'].values, [-8, -7, -6]) & np.isin(df['hour'].values, list(range(7, 16)))
    long_sig = pd.Series(sig).shift(1).fillna(False).to_numpy()
    return long_sig, np.zeros(len(df), bool), 150, 300, 16


def layer_S164_eurusd(df):
    """EURUSD Pre-Month-End Fix Reversal — short، from_end=-3، hour=13. SL15/TP20 mh12."""
    df = add_from_end(df)
    short_sig = (df['from_end'].values == -3) & (df['hour'].values == 13)
    return np.zeros(len(df), bool), short_sig, 15, 20, 12


def layer_S73_eurusd(df):
    """EURUSD Session-Open Drift — long ساعت 0 UTC + pullback. SL12/TP12 mh6."""
    hour = df['hour'].values
    n = len(df)
    is_h0 = np.zeros(n, bool)
    is_h0[:-1] = (hour[1:] == 0) & (hour[:-1] != 0)
    c = df['close'].values
    pull = np.zeros(n, bool)
    for i in range(4, n):
        pull[i] = c[i] < c[i-4]
    long_sig = is_h0 & pull
    return long_sig, np.zeros(len(df), bool), 12, 12, 6


LAYERS = [
    ('S139_Overnight',  'XAUUSD', 'M15', layer_S139_overnight),
    ('S141_TurnOfMonth','XAUUSD', 'M15', layer_S141_turnofmonth),
    ('S144_EndOfMonth', 'XAUUSD', 'M15', layer_S144_endofmonth),
    ('S164_EUR_PreEOM', 'EURUSD', 'M15', layer_S164_eurusd),
    ('S73_EUR_SessDrift','EURUSD','M15', layer_S73_eurusd),
]


def main():
    print("="*120)
    print("RQS+ AUDIT — لایه‌های فعالِ سایت (۶ گیت، veto). G0=WR≥60٪ & n≥30")
    print("="*120)
    results = {}
    for name, pair, tf, fn in LAYERS:
        try:
            df = load(pair, tf)
            long_sig, short_sig, sl, tp, mh = fn(df)
            r = sim_and_rqs(df, long_sig, short_sig, sl, tp, mh, pair)
            if r is None:
                print(f"{name:28s} | NO TRADES")
                results[name] = {'verdict': 'REJECT (no trades)'}
                continue
            print(rqs.format_report(name, r))
            results[name] = r
        except Exception as e:
            print(f"{name:28s} | ERROR: {e}")
            results[name] = {'verdict': f'ERROR: {e}'}
    out = os.path.join(ROOT, 'results', '_rqs_audit_active_layers.json')
    with open(out, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nنتایج ذخیره شد: {out}")


if __name__ == '__main__':
    main()
