# -*- coding: utf-8 -*-
"""
S362 — گامِ ۳ث: **بخشِ همپوشان به‌عنوان فیلتر**. چهارمین و آخرین پروتکلِ بهبودِ
پیش‌ثبت‌شده در سندِ `S357` بندِ ۶. تنها پس از شکستِ این گام اعلامِ `DEAD` مجاز است.

────────────────────────────────────────────────────────────────────────────────
چرا آماره‌ها **import** می‌شوند و بازنویسی نمی‌شوند
────────────────────────────────────────────────────────────────────────────────
فازهای B و C از `s359_s341_reversion_filter` گرفته می‌شوند نه از نو نوشته. آن
توابع همان استانداردِ پیش‌ثبت‌شده را رمز کرده‌اند: تقسیمِ ۶۰/۴۰، دو مدلِ صفرِ
هم‌زمان‌الزامی (`SUBSET` هم‌انتخاب‌گر و `SHIFT` دوّارِ مشترک)، `p`ِ تجربیِ
جای‌گشتی که مستقل شمرده می‌شود، و معیارِ تعمیمِ فازِ C که روی **لیفت** سنجیده
می‌شود نه `WR`ِ خام. اگر همان منطق اینجا دوباره نوشته می‌شد، دو گامِ فیلترِ این
نشست با دو خط‌کشِ کمی متفاوت داوری می‌شدند و مقایسه‌شان در گزارشِ نهایی
بی‌معنا می‌شد.

پلی که این بازاستفاده را **دقیق** می‌کند: `S359.phase_b` ماسکش را با آستانه‌گذاری
روی یک سریِ پیوسته می‌سازد (`filter_mask(vals, thr, dirn)`). یک سریِ صفر/یک که در
آستانهٔ `0.5` و جهتِ `+1` آستانه‌گذاری شود، **عیناً** هر ماسکِ بولیِ دلبخواه را
بازتولید می‌کند، چون سری هیچ مقدارِ غیرمتناهی ندارد و نگهبانِ `isfinite` بی‌اثر
است. این یک **هم‌ریختیِ دقیق** است نه تقریب، و یک `assert` در زمانِ اجرا آن را
با بازسازیِ ماسک از مسیرِ خودِ تابعِ import‌شده تحقیق می‌کند؛ پس اگر روزی
کنوانسیونِ آستانه‌گذاری عوض شود، این هارنس **بلند** شکست می‌خورد و در سکوت چیزِ
دیگری اندازه نمی‌گیرد.

────────────────────────────────────────────────────────────────────────────────
قبضِ چندگانگی — عیناً از سندِ پیش‌ثبت، بندِ ۵
────────────────────────────────────────────────────────────────────────────────
    منبع (۶) × جهت (۲) × پنجره (۲) × θ (۴) = ۹۶ کاندیدا
    honest = 1 | conservative = 96 | stress = 96 × 4 = 384

`S359.phase_b` این سه عدد را از **گلوبال‌های ماژولِ S359** می‌خواند. پس آن‌ها پیش
از صدا زدن، به مقادیرِ S362 **موقتاً جایگزین** می‌شوند و بعد بازگردانده می‌شوند.
این جایگزینی صریح ثبت می‌شود چون در غیرِ این صورت قبضِ ۸۴ تاییِ S359 پرداخت
می‌شد که **کمتر** از بدهیِ واقعیِ این گام است.

نکتهٔ ضدتقلب: روی کارتی که همهٔ شش منبع در دسترس نیست، `N` **کاهش نمی‌یابد** —
همان ۹۶ می‌ماند. کم‌کردنِ `N` به‌بهانهٔ «منبعِ کمتر» همان «خریدنِ پاس» است که
بندِ ۷ سندِ `S357` ممنوع کرده.

────────────────────────────────────────────────────────────────────────────────
پنجرهٔ علّی
────────────────────────────────────────────────────────────────────────────────
`window_any(m, W)` می‌گوید آیا لایهٔ منبع در **کندلِ جاری یا `W-1` کندلِ قبل** فعال
بوده. با جمعِ تجمعی پیاده شده تا هزینه‌اش خطی باشد نه درجه‌دو، و **هیچ ارجاعِ
آینده‌نگرانه ندارد** ⇒ فیلتر در زمانِ واقعی قابلِ محاسبه می‌ماند.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import s357_s341_v24_rejudge as S357      # noqa: E402
from strategies import s358_s341_vote_ensemble as S358    # noqa: E402
from strategies import s359_s341_reversion_filter as S359  # noqa: E402
from strategies import s362_cocard_masks as MK            # noqa: E402

OUT = "results/_scan_S362"

SEEDS = S357.SEEDS                 # (23, 101, 777)
PERM_K = S357.PERM_K               # 2000
P_BAR = S358.P_BAR                 # 0.001 — شل نمی‌شود
SPLIT_FRAC = S359.SPLIT_FRAC       # 0.60
THETA_GRID = S359.THETA_GRID       # (4, 7, 11, 16) — عیناً از S358
N_IS_FLOOR = S359.N_IS_FLOOR       # 57
GEN_MIN_MEMBERS = S359.GEN_MIN_MEMBERS  # 44 از 72

# ── گریدِ پیش‌ثبت‌شده و **بسته** (بندِ ۵ سندِ S362) ───────────────────────────
SRC_ORDER = ('S326', 'S327', 'S333', 'S335', 'ANY_REVERSAL', 'ANY_TREND')
DIRECTIONS = ('CONFIRM', 'VETO')
WINDOWS = (3, 13)                  # اعدادِ غیررند — اشتباهِ رایجِ #۷

N_TRIALS_HONEST = 1
N_TRIALS_CONSERV = (len(SRC_ORDER) * len(DIRECTIONS)
                    * len(WINDOWS) * len(THETA_GRID))          # ۹۶
N_TRIALS_STRESS = N_TRIALS_CONSERV * 4                          # ۳۸۴


# ═══════════════════════ ۱. عملگرهای پایه ═══════════════════════
def window_any(mask, w):
    """آیا `mask` در `[i-w+1 … i]` جایی True بوده. علّی و خطی."""
    m = np.asarray(mask, bool).astype(np.int32)
    n = m.size
    cs = np.concatenate(([0], np.cumsum(m)))
    idx = np.arange(n)
    lo = np.maximum(0, idx - w + 1)
    return (cs[idx + 1] - cs[lo]) > 0


def keep_mask(src_mask, direction, w):
    """ماسکِ **نگه‌داشتن** برای یک (منبع، جهت، پنجره).

    `CONFIRM` ⇒ فقط کندل‌هایی که منبع در پنجره فعال بوده.
    `VETO`    ⇒ فقط کندل‌هایی که منبع در پنجره فعال **نبوده**.
    """
    a = window_any(src_mask, w)
    return a if direction == 'CONFIRM' else ~a


def synthetic_series(mask):
    """سریِ صفر/یکِ شناور — پلِ هم‌ریختِ بازاستفاده از `S359.filter_mask`."""
    return np.asarray(mask, bool).astype(float)


def assert_isomorphism(mask):
    """تحقیقِ عددیِ اینکه پل دقیق است، نه ادعای آن."""
    rebuilt = S359.filter_mask(synthetic_series(mask), 0.5, +1)
    if not np.array_equal(rebuilt, np.asarray(mask, bool)):
        raise AssertionError(
            'synthetic-series bridge broken: S359.filter_mask no longer '
            'reproduces a boolean mask at thr=0.5, dirn=+1')


# ═══════════════════ ۲. ممیزیِ همپوشانی — بندِ ۱ قانونِ پروژه ═══════════════════
def audit_card(card, verbose=True):
    """«با کدام لایه و **چند درصد**» — پیش‌شرطِ آزمونِ فیلتر.

    دو سنجه گزارش می‌شود چون معنایشان یکی نیست:
      * `share_of_s341` — چند درصدِ کندل‌های سیگنالِ S341 با منبع هم‌زمان‌اند.
        این همان عددی است که قانونِ همپوشانیِ پروژه می‌خواهد.
      * `jaccard` — تقارنِ کاملِ دو مجموعه. برای دیدنِ اینکه منبع چقدر
        **بزرگ‌تر** از S341 است (یک منبعِ پرشلیک می‌تواند ۱۰۰٪ پوشش بدهد و
        اطلاعِ صفر داشته باشد).
    """
    P = S359.prepare(card)
    if P is None:
        return dict(card=card, status='NO_DATA')
    df, F = P['df'], P['F']
    srcs, missing = MK.build_sources(df, card)
    n = len(df)
    lo = min(300, max(0, n // 10))
    rows = []
    for theta in THETA_GRID:
        ls, ss = S358.rule_signals(P['v']['long'], P['v']['short'], theta)
        sig = ls | ss
        sig[:lo] = False
        n_sig = int(sig.sum())
        for name in SRC_ORDER:
            if name not in srcs:
                continue
            for w in WINDOWS:
                a = window_any(srcs[name], w)
                inter = int((sig & a).sum())
                union = int((sig | a).sum())
                rows.append(dict(
                    theta=theta, source=name, family=MK.FAMILY.get(name, 'combo'),
                    window=w, n_s341=n_sig, n_source=int(a.sum()),
                    n_intersect=inter,
                    share_of_s341=round(100.0 * inter / n_sig, 3) if n_sig else None,
                    jaccard=round(100.0 * inter / union, 3) if union else None))
    if verbose:
        print(f"\n=== {card} OVERLAP AUDIT :: bars={n} missing={missing or 'none'}",
              flush=True)
        for r in rows:
            if r['theta'] == THETA_GRID[0]:
                print(f"    θ={r['theta']:2d} {r['source']:<13s}"
                      f"({r['family'][:4]}) W={r['window']:2d} "
                      f"n_s341={r['n_s341']:5d} share={r['share_of_s341']}% "
                      f"jaccard={r['jaccard']}%", flush=True)
    return dict(card=card, status='AUDITED', bars=n, missing=missing,
                sources_available=[k for k in SRC_ORDER if k in srcs], rows=rows)


# ═══════════════════ ۳. فازِ A — جست‌وجوی درون‌نمونه‌ای ═══════════════════
def phase_a_overlap(df, F, v, tables, cut, card, verbose=True):
    """۹۶ کاندیدا روی `bars[lo : 0.60n]`. رتبه‌بندی با `z`ِ دوجمله‌ای.

    چرا `z` و نه لیفتِ خام: فیلتر با کوچک‌کردنِ `n` واریانس را بالا می‌برد، و
    لیفتِ خام همیشه تهاجمی‌ترین فیلتر را تاج‌گذاری می‌کند. `z` این تورّم را با
    تقسیم بر `sqrt(p(1-p)/n)` **درست** جریمه می‌کند. این فقط ابزارِ رتبه‌بندیِ
    ارزانِ فازِ A است؛ حکم با جای‌گشتِ فازِ B صادر می‌شود.
    """
    srcs, missing = MK.build_sources(df, card)
    lo = min(300, max(0, len(df) // 10))
    base = {}
    for theta in THETA_GRID:
        ls, ss = S358.rule_signals(v['long'], v['short'], theta)
        wr0, n0, _, _ = S359.wr_on(ls, ss, tables, lo=lo, hi=cut)
        base[theta] = dict(wr=wr0, n=n0, sig=(ls, ss))
        if verbose:
            print(f"  [A] θ={theta:2d} baseline IS: n={n0} WR="
                  f"{'--' if wr0 is None else f'{wr0:.2f}%'}", flush=True)

    cands, cache, n_eval = [], {}, 0
    for name in SRC_ORDER:
        if name not in srcs:
            continue
        for direction in DIRECTIONS:
            for w in WINDOWS:
                km = keep_mask(srcs[name], direction, w)
                assert_isomorphism(km)
                key = (f'{name}_{direction}', w)
                cache[key] = synthetic_series(km)
                for theta in THETA_GRID:
                    n_eval += 1
                    b = base[theta]
                    if b['wr'] is None or b['n'] < N_IS_FLOOR:
                        continue
                    ls, ss = b['sig']
                    wr1, n1, _, _ = S359.wr_on(ls & km, ss & km, tables,
                                               lo=lo, hi=cut)
                    if wr1 is None or n1 < N_IS_FLOOR:
                        continue
                    p0 = b['wr'] / 100.0
                    sd = 100.0 * (p0 * (1.0 - p0) / n1) ** 0.5
                    lift = wr1 - b['wr']
                    cands.append(dict(
                        name=key[0], p=w, source=name, direction=direction,
                        window=w, family=MK.FAMILY.get(name, 'combo'),
                        dirn=+1, q=None, thr=0.5, theta=theta, n_is=n1,
                        wr_is=round(wr1, 3), wr_base_is=round(b['wr'], 3),
                        n_base_is=b['n'], keep_frac=round(n1 / b['n'], 4),
                        lift_is=round(lift, 3),
                        z_binom=round(lift / sd, 3) if sd > 0 else None))
    cands.sort(key=lambda d: -(d['z_binom'] if d['z_binom'] is not None else -99))
    if verbose:
        print(f"  [A] evaluated={n_eval} of billed {N_TRIALS_CONSERV} | "
              f"{len(cands)} admissible (floor n_is ≥ {N_IS_FLOOR}) | "
              f"missing sources={missing or 'none'}; top 6 by binomial z:",
              flush=True)
        for c in cands[:6]:
            print(f"      {c['source']:<13s} {c['direction']:<7s} W={c['window']:2d} "
                  f"θ={c['theta']:2d} n={c['n_is']:5d} keep={c['keep_frac']:.3f} "
                  f"WR {c['wr_base_is']:.2f}→{c['wr_is']:.2f} "
                  f"lift={c['lift_is']:+.2f}pp z={c['z_binom']}", flush=True)
    return cands, cache, missing, n_eval


# ═══════════════════ ۴. اجرا برای یک کارت ═══════════════════
def _patched_bill():
    """قبضِ S362 را به گلوبال‌های S359 تحمیل می‌کند و مقادیرِ قبلی را برمی‌گرداند."""
    old = (S359.N_TRIALS_HONEST, S359.N_TRIALS_CONSERV, S359.N_TRIALS_STRESS)
    S359.N_TRIALS_HONEST = N_TRIALS_HONEST
    S359.N_TRIALS_CONSERV = N_TRIALS_CONSERV
    S359.N_TRIALS_STRESS = N_TRIALS_STRESS
    return old


def _restore_bill(old):
    (S359.N_TRIALS_HONEST, S359.N_TRIALS_CONSERV, S359.N_TRIALS_STRESS) = old


def run_card(card, k_perm=PERM_K, verbose=True):
    P = S359.prepare(card)
    if P is None:
        return dict(card=card, status='NO_DATA', step='3th',
                    note=f'data/{card.replace("-", "_")}.csv does not exist')
    if verbose:
        print(f"\n=== {card} :: bars={len(P['df'])} cut60={P['cut']} "
              f"bracket={P['source']} SL={P['cfg']['sl']} TP={P['cfg']['tp']} "
              f"mh={P['cfg']['mh']}", flush=True)
    cands, cache, missing, n_eval = phase_a_overlap(
        P['df'], P['F'], P['v'], P['tables'], P['cut'], card, verbose=verbose)
    if not cands:
        return dict(card=card, status='NO_CANDIDATE', step='3th',
                    missing_sources=missing, phase_a_evaluated=n_eval,
                    note=f'no overlap filter reached the in-sample floor of '
                         f'{N_IS_FLOOR} trades')
    top = dict(cands[0])
    top.update(sl=P['cfg']['sl'], tp=P['cfg']['tp'], mh=P['cfg']['mh'])
    old = _patched_bill()
    try:
        rec = S359.phase_b(card, P['df'], P['asset'], P['F'], P['fracs'],
                           P['v'], P['tables'], P['cut'], top, cache,
                           k_perm=k_perm, verbose=verbose, run_gen=True)
    finally:
        _restore_bill(old)
    rec['step'] = '3th'
    rec['protocol'] = 'OVERLAP_AS_FILTER'
    rec['missing_sources'] = missing
    rec['phase_a_evaluated'] = n_eval
    rec['phase_a_candidates'] = len(cands)
    rec['phase_a_top10'] = cands[:10]
    rec['multiplicity_bill'] = dict(honest=N_TRIALS_HONEST,
                                    conservative=N_TRIALS_CONSERV,
                                    stress=N_TRIALS_STRESS)
    if rec.get('decision') == 'DEAD_UNDER_FILTER':
        rec['decision'] = 'DEAD_UNDER_OVERLAP_FILTER'
    elif rec.get('decision') == 'ALIVE_UNDER_FILTER':
        rec['decision'] = 'ALIVE_UNDER_OVERLAP_FILTER'
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='search', choices=('audit', 'search'))
    ap.add_argument('--cards', default=None)
    ap.add_argument('--k', type=int, default=PERM_K)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if a.mode == 'audit':
        cards = ([c.strip() for c in a.cards.split(',') if c.strip()]
                 if a.cards else S357.CARDS_ALL)
        for card in cards:
            rec = audit_card(card)
            with open(os.path.join(OUT, f'audit_{card}.json'), 'w',
                      encoding='utf-8') as f:
                json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
            print(f"  [saved] {OUT}/audit_{card}.json status={rec['status']}",
                  flush=True)
        return

    cards = ([c.strip() for c in a.cards.split(',') if c.strip()]
             if a.cards else S357.SITE_CARDS)
    for card in cards:
        rec = run_card(card, k_perm=a.k)
        with open(os.path.join(OUT, f'{card}.json'), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
        print(f"  [saved] {OUT}/{card}.json status={rec.get('status')} "
              f"decision={rec.get('decision')}", flush=True)


if __name__ == '__main__':
    main()
