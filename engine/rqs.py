# -*- coding: utf-8 -*-
"""
RQS+ — Robust Quality Score (Extended) — موتورِ ارزیابیِ کیفیتِ مقاوم
================================================================================
سندِ مرجع: docs/RQS_ROBUST_QUALITY_SCORE.md

این ماژول ۶ دروازهٔ RQS+ را روی یک DataFrameِ معاملات (خروجیِ scalp_engine.simulate_trades)
محاسبه می‌کند و حکمِ پذیرش/رد + نمرهٔ پیوسته (۰..۱۰۰) را برمی‌گرداند.

منطقِ veto: ردِ حتی یک گیت ⇒ مردود (سقفِ نمره ۴۰).

گیت‌ها:
  G0  WR Floor        : WR ≥ 60٪  و  n ≥ 30
  G1  Edge over Random: net_edge>0  و  WR_excess ≥ 3٪  و  p_value < 0.05 (binomial)
  G2  Profit Factor   : PF ≥ 1.3
  G3  Tail Risk       : maxDD ≤ 8٪  و  MaxConsecLoss ≤ 8
  G4  Stability (WF)  : هر ۴ پنجرهٔ walk-forward مثبت + هر دو نیمه مثبت
  G5  Expectancy      : expectancy_pip > 0.5 × spread_cost
"""
import numpy as np
import pandas as pd
from math import comb

from engine import scalp_engine as se

# ---------- آستانه‌های رسمیِ RQS+ ----------
WR_FLOOR       = 60.0     # G0
N_FLOOR        = 30       # G0
WR_EXCESS_MIN  = 3.0      # G1 (درصد)
P_VALUE_MAX    = 0.05     # G1
PF_MIN         = 1.3      # G2
MAXDD_MAX_PCT  = 8.0      # G3
MCL_MAX        = 8        # G3 (max consecutive losses)
EXP_COST_MULT  = 0.5      # G5 (expectancy > 0.5 × spread_cost)


def _binom_pvalue_one_sided(wins, n, p0):
    """P(X >= wins) under Binomial(n, p0) — آزمونِ یک‌دامنه که لبه از رندوم بهتر است."""
    if n <= 0:
        return 1.0
    wins = int(round(wins))
    p0 = min(max(p0, 1e-9), 1 - 1e-9)
    # جمعِ دم بالا
    tail = 0.0
    for k in range(wins, n + 1):
        tail += comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
    return float(min(1.0, tail))


def _max_consec_losses(outcomes):
    """بیشترین رشتهٔ باختِ متوالی."""
    mcl = cur = 0
    for o in outcomes:
        if o == 'win':
            cur = 0
        else:
            cur += 1
            mcl = max(mcl, cur)
    return mcl


def _split_positive(trades, asset, k):
    """آیا هر یک از k پنجرهٔ زمانی (به ترتیبِ exit_bar) net مثبت دارد؟ فهرستِ netها."""
    if trades is None or len(trades) == 0:
        return [0.0] * k, False
    tr = trades.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    bounds = np.linspace(0, n, k + 1).astype(int)
    nets = []
    for i in range(k):
        a, b = bounds[i], bounds[i + 1]
        sub = tr.iloc[a:b]
        if len(sub) == 0:
            nets.append(0.0)
            continue
        s, _ = se.run_capital(sub, asset)
        nets.append(float(s['net_profit']))
    all_pos = all(x > 0 for x in nets)
    return nets, all_pos


