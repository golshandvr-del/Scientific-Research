# -*- coding: utf-8 -*-
"""
اعتبارسنجیِ **RQS2 روی دادهٔ واقعی** — سه موردِ معلوم‌الجوابِ S346
================================================================================
تستِ واحد (`engine/rqs2_selftest.py`) با معاملاتِ مصنوعی ثابت کرد که معیار در
شرایطِ کنترل‌شده درست رفتار می‌کند. اما پرسشِ نهایی این است:

    آیا RQS2 روی **همان داده‌های واقعیِ** پروژه، همان تفکیکی را می‌دهد که ما
    با دستِ خودمان و با چند آزمونِ جداگانه (ابلیشنِ جهت + مدلِ صفر) کشف کردیم؟

سه موردِ معلوم (پیش از اجرا اعلام‌شده تا آزمون ابطال‌پذیر باشد):

  C1  XAUUSD-D1  breakout/both p=13 m=2.058 h=5  + ۲ فیلتر
      RQS+ = 83.9 ACCEPT   ·  انتظارِ ما از RQS2: **ACCEPT**
      دلیل: هر دو سمت مستقلاً لبه دارند (لانگ +10.0pp/5.9σ، شورت +16.2pp/5.6σ)

  C2  XAUUSD-D1  breakout/long p=34 m=1.618 h=13 + ۱ فیلتر
      RQS+ = 85.0 ACCEPT (**بالاترین نمرهٔ کلِ پرونده**)
      انتظارِ ما از RQS2: **REJECT** روی `H4`
      دلیل: تک‌سویه است و سمتِ شورتِ همان هندسه صفرِ مطلق است (−0.37pp)

  C3  XAUUSD-W1  breakout/both p=21 m=1.272 h=13 + صفر فیلتر
      RQS+ = 84.2 ACCEPT  ·  انتظارِ ما از RQS2: **REJECT** روی `H3`
      دلیل: ورودِ بی‌قید ۵۸.۲٪ می‌برد و جای‌گشت‌ها تا ۶۵.۶٪ می‌روند؛ سیگنال ۶۳.۰٪

اگر RQS2 این سه را درست تفکیک کند، معیار **روی واقعیت** اعتبار دارد و می‌تواند
معیارِ رسمیِ پروژه شود. اگر نه، معیار باید اصلاح شود — نه اینکه واقعیت.

اجرا:  python -m strategies.s346_rqs2_validate
"""
from __future__ import annotations

import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from engine import rqs as RQS
from engine import rqs2 as R2
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_geom import CARDS, event_mask
from strategies.s346_bank401 import build_parts
from strategies.s346_verdict import gate_from_bank

OUT = 'results/_scan_S346'

# ------------------------------------------------------------------------------
# اندازهٔ فضای جست‌وجویی که **واقعاً** پیمایش شد (برای H5)
# ------------------------------------------------------------------------------
#   مرحلهٔ ۱: ۱۲۹۶ هندسه (۱۲۴۸ برای W1) پیمایشِ کامل
#   مرحلهٔ ۲: ۲۴ هندسهٔ برتر × ۴۰۱ اندیکاتور × ۱۰ آستانه = ۹۶٬۲۴۰ آزمونِ فیلتر
#   جمع ≈ ۹۷٬۵۰۰. این عدد **صادقانه** اعلام می‌شود؛ کم‌گفتنش تقلب است چون
#   کرانِ «بهترینِ شانس» با آن بالا می‌رود.
N_TRIALS_FILTERED = 1296 + 24 * 401 * 10
#   لایهٔ بی‌فیلتر (C3) فقط از پیمایشِ هندسه بیرون آمد ⇒ جریمهٔ کمتر، صادقانه‌تر.
N_TRIALS_BARE = 1248


