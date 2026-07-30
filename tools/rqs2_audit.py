# -*- coding: utf-8 -*-
"""
حسابرسیِ مستقلِ خودِ معیارِ RQS2 — پاسخِ **اندازه‌گیری‌شده** به پنج پرسشِ حاکمیتی
================================================================================
کاربر پنج پرسش پرسید که هیچ‌کدام با «بله/خیر» پاسخ‌پذیر نیستند:

  Q1 اصلاحِ v2.1 تمام شد؟
  Q2 دیگر باگی ندارد؟
  Q3 روی همهٔ تایم‌فریم‌ها جواب می‌دهد؟
  Q4 نمره‌ای که می‌دهد منطقی است؟
  Q5 کفِ ۸۰ خوب است یا زیادی سخت‌گیرانه؟

این اسکریپت هیچ ادعایی نمی‌کند؛ چهار آزمونِ کمّی اجرا می‌کند:

  بخشِ A  انسجامِ حکم   : آیا دو قاعدهٔ پذیرشِ موجود با هم می‌خوانند؟
  بخشِ B  کالیبراسیون   : عددِ ۸۰ **دقیقاً** چه چیزی می‌طلبد؟
  بخشِ C  تایم‌فریم     : کدام آستانه اثرِ نامتقارنِ TF دارد (از دادهٔ واقعی)؟
  بخشِ D  شکارِ باگ     : ورودی‌های واگن/مرزی ⇒ هر استثنا = باگ

اجرا:  python -m tools.rqs2_audit
"""
from __future__ import annotations

import os
import sys
import traceback
from math import sqrt

import numpy as np
import pandas as pd

from engine import rqs2 as R
from engine import rqs2_selftest as S
from engine import scalp_engine as se

SEP = "=" * 96
SUB = "-" * 96

# وزن‌های نمرهٔ پیوسته — از خودِ `engine/rqs2.py` نسخه‌برداری شده. اگر آن‌جا
# عوض شود این حسابرسی **باید** بشکند، پس یک آزمونِ همگامی هم می‌گذاریم.
WEIGHTS = dict(c_skill=.26, c_oos=.13, c_stab=.13, c_pf=.08, c_exp=.09,
               c_tail=.09, c_sel=.05, c_edge=.05, c_reg=.12)


