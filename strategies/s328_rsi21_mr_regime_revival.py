# -*- coding: utf-8 -*-
"""
S328 — احیای S167 (RSI-21 Mean-Reversion) با فیلترِ رژیمِ رنج + قانونِ شناوری
================================================================================
منشأ: S167 (کتابِ Subarkah 2009) — RSI-21 cross-back mean-reversion.
      در S167 روی XAUUSD M15 با WR=53.1٪ لبه داشت اما به‌دلیلِ ناپایداریِ walk-forward
      (پنجرهٔ W3 منفی، PF=0.73) رد شد. هرگز مولتی‌تایم‌فریمِ کامل + فیلترِ رژیم آزموده نشد.

فرضیهٔ علمیِ نشست (تفکرِ غیرخطی):
  mean-reversion فقط در بازارِ RANGE کار می‌کند؛ در بازارِ TREND قوی، RSI در اشباع
  «می‌ماند» و ورودِ خلافِ‌روند ذبح می‌شود (این دقیقاً چیزی است که W3 را در S167 منفی کرد).
  ⇒ راهِ احیا = فیلترِ رژیمِ رنج (ADX پایین + Efficiency-Ratio پایین) که MR را فقط
  در محیطِ طبیعی‌اش (رنج) فعال کند، به‌علاوهٔ قانونِ شناوریِ TP/SL مخصوصِ هر TF.

معیار: RQS+ (۶ گیت، docs/RQS_ROBUST_QUALITY_SCORE.md). موتور: engine/scalp_engine + engine/rqs.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicators as ind


def efficiency_ratio(close, period):
    """Kaufman Efficiency Ratio: |net change| / sum(|bar change|). نزدیک ۰ = رنج، نزدیک ۱ = روند."""
    change = close.diff(period).abs()
    vol = close.diff().abs().rolling(period).sum()
    return (change / vol.replace(0, np.nan)).fillna(0.0)


def build_signals(df, rsi_period, lo, hi, adx_max=None, er_max=None, adx_period=14, er_period=10):
    """
    RSI-21 cross-back mean-reversion + فیلترِ رژیمِ رنج (همه causal / shift-safe).
      Long : RSI از زیرِ lo به بالا برگردد (rsi_prev<lo و rsi>=lo)
      Short: RSI از بالای hi به پایین برگردد (rsi_prev>hi و rsi<=hi)
      فیلترِ رنج: فقط اگر ADX<=adx_max و ER<=er_max (اگر داده شوند).
    خروجی: long_sig, short_sig (بولین، هم‌طولِ df).
    """
    close = df['close']
    r = ind.rsi(close, rsi_period)
    r_prev = r.shift(1)

    long_raw = (r_prev < lo) & (r >= lo)
    short_raw = (r_prev > hi) & (r <= hi)

    mask = pd.Series(True, index=df.index)
    if adx_max is not None:
        adx_v, _, _ = ind.adx(df, adx_period)
        mask &= (adx_v.shift(1) <= adx_max)   # shift ⇒ رژیمِ کندلِ قبل، بدونِ look-ahead
    if er_max is not None:
        er = efficiency_ratio(close, er_period)
        mask &= (er.shift(1) <= er_max)

    long_sig = (long_raw & mask).fillna(False).values
    short_sig = (short_raw & mask).fillna(False).values
    return long_sig, short_sig


def evaluate(asset, tf_file, rsi_period, lo, hi, sl_pip, tp_pip, max_hold,
             side='long', adx_max=None, er_max=None):
    df = se.load_data(tf_file)
    long_sig, short_sig = build_signals(df, rsi_period, lo, hi, adx_max, er_max)
    if side == 'long':
        short_sig = np.zeros(len(df), dtype=bool)
    elif side == 'short':
        long_sig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, asset,
                                max_hold=max_hold, allow_overlap=False)
    if trades is None or len(trades) == 0:
        return None, trades, df
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip, tp_pip=tp_pip)
    return r, trades, df


# پیکربندیِ TF ها (طلا و یورو)
TFS = {
    'XAUUSD': {
        'M5':  'data/XAUUSD_M5.csv',
        'M15': 'data/XAUUSD_M15.csv',
        'M30': 'data/XAUUSD_M30.csv',
        'H1':  'data/XAUUSD_H1.csv',
        'H4':  'data/XAUUSD_H4.csv',
    },
    'EURUSD': {
        'M5':  'data/EURUSD_M5.csv',
        'M15': 'data/EURUSD_M15.csv',
        'M30': 'data/EURUSD_M30.csv',
    },
}


def baseline_scan():
    """گامِ ۱: بازتولیدِ S167 خام (بدونِ فیلترِ رژیم) روی همهٔ TF — نقطهٔ شروع."""
    print("=" * 100)
    print("BASELINE — S167 RSI-21 MR خام (بدونِ فیلترِ رژیم) — cross-back، long فقط")
    print("=" * 100)
    # TP/SL نزدیکِ S167 (LO25/HI75, SL150/TP225 روی M15). برای TF های دیگر مقیاس ATR بعداً.
    for asset in ['XAUUSD', 'EURUSD']:
        for tf, f in TFS[asset].items():
            if not os.path.exists(f):
                continue
            r, tr, df = evaluate(asset, f, 21, 25, 75, 150, 225, 16, side='long')
            if r is None:
                print(f"{asset}-{tf:4s}: no trades")
                continue
            print(f"{asset}-{tf:4s} | " + rqs.format_report('RSI21-MR-raw', r))


def regime_sweep(asset, tf, f, sl_grid, tp_grid, side='long', max_holds=(12, 16, 24)):
    """
    گامِ ۲: جاروبِ فیلترِ رژیمِ رنج + آستانهٔ RSI + TP/SL مخصوصِ TF.
    قانونِ شناوری: چند متغیر هم‌زمان (adx_max, er_max, lo/hi, sl, tp, mh) برحسبِ هم.
    خروجی: فهرستِ کاندیدهای گیت-پاس (all 6) مرتب بر RQS.
    """
    ADX_MAXES = [None, 30, 25, 22, 18]
    ER_MAXES  = [None, 0.45, 0.35, 0.28, 0.22]
    THRESHES  = [(25, 75), (20, 80), (30, 70), (22, 78)]
    results = []
    df = se.load_data(f)
    for (lo, hi) in THRESHES:
        for adx_max in ADX_MAXES:
            for er_max in ER_MAXES:
                long_sig, short_sig = build_signals(df, 21, lo, hi, adx_max, er_max)
                if side == 'long':
                    short_sig = np.zeros(len(df), dtype=bool)
                else:
                    long_sig = np.zeros(len(df), dtype=bool)
                base_n = int(long_sig.sum() + short_sig.sum())
                if base_n < 30:
                    continue
                for sl in sl_grid:
                    for tp in tp_grid:
                        for mh in max_holds:
                            tr = se.simulate_trades(df, long_sig, short_sig, sl, tp,
                                                    asset, max_hold=mh, allow_overlap=False)
                            if tr is None or len(tr) < 30:
                                continue
                            r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
                            m = r['metrics']
                            row = dict(asset=asset, tf=tf, side=side, lo=lo, hi=hi,
                                       adx_max=adx_max, er_max=er_max, sl=sl, tp=tp, mh=mh,
                                       rqs=r['rqs_score'], passed=r['passed'],
                                       n=m['n_trades'], wr=m['win_rate'], pf=m['profit_factor'],
                                       dd=m['max_dd_pct'], mcl=m['max_consec_losses'],
                                       p=m['p_value'], net=m['net_profit'],
                                       gates=''.join('1' if v else '0' for v in r['gates'].values()))
                            results.append(row)
    results.sort(key=lambda x: (x['passed'], x['rqs']), reverse=True)
    return results


# TP/SL مخصوصِ هر TF بر مبنای ATRِ واقعی (اعدادِ غیررند — طبقِ اشتباهِ رایج #۷)
# MR: TP نزدیک‌تر از SL منطقی است (بردهای سریعِ کوچک ⇒ WR بالا).
TFSPEC = {
    ('XAUUSD', 'M5'):  dict(sl=[55, 70, 90, 110], tp=[35, 48, 65, 85]),
    ('XAUUSD', 'M15'): dict(sl=[70, 95, 120, 150], tp=[45, 65, 90, 120]),
    ('XAUUSD', 'M30'): dict(sl=[80, 110, 140, 175], tp=[55, 80, 110, 150]),
    ('XAUUSD', 'H1'):  dict(sl=[110, 150, 195, 245], tp=[75, 110, 155, 210]),
    ('XAUUSD', 'H4'):  dict(sl=[200, 280, 360], tp=[140, 220, 300]),
    ('EURUSD', 'M5'):  dict(sl=[18, 26, 34], tp=[12, 18, 26]),
    ('EURUSD', 'M15'): dict(sl=[24, 34, 46], tp=[16, 24, 34]),
    ('EURUSD', 'M30'): dict(sl=[30, 42, 56], tp=[20, 30, 42]),
}


def regime_sweep_deep(asset, tf, f, sl_grid, tp_grid, side='short', max_holds=(16, 24, 36)):
    """
    جاروبِ عمیقِ SHORT-fade با آستانه‌های ریزترِ RSI + ترکیبِ فیلترِ ADX×ER هم‌زمان
    (قانونِ شناوری: چند متغیر برحسبِ هم). هدف: احیای TF های بالاتر که در جاروبِ اولیه رد شدند.
    """
    ADX_MAXES = [None, 35, 28, 22]
    ER_MAXES  = [None, 0.40, 0.30, 0.22, 0.16]
    THRESHES  = [(25, 75), (20, 80), (22, 78), (18, 82), (25, 78)]
    results = []
    df = se.load_data(f)
    for (lo, hi) in THRESHES:
        for adx_max in ADX_MAXES:
            for er_max in ER_MAXES:
                long_sig, short_sig = build_signals(df, 21, lo, hi, adx_max, er_max)
                if side == 'long':
                    short_sig = np.zeros(len(df), dtype=bool)
                else:
                    long_sig = np.zeros(len(df), dtype=bool)
                if int(long_sig.sum() + short_sig.sum()) < 30:
                    continue
                for sl in sl_grid:
                    for tp in tp_grid:
                        for mh in max_holds:
                            tr = se.simulate_trades(df, long_sig, short_sig, sl, tp,
                                                    asset, max_hold=mh, allow_overlap=False)
                            if tr is None or len(tr) < 30:
                                continue
                            r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
                            m = r['metrics']
                            results.append(dict(asset=asset, tf=tf, side=side, lo=lo, hi=hi,
                                adx_max=adx_max, er_max=er_max, sl=sl, tp=tp, mh=mh,
                                rqs=r['rqs_score'], passed=r['passed'], n=m['n_trades'],
                                wr=m['win_rate'], pf=m['profit_factor'], dd=m['max_dd_pct'],
                                mcl=m['max_consec_losses'], p=m['p_value'], net=m['net_profit'],
                                gates=''.join('1' if v else '0' for v in r['gates'].values())))
    results.sort(key=lambda x: (x['passed'], x['rqs']), reverse=True)
    return results


def deep_revival(asset='XAUUSD', side='short'):
    """جاروبِ عمیقِ احیا (تمرکز بر SHORT-fade) روی همهٔ TF."""
    print("=" * 110)
    print(f"S328 DEEP REVIVAL — {asset} — side={side} — RSI21-MR-fade + رژیمِ رنجِ ADX×ER + شناوری")
    print("=" * 110)
    all_pass = {}
    for tf, f in TFS[asset].items():
        if not os.path.exists(f):
            continue
        spec = TFSPEC.get((asset, tf))
        if spec is None:
            continue
        res = regime_sweep_deep(asset, tf, f, spec['sl'], spec['tp'], side=side)
        passers = [r for r in res if r['passed'] and r['rqs'] >= 80]
        all_pass[tf] = passers
        top = res[:1]
        print(f"\n--- {asset}-{tf} : {len(res)} combos | gate-pass(RQS≥80)={len(passers)} ---")
        for r in (passers[:6] if passers else top):
            print(f"  RQS={r['rqs']:5.1f} {'PASS' if r['passed'] else 'rej '} | "
                  f"lo{r['lo']}/hi{r['hi']} adx≤{r['adx_max']} er≤{r['er_max']} "
                  f"SL{r['sl']}/TP{r['tp']} mh{r['mh']} | n={r['n']} WR={r['wr']:.1f}% "
                  f"PF={r['pf']:.2f} DD={r['dd']:.1f}% MCL={r['mcl']} p={r['p']:.3f} net={r['net']:+.0f}")
    return all_pass


def full_revival(asset='XAUUSD', side='long'):
    """جاروبِ کاملِ احیا روی همهٔ TF های یک دارایی."""
    print("=" * 110)
    print(f"S328 REVIVAL SWEEP — {asset} — side={side} — RSI21-MR + فیلترِ رژیمِ رنج + شناوریِ TP/SL")
    print("=" * 110)
    for tf, f in TFS[asset].items():
        if not os.path.exists(f):
            continue
        spec = TFSPEC.get((asset, tf))
        if spec is None:
            continue
        res = regime_sweep(asset, tf, f, spec['sl'], spec['tp'], side=side)
        passers = [r for r in res if r['passed'] and r['rqs'] >= 80]
        top = res[:1]
        print(f"\n--- {asset}-{tf} : {len(res)} combos | gate-pass(RQS≥80)={len(passers)} ---")
        for r in (passers[:5] if passers else top):
            print(f"  RQS={r['rqs']:5.1f} {'PASS' if r['passed'] else 'rej '} | "
                  f"lo{r['lo']}/hi{r['hi']} adx≤{r['adx_max']} er≤{r['er_max']} "
                  f"SL{r['sl']}/TP{r['tp']} mh{r['mh']} | n={r['n']} WR={r['wr']:.1f}% "
                  f"PF={r['pf']:.2f} DD={r['dd']:.1f}% MCL={r['mcl']} G={r['gates']} net={r['net']:+.0f}")


if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'baseline'
    if mode == 'baseline':
        baseline_scan()
    elif mode == 'revive':
        asset = sys.argv[2] if len(sys.argv) > 2 else 'XAUUSD'
        side = sys.argv[3] if len(sys.argv) > 3 else 'long'
        full_revival(asset, side)
    elif mode == 'deep':
        asset = sys.argv[2] if len(sys.argv) > 2 else 'XAUUSD'
        side = sys.argv[3] if len(sys.argv) > 3 else 'short'
        deep_revival(asset, side)
