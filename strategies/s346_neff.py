# -*- coding: utf-8 -*-
"""
اندازه‌گیریِ **تعدادِ آزمون‌های مؤثرِ مستقل** در فضای جست‌وجوی واقعیِ S346
================================================================================
دروازهٔ `H5` در RQS2 می‌پرسد: «بهترینِ N تلاش را برداشتم؛ شانسِ محض چقدر خوب
ظاهر می‌شد؟» و کران را با `E[max_N]` می‌گیرد. اما آن کران برای N آزمونِ
**مستقل** معتبر است. فضای ما به‌شدت افزونه است:

  • ۴۰۱ اندیکاتور ⇒ ده‌ها میانگینِ متحرک و نوسان‌سنجِ تقریباً یکسان
  • ۱۲۹۶ هندسه   ⇒ پارامترهای مشترک؛ خیلی از ترکیب‌ها سیگنالِ یکسان می‌دهند
  • ۱۰ آستانهٔ چارکی به‌ازای هر ستون ⇒ دروازه‌های **تُوی‌هم** (nested)

پس N مؤثر باید **اندازه‌گیری** شود، نه فرض. این اسکریپت آن را با برآوردگرِ
مقدارِ ویژه (Nyholt/Cheverud) روی **همان داده‌های واقعی** می‌سنجد و عدد را در
`results/_scan_S346/<card>_neff.json` ذخیره می‌کند تا داوری از آن استفاده کند.

⚠️ صداقتِ روش: اگر عدد بزرگ درآمد، همان بزرگ اعلام می‌شود. هدف پایین آوردنِ
کران نیست؛ هدف **درست** کردنِ آن است. عددِ نهایی همراه با تفکیکِ سه مرحله
گزارش می‌شود تا هر کسی بتواند بازبینی کند.

اجرا:  python -m strategies.s346_neff XAUUSD-D1
"""
from __future__ import annotations

import sys
import os
import json
import itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from engine.rqs2 import effective_trials, expected_max_z
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_geom import CARDS, event_mask
from strategies.s346_bank401 import build_parts
from strategies.s346_joint import (MODES, SIDES, P_LIST, MULT_LIST, ER_LIST,
                                   SL_LIST, RR_LIST, HOLD_LIST)
from strategies.s346_stack import outcomes_for_geom

OUT = 'results/_scan_S346'
QLIST = (0.10, 0.15, 0.20, 0.25, 0.30, 0.70, 0.75, 0.80, 0.85, 0.90)


def stage_a_signals(card, df, warmup_of):
    """M_eff مرحلهٔ ۱: افزونگیِ **سریِ سیگنال** روی شبکهٔ هندسه.

    سریِ سیگنالِ علامت‌دار: +1 رویدادِ لانگ، −1 رویدادِ شورت، 0 هیچ. تنها
    (mode, mult, er, p, side) این سری را عوض می‌کنند — (sl, rr, hold) روی
    *نتیجه* اثر دارند نه بر *رویداد*، پس در مرحلهٔ B جدا سنجیده می‌شوند.
    """
    cols, labels = [], []
    ch_cache = {}
    for mode, p, mult, er, side in itertools.product(
            MODES, P_LIST, MULT_LIST, ER_LIST, SIDES):
        if p not in ch_cache:
            ch_cache[p] = adaptive_channel(df, p=p, mult=1.0)
        ch = ch_cache[p]
        ls, ss = event_mask(df, ch, mode, mult, er, warmup_of(p))
        if side == 'long':
            v = ls.astype('float64')
        elif side == 'short':
            v = -ss.astype('float64')
        else:
            v = ls.astype('float64') - ss.astype('float64')
        cols.append(v)
        labels.append((mode, p, mult, er, side))
    X = np.column_stack(cols)
    m_eff = effective_trials(X)
    return X, labels, m_eff, ch_cache


def stage_b_outcomes(card, df, ch_cache, asset, warmup_of):
    """M_eff مرحلهٔ ۲: افزونگیِ شبکهٔ **براکت** (sl × rr × hold) = ۱۲ ترکیب.

    روی یک مجموعهٔ رویدادِ ثابت، بردارِ برد/باختِ هر ترکیب سنجیده می‌شود. اگر
    براکت‌ها نتیجهٔ عملاً یکسانی بدهند (مثلاً hold بلند و SL نزدیک)، آزمون‌ها
    افزونه‌اند و N مؤثر کمتر است.
    """
    g0 = dict(mode='breakout', side='both', p=P_LIST[0], mult=MULT_LIST[1],
              er_thr=ER_LIST[0], sl_k=SL_LIST[0], rr=RR_LIST[0],
              hold=HOLD_LIST[0], tp_mode='atr')
    ch = ch_cache[g0['p']]
    ref, _ = outcomes_for_geom(df, ch, asset, g0, warmup_of(g0['p']))
    base_idx = ref['sig_idx']
    if len(base_idx) < 40:
        return None, 1.0
    pos = {int(b): i for i, b in enumerate(base_idx)}
    cols = []
    for sl, rr, hold in itertools.product(SL_LIST, RR_LIST, HOLD_LIST):
        g = dict(g0, sl_k=sl, rr=rr, hold=hold)
        fo, _ = outcomes_for_geom(df, ch, asset, g, warmup_of(g['p']))
        v = np.full(len(base_idx), np.nan)
        for b, w in zip(fo['sig_idx'], fo['win']):
            j = pos.get(int(b))
            if j is not None:
                v[j] = 1.0 if w else 0.0
        cols.append(np.nan_to_num(v, nan=0.5))
    X = np.column_stack(cols)
    return X, effective_trials(X)


