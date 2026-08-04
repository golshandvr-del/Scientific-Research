# -*- coding: utf-8 -*-
"""تجزیهٔ نرخِ سیگنال — «۴۲ معامله در ۱۵.۵ سال» از کجا می‌آید؟

## پرسشِ این ابزار
حسابرسیِ دهانهٔ داده (`results/FINDING_DATA_SPAN_REFUTES_CONSULTANT_ACTION_1.md`)
نشان داد کارتِ `XAUUSD_M30` در **۱۵.۵ سال** فقط **۴۲ معامله** زده — یعنی یک معامله
هر ۱۳۵ روزِ تقویمی، و نرخِ پذیرشِ ۰.۰۲۳٪. آن سند **دو خوانشِ رقیب** را بدونِ داوری
ثبت کرد:

  **(الف) نادر بودنِ واقعیِ رویداد** — بازار این وضعیت را حقیقتاً کم می‌سازد.
      اگر این درست باشد، مسئله **آماری غیرقابلِ نجات** است: نه داده‌ی بیشتر
      (۱۳۱ سال لازم است و بازارِ مدرنِ طلا ۵۵ سال سن دارد) و نه بهبودِ قاعده.

  **(ب) بیش‌قید بودنِ قاعده** — چهار شرطِ AND-شده + تأییدِ بازگشت، نرخِ پذیرش را
      مصنوعی به ۰.۰۲۳٪ می‌رساند بی‌آنکه رویداد در بازار نادر باشد.
      اگر این درست باشد، مسئله **مهندسی** است و با شُل‌کردنِ قیدها حل می‌شود.

این ابزار بینِ (الف) و (ب) داوری می‌کند — با اندازه‌گیری، نه با استدلال.

## روشِ داوری: تجزیهٔ آبشاری (cascade decomposition)
سیگنالِ نهاییِ لایهٔ میزبان S333 حاصلِ زنجیرهٔ AND است (خطوطِ ۱۶۹–۱۸۳ از
`strategies/s333_s79_pullback_revival.py`):

    up_trend  ∧  rsi_pullback  ∧  confirm_turn  ∧  hurst>θ  [∧ er>θ]  [∧ r2>θ]

و بعد `simulate_trades(allow_overlap=False)` هر سیگنالی را که در بازهٔ اشغالِ
معاملهٔ قبلی بیفتد **دور می‌ریزد** (خطوطِ ۱۴۹–۱۵۰ از `engine/scalp_engine.py`).

پس زنجیره را قید-به-قید باز می‌کنیم و در هر گام می‌شماریم چند کندل زنده می‌ماند.
نتیجه، یک آبشارِ عددی است که می‌گوید **کدام قید** کشندهٔ اصلی است.

## چرا این ابزار درجهٔ آزادی خرج نمی‌کند
این اسکریپت **هیچ فرضیه‌ای نمی‌آزماید**: هیچ WR، هیچ سود، هیچ p-value و هیچ
انتخابِ پارامتری تولید نمی‌کند. فقط **شمارشِ کندل** است — یعنی توصیفِ خودِ قاعدهٔ
موجود، نه جست‌وجوی قاعدهٔ نو. بنابراین به دفترِ چندگانگی (multiplicity ledger)
چیزی بدهکار نمی‌شود و آزادانه قابلِ اجراست.

**مرزِ صداقت:** خروجیِ این ابزار **مجوزِ شُل‌کردنِ قیدها نیست**. اگر (ب) تأیید شود،
هر شُل‌کردنی یک فرضیهٔ نو است و باید هزینهٔ آماریِ خودش را در دفتر بپردازد.
این ابزار فقط می‌گوید «کجا را بکَنیم»، نه «چه چیزی پیدا کردیم».
"""
import sys, os, json, datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

from engine import scalp_engine as SE
from engine import indicator_bank as ib
import strategies.s333_s79_pullback_revival as S333

OUT = 'results/_audit_selectivity'
os.makedirs(OUT, exist_ok=True)

# کارت‌هایی که لایهٔ میزبان رویشان پیکربندیِ ثبت‌شده دارد (BEST_CFG)
CARDS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1']


