# -*- coding: utf-8 -*-
"""
S346 — بهینه‌سازیِ **مشترکِ** هندسه × فیلتر با هدفِ «بیشینهٔ N»
================================================================================
چرا این فایل لازم شد؟ (درسِ روش‌شناختیِ این نشست)
--------------------------------------------------------------------------------
هندسهٔ قبلی (p=21، hold=34، fade/long) زیرِ تابعِ هدفِ **غلط** انتخاب شده بود
(اکتشاف با allow_overlap=True، داوری با False). پس از اصلاحِ تابعِ هدف، آن هندسه
تنها n=148 معاملهٔ نهایی می‌داد — مجاز (کفِ RQS+ برابر ۳۰ است) ولی خلافِ
هدفِ صریحِ این نشست: **N بالا و تعدادِ معاملهٔ زیاد**.

نکتهٔ کلیدی: `hold` بزرگ ⇒ حساب مدتِ طولانی اشغال ⇒ صف اکثرِ رویدادها را دور
می‌ریزد. پس «تعدادِ معاملهٔ نهایی» تابعِ **مشترکِ** هندسه و فیلتر است و نمی‌توان
اول هندسه را (با معیارِ WR) قطعی کرد و بعد فیلتر زد. باید هر دو را همزمان گشت.

تابعِ هدفِ رسمیِ این فایل:
        max  n_ALL(post-queue, post-filter)
        به‌شرطِ   min(WR_D, WR_H) ≥ wr_floor     (پیش‌بینِ G0)
                 min(PF_D, PF_H) ≥ pf_floor      (پیش‌بینِ G2)

--------------------------------------------------------------------------------
🛡️ سپرهای فعال در این فایل
--------------------------------------------------------------------------------
• **ضدِ اشتباهِ #۸ (تقلبِ WR با TP<SL):** قیدِ `rr ≥ 1.0` و در خانوادهٔ `mid`
  قیدِ `tp_d ≥ sl_d` — به‌صورتِ **ساختاری** در فضای جست‌وجو. یعنی تقلب
  «ناممکن» است، نه «ممنوع».
• **ضدِ اشتباهِ #۷ (اعدادِ رند):** همهٔ دوره‌ها از دنبالهٔ لوکاس/فیبوناچی
  (۱۳/۲۱/۳۴/۵۵/۷۶) و ضرایب از نسبت‌های طلایی (۱.۲۷۲/۱.۶۱۸/۲.۰۵۸/۲.۶۱۸) —
  هیچ ۵۰/۱۰۰/۲۰۰ی در کار نیست.
• **ضدِ اشتباهِ #۶ (TP/SL یکسان برای همهٔ TFها):** SL/TP بر حسبِ `sl_k × ATR_تطبیقی`
  یعنی **شناور** و ذاتاً متناسبِ هر TF (قانونِ «شاید همه چیز شناور است»).
• **ضدِ اشتباهِ #۵ (نتیجه‌گیری از یک TF):** این فایل روی همهٔ کارت‌ها اجرا می‌شود و
  هر کارت مستقل ذخیره می‌شود.
• **تکرارپذیری:** آستانه‌ها **فقط** از نیمهٔ discovery و شرطِ بهبود در **هر دو**
  نیمه (discovery و holdout) اجباری است.
"""
import sys
import os
import json
import itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_geom import CARDS
from strategies.s346_stack import build_features, outcomes_for_geom
from strategies.s346_stack2 import q_stats, screen, stack_maxn
from strategies.s346_bank401 import build_parts, screen401

OUT = 'results/_scan_S346'


# ------------------------------------------------------------------------------
# فضای هندسه — کوچک ولی هدفمند: hold کوتاه برای گردشِ سریعِ صف (⇒ N بالا)
# ------------------------------------------------------------------------------
P_LIST = (13, 21, 34)            # لوکاس/فیبوناچی — نه رند
MULT_LIST = (1.272, 1.618, 2.058)  # نسبت‌های طلایی
ER_LIST = (0.146, 0.236)         # آستانهٔ کاراییِ کایفمن
SL_LIST = (1.0, 1.618)           # ضریبِ ATRِ تطبیقی برای SL
RR_LIST = (1.0, 1.272)           # ⚠️ همیشه ≥ ۱ ⇒ ضدِ تقلبِ ساختاری
HOLD_LIST = (5, 8, 13)           # ⭐ کوتاه = گردشِ سریعِ صف = N بالا
MODES = ('fade', 'breakout')
SIDES = ('long', 'short', 'both')


