# -*- coding: utf-8 -*-
"""S382 — `Williams %R(14)` گذر به بالای −۱۳ | XAUUSD_H4 | long | صفر فیلتر

═══════════════════════════════════════════════════════════════════════════
منطقِ لایه — و اینکه چرا ضدِ شهود است
═══════════════════════════════════════════════════════════════════════════

`Williams %R(14) > −۱۳` یعنی قیمت در **۱۳٪ بالاییِ** دامنهٔ ۱۴-کندلی است:
ناحیهٔ **اشباعِ خرید**. و ما در آن نقطه **long** می‌زنیم.

این خلافِ خواندنِ کلاسیکِ Williams %R است (اشباعِ خرید ⇒ سیگنالِ فروش).
پس این یک لایهٔ **مومنتومی** است — «خریدنِ قدرت» — نه بازگشتی.

کشفش تنها به این دلیل ممکن شد که جاروبِ `step2_raw_edge_scan` **هر دو**
جهت را برای هر قاعده آزمود و اجازه داد **داده** تصمیم بگیرد، نه
پیش‌داوریِ سبک. با فرضِ خواندنِ کلاسیک، این لایه هرگز دیده نمی‌شد.

═══════════════════════════════════════════════════════════════════════════
چرا این لایه ارزشِ آزمونِ کاملِ rqs2 را دارد
═══════════════════════════════════════════════════════════════════════════

S380 نشان داد ۶۴٪ ردهای آرشیو **هیچ اطلاعاتی حمل نمی‌کنند**، چون نمونه‌شان
حتی لبهٔ ۹ واحدیِ S353 را نمی‌دید. اجرای آزمونِ گرانِ کور روی نمونهٔ گرسنه
اتلافِ محض است.

این لایه با n=۸۶۹ از آستانهٔ ۷۸۴ (لبهٔ ۵ واحدی، توانِ ۸۰٪) گذشته است، پس
**نخستین** نامزدِ تاریخِ پروژه است که نتیجه‌اش — پذیرش یا رد — اطلاعات
حمل می‌کند.

═══════════════════════════════════════════════════════════════════════════
صداقتِ آماری: `n_trials` = ۲۳٬۷۵۵
═══════════════════════════════════════════════════════════════════════════

فضای جست‌وجوی واقعی که پیموده شد:
    ۲۴۸ قاعده × ۲ ضریبِ SL × ۳ نسبتِ rr × ۲ جهت × ۸ کارت = ۲۳٬۷۵۵ آزمون

این عددِ کامل به `compute_rqs2` داده می‌شود، نه یک عددِ کوچکِ خوش‌بینانه.
دروازهٔ H5 (بقا در آزمونِ چندگانه) باید بارِ **واقعی** را ببیند. کم‌گزارشیِ
`n_trials` دقیقاً همان جنسِ تقلبی است که معیار برای بستنش ساخته شد.

═══════════════════════════════════════════════════════════════════════════
پارامترها — همه غیررند (ضدِ اشتباهِ #۷)
═══════════════════════════════════════════════════════════════════════════

  • آستانهٔ Williams: **−۱۳** (نه −۲۰ کلاسیک)
  • دورهٔ Williams: ۱۴
  • SL = ۱.۵ × ATR(۱۰۰) ⇒ روی H4 طلا = ۱۲۲.۸۵ pip (خودکالیبره، نه عددِ ثابت)
  • TP = ۱.۵ × SL ⇒ **TP > SL** (ضدِ اشتباهِ #۸)

هندسه از ATRِ **همان کارت** می‌آید، پس روی هر تایم‌فریم عددِ متفاوتی
می‌شود (ضدِ اشتباهِ #۶).
"""

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R

# ── پارامترهای قفل‌شده (از جاروبِ S382، هندسهٔ دارای معناداریِ تصحیح‌شده) ──
WILLR_P = 14
WILLR_THR = -13.0        # غیررند — نه −۲۰ کلاسیک
ATR_P = 100
SL_K = 1.5
RR = 1.5                 # TP > SL

CARD = 'XAUUSD_H4'
ASSET = 'XAUUSD'
SIDE = 'long'

# فضای جست‌وجوی واقعیِ پیموده‌شده — گزارشِ صادقانه به H5
N_TRIALS = 23755

OUT = 'results/_s382'


