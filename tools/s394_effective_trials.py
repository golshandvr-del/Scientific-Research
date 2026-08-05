# -*- coding: utf-8 -*-
"""S394 — شمارشِ **آزمون‌های مؤثرِ مستقل** برای دروازهٔ `H5`.

⚠️ این ابزار می‌تواند با «دور زدنِ معیار» اشتباه گرفته شود. سه قیدِ ثبت‌شده
در پیش‌ثبتِ S394 آن را ممنوع می‌کنند:
  ۱. این محور در پیش‌ثبتِ S393 §۷ **پیش از** دیدنِ نتیجهٔ فیلترها مجاز شمرده
     شد؛ فیلترها شکست خوردند (۰ از ۱۵) ⇒ ترتیبِ زمانی صادقانه است.
  ۲. **هیچ آستانه‌ای پایین نمی‌آید.** `H5` همان `z_obs > E[max_z(N)]` است؛
     تنها پرسش «N چیست» — پرسشی آماری با پاسخِ اندازه‌گیری‌پذیر.
  ۳. **نقطهٔ شکست پیشاپیش قفل شد: N ≈ ۲٬۷۰۰.** اگر `M_eff` بالاتر افتاد،
     نامزد **رد** می‌شود و هیچ برآوردگرِ جایگزینی امتحان نخواهد شد.

فضایِ جست‌وجوی قفل‌شده (پیش‌ثبتِ S394 §۳) — سه مؤلفه، فرمولِ **ضربی**:
    M_eff_total = M_eff(A قواعد) × M_eff(B هندسه‌ها) × M_eff(C فیلترها)
ضربی چون فضا حاصل‌ضربِ دکارتی است ⇒ **محافظه‌کارانه‌تر** از جمعی.
و کفِ محافظه‌کارانهٔ ۱۰۰۰ (برای ۱۴ کارتِ دیگر و ۲۰۰ استراتژیِ ثبت‌نشده).

آزمونِ سلامتِ برآوردگر — **پیش از** استفاده اجرا می‌شود:
    ستون‌های یکسان  ⇒ M_eff ≈ 1
    ستون‌های متعامد ⇒ M_eff ≈ M
اگر پاس نشد، ابزار **متوقف** می‌شود.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R  # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s394')
os.makedirs(OUT, exist_ok=True)

CARD = 'XAUUSD_H1'
Z_OBS = 3.739          # نامزد — قفل‌شده
BREAK_N = 2700         # نقطهٔ شکستِ پیشاپیش‌ثبت‌شده
FLOOR = 1000.0         # کفِ محافظه‌کارانه


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sanity_check():
    """آزمونِ سلامتِ برآوردگر — شرطِ پیش‌ثبت‌شدهٔ استفاده."""
    rng = np.random.default_rng(20260805)
    n, M = 4000, 24
    # ۱) ستون‌های یکسان
    col = rng.standard_normal(n)
    same = np.tile(col.reshape(-1, 1), (1, M))
    m_same = R.effective_trials(same)
    # ۲) ستون‌های مستقل (تقریبِ متعامد)
    indep = rng.standard_normal((n, M))
    m_indep = R.effective_trials(indep)
    ok = (m_same <= 2.5) and (m_indep >= 0.85 * M)
    print('  sanity: identical(M=%d) -> M_eff=%.3f  (expect ~1)' % (M, m_same))
    print('  sanity: independent(M=%d) -> M_eff=%.3f  (expect ~%d)'
          % (M, m_indep, M))
    print('  sanity verdict: %s' % ('PASS' if ok else 'FAIL'))
    return ok, m_same, m_indep


def comp_A(L, RB, df):
    """مؤلفهٔ A — ۲۴۸ قاعدهٔ ورود، سریِ بولیِ سیگنال روی XAUUSD_H1."""
    bank = RB.build_rules()
    cols, names = [], []
    for nm, fn in bank:
        try:
            s = np.asarray(fn(df)).astype(float)
        except Exception:
            continue
        if s.shape[0] != len(df):
            continue
        if np.nanvar(s) <= 1e-12:
            continue          # قاعدهٔ همیشه-خاموش، آزمونِ واقعی نیست
        cols.append(np.nan_to_num(s, nan=0.0))
        names.append(nm)
    X = np.column_stack(cols)
    return X, names


def comp_B(L):
    """مؤلفهٔ B — ۴۸ هندسه (۸ کارت × ۲ slk × ۳ rr)، سریِ نتیجهٔ معامله.

    هر ستون: بردارِ برد/باختِ معاملاتِ همان هندسه روی **قاعدهٔ نامزد**،
    نمونه‌برداری‌شده روی شبکهٔ زمانیِ مشترک (کندلِ ورود).
    کارت‌های مختلف تایم‌فریمِ مختلف دارند ⇒ روی محورِ زمانِ تقویمیِ
    مشترک (روز) تجمیع می‌شوند تا همبستگی قابلِ اندازه‌گیری شود.
    """
    CARDS = ['XAUUSD_D1', 'XAUUSD_H4', 'XAUUSD_H1', 'XAUUSD_M30',
             'XAUUSD_M15', 'EURUSD_D1', 'EURUSD_H4', 'EURUSD_H1']
    RB = _mod('tools/step1_rule_bank.py', '_rb2')
    bank = dict(RB.build_rules())
    rule = bank['cci20_xup_135']
    cols, names = [], []
    for card in CARDS:
        try:
            d = L.load(card)
        except Exception:
            continue
        asset = 'EURUSD' if card.startswith('EUR') else 'XAUUSD'
        ps = L.pip_size(asset)
        am = float(np.nanmedian(L.atr(d).to_numpy()))
        sig = pd.Series(np.asarray(rule(d)).astype(bool), index=d.index)
        for slk in (1.5, 1.15):
            for rr in (1.5, 2.2, 2.6):
                _bk = L.RR
                try:
                    L.RR = rr
                    tr = L.simulate_trades(d, sig, am * slk, rr, True, ps)
                finally:
                    L.RR = _bk
                if len(tr) < 30:
                    continue
                # سریِ روزانه: میانگینِ نتیجه در هر روزِ تقویمی
                dt = d['dt'].to_numpy()
                day = pd.to_datetime(
                    dt[tr['entry_bar'].to_numpy()]).normalize()
                win = (tr['outcome'] == 'win').astype(float).to_numpy()
                s = pd.Series(win, index=day).groupby(level=0).mean()
                cols.append(s)
                names.append(f'{card}_k{slk}_rr{rr}')
    # هم‌ترازیِ روی اجتماعِ روزها؛ روزهای بی‌معامله = میانگینِ ستون (بی‌اثر)
    Xdf = pd.concat(cols, axis=1)
    Xdf.columns = names
    Xdf = Xdf.apply(lambda c: c.fillna(c.mean()))
    return Xdf.to_numpy(float), names


def comp_C(L, df):
    """مؤلفهٔ C — ۲۸ فیلتر (۱۳ از S391 + ۱۵ از S393)، سریِ بولیِ ماسک."""
    F1 = _mod('tools/s391_dd_filter.py', '_f1')
    F2 = _mod('tools/s393_alpha_filter.py', '_f2')
    cols, names = [], []
    for src, tag in ((F1.build_filters(df), 's391'),
                     (F2.build_filters(df), 's393')):
        for nm, mask in src:
            if nm == 'none':
                continue
            a = np.asarray(mask).astype(float)
            if np.nanvar(a) <= 1e-12:
                continue
            cols.append(a)
            names.append(f'{tag}:{nm}')
    return np.column_stack(cols), names


def main():
    print('S394 effective independent trials | card=%s' % CARD)
    print('z_obs=%.3f  BREAK_N=%d (pre-registered)  FLOOR=%.0f'
          % (Z_OBS, BREAK_N, FLOOR))
    print()
    print('=== step 0: estimator sanity (pre-registered gate) ===')
    ok, m_same, m_indep = sanity_check()
    if not ok:
        print('ABORT — estimator failed its sanity test.')
        return
    print()

    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    df = L.load(CARD)

    res = {'z_obs': Z_OBS, 'break_n': BREAK_N, 'floor': FLOOR,
           'sanity_identical': round(m_same, 3),
           'sanity_independent': round(m_indep, 3)}

    print('=== component A: entry rules ===')
    XA, nA = comp_A(L, RB, df)
    mA = R.effective_trials(XA)
    print('  raw M=%d  ->  M_eff=%.2f  (ratio %.3f)'
          % (XA.shape[1], mA, mA / XA.shape[1]))
    res.update(A_raw=XA.shape[1], A_eff=round(mA, 3))
    json.dump(res, open(os.path.join(OUT, 'meff.json'), 'w'), indent=1)

    print('=== component B: geometries ===')
    XB, nB = comp_B(L)
    mB = R.effective_trials(XB)
    print('  raw M=%d  ->  M_eff=%.2f  (ratio %.3f)'
          % (XB.shape[1], mB, mB / XB.shape[1]))
    res.update(B_raw=XB.shape[1], B_eff=round(mB, 3))
    json.dump(res, open(os.path.join(OUT, 'meff.json'), 'w'), indent=1)

    print('=== component C: filters ===')
    XC, nC = comp_C(L, df)
    mC = R.effective_trials(XC)
    print('  raw M=%d  ->  M_eff=%.2f  (ratio %.3f)'
          % (XC.shape[1], mC, mC / XC.shape[1]))
    res.update(C_raw=XC.shape[1], C_eff=round(mC, 3))

    total = mA * mB * mC
    total_floored = max(total, FLOOR)
    zbar = R.expected_max_z(total_floored)
    res.update(m_eff_product=round(total, 2),
               m_eff_final=round(total_floored, 2),
               z_bar_effective=round(zbar, 4),
               gap=round(Z_OBS - zbar, 4),
               h5_pass=bool(Z_OBS > zbar))
    print()
    print('=== combination (locked: multiplicative) ===')
    print('  M_eff = %.2f x %.2f x %.2f = %.2f' % (mA, mB, mC, total))
    print('  after conservative floor(%.0f): %.2f' % (FLOOR, total_floored))
    print('  z_bar(M_eff) = %.4f   vs   z_obs = %.3f   gap = %+.4f'
          % (zbar, Z_OBS, Z_OBS - zbar))
    print('  H5 verdict: %s' % ('PASS' if Z_OBS > zbar else 'FAIL'))
    print()
    print('  raw-count bound for reference: z_bar(23913) = %.4f'
          % R.expected_max_z(23913))
    json.dump(res, open(os.path.join(OUT, 'meff.json'), 'w'), indent=1)
    print()
    print('written -> results/_s394/meff.json')


if __name__ == '__main__':
    main()