def geometries():
    """مولدِ هندسه‌ها با قیدِ سختِ ضدِ تقلب."""
    for mode, side, p, mult, er, sl, rr, hold in itertools.product(
            MODES, SIDES, P_LIST, MULT_LIST, ER_LIST, SL_LIST, RR_LIST, HOLD_LIST):
        assert rr >= 1.0, 'anti-gaming: TP must be >= SL'
        yield dict(mode=mode, side=side, p=p, mult=mult, er_thr=er,
                   sl_k=sl, rr=rr, hold=hold, tp_mode='atr')


def prepare_fast(df, ch, F, asset, split_idx, geom, warmup):
    """
    ساختِ P برای یک هندسه — با استفادهٔ مجدد از df/ch (کشِ گران‌ها).

    ⚠️ `F=None` مجاز است: در حالتِ بانکِ کاملِ ۴۰۱، ماتریسِ ویژگی هرگز یکجا در
    حافظه نمی‌آید (۴۸۰MB > RAM). آن‌جا `screen401` خودش قطعاتِ parquet را
    یکی‌یکی می‌خواند و در پایان تنها ستون‌های زنده‌مانده را در `P['FV']` می‌گذارد.
    """
    fo, spread = outcomes_for_geom(df, ch, asset, geom, warmup)
    sb = fo['sig_idx']
    if len(sb) == 0:
        return None
    P = dict(fo=fo, sb=sb, spread=spread, F=F,
             pnl=fo['pnl_pip'], win=fo['win'], is_d=sb < split_idx)
    P['FV'] = F.iloc[sb].reset_index(drop=True) if F is not None else None
    return P


def sweep_card(card, min_base_n=600, top_k=24, save=True, wr_min_base=51.0):
    """
    ⚡ مرحلهٔ ۱ — **sweepِ ارزان**: برای هر هندسه فقط «آمارِ پایهٔ صف» را حساب
    می‌کند (بدونِ غربالِ بانک). دو خروجی: بودجهٔ N و کیفیتِ پایه.

    ⭐ اصلاحِ معیارِ انتخاب (اندازه‌گیریِ تجربیِ همین نشست)
    ------------------------------------------------------------------
    نسخهٔ اول **فقط** بر اساسِ `base_n` رتبه می‌داد، با این استدلال که «لبهٔ خامِ
    بی‌طرف بهترین بسترِ فیلتر است». آزمونِ مستقیم این استدلال را **رد کرد**:

        هندسهٔ پرظرفیت breakout/both p=21 h=5 :
            پایه  n=29713  WR=47.32٪  (زیرِ WRِ سربه‌سر)
            پس از غربالِ کلِ ۴۰۱ ابزار + انباشت →  WR=53.78٪
        ⇒ سقفِ لیفتِ قابلِ حصول ≈ **+۶.۵pp**

    یعنی «انتخابِ زیرمجموعه» یک عملگرِ محدود است، نه معجزه: نمی‌تواند ۱۴pp
    شکاف (۴۷ → ۶۱) را پر کند. پس پایهٔ زیرِ سربه‌سر از اساس **بی‌فایده** است،
    هرچقدر هم N داشته باشد.

    معیارِ اصلاح‌شده: ابتدا **کیفیتِ حداقلیِ پایه** به‌عنوان قید
    (`min(WR_D, WR_H) ≥ wr_min_base`)، سپس رتبه‌بندی بر اساسِ N در میانِ
    واجدانِ شرط. یعنی «بیشترین N از میانِ پایه‌های *قابلِ نجات*».
    """
    asset, path = CARDS[card]
    df = se.load_data(path)
    split_idx = int(len(df) * 0.60)
    os.makedirs(OUT, exist_ok=True)
    ch_cache = {}
    geoms = list(geometries())
    print(f"=== S346-SWEEP :: {card} :: {len(geoms)} geometries (base-queue only) ===",
          flush=True)
    rows = []
    for gi, g in enumerate(geoms):
        if g['p'] not in ch_cache:
            ch_cache[g['p']] = adaptive_channel(df, p=g['p'], mult=1.0)
        ch = ch_cache[g['p']]
        warmup = max(5 * g['p'], 250)
        fo, spread = outcomes_for_geom(df, ch, asset, g, warmup)
        sb = fo['sig_idx']
        if len(sb) == 0:
            continue
        Pmin = dict(fo=fo, sb=sb, spread=spread, pnl=fo['pnl_pip'],
                    win=fo['win'], is_d=sb < split_idx)
        bd, bh, ba = q_stats(Pmin, np.ones(len(sb), bool))
        rows.append(dict(geom=g, n_ev=int(len(sb)), base_n=ba['n'],
                         base_wr=ba['wr'], base_pf=ba['pf'], base_exp=ba['exp'],
                         wr_d=bd['wr'], wr_h=bh['wr'], n_d=bd['n'], n_h=bh['n']))
        if (gi + 1) % 200 == 0:
            print(f"  ... {gi+1}/{len(geoms)}", flush=True)
    # کیفیتِ پایه = بدترینِ دو بازه (تکرارپذیری از همان ابتدا الزامی است)
    for r in rows:
        r['base_wr_min'] = min(r['wr_d'], r['wr_h'])
        # فاصله تا کف ⇒ آیا با سقفِ لیفتِ +۶.۵pp اصلاً قابلِ رسیدن است؟
        r['gap_to_floor'] = round(WR_FLOOR_REF - r['base_wr_min'], 2)
        r['reachable'] = bool(r['gap_to_floor'] <= LIFT_CEILING_PP)
    if save:
        with open(f"{OUT}/{card}_sweep.json", 'w') as f:
            json.dump(dict(card=card, rows=rows), f, default=float)

    # ⭐ قیدِ کیفیت **قبل از** رتبهٔ N: «بیشترین N از میانِ پایه‌های قابلِ نجات»
    elig = [r for r in rows
            if r['base_n'] >= min_base_n and r['base_wr_min'] >= wr_min_base]
    elig.sort(key=lambda r: -r['base_n'])
    rows.sort(key=lambda r: -r['base_wr_min'])

    print(f">>> {card} sweep done: {len(rows)} geoms. "
          f"Top by BASE QUALITY (min WR over D/H):", flush=True)
    for r in rows[:12]:
        g = r['geom']
        print(f"   wr_min={r['base_wr_min']:5.2f} gap={r['gap_to_floor']:+6.2f} "
              f"{'REACH' if r['reachable'] else '  -  '} "
              f"n={r['base_n']:5d} PF={r['base_pf']:.3f} | "
              f"{g['mode']:8s}/{g['side']:5s} p={g['p']:2d} m={g['mult']} "
              f"sl={g['sl_k']} rr={g['rr']} h={g['hold']:2d}", flush=True)

    n_reach = sum(1 for r in rows if r['reachable'])
    print(f">>> reachable geoms (gap <= {LIFT_CEILING_PP}pp lift ceiling): "
          f"{n_reach}/{len(rows)}", flush=True)
    sel = elig[:top_k]
    print(f">>> selected {len(sel)} geometries for expensive stacking "
          f"(base n>={min_base_n} AND base wr_min>={wr_min_base})", flush=True)
    if not sel:
        print("!!! NO eligible geometry — the raw tool has no salvageable base on "
              "this card at this quality floor. Widening geometry family is required "
              "(subset selection alone cannot bridge the gap).", flush=True)
    return sel