def stage_c_filters(card, df, ch, ev_idx):
    """M_eff مرحلهٔ ۳: افزونگیِ ۴۰۱ اندیکاتور × ۱۰ آستانه، روی **اندیس‌های رویداد**.

    نکتهٔ ظریف: همبستگی باید در همان نقاطی سنجیده شود که آزمون واقعاً در آن‌ها
    انجام شده (رویدادها)، نه روی کلِ سری — وگرنه افزونگی دست‌کم/بیش‌برآورد
    می‌شود. آستانه‌ها هم روی **دروازهٔ بولین** سنجیده می‌شوند نه مقدارِ خام،
    چون آنچه آزمون می‌شود همان دروازه است.
    """
    man = build_parts(card, df, ch)
    vals, names = [], []
    for pth, pcols in zip(man['parts'], man['part_cols']):
        arr = np.load(pth, mmap_mode='r')
        for j, cname in enumerate(pcols):
            if not cname.startswith('B:'):
                continue
            v = np.asarray(arr[ev_idx, j], dtype='float64')
            vals.append(v)
            names.append(cname)
    V = np.column_stack(vals)
    finite = np.isfinite(V)
    V = np.where(finite, V, np.nan)
    m_ind = effective_trials(np.nan_to_num(V, nan=0.0))

    # آستانه‌ها: دروازه‌های بولینِ ۱۰ چارک برای نمونه‌ای از ستون‌ها
    rng = np.random.default_rng(11)
    pick = rng.choice(V.shape[1], size=min(60, V.shape[1]), replace=False)
    m_thr_list = []
    for j in pick:
        v = V[:, j]
        if not np.isfinite(v).any():
            continue
        gates = []
        for q in QLIST:
            thr = np.nanquantile(v, q)
            g = (v >= thr) if q <= 0.5 else (v <= thr)
            gates.append(np.nan_to_num(g.astype('float64'), nan=0.0))
        G = np.column_stack(gates)
        if np.nanvar(G) > 0:
            m_thr_list.append(effective_trials(G))
    m_thr = float(np.median(m_thr_list)) if m_thr_list else 1.0
    return m_ind, m_thr, len(names)


def run(card='XAUUSD-D1', n_selected=24):
    asset, path = CARDS[card]
    df = se.load_data(path)

    def warmup_of(p):
        return max(5 * p, 250)

    print(f"=== N_eff measurement :: {card} (bars={len(df)}) ===", flush=True)

    XA, labels, m_sig, ch_cache = stage_a_signals(card, df, warmup_of)
    print(f"  stage A signals : columns={XA.shape[1]:4d}  M_eff={m_sig:8.1f}",
          flush=True)

    XB, m_brk = stage_b_outcomes(card, df, ch_cache, asset, warmup_of)
    print(f"  stage B brackets: columns={0 if XB is None else XB.shape[1]:4d}  "
          f"M_eff={m_brk:8.1f}", flush=True)

    # اندیس‌های رویداد برای سنجشِ فیلترها = رویدادهای هندسهٔ نمایندهٔ پرتکرار
    ch = ch_cache[P_LIST[0]]
    ls, ss = event_mask(df, ch, 'breakout', MULT_LIST[1], ER_LIST[0],
                        warmup_of(P_LIST[0]))
    ev_idx = np.where(ls | ss)[0]
    print(f"  event bars for filter correlation: {len(ev_idx)}", flush=True)

    m_ind, m_thr, n_cols = stage_c_filters(card, df, ch, ev_idx)
    print(f"  stage C filters : columns={n_cols:4d}  M_eff_ind={m_ind:8.1f}  "
          f"M_eff_thr={m_thr:5.2f}", flush=True)

    # هندسه‌های انتخاب‌شده برای مرحلهٔ گران — افزونگیِ خودشان هم مهم است
    m_sel = min(float(n_selected), m_sig)

    n_geom_raw = XA.shape[1] * (0 if XB is None else XB.shape[1])
    n_filt_raw = n_selected * n_cols * len(QLIST)
    n_raw = n_geom_raw + n_filt_raw

    n_geom_eff = m_sig * m_brk
    n_filt_eff = m_sel * m_ind * m_thr
    n_eff = n_geom_eff + n_filt_eff

    print(f"  ---", flush=True)
    print(f"  RAW trials  : geometry={n_geom_raw:,}  filter={n_filt_raw:,}  "
          f"total={n_raw:,}  => bound {expected_max_z(n_raw):.3f} sigma",
          flush=True)
    print(f"  EFF trials  : geometry={n_geom_eff:,.0f}  filter={n_filt_eff:,.0f} "
          f" total={n_eff:,.0f}  => bound {expected_max_z(n_eff):.3f} sigma",
          flush=True)

    rec = dict(card=card, bars=int(len(df)),
               m_eff_signal=round(m_sig, 3), n_signal_cols=int(XA.shape[1]),
               m_eff_bracket=round(m_brk, 3),
               n_bracket_cols=(0 if XB is None else int(XB.shape[1])),
               m_eff_indicator=round(m_ind, 3), n_indicator_cols=int(n_cols),
               m_eff_threshold=round(m_thr, 3), n_thresholds=len(QLIST),
               n_selected=int(n_selected), m_eff_selected=round(m_sel, 3),
               n_trials_raw=int(n_raw), n_trials_eff=int(round(n_eff)),
               bound_raw=round(expected_max_z(n_raw), 4),
               bound_eff=round(expected_max_z(n_eff), 4),
               n_event_bars=int(len(ev_idx)))
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{card}_neff.json", 'w') as fh:
        json.dump(rec, fh, indent=1)
    print(f"  saved -> {OUT}/{card}_neff.json", flush=True)
    return rec


if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-D1')