def compute_rqs(trades, asset, sl_pip=None, tp_pip=None,
                initial_capital=10000.0):
    """
    ورودی:
      trades : DataFrameِ خروجیِ simulate_trades (ستون‌های pnl_pip, sl_pip, tp_pip, outcome, exit_bar)
      asset  : 'XAUUSD' یا 'EURUSD' …
      sl_pip, tp_pip : اگر داده نشوند از میانهٔ ستون‌های trades گرفته می‌شوند.

    خروجی: dict شاملِ gates (پاس/رد هرکدام)، متریک‌ها، verdict، rqs_score.
    """
    res = {'asset': asset, 'gates': {}, 'metrics': {}, 'passed': False, 'rqs_score': 0.0}

    if trades is None or len(trades) == 0:
        res['metrics']['n_trades'] = 0
        res['verdict'] = 'REJECT (no trades)'
        for g in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5']:
            res['gates'][g] = False
        return res

    tr = trades.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    outcomes = tr['outcome'].tolist()
    wins = sum(1 for o in outcomes if o == 'win')
    wr = wins / n * 100.0

    # SL/TP مؤثر
    if sl_pip is None:
        sl_pip = float(np.median(tr['sl_pip'].values))
    if tp_pip is None and 'tp_pip' in tr.columns:
        tp_pip = float(np.median(tr['tp_pip'].values))
    if not tp_pip or tp_pip <= 0:
        tp_pip = sl_pip  # پیش‌فرضِ محافظه‌کارانه ⇒ breakeven=50٪

    # سرمایه‌محور
    cap, _ = se.run_capital(tr, asset, initial_capital=initial_capital)
    net_profit = cap['net_profit']
    pf = cap['profit_factor']
    maxdd_pct = abs(cap['max_dd_pct'])

    # expectancy بر حسبِ pip (پس از هزینه — pnl_pip از پیش هزینه‌دار است)
    exp_pip = float(np.mean(tr['pnl_pip'].values))
    spread_cost = se.ASSETS[asset]['spread_pip']

    # G0 — WR Floor
    g0 = (wr >= WR_FLOOR) and (n >= N_FLOOR)

    # G1 — Edge over Random
    wr_breakeven = sl_pip / (sl_pip + tp_pip) * 100.0 if (sl_pip + tp_pip) > 0 else 50.0
    wr_excess = wr - wr_breakeven
    net_edge = exp_pip  # لبهٔ خالصِ pip
    p_value = _binom_pvalue_one_sided(wins, n, wr_breakeven / 100.0)
    g1 = (net_edge > 0) and (wr_excess >= WR_EXCESS_MIN) and (p_value < P_VALUE_MAX)

    # G2 — Profit Factor
    g2 = (pf >= PF_MIN)

    # G3 — Tail Risk
    mcl = _max_consec_losses(outcomes)
    g3 = (maxdd_pct <= MAXDD_MAX_PCT) and (mcl <= MCL_MAX)

    # G4 — Stability (walk-forward 4 + two halves)
    wf_nets, wf_ok = _split_positive(tr, asset, 4)
    half_nets, half_ok = _split_positive(tr, asset, 2)
    g4 = wf_ok and half_ok

    # G5 — Expectancy vs cost
    g5 = (exp_pip > EXP_COST_MULT * spread_cost)

    gates = {'G0': g0, 'G1': g1, 'G2': g2, 'G3': g3, 'G4': g4, 'G5': g5}
    all_pass = all(gates.values())

    # نمرهٔ پیوسته
    def clip01(x):
        return float(min(1.0, max(0.0, x)))

    comp_pf   = clip01((pf - 1.0) / (2.0 - 1.0)) if np.isfinite(pf) else 1.0
    comp_exp  = clip01(exp_pip / (2.0 * spread_cost)) if spread_cost > 0 else 1.0
    comp_stab = (sum(1 for x in wf_nets if x > 0) / 4.0) * (1.0 if half_ok else 0.5)
    comp_edge = clip01((P_VALUE_MAX - p_value) / P_VALUE_MAX)
    comp_tail = clip01(1 - maxdd_pct / MAXDD_MAX_PCT) * clip01(1 - mcl / MCL_MAX)
    comp_wr   = clip01((wr - 60.0) / 20.0)

    weighted = (0.25 * comp_pf + 0.20 * comp_exp + 0.20 * comp_stab +
                0.15 * comp_edge + 0.15 * comp_tail + 0.05 * comp_wr)

    if all_pass:
        rqs_score = 40.0 + 60.0 * weighted
    else:
        rqs_score = min(40.0, 40.0 * weighted)

    res['metrics'] = {
        'n_trades': n, 'win_rate': round(wr, 2), 'net_profit': round(net_profit, 1),
        'profit_factor': round(pf, 3) if np.isfinite(pf) else 999.0,
        'max_dd_pct': round(maxdd_pct, 2), 'max_consec_losses': mcl,
        'expectancy_pip': round(exp_pip, 4), 'spread_cost_pip': spread_cost,
        'wr_breakeven': round(wr_breakeven, 2), 'wr_excess': round(wr_excess, 2),
        'p_value': round(p_value, 5), 'sl_pip': sl_pip, 'tp_pip': tp_pip,
        'wf_nets': [round(x, 1) for x in wf_nets],
        'half_nets': [round(x, 1) for x in half_nets],
    }
    res['gates'] = gates
    res['passed'] = all_pass
    res['rqs_score'] = round(rqs_score, 1)
    res['verdict'] = 'ACCEPT' if all_pass else 'REJECT'
    return res


def format_report(name, r):
    """گزارشِ تک‌خطیِ خوانا."""
    m = r['metrics']
    g = r['gates']
    gline = ' '.join(f"{k}:{'✓' if v else '✗'}" for k, v in g.items())
    return (f"{name:28s} | {r['verdict']:6s} RQS={r['rqs_score']:5.1f} | "
            f"n={m.get('n_trades',0):4d} WR={m.get('win_rate',0):4.1f}% "
            f"PF={m.get('profit_factor',0):.2f} DD={m.get('max_dd_pct',0):.1f}% "
            f"MCL={m.get('max_consec_losses',0)} p={m.get('p_value',1):.3f} | {gline}")
