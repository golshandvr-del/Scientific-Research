# -*- coding: utf-8 -*-
"""
S346 — **مدلِ صفر (Null Model)**: آیا سیگنال اصلاً چیزی به «ورودِ بی‌قید» می‌افزاید؟
================================================================================
پرسشی که این فایل پاسخ می‌دهد
--------------------------------------------------------------------------------
دروازهٔ G1 در RQS+ لبه را نسبت به **سربه‌سرِ هندسی** می‌سنجد:
`wr_breakeven = SL/(SL+TP)`. برای `RR=1.0` این عدد ۵۰٪ است. اما ۵۰٪ نرخِ برندِ
درستی برای براکتِ متقارن **فقط در پیاده‌رویِ تصادفیِ بی‌رانش** است. اگر دارایی در
بازهٔ داده رانشِ صعودیِ قوی داشته باشد، یک براکتِ `1×ATR / 1×ATR` که **روی هر
کندل و بی‌هیچ سیگنالی** باز شود، می‌تواند ذاتاً بیش از ۵۰٪ ببرد — چون TP در جهتِ
رانش نزدیک‌تر «احساس» می‌شود.

⇒ در آن حالت، عبور از G1 هیچ کشفی را ثابت نمی‌کند؛ فقط رانشِ دارایی را بازتاب
می‌دهد. این همان چیزی است که ابلیشنِ جهت را روی `XAUUSD-D1` نجات‌بخش کرد، ولی
ابلیشنِ جهت **کافی نیست**: روی `XAUUSD-W1` هر دو سمت مثبت بودند، اما ۸۴٪ رویدادها
لانگ بود و شورت فقط n=22 داشت ⇒ ابلیشن آماری بی‌توان است.

پس یک کنترلِ مستقل لازم است: **همان براکت، همان hold، همان صف، ولی بدونِ شرطِ
سیگنال.** هر لبهٔ ادعایی باید این خطِ مبنا را به‌طور معنادار بشکند.

سه خطِ مبنای محاسبه‌شده
--------------------------------------------------------------------------------
  NULL-long   : ورودِ Long روی **هر** کندلِ واجدِ warmup (بدونِ شرط)
  NULL-short  : همان، Short
  NULL-mixed  : همان الگویِ لانگ/شورتِ سیگنالِ واقعی ولی با **جای‌گشتِ زمانی**
                (رویدادها به تعدادِ یکسان اما در اندیس‌های تصادفی) — کنترلِ
                «آیا *زمان‌بندیِ* سیگنال مهم است یا فقط *تعدادش*؟»

معیارِ پذیرش (lift): `WR_signal − WR_null_same_side`. اگر این عدد کوچک باشد،
لایه فقط «رانشِ دارایی با یک براکت» است، نه الگویابی — هرچقدر هم RQS+ بالا باشد.
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from engine import rqs as RQS                  # noqa: E402
from strategies.s346_adaptive_channel import adaptive_channel   # noqa: E402
from strategies.s346_geom import CARDS, event_mask              # noqa: E402

OUT = 'results/_scan_S346'


def _brackets(df, ch, geom, asset):
    """SL/TP بر حسبِ pip — عیناً مثلِ داوریِ رسمی (شاملِ قیدِ ضدِ تقلبِ #۸)."""
    pip = se.ASSETS[asset]['pip']
    sl_price = geom['sl_k'] * ch['atr_a']
    tp_price = geom['rr'] * sl_price
    with np.errstate(invalid='ignore'):
        sl_pip = np.nan_to_num(sl_price / pip, nan=0.0)
        tp_pip = np.nan_to_num(tp_price / pip, nan=0.0)
    return sl_pip, np.maximum(tp_pip, sl_pip)


def _run(df, ls, ss, sl_pip, tp_pip, asset, hold):
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset,
                            max_hold=hold, allow_overlap=False)
    return RQS.compute_rqs(tr, asset)


