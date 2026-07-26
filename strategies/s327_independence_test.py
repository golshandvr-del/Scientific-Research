# -*- coding: utf-8 -*-
"""
S327 — تستِ استقلالِ لبه روی نقاطِ منحصربه‌فرد (قانونِ همپوشانی، بندِ سوم)
================================================================================
مسئله: در EURUSD_M15 همپوشانیِ S327 با S326 = ۷۷.۸٪ (بالا). سؤالِ علمی:
  آیا S327 روی EUR M15 یک لبهٔ *مستقل* دارد یا صرفاً زیرمجموعهٔ S326 است؟

روش: سیگنال‌های S327 را به دو گروه می‌شکنیم:
  (الف) نقاطِ همپوشان با S326 (±۲ کندل)
  (ب) نقاطِ منحصربه‌فردِ S327 (هیچ سیگنالِ S326 در ±۲ کندل)
سپس RQS+ را روی هر دو زیرمجموعه جدا می‌سنجیم. اگر گروهِ (ب) هم مستقلاً باکیفیت
باشد ⇒ S327 ارزشِ افزودنِ مستقل دارد. اگر فقط (الف) خوب باشد ⇒ S327 عمدتاً
هم‌سیگنالِ S326 است و باید به‌عنوان *تأییدِ متعامد* دیده شود، نه لایهٔ مستقلِ نو.

این کار را برای هر TF ای که S326 در آن فعال است انجام می‌دهیم (XAU M5/M30، EUR M15).
"""
import sys, json
sys.path.insert(0, '.')
import numpy as np
from engine import scalp_engine as se
from engine import rqs
import strategies.s327_sell_climax_reversal_rqs as S327
from strategies.s326_streak_reversal_revival import (
    load as s326_load, build_features as s326_build, make_signals as s326_sig)
import warnings; warnings.filterwarnings('ignore')

TOL = 2

S327_WINNERS = {
    'XAUUSD_M5':  dict(k_body=1.6, br_min=0.6,  streak_n=2, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=24),
    'XAUUSD_M30': dict(k_body=1.6, br_min=0.6,  streak_n=2, rsi_lo=30, regime='trend', sl_m=2.4, tp_m=1.0,  hold=16),
    'EURUSD_M15': dict(k_body=2.0, br_min=0.6,  streak_n=3, rsi_lo=30, regime='trend', sl_m=3.1, tp_m=1.15, hold=16),
}
S326_WINNERS = {
    'XAUUSD_M5':  dict(streak_n=5, run_min=0.0, rsi_lo=30, regime='trend', sl_m=3.1, tp_m=1.15, hold=24),
    'XAUUSD_M30': dict(streak_n=5, run_min=2.5, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=48),
    'EURUSD_M15': dict(streak_n=4, run_min=0.0, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=48),
}


def near_any(i, idx_b, tol=TOL):
    return len(idx_b) > 0 and np.any(np.abs(idx_b - i) <= tol)


def rqs_on_subset(df, sig_bool, asset, cfg):
    """RQS+ روی زیرمجموعه‌ای از سیگنال‌ها (همان TP/SL/hold لایهٔ S327)."""
    feat = S327.build_features(df, asset)
    atr = feat['atr']
    pip = se.ASSETS[asset]['pip']
    atr_pip = np.where(atr > 0, atr / pip, np.nan)
    valid = sig_bool & np.isfinite(atr_pip) & (atr_pip > 0)
    sl = np.where(np.isfinite(atr_pip), cfg['sl_m'] * atr_pip, 1.0)
    tp = np.where(np.isfinite(atr_pip), cfg['tp_m'] * atr_pip, 1.0)
    short = np.zeros(feat['n'], dtype=bool)
    tr = se.simulate_trades(df, valid, short, sl, tp, asset,
                            max_hold=cfg['hold'], allow_overlap=False)
    return rqs.compute_rqs(tr, asset)


def main():
    print("=" * 96)
    print("S327 — تستِ استقلالِ لبه روی نقاطِ منحصربه‌فرد (غیرهمپوشان با S326)")
    print("=" * 96)
    report = {}
    for key, cfg in S327_WINNERS.items():
        asset, tf = key.split('_')
        df = S327.load(asset, tf)
        feat = S327.build_features(df, asset)
        s327 = S327.make_signals(feat, cfg['k_body'], cfg['br_min'], cfg['streak_n'],
                                 cfg['rsi_lo'], cfg['regime'], feat['atr'], feat['c'])
        s327 = np.nan_to_num(s327, nan=False).astype(bool)

        c326 = S326_WINNERS[key]
        df2 = s326_load(asset, tf); f2 = s326_build(df2, asset)
        s326 = s326_sig(f2, c326['streak_n'], c326['run_min'], c326['rsi_lo'],
                        c326['regime'], f2['atr'], f2['c'])
        s326 = np.nan_to_num(s326, nan=False).astype(bool)
        idx326 = np.where(s326)[0]

        idx327 = np.where(s327)[0]
        overlap_mask = np.zeros(len(df), dtype=bool)
        unique_mask = np.zeros(len(df), dtype=bool)
        for i in idx327:
            if near_any(i, idx326):
                overlap_mask[i] = True
            else:
                unique_mask[i] = True

        r_all = rqs_on_subset(df, s327, asset, cfg)
        r_ovl = rqs_on_subset(df, overlap_mask, asset, cfg)
        r_uni = rqs_on_subset(df, unique_mask, asset, cfg)

        print(f"\n[{key}]  total S327={int(s327.sum())}  "
              f"همپوشان={int(overlap_mask.sum())}  منحصربه‌فرد={int(unique_mask.sum())}")
        print("  " + rqs.format_report('  ALL     ', r_all))
        print("  " + rqs.format_report('  OVERLAP ', r_ovl))
        print("  " + rqs.format_report('  UNIQUE  ', r_uni))
        report[key] = dict(
            n_total=int(s327.sum()), n_overlap=int(overlap_mask.sum()),
            n_unique=int(unique_mask.sum()),
            rqs_all=r_all['rqs_score'], rqs_overlap=r_ovl['rqs_score'],
            rqs_unique=r_uni['rqs_score'],
            unique_passed=bool(r_uni['passed']),
            unique_metrics=r_uni['metrics'])
    def clean(x):
        if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [clean(v) for v in x]
        if isinstance(x, np.bool_): return bool(x)
        if isinstance(x, np.integer): return int(x)
        if isinstance(x, np.floating): return float(x)
        return x
    json.dump(clean(report), open('results/_s327_independence_test.json', 'w'),
              ensure_ascii=False, indent=1)
    print("\nsaved results/_s327_independence_test.json")


if __name__ == '__main__':
    main()