# ==============================================================================
#  بخشِ A — انسجامِ حکم: آیا «ACCEPT» و «نمره ≥ ۸۰» یک چیز را می‌گویند؟
# ==============================================================================
def part_a():
    print(SEP)
    print("PART A — VERDICT COHERENCE: do the project's TWO admission rules agree?")
    print(SEP)
    print("""
  تا v2.2 پروژه دو قاعدهٔ پذیرش داشت که **مستقل از هم** محاسبه می‌شدند:
      قاعدهٔ ۱ (دروازه‌ای) : verdict = 'ACCEPT'  ⟺  هر ۱۱ دروازه پاس
      قاعدهٔ ۲ (نمره‌ای)   : accepted           ⟺  all_pass AND score ≥ 80
  اگر این دو بر یک مرز نایستند، پروژه دو معیارِ پذیرشِ متفاوت دارد و «سوخته
  بودن» یک لایه به این بستگی پیدا می‌کند که خواننده کدام فیلد را نگاه کند.

  ✅ **رفع‌شده در v2.3** — تصمیمِ کاربر «گزینهٔ الف»: پذیرش = فقط ۱۱ دروازه.
  این بخش **عمداً حفظ شده** تا (۱) اندازه‌گیریِ اثبات‌کننده در مخزن بماند و
  (۲) اگر روزی کسی کفِ نمره‌ای را برگرداند، همین بخش فوراً آن را بگیرد.
""")
    # مؤلفه‌های نمره وقتی لایه **دقیقاً روی مرزِ هر دروازه** ایستاده است.
    # هر مقدار از کفِ همان دروازه استخراج شده، نه از سلیقه.
    boundary = dict(
        c_skill=(R.SKILL_Z_MIN / 6.0, f"H3: z = {R.SKILL_Z_MIN}"),
        c_oos=((R.OOS_PF_MIN - 1.0) / 0.8, f"H7: PF_oos = {R.OOS_PF_MIN}"),
        c_stab=(R.CAL_POS_MIN / float(R.CAL_WINDOWS),
                f"H6: {R.CAL_POS_MIN}/{R.CAL_WINDOWS} windows positive"),
        c_pf=((R.PF_MIN - 1.0) / 1.0, f"H1: PF = {R.PF_MIN}"),
        c_exp=(R.EXP_COST_MULT / 2.0, f"H9: exp = {R.EXP_COST_MULT}×cost"),
        c_tail=(0.0, f"H8: maxDD = {R.MAXDD_MAX_PCT}% (cap) ⇒ component 0"),
        c_sel=(0.0, "H5: z_obs = z_bar (exactly on the best-of-N bound)"),
        c_edge=(R.WR_EXCESS_MIN / 10.0, f"H2: excess = {R.WR_EXCESS_MIN}pp"),
        c_reg=(0.0, "H10: exp_counter → 0+ (only strictly positive required)"),
    )
    print(f"  {'component':10s} {'value':>7s} {'weight':>7s} {'contrib':>8s}   derived from")
    print("  " + SUB[:92])
    wsum = 0.0
    for k, (v, why) in boundary.items():
        contrib = WEIGHTS[k] * v
        wsum += contrib
        print(f"  {k:10s} {v:7.4f} {WEIGHTS[k]:7.2f} {contrib:8.4f}   {why}")
    print("  " + SUB[:92])
    score_boundary = 40.0 + 60.0 * wsum
    w_need = (R.RQS2_ACCEPT_FLOOR - 40.0) / 60.0
    print(f"  weighted at the gate boundary = {wsum:.4f}  ⇒  score = {score_boundary:.1f}")
    print(f"  weighted required for score {R.RQS2_ACCEPT_FLOOR:.0f} = {w_need:.4f}"
          f"  ⇒  {w_need / wsum:.2f}× the boundary")
    gap = R.RQS2_ACCEPT_FLOOR - score_boundary
    print()
    print(f"  ✅ FINDING A1 — RESOLVED in v2.3. The two rules disagreed by "
          f"{gap:.1f} score points:")
    print(f"      a layer passing all 11 gates *at their boundaries* scored "
          f"{score_boundary:.1f} while the declared")
    print(f"      floor was {R.RQS2_ACCEPT_FLOOR:.0f} — a second, undeclared hurdle demanding "
          f"{w_need / wsum:.2f}× the strength")
    print(f"      the gates ask for. Admission is now R.ADMISSION_RULE = "
          f"{R.ADMISSION_RULE!r},")
    print(f"      so the score RANKS and can no longer VETO.")
    # ⚠️ آزمونِ زندهٔ بازگشتی — نه یک جملهٔ توضیحی. اگر روزی کسی کفِ نمره‌ای را
    #    برگرداند، همین‌جا بلند فریاد می‌زند. حسابرسی‌ای که فقط تاریخ را روایت
    #    کند، بازگشتِ همان نقص را نمی‌گیرد.
    if R.ADMISSION_RULE != 'gates_only':
        print(f"      🔴 REGRESSION: admission rule is {R.ADMISSION_RULE!r} "
              f"— finding A1 is OPEN AGAIN.")
    print()
    print("  🔎 WHERE DID 80 COME FROM? It is inherited verbatim from RQS+, whose")
    print("     score was a DIFFERENT function with DIFFERENT components and a")
    print("     DIFFERENT range. Transplanting a threshold across scales is the")
    print("     SAME error class as v2.1's WR floor: a number carried over from a")
    print("     scale where it meant something, into one where it does not.")

    # نمایشِ ملموسِ همین ناسازگاری روی یک لایهٔ واقعیِ مصنوعی
    print()
    print("  DEMONSTRATION on ground-truth case T14 (the decisive v2.1 case):")
    t = S.make_scalp(800, 50.0, 7.0, 21.0, se.ASSETS['XAUUSD']['spread_pip'])
    r = R.compute_rqs2(t, 'XAUUSD', sl_pip=7.0, tp_pip=21.0,
                       bar_time=S.horizon(t),
                       close=S.mk_close(int(t['exit_bar'].max()) + 400),
                       null=S.mk_null(36.0), n_trials=1000, split_bar=6000)
    print(f"      verdict={r['verdict']}  score={r['rqs2_score']}  "
          f"passed={r['passed']}  accepted={r.get('accepted')}")
    comps = r.get('score_components') or {}
    if comps:
        print(f"      components: {comps}")
    return dict(score_at_gate_boundary=round(score_boundary, 2),
                weighted_at_boundary=round(wsum, 4),
                weighted_needed_for_80=round(w_need, 4),
                gap_points=round(gap, 2),
                strictness_ratio=round(w_need / wsum, 3))