def null_baselines(card, geom, filters=None, n_perm=20, seed=7, verbose=True):
    """
    خطوطِ مبنا برای یک لایه. برمی‌گرداند dict با کلیدهای
    signal / null_long / null_short / perm.

    `filters` : فهرستِ فیلترهای بانکِ ۴۰۱ (پیشوندِ `B:`). **باید** پاس داده شود
        وقتی لایهٔ موردِ داوری فیلتر دارد، وگرنه `signal` پایهٔ بی‌فیلتر را
        می‌سنجد و مقایسه بی‌معنا می‌شود. نکتهٔ ظریفِ طراحیِ کنترل: جای‌گشت با
        **تعدادِ رویدادِ لایهٔ نهایی (پس از فیلتر)** انجام می‌شود، نه پایه —
        چون فیلتر تعدادِ معاملات را کم می‌کند و WR در نمونهٔ کوچک‌تر واریانسِ
        بیشتری دارد؛ اگر جای‌گشت با n بزرگ‌ترِ پایه ساخته شود، خطِ مبنا مصنوعاً
        باریک و آزمون به‌غلط «معنادار» می‌شود.
    """
    asset, path = CARDS[card]
    df = se.load_data(path)
    ch = adaptive_channel(df, p=geom['p'], mult=1.0)
    n = len(df)
    warmup = max(5 * geom['p'], 250)
    sl_pip, tp_pip = _brackets(df, ch, geom, asset)

    ls, ss = event_mask(df, ch, geom['mode'], geom['mult'], geom['er_thr'], warmup)
    if filters:
        from strategies.s346_bank401 import build_parts
        from strategies.s346_verdict import gate_from_bank
        man = build_parts(card, df, ch)
        gate = gate_from_bank(man, filters, n)
        ls = ls & gate
        ss = ss & gate
    sd = geom['side']
    ls_s = np.zeros(n, bool) if sd == 'short' else ls.copy()
    ss_s = np.zeros(n, bool) if sd == 'long' else ss.copy()

    # ماسکِ «هر کندلِ واجد» — همان گاردِ warmup و همان اعتبارِ ATR
    valid = np.zeros(n, bool)
    valid[warmup:] = True
    valid &= np.isfinite(sl_pip) & (sl_pip > 0)

    res = {}
    res['signal'] = _run(df, ls_s, ss_s, sl_pip, tp_pip, asset, geom['hold'])
    z = np.zeros(n, bool)
    res['null_long'] = _run(df, valid, z, sl_pip, tp_pip, asset, geom['hold'])
    res['null_short'] = _run(df, z, valid, sl_pip, tp_pip, asset, geom['hold'])

    # جای‌گشتِ زمانی: همان **تعدادِ** رویداد، اندیس‌های تصادفی از میانِ valid
    rng = np.random.default_rng(seed)
    vidx = np.flatnonzero(valid)
    perm = {'long': [], 'short': []}
    for side_name, base in (('long', ls_s), ('short', ss_s)):
        k = int(base.sum())
        if k == 0 or k > len(vidx):
            continue
        for _ in range(n_perm):
            pick = rng.choice(vidx, size=k, replace=False)
            m = np.zeros(n, bool)
            m[pick] = True
            a, b = (m, z) if side_name == 'long' else (z, m)
            r = _run(df, a, b, sl_pip, tp_pip, asset, geom['hold'])
            perm[side_name].append(r['metrics'].get('win_rate', 0.0))
    res['perm'] = {k: (dict(mean=float(np.mean(v)), sd=float(np.std(v)),
                            lo=float(np.min(v)), hi=float(np.max(v)), k=len(v))
                       if v else None)
                   for k, v in perm.items()}

    if verbose:
        sm = res['signal']['metrics']
        nl = res['null_long']['metrics']
        ns = res['null_short']['metrics']
        print(f"   SIGNAL     n={sm['n_trades']:5d} WR={sm['win_rate']:6.2f} "
              f"PF={sm['profit_factor']:5.2f} exp={sm['expectancy_pip']:+8.2f}pip",
              flush=True)
        print(f"   NULL long  n={nl['n_trades']:5d} WR={nl['win_rate']:6.2f} "
              f"PF={nl['profit_factor']:5.2f} exp={nl['expectancy_pip']:+8.2f}pip",
              flush=True)
        print(f"   NULL short n={ns['n_trades']:5d} WR={ns['win_rate']:6.2f} "
              f"PF={ns['profit_factor']:5.2f} exp={ns['expectancy_pip']:+8.2f}pip",
              flush=True)
        for k, v in res['perm'].items():
            if v:
                print(f"   PERM {k:5s} WR mean={v['mean']:6.2f} sd={v['sd']:5.2f} "
                      f"range=[{v['lo']:.2f},{v['hi']:.2f}] over {v['k']} draws",
                      flush=True)
        # لیفتِ نهایی
        base_wr = max(nl['win_rate'], ns['win_rate'])
        pm = [v['mean'] for v in res['perm'].values() if v]
        perm_wr = max(pm) if pm else base_wr
        ref = max(base_wr, perm_wr)
        print(f"   ⇒ LIFT over strongest null = "
              f"{sm['win_rate'] - ref:+.2f}pp  (null ref={ref:.2f})", flush=True)
    return res


def run(card, verdict_file=None, top_k=3, n_perm=20, save=True):
    """روی کاندیداهای پذیرفته‌شدهٔ یک کارت (از فایلِ داوری) اجرا می‌شود."""
    vf = verdict_file or f"{OUT}/{card}_bare_verdict.json"
    if not os.path.exists(vf):
        vf = f"{OUT}/{card}_verdict.json"
    if not os.path.exists(vf):
        print(f"!!! no verdict file for {card}", flush=True)
        return []
    rs = json.load(open(vf))['results']
    acc = [r for r in rs if r['formal'].get('passed')]
    if not acc:
        print(f"!!! {card}: no accepted candidate in {vf}", flush=True)
        return []
    # فقط هندسه‌های یکتا (بسیاری از کاندیداها فقط در hold تفاوت دارند)
    seen, pool = set(), []
    for r in acc:
        g = r['geom']
        key = (g['mode'], g['side'], g['p'], g['mult'], g['er_thr'],
               g['sl_k'], g['rr'], g['hold'])
        if key in seen:
            continue
        seen.add(key)
        pool.append(r)
    pool = pool[:top_k]

    print(f"=== S346 NULL-MODEL CONTROL :: {card} ({len(pool)} accepted "
          f"geometries, {n_perm} permutations each) ===", flush=True)
    out = []
    for i, r in enumerate(pool, 1):
        g = r['geom']
        nf = len(r.get('filters') or [])
        print(f"\n[{i}/{len(pool)}] {g['mode']}/{g['side']} p={g['p']} "
              f"m={g['mult']} er={g['er_thr']} sl={g['sl_k']} rr={g['rr']} "
              f"h={g['hold']} | filters={nf} | claimed RQS="
              f"{r['formal']['rqs_score']}", flush=True)
        res = null_baselines(card, g, filters=r.get('filters') or [],
                             n_perm=n_perm)
        out.append(dict(geom=g, n_filters=nf,
                        claimed_rqs=r['formal']['rqs_score'],
                        signal=res['signal'], null_long=res['null_long'],
                        null_short=res['null_short'], perm=res['perm']))
        if save:
            with open(f"{OUT}/{card}_null.json", 'w') as fh:
                json.dump(dict(card=card, results=out), fh, default=float)
            print(f"   [checkpointed {i}/{len(pool)}]", flush=True)
    return out


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-W1'
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    npm = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    run(card, top_k=k, n_perm=npm)
