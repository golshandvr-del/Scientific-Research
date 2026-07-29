# -*- coding: utf-8 -*-
"""
S340c — ممیزیِ همپوشانیِ micro-channel (S340, XAUUSD-H4-LONG) با لایه‌های فعالِ H4:
        S327 (Sell-Climax Reversal LONG) و S332 (Squeeze breakout LONG).
================================================================================
قانونِ همپوشانی: قبل از ثبت باید بدانیم لبهٔ نو مستقل است یا فیلترِ لایه‌های موجود.
معیار: نسبتِ entry_barهای S340 که با entry_barِ لایهٔ دیگر در پنجرهٔ ±tol کندل منطبق‌اند.
"""
import numpy as np
from engine import scalp_engine as se
from strategies.s340_brooks_micro_channel import micro_channel_signals
from strategies.s332_squeeze_rqs_revival import build_squeeze_signal

TOL = 3  # پنجرهٔ کندلِ هم‌پوشانی (H4: ±3 کندل = ±12h)


def entry_bars_from_sig(df, sig, sl, tp, mh, asset='XAUUSD'):
    n = len(df)
    tr = se.simulate_trades(df, sig, np.zeros(n, bool), sl_pip=sl, tp_pip=tp,
                            asset=asset, max_hold=mh, allow_overlap=False)
    return set(tr['entry_bar'].tolist()), tr


def overlap_pct(a_bars, b_bars, tol=TOL):
    """نسبتِ عناصرِ a که یک عضوِ b در فاصلهٔ ≤tol دارند."""
    if not a_bars:
        return 0.0, 0
    b = np.array(sorted(b_bars))
    hit = 0
    for x in a_bars:
        if len(b) and np.min(np.abs(b - x)) <= tol:
            hit += 1
    return 100.0 * hit / len(a_bars), hit


def main():
    df = se.load_data('data/XAUUSD_H4.csv')
    n = len(df)

    # --- S340 micro-channel (لایهٔ نو) ---
    sig340 = micro_channel_signals(df, 'long', 3, 7, 8, 21, 0.40, 0.45, 0.70)
    a_bars, tr340 = entry_bars_from_sig(df, sig340, 520, 780, 20)
    print(f"S340 micro-channel: {len(a_bars)} entries")

    # --- S332 squeeze (config رجیستری XAUUSD-H4) ---
    sig332 = build_squeeze_signal(df, bb_period=20, bb_k=2.0, sqz_lookback=100,
                                  sqz_pct=0.25, breakout_lookback=6,
                                  trend_gate=True, ema_fast=50, ema_slow=200)
    b332, _ = entry_bars_from_sig(df, sig332, 520, 780, 20)
    print(f"S332 squeeze:       {len(b332)} entries")

    p332, h332 = overlap_pct(a_bars, b332)
    print(f"\n>> همپوشانیِ S340 با S332: {p332:.1f}%  ({h332}/{len(a_bars)} ورودی در ±{TOL} کندل)")

    # اشتراکِ زمانی معکوس (چند درصد از S332 هم در S340 هست)
    p332r, _ = overlap_pct(b332, a_bars)
    print(f"   (معکوس: {p332r:.1f}% از S332 نزدیکِ S340)")


if __name__ == '__main__':
    main()
