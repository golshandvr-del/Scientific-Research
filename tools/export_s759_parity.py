# -*- coding: utf-8 -*-
"""S759 — مرجعِ عددیِ پریتی برای پورتِ TS (web_tool/src/informed_structure_s759.ts)

از ماشینِ منجمدِ حکم (strategies/s759_informed_structure.py، L=5) روی همان سری‌ای
که حکم روی آن صادر شد (H1 رسمیِ mt5_full → H4 با resample('4h')) خروجی می‌گیرد:
  · زمانِ همهٔ کندل‌های سیگنال (گیت‌شده و بی‌گیت) روی کلِ ۱۵.۶ سال
  · ATR89 (دلار) و SL/TP (دلار) روی هر کندلِ سیگنال
  · زمانِ ورودِ ۱۷۵ معامله (پس از allow_overlap=False) و توزیعِ bars_held
کنترلِ سلامت: ۱۷۵ معامله و WR=52.00 (سند §۳) باید بازتولید شود، وگرنه خروجی نمی‌دهد.

اجرا:  python3 tools/export_s759_parity.py
خروجی: results/_s759_parity/XAUUSD_H4.json
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import scalp_engine as se                       # noqa: E402
from strategies import s759_informed_structure as S9         # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s759_parity', 'XAUUSD_H4.json')
PIP = se.ASSETS['XAUUSD']['pip']


def main():
    df, src = S9.load_tf('H4')
    assert 'mt5_full' in src
    n = len(df)
    warm = max(S9.ATR_P * 4, 400)
    atr = S9.atr_pips(df)
    g, u = S9.informed_long(df, 5, atr)
    g[:warm] = False
    u = u.copy(); u[:warm] = False
    sl = S9.SL_K * atr
    tr = se.simulate_trades(df, g, np.zeros(n, bool), sl, S9.RR * sl, 'XAUUSD',
                            max_hold=S9.MAX_HOLD, allow_overlap=False)
    wr = round(float((tr['pnl_pip'] > 0).mean() * 100), 2)
    assert len(tr) == 175 and wr == 52.0, (len(tr), wr)
    t = df['time'].values.astype(np.int64)
    gi = np.where(g)[0]
    bh = tr['bars_held'].values
    out = dict(
        card='XAUUSD-H4', src=src, bars=n, warmup=warm,
        first_time=int(t[0]), last_time=int(t[-1]),
        pip=PIP, L=5, rho_min=S9.RHO_MIN, atr_p=S9.ATR_P, sl_k=S9.SL_K, rr=S9.RR,
        max_hold=S9.MAX_HOLD,
        n_sig_gated=int(g.sum()), n_sig_ungated=int(u.sum()),
        sig_times=[int(x) for x in t[gi]],
        sig_atr_usd=[round(float(atr[i] * PIP), 6) for i in gi],
        sig_sl_usd=[round(float(sl[i] * PIP), 6) for i in gi],
        ungated_times=[int(x) for x in t[np.where(u)[0]]],
        trade_signal_times=[int(t[i]) for i in tr['signal_bar'].values],
        trade_entry_times=[int(t[i]) for i in tr['entry_bar'].values],
        n_trades=len(tr), wr=wr,
        bars_held=dict(min=int(bh.min()), median=float(np.median(bh)),
                       p95=float(np.percentile(bh, 95)), max=int(bh.max()),
                       n_time_exit=int((tr['outcome'] == 'time').sum())
                       if 'outcome' in tr else None),
        outcome_counts={k: int(v) for k, v in tr['outcome'].value_counts().items()},
        last400=dict(
            times=[int(x) for x in t[-400:]],
            atr_usd=[round(float(x * PIP), 6) for x in atr[-400:]],
        ),
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(out, f)
    print(f'saved {OUT}: gated={out["n_sig_gated"]} ungated={out["n_sig_ungated"]} '
          f'trades={len(tr)} WR={wr} held={out["bars_held"]} outcomes={out["outcome_counts"]}')


if __name__ == '__main__':
    main()
