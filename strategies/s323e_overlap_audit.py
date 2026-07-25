# -*- coding: utf-8 -*-
"""
S323e — قانونِ همپوشانیِ اجباری (الزامی): همپوشانیِ سیگنالیِ لایهٔ احیاشدهٔ S11
(S/R Pullback + Golden Window) با لایه‌های فعالِ طلای موجود روی TFهای مشترک.
================================================================================
قانونِ همپوشانیِ پروژه: پیش از افزودنِ هر لایه باید دقیقاً سنجید (۱) با کدام
لایه/لایه‌ها و چند درصد همپوشانیِ سیگنال دارد؛ (۲) آیا بخشِ همپوشان به‌عنوان
فیلتر می‌ارزد؛ (۳) حتی ۱٪ ناهمپوشانی ارزشِ افزودن دارد؛ (۴) از شبیه‌سازِ رویداد-محور.

TFهای احیاشدهٔ S323 و لایه‌های فعالِ طلای هم‌TF:
  • M15 → S322 (Ichimoku Kumo Trend-Pullback, RQS=86.2)  [تنها لایهٔ فعالِ طلای M15]
  • M30 → S321 (MA-Ribbon, RQS=88), S313 (Squeeze→Breakout, RQS=92.5)
  • H1  → S313 (Squeeze→Breakout روی H1)

معیارِ همپوشانی: نسبتِ کندل‌های ورودِ هم‌جهتِ S323 که یک لایهٔ فعال هم در پنجرهٔ
±۲ کندل سیگنالِ ورودِ هم‌جهت می‌دهد، به کلِّ سیگنال‌های S323.
اجرا: python3 strategies/s323e_overlap_audit.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from engine import scalp_engine as se
from engine import indicators as ind
import strategies.s323_s11_sr_pullback_revival as S323
import strategies.s322_ichimoku_kumo as S322
import warnings; warnings.filterwarnings('ignore')

# کانفیگ‌های نهاییِ احیاشدهٔ S323 (از results/_s323_sr_pullback_revival.json)
S323_CFG = json.load(open(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'results', '_s323_sr_pullback_revival.json')))


def dilate(mask, W=2):
    d = mask.copy()
    for k in range(1, W + 1):
        d[k:] |= mask[:-k]
        d[:-k] |= mask[k:]
    return d


def s313_signals(df):
    """بازتولیدِ منطقِ S313: BB-squeeze سپس شکست + ADX≥30 (فقط جهتِ سیگنال)."""
    c = df['close']
    _, up, lo = ind.bollinger(c, 20, 2.0)
    up = up.values; lo = lo.values
    adx14 = ind.adx(df, 14)
    adx14 = (adx14[0] if isinstance(adx14, tuple) else adx14)
    adx14 = adx14.values if hasattr(adx14, 'values') else np.asarray(adx14)
    bb_width = up - lo
    n = len(c); price = c.values
    sqz = np.zeros(n, bool)
    for i in range(100, n):
        thr = np.nanpercentile(bb_width[i - 100:i], 25)
        sqz[i] = bb_width[i] <= thr
    long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)
    for i in range(1, n):
        if sqz[i - 1] and adx14[i] >= 30:
            if price[i] > up[i]:
                long_sig[i] = True
            elif price[i] < lo[i]:
                short_sig[i] = True
    return long_sig, short_sig


def s322_signals(df, cfg):
    """سیگنالِ ورودِ S322 (Ichimoku Kumo) با کانفیگِ live M15."""
    f = S322.build_features(df)
    ls, ss, _, _ = S322.make_signals(f, cfg, cfg.get('side', 'long'))
    return ls, ss


def s323_signals(asset, tf):
    """سیگنالِ ورودِ لایهٔ احیاشدهٔ S323 با کانفیگِ نهاییِ همان TF."""
    df = se.load_data(f'data/{asset}_{tf}.csv')
    cfg = S323_CFG[f'{asset}_{tf}']['cfg']
    f = S323.build_features(df, asset)
    ls, ss, _, _ = S323.make_signals(f, cfg)
    return df, ls, ss


def audit_tf(tf, others):
    """others: list of (name, long_mask, short_mask)."""
    asset = 'XAUUSD'
    df, ls, ss = s323_signals(asset, tf)
    n = len(df)
    s323_any = ls | ss
    n323 = int(s323_any.sum())
    print(f"\n{'='*72}\n### XAUUSD {tf} — S323 total entry bars: {n323}")
    if n323 == 0:
        print("  (no signals)"); return
    union_overlap = np.zeros(n, bool)
    for name, o_ls, o_ss in others:
        o_ls = o_ls[:n] if len(o_ls) >= n else np.pad(o_ls, (0, n - len(o_ls)))
        o_ss = o_ss[:n] if len(o_ss) >= n else np.pad(o_ss, (0, n - len(o_ss)))
        ov_long = ls & dilate(o_ls)
        ov_short = ss & dilate(o_ss)
        ov = ov_long | ov_short
        n_ov = int(ov.sum())
        n_other = int((o_ls | o_ss).sum())
        pct = 100.0 * n_ov / max(1, n323)
        print(f"  vs {name:24s} entries={n_other:4d} | overlap(±2,same-dir)="
              f"{n_ov:4d} = {pct:5.1f}% of S323")
        union_overlap |= ov
    n_u = int(union_overlap.sum())
    pct_u = 100.0 * n_u / max(1, n323)
    print(f"  {'-'*66}")
    print(f"  اتحادِ همپوشانی با همهٔ لایه‌ها : {n_u} bar = {pct_u:.1f}% از S323")
    print(f"  ⇒ سهمِ مستقلِ (ناهمپوشانِ) S323 : {100 - pct_u:.1f}%")
    return pct_u


def main():
    print("S323e — Overlap Audit (mandatory) | S11-revived vs active gold layers")
    results = {}

    # M15: تنها لایهٔ فعالِ طلای M15 = S322 (Ichimoku)
    df15 = se.load_data('data/XAUUSD_M15.csv')
    ls322, ss322 = s322_signals(df15, S322.BEST['XAUUSD']['M15'])
    results['M15'] = audit_tf('M15', [('S322_Ichimoku', ls322, ss322)])

    # M30: S321 (Ribbon) + S313 (Squeeze)
    df30 = se.load_data('data/XAUUSD_M30.csv')
    import strategies.s321f_ribbon_m30_slopefilter as S321F
    from strategies.s321k_overlap_check import FINAL as RIB_FINAL
    pip = se.ASSETS['XAUUSD']['pip']
    feats30 = S321F.build_features(df30, pip)
    ls321, ss321, _, _ = S321F.make_signals(feats30, RIB_FINAL, 'both')
    ls313_30, ss313_30 = s313_signals(df30)
    results['M30'] = audit_tf('M30', [('S321_Ribbon', ls321, ss321),
                                      ('S313_Squeeze', ls313_30, ss313_30)])

    # H1: S313 (Squeeze روی H1)
    df1h = se.load_data('data/XAUUSD_H1.csv')
    ls313_1h, ss313_1h = s313_signals(df1h)
    results['H1'] = audit_tf('H1', [('S313_Squeeze', ls313_1h, ss313_1h)])

    print(f"\n{'='*72}\nخلاصهٔ همپوشانی (٪ همپوشان با اتحادِ لایه‌های فعال):")
    for tf, pct in results.items():
        verdict = ("مستقل — ارزشِ افزودن دارد" if (pct or 0) < 40
                   else "همپوشانِ بالا — بررسیِ نقشِ فیلتر")
        print(f"  {tf}: {pct:.1f}%  → {verdict}")


if __name__ == '__main__':
    main()
