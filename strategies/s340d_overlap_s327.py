# -*- coding: utf-8 -*-
"""
S340d — ممیزیِ همپوشانیِ micro-channel (S340) با S327 (Sell-Climax Reversal LONG) روی XAU-H4.
"""
import numpy as np
from engine import scalp_engine as se
from strategies.s340_brooks_micro_channel import micro_channel_signals
from strategies import s327_sell_climax_reversal_rqs as s327
from strategies.s340c_overlap_audit import entry_bars_from_sig, overlap_pct, TOL


def main():
    df = se.load_data('data/XAUUSD_H4.csv')
    n = len(df)

    sig340 = micro_channel_signals(df, 'long', 3, 7, 8, 21, 0.40, 0.45, 0.70)
    a_bars, _ = entry_bars_from_sig(df, sig340, 520, 780, 20)
    print(f"S340 micro-channel: {len(a_bars)} entries")

    # S327 با config رجیستریِ XAUUSD-H4
    df327 = s327.load('XAUUSD', 'H4')
    feat = s327.build_features(df327, 'XAUUSD')
    sig327 = s327.make_signals(feat, k_body=2.5, br_min=0.6, streak_n=0,
                               rsi_lo=35, regime='trend', atr=feat['atr'], c=feat['c'])
    # طولِ df327 و df ممکن است اندکی فرق کند؛ هم‌تراز کنیم
    m = min(len(sig327), n)
    sig327b = np.zeros(n, bool); sig327b[:m] = sig327[:m]
    b327, _ = entry_bars_from_sig(df, sig327b, 520, 780, 20)
    print(f"S327 sell-climax:   {len(b327)} entries")

    p, hit = overlap_pct(a_bars, b327)
    print(f"\n>> همپوشانیِ S340 با S327: {p:.1f}%  ({hit}/{len(a_bars)} ورودی در ±{TOL} کندل)")
    pr, _ = overlap_pct(b327, a_bars)
    print(f"   (معکوس: {pr:.1f}% از S327 نزدیکِ S340)")


if __name__ == '__main__':
    main()
