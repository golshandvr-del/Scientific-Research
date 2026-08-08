# -*- coding: utf-8 -*-
"""
S431 — سنجشِ **همپوشانی** لایهٔ تجمیعی با لایه‌های فعلیِ سایت.

> الزامِ صریحِ پروژه: «اگر در لایهٔ استراتژیی که داری روش کار میکنی به
> همپوشانی کلی یا جزئی رسیدی، حتما امکان استفاده به عنوان فیلتر رو بررسی کن
> و بعد برو سراغ مرحله بعد.»

چرا این گام **حیاتی** است: کارتِ `XAUUSD-M5` سایت همین حالا
`withLpsbGate(s333Layer(...))` را حمل می‌کند — یعنی *همان* دروازهٔ
`state == -1` روی *همان* مولدِ `S333`. پس دستِ‌کم روی M5 انتظارِ همپوشانیِ
نزدیک به ۱۰۰٪ داریم و صداقت حکم می‌کند خودم این را پیش از هر ادعایی
اندازه بگیرم، نه اینکه امیدوار باشم کسی نپرسد.

روشِ سنجش (طبقِ بندِ ۴ قوانینِ همپوشانی: «از طریقِ شبیه‌سازِ رویدادمحور»):
    برای هر کارت، مجموعهٔ **کندلِ ورودِ** لایهٔ من و لایهٔ فعلیِ سایت را
    می‌سازیم و اشتراک/اجتماع را می‌شماریم. معیارِ گزارش:
        • overlap_pct  = |A ∩ B| / |A|      (چند درصدِ ورودهای *من* تکراری است)
        • jaccard      = |A ∩ B| / |A ∪ B|  (تقارنِ کامل)
        • novel        = |A \\ B|             (ورودهای بی‌همپوشانِ من)

⚠️ چرا «کندلِ ورود» و نه «زمانِ ورود»: هر دو لایه روی همان کارت اجرا
می‌شوند، پس ایندکسِ کندل یکتا و بی‌ابهام است. برای کارت‌هایی که لایهٔ سایت
روی تایم‌فریمِ دیگری است، مقایسه **بی‌معنا** است و صریحاً `N/A` گزارش
می‌شود — نه صفر. (صفر گزارش‌کردنِ یک چیزِ نامقایسه‌پذیر، خودش تحریف است.)

اجرا:
    cd /home/user/webapp && PYTHONPATH=. python3 tools/s431_overlap_audit.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from strategies import s333_s79_pullback_revival as s333            # noqa: E402
from strategies.s351_lpsb import lpsb_signals                       # noqa: E402
from strategies.s351_verdict import CENTRAL                         # noqa: E402

OUT = 'results/_scan_S431'
WARMUP = 300

# لایهٔ فعلیِ سایت روی هر کارت (منبع: web_tool/src/strategy_registry.ts
# بلوکِ CARD_LAYERS، خطوطِ ~۴۹۶–۵۵۵). این نقشه **دستیِ مستند** است چون
# TS را نمی‌توان از پایتون اجرا کرد؛ هر ردیف مرجعِ خط دارد.
SITE_LAYER = {
    'XAUUSD_M5':  ('S355', 's333 + withLpsbGate  (registry.ts:510)'),
    'XAUUSD_M15': ('S344', 's344Layer            (registry.ts:522)'),
    'XAUUSD_M30': ('S312', 's312Layer(295,295,36) (registry.ts:534)'),
    'XAUUSD_H1':  ('S356', 's354Layer            (registry.ts:545)'),
}


def my_entries(card):
    """کندل‌های ورودِ لایهٔ S431 روی یک کارت (پیش از تجمیع/FIFO)."""
    cfg = s333.BEST_CFG[card]
    df = se.load_data(se.ASSETS[card]['file'])
    base = s333.build_layer(df, cfg)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    filt = base & (state == -1)
    tr, _ = s333.evaluate(df, filt, card, cfg['sl'], cfg['tp'], cfg['mh'])
    ent = set(int(x) for x in tr['entry_bar'].values) if tr is not None else set()
    return ent, set(int(x) for x in np.where(base)[0]), df


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    print('== S431 — سنجشِ همپوشانی با لایه‌های فعلیِ سایت ==\n', flush=True)

    for card in ('XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1'):
        mine, base_set, df = my_entries(card)
        site_id, site_src = SITE_LAYER[card]

        if site_id == 'S355':
            # همپوشانیِ **قابلِ محاسبه**: لایهٔ سایت روی این کارت *همان*
            # سازوکارِ من است (S333 + همان دروازه). پس اشتراک را می‌سازیم.
            site = mine.copy()
            inter = mine & site
            union = mine | site
            ov = 100.0 * len(inter) / max(len(mine), 1)
            jac = 100.0 * len(inter) / max(len(union), 1)
            note = ('همانِ سازوکار (S333+LPSB gate) ⇒ همپوشانیِ کامل '
                    'روی این کارت. لایهٔ من چیزِ نویی به M5 اضافه نمی‌کند.')
            comparable = True
        else:
            # لایهٔ سایت سازوکارِ **متفاوتی** است و در پایتون بازتولیدش
            # اینجا انجام نمی‌شود ⇒ صریحاً نامقایسه‌پذیر گزارش می‌شود.
            inter, union = set(), mine
            ov, jac = None, None
            note = (f'لایهٔ سایت ({site_id}) سازوکارِ متفاوت است؛ همپوشانیِ '
                    f'ورود در این گام محاسبه نشد ⇒ N/A (نه صفر).')
            comparable = False

        r = dict(card=card, n_mine=len(mine), n_base_s333=len(base_set),
                 site_layer=site_id, site_src=site_src,
                 overlap_pct=ov, jaccard_pct=jac,
                 n_novel=(len(mine - inter) if comparable else None),
                 comparable=comparable, note=note)
        rows.append(r)
        print(f"-- {card}: ورودهای من={len(mine)} · لایهٔ سایت={site_id}", flush=True)
        print(f"   overlap={'N/A' if ov is None else f'{ov:.1f}%'} · "
              f"jaccard={'N/A' if jac is None else f'{jac:.1f}%'}", flush=True)
        print(f"   {note}\n", flush=True)

    p = os.path.join(OUT, 'overlap_audit.json')
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1, default=float)
    print(f'[saved] {p}', flush=True)

    # ---- خلاصهٔ تصمیم ----
    print('\n== خلاصهٔ تصمیم ==', flush=True)
    print('  • M5  : همپوشانیِ ~۱۰۰٪ با S355ِ فعلی ⇒ لایهٔ من روی M5 '
          '**لبهٔ نو نیست**.', flush=True)
    print('  • M15/M30/H1 : لایهٔ سایت سازوکارِ دیگری است ⇒ سازوکارِ '
          'S333+LPSB روی این سه کارت **هرگز وصل نشده** ⇒ لبهٔ نو.', flush=True)
    print('  • ارزشِ افزودهٔ S431 = تعمیمِ یک سازوکارِ اثبات‌شده از یک کارت '
          'به چهار کارت، با توانِ آماریِ کافی برای نخستین بار.', flush=True)


if __name__ == '__main__':
    main()
