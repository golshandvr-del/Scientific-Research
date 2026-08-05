# -*- coding: utf-8 -*-
"""S384 — آزمونِ **حدِ‌ضررِ پهن روی کارت‌های پرفرکانس** (راه ۱ از S383).

════════════════════════════════════════════════════════════════════════════
چه چیزی آزموده می‌شود
════════════════════════════════════════════════════════════════════════════
S383 اندازه‌گیری کرد که نسبتِ هزینه/SL، سربه‌سر را با همبستگیِ +۱.۰۰۰۰
تعیین می‌کند و lift را با −۰.۹۴۴۵ نابود. زنجیرهٔ تضاد این بود:

    فرکانس ⇒ TFِ کوتاه ⇒ ATR کوچک ⇒ SL کوچک ⇒ هزینه/SL بزرگ ⇒ سربه‌سرِ بلند

این اسکریپت زنجیره را در **حلقهٔ چهارم** می‌شکند: SL را مستقل از ATRِ
کوچک، پهن می‌کند. اگر lift مثبت شود **و** فرکانس بالای ۲۵۲/سال بماند،
هدفِ سایت حل شده است.

════════════════════════════════════════════════════════════════════════════
سه انتخابِ طراحی، هر یک بر ضدِ یک خطای مشخص
════════════════════════════════════════════════════════════════════════════

① **مدلِ صفر برای هر (کارت، sl_k) از نو ساخته می‌شود.**
   نه یک‌بار برای هر کارت. علت در پیش‌ثبت ثبت شد: با SL و TPِ پهن‌تر،
   یک لایهٔ long بیشتر به رانشِ صعودیِ طلا نزدیک می‌شود. اگر مدلِ صفرِ
   `sl_k=1.5` روی `sl_k=9.0` بازاستفاده شود، بتای بازار به‌جای آلفا
   شمرده می‌شود — و این **همان** تله‌ای است که XAUUSD_D1 در MTF در آن
   افتاد (خریدارِ کور ۴۵.۷۵ در برابرِ لایه ۴۴.۵۹).

② **`sl_k=1.5` به‌عنوانِ شاهدِ درونی حاضر است.**
   نتیجه‌اش باید *دقیقاً* با فایل‌های `results/_s382_mtf/` بخواند. اگر
   نخواند، یک باگ داریم و کلِ سند باطل است. این ارزان‌ترین آزمونِ صحت
   ممکن است: صفر هزینهٔ اضافه، چون این ردیف به‌هرحال لازم است تا اثرِ
   پهن‌کردن نسبت به مبنا سنجیده شود.

③ **`n_trials = 23785` صادقانه.**
   ۲۳٬۷۵۵ (جست‌وجویِ raw-edge که ما را به این قاعده رساند) + ۳۰ (این شبکه).
   کم‌شمردنِ سابقهٔ جست‌وجو، دقیقاً دور زدنِ معیار است.

════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import os
import sys
import json
import importlib.util
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R                                    # noqa: E402

OUT = 'results/_s384'
COST_PIP = 3.3
SEED = 20260805
K = 2000
N_TRIALS = 23785            # ۲۳٫۷۵۵ سابقه + ۳۰ این شبکه
SITE_TARGET = 252.0
RQS2_FLOOR = 50.0

# شبکهٔ قفل‌شده در پیش‌ثبت S384 — تنها محورِ آزاد
SL_K_GRID = [1.5, 3.0, 4.5, 6.0, 9.0]

CARDS = ['XAUUSD_M30', 'XAUUSD_M15', 'XAUUSD_M5',
         'EURUSD_M30', 'EURUSD_M15', 'EURUSD_M5']


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_one(card, sl_k, L, NM, df, atr_med, ps):
    """یک ترکیبِ (کارت، sl_k) را کاملاً می‌آزماید.

    `df` و `atr_med` از بیرون داده می‌شوند تا برای هر ۵ مقدارِ `sl_k` روی
    یک کارت، داده **یک‌بار** بارگذاری شود. این صرفاً کارآمدی است و هیچ
    اثری روی نتیجه ندارد، چون ATR از خودِ داده می‌آید و به `sl_k` وابسته
    نیست.
    """
    asset = card.split('_')[0]
    sl_abs = atr_med * sl_k
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * L.RR
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    cost_share = 100.0 * COST_PIP / sl_pip

    sig = L.signals(df)
    n_sig = int(sig.fillna(False).sum())
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    base = dict(card=card, sl_k=sl_k, span_years=round(span, 2),
                n_signals=n_sig, n_trades=len(tr),
                sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                cost_share_pct=round(cost_share, 2))
    if len(tr) < 30:
        base['verdict'] = 'TOO_FEW_TRADES'
        return base

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())

    # ── مدلِ صفرِ **همین** (کارت، sl_k) — هرگز بازاستفاده ─────────────
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
    per_year = len(tr) / span

    base.update(
        per_year=round(per_year, 1), avg_held_bars=round(held, 1),
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        uncond_wr=round(unc, 2), perm_mean=round(perm['mean'], 2),
        perm_max=round(perm['max'], 2), perm_sd=round(perm['sd'], 2),
        pf=m.get('profit_factor'), net=m.get('net_profit'),
        z=m.get('skill_z'), rqs2=res.get('rqs2_score'),
        verdict=res.get('verdict'), gates=res.get('gates'),
        # ── پنج شرطِ پذیرشِ پیش‌ثبت‌شده، هر یک جداگانه ثبت می‌شود ──
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
    cards = sys.argv[1:] or CARDS
    print(f'S384 wide-stop | rule LOCKED: willr({L.WILLR_P})>{L.WILLR_THR} '
          f'rr={L.RR} side=long | sl_k grid={SL_K_GRID} | n_trials={N_TRIALS}')
    print()
    hdr = (f'{"card":12s} {"k":>4s} {"slpip":>7s} {"c/SL%":>6s} {"n":>6s} '
           f'{"/yr":>7s} {"held":>6s} {"wr":>6s} {"be":>6s} {"lift":>7s} '
           f'{"unc":>6s} {"pmax":>6s} {"5cond":>6s} verdict')
    print(hdr)
    print('-' * len(hdr))
    for card in cards:
        df = L.load(card)
        ps = L.pip_size(card.split('_')[0])
        atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
        for sl_k in SL_K_GRID:
            try:
                r = run_one(card, sl_k, L, NM, df, atr_med, ps)
            except Exception as e:
                print(f'{card:12s} {sl_k:4.1f} ERROR {str(e)[:60]}')
                continue
            # ذخیرهٔ فوری — قانونِ «اندک اندک»
            with open(f'{OUT}/{card}_k{sl_k}.json', 'w') as f:
                json.dump(r, f, ensure_ascii=False, default=str)
            if r.get('verdict') == 'TOO_FEW_TRADES':
                print(f'{card:12s} {sl_k:4.1f} {r["sl_pip"]:7.1f} '
                      f'{r["cost_share_pct"]:6.2f} {r["n_trades"]:6d} '
                      f'{"":>7s} {"":>6s} {"":>6s} {"":>6s} {"":>7s} '
                      f'{"":>6s} {"":>6s} {"":>6s} TOO_FEW_TRADES')
                continue
            print(f'{card:12s} {sl_k:4.1f} {r["sl_pip"]:7.1f} '
                  f'{r["cost_share_pct"]:6.2f} {r["n_trades"]:6d} '
                  f'{r["per_year"]:7.1f} {r["avg_held_bars"]:6.1f} '
                  f'{r["wr"]:6.2f} {r["be"]:6.2f} {r["lift"]:+7.2f} '
                  f'{r["uncond_wr"]:6.2f} {r["perm_max"]:6.2f} '
                  f'{("YES" if r["all_five"] else "no"):>6s} '
                  f'{r.get("verdict")}')
        print()


if __name__ == '__main__':
    main()
