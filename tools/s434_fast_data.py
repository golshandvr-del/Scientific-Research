"""
s434_fast_data.py — لایهٔ دادهٔ سریع + **معناشناسیِ درستِ** سیگنالِ زمان‌محور
================================================================================

این فایل دو مسئلهٔ **متفاوت** را حل می‌کند که هر دو با ورودِ دادهٔ کاملِ MT5
(۱۹ تایم‌فریمِ طلا، ۶۰۰MB، تا ۵ میلیون کندل) پیدا شدند. عمداً در یک فایل‌اند
چون مسئلهٔ دوم فقط هنگام حلِ مسئلهٔ اول کشف شد.

--------------------------------------------------------------------------------
مسئلهٔ ۱ — هزینهٔ محاسبه (نگرانیِ صریحِ کاربر)
--------------------------------------------------------------------------------
سنجشِ واقعی (نه تخمین) روی همین سندباکس:

| کارت                | بارگذاریِ CSV | شبیه‌سازیِ یک ترکیب | ۱۲۹۶ ترکیب |
|---------------------|---------------|---------------------|-------------|
| M30 (۱۸۲ هزار کندل) | ۰.۱۴s         | ۰.۱۹s               | ~۴ دقیقه    |
| M5  (۱.۰۹ میلیون)   | ۰.۷۶s         | ۰.۳۲s               | ~۷ دقیقه    |
| M1  (۵.۰۰ میلیون)   | **۳.۸۲s**     | **۲.۳۰s**           | **~۵۰ دقیقه** |

دو گلوگاهِ مستقل در این جدول دیده می‌شود:

1. **بارگذاریِ CSV** — ۳.۸۲ ثانیه برای M1. اگر جستجو در چند اجرا انجام شود
   (که طبق «قانونِ اندک اندک» باید بشود، تا چک‌پوینت ممکن باشد) این هزینه
   هر بار تکرار می‌شود. راه‌حل: کشِ باینریِ `.npz` — یک بار ساخته می‌شود،
   بعد با `np.load` در کسری از ثانیه خوانده می‌شود.

2. **شبیه‌سازیِ هر ترکیب** — ۲.۳۰ ثانیه برای M1 در برابر ۰.۱۹ برای M30.
   نسبتِ ۱۲ برابر، در حالی که نسبتِ کندل‌ها ۲۷ برابر است ⇒ زمان **زیرخطی**
   رشد می‌کند، چون شبیه‌ساز فقط از کندل‌های سیگنال به بعد را می‌پیماید.
   **پس گلوگاهِ واقعی تعدادِ کلِ کندل نیست، تعدادِ سیگنال است.**

--------------------------------------------------------------------------------
مسئلهٔ ۲ — 🔬 کشفِ معناشناختی (مهم‌تر از مسئلهٔ ۱)
--------------------------------------------------------------------------------
هنگام سنجشِ M1 این اعداد را دیدم:

    کندل‌های با ساعتِ ۲۲ یا ۲۳ = ۳۶۵٬۱۴۴
    که دقیقهٔ صفر دارند         =   ۶٬۲۲۰
    معاملاتِ حاصل               =   ۲٬۷۱۱   ⇒ ۹۹.۳٪ سیگنال‌ها دور ریخته می‌شوند

قانونِ S139 این است: «ورود در open کندلِ بعد از کندلی که **ساعتش ۲۲ یا ۲۳**
است.» روی M15 در هر ساعت ۴ کندل هست، پس این قانون ۸ سیگنال در شبانه‌روز
می‌دهد. روی M1 در هر ساعت **۶۰** کندل هست ⇒ ۱۲۰ سیگنال.

اما مسئله سرعت نیست، **معنا** است:

  * روی M15، لایه یعنی «در بازگشاییِ سشنِ آسیا وارد شو».
  * پورتِ ساده به M1 یعنی «در هر دقیقه از آن دو ساعت تلاش کن وارد شوی».

اینها **دو لایهٔ متفاوت‌اند**. دومی چیزی است که پروژه هرگز نپذیرفته، و اگر
آن را با نامِ S139 بیازمایم و پاس شود، عملاً **لایهٔ دیگری** را جای S139
جا زده‌ام. این مصداقِ مستقیمِ **اشتباهِ رایجِ ۶** است: «استفاده از پارامترِ
یکسان برای همهٔ تایم‌فریم‌ها»، فقط این بار پارامتر یک عددِ TP/SL نیست بلکه
خودِ **تعریفِ سیگنال** است.

راه‌حل: معنا حفظ شود نه فرمول. `SESSION_OPEN` سیگنال را به **اولین کندلِ
هر ساعتِ هدف** محدود می‌کند، پس روی هر تایم‌فریمی «بازگشاییِ سشن» می‌ماند:

| TF  | کندل در هر ساعت | سیگنالِ خامِ ساده | سیگنالِ SESSION_OPEN |
|-----|------------------|---------------------|-----------------------|
| M1  | ۶۰               | ۳۶۵٬۱۴۴             | ۶٬۲۲۰                 |
| M5  | ۱۲               | ~۷۳٬۰۰۰             | ~۶٬۲۰۰                |
| M15 | ۴                | ~۲۴٬۰۰۰             | ~۶٬۲۰۰                |
| H1  | ۱                | ~۶٬۲۰۰              | ~۶٬۲۰۰                |

نکتهٔ زیبا: روی H1 دو تعریف **یکسان** می‌شوند، پس این تعمیم با نسخهٔ
تاریخیِ لایه در تناقض نیست — آن را در تایم‌فریم‌های ریزتر **حفظ** می‌کند.
و به‌عنوانِ اثرِ جانبی، مسئلهٔ ۱ هم حل می‌شود: ۵۹× کاهشِ سیگنال روی M1.

⚠️ صداقتِ روش‌شناختی: هر دو تعریف در دسترس می‌مانند (`RAW_HOUR` و
`SESSION_OPEN`). من مدعی نیستم که SESSION_OPEN «بهتر» است — مدعی‌ام که
**همان لایه** است. اگر RAW_HOUR روی M1 پاس شد، به‌عنوانِ لایهٔ **نو** با
شمارهٔ جدا و افشای همپوشانی گزارش می‌شود، نه به‌عنوانِ S139.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, 'data', '_cache')

# مسیرها به ترتیبِ اولویت: دادهٔ کاملِ MT5 مقدم است، بعد دادهٔ قدیمیِ پروژه.
# ⚠️ عمداً fallback دارد ولی **کدام مسیر استفاده شد** را برمی‌گرداند و در
#   کش ذخیره می‌کند، چون E-16 نشان داد دو فایلِ همنام می‌توانند بازهٔ زمانیِ
#   کاملاً متفاوتی داشته باشند (M5 قدیمی ۲.۸ سال، جدید ۱۵.۶ سال) و نتیجه‌ای
#   که نداند روی کدام محاسبه شده، بی‌معنا است.
SEARCH_PATHS = (
    os.path.join(ROOT, 'data', 'mt5_full', '{asset}_{tf}.csv'),
    os.path.join(ROOT, 'data', '{asset}_{tf}.csv'),
)

TF_MINUTES = {
    'M1': 1, 'M2': 2, 'M3': 3, 'M4': 4, 'M5': 5, 'M6': 6, 'M10': 10,
    'M12': 12, 'M15': 15, 'M20': 20, 'M30': 30,
    'H1': 60, 'H2': 120, 'H3': 180, 'H4': 240, 'H6': 360, 'H8': 480,
    'H12': 720, 'D1': 1440, 'W1': 10080, 'MN1': 43200,
}


def resolve(asset: str, tf: str) -> str:
    """مسیرِ فایلِ CSV را پیدا می‌کند و **صریحاً** برمی‌گرداند کدام یکی بود."""
    for pat in SEARCH_PATHS:
        fp = pat.format(asset=asset, tf=tf)
        if os.path.exists(fp):
            return fp
    raise FileNotFoundError(f'{asset}_{tf}.csv در هیچ‌یک از مسیرها نیست')


def load_fast(asset: str, tf: str, *, rebuild: bool = False) -> dict:
    """دادهٔ کندل را می‌خوانَد و **کشِ باینری** می‌سازد/می‌خواند.

    برمی‌گرداند دیکشنری با کلیدهای:
      time, open, high, low, close, volume  (همه `np.ndarray`)
      hour, minute, dow                     (پیش‌محاسبه‌شده)
      src, n_bars, first_utc, last_utc, span_years

    چرا کش: بارگذاریِ CSVِ M1 سه‌ونیم ثانیه است و طبق «قانونِ اندک اندک»
    جستجو باید در چند اجرای جدا انجام شود تا چک‌پوینت ممکن باشد، پس این
    هزینه ده‌ها بار تکرار می‌شود.

    ⚠️ کش با **mtime و حجمِ** فایلِ منبع کلید می‌شود، نه فقط نامِ آن. اگر
      کاربر فایلِ داده را عوض کند، کشِ قدیمی بی‌اعتبار می‌شود. بدونِ این،
      یک کشِ کهنه می‌تواند نتیجهٔ «بازتولیدشده»ای بدهد که با دادهٔ روی دیسک
      نمی‌خواند — و چون هیچ خطایی نمی‌دهد، ساعت‌ها بی‌خبر می‌مانم.
    """
    src = resolve(asset, tf)
    st = os.stat(src)
    key = hashlib.sha256(
        f'{src}|{st.st_size}|{int(st.st_mtime)}|v1'.encode()).hexdigest()[:16]
    os.makedirs(CACHE_DIR, exist_ok=True)
    cp = os.path.join(CACHE_DIR, f'{asset}_{tf}_{key}.npz')

    if os.path.exists(cp) and not rebuild:
        z = np.load(cp, allow_pickle=False)
        out = {k: z[k] for k in z.files if k != '_meta'}
        meta = json.loads(str(z['_meta'])) if '_meta' in z.files else {}
        out.update(meta)
        return out

    df = pd.read_csv(src)
    t = df['time'].values.astype(np.int64)
    dt = pd.to_datetime(df['time'], unit='s')
    out = {
        'time': t,
        'open': df['open'].values.astype(np.float64),
        'high': df['high'].values.astype(np.float64),
        'low': df['low'].values.astype(np.float64),
        'close': df['close'].values.astype(np.float64),
        'volume': df['volume'].values.astype(np.float64)
        if 'volume' in df.columns else np.zeros(len(df)),
        'hour': dt.dt.hour.values.astype(np.int16),
        'minute': dt.dt.minute.values.astype(np.int16),
        'dow': dt.dt.dayofweek.values.astype(np.int16),
    }
    meta = {
        'src': src, 'asset': asset, 'tf': tf, 'n_bars': int(len(df)),
        'first_utc': str(dt.iloc[0]), 'last_utc': str(dt.iloc[-1]),
        'span_years': round((dt.iloc[-1] - dt.iloc[0]).days / 365.25, 2),
    }
    np.savez_compressed(cp, _meta=json.dumps(meta), **out)
    out.update(meta)
    return out


def as_dataframe(d: dict) -> pd.DataFrame:
    """چون `engine.scalp_engine.simulate_trades` یک DataFrame می‌خواهد.

    ⚠️ فقط ستون‌هایی که موتور لازم دارد ساخته می‌شوند. ساختنِ DataFrameِ کامل
      با ستون‌های مشتق، حافظهٔ M1 را از ۲۴۰MB به بیش از ۶۰۰MB می‌برد و در
      سندباکسِ فعلی به ریست منتهی می‌شود — که یک بار در همین مأموریت دیدم.
    """
    return pd.DataFrame({
        'time': d['time'], 'open': d['open'], 'high': d['high'],
        'low': d['low'], 'close': d['close'], 'volume': d['volume'],
    })


# ══════════════════════════════════════════════════════════════════════════
#  معناشناسیِ سیگنالِ زمان‌محور — هستهٔ کشفِ مسئلهٔ ۲
# ══════════════════════════════════════════════════════════════════════════

def session_open_signal(d: dict, hours=(22, 23), mode: str = 'SESSION_OPEN'):
    """سیگنالِ «بازگشاییِ سشن» با **معناشناسیِ حفظ‌شده** روی هر تایم‌فریم.

    دو حالت:

    ``SESSION_OPEN`` (پیش‌فرض) — تنها **اولین کندلِ** هر ساعتِ هدف.
        روی H1 با ``RAW_HOUR`` **یکسان** است (چون هر ساعت فقط یک کندل دارد)،
        پس این تعمیم نسخهٔ تاریخیِ لایه را نقض نمی‌کند بلکه آن را به
        تایم‌فریم‌های ریزتر **منتقل** می‌کند.

    ``RAW_HOUR`` — هر کندلی که ساعتش در `hours` است (پورتِ ساده).
        روی M1 معنایش «هر دقیقه از آن دو ساعت تلاش کن» است ⇒ لایهٔ دیگری.
        نگه داشته می‌شود چون **حذفِ** یک گزینه هم یک انتخابِ پژوهشی است و
        باید داده تصمیم بگیرد نه سلیقهٔ من. اگر این حالت پاس شد، به‌عنوانِ
        لایهٔ **نو** با شمارهٔ جدا و افشای همپوشانی گزارش می‌شود، نه S139.

    ⚠️ چرا «اولین کندلِ ساعت» را با `minute == 0` تعریف **نمی‌کنم**: روی
      تایم‌فریم‌هایی مثل M12 یا M20 که ۶۰ بر آنها بخش‌پذیر است مشکلی نیست،
      اما روی M4 مرزهای کندل روی ۰،۴،۸… می‌افتد و `minute == 0` درست است،
      حال آنکه روی تایم‌فریمی مثل H3 «اولین کندلِ ساعتِ ۲۲» ممکن است اصلاً
      وجود نداشته باشد. پس تعریفِ مقاوم این است: کندلی که ساعتش هدف است و
      **کندلِ قبلی‌اش ساعتِ دیگری داشته** — یعنی لبهٔ ورود به آن ساعت.
      این تعریف به شبکهٔ دقیقه‌ای وابسته نیست و روی هر ۱۹ تایم‌فریم کار می‌کند.
    """
    h = d['hour']
    in_h = np.isin(h, np.asarray(hours, dtype=h.dtype))
    if mode == 'RAW_HOUR':
        return in_h
    if mode != 'SESSION_OPEN':
        raise ValueError(f'mode نامعتبر: {mode}')
    prev = np.empty_like(h)
    prev[0] = -1
    prev[1:] = h[:-1]
    # لبهٔ ورود: ساعت هدف است و ساعتِ کندلِ قبلی هدف **نبود**
    prev_in = np.isin(prev, np.asarray(hours, dtype=h.dtype))
    return in_h & (~prev_in)


def hold_bars_for(tf: str, hours: float = 24.0) -> int:
    """`max_hold` را از یک **پنجرهٔ ساعتیِ واقعی** می‌سازد، نه عددِ ثابتِ کندل.

    اصلِ S139 روی M15 با ``max_hold=96`` نوشته شده که یعنی ۲۴ ساعت. استفادهٔ
    مستقیمِ ۹۶ روی H1 یعنی چهار روز نگه‌داشتن ⇒ لایهٔ دیگری با نامِ S139.
    این همان **اشتباهِ رایجِ ۶** است و اینجا ساختاراً بسته می‌شود.
    """
    return max(1, int(round(hours * 60.0 / TF_MINUTES[tf])))


def signal_census(asset: str, tfs, hours=(22, 23)) -> list:
    """شمارشِ سیگنال در دو معناشناسی روی چند تایم‌فریم — برای **اثبات** ادعا.

    این تابع چیزی را بهینه نمی‌کند؛ فقط عددی می‌دهد که ادعای «۵۹× کاهش» و
    «روی H1 دو تعریف یکسان‌اند» را قابلِ بازبینی می‌کند.
    """
    rows = []
    for tf in tfs:
        t0 = time.time()
        d = load_fast(asset, tf)
        raw = int(session_open_signal(d, hours, 'RAW_HOUR').sum())
        so = int(session_open_signal(d, hours, 'SESSION_OPEN').sum())
        rows.append({
            'tf': tf, 'src': os.path.basename(os.path.dirname(d['src'])),
            'n_bars': d['n_bars'], 'span_years': d['span_years'],
            'raw_hour': raw, 'session_open': so,
            'reduction': round(raw / so, 2) if so else None,
            'identical': raw == so,
            'hold_bars_24h': hold_bars_for(tf),
            'load_s': round(time.time() - t0, 3),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default='M1,M5,M15,M30,H1')
    ap.add_argument('--rebuild', action='store_true')
    ap.add_argument('--census', action='store_true')
    a = ap.parse_args()
    tfs = [t.strip() for t in a.tfs.split(',') if t.strip()]

    if a.rebuild:
        for tf in tfs:
            t0 = time.time()
            d = load_fast(a.asset, tf, rebuild=True)
            print(f'  کش ساخته شد {a.asset}-{tf}: {d["n_bars"]:,} کندل '
                  f'({d["span_years"]}س) در {time.time()-t0:.2f}s '
                  f'← {os.path.basename(d["src"])}')
            sys.stdout.flush()

    if a.census or not a.rebuild:
        rows = signal_census(a.asset, tfs)
        print(f'\n{"TF":<5} {"منبع":<9} {"کندل":>10} {"سال":>5} '
              f'{"RAW":>8} {"SESSION":>8} {"نسبت":>6} {"یکسان":>6} '
              f'{"هولد۲۴h":>8} {"بارگذاری":>8}')
        for r in rows:
            print(f'{r["tf"]:<5} {r["src"]:<9} {r["n_bars"]:>10,} '
                  f'{r["span_years"]:>5.1f} {r["raw_hour"]:>8,} '
                  f'{r["session_open"]:>8,} {str(r["reduction"]):>6} '
                  f'{"✓" if r["identical"] else "—":>6} '
                  f'{r["hold_bars_24h"]:>8} {r["load_s"]:>8.3f}')
        os.makedirs(os.path.join(ROOT, 'results', '_s434_search'), exist_ok=True)
        fp = os.path.join(ROOT, 'results', '_s434_search',
                          f'signal_census_{a.asset}.json')
        json.dump({'note': 'S434 signal-semantics census', 'rows': rows},
                  open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'\n[ذخیره] {fp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