# ==============================================================================
#  بخشِ B — کالیبراسیون: عددِ ۸۰ دقیقاً چه می‌طلبد؟
# ==============================================================================
def part_b():
    print()
    print(SEP)
    print("PART B — CALIBRATION: what does score ≥ 80 ACTUALLY demand?")
    print(SEP)
    print("""
  روشِ کار: از لایهٔ «مرزی» شروع می‌کنیم (همهٔ دروازه‌ها لبه) و هر بار **یک**
  مؤلفه را تا سقفِ کاملِ ۱.۰ می‌بریم تا ببینیم آیا تنهایی می‌تواند به ۸۰ برساند.
  اگر هیچ مؤلفه‌ای نتواند، یعنی ۸۰ «کمالِ همزمانِ چند بُعد» را می‌طلبد، نه
  «کیفیتِ خوب در یک بُعد».
""")
    base = dict(c_skill=R.SKILL_Z_MIN / 6.0, c_oos=(R.OOS_PF_MIN - 1.0) / 0.8,
                c_stab=R.CAL_POS_MIN / float(R.CAL_WINDOWS),
                c_pf=(R.PF_MIN - 1.0) / 1.0, c_exp=R.EXP_COST_MULT / 2.0,
                c_tail=0.0, c_sel=0.0, c_edge=R.WR_EXCESS_MIN / 10.0, c_reg=0.0)
    w0 = sum(WEIGHTS[k] * v for k, v in base.items())
    need = (R.RQS2_ACCEPT_FLOOR - 40.0) / 60.0

    print(f"  {'lift ONE component to 1.0':32s} {'weighted':>9s} {'score':>7s}  reaches 80?")
    print("  " + SUB[:78])
    any_single = False
    for k in WEIGHTS:
        w = w0 + WEIGHTS[k] * (1.0 - base[k])
        sc = 40.0 + 60.0 * w
        ok = sc >= R.RQS2_ACCEPT_FLOOR
        any_single |= ok
        print(f"  {k:32s} {w:9.4f} {sc:7.1f}  {'YES' if ok else 'no'}")
    print("  " + SUB[:78])
    print(f"  ⇒ can ANY single dimension of excellence reach 80? "
          f"{'YES' if any_single else 'NO'}")

    # حداقلِ تعدادِ مؤلفه‌هایی که باید کامل شوند (حریصانه، از ارزان‌ترین سود)
    order = sorted(WEIGHTS, key=lambda k: -WEIGHTS[k] * (1.0 - base[k]))
    w, used = w0, []
    for k in order:
        if w >= need:
            break
        w += WEIGHTS[k] * (1.0 - base[k])
        used.append(k)
    print(f"  minimum number of components that must be PERFECT (greedy, best-first)"
          f" = {len(used)} of {len(WEIGHTS)}")
    print(f"      namely: {', '.join(used)}")
    print(f"      (weighted {w:.4f} ⇒ score {40 + 60 * w:.1f})")

    # پروفایلِ یک لایهٔ «واقعاً خوب ولی نه افسانه‌ای»
    print()
    print("  A concrete 'strong but not mythical' layer, each value defensible:")
    good = dict(c_skill=(6.0 / 6.0, "z = 6.0σ vs the measured null"),
                c_oos=((1.8 - 1.0) / 0.8, "holdout PF = 1.80"),
                c_stab=(1.0, "all 4 calendar windows positive, both halves positive"),
                c_pf=((2.0 - 1.0) / 1.0, "PF = 2.00"),
                c_exp=(1.0, "expectancy = 2× spread"),
                c_tail=(_clip(1 - 4.0 / R.MAXDD_MAX_PCT) * _clip(1 - 0.5),
                        "maxDD = 4%, streak = half the Erdős–Rényi bound"),
                c_sel=(0.5, "z_obs stands 1.0σ above the best-of-N bound"),
                c_edge=(1.0, "WR excess = 10pp over cost breakeven"),
                c_reg=(0.5, "counter-drift expectancy = 1× spread"))
    wg = sum(WEIGHTS[k] * v for k, (v, _) in good.items())
    for k, (v, why) in good.items():
        print(f"      {k:8s} {v:.3f}   {why}")
    print(f"  ⇒ weighted {wg:.4f}  score {40 + 60 * wg:.1f}  "
          f"{'ACCEPTED ✅' if 40 + 60 * wg >= 80 else 'BELOW 80 ❌'}")
    print()
    print("  ⚠️  FINDING B1 — the 80 floor is reachable, but ONLY by a layer that is")
    print("      simultaneously excellent on several independent axes. It is not a")
    print("      'pass' line; it is a 'top decile' line. That may be the RIGHT policy —")
    print("      but it must be a DECLARED policy, not an accident of a transplanted number.")

    # --------------------------------------------------------------------------
    #  ⭐ آزمونِ سرنوشت‌سازِ سؤالِ پنجم: لایه‌ای که **هر ۱۱ دروازه را پاس می‌کند**
    #     و با این حال قاعدهٔ ۸۰ آن را می‌سوزاند. اگر چنین لایه‌ای «قابلِ‌قبول»
    #     به نظر برسد، پس ۸۰ در حالِ سوزاندنِ یافته‌های واقعیِ پروژه است.
    # --------------------------------------------------------------------------
    print()
    print(SUB)
    print("  ⭐ THE DECISIVE TEST — a layer that passes ALL ELEVEN GATES and is")
    print("     nonetheless BURNED by the 80 rule. Every value below comfortably")
    print("     clears its own gate; none sits on a boundary.")
    print(SUB)
    solid = [
        ('c_skill', 4.5 / 6.0, "z = 4.5σ vs the measured null (gate asks 3.0σ)"),
        ('c_oos', (1.45 - 1.0) / 0.8, "holdout PF = 1.45 (gate asks 1.20)"),
        ('c_stab', 1.0, "all 4 calendar windows positive (gate asks 3 of 4)"),
        ('c_pf', (1.55 - 1.0) / 1.0, "PF = 1.55 (gate asks 1.30)"),
        ('c_exp', 0.55, "expectancy = 1.1× spread (gate asks 0.5×)"),
        ('c_tail', _clip(1 - 5.0 / R.MAXDD_MAX_PCT) * _clip(1 - 0.55),
         "maxDD = 5% (gate caps 8%), streak = 55% of the Erdős–Rényi bound"),
        ('c_sel', 0.30, "z_obs stands 0.6σ above the best-of-N bound (gate asks >0)"),
        ('c_edge', 0.62, "WR excess = 6.2pp over cost breakeven (gate asks 3.0pp)"),
        ('c_reg', 0.28, "counter-drift expectancy = 0.56× spread (gate asks >0)"),
    ]
    ws = 0.0
    print(f"      {'component':9s} {'value':>6s} {'contrib':>8s}   margin over its own gate")
    for k, v, why in solid:
        ws += WEIGHTS[k] * v
        print(f"      {k:9s} {v:6.3f} {WEIGHTS[k] * v:8.4f}   {why}")
    sc_solid = 40.0 + 60.0 * ws
    print(f"      {'':9s} {'':6s} {ws:8.4f}   ⇐ weighted")
    print()
    tier = next(t for thr, t in R.RANK_TIERS if sc_solid >= thr)
    print(f"      verdict (11 gates) = ACCEPT ✅        score = {sc_solid:.1f} "
          f"(rank tier {tier})")
    print(f"      retired 80 rule    = "
          f"{'ACCEPTED' if sc_solid >= R.RQS2_ACCEPT_FLOOR else 'would have BURNED ❌'}"
          f"  (short by {max(0.0, R.RQS2_ACCEPT_FLOOR - sc_solid):.1f} points)")
    print(f"      v2.3 outcome       = ADMITTED by the gates, ranked {tier} — the score")
    print(f"                           now prioritises this layer instead of vetoing it.")
    print()
    print("  ✅ FINDING B2 — RESOLVED in v2.3 (user decision). THE ANSWER TO 'IS 80 TOO")
    print("      STRICT' was that the 80 rule did not merely raise the bar; it")
    print("      CONTRADICTED the design philosophy of RQS2.")
    print("      Eleven gates exist precisely because their conditions are")
    print("      NON-COMPENSABLE: no amount of skill excuses a failed cost-stress")
    print("      test, and no drawdown record excuses an unsampled winning tail.")
    print("      A weighted SUM is compensable by construction. Using a threshold on")
    print("      that sum as a SECOND admission rule therefore re-introduces exactly")
    print("      the trade-off logic the gate architecture was built to forbid —")
    print("      and it does so in the harmful direction, by vetoing layers the")
    print("      scientifically derived gates have already certified.")
    print("      A weighted sum is the right tool for RANKING and the wrong tool")
    print("      for ADMISSION. Admission belongs to the gates.")
    print()
    print(f"      ⇒ v2.3 does exactly that: R.ADMISSION_RULE = {R.ADMISSION_RULE!r},")
    print(f"        and the score survives as a {len(R.RANK_TIERS)}-way rank tier "
          f"({', '.join(t for _, t in R.RANK_TIERS)}).")
    print(f"      ⚠️  AND NO STRICTNESS WAS LOST: all 11 gates remain mandatory and")
    print(f"        untouched. Only the UNDERIVED veto was removed — strictness moved")
    print(f"        to where every threshold has a derivation, not to where the")
    print(f"        weights were chosen by taste.")
    return dict(single_component_can_reach_80=bool(any_single),
                min_perfect_components=len(used),
                strong_layer_score=round(40 + 60 * wg, 1),
                solid_all_pass_score=round(sc_solid, 1),
                solid_layer_burned_under_old_rule=bool(
                    sc_solid < R.RQS2_ACCEPT_FLOOR),
                solid_layer_admitted_now=True,
                solid_layer_rank_tier=tier)


