# -*- coding: utf-8 -*-
"""
S357-B — گامِ **۳الف** پیش‌ثبت‌شده: آزمونِ **سطحِ خانواده** (مسیرِ `B`) برای S341
================================================================================

چرا این آزمون؟
--------------
بازداوریِ `s357_s341_v24_rejudge.py` نشان داد لبهٔ S341 **واقعی** است اما با
پیکربندیِ منجمد **رد** می‌شود، و علتِ رد **کمبودِ توان** است نه نبودِ لبه:

    کارت        n    WR      lift        z       n لازم برای H5
    XAU-M5      48   70.83%  +21.12pp   2.93    83   (۱.۷۳×)
    XAU-H1      42   66.67%  +16.54pp   2.14   136   (۳.۲۴×)
    XAU-M30     61   63.93%  +14.93pp   2.33   167   (۲.۷۴×)
    XAU-M15     40   65.00%  +14.90pp   1.89   166   (۴.۱۵×)

`H5` بهای **انتخابِ بهترینِ ۱۰٬۳۶۸** را می‌گیرد (کران `E[max_z]=3.855σ`).
`RQS2_SPEC §۲.۵` راهِ مشروعِ عبور را تعریف کرده:

> جریمهٔ چندگانگی بهای **انتخاب** است. اگر هیچ عضوی انتخاب نشود، بهایی نیست ⇒ `N=1`
> ⇒ کران `E[max_1] = 0.52σ`.

پس آمارهٔ آزمون **میانگینِ کلِ ۷۲ ساختارِ خانواده** است، نه بهترین عضو. این کار
هم‌زمان مسئلهٔ توان را هم حل می‌کند، چون میانگین‌گیری واریانسِ آمارهٔ صفر را
می‌شکند (روی `S346`: `sd` از ~۷pp به ۰.۲۳۸pp و لیفتِ +۳.۱۱pp به ۱۳.۰۶σ رسید).

خانوادهٔ پیش‌ثبت‌شده (بندِ ۶ پیش‌ثبت، «میانگینِ کلِ ۷۲ ساختارِ گرید»)
--------------------------------------------------------------------
    side(2) × w(3) × buf(2) × regime(3) × require_second(2) = ۷۲ عضو
    stretch = None ، exh = None      ← دو درجهٔ آزادیِ *گزینشیِ* احیای H1 حذف می‌شوند
    براکت = `sl/tp/mh`ِ منجمدِ همان کارت

`side` هر دو جهت را دارد ⇒ جهت **گزینش نمی‌شود** (عیناً `side=both`ِ `S354`).

⚠️ نقدِ آماری بر مدلِ صفرِ رسمی — و چرا اینجا **دو** مدل ساخته می‌شود
---------------------------------------------------------------------
`s354_family.py`/`s346_family.py` برای هر عضو **زمان‌های تصادفیِ مستقل** می‌کشند.
اما اعضای واقعیِ خانواده **هم‌زمان** شلیک می‌کنند: هر ۷۲ عضو یک الگوی واحد
(swing-point fade) را با تنظیماتِ کمی متفاوت می‌بینند، پس ورودهایشان به‌شدت
هم‌بسته است. میانگینِ ۷۲ قرعهٔ **مستقل** واریانسی به‌اندازهٔ `sd²/72` دارد، در حالی
که میانگینِ ۷۲ عضوِ **هم‌بسته** واریانسی نزدیک به `sd²·ρ̄` دارد که بسیار بزرگ‌تر
است. نتیجه: `sd`ِ صفر **کم‌برآورد** و `z` مصنوعاً **بزرگ** می‌شود. این دقیقاً
«دور زدنِ معیار» (اشتباهِ رایجِ #۸) است و انجامش نمی‌دهم.

پس دو مدلِ صفر ساخته و **هر دو** گزارش می‌شود:

  · `INDEP`  — قرعهٔ مستقل برای هر عضو (کنوانسیونِ رسمیِ پروژه؛ خوش‌بینانه).
  · `SHIFT`  — یک **شیفتِ دوّارِ مشترک** `δ` که ورودهای **همهٔ** اعضا را با هم
               جابه‌جا می‌کند. ساختارِ زمانیِ درون‌عضوی و **کلِ هم‌بستگیِ بین‌عضوی**
               دست‌نخورده می‌ماند و فقط رابطهٔ «زمانِ سیگنال ↔ حرکتِ قیمت» شکسته
               می‌شود. این آمارهٔ صفر **همان ساختارِ همبستگیِ مشاهده** را دارد ⇒
               `sd`ِ درست ⇒ **محافظه‌کارانه‌تر**.

**مدلِ حاکم `SHIFT` است.** اگر لایه فقط زیرِ `INDEP` پاس شود، پاس **اعلام نمی‌شود**.

کرانِ چندگانگی در سه سطح (محافظه‌کارتر از پیش‌ثبت)
--------------------------------------------------
    N=1    → کرانِ پیش‌ثبت‌شدهٔ مسیرِ B (هیچ گزینشی)
    N=12   → اگر انتخابِ *براکتِ* منجمد هم یک گزینش شمرده شود
    N=864  → اگر کلِ گریدِ ساختار×براکت بدهکار شمرده شود (تنبیهیِ حداکثری)

اجرا:  python3 strategies/s357b_s341_family_pathB.py --cards site
"""
import argparse
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                  # noqa: E402
from engine.rqs2 import expected_max_z                                 # noqa: E402
from strategies.s357_s341_v24_rejudge import (                         # noqa: E402
    ARCHIVE_CFG, CARDS_ALL, SITE_CARDS, DERIVED,
    W_GRID, BUF_GRID, REGIME_GRID, SECOND_GRID, SIDE_GRID,
    base_features, signals_vec, outcome_table, wr_of, resolve_cfg,
)
from strategies.s341_brooks_swing_levels import _fractal_levels        # noqa: E402

