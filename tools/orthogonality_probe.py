# -*- coding: utf-8 -*-
"""آزمونِ متعامدسازیِ قید — **پیش‌آزمونِ اجباری قبل از هر بک‌تست**

## چرا این ابزار پیش از بک‌تست اجرا می‌شود
`results/FINDING_S333_CONJUNCTION_CONFLICT_DIAGNOSIS.md` اثبات کرد که بحرانِ
کفایتِ نمونه در لایهٔ میزبان از **تضادِ ساختاریِ دو قیدِ هم‌منبع** می‌آید:
`ema20>ema100` و `RSI(21)<35` هر دو از `diff(close)` ساخته می‌شوند و جهتِ متضاد
اعلام می‌کنند، پس نسبتِ استقلالشان `0.103` است — یعنی ۱۰ برابر کمتر از حالتِ
مستقل هم‌رخداد می‌شوند. آن سند نتیجه گرفت که این نقص **با هیچ مقدار داده‌ای
ترمیم نمی‌شود**، چون ویژگیِ ساختارِ قاعده است نه اندازهٔ نمونه.

پیامدِ عملی: **افزودنِ هر قیدِ نو به لایهٔ میزبان بدونِ سنجشِ نسبتِ استقلال،
ریسکِ تکرارِ همان تله را دارد** — و آن تله فقط پس از یک بک‌تستِ کاملِ گران
(و خرجِ درجهٔ آزادی) آشکار می‌شود.

این ابزار آن سنجش را **پیش از** بک‌تست انجام می‌دهد.

## معیار
```
ratio(A,B) = P(A ∧ B) / [P(A) × P(B)]
```
- `ratio ≈ 1`   ⇒ متعامد؛ افتِ نمونه فقط ضربِ احتمال‌هاست (سالم).
- `ratio < 0.25` ⇒ **پرچمِ تضادِ ساختاری**؛ قید نامزدِ رد است.
- `ratio > 4`    ⇒ **پرچمِ افزونگی**؛ قیدِ نو تقریباً همان قیدِ قبلی است
                   (اطلاعاتِ نو نمی‌افزاید، فقط توهمِ تأیید می‌سازد).

## چرا درجهٔ آزادی خرج نمی‌کند
هیچ WR، سود، p-value یا معامله‌ای تولید نمی‌شود. فقط **شمارشِ هم‌رخدادیِ کندل**
است — توصیفِ هندسهٔ فضایِ حالت، نه جست‌وجوی لبه. پس به دفترِ چندگانگی بدهکار
نمی‌شود و روی هر تعداد قید قابلِ اجراست.

## مرزِ صداقت
خروجیِ این ابزار **هیچ قیدی را تأیید نمی‌کند**. `ratio ≈ 1` فقط می‌گوید
«این قید نمونه را به‌طورِ ساختاری نمی‌کشد» — **نه** اینکه لبه‌ای دارد.
سنجشِ لبه فقط با بک‌تستِ کاملِ RQS2 و پرداختِ هزینهٔ آماری ممکن است.
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

from engine import scalp_engine as SE
import strategies.s333_s79_pullback_revival as S333

OUT = 'results/_audit_orthogonality'
os.makedirs(OUT, exist_ok=True)

FLAG_CONFLICT = 0.25
FLAG_REDUNDANT = 4.0


# ═══════════════════════════════════════════════════════════════════════════
#  پروفایلِ حجم — بازتولیدِ الگوریتمِ `Trinity Volume Profile` (Pine v6)
#  منبع: Telegram-Resource/telegram_source_1/Trinity Volume Profile @free_fx_pro.md
# ═══════════════════════════════════════════════════════════════════════════
def volume_profile(df, bbars=150, cnum=24, percent=70.0):
    """POC / VAH / VAL غلتانِ forward-safe.

    عیناً منطقِ سورسِ Pine، با سه تفاوتِ **اجباریِ** بک‌تست:

    ۱) **forward-safe:** پروفایلِ هر کندل فقط از `bbars` کندلِ **گذشته** (تا
       `i-1`) ساخته می‌شود. سورسِ Pine روی «آخرین N کندلِ چارت» کار می‌کند که
       در بک‌تست نشتِ آینده است.
    ۲) **تخصیصِ حجمِ بدنه/سایه:** همان فرمولِ سورس
       (`bodyvol = body·vol / (2·topwick + 2·botwick + body)`).
    ۳) **گسترشِ ناحیهٔ ارزش:** از POC به دو سو، هر بار سمتِ پرحجم‌تر، تا رسیدن
       به `percent%` از کلِ حجم — همان الگوریتمِ market-profile.

    خروجی: `poc`, `vah`, `val` (آرایه‌های هم‌طولِ df؛ NaN تا پر شدنِ پنجره).
    """
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    o = df['open'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    v = df['volume'].values.astype(np.float64)
    n = len(df)

    poc = np.full(n, np.nan)
    vah = np.full(n, np.nan)
    val = np.full(n, np.nan)

    # سهمِ حجمِ بدنه و سایه‌های هر کندل (طبقِ سورس)
    body = np.abs(c - o)
    topw = h - np.maximum(c, o)
    botw = np.minimum(c, o) - l
    denom = 2.0 * topw + 2.0 * botw + body
    denom[denom <= 0] = 1e-12
    v_body = body * v / denom
    v_topw = 2.0 * topw * v / denom
    v_botw = 2.0 * botw * v / denom

    for i in range(bbars, n):
        s = i - bbars          # پنجره: [s, i-1] — کندلِ جاری حذف ⇒ forward-safe
        e = i
        top = h[s:e].max()
        bot = l[s:e].min()
        if not np.isfinite(top) or top <= bot:
            continue
        step = (top - bot) / cnum
        if step <= 0:
            continue

        vols = np.zeros(cnum)
        # لبه‌های بین‌ها
        edges = bot + step * np.arange(cnum + 1)

        for j in range(s, e):
            # سهمِ بدنه در بازهٔ [min(o,c), max(o,c)]
            for lo, hi, vv in (
                (min(o[j], c[j]), max(o[j], c[j]), v_body[j]),
                (max(c[j], o[j]), h[j], v_topw[j]),
                (l[j], min(c[j], o[j]), v_botw[j]),
            ):
                if hi <= lo or vv <= 0:
                    continue
                # هم‌پوشانیِ [lo,hi] با هر بین — تخصیصِ متناسب (تابعِ get_vol سورس)
                k0 = max(0, int((lo - bot) / step))
                k1 = min(cnum - 1, int((hi - bot) / step))
                span = hi - lo
                for k in range(k0, k1 + 1):
                    ov = min(hi, edges[k + 1]) - max(lo, edges[k])
                    if ov > 0:
                        vols[k] += vv * ov / span

        tot = vols.sum()
        if tot <= 0:
            continue
        ip = int(np.argmax(vols))
        poc[i] = bot + step * (ip + 0.5)

        # گسترشِ ناحیهٔ ارزش از POC تا percent% حجم
        target = tot * percent / 100.0
        acc = vols[ip]
        lo_i = hi_i = ip
        while acc < target and (lo_i > 0 or hi_i < cnum - 1):
            below = vols[lo_i - 1] if lo_i > 0 else -1.0
            above = vols[hi_i + 1] if hi_i < cnum - 1 else -1.0
            if above >= below:
                hi_i += 1
                acc += vols[hi_i]
            else:
                lo_i -= 1
                acc += vols[lo_i]
        val[i] = bot + step * lo_i
        vah[i] = bot + step * (hi_i + 1)

    return poc, vah, val


def ratio(A, B):
    """نسبتِ استقلالِ دو ماسکِ بولین."""
    A = np.asarray(A, bool); B = np.asarray(B, bool)
    pA, pB = A.mean(), B.mean()
    pAB = (A & B).mean()
    ind = pA * pB
    return (pAB / ind if ind > 0 else np.nan), pA, pB, pAB, ind


def verdict(r):
    if not np.isfinite(r):
        return 'N/A'
    if r < FLAG_CONFLICT:
        return 'CONFLICT'
    if r > FLAG_REDUNDANT:
        return 'REDUNDANT'
    return 'ok'


def main():
    cards = sys.argv[1:] or ['XAUUSD_M30']
    report = []

    for card in cards:
        pair, tf = card.split('_')
        path = f'data/{pair}_{tf}.csv'
        if not os.path.exists(path):
            print(f'!! missing {path}'); continue

        df = SE.load_data(path)
        n = len(df)
        c = df['close'].values

        print('=' * 90)
        print(f'{card}   bars={n:,}')
        print('=' * 90)

        # ── قیدهای موجودِ لایهٔ میزبان (مرجعِ مقایسه) ──
        cfg = S333.BEST_CFG.get(card, S333.BEST_CFG['XAUUSD_M30'])
        ef = S333.ema(c, cfg['ef']); es = S333.ema(c, cfg['es'])
        r = S333.rsi(c, cfg['rp'])
        A_trend = ef > es
        A_rsi = r < cfg['rth']

        # ── قیدهای نامزدِ نو: حجم‌محور (منبعِ اطلاعاتیِ مستقل از diff(close)) ──
        print('computing volume profile (this is the slow part) ...', flush=True)
        poc, vah, val = volume_profile(df, bbars=150, cnum=24, percent=70.0)
        ok = np.isfinite(val) & np.isfinite(vah) & np.isfinite(poc)

        width = vah - val
        with np.errstate(invalid='ignore', divide='ignore'):
            # موقعیتِ نسبیِ قیمت در ناحیهٔ ارزش: 0=VAL، 1=VAH
            vpos = (c - val) / np.where(width > 0, width, np.nan)

        cands = {
            'near_VAL (vpos<0.25)':   ok & (vpos < 0.25),
            'below_VAL (vpos<0)':     ok & (vpos < 0.0),
            'near_VAH (vpos>0.75)':   ok & (vpos > 0.75),
            'below_POC (c<poc)':      ok & (c < poc),
            'inside_VA (0<vpos<1)':   ok & (vpos > 0) & (vpos < 1),
        }

        pairs = [('trend(ema%d>ema%d)' % (cfg['ef'], cfg['es']), A_trend),
                 ('rsi<%d' % cfg['rth'], A_rsi)]

        print(f"\n{'candidate':26s} {'vs existing':22s} {'P(A)':>7s} {'P(B)':>7s} "
              f"{'P(A&B)':>8s} {'indep':>8s} {'ratio':>7s}  verdict")
        print('-' * 100)

        rows = []
        for cname, C in cands.items():
            for ename, E in pairs:
                rr, pA, pB, pAB, ind = ratio(E, C)
                vd = verdict(rr)
                mark = {'CONFLICT': '🔴', 'REDUNDANT': '🟠', 'ok': '✅'}.get(vd, '  ')
                print(f'{cname:26s} {ename:22s} {pA:7.4f} {pB:7.4f} '
                      f'{pAB:8.5f} {ind:8.5f} {rr:7.3f}  {mark} {vd}')
                rows.append(dict(candidate=cname, existing=ename,
                                 p_a=round(pA, 5), p_b=round(pB, 5),
                                 p_ab=round(pAB, 6), indep=round(ind, 6),
                                 ratio=(round(rr, 4) if np.isfinite(rr) else None),
                                 verdict=vd))
            print()

        report.append(dict(card=card, bars=n, cfg=dict(cfg), rows=rows))

    with open(os.path.join(OUT, 'ortho.json'), 'w') as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(f'saved → {OUT}/ortho.json')


if __name__ == '__main__':
    main()
