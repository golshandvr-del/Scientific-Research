# -*- coding: utf-8 -*-
"""S382 — اجرایِ **مولتی-تایم‌فریم** طبقِ قانونِ اولِ پروژه.

═══════════════════════════════════════════════════════════════════════════
قانونِ MTF چه می‌خواهد
═══════════════════════════════════════════════════════════════════════════

«هر لایهٔ جدید باید به طورِ مجزا روی هریک از تایم‌فریم‌ها تست شده و
نتیجه گزارش و بررسی شود.» و «اگر لایه‌ای در چندین تایم‌فریم موفق شد،
باید در سایت منطقِ مربوط به همهٔ تایم‌فریم‌های تاییدشده اعمال شود.»

پس S382 که روی `XAUUSD_H4` پاس شد، **کافی نیست**. باید روی هر کارت
مستقلاً آزموده شود — روی طلا و یورو، در همهٔ تایم‌فریم‌ها.

═══════════════════════════════════════════════════════════════════════════
تصمیمِ کلیدی: پارامترها **قفل** می‌مانند
═══════════════════════════════════════════════════════════════════════════

`WILLR_P=14`، `WILLR_THR=-13`، `SL_K=1.5`، `RR=1.5` روی **هیچ** کارتی
تغییر نمی‌کنند. این تصمیم عمدی است و دو دلیلِ متفاوت دارد:

۱) **صداقتِ آماری.** اگر برای هر کارت آستانه را بهینه کنم، بارِ
   چندگانگی ضرب در تعدادِ کارت‌ها می‌شود و z سقوط می‌کند. بدتر:
   هر کارت یک «موفقیت» می‌سازد که در واقع برازشِ همان کارت است.
   قانونِ «شاید همه چیز شناور است» اجازهٔ متغیرکردنِ پارامتر می‌دهد،
   ولی آن قانون برای **نجاتِ لایهٔ سوخته** است، نه برای تکثیرِ یک
   موفقیتِ موجود با برازشِ مجدد.

۲) **آزمونِ اصالت.** اگر یک لبه **واقعی** باشد، باید با پارامترِ ثابت
   روی چند کارت ظاهر شود (حتی ضعیف‌تر). اگر فقط با پارامترِ خاصِ هر
   کارت ظاهر شود، آن لبه نیست — نویزِ برازش‌شده است. پس این اجرا
   همزمان یک **آزمونِ اعتبارِ خارجی** برای خودِ S382 است.

⚠️ آنچه **باید** روی هر کارت متفاوت باشد: `SL` مطلق. چون از
`ATR(100)`ِ همان کارت می‌آید، خودکار مقیاس می‌گیرد — روی H4 برابر
۱۲۲.۸۵ pip و روی M30 عددِ بسیار کوچک‌تری. این دقیقاً ضدِ اشتباهِ رایجِ
#۶ (هندسهٔ یکسان برای همه تایم‌فریم‌ها) است و **بدونِ** هیچ برازشی
حاصل می‌شود.

═══════════════════════════════════════════════════════════════════════════
مدلِ صفر برای **هر کارت** جداگانه
═══════════════════════════════════════════════════════════════════════════

خطِ مبنای بی‌مهارت روی هر کارت متفاوت است، چون روندِ دارایی و نسبتِ
هزینه به ATR فرق می‌کند. استفاده از مدلِ صفرِ H4 برای M30 یک خطای
فاحش می‌بود. پس برای هر کارت، دو خطِ مبنا از نو اندازه‌گیری می‌شود.

═══════════════════════════════════════════════════════════════════════════
ذخیرهٔ مرحله‌به‌مرحله (قانونِ سومِ پروژه: «اندک اندک»)
═══════════════════════════════════════════════════════════════════════════

نتیجهٔ هر کارت **بلافاصله** روی دیسک نوشته می‌شود. چهار ریستِ سندباکس
در این پروژه نشان داد این یک احتیاطِ نظری نیست.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2 as R          # noqa: E402

OUT = 'results/_s382_mtf'
SEED = 20260805
K = 2000
N_TRIALS = 23755                       # همان فضای جست‌وجوی اسکنِ خام

# ترتیب: بلندترین تاریخ اول (یافتهٔ سرشماری: توان اثبات از بازه می‌آید).
# D1/W1 حذف نمی‌شوند — عمداً آزموده می‌شوند تا یافتهٔ «سقفِ ساختاری»
# روی این لایه هم **آزمون** شود، نه فرض.
CARDS = [
    'XAUUSD_H4', 'XAUUSD_H1', 'XAUUSD_M30', 'XAUUSD_D1',
    'EURUSD_H4', 'EURUSD_H1', 'EURUSD_M30', 'EURUSD_D1',
    'XAUUSD_M15', 'EURUSD_M15', 'XAUUSD_M5', 'EURUSD_M5',
]


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_card(card, L, NM):
    """یک کارت را کاملاً می‌آزماید: معاملات + مدلِ صفر + هر ۱۱ دروازه."""
    asset = card.split('_')[0]
    df = L.load(card)
    ps = L.pip_size(asset)
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * L.RR
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25

    sig = L.signals(df)
    n_sig = int(sig.fillna(False).sum())
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    if len(tr) < 30:
        return dict(card=card, span_years=round(span, 2), n_signals=n_sig,
                    n_trades=len(tr), verdict='TOO_FEW_TRADES',
                    sl_pip=round(sl_pip, 2))

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + 3.3) / (tp_pip + sl_pip)

    # ── مدلِ صفرِ **همان کارت** — هرگز بازاستفاده از کارتِ دیگر ──────
    unc = max(NM.uncond_baseline(L, df, sl_abs, ps, s)[0] or -1e9
              for s in (1, 3, 7))
    perm = NM.perm_baseline(L, df, sl_abs, ps, n_sig, k=K, seed=SEED)
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
    return dict(
        card=card, span_years=round(span, 2), n_signals=n_sig,
        n_trades=len(tr), per_year=round(len(tr) / span, 1),
        sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        pf=m.get('profit_factor'), net=m.get('net_profit'),
        uncond_wr=round(unc, 2), perm_mean=round(perm['mean'], 2),
        perm_max=round(perm['max'], 2), perm_sd=round(perm['sd'], 2),
        beats_perm_max=bool(wr > perm['max']),
        z=m.get('skill_z'), rqs2=res.get('rqs2_score'),
        verdict=res.get('verdict'), gates=res.get('gates'),
        notes=[str(x)[:110] for x in (res.get('notes') or [])],
    )


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    cards = sys.argv[1:] or CARDS
    print(f'S382 MTF | params LOCKED: willr({L.WILLR_P})>{L.WILLR_THR} '
          f'sl_k={L.SL_K} rr={L.RR} side=long | k={K} n_trials={N_TRIALS}')
    print()
    hdr = (f'{"card":13s} {"span":>6s} {"n":>5s} {"/yr":>6s} {"slpip":>7s} '
           f'{"wr":>6s} {"be":>6s} {"lift":>6s} {"unc":>6s} {"pmax":>6s} '
           f'{"z":>5s} {"rqs2":>6s} verdict')
    print(hdr)
    print('-' * len(hdr))
    for card in cards:
        try:
            r = run_card(card, L, NM)
        except Exception as e:
            print(f'{card:13s} ERROR {str(e)[:70]}')
            continue
        # ذخیرهٔ فوری — قانونِ «اندک اندک»
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        if r.get('verdict') == 'TOO_FEW_TRADES':
            print(f'{card:13s} {r["span_years"]:6.2f} {r["n_trades"]:5d} '
                  f'{"":>6s} {r["sl_pip"]:7.1f} {"":>6s} {"":>6s} {"":>6s} '
                  f'{"":>6s} {"":>6s} {"":>5s} {"":>6s} TOO_FEW_TRADES')
            continue
        z = r.get('z')
        print(f'{card:13s} {r["span_years"]:6.2f} {r["n_trades"]:5d} '
              f'{r["per_year"]:6.1f} {r["sl_pip"]:7.1f} {r["wr"]:6.2f} '
              f'{r["be"]:6.2f} {r["lift"]:+6.2f} {r["uncond_wr"]:6.2f} '
              f'{r["perm_max"]:6.2f} '
              f'{(f"{z:5.2f}" if isinstance(z,(int,float)) else "  n/a")} '
              f'{(r.get("rqs2") or 0):6.1f} {r.get("verdict")}')


if __name__ == '__main__':
    main()