OUT = 'results/_scan_S357B'

K_PERM = 1000          # قرعه در هر مدلِ صفر
SEEDS = (23, 101, 777)
N_LABELS = (('N1', 1), ('N12', 12), ('N864', 864))


def members():
    """۷۲ عضوِ خانواده — **هیچ رتبه‌بندی، هیچ گزینشی**.

    ترتیب صرفاً برای بازتولیدپذیریِ قرعه‌ها تثبیت شده است؛ هیچ عضوی «بهتر» نیست.
    """
    out = []
    for side, w, buf, reg, sec in itertools.product(
            SIDE_GRID, W_GRID, BUF_GRID, REGIME_GRID, SECOND_GRID):
        out.append(dict(side=side, w=w, buf=buf, regime=reg, require_second=sec,
                        stretch=None, exh=None))
    return out


def family_observed(F, fracs, cfg, tables, verbose=True):
    """WRِ هر عضو با براکتِ منجمد؛ خروجی: فهرستِ اعضای «قابلِ‌استفاده»."""
    rows = []
    for mi, m in enumerate(members()):
        sig = signals_vec(F, fracs[m['w']], m['side'], m['w'], m['buf'],
                          m['regime'], m['require_second'], None, None)
        picks = np.flatnonzero(sig)
        res, xbar = tables[m['side']]
        wr = wr_of(picks, res, xbar)
        # `used` را هم لازم داریم: قرعهٔ صفر باید همان تعدادِ ورود را بگذارد
        used = 0
        last_exit = -1
        for si in picks:
            if si + 1 <= last_exit or res[si] == 0:
                continue
            used += 1
            last_exit = xbar[si]
        rows.append(dict(i=mi, side=m['side'], w=m['w'], buf=m['buf'],
                         regime=m['regime'], second=m['require_second'],
                         n_sig=int(picks.size), n_used=used,
                         wr=None if wr is None else round(wr, 4),
                         picks=picks))
    usable = [r for r in rows if r['wr'] is not None and r['n_used'] > 0]
    if verbose:
        wrs = [r['wr'] for r in usable]
        print(f"    family: {len(usable)}/{len(rows)} members usable | "
              f"mean WR={np.mean(wrs):.3f}% | member WR range "
              f"[{min(wrs):.1f}, {max(wrs):.1f}] | total entries="
              f"{sum(r['n_used'] for r in usable)}", flush=True)
    return rows, usable


