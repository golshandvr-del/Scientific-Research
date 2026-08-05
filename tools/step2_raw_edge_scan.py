# -*- coding: utf-8 -*-
"""گامِ ۲: اکتشافِ **لبهٔ خام** — کدام قاعدهٔ بی‌فیلتر به‌تنهایی lift دارد؟

═══════════════════════════════════════════════════════════════════════════
چرا این ابزار، و چرا **الان**
═══════════════════════════════════════════════════════════════════════════

سه یافتهٔ پیشینِ همین نشست، مسیر را یکتا کردند:

  • S378 — بودجهٔ معامله روی M30/H1 **فراوان** است: میانهٔ قاعدهٔ خام
    ۳۲۷ سیگنال در سال، یعنی ۶.۵× کفِ معیار و ۱.۳× هدفِ سایت.

  • S379 — فیلترِ **جهت‌متضاد** ۹۹.۷٪ بودجه را می‌خورد (۸۳۶ → ۲.۴ در سال)
    و ده جفتِ فیلتر در ۱۵.۵ سال **صفر** بار رخ داده‌اند. پس افزودنِ
    فیلتر برای ساختنِ لبه، راهِ بسته است.

  • S381 — `lift` را با بزرگ‌کردنِ TP **نمی‌توان خرید**: بازار ~۷۰٪ هر
    هدیهٔ هندسی را با افتِ WR پس می‌گیرد، و مدتِ اشغالِ طولانی‌تر `n` را
    هم ۹–۲۶٪ می‌خورد.

نتیجهٔ منطقیِ اجتنابْ‌ناپذیر: اگر لبه **نه** از فیلتر می‌آید و **نه** از
هندسه، پس باید از **خودِ سیگنال** بیاید. و تا امروز پروژه هرگز نپرسیده
است «کدام سیگنالِ خامِ بی‌فیلتر به‌تنهایی lift دارد؟» — همیشه از یک
سیگنالِ فرض‌شده شروع کرده و فیلتر رویش انبار کرده.

این ابزار آن پرسشِ نپرسیده را می‌پرسد.

═══════════════════════════════════════════════════════════════════════════
طراحی — و اینکه چرا هر انتخاب این‌گونه است
═══════════════════════════════════════════════════════════════════════════

۱) **صفر فیلتر.** هر قاعده تنها یک شرط است. این نه ساده‌گرایی است و نه
   اجتناب از پیچیدگی (اشتباهِ #۲)؛ برعکس، این **اندازه‌گیریِ خطِ پایه**
   است. تا ندانیم سیگنالِ خام چه lift‌ای دارد، نمی‌توانیم بدانیم یک فیلتر
   چیزی افزود یا فقط بودجه خورد. یک ماهِ گذشته این خطِ پایه را نداشت.

۲) **هندسهٔ ATR-محور، در هر کارت متفاوت.** SL = k×ATR که ATR در هر
   تایم‌فریم مقدارِ خودش را دارد، پس SL/TP روی M30 و H1 و M15 **عددهای
   متفاوتی** می‌شوند. این ضدِ اشتباهِ #۶ است (TP/SL یکسان برای همه TF).

۳) **rr ≥ ۱ همیشه.** کمینه ۱.۰، و شبکه {1.0, 1.5, 2.0}. هیچ rr<1 وجود
   ندارد، پس تورمِ WR با TPِ کوچک‌تر از SL ساختاراً ناممکن است
   (ضدِ اشتباهِ #۸). و S381 نشان داد rr بزرگ‌تر هم مجانی نیست، پس شبکه
   کوچک و صریح نگه داشته می‌شود تا بارِ چندگانگی قابلِ شمارش بماند.

۴) **معیارِ داوری: lift در برابرِ سربه‌سرِ هزینه‌دار.** نه WR خام.
   `BE = (SL + cost)/(TP + SL)` با cost = ۳.۳ pip (اسپردِ واقعیِ حساب).
   S363 با WR=۸۱٪ لبهٔ کمتری از S353 با WR=۵۰٪ داشت، چون سربه‌سرش
   ۷۵.۷٪ بود. WR بی‌سربه‌سر بی‌معناست.

۵) **گزارشِ اجباریِ Δn.** یافتهٔ نوِ S381: مدتِ اشغال، کانالِ سومِ خرجِ
   بودجه است. پس `n` و `per_year` در کنارِ lift گزارش می‌شوند، همیشه.

۶) **ترتیبِ کارت‌ها: بلندترین تاریخ اول.** M30 و H1 (۱۵.۵ سال) پیش از
   M15 (۶.۴ سال) و M5 (۲.۸ سال). چون S377 نشان داد ظرفیتِ اثباتِ هر کارت
   با بازهٔ تقویمی‌اش تعیین می‌شود، و کارت‌های D1/W1 حذف می‌شوند چون
   S378 نشان داد **صفر** قاعده از ۲۴۸ روی آن‌ها به کفِ ۵۰/سال می‌رسد.

۷) **ذخیرهٔ مرحله‌به‌مرحله.** خروجیِ هر کارت به‌محضِ اتمام نوشته می‌شود
   (قانونِ اندک‌اندک). چهار ریستِ سندباکس در این پروژه رخ داده؛ انتظار
   برای اتمامِ کل، اتلافِ محتوم است.

═══════════════════════════════════════════════════════════════════════════
این ابزار **کشف** نمی‌کند، **غربال** می‌کند
═══════════════════════════════════════════════════════════════════════════

خروجی، لیستِ نامزدهاست نه لیستِ لایه‌های تأییدشده. هر نامزدی که lift
مثبتِ معنادار نشان دهد، باید بعداً از شبیه‌سازِ رویدادمحور و `compute_rqs2`
کامل بگذرد. اینجا هدف تنها این است که از ۲۴۸×۳ = ۷۴۴ ترکیب، آن چند موردی
که ارزشِ محاسبهٔ کاملِ rqs2 را دارند جدا شوند — همان‌طور که S380 نشان داد
اجرای آزمونِ کورِ گران روی نمونهٔ گرسنه، اتلافِ محض است.
"""