def cascade(df, cfg, asset):
    """آبشارِ قید-به-قید. هر گام: چند کندل پس از افزودنِ این قید زنده است؟

    عیناً همان ترتیبی که `S333.build_layer` اعمال می‌کند — بازتولید، نه بازنویسی.
    """
    c = df['close'].values
    h = df['high'].values
    n = len(df)

    ef = S333.ema(c, cfg['ef'])
    es = S333.ema(c, cfg['es'])
    r = S333.rsi(c, cfg['rp'])
    r_prev = np.concatenate([[r[0]], r[:-1]])
    c_prevhigh = np.concatenate([[h[0]], h[:-1]])

    steps = []          # [(نامِ قید, ماسکِ تجمعی)]

    # گام ۰: همهٔ کندل‌ها
    m = np.ones(n, bool)
    steps.append(('all_bars', m.copy()))

    # گام ۱: روندِ صعودیِ کلان (EMA_fast > EMA_slow)
    m = m & (ef > es)
    steps.append(('+ up_trend (ema%d>ema%d)' % (cfg['ef'], cfg['es']), m.copy()))

    # گام ۲: pullbackِ RSI  — بستگی به نوعِ تأیید دارد
    conf = cfg.get('confirm', 'rsi_turn')
    if conf == 'none':
        m2 = m & (r < cfg['rth'])
        steps.append(('+ rsi<%d [confirm=none]' % cfg['rth'], m2.copy()))
        m = m2
    elif conf == 'rsi_turn':
        m2 = m & (r_prev < cfg['rth'])
        steps.append(('+ rsi_prev<%d (dip)' % cfg['rth'], m2.copy()))
        m3 = m2 & (r > r_prev) & (r < cfg['rth'] + 10)
        steps.append(('+ rsi_turn (bounce off low)', m3.copy()))
        m = m3
    elif conf == 'price_turn':
        dipped = (r < cfg['rth']) | (r_prev < cfg['rth'])
        m2 = m & dipped
        steps.append(('+ rsi dipped<%d' % cfg['rth'], m2.copy()))
        m3 = m2 & (c > c_prevhigh)
        steps.append(('+ price_turn (close>prev high)', m3.copy()))
        m = m3
    else:
        raise ValueError(conf)

    # گام ۳: فیلترِ رژیمِ Hurst
    hu = np.nan_to_num(ib.compute('hurst', df).values, nan=-1.0)
    m = m & (hu > cfg['hurst'])
    steps.append(('+ hurst>%.2f' % cfg['hurst'], m.copy()))

    # گام ۴/۵: فیلترهای اختیاری
    if cfg.get('er') is not None:
        er = np.nan_to_num(ib.compute('er_lucas_29', df).values, nan=-1.0)
        m = m & (er > cfg['er'])
        steps.append(('+ er>%.2f' % cfg['er'], m.copy()))
    if cfg.get('r2') is not None:
        r2 = np.nan_to_num(ib.compute('r2_fib_89', df).values, nan=-1.0)
        m = m & (r2 > cfg['r2'])
        steps.append(('+ r2>%.2f' % cfg['r2'], m.copy()))

    final_sig = m

    # ── گامِ آخر و مهم: خفگیِ همپوشانی (overlap suppression) ──
    # `allow_overlap=False` هر سیگنالی را که در بازهٔ اشغالِ معاملهٔ باز بیفتد حذف می‌کند.
    # این «قیدِ قاعده» نیست، «قیدِ اجرا» است — و ممکن است کشندهٔ اصلی باشد.
    tr = SE.simulate_trades(df, final_sig, np.zeros(n, bool),
                            cfg['sl'], cfg['tp'], asset, max_hold=cfg['mh'])
    n_exec = len(tr)

    tr_ov = SE.simulate_trades(df, final_sig, np.zeros(n, bool),
                               cfg['sl'], cfg['tp'], asset, max_hold=cfg['mh'],
                               allow_overlap=True)
    n_exec_ov = len(tr_ov)

    return steps, final_sig, n_exec, n_exec_ov


def main():
    report = []
    for card in CARDS:
        pair, tf = card.split('_')
        path = f'data/{pair}_{tf}.csv'
        if not os.path.exists(path):
            print(f'!! missing {path}')
            continue
        cfg = S333.BEST_CFG[card]
        df = SE.load_data(path)
        n = len(df)
        t0, t1 = int(df['time'].iloc[0]), int(df['time'].iloc[-1])
        years = (t1 - t0) / (365.25 * 86400)

        steps, final_sig, n_exec, n_exec_ov = cascade(df, cfg, card)

        print('=' * 78)
        print(f'{card}   bars={n:,}   span={years:.1f}y   '
              f'({dt.datetime.utcfromtimestamp(t0).strftime("%Y-%m-%d")} → '
              f'{dt.datetime.utcfromtimestamp(t1).strftime("%Y-%m-%d")})')
        print('-' * 78)
        print(f'{"constraint":42s} {"bars":>9s} {"% of all":>9s} {"kept%":>7s}')
        print('-' * 78)

        rows = []
        prev = None
        for name, mask in steps:
            k = int(mask.sum())
            pct_all = 100.0 * k / n
            kept = (100.0 * k / prev) if prev else 100.0
            print(f'{name:42s} {k:9,d} {pct_all:8.3f}% {kept:6.1f}%')
            rows.append(dict(constraint=name, bars=k,
                             pct_of_all=round(pct_all, 4),
                             kept_pct_of_prev=round(kept, 2)))
            prev = k

        n_sig = int(final_sig.sum())
        kept_exec = (100.0 * n_exec / n_sig) if n_sig else 0.0
        print('-' * 78)
        print(f'{"= raw signal bars":42s} {n_sig:9,d} {100.0*n_sig/n:8.3f}%')
        print(f'{"→ executed (allow_overlap=False)":42s} {n_exec:9,d} '
              f'{100.0*n_exec/n:8.3f}% {kept_exec:6.1f}%')
        print(f'{"→ executed (allow_overlap=True)":42s} {n_exec_ov:9,d} '
              f'{100.0*n_exec_ov/n:8.3f}%')
        print(f'   overlap suppression discards {n_sig - n_exec:,} of {n_sig:,} '
              f'signals ({100.0 - kept_exec:.1f}%)')
        if n_exec:
            print(f'   → 1 trade per {years*365.25/n_exec:.1f} calendar days'
                  f'   |   x{356.0/n_exec:.1f} needed for H5 barrier (356)')
        print()

        report.append(dict(
            card=card, bars=n, span_years=round(years, 2),
            cfg={k: (v if not isinstance(v, float) else round(v, 4))
                 for k, v in cfg.items()},
            cascade=rows,
            raw_signal_bars=n_sig,
            executed_no_overlap=n_exec,
            executed_with_overlap=n_exec_ov,
            overlap_discard_pct=round(100.0 - kept_exec, 2),
            days_per_trade=(round(years * 365.25 / n_exec, 1) if n_exec else None),
        ))

    with open(os.path.join(OUT, 'cascade.json'), 'w') as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(f'saved → {OUT}/cascade.json')


if __name__ == '__main__':
    main()