def null_indep(usable, tables, valid_by_side, rng, k_perm):
    """مدلِ صفرِ `INDEP` — قرعهٔ **مستقل** برای هر عضو (کنوانسیونِ رسمیِ پروژه).

    ⚠️ خوش‌بینانه: هم‌بستگیِ بین‌عضوی را نمی‌بازتاباند ⇒ `sd` کم‌برآورد.
    """
    draws = np.empty(k_perm, dtype=float)
    for d in range(k_perm):
        vals = []
        for r in usable:
            v = valid_by_side[r['side']]
            k = min(r['n_used'], v.size)
            if k <= 0:
                continue
            pick = np.sort(rng.choice(v, size=k, replace=False))
            res, xbar = tables[r['side']]
            wr = wr_of(pick, res, xbar)
            if wr is not None:
                vals.append(wr)
        draws[d] = np.mean(vals) if vals else np.nan
    return draws


def null_shift(usable, tables, n_bars, rng, k_perm):
    """مدلِ صفرِ `SHIFT` — یک **شیفتِ دوّارِ مشترک** برای همهٔ اعضا (حاکم).

    ورودهای هر عضو با هم و با یک `δ`ِ واحد می‌چرخند، پس:
      · فاصله‌های درون‌عضوی حفظ می‌شود (خوشه‌بندیِ زمانیِ سیگنال)،
      · **هم‌پوشانیِ بین‌عضوی حفظ می‌شود** (اعضا هنوز هم‌زمان شلیک می‌کنند)،
      · تنها رابطهٔ «زمانِ سیگنال ↔ قیمت» می‌شکند.
    ⇒ آمارهٔ صفر همان ساختارِ همبستگیِ مشاهده را دارد ⇒ `sd`ِ صادق.
    """
    draws = np.empty(k_perm, dtype=float)
    lo, hi = int(0.02 * n_bars), int(0.98 * n_bars)   # δ خیلی کوچک ≈ عدم‌شیفت
    for d in range(k_perm):
        delta = int(rng.integers(lo, hi))
        vals = []
        for r in usable:
            pick = np.sort((r['picks'] + delta) % n_bars)
            res, xbar = tables[r['side']]
            wr = wr_of(pick, res, xbar)
            if wr is not None:
                vals.append(wr)
        draws[d] = np.mean(vals) if vals else np.nan
    return draws


def summarise(obs, draws, tag):
    d = draws[np.isfinite(draws)]
    if d.size < 2:
        return dict(model=tag, ok=False, note='null degenerate')
    mu, sd = float(d.mean()), float(d.std(ddof=1))
    z = (obs - mu) / sd if sd > 0 else float('inf')
    ge = int((d >= obs - 1e-12).sum())
    p_emp = (1.0 + ge) / (1.0 + d.size)
    out = dict(model=tag, ok=True, k=int(d.size), null_mean=round(mu, 4),
               null_sd=round(sd, 4), null_max=round(float(d.max()), 4),
               obs=round(obs, 4), lift_pp=round(obs - mu, 4), z=round(z, 3),
               ge=ge, p_emp=round(p_emp, 6))
    for name, N in N_LABELS:
        b = float(expected_max_z(N))
        out[f'bound_{name}'] = round(b, 3)
        out[f'pass_{name}'] = bool(z >= b)
    return out