import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COST_PIP = 3.3          # اسپردِ واقعیِ حسابِ دمو (۰.۳۳ $/oz = ۳۳ point)
TRADING_DAYS = 252
SITE_TARGET = 252       # هدفِ سایت: روزی ۱ سیگنال
RQS2_FLOOR = 50         # کفِ نرخ برای رسیدن به ۷۸۴ معامله در ۱۵.۵ سال

ATR_P = 100             # دورهٔ ATR — غیررند نیست ولی خودکالیبره است
SL_K = [1.5, 2.0]       # ضریبِ ATR برای SL (بهترین‌های تاریخیِ پروژه)
RR = [1.0, 1.5, 2.0]    # هرگز <۱ — ضدِ اشتباهِ #۸

OUT = 'results/_step2_rawedge'

# کارت‌ها به ترتیبِ بازهٔ تقویمی (بلندترین اول). D1/W1 حذف — S378
CARDS = [
    'XAUUSD_M30', 'XAUUSD_H1', 'EURUSD_M30', 'EURUSD_H1',
    'XAUUSD_H4', 'EURUSD_H4', 'XAUUSD_M15', 'EURUSD_M15',
]


def pip_size(asset):
    """اندازهٔ یک pip. طلا: ۰.۱ $/oz. یورو: ۰.۰۰۰۱."""
    return 0.1 if asset.startswith('XAU') else 0.0001