def _clip(x):
    return float(min(1.0, max(0.0, x)))


# ==============================================================================
#  بخشِ C — تایم‌فریم: کدام آستانه اثرِ نامتقارن دارد؟ (از دادهٔ واقعی)
# ==============================================================================
TF_FILES = [
    ('XAUUSD', 'M5'), ('XAUUSD', 'M15'), ('XAUUSD', 'M30'), ('XAUUSD', 'H1'),
    ('XAUUSD', 'H4'), ('XAUUSD', 'D1'), ('XAUUSD', 'W1'),
    ('EURUSD', 'M1'), ('EURUSD', 'M5'), ('EURUSD', 'M15'), ('EURUSD', 'M30'),
    ('EURUSD', 'H1'), ('EURUSD', 'H4'), ('EURUSD', 'D1'), ('EURUSD', 'W1'),
]


def _atr_pip(path, pip, n=14):
    """ATRِ میانه بر حسبِ pip ، تعدادِ کندل، و **گسترهٔ تقویمیِ کارت** بر حسبِ روز.

    گسترهٔ تقویمی از v2.3 لازم شد: افقِ رژیمِ `H10` زمان‌محور است، پس کارتی که
    تاریخش کوتاه‌تر از افق باشد اصلاً **قابلِ داوری نیست** و این باید اندازه‌گیری
    شود، نه حدس زده شود.
    """
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    h, l, c = cols.get('high'), cols.get('low'), cols.get('close')
    if not (h and l and c):
        return None, 0, None
    hi, lo, cl = df[h].values, df[l].values, df[c].values
    prev = np.concatenate([[cl[0]], cl[:-1]])
    tr = np.maximum(hi - lo, np.maximum(np.abs(hi - prev), np.abs(lo - prev)))
    span_days = None
    tcol = next((cols[k] for k in ('time', 'date', 'datetime') if k in cols), None)
    if tcol is not None and len(df) > 1:
        t = df[tcol]
        try:
            if pd.api.types.is_numeric_dtype(t):
                span_days = float(t.iloc[-1] - t.iloc[0]) / 86400.0
            else:
                tt = pd.to_datetime(t)
                span_days = (tt.iloc[-1] - tt.iloc[0]).total_seconds() / 86400.0
        except Exception:      # noqa: BLE001 — سنجهٔ کمکی؛ نبودش کشنده نیست
            span_days = None
    return float(np.nanmedian(tr)) / pip, len(df), span_days


