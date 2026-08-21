# -*- coding: utf-8 -*-
"""
s602_overlap_audit.py — ممیزیِ همپوشانیِ استخرِ ACCEPTشدهٔ S602 {D1,H8}
================================================================================
تعهدِ پیش‌ثبتِ S602 §4.5: «در صورتِ ACCEPT: همپوشانی با لایه‌های سایت با
شبیه‌سازِ رویدادمحور + آزمونِ فیلتر، سپس اطلاع به کاربر و انتظارِ تأیید.»

قانونِ همپوشانیِ پروژه — سه پرسش:
  ۱) با کدام لایه‌ها و چند درصد؟ (تلاقیِ بازهٔ [ورود,خروج] + ژاکاردِ روزِ ورود)
  ۲) بخشِ متفاوت ارزش دارد؟
  ۳) بخشِ همپوشان به‌عنوانِ فیلتر چه می‌کند؟ (بلافاصله آزموده می‌شود)

مقایسه‌شونده‌ها:
  · ۵ لایهٔ ACCEPT سایت — بازتولید عیناً با توابعِ s950_overlap_audit
    (S382_H4، S344_M15، S356_H1، S312_M30، S355_M5) — صفر بازنویسی.
  · S950-H8 drift-aligned (ACCEPT 80 از دانشمندِ موازی) — چون عضوِ غالبِ
    S602 (سهم ۸۱٪) روی همان کارتِ H8 نشسته است؛ اگر این دو یکی باشند،
    S602 «کشفِ تازه» نیست و باید صادقانه گزارش شود.

بازتولیدِ S602: عیناً زنجیرهٔ داوری — member_population(D1,H8) از
s601_engle_pool (با CANDIDATES بازنویسی‌شده مثلِ wrapper رسمی s602) +
rp.pool_cards (FIFO تقویمی). ستون‌های t_entry/t_exit خودِ استخر مبنای
بازه‌هاست ⇒ دقیقاً همان ۳۶۳ معامله‌ای که حکم گرفت.

قلمروها: فقط *خواندن* از قلمروِ S840 (انگل) و S950؛ هیچ فایلی از آن
دهه‌ها تغییر نمی‌کند.
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import strategies.s601_engle_pool as base                    # noqa: E402
import engine.rqs2_pool as rp                                 # noqa: E402
from strategies.s950_overlap_audit import (                   # noqa: E402
    s382_trades, s344_trades, s356_trades, s312_trades, s355_trades,
    s950_trades, to_dt, intervals_from_trades, interval_overlap_pct)

OUT = 'results/_s602_engle_pool_d1h8'


def s602_pool():
    """بازتولیدِ دقیقِ استخرِ داوری‌شدهٔ S602 (همان مسیرِ wrapper رسمی)."""
    base.CANDIDATES = ['D1', 'H8']
    base.SEED = 20260818
    members = []
    for tf in base.CANDIDATES:
        m = base.member_population(tf)
        if m is None:
            raise RuntimeError(f'بازتولیدِ عضو {tf} شکست خورد — ممیزی باطل.')
        members.append(m)
    res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                              lift=m['lift']) for m in members])
    pool = res['pool'].sort_values('t_entry').reset_index(drop=True)
    if len(pool) != 363:
        raise RuntimeError(f'n={len(pool)} ≠ 363 — با حکمِ رسمی نمی‌خواند.')
    return pool


def main():
    print('بازتولیدِ استخرِ S602 {D1,H8}…', flush=True)
    pool = s602_pool()
    iv602 = list(zip(pool['t_entry'].values, pool['t_exit'].values))
    days602 = set(pd.DatetimeIndex(pool['t_entry']).normalize())
    pnl = pool['pnl_pip'].values
    print(f'S602 pool: n={len(pool)} (سلامت ✓ = ۳۶۳ معاملهٔ حکم)', flush=True)

    layers = {}
    for name, fn in (('S382_H4', s382_trades), ('S344_M15', s344_trades),
                     ('S356_H1', s356_trades), ('S312_M30', s312_trades),
                     ('S355_M5', s355_trades)):
        try:
            tr, dt = fn()
            iv, days = intervals_from_trades(tr, dt)
            layers[name] = dict(iv=iv, days=days, n=len(tr))
            print(f'{name}: n={len(tr)}', flush=True)
        except Exception as e:                                # noqa: BLE001
            layers[name] = dict(error=repr(e))
            print(f'{name}: ERROR {e!r}', flush=True)

    # S950-H8 — همسایهٔ هم‌کارت (فقط خواندنی)
    try:
        tr950, df950, _, _ = s950_trades()
        dt950 = to_dt(df950['time'].values)
        iv950, days950 = intervals_from_trades(tr950, dt950)
        layers['S950_H8'] = dict(iv=iv950, days=days950, n=len(tr950))
        print(f'S950_H8: n={len(tr950)}', flush=True)
    except Exception as e:                                    # noqa: BLE001
        layers['S950_H8'] = dict(error=repr(e))
        print(f'S950_H8: ERROR {e!r}', flush=True)

    report = dict(s602=dict(n=len(pool)), vs={})
    overlap_mask_site = np.zeros(len(pool), bool)   # فقط ۵ لایهٔ سایت
    SITE = {'S382_H4', 'S344_M15', 'S356_H1', 'S312_M30', 'S355_M5'}
    per_layer_mask = {}
    for name, L in layers.items():
        if 'error' in L:
            report['vs'][name] = dict(error=L['error'])
            continue
        pct, hits = interval_overlap_pct(iv602, L['iv'])
        jd = (100.0 * len(days602 & L['days']) /
              max(len(days602 | L['days']), 1))
        b_sorted = sorted(L['iv'])
        starts = np.array([x[0] for x in b_sorted])
        ends = np.array([x[1] for x in b_sorted])
        mask = np.zeros(len(pool), bool)
        for i, (a0, a1) in enumerate(iv602):
            j = np.searchsorted(starts, a1, side='right')
            if j > 0 and np.any(ends[:j] >= a0):
                mask[i] = True
        per_layer_mask[name] = mask
        if name in SITE:
            overlap_mask_site |= mask
        # این‌همانیِ ورود با S950 (هم‌کارتِ H8): ورودِ دقیقاً هم‌کندل
        same_entry = None
        if name == 'S950_H8':
            e602 = set(pool['t_entry'].values.astype('datetime64[ns]'))
            eb = np.asarray([x[0] for x in L['iv']], dtype='datetime64[ns]')
            same_entry = int(sum(1 for x in eb if x in e602))
        report['vs'][name] = dict(n_other=L['n'], concur_pct=round(pct, 2),
                                  concur_hits=hits, jac_day=round(jd, 2),
                                  **({'same_entry_bars': same_entry}
                                     if same_entry is not None else {}))
        print(f'{name}: concur={pct:.2f}% ({hits}/{len(iv602)}) '
              f'jac_day={jd:.2f}%'
              + (f' same_entry={same_entry}' if same_entry is not None else ''),
              flush=True)

    # ---------- پرسشِ ۳ — فیلترِ همپوشانی با ۵ لایهٔ سایت ----------
    n_ov = int(overlap_mask_site.sum())
    report['overlap_as_filter_site'] = dict(n_overlap=n_ov, n_total=len(pool))
    if n_ov >= 5 and n_ov <= len(pool) - 5:
        wr_ov = 100.0 * float((pnl[overlap_mask_site] > 0).mean())
        wr_no = 100.0 * float((pnl[~overlap_mask_site] > 0).mean())
        report['overlap_as_filter_site'].update(
            wr_overlap=round(wr_ov, 2), wr_nonoverlap=round(wr_no, 2),
            net_pip_overlap=round(float(pnl[overlap_mask_site].sum()), 1),
            net_pip_nonoverlap=round(float(pnl[~overlap_mask_site].sum()), 1))
        print(f'فیلترِ سایت: WR(هم‌زمان)={wr_ov:.1f}% vs WR(مستقل)={wr_no:.1f}% '
              f'(n_ov={n_ov})', flush=True)
    else:
        report['overlap_as_filter_site']['note'] = (
            'همپوشانِ سایت زیرِ آستانهٔ آزمونِ فیلتر — چیزی برای فیلترشدن نیست.')
        print(f'همپوشانِ سایت: {n_ov} معامله — زیر آستانه.', flush=True)

    # فیلترِ جداگانه برای S950 (هم‌کارت) — اگر معنادار باشد
    if 'S950_H8' in per_layer_mask:
        m950 = per_layer_mask['S950_H8']
        k = int(m950.sum())
        d = dict(n_overlap=k, n_total=len(pool))
        if 5 <= k <= len(pool) - 5:
            d.update(wr_overlap=round(100 * float((pnl[m950] > 0).mean()), 2),
                     wr_nonoverlap=round(100 * float((pnl[~m950] > 0).mean()), 2),
                     net_pip_overlap=round(float(pnl[m950].sum()), 1),
                     net_pip_nonoverlap=round(float(pnl[~m950].sum()), 1))
        report['overlap_as_filter_s950'] = d
        print(f'فیلترِ S950-H8: {json.dumps(d, ensure_ascii=False)}', flush=True)

    json.dump(report, open(f'{OUT}/overlap_audit.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print('ذخیره شد:', f'{OUT}/overlap_audit.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