def n_trials_eff(card, fallback):
    """N **مؤثرِ اندازه‌گیری‌شده** (اگر موجود باشد) به‌جای شمارشِ خام.

    ⚠️ چرا این جانشینی *تقلب نیست*: کرانِ `E[max_N]` برای آزمون‌های **مستقل**
    مشتق شده و آزمون‌های ما همبسته‌اند؛ گذاشتنِ شمارشِ خام یک **خطای ریاضیِ
    آشکار** است، مستقل از اینکه نتیجه به سودِ ما تمام شود یا نه. و در عمل هم
    به سودِ ما تمام نشد (۹۷٬۵۳۶ → ۵۶٬۴۹۹ یعنی کران فقط ۴.۳۸۵ → ۴.۲۶۵).
    """
    p = f"{OUT}/{card}_neff.json"
    if not os.path.exists(p):
        return int(fallback), 'raw (no measurement available)'
    d = json.load(open(p))
    return int(d['n_trials_eff']), (f"measured effective (raw={d['n_trials_raw']:,}, "
                                    f"M_eff ind={d['m_eff_indicator']}, "
                                    f"thr={d['m_eff_threshold']})")


def load_case(card, kind, geom_key):
    """خواندنِ (هندسه، فیلترها) از فایلِ داوریِ ذخیره‌شده + مدلِ صفرِ متناظر."""
    vf = f"{OUT}/{card}_verdict.json" if kind == 'filtered' \
        else f"{OUT}/{card}_bare_verdict.json"
    rows = json.load(open(vf))['results']
    nulls = json.load(open(f"{OUT}/{card}_null.json"))['results']

    def key(g):
        return (g['mode'], g['side'], g['p'], g['mult'], g['hold'])

    hit = [r for r in rows if key(r['geom']) == geom_key]
    if not hit:
        raise SystemExit(f"geometry {geom_key} not found in {vf}")
    row = hit[0]
    nh = [r for r in nulls if key(r['geom']) == geom_key]
    if not nh:
        raise SystemExit(f"no measured null for {geom_key} in {card}_null.json")
    return row, nh[0]


def simulate(card, geom, filters):
    """بازتولیدِ **دقیقاً همان** معاملاتی که داوریِ رسمی روی آن انجام شد."""
    asset, path = CARDS[card]
    df = se.load_data(path)
    ch = adaptive_channel(df, p=geom['p'], mult=1.0)
    warmup = max(5 * geom['p'], 250)
    ls, ss = event_mask(df, ch, geom['mode'], geom['mult'], geom['er_thr'], warmup)

    if filters:
        man = build_parts(card, df, ch)
        gate = gate_from_bank(man, filters, len(df))
        ls = ls & gate
        ss = ss & gate

    sd = geom['side']
    if sd == 'long':
        ss = np.zeros(len(df), bool)
    elif sd == 'short':
        ls = np.zeros(len(df), bool)

    pip = se.ASSETS[asset]['pip']
    sl_price = geom['sl_k'] * ch['atr_a']
    tp_price = geom['rr'] * sl_price
    with np.errstate(invalid='ignore'):
        sl_pip = np.nan_to_num(sl_price / pip, nan=0.0)
        tp_pip = np.nan_to_num(tp_price / pip, nan=0.0)
    tp_pip = np.maximum(tp_pip, sl_pip)      # قیدِ ضدِ تقلبِ #۸

    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset,
                            max_hold=geom['hold'], allow_overlap=False)
    return df, asset, tr, sl_pip, tp_pip