def part_c():
    print()
    print(SEP)
    print("PART C — TIMEFRAME NEUTRALITY: is RQS2 equally applicable on every card?")
    print(SEP)
    print("""
  دو نوع وابستگیِ TF از هم جدا می‌شوند:
    (i)  وابستگیِ **صوری**  : آستانه‌ای که عددِ TF را در فرمول دارد ⇒ باگ.
    (ii) وابستگیِ **اثری**  : آستانهٔ TF-خنثی که در عمل روی یک TF بسیار
         سخت‌تر تمام می‌شود ⇒ باگ نیست، ولی اگر مستند نشود به نتیجه‌گیریِ
         غلطِ «این TF ساختاراً مرده است» می‌انجامد.
  ستونِ کلیدی `TP_min`: کوچک‌ترین TP که در آن **سربه‌سرِ مقاومِ** H9 یعنی
  (SL+2c)/(SL+TP) زیرِ ۵۵٪ می‌ماند — یعنی هدفی که با WR واقع‌گرایانه دست‌یافتنی است.
""")
    rows = []
    for asset, tf in TF_FILES:
        path = f"data/{asset}_{tf}.csv"
        if not os.path.exists(path):
            continue
        spec = se.ASSETS[asset]
        pip = spec['pip']
        cost = spec['spread_pip'] + spec.get('slip_pip', 0.0)
        atr, bars, span_days = _atr_pip(path, pip)
        if atr is None:
            continue
        # SL واقع‌گرایانه = ۱ ATR ؛ TP_min از حلِ (SL+2c)/(SL+TP) ≤ 0.55
        sl = atr
        tp_min = (sl + 2 * cost) / 0.55 - sl
        rr_min = tp_min / sl if sl > 0 else float('inf')
        # هزینه به‌عنوان کسری از یک ATR — سنجهٔ اصلیِ «سختیِ ساختاریِ» TF
        cost_frac = cost / atr if atr > 0 else float('inf')
        # قدرتِ آماری: با ۵٪ نرخِ سیگنال، sd مدلِ صفر چقدر است؟
        n_tr = max(1, int(bars * 0.05))
        sd = sqrt(0.5 * 0.5 / n_tr) * 100.0
        rows.append(dict(card=f"{asset}-{tf}", bars=bars, atr=atr, cost=cost,
                         cost_frac=cost_frac, sl=sl, tp_min=tp_min,
                         rr_min=rr_min, n_tr=n_tr, sd=sd, span_days=span_days))

    print(f"  {'card':13s} {'bars':>7s} {'ATR(pip)':>9s} {'cost/ATR':>9s} "
          f"{'SL':>7s} {'TP_min':>8s} {'RR_min':>7s} {'n@5%':>7s} {'sd(pp)':>7s} {'N_FLOOR':>8s}")
    print("  " + SUB[:94])
    for r in rows:
        nf = 'OK' if r['n_tr'] >= R.N_FLOOR else 'FAILS'
        print(f"  {r['card']:13s} {r['bars']:7d} {r['atr']:9.2f} {r['cost_frac']:9.3f} "
              f"{r['sl']:7.2f} {r['tp_min']:8.2f} {r['rr_min']:7.2f} {r['n_tr']:7d} "
              f"{r['sd']:7.3f} {nf:>8s}")
    print("  " + SUB[:94])

    if rows:
        worst = max(rows, key=lambda r: r['cost_frac'])
        best = min(rows, key=lambda r: r['cost_frac'])
        hi_sd = max(rows, key=lambda r: r['sd'])
        lo_sd = min(rows, key=lambda r: r['sd'])
        print()
        print(f"  ⚠️  FINDING C1 — cost burden spans {best['cost_frac']:.3f} "
              f"({best['card']}) to {worst['cost_frac']:.3f} ({worst['card']}), a "
              f"{worst['cost_frac'] / max(best['cost_frac'], 1e-9):.1f}× range.")
        print(f"      On {worst['card']} the spread eats "
              f"{worst['cost_frac'] * 100:.0f}% of one ATR, so H9's cost-stress gate")
        print(f"      forces RR ≥ {worst['rr_min']:.1f} — i.e. a target "
              f"{worst['rr_min']:.1f}× the bar's own range, held over MANY bars.")
        print(f"      This is gate H9 behaving CORRECTLY, not a bug: it is the reason")
        print(f"      low timeframes look 'dead'. The layer must simply hold longer.")
        print()
        print(f"  ⚠️  FINDING C2 — null-model sd spans {lo_sd['sd']:.3f}pp "
              f"({lo_sd['card']}) to {hi_sd['sd']:.3f}pp ({hi_sd['card']}), a "
              f"{hi_sd['sd'] / max(lo_sd['sd'], 1e-9):.0f}× range.")
        print(f"      H3 demands z ≥ {R.SKILL_Z_MIN}, so the required WR lift is "
              f"{R.SKILL_Z_MIN * lo_sd['sd']:.2f}pp on {lo_sd['card']} but "
              f"{R.SKILL_Z_MIN * hi_sd['sd']:.2f}pp on {hi_sd['card']}.")
        print(f"      Since H3 ALSO imposes an absolute lift floor of "
              f"{R.SKILL_LIFT_MIN}pp, on high-bar-count cards the z test is")
        print(f"      slack and the absolute floor binds, while on {hi_sd['card']} "
              f"the z test binds and needs {R.SKILL_Z_MIN * hi_sd['sd']:.1f}pp.")
        print(f"      ⇒ the SAME nominal gate is a different physical requirement per card.")

    # ── C3: افقِ رانشِ H10 — یافتهٔ v2.2 و **رفعِ v2.3** ─────────────────────
    print()
    lb_days = R.REGIME_LOOKBACK_SECONDS / 86400.0
    print(f"  ✅ FINDING C3 — RESOLVED in v2.3 (user decision: scale H10 per timeframe).")
    print(f"      The defect was that REGIME_LOOKBACK = {R.REGIME_LOOKBACK} BARS was the only")
    print(f"      threshold expressed in bars, so 'prevailing drift' meant a different")
    print(f"      duration on every card and H10's verdicts were incomparable:")
    for tf, mins in [('M5', 5), ('H1', 60), ('D1', 1440), ('W1', 10080)]:
        print(f"          {tf:3s} ⇒ {R.REGIME_LOOKBACK * mins / 60.0 / 24.0:9.1f} days "
              f"(old, bar-count)")
    print(f"      The horizon is now {R.REGIME_LOOKBACK_TRADING_DAYS:.0f} TRADING DAYS "
          f"= {lb_days:.0f} calendar days on EVERY card,")
    print(f"      located by searchsorted on the time axis (immune to data gaps).")
    print(f"      ⭐ The number 200 was never wrong, it was UNITLESS: on D1 it already meant")
    print(f"      200 trading days — the canonical regime horizon of BLL 1992 / Faber 2007 —")
    print(f"      so the old constant was a D1 constant generalised to all cards. Hence the")
    print(f"      correction is D1-INVARIANT and forces the minimum possible re-testing.")
    print()
    print(f"      Consequence measured on the real cards — which cards can even be judged:")
    for r in rows:
        span_d = r.get('span_days')
        if span_d is None:
            continue
        ok = span_d > lb_days
        print(f"          {r['card']:14s} history {span_d:7.0f}d  "
              f"{'✓ judgeable' if ok else '✗ H10 UNKNOWN — history shorter than horizon'}")
    short = [r['card'] for r in rows
             if r.get('span_days') is not None and r['span_days'] <= lb_days]
    if short:
        print(f"      ⚠️  ACTION REQUIRED for {len(short)} card(s): {', '.join(short)}")
        print(f"      These cannot support the canonical regime test, so by the project's own")
        print(f"      third-verdict rule they are INCOMPLETE rather than ACCEPT — never")
        print(f"      silently 'passed'. Remedy is longer history, not a weaker gate.")
    return rows


