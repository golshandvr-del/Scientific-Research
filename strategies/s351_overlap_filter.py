# -*- coding: utf-8 -*-
"""
S351 — آزمونِ **اجباریِ** همپوشانی و کاربردِ فیلتری (قانونِ همپوشانیِ پروژه)
================================================================================
قانونِ پروژه صریح است: اگر لایهٔ نو با لایه‌های موجود همپوشانی کلی یا جزئی
داشت، «حتماً امکانِ استفاده به‌عنوان فیلتر را بررسی کن و این را به مراحلِ
بعد موکول نکن هرگز». این فایل همان کار را می‌کند.

--------------------------------------------------------------------------------
دو پرسشِ مستقل که این‌جا اندازه‌گیری می‌شوند
--------------------------------------------------------------------------------
پرسشِ ۱ — **همپوشانیِ رویداد**: چند درصد از سیگنال‌های لایهٔ پذیرفته‌شدهٔ S333
    (pullbackِ احیاشده) روی همان کندلِ سیگنالِ LPSB می‌افتد؟
    پیش‌بینیِ نظری: ~۰٪. چون S333 یک **پول‌بکِ درونِ روند** است (ورود در
    عقب‌نشینی) و LPSB یک **شکستِ ساختار** است (ورود در گسست). این دو رویداد
    ساختاراً در نقاطِ متفاوتِ چرخه رخ می‌دهند. اگر عدد نزدیکِ صفر بود، LPSB
    لبهٔ رویدادیِ مستقل دارد و «بازتولیدِ لایهٔ موجود» نیست.

پرسشِ ۲ — **ارزشِ فیلتری**: مهم‌ترین دارایی‌ای که LPSB در این نشست تولید کرد،
    نه ماشهٔ آن، بلکه **وضعیتِ ساختار** `state ∈ {+1, −1}` است — یک متغیرِ
    ماندگار که می‌گوید «آخرین شکستِ لگ-متناسب صعودی بود یا نزولی». روی
    XAUUSD-D1 این متغیر lift جهتیِ **+۲۳.۹pp** نشان داد؛ چنین متغیری کاندیدِ
    درجه‌یکِ **تأییدِ جهت** برای لایه‌های موجود است.

    آزمون: S333 یک لایهٔ **لانگ‌محور** است. طبق منطق، سیگنالِ لانگِ آن باید
    وقتی بهتر باشد که ساختارِ بازار هم صعودی باشد (`state = +1`). پس:

        S333_filtered = S333_signal  AND  (LPSB_state == +1)

    اگر این کار WR/PF را بالا ببرد ⇒ **بهبودِ لایهٔ موجود** (راهِ اولِ پروژه)،
    که به‌خودیِ‌خود یک دستاورد است حتی اگر LPSB به‌عنوان لایهٔ مستقل رد شود.

--------------------------------------------------------------------------------
⛔ سپرهای انصاف
--------------------------------------------------------------------------------
    ۱) هندسهٔ ارزیابی **همان هندسهٔ خودِ S333** است (`BEST_CFG`: sl/tp/max_hold
       مخصوصِ هر TF). هیچ پارامترِ S333 دست‌کاری نمی‌شود — تنها یک ماسکِ
       جهتی روی سیگنالش گذاشته می‌شود. پس هر تفاوت **فقط** به فیلتر منتسب است.
    ۲) `state` علّی است: از `confirmed_pivots` ساخته می‌شود که فقط کندل‌های
       بسته‌شده را می‌خواند (نقصِ repaintِ سورسِ MT4 در بازسازی رفع شد).
    ۳) هیچ آستانه‌ای برای فیلتر تنظیم نمی‌شود — `state == +1` تنها حالتِ
       ممکن است، صفرْ درجهٔ آزادی. پس این فیلتر **قابلِ over-fit نیست**.
    ۴) پارامترِ LPSB همان عضوِ مرکزیِ پیش‌ثبت‌شده (L=8، f=0.33) است.

اجرا: PYTHONPATH=. python strategies/s351_overlap_filter.py
"""
import os
import sys
import json

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from strategies import s333_s79_pullback_revival as s333           # noqa: E402
from strategies.s351_lpsb import lpsb_signals                      # noqa: E402
from strategies.s351_verdict import CENTRAL                        # noqa: E402

