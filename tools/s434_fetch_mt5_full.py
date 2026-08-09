"""
s434_fetch_mt5_full.py — بازتولیدِ دادهٔ کاملِ MT5 طلا (۱۹ تایم‌فریم)
================================================================================

**چرا این فایل وجود دارد**

کاربر تاریخچهٔ کاملِ MT5 ویندوز را استخراج کرد و به‌صورت یک آرشیوِ RAR
(۱۵۸,۴۳۸,۴۲۹ بایت) در اختیارِ تیم گذاشت. محتوایش ۱۹ تایم‌فریمِ XAUUSD و
۶۰۰.۵ مگابایت CSV است. این حجم **در گیت کامیت نمی‌شود** — دلیلش در
`.gitignore` مستند است: قانونِ غیرقابل‌مذاکرهٔ پروژه «commit + push بعد از هر
تغییرِ فایل» است، و ۶۰۰ مگابایت CSV هر push را آن‌قدر کند می‌کند که فشارِ
دسته‌کردنِ تغییرات ایجاد شود — یعنی کامیت‌کردنِ داده همان قانونی را تخریب
می‌کند که به‌ظاهر به آن خدمت می‌کند.

راهِ جایگزین **قوی‌تر** است: این اسکریپت + `data/mt5_full/MANIFEST.json`
کامیت می‌شوند، پس هر AI دیگری می‌تواند داده را بازتولید کند و — مهم‌تر —
با SHA256 **اثبات** کند که بایت‌به‌بایت همان داده است. یک blob در تاریخِ گیت
چنین تضمینی نمی‌دهد.

--------------------------------------------------------------------------------
**دو دستاوردِ علمیِ این داده برای پروژه**

1. **`XAUUSD_M1` که پروژه هرگز نداشت** — ۵٬۰۰۰٬۰۰۰ کندل، ۱۴.۳ سال.
   قانونِ اولِ پروژه (MTF) صریحاً می‌گوید «از xauusd و m1 شروع کن»، اما در
   گامِ ۵ همین مأموریت کشف کردم که فایلِ M1 طلا **وجود ندارد** و ناچار از M5
   شروع کردم. این شکاف حالا پر شده است.

2. **رفعِ کشفِ E-16 (بایاسِ دورهٔ تاریخی)** — در گامِ ۸ اندازه گرفتم که
   `data/XAUUSD_M5.csv` قبلی فقط **۲.۸ سال** (از ۲۰۲۳-۰۹) را می‌پوشاند و
   بنابراین تقریباً هیچ بازارِ خرسیِ ممتدی را **ندیده** است — پس آمارِ رژیمی‌اش
   ساختاراً خوش‌بین بود. M5 جدید **۱۵.۶ سال** و شاملِ بازارِ خرسیِ ۲۰۱۱–۲۰۱۸
   است. آن استدلال حالا با **اندازه‌گیری** قابلِ تسویه است، نه با بحث.

--------------------------------------------------------------------------------
**سازگاری — سنجیده شد، فرض نشده**

خطرِ واقعی: اگر این داده از بروکر یا فیدِ دیگری می‌آمد، هر محاسبهٔ بعدی در
سکوت آلوده می‌شد و بدتر، مقایسه‌اش با بایگانیِ نتایجِ قبلی بی‌معنا می‌شد.
پس ادغام بر حسبِ timestamp انجام شد:

    ادغامِ M30 جدید با `data/XAUUSD_M30.csv` موجود
    ⇒ ۱۸۱٬۳۸۳ کندلِ مشترک (= ۱۰۰.۰٪ فایلِ قدیم)
    ⇒ open/high/low/close/volume در **۱۰۰.۰۰٪** موارد یکسان

نتیجه: **همان بروکر، همان فید.** پس نتایجِ قدیم و جدید هم‌سنجه‌اند.

--------------------------------------------------------------------------------
**درسِ عملیاتی که گران تمام شد (ثبت می‌شود تا تکرار نشود)**

دانلودِ اولِ من در سکوت فاسد شد: پس از یک تایم‌اوت، با `curl -C -` ادامه
دادم و روی فایلِ ناقص ۴۹٬۱۵۲ بایتِ تکراری نوشته شد. نشانه‌ها گمراه‌کننده
بودند — آرشیو **بازشد** و ۳ فایل از ۱۹ را سالم استخراج کرد، و تنها بزرگ‌ترین
فایل خطای checksum داد. اگر فقط به «باز شد» اعتماد می‌کردم، با ۳ تایم‌فریم
کار را ادامه می‌دادم و هرگز نمی‌فهمیدم ۱۶ تایم‌فریمِ دیگر وجود دارد.
چیزی که مچ را گرفت، **مقایسهٔ حجمِ فایل با `Content-Length` سرور** بود.
⇒ این اسکریپت حجم را **قبل** از استخراج تأیید می‌کند و در صورتِ عدمِ تطابق
   دانلود را از صفر تکرار می‌کند، هرگز ادامه نمی‌دهد.

--------------------------------------------------------------------------------
**اجرا**

    python3 tools/s434_fetch_mt5_full.py            # دانلود + استخراج + تأیید
    python3 tools/s434_fetch_mt5_full.py --verify    # فقط تأییدِ SHA256 موجود

نیازمندی: باینریِ `unrar`. اگر نبود، اسکریپت راهِ ساختش را چاپ می‌کند
(سورس از rarlab، کامپایل با `make -j2`؛ ⚠️ موازیِ زیاد ندهید — تجربهٔ من:
`make -j4` دو بار اجرا شد، ۴۳ پروسهٔ کامپایلر همزمان ساخت و سندباکس را
از کار انداخت).
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'data', 'mt5_full')
MANIFEST = os.path.join(DEST, 'MANIFEST.json')

SOURCE_URL = 'https://abrehamrahi.ir/o/public/y6n6FKpq/'
EXPECTED_ARCHIVE_BYTES = 158438429       # از هدرِ Content-Length سرور

UNRAR_CANDIDATES = ('unrar', '/home/user/unrar/unrar',
                    os.path.expanduser('~/.local/bin/unrar'))


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def find_unrar() -> str | None:
    for c in UNRAR_CANDIDATES:
        p = shutil.which(c) if os.sep not in c else (c if os.path.exists(c) else None)
        if p:
            return p
    return None


def verify() -> int:
    """تأییدِ SHA256 فایل‌های موجود در برابرِ مانیفست. کدِ خروج = تعدادِ خطا."""
    if not os.path.exists(MANIFEST):
        print(f'[توقف] مانیفست نیست: {MANIFEST}')
        return 1
    man = json.load(open(MANIFEST, encoding='utf-8'))
    bad = missing = ok = 0
    for rec in man['files']:
        fp = os.path.join(DEST, rec['file'])
        if not os.path.exists(fp):
            print(f'  ✗ غایب      {rec["file"]}')
            missing += 1
            continue
        got = sha256_of(fp)
        if got != rec['sha256']:
            print(f'  ✗ ناهمسان   {rec["file"]}\n      انتظار {rec["sha256"][:24]}…'
                  f'\n      دریافت {got[:24]}…')
            bad += 1
        else:
            print(f'  ✓ {rec["file"]:<20} {rec["bars"]:>8} کندل  '
                  f'{rec["span_years"]:>5.1f} سال')
            ok += 1
    print(f'\n[نتیجه] سالم={ok}  ناهمسان={bad}  غایب={missing}')
    return bad + missing


def download(dest_rar: str) -> None:
    """دانلود **از صفر**. عمداً از resume استفاده نمی‌شود — دلیلش در سرصفحه."""
    if os.path.exists(dest_rar):
        os.remove(dest_rar)          # ⚠️ هرگز ادامه نده؛ resume آرشیو را فاسد کرد
    print(f'[دانلود] {SOURCE_URL}')
    urllib.request.urlretrieve(SOURCE_URL, dest_rar)
    got = os.path.getsize(dest_rar)
    if got != EXPECTED_ARCHIVE_BYTES:
        raise RuntimeError(
            f'حجمِ آرشیو نمی‌خواند: دریافت {got:,} ≠ انتظار '
            f'{EXPECTED_ARCHIVE_BYTES:,}. دانلود ناقص است — دوباره اجرا کنید. '
            f'(اعتماد به «آرشیو باز شد» کافی نیست: نسخهٔ فاسدِ من ۳ فایل از ۱۹ '
            f'را سالم استخراج کرد.)')
    print(f'[دانلود] تأیید شد: {got:,} بایت')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true',
                    help='فقط SHA256 فایل‌های موجود را بسنج')
    ap.add_argument('--workdir', default=os.path.expanduser('~/mt5dl'))
    args = ap.parse_args()

    os.makedirs(DEST, exist_ok=True)
    if args.verify:
        return verify()

    tool = find_unrar()
    if not tool:
        print('[توقف] باینریِ unrar پیدا نشد. ساختنش:\n'
              '  curl -sL -o u.tar.gz https://www.rarlab.com/rar/unrarsrc-7.1.6.tar.gz\n'
              '  tar xzf u.tar.gz && cd unrar && make -j2\n'
              '  ⚠️ بیش از -j2 ندهید و دو بار اجرا نکنید.')
        return 1

    os.makedirs(args.workdir, exist_ok=True)
    rar = os.path.join(args.workdir, 'history.rar')
    download(rar)

    print('[آزمونِ صحت] unrar t …')
    r = subprocess.run([tool, 't', rar], capture_output=True, text=True)
    if 'All OK' not in r.stdout:
        print('[توقف] آرشیو آزمونِ صحت را پاس نکرد:\n' + r.stdout[-800:])
        return 1
    print('[آزمونِ صحت] All OK')

    stage = os.path.join(args.workdir, 'x')
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    subprocess.run([tool, 'x', '-y', '-idq', rar, stage + os.sep], check=True)

    got = sorted(glob.glob(os.path.join(stage, '*.csv')))
    print(f'[استخراج] {len(got)} فایلِ CSV')
    for fp in got:
        shutil.copy2(fp, os.path.join(DEST, os.path.basename(fp)))
    print(f'[نصب] در {DEST}')

    return verify()


if __name__ == '__main__':
    sys.exit(main())
