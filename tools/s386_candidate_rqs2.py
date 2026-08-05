# -*- coding: utf-8 -*-
"""S386 گامِ ۲ — **ارزیابیِ کاملِ rqs2 + مدلِ صفر برای نامزدهای تجمیعِ پرتفوی.**

════════════════════════════════════════════════════════════════════════════
چه چیزی آزموده می‌شود
════════════════════════════════════════════════════════════════════════════
گامِ ۱ (`results/S386_STEP1_OVERLAP_VS_S382.md`) پنج نامزد را با
همپوشانیِ `jac_tol < 0.19` نسبت به لایهٔ پذیرفته‌شدهٔ S382 شناسایی کرد.
همپوشانیِ اندک، شرطِ **لازم** برای تجمیع است، ولی به‌هیچ‌وجه **کافی**
نیست: یک قاعدهٔ ناهمپوشانِ بی‌کیفیت، نرخِ کل را بالا می‌برد و لبه را
رقیق می‌کند. پس هر نامزد باید **به‌تنهایی** معیارِ پروژه را پاس کند —
این صریحاً در تعریفِ سودِ خالصِ پروژه آمده است:

    «... در شرایطی که هر لایه از استراتژی به تنهایی معیار پروژه رو پاس کند»

════════════════════════════════════════════════════════════════════════════
چهار انتخابِ طراحی، هر یک بر ضدِ یک خطای مشخص
════════════════════════════════════════════════════════════════════════════

① **همان شبیه‌سازِ S382/S384 استفاده می‌شود، نه نسخهٔ دوم.**
   `simulate_trades`، `atr`، `pip_size` و `load` همه از ماژولِ S382
   می‌آیند و مدلِ صفر از `s382_null_model`. علت: اگر نامزدِ نو با
   شبیه‌سازِ دیگری سنجیده شود، تفاوتِ شبیه‌ساز با تفاوتِ کیفیت اشتباه
   گرفته می‌شود. پروژه یک‌بار از این آسیب دیده (دانشِ سربه‌سر در یک
   ابزار بود و در ابزارِ حسابرسی نبود).

② **مدلِ صفر برای هر (کارت، قاعده، هندسه) از نو ساخته می‌شود.**
   درسِ قاطعِ S384/S385: `perm_max` تابعی از **تعدادِ معامله** است، نه
   یک ثابتِ کارت. با n کمتر، `perm_sd` بزرگ‌تر و دمِ شانس بلندتر
   می‌شود. بازاستفاده از مدلِ صفرِ S382 (که n=۸۶۹ داشت) برای نامزدی با
   n=۳۳۸ **سقفِ شانس را کم‌برآورد** می‌کند و پذیرشِ کاذب می‌سازد.

③ **قاعده از `step1_rule_bank` وارد می‌شود، بازنویسی نمی‌شود.**
   تا سیگنال‌ها بیت‌به‌بیت همان چیزی باشند که آرشیوِ ۲۳٬۷۵۵ آزمون و
   ماتریسِ همپوشانیِ گامِ ۱ استفاده کردند. هرگونه بازنویسی، زنجیرهٔ
   استنتاج را می‌شکند.

④ **`n_trials` صادقانه شمرده می‌شود.**
   ۲۳٬۷۵۵ (جست‌وجویِ raw-edge) + ۳۰ (شبکهٔ S384) + ۵ (این نامزدها)
   = ۲۳٬۷۹۰. کم‌شمردنِ سابقهٔ جست‌وجو دقیقاً «دور زدنِ معیارِ پروژه» است
   که در اشتباهاتِ رایج ممنوع شده.

════════════════════════════════════════════════════════════════════════════
هشدارِ توانِ آماری — پیش از اندازه‌گیری ثبت شد
════════════════════════════════════════════════════════════════════════════
برای دیدنِ لبهٔ ~۵.۵ واحدی با توانِ ۸۰٪ حدودِ ۶۵۰ معامله لازم است.
بزرگ‌ترین نامزد ۵۳۸ معامله دارد. پس انتظار می‌رود دروازهٔ توان برای
بیشترشان مرزی یا ناموفق باشد. این پیش‌بینی در گامِ ۱ ثبت شد و اگر
محقق شود، **ردِ آنها اطلاعات حمل می‌کند** (نه مثل ۶۴٪ آرشیوِ پروژه که
با ابزارِ کم‌توان سنجیده شدند و ردشان صفر اطلاعات داشت).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R                                    # noqa: E402

OUT = 'results/_s386'
COST_PIP = 3.3
SEED = 20260805
K = 2000
N_TRIALS = 23790            # ۲۳٬۷۵۵ سابقه + ۳۰ شبکهٔ S384 + ۵ نامزدِ اینجا
SITE_TARGET = 252.0

# ── پنج نامزدِ قفل‌شده در گامِ ۱ ────────────────────────────────────────
# (کارت، نامِ قاعده، sl_k، rr)  — هیچ‌یک `rr=1.0` نیست (اشتباهِ رایجِ ۸)
CANDIDATES = [
    ('XAUUSD_H4', 'willr27_xdn_-13', 2.0, 2.0),
    ('XAUUSD_H4', 'stoch33_xdn_80',  2.0, 2.0),
    ('XAUUSD_H4', 'rsi9_xdn_70',     2.0, 2.0),
    ('XAUUSD_H4', 'cci20_xdn_135',   2.0, 1.5),
    ('XAUUSD_H4', 'rsi14_xdn_70',    2.0, 1.5),
]


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_one(card, rule_name, sl_k, rr, L, NM, RB, df, atr_med, ps, sig):
    """یک نامزد را کاملاً می‌آزماید: شبیه‌ساز + مدلِ صفر + ۱۱ دروازهٔ rqs2."""
    asset = card.split('_')[0]
    sl_abs = atr_med * sl_k
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * rr
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    cost_share = 100.0 * COST_PIP / sl_pip

    n_sig = int(sig.fillna(False).sum())
    tr = L.simulate_trades(df, sig, sl_abs, rr, True, ps)
    base = dict(card=card, rule=rule_name, sl_k=sl_k, rr=rr,
                span_years=round(span, 2), n_signals=n_sig,
                n_trades=len(tr), sl_pip=round(sl_pip, 2),
                tp_pip=round(tp_pip, 2),
                cost_share_pct=round(cost_share, 2))
    if len(tr) < 30:
        base['verdict'] = 'TOO_FEW_TRADES'
        return base

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())

    # ── مدلِ صفرِ **همین** نامزد — هرگز بازاستفاده (درسِ S385) ──────────
    #
    # ⚠️ نکتهٔ حیاتیِ صحت: **هر دو** خطِ مبنا هندسه را از `L.RR` می‌گیرند
    # (`uncond_baseline` در سطرِ ۱۰۵ و `perm_baseline` در سطرِ ۱۲۹ از
    # `s382_null_model.py`). اگر `L.RR` جایگزین نشود، خریدارِ کور با
    # هندسهٔ لایهٔ S382 (rr=1.5) ساخته می‌شود در حالی که نامزد rr=2.0
    # دارد — و مقایسه بی‌اعتبار است، چون با TPِ دورتر، خریدارِ کور
    # ریاضیاً باید WRِ **پایین‌تری** بگیرد. اجرای نخستِ این ابزار همین
    # باگ را داشت: `uncond_wr` برای هر پنج نامزد دقیقاً ۴۱.۸۷ آمد
    # (غیرممکن)، در حالی که `perm_mean` درست تفکیک شد (۳۵.۹ در برابر
    # ۴۲.۰). پس **هر دو** فراخوانی داخلِ بلوکِ جایگزینی قرار می‌گیرند.
    _rr_backup = L.RR
    try:
        L.RR = rr
        # خطِ مبنای ①: ورود در هر کندل، **سخت‌ترین** گامِ نمونه‌برداری.
        unc = max(NM.uncond_baseline(L, df, sl_abs, ps, s)[0] or -1e9
                  for s in (1, 3, 7))
        # خطِ مبنای ②: همان تعدادِ سیگنال، زمان‌بندیِ تصادفی.
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
        # ── شرایطِ پیش‌ثبت‌شده، هر یک جداگانه ─────────────────────────
        c1_lift_pos=bool(wr - be > 0),
        c2_beats_uncond=bool(wr > unc),
        c3_beats_perm_max=bool(wr > perm['max']),
        c5_accept=bool(res.get('verdict') == 'ACCEPT'),
    )
    base['all_four'] = bool(base['c1_lift_pos'] and base['c2_beats_uncond']
                            and base['c3_beats_perm_max']
                            and base['c5_accept'])
    return base


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    # `build_rules()` لیستی از تاپل‌های (نام، تابع) برمی‌گرداند — به نگاشت
    # تبدیل می‌شود تا نامزدها با **نامِ دقیقِ آرشیو** آدرس‌دهی شوند.
    bank = dict(RB.build_rules())
    print(f'S386 candidate rqs2 | n_trials={N_TRIALS} | K={K} | seed={SEED}')
    print(f'rule bank: {len(bank)} rules available')
    print()
    hdr = (f'{"rule":18s} {"k":>4s} {"rr":>4s} {"nsig":>6s} {"n":>6s} '
           f'{"/yr":>6s} {"held":>6s} {"wr":>6s} {"be":>6s} {"lift":>7s} '
           f'{"unc":>6s} {"alpha":>7s} {"pmax":>6s} {"gap":>6s} '
           f'{"z":>6s} {"rqs2":>6s} verdict')
    print(hdr)
    print('-' * len(hdr))

    want = sys.argv[1:]
    cache = {}
    for card, rule_name, sl_k, rr in CANDIDATES:
        if want and rule_name not in want:
            continue
        if card not in cache:
            df = L.load(card)
            ps = L.pip_size(card.split('_')[0])
            atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
            cache[card] = (df, ps, atr_med)
        df, ps, atr_med = cache[card]
        fn = bank.get(rule_name)
        if fn is None:
            print(f'{rule_name:18s} RULE NOT IN BANK')
            continue
        try:
            sig = fn(df)
            r = run_one(card, rule_name, sl_k, rr, L, NM, RB,
                        df, atr_med, ps, sig)
        except Exception as e:
            print(f'{rule_name:18s} ERROR {type(e).__name__}: {str(e)[:70]}')
            continue
        # ذخیرهٔ فوری — قانونِ «اندک اندک»، پنج ریستِ سندباکس آن را توجیه کرد
        tag = rule_name.replace('/', '_')
        with open(f'{OUT}/{card}_{tag}_k{sl_k}_rr{rr}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        if r.get('verdict') == 'TOO_FEW_TRADES':
            print(f'{rule_name:18s} {sl_k:4.1f} {rr:4.1f} '
                  f'{r["n_signals"]:6d} {r["n_trades"]:6d} TOO_FEW_TRADES')
            continue
        gap = r['wr'] - r['perm_max']
        print(f'{rule_name:18s} {sl_k:4.1f} {rr:4.1f} {r["n_signals"]:6d} '
              f'{r["n_trades"]:6d} {r["per_year"]:6.1f} '
              f'{r["avg_held_bars"]:6.1f} {r["wr"]:6.2f} {r["be"]:6.2f} '
              f'{r["lift"]:+7.2f} {r["uncond_wr"]:6.2f} {r["alpha"]:+7.2f} '
              f'{r["perm_max"]:6.2f} {gap:+6.2f} '
              f'{(r["z"] if r["z"] is not None else float("nan")):6.2f} '
              f'{(r["rqs2"] if r["rqs2"] is not None else float("nan")):6.1f} '
              f'{r["verdict"]}')
    print()
    print('done.')


if __name__ == '__main__':
    main()