OUT = 'results/_scan_S351'
WARMUP = 300

# کارت‌هایی که S333 روی آن‌ها لایهٔ فعالِ پذیرفته‌شده دارد
S333_CARDS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1']


def brief(tr, r):
    """متریک‌ها زیرِ کلیدِ `metrics` در خروجیِ RQS+ می‌نشینند، نه در ریشه."""
    if tr is None or r is None:
        return dict(n=0)
    m = r.get('metrics', {}) or {}
    return dict(n=int(len(tr)),
                wr=float(m.get('wr', float('nan'))),
                pf=float(m.get('pf', float('nan'))),
                net=float(m.get('net', m.get('net_profit', float('nan')))),
                exp=float(m.get('exp', float('nan'))),
                rqs=float(r.get('rqs_score', float('nan'))),
                verdict=str(r.get('verdict', '?')))


def run():
    rows = []
    for key in S333_CARDS:
        cfg = s333.BEST_CFG[key]
        path = se.ASSETS[key]['file']
        if not os.path.exists(path):
            print(f"!! {key}: no data", flush=True)
            continue
        df = se.load_data(path)
        n = len(df)

        # ---------- سیگنالِ اصلیِ S333 (دست‌نخورده) ----------
        base = s333.build_layer(df, cfg)

        # ---------- LPSB: ماشه و وضعیتِ ساختار ----------
        ls, ss, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'],
                                     warmup=WARMUP)
        lpsb_event = ls | ss

        nb = int(base.sum())
        if nb == 0:
            print(f"!! {key}: S333 produced no signal", flush=True)
            continue

        # ---------- پرسشِ ۱: همپوشانیِ رویداد ----------
        both = int((base & lpsb_event).sum())
        ov_pct = 100.0 * both / nb

        # ---------- پرسشِ ۲: فیلترِ جهتیِ ساختار ----------
        filt = base & (state == 1)
        anti = base & (state == -1)

        tr_b, r_b = s333.evaluate(df, base, key, cfg['sl'], cfg['tp'], cfg['mh'])
        tr_f, r_f = s333.evaluate(df, filt, key, cfg['sl'], cfg['tp'], cfg['mh'])
        tr_a, r_a = s333.evaluate(df, anti, key, cfg['sl'], cfg['tp'], cfg['mh'])

        b, f, a = brief(tr_b, r_b), brief(tr_f, r_f), brief(tr_a, r_a)
        row = dict(card=key, cfg=dict(cfg), bars=n,
                   n_s333_signals=nb, n_lpsb_events=int(lpsb_event.sum()),
                   overlap_bars=both, overlap_pct=ov_pct,
                   baseline=b, structure_up=f, structure_down=a)
        rows.append(row)

        print(f"\n=== {key} ===", flush=True)
        print(f"    S333 signals={nb}  LPSB events={int(lpsb_event.sum())}  "
              f"same-bar overlap={both} ({ov_pct:.2f}%)", flush=True)
        print(f"    baseline        n={b.get('n',0):4d} WR={b.get('wr',float('nan')):6.2f}% "
              f"PF={b.get('pf',float('nan')):5.2f} net=${b.get('net',float('nan')):>10,.0f} "
              f"RQS={b.get('rqs',float('nan')):5.1f}", flush=True)
        print(f"    state=+1 (up)   n={f.get('n',0):4d} WR={f.get('wr',float('nan')):6.2f}% "
              f"PF={f.get('pf',float('nan')):5.2f} net=${f.get('net',float('nan')):>10,.0f} "
              f"RQS={f.get('rqs',float('nan')):5.1f}", flush=True)
        print(f"    state=-1 (down) n={a.get('n',0):4d} WR={a.get('wr',float('nan')):6.2f}% "
              f"PF={a.get('pf',float('nan')):5.2f} net=${a.get('net',float('nan')):>10,.0f} "
              f"RQS={a.get('rqs',float('nan')):5.1f}", flush=True)

    os.makedirs(OUT, exist_ok=True)
    p = f'{OUT}/_overlap_filter.json'
    with open(p, 'w') as fh:
        json.dump(rows, fh, indent=1, default=float)
    print(f"\n    [checkpoint] {p}", flush=True)


if __name__ == '__main__':
    run()