def load(card):
    df = pd.read_csv(f'data/{card}.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def atr(df, p=ATR_P):
    h, l, c = df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def breakeven_wr(sl_pip, tp_pip, cost=COST_PIP):
    """نرخِ سربه‌سرِ هزینه‌دار. تنها معیارِ درستِ سنجشِ WR."""
    return 100.0 * (sl_pip + cost) / (tp_pip + sl_pip)


# ═══════════════════════════════════════════════════════════════════════════
# شبیه‌سازیِ بریسکت — با **قیدِ عدمِ هم‌پوشانی**
#
# چرا قیدِ هم‌پوشانی حیاتی است (یافتهٔ S381):
#   اگر معاملات هم‌پوشان مجاز باشند، `n` مصنوعاً بزرگ می‌شود و هر
#   آزمونِ معناداری فریب می‌خورد، چون معاملاتِ هم‌پوشان روی همان حرکتِ
#   قیمت سوار‌ند و مستقل نیستند. S381 نشان داد مدتِ اشغال کانالِ سومِ
#   خرجِ بودجه است — پس همین قید، آن کانال را **می‌سنجد** نه پنهان می‌کند.
#
# منطق: از هر سیگنال، فقط اگر معاملهٔ قبلی بسته شده باشد وارد می‌شویم.
# دقیقاً همان کاری که یک معامله‌گرِ واقعی با یک حسابِ واحد می‌کند.
#
# ترتیبِ داخلِ کندل: اگر هم SL و هم TP در یک کندل لمس شوند، **SL**
# برنده اعلام می‌شود. این محافظه‌کارانه‌ترین فرض است و از خوش‌بینیِ
# دروغین جلوگیری می‌کند — همان جنسِ خطایی که هفت باگِ ابزار همه به سودِ
# ما داشتند.
# ═══════════════════════════════════════════════════════════════════════════

def simulate_brackets(high, low, close, entries, sl_pts, tp_pts, is_long):
    """بریسکتِ ثابت با قیدِ تک‌معامله. برمی‌گرداند (wins, losses, bars_held)."""
    n = len(close)
    wins = 0
    losses = 0
    held = 0
    i = 0
    idx = np.flatnonzero(entries)
    ptr = 0
    while ptr < len(idx):
        e = idx[ptr]
        if e < i or e + 1 >= n:
            ptr += 1
            continue
        entry = close[e]
        if is_long:
            sl_px, tp_px = entry - sl_pts, entry + tp_pts
        else:
            sl_px, tp_px = entry + sl_pts, entry - tp_pts
        # از کندلِ بعدی به جلو
        j = e + 1
        out = None
        while j < n:
            if is_long:
                hit_sl = low[j] <= sl_px
                hit_tp = high[j] >= tp_px
            else:
                hit_sl = high[j] >= sl_px
                hit_tp = low[j] <= tp_px
            if hit_sl:            # SL اولویت دارد — محافظه‌کارانه
                out = ('L', j)
                break
            if hit_tp:
                out = ('W', j)
                break
            j += 1
        if out is None:
            break                 # پایانِ داده؛ معاملهٔ باز شمرده نمی‌شود
        if out[0] == 'W':
            wins += 1
        else:
            losses += 1
        held += out[1] - e
        i = out[1] + 1            # قیدِ عدمِ هم‌پوشانی
        while ptr < len(idx) and idx[ptr] < i:
            ptr += 1
    return wins, losses, held


def load_rule_bank():
    """بازاستفاده از بانکِ قواعدِ گامِ ۱ — نه بازنویسیِ آن.

    چرا بازاستفاده: بانکِ گامِ ۱ روی هر ۱۵ کارت اجرا شده و نتایجش
    بازتولیدپذیریِ دقیق نشان داده (اعدادِ یکسان پس از ریستِ سندباکس).
    بازنویسی‌اش یعنی معرفیِ یک نسخهٔ دومِ ناهمگام — همان جنسِ خطایی که
    باعث شد دانشِ سربه‌سر در `rqs2_site_triage` باشد ولی در ابزارِ
    حسابرسی نباشد.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        '_rb', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'step1_rule_bank.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.build_rules()


def side_of(rule_name):
    """جهتِ اقتصادیِ قاعده را از نامش استنتاج می‌کند.

    این تابع مستقیماً از یافتهٔ S379 می‌آید: تضادِ **جهتی** علتِ اصلیِ
    قحطی بود، نه تعدادِ فیلترها. پس جهت باید صریح و ماشین‌خوان باشد.

    قاعده‌ها دو دسته‌اند:
      • صعودی (long): گذر به **بالا** از یک آستانه/میانگین، شکستِ سقف
      • نزولی (short): گذر به **پایین**، شکستِ کف

    اما یک نکتهٔ ظریف: `rsi_xdn_30` (ورود به ناحیهٔ اشباعِ فروش) در
    سبکِ بازگشتی یک سیگنالِ **خرید** است، و در سبکِ مومنتومی یک سیگنالِ
    **فروش**. چون نمی‌دانیم کدام درست است، **هر دو** جهت آزموده می‌شود
    و داده تصمیم می‌گیرد. این عمداً است: پیش‌داوریِ سبک، همان اشتباهی
    است که باعث شد پروژه فیلترِ جهت‌متضاد را یک ماه نبیند.
    """
    return ('long', 'short')      # هر دو جهت — داده تصمیم می‌گیرد


def scan_card(card, rules):
    asset = card.split('_')[0]
    ps = pip_size(asset)
    df = load(card)
    a = atr(df).to_numpy()
    high = df['high'].to_numpy(float)
    low = df['low'].to_numpy(float)
    close = df['close'].to_numpy(float)
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25

    rows = []
    for rname, rfn in rules:
        try:
            sig = np.asarray(rfn(df).fillna(False), dtype=bool)
        except Exception:
            continue
        nsig = int(sig.sum())
        if nsig < 30:
            continue
        for k in SL_K:
            # SL از ATRِ **همان کارت** ⇒ عددِ متفاوت در هر تایم‌فریم (ضدِ #۶)
            sl_med = float(np.nanmedian(a)) * k
            if not np.isfinite(sl_med) or sl_med <= 0:
                continue
            sl_pip = sl_med / ps
            for rr in RR:
                tp_med = sl_med * rr
                tp_pip = sl_pip * rr
                be = breakeven_wr(sl_pip, tp_pip)
                for side in ('long', 'short'):
                    w, l, held = simulate_brackets(
                        high, low, close, sig, sl_med, tp_med, side == 'long')
                    n = w + l
                    if n < 30:
                        continue
                    wr = 100.0 * w / n
                    rows.append(dict(
                        rule=rname, side=side, sl_k=k, rr=rr,
                        sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                        n=n, wr=round(wr, 3), be=round(be, 3),
                        lift=round(wr - be, 3),
                        per_year=round(n / span, 1),
                        avg_held=round(held / n, 1) if n else None,
                    ))
    rows.sort(key=lambda r: -r['lift'])
    return dict(card=card, span_years=round(span, 2), n_rules=len(rules),
                n_tests=len(rows), rows=rows)


def main():
    cards = sys.argv[1:] or CARDS
    os.makedirs(OUT, exist_ok=True)
    rules = load_rule_bank()
    print(f'rule bank: {len(rules)} bare rules  |  '
          f'grid: sl_k={SL_K} rr={RR} sides=2  '
          f'=> {len(rules)*len(SL_K)*len(RR)*2} tests/card')
    print()
    for card in cards:
        try:
            res = scan_card(card, rules)
        except Exception as e:
            print(f'{card:14s} ERROR {str(e)[:60]}')
            continue
        pos = [r for r in res['rows'] if r['lift'] > 0]
        strong = [r for r in res['rows']
                  if r['lift'] >= 5.0 and r['per_year'] >= RQS2_FLOOR]
        site = [r for r in res['rows']
                if r['lift'] >= 5.0 and r['per_year'] >= SITE_TARGET]
        res['n_positive'] = len(pos)
        res['n_strong'] = len(strong)
        res['n_site'] = len(site)
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(res, f, ensure_ascii=False)
        print(f'{card:14s} span={res["span_years"]:6.2f}y  tests={res["n_tests"]:5d}  '
              f'lift>0={len(pos):5d}  lift>=5&rate>=50={len(strong):4d}  '
              f'&rate>=252={len(site):3d}  -> {card}.json')


if __name__ == '__main__':
    main()