def judge(label, card, kind, geom_key, expect, n_trials):
    row, nrow = load_case(card, kind, geom_key)
    geom, filters = row['geom'], (row.get('filters') or [])
    df, asset, tr, sl_arr, tp_arr = simulate(card, geom, filters)

    # SL/TP نمایندهٔ لایه = میانهٔ **معاملاتِ واقعی** (نه کلِ سری)، چون براکت
    # شناور است و آنچه اهمیت دارد مقدارِ آن در لحظاتِ ورودِ واقعی است.
    eb = tr['entry_bar'].values.astype(int) if len(tr) else np.array([], int)
    sl_med = float(np.median(sl_arr[eb])) if len(eb) else None
    tp_med = float(np.median(tp_arr[eb])) if len(eb) else None

    null = R2.null_from_s346(nrow)
    split_bar = int(len(df) * 0.60)

    r_old = RQS.compute_rqs(tr, asset)
    r_new = R2.compute_rqs2(
        tr, asset, sl_pip=sl_med, tp_pip=tp_med,
        bar_time=df['time'].values, close=df['close'].values,
        null=null, n_trials=n_trials, split_bar=split_bar)

    print()
    print("-" * 100)
    print(f"{label}  ::  {card}  {geom['mode']}/{geom['side']} p={geom['p']} "
          f"m={geom['mult']} er={geom['er_thr']} sl={geom['sl_k']} rr={geom['rr']} "
          f"h={geom['hold']} | filters={len(filters)}")
    print(f"   RQS+  : {r_old['verdict']:6s} score={r_old['rqs_score']:5.1f}")
    print("   RQS2  : " + R2.format_rqs2('', r_new).strip(' |'))
    m = r_new['metrics']
    print(f"      null_ref={m['null_ref_wr']}%  lift={m['skill_lift_pp']}pp  "
          f"z={m['skill_z']}  perm_max={m['perm_max']}  "
          f"z_bound={m['z_luck_bound']} (N={n_trials:,})  margin={m['z_margin']}")
    print(f"      side_n={m['side_n']}  side_wr={m['side_wr']}  "
          f"side_lift={m['side_lift_pp']}  prune={m['prune_sides']}")
    print(f"      counter_drift={m['counter_drift']}")
    print(f"      be_cost={m['breakeven_wr_cost']}%  excess={m['wr_excess_cost']}pp  "
          f"exp={m['expectancy_pip']}pip  exp@2xcost={m['expectancy_at_2x_cost']}")
    print(f"      cal_nets={m['cal_nets']}  oos={m['oos']}")
    for nt in r_new['notes']:
        print(f"      note: {nt}")

    got = r_new['verdict']
    ok = (got == expect)
    print(f"   EXPECT {expect} -> GOT {got}   {'✅ PASS' if ok else '❌ FAIL'}")
    return ok, dict(label=label, card=card, geom=geom, n_filters=len(filters),
                    rqs_plus=r_old['rqs_score'], rqs_plus_verdict=r_old['verdict'],
                    rqs2=r_new['rqs2_score'], rqs2_verdict=got,
                    gates=r_new['gates'], metrics=m, expect=expect, ok=ok)


def main():
    print("=" * 100)
    print("RQS2 REAL-DATA VALIDATION — three known S346 cases")
    print("=" * 100)
    cases = [
        ('C1 D1 symmetric (true edge)', 'XAUUSD-D1', 'filtered',
         ('breakout', 'both', 13, 2.058, 5), 'ACCEPT', N_TRIALS_FILTERED),
        ('C2 D1 long-only (RQS+ top)', 'XAUUSD-D1', 'filtered',
         ('breakout', 'long', 34, 1.618, 13), 'REJECT', N_TRIALS_FILTERED),
        ('C3 W1 bare (drift rider)', 'XAUUSD-W1', 'bare',
         ('breakout', 'both', 21, 1.272, 13), 'REJECT', N_TRIALS_BARE),
    ]
    allok, out = True, []
    for label, card, kind, gk, expect, nt_fallback in cases:
        nt, how = n_trials_eff(card, nt_fallback)
        print(f"\n[{label}] n_trials = {nt:,}  [{how}]")
        try:
            ok, rec = judge(label, card, kind, gk, expect, nt)
        except SystemExit as e:
            print(f"\n{label}: SKIPPED — {e}")
            continue
        allok &= ok
        out.append(rec)
        with open(f"{OUT}/rqs2_validation.json", 'w') as fh:
            json.dump(dict(cases=out), fh, default=float, indent=1)
        print("   [checkpointed]", flush=True)

    print()
    print("=" * 100)
    print("VALIDATION RESULT: " + ("ALL PASS ✅" if allok else "FAILURES ❌"))
    print("=" * 100)
    return 0 if allok else 1


if __name__ == '__main__':
    raise SystemExit(main())
