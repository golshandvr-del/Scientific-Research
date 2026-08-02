# -*- coding: utf-8 -*-
"""
S363 · پروتکل **P3-A — اندازه‌گیریِ چندگانگیِ واقعیِ بُعدِ براکت**

پیاده‌سازیِ `results/S363_ADDENDUM_P3_BRACKET_MULTIPLICITY_PREREG.md`
(کامیت‌شده **پیش از** نوشتنِ این فایل).

پرسشِ واحد: ضریبِ `× 15` که بدونِ اندازه‌گیری به صورت‌حسابِ چندگانگی اعمال
می‌شود، در واقعیت چند است؟

روش: **دقیقاً همان** `_m_eff_from_bool_matrix` که روی ۴۳۲ ستونِ سیگنال اجرا
می‌شود، این بار روی ماتریسِ `(سیگنال × ۱۵ براکت)` از برچسبِ برد/باخت.
هیچ روشِ جدیدی اختراع نمی‌شود ⇒ صفر درجهٔ آزادی.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R2                                            # noqa: E402
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s363_s327_v24_rejudge import (                           # noqa: E402
    ARCHIVE_CFG, G_SLTP, G_HOLD, N_SIGNAL_COLUMNS, SITE_CARDS, ARCHIVE_ONLY_CARDS,
    build_features, geometry, signal_of, outcome_table,
    _m_eff_from_bool_matrix, _neff_selfcheck)

OUT = "results/_scan_S363"
ALL_CARDS = SITE_CARDS + ARCHIVE_ONLY_CARDS


def bracket_win_matrix(df, asset, feat, sig, verbose=True):
    """`X[i, b]` = آیا سیگنالِ i در براکتِ b برنده شد؟  (b = ۱۵ براکتِ آرشیو)

    سطرها = **فقط سیگنال‌های پیکربندیِ منجمدِ آرشیو**، نه کلِ کندل‌ها.
    (§۲-۱ پیش‌ثبت: کندل‌های بی‌سیگنال در همهٔ براکت‌ها یکسان‌اند و همبستگی را
    مصنوعاً بالا می‌برند ⇒ صورت‌حساب را غیرمنصفانه *کم* می‌کنند.)

    برچسبِ برد = `pnl_pip > 0`، همان تعریفِ موتور — نه «کدام سد لمس شد».
    """
    idx = np.flatnonzero(sig)
    cols, labels = [], []
    for (sl_m, tp_m) in G_SLTP:
        sl_arr, tp_arr, _ = geometry(feat, asset, sl_m, tp_m)
        for hold in G_HOLD:
            res, _ = outcome_table(df, asset, sl_arr, tp_arr, hold)
            cols.append((res[idx] > 0).astype(np.uint8))
            labels.append(f"sl{sl_m}_tp{tp_m}_h{hold}")
    X = np.column_stack(cols)
    if verbose:
        wr = 100.0 * X.mean(axis=0)
        print(f"    brackets: n_signals={X.shape[0]} n_brackets={X.shape[1]}  "
              f"WR range {wr.min():.1f}%..{wr.max():.1f}%")
    return X, labels


def measure(card, verbose=True):
    asset, tf = card.split('-')
    df = se.load_data(os.path.join('data', f'{asset}_{tf}.csv'))
    feat = build_features(df, asset)
    cfg = ARCHIVE_CFG[card]
    sig = signal_of(feat, cfg, asset)

    if verbose:
        print(f"\n=== {card} :: P3-A  n_signals={int(sig.sum())}", flush=True)

    X, labels = bracket_win_matrix(df, asset, feat, sig, verbose)

    # خودآزمونِ اجباری — اگر مسیرِ شمارشی با موتور نخواند، هیچ صورت‌حسابی صادر نکن
    mine, ref, delta = _neff_selfcheck(X, n_rows=X.shape[0], n_cols=X.shape[1])
    if delta > 1e-6:
        raise AssertionError(
            f"{card}: count-based M_eff ({mine:.9f}) != R2.effective_trials "
            f"({ref:.9f}); delta={delta:.3e}. Refusing to issue a bill.")

    m_eff, m_used = _m_eff_from_bool_matrix(X)

    # تفکیکِ بُعدها (پیش‌بینیِ P3A-2): sl/tp با hold ثابت، و hold با sl/tp ثابت
    nh = len(G_HOLD)
    sltp_only = X[:, ::nh]                       # ۵ ستون، hold = G_HOLD[0]
    hold_only = X[:, :nh]                        # ۳ ستون، sltp = G_SLTP[0]
    m_sltp, _ = _m_eff_from_bool_matrix(sltp_only)
    m_hold, _ = _m_eff_from_bool_matrix(hold_only)

    # همبستگیِ میانگینِ زوجی — عددِ شهودیِ پشتِ M_eff
    Xf = X.astype(np.float64)
    sd = Xf.std(axis=0)
    keep = sd > 1e-12
    corr = np.corrcoef(Xf[:, keep], rowvar=False) if keep.sum() > 1 else np.eye(1)
    iu = np.triu_indices(corr.shape[0], 1)
    mean_r = float(corr[iu].mean()) if iu[0].size else float('nan')

    rec = dict(
        card=card, n_signals=int(sig.sum()),
        n_brackets=int(X.shape[1]), n_brackets_with_variance=m_used,
        m_eff_bracket=round(float(m_eff), 4),
        m_eff_sltp_dim=round(float(m_sltp), 4),
        m_eff_hold_dim=round(float(m_hold), 4),
        mean_pairwise_corr=round(mean_r, 4),
        selfcheck_delta=float(delta),
        assumed_multiplier=15,
        reduction_factor=round(15.0 / float(m_eff), 3),
        bracket_labels=labels)

    if verbose:
        print(f"    mean pairwise corr between brackets = {mean_r:+.4f}")
        print(f"    M_eff(bracket)   = {m_eff:.3f}  of 15   "
              f"(selfcheck delta={delta:.2e})")
        print(f"    M_eff(sl/tp dim) = {m_sltp:.3f}  of 5")
        print(f"    M_eff(hold dim)  = {m_hold:.3f}  of 3")
        print(f"    → bill reduction factor = {15.0/m_eff:.2f}×")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default=','.join(ALL_CARDS))
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print("=" * 92)
    print("S363 · P3-A — اندازه‌گیریِ چندگانگیِ واقعیِ بُعدِ براکت")
    print("  پیش‌ثبت: results/S363_ADDENDUM_P3_BRACKET_MULTIPLICITY_PREREG.md")
    print("  روش: همان Nyholt–Cheverud که روی ۴۳۲ ستونِ سیگنال اجرا می‌شود")
    print("=" * 92)

    recs = []
    for card in args.cards.split(','):
        rec = measure(card)
        recs.append(rec)
        # چک‌پوینتِ مرحله‌به‌مرحله (قانونِ سوم)
        with open(os.path.join(OUT, f'P3A_{card}.json'), 'w') as f:
            json.dump(rec, f, indent=1, ensure_ascii=False)
        print(f"  → saved {OUT}/P3A_{card}.json", flush=True)

    ms = np.array([r['m_eff_bracket'] for r in recs])
    print(f"\n{'='*92}")
    print("خلاصه — M_eff(bracket) روی همهٔ کارت‌ها")
    print(f"{'='*92}")
    print(f"  {'card':13s}{'n_sig':>7}{'meanCorr':>10}{'M_eff':>9}"
          f"{'M_sltp':>9}{'M_hold':>9}{'reduction':>11}")
    for r in recs:
        print(f"  {r['card']:13s}{r['n_signals']:7d}"
              f"{r['mean_pairwise_corr']:10.3f}{r['m_eff_bracket']:9.3f}"
              f"{r['m_eff_sltp_dim']:9.3f}{r['m_eff_hold_dim']:9.3f}"
              f"{r['reduction_factor']:10.2f}×")
    print(f"\n  pooled M_eff(bracket) = {ms.mean():.3f} ± {ms.std():.3f}  "
          f"(range {ms.min():.3f}..{ms.max():.3f})")
    print(f"  prediction P3A-1 (2 ≤ M_eff ≤ 5): "
          f"{'CONFIRMED' if 2 <= ms.mean() <= 5 else 'FALSIFIED'}")
    print(f"  prediction P3A-3 (spread ≤ ±1.5): "
          f"{'CONFIRMED' if ms.max()-ms.min() <= 3.0 else 'FALSIFIED'}")
    print(f"  stopping rule (abort if M_eff > 8): "
          f"{'ABORT — correction useless' if ms.mean() > 8 else 'correction is material'}")

    with open(os.path.join(OUT, 'P3A_SUMMARY.json'), 'w') as f:
        json.dump(dict(protocol='P3-A', cards=recs,
                       pooled_m_eff=round(float(ms.mean()), 4),
                       pooled_sd=round(float(ms.std()), 4),
                       n_signal_columns=N_SIGNAL_COLUMNS), f,
                  indent=1, ensure_ascii=False)
    print(f"→ saved {OUT}/P3A_SUMMARY.json")


if __name__ == '__main__':
    main()