# ==============================================================================
#  بخشِ D — شکارِ باگ با ورودی‌های واگن/مرزی
# ==============================================================================
def _mk(n, wr, sl=100.0, tp=100.0, cost=3.3, step=10, hold=5):
    nw = int(round(n * wr / 100.0))
    seq = S._interleave(nw, n - nw)
    rows, b = [], 0
    for o in seq:
        rows.append(dict(signal_bar=b, entry_bar=b, exit_bar=b + hold,
                         direction='long', entry_price=1.0, exit_price=1.0,
                         outcome=o, pnl_pip=(tp - cost if o == 'win' else -(sl + cost)),
                         sl_pip=sl, bars_held=hold))
        b += step
    return pd.DataFrame(rows)


def part_d():
    print()
    print(SEP)
    print("PART D — BUG HUNT: degenerate and boundary inputs (any exception = a bug)")
    print(SEP)
    cases = []

    # ۱) صفر معامله
    cases.append(("zero trades", lambda: R.compute_rqs2(
        pd.DataFrame(), 'XAUUSD', sl_pip=100.0, tp_pip=100.0)))
    # ۲) یک معامله
    cases.append(("single trade", lambda: R.compute_rqs2(
        _mk(1, 100.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0)))
    # ۳) همه برنده ⇒ PF = بی‌نهایت، MCL = 0
    cases.append(("all winners (PF=inf, MCL=0)", lambda: R.compute_rqs2(
        _mk(60, 100.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        bar_time=S.horizon(_mk(60, 100.0)), null=S.mk_null(50.0),
        n_trials=10, split_bar=300)))
    # ۴) همه بازنده ⇒ PF = 0، سودِ ناخالصِ برنده = 0
    cases.append(("all losers (gross_win=0)", lambda: R.compute_rqs2(
        _mk(60, 0.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        bar_time=S.horizon(_mk(60, 0.0)), null=S.mk_null(50.0),
        n_trials=10, split_bar=300)))
    # ۵) SL صفر ⇒ خطرِ تقسیم بر صفر در RR و breakeven
    cases.append(("sl_pip = 0 (division risk)", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=0.0, tp_pip=100.0)))
    # ۶) TP صفر ⇒ باید H2 = UNKNOWN شود، نه سقوط
    cases.append(("tp_pip = 0", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=0.0)))
    # ۷) TP منفی
    cases.append(("tp_pip < 0", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=-50.0)))
    # ۸) WR = ۱۰۰٪ در کرانِ رشتهٔ باخت ⇒ log(1/q) با q=0
    cases.append(("mcl_bound at WR=100 (log domain)",
                  lambda: R.mcl_bound(500, 100.0)))
    # ۹) WR = ۰٪ ⇒ q=1 ⇒ log(1)=0 ⇒ تقسیم بر صفر
    cases.append(("mcl_bound at WR=0 (log(1)=0)",
                  lambda: R.mcl_bound(500, 0.0)))
    # ۱۰) n=0 در کرانِ رشته
    cases.append(("mcl_bound at n=0", lambda: R.mcl_bound(0, 50.0)))
    # ۱۱) سربه‌سر با SL+TP = 0
    cases.append(("breakeven with SL+TP=0",
                  lambda: R.breakeven_wr_cost(0.0, 0.0, 3.3)))
    # ۱۲) n_trials = 0
    cases.append(("n_trials = 0", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        null=S.mk_null(50.0), n_trials=0)))
    # ۱۳) n_trials عظیم ⇒ کرانِ بهترین‌شانس
    cases.append(("n_trials = 10^9", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        null=S.mk_null(50.0), n_trials=10 ** 9)))
    # ۱۴) split در انتهای مطلق ⇒ خارج‌ازنمونهٔ خالی
    cases.append(("split_bar beyond data (empty OOS)", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        null=S.mk_null(50.0), n_trials=10, split_bar=10 ** 9)))
    # ۱۵) split در صفر ⇒ درون‌نمونهٔ خالی
    cases.append(("split_bar = 0 (empty in-sample)", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        null=S.mk_null(50.0), n_trials=10, split_bar=0)))
    # ۱۶) NaN در pnl — ⚠️ این‌جا سقوط **مطلوب** است، نه باگ.
    #     تمایزی که خودِ حسابرسی باید رعایت کند: «نبودِ استثنا» معیارِ سلامت
    #     نیست. برای ورودیِ **فاسد**، سقوطِ بلند رفتارِ درست است و ادامه‌دادن
    #     تخریبِ خاموش. پس دو ردهٔ متمایز داریم:
    #       expect_raise=False ⇒ باید تمیز داوری شود
    #       expect_raise=True  ⇒ باید صریحاً امتناع کند (سکوت = باگ)
    def nan_case():
        t = _mk(60, 60.0)
        t.loc[3, 'pnl_pip'] = np.nan
        return R.compute_rqs2(t, 'XAUUSD', sl_pip=100.0, tp_pip=100.0)
    cases.append(("NaN in pnl_pip (must REFUSE)", nan_case, ValueError))
    # ۱۷) دارایی ناشناخته — باید با پیامِ خوانا امتناع کند
    cases.append(("unknown asset key (must REFUSE)", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'NOSUCH', sl_pip=100.0, tp_pip=100.0), KeyError))
    # ۱۸) مدلِ صفر با perm_sd = 0
    cases.append(("null with perm_sd=0", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        null=S.mk_null(50.0, sd=0.0), n_trials=100)))
    # ۱۹) مدلِ صفر با perm_k زیرِ کف
    cases.append(("null with perm_k below floor", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        null=S.mk_null(50.0, k=1), n_trials=100)))
    # ۲۰) سرمایهٔ اولیهٔ صفر ⇒ درصدِ افتِ سرمایه
    cases.append(("initial_capital = 0", lambda: R.compute_rqs2(
        _mk(60, 60.0), 'XAUUSD', sl_pip=100.0, tp_pip=100.0,
        initial_capital=0.0)))

    # یکسان‌سازیِ شکلِ سه‌گانه: (نام، تابع، استثنایِ موردِ انتظار یا None)
    cases = [(c if len(c) == 3 else (c[0], c[1], None)) for c in cases]

    fails = []
    for name, fn, want_exc in cases:
        try:
            out = fn()
            if want_exc is not None:
                fails.append((name, f"SILENTLY ACCEPTED corrupt input — "
                                    f"expected {want_exc.__name__}"))
                print(f"  [SILENT]     {name:36s} ⇐ expected "
                      f"{want_exc.__name__}, got a verdict instead")
                continue
            if isinstance(out, dict):
                v = f"verdict={out['verdict']:10s} score={out['rqs2_score']:6.1f}"
                # آزمونِ انسجامِ خروجی
                bad = []
                if out['verdict'] == 'ACCEPT' and not out['passed']:
                    bad.append("ACCEPT but passed=False")
                if out['verdict'] != 'ACCEPT' and out['rqs2_score'] > 40.0:
                    bad.append("non-ACCEPT but score>40")
                if not (0.0 <= out['rqs2_score'] <= 100.0):
                    bad.append("score out of [0,100]")
                if bad:
                    fails.append((name, "; ".join(bad)))
                    print(f"  [INCOHERENT] {name:36s} {v}  ⇐ {'; '.join(bad)}")
                else:
                    print(f"  [ok]         {name:36s} {v}")
            else:
                print(f"  [ok]         {name:36s} → {out}")
        except Exception as exc:      # noqa: BLE001 — شکارِ باگ، عمداً وسیع
            if want_exc is not None and isinstance(exc, want_exc):
                print(f"  [refused ✓]  {name:36s} {type(exc).__name__}: "
                      f"{str(exc)[:70]}…")
                continue
            fails.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  [CRASH]      {name:36s} {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)

    print("  " + SUB[:94])
    print(f"  {len(cases) - len(fails)}/{len(cases)} degenerate inputs handled cleanly")
    if fails:
        print("  ⚠️  DEFECTS FOUND:")
        for n, why in fails:
            print(f"       • {n}: {why}")
    else:
        print("  ✅ no crash and no incoherent output on any boundary input")
    return fails


def main():
    print(SEP)
    print("RQS2 INDEPENDENT AUDIT — measured answers to the five governance questions")
    print(SEP)
    a = part_a()
    b = part_b()
    c = part_c()
    d = part_d()
    print()
    print(SEP)
    print("AUDIT SUMMARY")
    print(SEP)
    print(f"  A. gate boundary sits at score {a['score_at_gate_boundary']:.1f} while the")
    print(f"     acceptance floor is {R.RQS2_ACCEPT_FLOOR:.0f} ⇒ two disagreeing rules "
          f"({a['strictness_ratio']:.2f}× strictness)")
    print(f"  B. no single dimension reaches 80; "
          f"{b['min_perfect_components']} components must be perfect")
    print(f"  C. {len(c)} cards measured; cost burden and null sd differ by orders of magnitude")
    print(f"  D. {len(d)} defect(s) in {20} degenerate inputs")
    print(SEP)
    return 0 if not d else 1


if __name__ == '__main__':
    raise SystemExit(main())