def load(card):
    df = pd.read_csv(f'data/{card}.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def willr(df, p=WILLR_P):
    hh = df['high'].astype(float).rolling(p).max()
    ll = df['low'].astype(float).rolling(p).min()
    return -100.0 * (hh - df['close'].astype(float)) / (hh - ll).replace(0.0, np.nan)


def atr(df, p=ATR_P):
    h, l, c = df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def signals(df):
    """گذر به بالای آستانه — **رویداد**، نه حالت.

    چرا رویداد و نه حالت: شمردنِ کندل‌هایی که شرط در آن‌ها برقرار است،
    کندل می‌شمارد نه فرصتِ ورود. یک گردشِ ۲۰-کندلی بالای آستانه **یک**
    فرصت است، نه بیست. این تمایز در گامِ ۱ اندازه‌گیری شد و نرخ را
    ۵ تا ۲۰ برابر متورم می‌کرد.
    """
    w = willr(df)
    return (w.shift(1) <= WILLR_THR) & (w > WILLR_THR)


def pip_size(asset):
    return 0.1 if asset.startswith('XAU') else 0.0001


def simulate_trades(df, sig, sl_px, tp_px_mult, is_long, ps):
    """شبیه‌سازِ رویدادمحور با قیدِ تک‌معامله. خروجی: DataFrameِ سازگار با rqs2.

    سه انتخابِ محافظه‌کارانه، هر یک بر ضدِ یک خطای شناخته‌شده:

    ۱) **قیدِ عدمِ هم‌پوشانی.** معاملاتِ هم‌پوشان روی همان حرکتِ قیمت سوارند
       و مستقل نیستند؛ اگر مجاز باشند `n` متورم می‌شود و آزمونِ جایگشت و
       دوجمله‌ای فریب می‌خورند. همچنین S381 نشان داد مدتِ اشغال، کانالِ
       سومِ خرجِ بودجه است — این قید آن را **می‌سنجد**، پنهان نمی‌کند.

    ۲) **اولویتِ SL در کندلِ مبهم.** اگر یک کندل هم SL و هم TP را لمس کند،
       SL برنده است. بدبینانه‌ترین فرضِ ممکن. علتِ انتخاب: حسابرسیِ پیشین
       هفت نقصِ ابزار یافت و **هر هفت** به سودِ ما خطا می‌کردند. شبیه‌سازی
       که کندلِ مبهم را خوش‌بینانه حل کند، همان کلاسِ خطا را بازتولید می‌کند.

    ۳) **حذفِ معاملهٔ بازِ پایانِ داده.** نه برد، نه باخت. نسبت‌دادنِ هر
       نتیجه‌ای به آن، یک فرضِ اندازه‌گیری‌نشده است.
    """
    n = len(df)
    high = df['high'].to_numpy(float)
    low = df['low'].to_numpy(float)
    close = df['close'].to_numpy(float)
    idx = np.flatnonzero(np.asarray(sig.fillna(False), dtype=bool))
    rows = []
    i = 0
    ptr = 0
    while ptr < len(idx):
        e = int(idx[ptr])
        if e < i or e + 1 >= n:
            ptr += 1
            continue
        entry = close[e]
        sl_abs = sl_px
        tp_abs = sl_px * tp_px_mult
        if is_long:
            sl_lvl, tp_lvl = entry - sl_abs, entry + tp_abs
        else:
            sl_lvl, tp_lvl = entry + sl_abs, entry - tp_abs
        j = e + 1
        out = None
        while j < n:
            if is_long:
                hit_sl = low[j] <= sl_lvl
                hit_tp = high[j] >= tp_lvl
            else:
                hit_sl = high[j] >= sl_lvl
                hit_tp = low[j] <= tp_lvl
            if hit_sl:
                out = ('loss', j, -sl_abs / ps)
                break
            if hit_tp:
                out = ('win', j, tp_abs / ps)
                break
            j += 1
        if out is None:
            break
        rows.append(dict(entry_bar=e, exit_bar=out[1], outcome=out[0],
                         pnl_pip=out[2], sl_pip=sl_abs / ps,
                         tp_pip=tp_abs / ps,
                         direction='long' if is_long else 'short'))
        i = out[1] + 1
        while ptr < len(idx) and idx[ptr] < i:
            ptr += 1
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load(CARD)
    ps = pip_size(ASSET)
    a = atr(df)
    sl_abs = float(np.nanmedian(a.to_numpy())) * SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * RR
    sig = signals(df)

    print(f'card={CARD}  bars={len(df)}  '
          f'span={(df["dt"].iloc[-1]-df["dt"].iloc[0]).days/365.25:.2f}y')
    print(f'signals={int(sig.fillna(False).sum())}  '
          f'SL={sl_pip:.2f}pip  TP={tp_pip:.2f}pip  rr={RR}')

    tr = simulate_trades(df, sig, sl_abs, RR, SIDE == 'long', ps)
    print(f'trades={len(tr)}  wins={(tr["outcome"]=="win").sum()}  '
          f'wr={100*(tr["outcome"]=="win").mean():.2f}%')

    bar_time = df['time'].to_numpy()
    close = df['close'].to_numpy(float)

    # تقسیمِ اکتشاف/خارج‌ازنمونه برای H7 — ۷۰٪ اول اکتشاف، ۳۰٪ آخر OOS.
    # چرا بر حسبِ **کندل** و نه معامله: تقسیمِ معامله‌محور اجازه می‌دهد
    # نشتِ زمانی رخ دهد، چون معاملاتِ نزدیکِ مرز از هر دو سو داده می‌بینند.
    split_bar = int(0.70 * len(df))

    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=bar_time, close=close,
                         n_trials=N_TRIALS, split_bar=split_bar)

    print()
    print(R.format_rqs2(f'S382_WilliamsR_{CARD}', res))

    with open(f'{OUT}/{CARD}_rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/{CARD}_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/{CARD}_rqs2.json  +  {CARD}_trades.csv')


if __name__ == '__main__':
    main()
