# -*- coding: utf-8 -*-
"""S386 گامِ ۳ — **لایهٔ ادغامی (union layer): تجمیع در سطحِ سیگنال، نه پرتفوی.**

════════════════════════════════════════════════════════════════════════════
چرا این گام لازم شد — زنجیرهٔ استنتاج
════════════════════════════════════════════════════════════════════════════
گامِ ۲ پنج نامزد را با آلفای **مثبتِ واقعی** (+۳.۲۵ تا +۴.۵۹ در برابرِ
خریدارِ کورِ اندازه‌گیری‌شده) پیدا کرد، ولی هر پنج رد شدند. حسابِ توان
علتِ ردشان را بی‌ابهام تعیین کرد:

    قاعده              آلفا    n فعلی   n لازم برای z=4.07   نسبت
    willr27_xdn_-13   +4.01      538          2472          4.6×
    cci20_xdn_135     +4.59      353          1953          5.5×
    stoch33_xdn_80    +3.61      473          3040          6.4×
    rsi14_xdn_70      +3.99      338          2580          7.6×
    rsi9_xdn_70       +3.25      452          3738          8.3×

پس مشکل **نبودِ لبه نیست، کمبودِ معامله است** — همان تشخیصی که در آغازِ
این پژوهش برای کلِ پروژه داده شد. و راهِ حلِ ساختاریِ کمبودِ معامله،
جمع‌کردنِ نمونه است.

════════════════════════════════════════════════════════════════════════════
تفاوتِ بنیادیِ «تجمیعِ پرتفوی» و «لایهٔ ادغامی»
════════════════════════════════════════════════════════════════════════════
تجمیعِ پرتفوی (که پیش‌ثبتِ S386 در نظر داشت) شش لایهٔ **جدا** را کنارِ
هم می‌گذارد؛ هرکدام باید خودش معیار را پاس کند و هیچ‌کدام نمی‌کند.

لایهٔ ادغامی یک چیزِ کاملاً متفاوت است: **یک** لایه که سیگنالش اجتماعِ
شرطِ چند قاعده است (`OR`). این یک استراتژیِ واحد است، پس:

  ✅ نمونه‌اش جمع می‌شود ⇒ توانِ آماری ساخته می‌شود
  ✅ یک هندسه دارد ⇒ مقایسه با مدلِ صفر معنادار است
  ✅ یک بارِ چندگانگی دارد، نه شش تا
  ⚠️ ولی آلفایش **میانگینِ وزنیِ** آلفاهاست، نه جمعِ آنها

آن هشدارِ سوم حیاتی است و پیش از اندازه‌گیری ثبت می‌شود: ادغام، آلفا را
**رقیق** می‌کند اگر اعضا آلفاهای نامساوی داشته باشند. جمعِ نمونه توان را
با √n می‌سازد ولی رقیق‌شدنِ آلفا خطی است، پس ادغام فقط وقتی برنده است
که آلفاها **نزدیک** باشند. آلفاهای ما ۳.۲۵ تا ۴.۵۹ — دامنهٔ ۱.۳۴ واحد
حولِ میانگینِ ~۳.۹. این نسبتاً همگن است، پس ادغام شانس دارد.

════════════════════════════════════════════════════════════════════════════
چهار ترکیبِ پیش‌ثبت‌شده — و چرا **همین چهار**
════════════════════════════════════════════════════════════════════════════
① `U5`   — پنج قاعدهٔ `xdn`
     خالص‌ترین آزمونِ ادغام: همه هم‌خانواده (خروج از اشباعِ خرید)، همه
     با آلفای مثبت، و همپوشانیِ زوجی‌شان حداکثر ۰.۳۲۶.

② `U3`   — سه قاعده با بالاترین آلفا: `cci20_xdn_135`, `willr27_xdn_-13`,
     `rsi14_xdn_70` (آلفا ۴.۵۹، ۴.۰۱، ۳.۹۹)
     آزمونِ فرضیهٔ رقیق‌شدن: اگر ادغام آلفا را رقیق می‌کند، حذفِ دو عضوِ
     ضعیف‌تر باید آلفای بالاتری بدهد. این ترکیب **صریحاً** برای سنجشِ
     همان مکانیزم انتخاب شد، نه برای بهینه‌سازی.

③ `U6`   — پنج `xdn` + قاعدهٔ S382 (`willr14_xup_-13`)
     بزرگ‌ترین نمونهٔ ممکن. عضوِ ششم آلفای ۷.۹۳ دارد (بالاترین)، پس
     باید آلفای ادغام را **بالا** ببرد و نمونه را هم بیشینه کند.
     ⚠️ ولی این ترکیب لایهٔ پذیرفته‌شده را می‌بلعد؛ اگر برنده شود،
     جانشینِ S382 است نه مکملِ آن. این در گزارش صریح گفته می‌شود.

④ `U2`   — `cci20_xdn_135` + `willr14_xup_-13`
     مستقل‌ترین زوجِ ممکن (ژاکاردِ ۰.۰۱۰۵، گشاد ۰.۰۷۳۷) با دو بالاترین
     آلفا. کم‌ترین رقیق‌شدگیِ نظری.

هیچ ترکیبِ دیگری آزموده نمی‌شود. علت: هر ترکیبِ اضافه یک آزمونِ اضافه
است و بارِ چندگانگی را بالا می‌برد. چهار ترکیب در `n_trials` شمرده شده.

════════════════════════════════════════════════════════════════════════════
هندسه: چرا `rr` هم آزموده می‌شود ولی `rr=1.0` هرگز
════════════════════════════════════════════════════════════════════════════
اعضا هندسه‌های متفاوت داشتند (rr=1.5 و rr=2.0)، پس لایهٔ ادغامی
نمی‌تواند هندسهٔ «آنها» را به ارث ببرد — باید هندسهٔ خودش را داشته باشد.
دو مقدار آزموده می‌شود: `rr ∈ {1.5, 2.0}`.

`rr = 1.0` **عمداً و صریحاً حذف شده** — اشتباهِ رایجِ ۸. جدولِ خامِ
نامزدها نشان داد `rr=1.0` روی همین کارت WRِ ۵۸.۸٪ می‌دهد که وسوسه‌انگیز
است و کاملاً بی‌ارزش. هیچ سلولی از این ابزار نمی‌تواند از آن کانال
بیاید.

`sl_k = 2.0` قفل است (همان مقدارِ هر پنج نامزد) تا محورِ آزاد فقط یکی
باشد و بارِ چندگانگی حداقل بماند.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R                                    # noqa: E402

OUT = 'results/_s386_union'
COST_PIP = 3.3
SEED = 20260805
K = 2000
SITE_TARGET = 252.0
CARD = 'XAUUSD_H4'
SL_K = 2.0
RR_GRID = [1.5, 2.0]              # rr=1.0 عمداً حذف — اشتباهِ رایجِ ۸

XDN5 = ['willr27_xdn_-13', 'stoch33_xdn_80', 'rsi9_xdn_70',
        'cci20_xdn_135', 'rsi14_xdn_70']
S382 = 'willr14_xup_-13'

COMBOS = {
    'U5': XDN5,
    'U3': ['cci20_xdn_135', 'willr27_xdn_-13', 'rsi14_xdn_70'],
    'U6': XDN5 + [S382],
    'U2': ['cci20_xdn_135', S382],
}

# ۲۳٬۷۵۵ raw-edge + ۳۰ شبکهٔ S384 + ۵ نامزد + ۸ سلولِ اینجا (۴ ترکیب × ۲ rr)
N_TRIALS = 23798


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_one(combo, members, rr, L, NM, df, atr_med, ps, sigs):
    """یک لایهٔ ادغامی را کاملاً می‌آزماید."""
    asset = CARD.split('_')[0]
    sl_abs = atr_med * SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * rr
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    cost_share = 100.0 * COST_PIP / sl_pip

    # ── اجتماعِ سیگنال‌ها (OR) — این تمامِ منطقِ لایهٔ ادغامی است ────────
    u = pd.Series(False, index=df.index)
    for mname in members:
        u = u | sigs[mname].fillna(False)
    n_sig = int(u.sum())
    # جمعِ سادهٔ اعضا، برای اندازه‌گیریِ صرفه‌جوییِ اجتماع
    naive = int(sum(int(sigs[m].fillna(False).sum()) for m in members))

    tr = L.simulate_trades(df, u, sl_abs, rr, True, ps)
    base = dict(card=CARD, combo=combo, members=members, n_members=len(members),
                sl_k=SL_K, rr=rr, span_years=round(span, 2),
                n_signals=n_sig, n_signals_naive_sum=naive,
                union_efficiency=round(n_sig / naive, 4) if naive else None,
                n_trades=len(tr), sl_pip=round(sl_pip, 2),
                tp_pip=round(tp_pip, 2),
                cost_share_pct=round(cost_share, 2))
    if len(tr) < 30:
        base['verdict'] = 'TOO_FEW_TRADES'
        return base

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())

    # ── مدلِ صفرِ **همین** ترکیب و **همین** هندسه ─────────────────────
    # هر دو خطِ مبنا داخلِ بلوکِ جایگزینیِ L.RR — باگِ گامِ ۲ تکرار نشود.
    _rr_backup = L.RR
    try:
        L.RR = rr
        unc = max(NM.uncond_baseline(L, df, sl_abs, ps, s)[0] or -1e9
                  for s in (1, 3, 7))
        perm = NM.perm_baseline(L, df, sl_abs, ps, n_sig, k=K, seed=SEED)
    finally:
        L.RR = _rr_backup

    null = {'long': dict(uncond_wr=unc, perm_mean=perm['mean'],
                         perm_sd=perm['sd'], perm_max=perm['max'],
                         perm_k=perm['k']),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}

    res = R.compute_rqs2(tr, asset, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=df['time'].to_numpy(),
                         close=df['close'].to_numpy(float), null=null,
                         n_trials=N_TRIALS, split_bar=int(0.70 * len(df)))
    m = res.get('metrics') or {}
    per_year = len(tr) / span

    base.update(
        per_year=round(per_year, 1), avg_held_bars=round(held, 1),
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        uncond_wr=round(unc, 2), alpha=round(wr - unc, 2),
        perm_mean=round(perm['mean'], 2), perm_max=round(perm['max'], 2),
        perm_sd=round(perm['sd'], 2),
        pf=m.get('profit_factor'), net=m.get('net_profit'),
        z=m.get('skill_z'), rqs2=res.get('rqs2_score'),
        verdict=res.get('verdict'), gates=res.get('gates'),
        n_fail=res.get('n_fail'), n_unknown=res.get('n_unknown'),
        power_limited=res.get('power_limited'),
        c1_lift_pos=bool(wr - be > 0),
        c2_beats_uncond=bool(wr > unc),
        c3_beats_perm_max=bool(wr > perm['max']),
        c4_site_rate=bool(per_year >= SITE_TARGET),
        c5_accept=bool(res.get('verdict') == 'ACCEPT'),
    )
    base['all_five'] = bool(base['c1_lift_pos'] and base['c2_beats_uncond']
                            and base['c3_beats_perm_max']
                            and base['c4_site_rate'] and base['c5_accept'])
    return base


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    bank = dict(RB.build_rules())

    df = L.load(CARD)
    ps = L.pip_size(CARD.split('_')[0])
    atr_med = float(np.nanmedian(L.atr(df).to_numpy()))

    needed = sorted({m for ms in COMBOS.values() for m in ms})
    sigs = {m: bank[m](df) for m in needed}

    print(f'S386 union layer | card={CARD} sl_k={SL_K} rr_grid={RR_GRID} '
          f'| n_trials={N_TRIALS} K={K}')
    print(f'materialised {len(sigs)} member signals')
    print()
    hdr = (f'{"combo":6s} {"rr":>4s} {"mem":>4s} {"nsig":>6s} {"naive":>6s} '
           f'{"eff":>6s} {"n":>6s} {"/yr":>6s} {"held":>6s} {"wr":>6s} '
           f'{"be":>6s} {"lift":>7s} {"unc":>6s} {"alpha":>7s} {"pmax":>6s} '
           f'{"gap":>6s} {"z":>6s} {"rqs2":>6s} verdict')
    print(hdr)
    print('-' * len(hdr))

    want = sys.argv[1:]
    for combo, members in COMBOS.items():
        if want and combo not in want:
            continue
        for rr in RR_GRID:
            try:
                r = run_one(combo, members, rr, L, NM, df, atr_med, ps, sigs)
            except Exception as e:
                print(f'{combo:6s} {rr:4.1f} ERROR '
                      f'{type(e).__name__}: {str(e)[:60]}')
                continue
            # ذخیرهٔ فوری — قانونِ «اندک اندک»
            with open(f'{OUT}/{CARD}_{combo}_rr{rr}.json', 'w') as f:
                json.dump(r, f, ensure_ascii=False, default=str)
            if r.get('verdict') == 'TOO_FEW_TRADES':
                print(f'{combo:6s} {rr:4.1f} TOO_FEW_TRADES')
                continue
            gap = r['wr'] - r['perm_max']
            print(f'{combo:6s} {rr:4.1f} {r["n_members"]:4d} '
                  f'{r["n_signals"]:6d} {r["n_signals_naive_sum"]:6d} '
                  f'{r["union_efficiency"]:6.3f} {r["n_trades"]:6d} '
                  f'{r["per_year"]:6.1f} {r["avg_held_bars"]:6.1f} '
                  f'{r["wr"]:6.2f} {r["be"]:6.2f} {r["lift"]:+7.2f} '
                  f'{r["uncond_wr"]:6.2f} {r["alpha"]:+7.2f} '
                  f'{r["perm_max"]:6.2f} {gap:+6.2f} '
                  f'{(r["z"] if r["z"] is not None else float("nan")):6.2f} '
                  f'{(r["rqs2"] if r["rqs2"] is not None else float("nan")):6.1f} '
                  f'{r["verdict"]}')
    print()
    print('done.')


if __name__ == '__main__':
    main()