def run_card(card, wr_floor=61.0, pf_floor=1.35, min_base_n=400,
             allow_time=False, top_report=15):
    """
    مرحلهٔ ۱: غربالِ ارزانِ هندسه‌ها بر اساسِ «بودجهٔ N» (base n پس از صف).
    مرحلهٔ ۲: انباشتِ فیلتر روی هندسه‌های واجد بودجه.
    مرحلهٔ ۳: انتخابِ بیشینهٔ n نهایی مشروط به کف‌های کیفیت.

    `allow_time=False` به‌صورتِ پیش‌فرض ⇒ سپرِ اشتباهِ رایجِ #۱ (لایهٔ زمان‌محور).
    """
    asset, path = CARDS[card]
    df = se.load_data(path)
    split_idx = int(len(df) * 0.60)
    os.makedirs(OUT, exist_ok=True)

    # کشِ کانال به‌ازای هر p (تنها به p وابسته است، نه به mult/side/hold)
    ch_cache = {}
    rows, best = [], None
    # ⚡ مرحلهٔ ۱: فقط هندسه‌های پرظرفیت (بودجهٔ N) به مرحلهٔ گران راه می‌یابند
    sel = sweep_card(card, min_base_n=min_base_n)
    geoms = [r['geom'] for r in sel]
    # ⭐ جعبه‌ابزارِ کاملِ ۴۰۱: قطعاتِ ویژگی یک‌بار ساخته و کش می‌شوند.
    # ویژگی‌های ساختاریِ کانال به p وابسته‌اند؛ p مرجع = پرتکرارترین p در sel
    # (اثرش تنها روی ۷ ستونِ CHAN است، نه ۴۰۱ ستونِ بانک).
    p_ref = max(set(g['p'] for g in geoms), key=[g['p'] for g in geoms].count) \
        if geoms else 21
    ch_ref = adaptive_channel(df, p=p_ref, mult=1.0)
    man = build_parts(card, df, ch_ref)
    print(f"=== S346-JOINT :: {card} :: {len(geoms)} geometries :: "
          f"objective=max N s.t. WR>={wr_floor} PF>={pf_floor} "
          f"(allow_time={allow_time}) ===", flush=True)

    for gi, g in enumerate(geoms):
        if g['p'] not in ch_cache:
            ch_cache[g['p']] = adaptive_channel(df, p=g['p'], mult=1.0)
        ch = ch_cache[g['p']]
        warmup = max(5 * g['p'], 250)
        P = prepare_fast(df, ch, None, asset, split_idx, g, warmup)
        if P is None:
            continue
        n_ev = len(P['sb'])
        bd, bh, ba = q_stats(P, np.ones(n_ev, bool))
        # --- غربالِ بودجهٔ N: اگر پایهٔ صف کوچک است، پس از فیلتر چیزی نمی‌ماند
        if ba['n'] < min_base_n:
            continue

        # ⭐ غربال روی **کلِ ۴۰۱ ابزار** (نه فهرستِ دستیِ ۱۱۲تایی) — قانونِ جعبه‌ابزار
        _, _, cands = screen401(P, card, man, allow_time=allow_time)
        if not cands:
            continue
        stack, hist, mask = stack_maxn(P, cands, wr_floor=wr_floor,
                                       pf_floor=pf_floor, verbose=False)
        sd, sh, sa = q_stats(P, mask)
        ok = (min(sd['wr'], sh['wr']) >= wr_floor and
              min(sd['pf'], sh['pf']) >= pf_floor and
              sd['n'] >= 30 and sh['n'] >= 20)
        row = dict(geom=g, base_n=ba['n'], base_wr=ba['wr'],
                   n_filters=len(stack), reached=bool(ok),
                   filters=[dict(col=f['col'], dir=f['dir'], thr=f['thr'])
                            for f in stack],
                   D=sd, H=sh, ALL=sa)
        rows.append(row)
        if ok and (best is None or sa['n'] > best['ALL']['n']):
            best = row
            print(f"  ★ NEW BEST n={sa['n']:5d} WR={sa['wr']:5.2f} PF={sa['pf']:.2f} "
                  f"| {g['mode']}/{g['side']} p={g['p']} m={g['mult']} "
                  f"sl={g['sl_k']} rr={g['rr']} h={g['hold']} | F={len(stack)}",
                  flush=True)
        # ⚠️ قانونِ «اندک اندک»: چون کلِ لیست ۲۴ هندسه است، checkpoint هر ۲۵ گام
        # هرگز اجرا نمی‌شد و در صورتِ ریستِ سندباکس تمامِ ساعت‌ها کار از دست می‌رفت.
        # پس بعد از **هر** هندسه ذخیره می‌کنیم.
        print(f"  ... {gi+1}/{len(geoms)} scanned, kept={len(rows)}, "
              f"last n={sa['n']} WR={sa['wr']:.2f} PF={sa['pf']:.2f} "
              f"reached={ok}", flush=True)
        _save(card, allow_time, rows, best)

    _save(card, allow_time, rows, best)
    rows_ok = [r for r in rows if r['reached']]
    rows_ok.sort(key=lambda r: -r['ALL']['n'])
    print(f">>> {card}: geoms_kept={len(rows)} reached={len(rows_ok)}", flush=True)
    for r in rows_ok[:top_report]:
        g = r['geom']
        print(f"   n={r['ALL']['n']:5d} WR={r['ALL']['wr']:5.2f} PF={r['ALL']['pf']:.2f} "
              f"exp={r['ALL']['exp']:6.2f} | D n={r['D']['n']:4d} WR={r['D']['wr']:5.2f} "
              f"| H n={r['H']['n']:4d} WR={r['H']['wr']:5.2f} | "
              f"{g['mode']}/{g['side']} p={g['p']} m={g['mult']} sl={g['sl_k']} "
              f"rr={g['rr']} h={g['hold']} F={r['n_filters']}", flush=True)
    return rows_ok


def _save(card, allow_time, rows, best):
    tag = 'notime' if not allow_time else 'time'
    with open(f"{OUT}/{card}_joint_{tag}.json", 'w') as f:
        json.dump(dict(card=card, allow_time=allow_time, rows=rows, best=best),
                  f, default=float)


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        args = ['XAUUSD-M15']
    for card in args:
        run_card(card)
