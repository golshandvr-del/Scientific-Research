# -*- coding: utf-8 -*-
"""
sim_calibrate.py — کالیبراسیونِ شبیه‌سازِ رویداد-محور روی دو برندهٔ تأییدشده
================================================================================
هدف: اثباتِ درستیِ شبیه‌ساز. اگر S164 و S73 که در ممیزیِ برداری RQS+ را پاس کردند
(RQS=85 و 81)، از مسیرِ شبیه‌سازِ *رویداد-محور* هم عبورِ قابل‌قبولی داشته باشند،
به موتور اعتماد می‌کنیم. هر تفاوتِ معنادار خودش یک کشفِ علمی است (یعنی بک‌تستِ
برداری خوش‌بین/بدبین بوده).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_strategies import STRATEGY_REGISTRY


def run_one(code, warmup=2000):
    reg = STRATEGY_REGISTRY[code]
    df = TS.load_data(reg['tf'])
    strat = reg['cls']()
    trades, eq = TS.simulate(df, strat, reg['asset'], tf=reg['tf'],
                             warmup=warmup, risk_per_trade=1.0)
    print(f"\n{'='*100}")
    print(f"{code} — {reg['label']}  ({reg['tf']}, {len(df)} bars)")
    print(f"{'='*100}")
    if trades is None or len(trades) == 0:
        print("  هیچ معامله‌ای تولید نشد.")
        return None
    n = len(trades)
    wins = (trades['outcome'] == 'win').sum()
    wr = wins / n * 100
    net_per_lot = trades['pnl_usd'].sum()
    net_sized = trades['pnl_usd_sized'].sum()
    print(f"  معاملات: n={n}  WR={wr:.1f}%  netP(1lot)={net_per_lot:+.0f}$  "
          f"netP(sized)={net_sized:+.0f}$")
    print(f"  موجودیِ نهایی: {eq[-1]:,.0f}$  (شروع 10,000$)")
    # توزیعِ دلیلِ خروج
    print(f"  دلایلِ خروج: {dict(trades['exit_reason'].value_counts())}")
    # RQS+
    r = RQS.compute_rqs(trades, reg['asset'])
    print("  " + RQS.format_report(code, r))
    gates = r['gates']
    gl = "  ".join(f"{g}:{'✓' if gates[g] else '✗'}" for g in ['G0','G1','G2','G3','G4','G5'])
    print(f"  دروازه‌ها: {gl}")
    return r


def main():
    print("#"*100)
    print("# کالیبراسیونِ شبیه‌سازِ رویداد-محور — دو برندهٔ تأییدشده (S164, S73)")
    print("#"*100)
    for code in ['S164', 'S73']:
        run_one(code)


if __name__ == '__main__':
    main()
