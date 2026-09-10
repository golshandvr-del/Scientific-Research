# -*- coding: utf-8 -*-
"""S547 — ممیزی هم‌پوشانی (قانون Overlap: هر کارت z≥2.5 ⇒ فوری) — فقط خواندن.

۱) در برابر S382-H4 لایو (WPR momentum، ورود/خروج واقعی؛ مرجع همان روش s520_overlap_audit)
   — data/XAUUSD_H4.csv بالادستی حذف شده ⇒ مرجع از data/full/XAUUSD_H4.csv (تجمیع H1 از mt5_full).
۲) ابطال‌گر F3 پیش‌ثبت: سهم روزهای ورودِ S547 که dom∈{10,13,20} هستند (قلمرو S312/S432).
۳) پایداری سالانه و نیمه‌ها (توصیفی — حکم فقط از موتور است).
هیچ عددی از این اسکریپت در حکم موتور دخالت ندارد.
"""
from __future__ import annotations
import importlib.util, json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); os.chdir(ROOT)
OUT = 'results/_s547'
COST_PIP = 3.3
CARDS = ['XAUUSD_M15', 'XAUUSD_M20', 'XAUUSD_M30', 'XAUUSD_H4', 'XAUUSD_H6', 'XAUUSD_H8']


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def trades_with_time(L, df, sigfn):
    ps = L.pip_size('XAUUSD')
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    tr = L.simulate_trades(df, sigfn(df), sl_abs, L.RR, True, ps).copy()
    dtv = df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    tr['t_entry'] = dtv[tr['entry_bar'].values]; tr['t_exit'] = dtv[tr['exit_bar'].values]
    sl_pip = sl_abs / ps; be = 100.0 * (sl_pip + COST_PIP) / (sl_pip * L.RR + sl_pip)
    return tr, be


def seg(tr, be):
    n = len(tr)
    if n == 0: return dict(n=0, wr=None, lift=None)
    wr = 100.0 * float((tr['outcome'] == 'win').mean()); return dict(n=n, wr=round(wr, 2), lift=round(wr - be, 2))


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    S547 = _mod('tools/s547_preholiday_runner.py', '_s547')
    s382_signals = L.signals  # نسخهٔ اصلی قبل از هر وصله

    df_h4 = pd.read_csv('data/full/XAUUSD_H4.csv'); df_h4['dt'] = pd.to_datetime(df_h4['time'], unit='s')
    tr_h4, _ = trades_with_time(L, df_h4, s382_signals)
    print(f'مرجع S382-H4 (H4 تجمیعی mt5_full): n={len(tr_h4)} (کارت قدیمی: 869)', flush=True)
    iv_e = tr_h4['t_entry'].values; iv_x = tr_h4['t_exit'].values
    o = np.argsort(iv_e); iv_e, iv_x = iv_e[o], iv_x[o]

    def in_h4(t):
        j = np.searchsorted(iv_e, t, 'right') - 1; lo = max(0, j - 8)
        return bool(np.any((iv_e[lo:j + 1] <= t) & (t < iv_x[lo:j + 1])))

    res = {}
    for card in CARDS:
        df = pd.read_csv(f'data/full/{card}.csv'); df['dt'] = pd.to_datetime(df['time'], unit='s')
        tr, be = trades_with_time(L, df, S547.make_signals)
        ov = np.array([in_h4(t) for t in tr['t_entry'].values])
        # F3: روز ورود واقعی = روز بعد از کندل سیگنال (open روز P) ⇒ تاریخ P
        t_entry = pd.to_datetime(tr['t_entry'].values)
        p_day = (t_entry + pd.Timedelta(days=1)).normalize()
        mid = np.isin(p_day.day, [10, 13, 20])
        win = (tr['outcome'] == 'win').to_numpy()
        yr = pd.Series(win, index=t_entry.year)
        yearly = yr.groupby(level=0).agg(['count', 'mean'])
        yearly['wr'] = (100 * yearly['mean']).round(1)
        pos_years = int((yearly['wr'] > be).sum()); n_years = len(yearly)
        h = len(tr) // 2
        halves = [round(100 * win[:h].mean(), 2), round(100 * win[h:].mean(), 2)]
        res[card] = dict(be=round(be, 2), n=len(tr),
                         s382_overlap_pct=round(100 * ov.mean(), 1), ov=seg(tr[ov], be), nonov=seg(tr[~ov], be),
                         f3_midmonth_pct=round(100 * mid.mean(), 1), midmonth=seg(tr[mid], be), non_midmonth=seg(tr[~mid], be),
                         years_above_be=f'{pos_years}/{n_years}', halves_wr=halves,
                         yearly_wr={int(k): [int(v['count']), float(v['wr'])] for k, v in yearly.iterrows()})
        r = res[card]
        print(f'{card}: n={r["n"]} be={r["be"]} | S382 overlap={r["s382_overlap_pct"]}% OV={r["ov"]} nonOV={r["nonov"]} | '
              f'F3 mid-month={r["f3_midmonth_pct"]}% mid={r["midmonth"]} nonmid={r["non_midmonth"]} | '
              f'years>BE {r["years_above_be"]} halves={halves}', flush=True)
    with open(f'{OUT}/overlap_audit.json', 'w') as f: json.dump(res, f, ensure_ascii=False)
    print('saved ->', f'{OUT}/overlap_audit.json')


if __name__ == '__main__':
    main()