def run_card(card, k_perm=K_PERM, verbose=True):
    asset, tf = card.split('-')
    path = f'data/{asset}_{tf}.csv'
    rec = dict(card=card, asset=asset, tf=tf, k_perm=k_perm)
    if not os.path.exists(path):
        rec['status'] = 'NO_DATA'
        return rec
    df = se.load_data(path)
    cfg, source, _, _ = resolve_cfg(card, df, asset)
    rec.update(source=source, bars=len(df),
               bracket=dict(sl=cfg['sl'], tp=cfg['tp'], mh=cfg['mh']))
    if verbose:
        print(f"\n=== {card} :: source={source} bars={len(df)} "
              f"SL={cfg['sl']} TP={cfg['tp']} mh={cfg['mh']}", flush=True)

    F = base_features(df, cfg)
    fracs = {w: _fractal_levels(F['h'], F['l'], w) for w in W_GRID}
    tables = {s: outcome_table(df, asset, cfg['sl'], cfg['tp'], cfg['mh'], s)
              for s in ('long', 'short')}
    valid_by_side = {s: np.flatnonzero(tables[s][0] != 0) for s in ('long', 'short')}

    rows, usable = family_observed(F, fracs, cfg, tables, verbose=verbose)
    rec['members'] = [{k: v for k, v in r.items() if k != 'picks'} for r in rows]
    rec['n_usable'] = len(usable)
    if len(usable) < 2:
        rec['status'] = 'FAMILY_DEGENERATE'
        return rec
    obs = float(np.mean([r['wr'] for r in usable]))
    rec['obs_family_wr'] = round(obs, 4)
    rec['total_entries'] = int(sum(r['n_used'] for r in usable))
    rec['status'] = 'JUDGED'
    rec['seeds'] = {}

    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        di = null_indep(usable, tables, valid_by_side, rng, k_perm)
        rng2 = np.random.default_rng(seed + 5000)
        ds = null_shift(usable, tables, len(df), rng2, k_perm)
        si = summarise(obs, di, 'INDEP')
        ss = summarise(obs, ds, 'SHIFT')
        rec['seeds'][str(seed)] = dict(INDEP=si, SHIFT=ss)
        if verbose:
            for s in (si, ss):
                if not s.get('ok'):
                    print(f"  seed={seed} {s['model']}: {s.get('note')}", flush=True)
                    continue
                print(f"  seed={seed} {s['model']:5s} null={s['null_mean']:.3f}% "
                      f"sd={s['null_sd']:.3f} | obs={s['obs']:.3f}% "
                      f"lift={s['lift_pp']:+.3f}pp z={s['z']:.2f} "
                      f"p_emp={s['p_emp']:.5f} | "
                      f"N1={'✅' if s['pass_N1'] else '❌'}({s['bound_N1']}) "
                      f"N12={'✅' if s['pass_N12'] else '❌'}({s['bound_N12']}) "
                      f"N864={'✅' if s['pass_N864'] else '❌'}({s['bound_N864']})",
                      flush=True)

    # حکمِ حاکم: `SHIFT` روی **همهٔ** بذرها، در سطحِ `N12` (براکت بدهکار شمرده شود)
    gov = [rec['seeds'][str(s)]['SHIFT'] for s in SEEDS]
    rec['verdict'] = dict(
        governing_model='SHIFT',
        all_seeds_pass_N1=all(g.get('pass_N1') for g in gov),
        all_seeds_pass_N12=all(g.get('pass_N12') for g in gov),
        all_seeds_pass_N864=all(g.get('pass_N864') for g in gov),
        min_z=round(min(g.get('z', -99) for g in gov), 3),
        max_p_emp=max(g.get('p_emp', 1.0) for g in gov))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='site')
    ap.add_argument('--k', type=int, default=K_PERM)
    args = ap.parse_args()
    cards = (SITE_CARDS if args.cards == 'site'
             else CARDS_ALL if args.cards == 'all' else args.cards.split(','))
    os.makedirs(OUT, exist_ok=True)
    for card in cards:
        try:
            rec = run_card(card, k_perm=args.k)
        except Exception as exc:                                    # noqa: BLE001
            rec = dict(card=card, status='ERROR', error=repr(exc))
            print(f"  [ERROR] {card}: {exc!r}", flush=True)
        with open(os.path.join(OUT, f'{card}.json'), 'w', encoding='utf-8') as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1, default=float)
        v = rec.get('verdict') or {}
        print(f"  [saved] {OUT}/{card}.json status={rec.get('status')} "
              f"SHIFT_N12={v.get('all_seeds_pass_N12')}", flush=True)


if __name__ == '__main__':
    main()
