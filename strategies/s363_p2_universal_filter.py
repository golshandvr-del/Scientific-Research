# -*- coding: utf-8 -*-
"""
S363 · پروتکل **P2 — فیلترِ جهان‌شمولِ بانکِ اندیکاتور** برای لایهٔ S327
===========================================================================

پیاده‌سازیِ دقیقِ `results/S363_ADDENDUM_P2_UNIVERSAL_FILTER_PREREG.md`
(کامیت‌شده **پیش از** این فایل).

مرحلهٔ ۱ از دو مرحله: **کشف** (`--stage discover`)
--------------------------------------------------
روی **۶۰٪ اولِ** میله‌های هر کارت، و فقط روی آن:

    برای هر یک از ۴۰۱ اندیکاتورِ بانک
      برای هر جهت در {KEEP_HIGH, KEEP_LOW}
        برای هر چندک در {0.20, 0.30, 0.40, 0.50, 0.60}
          z_split = آزمونِ دو-نسبتِ (نگه‌داشته‌ها) در برابر (دورریخته‌ها)

سپس کاندیداها بر اساسِ **کمینهٔ `z_split` روی هر ۷ کارت** رتبه می‌گیرند
(بندِ ۵ پیش‌ثبت: کمینه، نه میانگین — تا یک کارتِ درخشان چهار کارتِ مرده را
جبران نکند).

مرحلهٔ ۲ (`--stage confirm`) در فایل/کامیتِ جداگانه اجرا می‌شود، پس از قفلِ
برنده.

سه تصمیمِ مهندسیِ حساس
----------------------
**۱. چرا نتیجه‌ها یک‌بار محاسبه می‌شوند و ۴۰۱۰ بار نه.** هندسه در P2 منجمد
است، پس برآمدِ هر سیگنال (`win/lose`) به فیلتر **وابسته نیست**. فیلتر فقط
تصمیم می‌گیرد کدام سیگنال‌ها *بمانند*. پس `outcome_table` **یک‌بار** برای هر
کارت اجرا می‌شود و ۴۰۱۰ کاندیدا صرفاً ماسک‌های بولی روی همان بردارِ برآمدند.
این تفاوتِ بینِ چند ثانیه و چند ساعت است.

**۲. چرا اندیکاتور در نقطهٔ سیگنال خوانده می‌شود و نه در نقطهٔ ورود.** ورود در
کندلِ *بعدی* رخ می‌دهد. اگر اندیکاتور را در کندلِ ورود بخوانیم، اطلاعاتی وارد
تصمیم می‌شود که در لحظهٔ تصمیم‌گیری موجود نبوده ⇒ **نشتِ آینده**. مقدارِ
اندیکاتور دقیقاً روی `signal_bar` خوانده می‌شود، همان میله‌ای که هندسه هم از
`ATR`ِ آن ساخته می‌شود.

**۳. چرا چندک از دادهٔ کشف مشتق می‌شود و در فایل ذخیره می‌گردد.** آستانهٔ
عددیِ مطلق (`0.3172`) از چندکِ **۶۰٪ اول** به دست می‌آید و برای مرحلهٔ تأیید
**منجمد** می‌شود. اگر آستانه را روی کلِ داده دوباره حساب کنیم، ۴۰٪ دست‌نخورده
دیگر دست‌نخورده نیست — یک نشتِ ظریف که کلِ مسیرِ C را باطل می‌کند.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                    # noqa: E402
from engine import indicator_bank as ib                                  # noqa: E402
from strategies.s363_s327_v24_rejudge import (                           # noqa: E402
    ARCHIVE_CFG, SPLIT_FRAC, build_features, geometry, signal_of,
    outcome_table)
from strategies.s363_p1_legal_geometry import (                          # noqa: E402
    build_family, pick_deployment)

OUT = "results/_scan_S363"

# ═══════ گریدِ منجمدِ §۴ پیش‌ثبتِ P2 — پس از دیدنِ نتیجه تغییر نمی‌کند ═══════
QUANTILES = [0.20, 0.30, 0.40, 0.50, 0.60]
DIRECTIONS = ['KEEP_HIGH', 'KEEP_LOW']
RETENTION_MIN = 0.40          # کفِ ساختاری — پیش از دیدنِ عملکرد
RETENTION_MAX = 0.80          # سقفِ ساختاری — بالاتر از این، فیلتر کاری نمی‌کند

ALL_CARDS = ["XAUUSD-M5", "XAUUSD-M15", "XAUUSD-M30", "XAUUSD-H1",
             "XAUUSD-H4", "EURUSD-M15", "EURUSD-M30"]


# ═══════════════════════════ ابزارِ آماری ═══════════════════════════
def z_two_proportion(k1, n1, k2, n2):
    """`z`ِ آزمونِ دو-نسبتِ استاندارد (تجمیعِ واریانس تحتِ `H0`).

    `n1`/`n2` = تعدادِ معاملهٔ نگه‌داشته/دورریخته، `k1`/`k2` = تعدادِ برنده.
    اگر هر طرف تهی باشد یا واریانسِ تجمیعی صفر شود ⇒ `nan` (کاندیدا حذف).
    """
    if n1 < 1 or n2 < 1:
        return float('nan')
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    var = p * (1.0 - p) * (1.0 / n1 + 1.0 / n2)
    if var <= 0:
        return float('nan')
    return (p1 - p2) / np.sqrt(var)


# ═════════════════ آماده‌سازیِ یک کارت (یک‌بار، نه ۴۰۱۰ بار) ═════════════════
def prepare_card(card, verbose=True):
    """`(df, sig_idx_disc, win_disc, geom, split_bar)` برای بخشِ **کشف**.

    خروجی فقط به بخشِ کشف محدود است — هیچ میله‌ای از ۴۰٪ آخر لمس نمی‌شود.
    """
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return None
    df = se.load_data(path)
    n = len(df)
    split_bar = int(n * SPLIT_FRAC)

    cfg = ARCHIVE_CFG[card]
    fam, _ = build_family()
    geom = pick_deployment(fam, cfg)                 # هندسهٔ منجمدِ P1

    feat = build_features(df, asset)
    sl_arr, tp_arr, _ = geometry(feat, asset, geom['sl_m'], geom['tp_m'])
    sig = signal_of(feat, cfg, asset)
    res, _ = outcome_table(df, asset, sl_arr, tp_arr, geom['hold'])

    # ⚠️ نشتِ آینده: ورود در کندلِ بعد رخ می‌دهد، پس آخرین میله‌های ممکن حذف
    valid = sig & np.isfinite(res)
    idx_all = np.flatnonzero(valid)
    idx_disc = idx_all[idx_all < split_bar]          # ← فقط ۶۰٪ اول
    win_disc = (res[idx_disc] > 0).astype(np.int8)

    if verbose:
        print(f"  {card:12s} n_bars={n:7d} split@{split_bar:7d} "
              f"sig_total={idx_all.size:4d} sig_discovery={idx_disc.size:4d} "
              f"WR_disc={100.0*win_disc.mean() if win_disc.size else float('nan'):.2f}% "
              f"geom sl={geom['sl_m']} tp={geom['tp_m']} h={geom['hold']}",
              flush=True)
    return dict(card=card, asset=asset, df=df, split_bar=split_bar,
                idx_disc=idx_disc, win_disc=win_disc, geom=geom,
                n_bars=n, n_sig_total=int(idx_all.size))


# ═══════════════════════ جست‌وجویِ کشف روی یک اندیکاتور ═══════════════════════
def eval_indicator(name, cards):
    """`z_split` برای هر `(جهت، چندک)` روی **هر** کارت.

    خروجی: `{(direction, q): {card: dict}}` یا `None` اگر اندیکاتور روی هر
    کارتی محاسبه‌ناپذیر بود (بانک برای بعضی تایم‌فریم‌های کوتاه `nan` می‌دهد).
    """
    per_card_vals = {}
    for c in cards:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                s = ib.compute(name, c['df'])
            v = np.asarray(s, dtype=np.float64)
        except Exception:
            return None
        if v.shape[0] != c['n_bars']:
            return None
        vv = v[c['idx_disc']]                        # ← مقدار روی signal_bar
        if not np.isfinite(vv).any():
            return None
        per_card_vals[c['card']] = vv

    out = {}
    for direction in DIRECTIONS:
        for q in QUANTILES:
            rows = {}
            ok = True
            for c in cards:
                vv = per_card_vals[c['card']]
                w = c['win_disc']
                fin = np.isfinite(vv)
                if fin.sum() < 10:
                    ok = False
                    break
                # آستانه از چندکِ **دادهٔ کشف** (بندِ ۴ پیش‌ثبت)
                thr = float(np.quantile(vv[fin], q if direction == 'KEEP_HIGH'
                                        else 1.0 - q))
                keep = (vv >= thr) if direction == 'KEEP_HIGH' else (vv <= thr)
                keep = keep & fin
                n_keep = int(keep.sum())
                n_drop = int((~keep).sum())
                ret = n_keep / max(vv.size, 1)
                if not (RETENTION_MIN <= ret <= RETENTION_MAX):
                    ok = False                        # حذفِ ساختاری
                    break
                k1 = int(w[keep].sum())
                k2 = int(w[~keep].sum())
                z = z_two_proportion(k1, n_keep, k2, n_drop)
                if not np.isfinite(z):
                    ok = False
                    break
                rows[c['card']] = dict(
                    thr=thr, n_keep=n_keep, n_drop=n_drop,
                    wr_keep=round(100.0 * k1 / n_keep, 4),
                    wr_drop=round(100.0 * k2 / n_drop, 4),
                    retention=round(ret, 4), z=round(float(z), 4))
            if ok:
                out[(direction, q)] = rows
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default=','.join(ALL_CARDS))
    ap.add_argument('--limit', type=int, default=0,
                    help='فقط برای دودِ تست — ۰ یعنی هر ۴۰۱ اندیکاتور')
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    card_names = [c.strip() for c in args.cards.split(',') if c.strip()]

    print("=" * 92)
    print("S363 · P2 STAGE-1 DISCOVERY — universal indicator filter")
    print(f"  discovery segment = first {SPLIT_FRAC:.0%} of bars ONLY")
    print(f"  ranking statistic = MIN of z_split across {len(card_names)} cards")
    print("=" * 92)

    cards = []
    for name in card_names:
        c = prepare_card(name)
        if c is None:
            print(f"  {name}: NO DATA — skipped")
            continue
        cards.append(c)
    if len(cards) < len(card_names):
        print("⚠️ some cards missing — universality constraint would be weaker")

    names = ib.list_indicators()
    if args.limit:
        names = names[:args.limit]
    print(f"\nsweeping {len(names)} indicators × {len(DIRECTIONS)} directions "
          f"× {len(QUANTILES)} quantiles = "
          f"{len(names)*len(DIRECTIONS)*len(QUANTILES)} candidates per card\n",
          flush=True)

    # ── حافظهٔ نهانِ ازسرگیری‌پذیر (شاردِ هر-اندیکاتور) ──────────────────────
    # چرا: بانک چند اندیکاتورِ **بسیار کند** دارد (`cmo_fib_233` روی ۲۰۰ هزار
    # کندل ≈ ۲۲ ثانیه × ۷ کارت). کلِ جاروب ده‌ها دقیقه طول می‌کشد و سندباکسِ ما
    # در همین نشست **دوبار** ریست شده و هر بار یک اجرای ناتمام را نابود کرده
    # است. با نوشتنِ یک خطِ JSON پس از **هر** اندیکاتور و `flush`+`fsync`،
    # بیشترین چیزی که یک ریست می‌تواند ببلعد **یک اندیکاتور** است، نه کلِ جاروب.
    # این دقیقاً همان «قانونِ سوم — اندک اندک» است، در سطحِ درون-اسکریپت.
    partial = os.path.join(OUT, 'P2_PARTIAL.jsonl')
    done = {}
    if os.path.exists(partial):
        with open(partial) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue            # خطِ نیمه‌نوشته از یک ریست ⇒ نادیده
                done[rec['indicator']] = rec
        print(f"  resume: {len(done)} indicators already cached in "
              f"{partial} — they will be skipped\n", flush=True)

    t0 = time.time()
    fh = open(partial, 'a')
    for i, name in enumerate(names, 1):
        if name not in done:
            r = eval_indicator(name, cards)
            if r is None:
                rec = dict(indicator=name, usable=False, cands=[])
            else:
                cands = []
                for (direction, q), rows in r.items():
                    zs = [rows[c['card']]['z'] for c in cards]
                    cands.append(dict(
                        indicator=name, direction=direction, quantile=q,
                        z_min=round(float(min(zs)), 4),
                        z_mean=round(float(np.mean(zs)), 4),
                        z_max=round(float(max(zs)), 4),
                        n_cards=len(zs), per_card=rows))
                rec = dict(indicator=name, usable=True, cands=cands)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())       # دوامِ واقعی روی دیسک، نه فقط بافر
            done[name] = rec
        if i % 40 == 0:
            nv = sum(len(d['cands']) for d in done.values())
            nf = sum(1 for d in done.values() if not d['usable'])
            print(f"  ...{i}/{len(names)} indicators  "
                  f"({time.time()-t0:.0f}s, {nv} viable candidates, "
                  f"{nf} indicators unusable)", flush=True)
    fh.close()

    results = [c for name in names if name in done
               for c in done[name]['cands']]
    n_fail = sum(1 for name in names
                 if name in done and not done[name]['usable'])

    results.sort(key=lambda d: -d['z_min'])
    payload = dict(
        protocol='P2_STAGE1_DISCOVERY',
        prereg='results/S363_ADDENDUM_P2_UNIVERSAL_FILTER_PREREG.md',
        split_frac=SPLIT_FRAC,
        cards=[c['card'] for c in cards],
        card_meta={c['card']: dict(n_bars=c['n_bars'],
                                   split_bar=c['split_bar'],
                                   n_sig_total=c['n_sig_total'],
                                   n_sig_discovery=int(c['idx_disc'].size),
                                   wr_discovery=round(
                                       100.0 * float(c['win_disc'].mean()), 4)
                                   if c['win_disc'].size else None,
                                   geom=c['geom'])
                   for c in cards},
        grid=dict(n_indicators=len(names), directions=DIRECTIONS,
                  quantiles=QUANTILES,
                  retention_min=RETENTION_MIN, retention_max=RETENTION_MAX),
        n_indicators_unusable=n_fail,
        n_viable_candidates=len(results),
        elapsed_s=round(time.time() - t0, 1),
        top50=results[:50])

    path = os.path.join(OUT, 'P2_DISCOVERY.json')
    with open(path, 'w') as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)

    print(f"\n{'='*92}")
    print(f"discovery done in {payload['elapsed_s']}s — "
          f"{len(results)} viable candidates, {n_fail} indicators unusable")
    print(f"\n{'rank':>4} {'indicator':22s} {'dir':10s} {'q':>5} "
          f"{'z_min':>7} {'z_mean':>7} {'z_max':>7}")
    for i, r in enumerate(results[:20], 1):
        print(f"{i:4d} {r['indicator']:22s} {r['direction']:10s} "
              f"{r['quantile']:5.2f} {r['z_min']:7.3f} {r['z_mean']:7.3f} "
              f"{r['z_max']:7.3f}")
    print(f"\n→ saved {path}")


if __name__ == '__main__':
    main()
