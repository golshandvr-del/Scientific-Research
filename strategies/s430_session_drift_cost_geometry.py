# -*- coding: utf-8 -*-
"""
S430 — احیای `S73` («رانشِ بازگشاییِ سشن») از راهِ **هندسهٔ هزینه**
================================================================================
پیش‌ثبت: `results/S430_PREREG_S73_COST_GEOMETRY_RESURRECTION.md` (قبل از هر عدد
commit شد). مسیرِ چندگانگیِ `C`. معیارِ حاکم: `engine/rqs2.py` نسخهٔ **v2.6**.

────────────────────────────────────────────────────────────────────────────────
تشخیصِ سرشماری (`tools/s430_resurrection_census.py` روی ۱۴۷ فایلِ حکمِ رسمی):
از ۵۹۲ جفتِ (لایه×کارت)، `S73 / EURUSD-M15` تنها نامزدی است که **ده دروازه از
یازده** را با حاشیهٔ عظیم پاس کرده و فقط یکی را باخته:

    n = ۱۰۰۷ · WR = ۶۰.۴۸٪ · PF = ۱.۷۴۴ · z_skill = ۱۱.۳۲σ (رکوردِ پروژه)
    lift = +۱۸.۱۹pp · maxDD = ۲.۹۴٪ · خارج‌نمونه (n=۳۳۳): WR=۶۳.۹۶٪ PF=۲.۰۸۸
    ⇒ خارج‌نمونه **بهتر** از درون‌نمونه — نشانهٔ نبودِ over-fit
    تنها دروازهٔ افتاده: H9 (استحکامِ هزینه)
        expectancy      = +۱.۰۱۶۲ pip  ✅
        expectancy@2×c  = −۰.۵۸۳۸ pip  ❌  ← اینجا مرد

مکانیزمِ مرگ — **هندسه است، نه سیگنال**:
هندسهٔ آزمودهٔ S73 منجمد روی `SL=۱۲ TP=۱۲` (RR=1.0) بود. با هزینهٔ
`c = spread(1.0) + 2×slip(0.3) = ۱.۶ pip` روی EURUSD:

    سربه‌سرِ اسمی  = (SL + c) / (SL + TP) = ۱۳.۶ / ۲۴ = ۵۶.۶۷٪ → WR=۶۰.۴۸ ✅ (+۳.۸۱)
    سربه‌سرِ مقاوم = (SL + 2c) / (SL + TP) = ۱۵.۲ / ۲۴ = ۶۳.۳۳٪ → WR=۶۰.۴۸ ❌ (−۲.۸۵)

و `docs/FINDING_COST_BURDEN_GEOMETRY_LAW.md` همین را اندازه‌گیری کرده بود:
بارِ هزینهٔ این کارت `c/SL = ۱.۶/۱۲ = ۰.۲۷۱` است و در RR=1 سربه‌سرِ مقاومِ
واقعی به ۷۷٪ می‌رسد، حال آنکه در RR≈۲ به ~۵۰٪ سقوط می‌کند.

قانونِ پنجمِ بهبود (**حفظِ بودجه**) دقیقاً برای همین نوشته شده:
> «به‌جای اینکه با فیلتر WR را بالا ببرید (که معامله را می‌کشد)، نقطهٔ سربه‌سر
>  را پایین بیاورید (که معامله را نمی‌کشد). یعنی TP بزرگ‌تر از SL.»

اگر ۲.۸۵pp کمبود را با فیلتر جبران می‌کردیم، باید معامله حذف می‌شد ⇒ n کوچک‌تر
⇒ z کوچک‌تر ⇒ خطرِ افتادنِ H3/H0. ولی بردنِ TP از ۱۲ به ۱۸:

    سربه‌سرِ مقاوم = ۱۵.۲ / ۳۰ = ۵۰.۶۷٪   ⇒ تخفیفِ **۱۲.۶۶ واحدی**، بدونِ حذفِ
    حتی یک معامله. n دست‌نخورده می‌ماند و توانِ آماری حفظ می‌شود.

⚠️ تلهٔ آشکار (و علتِ اینکه این کار *بدیهی* نیست): با TP دورتر، WR **پایین
می‌آید** (هدف سخت‌تر می‌شود). سؤالِ واقعی: آیا WR کندتر از سربه‌سر می‌افتد؟
این را فقط شبیه‌ساز می‌گوید — و همین چیزی است که این فایل می‌سنجد.
این «دور زدنِ معیار» نیست؛ نقطهٔ مقابلِ اشتباهِ رایجِ ۸ است: آنجا تقلب
`TP < SL` برای بادکردنِ WR بود؛ اینجا `TP > SL` است که WR را **قربانی** می‌کند
و به‌جایش سربه‌سر را واقعاً پایین می‌آورد.

────────────────────────────────────────────────────────────────────────────────
منطقِ لایه (بازتولیدِ verbatim از `strategies/s73_eurusd_session_drift.py`):
  • ورود LONG در openِ کندلِ بعدِ کندلِ لنگرِ سشن (بازگشاییِ نقدینگیِ اروپا).
  • فیلترِ buy-the-dip: فقط اگر `dip_len` کندلِ قبلی نزولی بوده باشند.
  • خروجِ زمانی در `max_hold` کندل اگر TP/SL نخورد.
  • فقط LONG (سمتِ شورت در بایگانی زیان‌ده بود).

⚠️ قاعدهٔ لنگرِ زمانی (در پیش‌ثبت قید شد): ساعتِ لنگر **هرگز** به `hour==0`
هارد-کد نمی‌شود. `hour==0` یک ویژگیِ محورِ زمانِ همین فایلِ EURUSD است؛ روی
XAUUSD و روی TFهای دیگر لنگر باید از **خودِ داده** استخراج شود، وگرنه
اشتباهِ رایجِ ۱ (تمرکزِ کورکورانه بر لایهٔ زمان‌محور) تکرار می‌شود.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se

# ── ثابت‌های پیش‌ثبت‌شده (تغییرِ این‌ها بعد از دیدنِ نتیجه = تقلب) ───────────
ANCHOR_HOUR_EUR = 0      # لنگرِ کشف‌شدهٔ S73 روی EURUSD (بازگشاییِ اروپا، UTC)
DIP_LEN         = 4      # تعدادِ کندلِ نزولیِ لازم (فیلترِ buy-the-dip)
SL_PIP_BASE     = 12.0   # SLِ منجمدِ نسخهٔ اصلی — مبنای مقایسه
MAX_HOLD_BASE   = 6      # خروجِ زمانیِ نسخهٔ اصلی (~۱.۵ ساعت روی M15)


def cost_pip(asset: str) -> float:
    """هزینهٔ کاملِ رفت‌وبرگشت بر حسبِ pip — **همان** تعریفی که H9 با آن داوری
    می‌کند: اسپردِ کامل + اسلیپیجِ دو طرف. اگر اینجا کمتر بگیریم، خودمان را
    فریب داده‌ایم."""
    cfg = se.ASSETS[asset]
    return float(cfg['spread_pip']) + 2.0 * float(cfg['slip_pip'])


def breakevens(sl_pip: float, tp_pip: float, asset: str):
    """(سربه‌سرِ اسمی، سربه‌سرِ مقاوم) بر حسبِ درصد.

    سربه‌سرِ مقاوم = همان تستِ H9: هزینه را ۲× می‌کند تا لایه‌ای که فقط در
    اسپردِ خوش‌بینانه زنده است، افشا شود."""
    c = cost_pip(asset)
    denom = sl_pip + tp_pip
    return (100.0 * (sl_pip + c) / denom,
            100.0 * (sl_pip + 2.0 * c) / denom)


def bars_per_hour(df: pd.DataFrame) -> float:
    """گامِ زمانیِ واقعیِ داده بر حسبِ کندل-در-ساعت (از خودِ داده، نه فرض).

    ⚠️ این تابع علاجِ BUG-TFM است (همان باگی که در S396 افشا شد: کدی که برای
    همهٔ کارت‌ها کندلِ ۱۵ دقیقه‌ای فرض می‌کرد). `max_hold` باید **زمانِ ثابت**
    باشد نه تعدادِ کندلِ ثابت، وگرنه روی H1 شش کندل = ۶ ساعت می‌شود."""
    d = np.median(np.diff(df['time'].values.astype(np.float64)))
    return 3600.0 / d if d > 0 else 1.0


def anchor_signal(df: pd.DataFrame, anchor_hour: int, dip_len: int) -> np.ndarray:
    """سیگنالِ خامِ لایه: کندلِ لنگر + فیلترِ dip.

    forward-safe است: سیگنال روی کندلِ لنگر ثبت می‌شود و موتور در openِ کندلِ
    **بعدی** وارد می‌شود؛ فیلترِ dip فقط کندل‌های *گذشته* را می‌بیند.
    """
    dt = pd.to_datetime(df['time'].values, unit='s')
    is_anchor = (dt.hour == anchor_hour) & (dt.minute == 0)

    # ⚠️ اصلاحِ باگِ بازتولید (S430، گامِ ۳): تعریفِ «dip» در S73 اصلی
    # **جابه‌جاییِ خالصِ قیمت در `dip_len` کندل** است، نه «`dip_len` کندلِ
    # نزílیِ پیاپی». منبع: `strategies/s73_eurusd_session_drift.py` خطوطِ ۸۷–۹۱:
    #     prior[k:] = c[k:] - c[:-k];  long_sig &= (prior < 0)
    # تفاوت **کیفی** است، نه سلیقه‌ای: نسخهٔ «پیاپی» ~۱۰× سخت‌گیرتر است
    # (۱۲۲ سیگنال در برابر ۱۱۹۴) و توانِ آماریِ لایه را نابود می‌کند.
    # بازتولیدِ verbatim یک الزام است، نه یک تشریف: اگر منطق را عوض کنیم،
    # دیگر «احیای S73» نیست و z=۱۱.۳۲σِ بایگانی هیچ ربطی به آن ندارد.
    c = df['close'].values.astype(np.float64)
    prior = np.zeros(len(df), dtype=np.float64)
    if dip_len > 0:
        prior[dip_len:] = c[dip_len:] - c[:-dip_len]
        dip = prior < 0.0
        dip[:dip_len] = False         # حاشیهٔ ابتدایی: داده‌ای نیست
    else:
        dip = np.ones(len(df), dtype=bool)

    return np.asarray(is_anchor) & dip


def discover_anchor(df: pd.DataFrame, asset: str, sl_pip: float, tp_pip: float,
                    dip_len: int, max_hold: int):
    """لنگرِ زمانی را از **خودِ داده** پیدا می‌کند (ضدِ هارد-کدِ `hour==0`).

    برای هر ساعتِ ۰..۲۳ لایه را می‌سازد و expectancy را می‌سنجد؛ بهترین ساعت
    برگردانده می‌شود. ⚠️ این خودش یک جست‌وجو است و **هزینهٔ چندگانگی دارد**:
    تعدادِ واریانتِ آزموده (`n_trials`) باید شاملِ این ۲۴ حالت شود، وگرنه H5
    را فریب داده‌ایم. شمارشِ صادقانه در runner انجام می‌شود.
    """
    out = []
    for hh in range(24):
        sig = anchor_signal(df, hh, dip_len)
        if sig.sum() < 30:
            out.append((hh, float('nan'), 0))
            continue
        tr = se.simulate_trades(df, sig, np.zeros(len(df), bool),
                                sl_pip, tp_pip, asset, max_hold=max_hold)
        if len(tr) < 30:
            out.append((hh, float('nan'), len(tr)))
            continue
        out.append((hh, float(np.mean(tr['pnl_pip'])), len(tr)))
    valid = [r for r in out if not np.isnan(r[1])]
    best = max(valid, key=lambda r: r[1]) if valid else (None, float('nan'), 0)
    return best[0], out


def build(df: pd.DataFrame, asset: str, *, anchor_hour: int,
          sl_pip: float, tp_pip: float, dip_len: int = DIP_LEN,
          hold_hours: float = 1.5):
    """ساختِ لایه و اجرای شبیه‌سازِ رویدادمحور.

    `hold_hours` بر حسبِ **ساعت** است (نه کندل) تا روی همهٔ TFها معنیِ اقتصادیِ
    یکسان داشته باشد — علاجِ BUG-TFM.
    """
    mh = max(1, int(round(hold_hours * bars_per_hour(df))))
    sig = anchor_signal(df, anchor_hour, dip_len)
    tr = se.simulate_trades(df, sig, np.zeros(len(df), dtype=bool),
                            sl_pip, tp_pip, asset, max_hold=mh)
    return sig, tr, mh


def main():
    """تشخیصِ سریع: بازتولیدِ هندسهٔ اصلی و نمایشِ شکافِ H9."""
    asset = 'EURUSD'
    df = se.load_data('data/EURUSD_M15.csv')
    c = cost_pip(asset)
    print(f'== S430 تشخیص — {asset}-M15 · هزینهٔ کامل = {c:.2f} pip ==')
    print(f'{"SL":>5} {"TP":>5} {"RR":>6} {"n":>6} {"WR":>7} '
          f'{"BE":>7} {"RBE":>7} {"exp":>9} {"exp@2c":>9}')
    for tp in (12.0, 18.0, 24.0):
        sig, tr, mh = build(df, asset, anchor_hour=ANCHOR_HOUR_EUR,
                            sl_pip=SL_PIP_BASE, tp_pip=tp)
        if len(tr) == 0:
            continue
        wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
        be, rbe = breakevens(SL_PIP_BASE, tp, asset)
        e = float(np.mean(tr['pnl_pip']))
        print(f'{SL_PIP_BASE:5.1f} {tp:5.1f} {tp/SL_PIP_BASE:6.3f} {len(tr):6d} '
              f'{wr:7.2f} {be:7.2f} {rbe:7.2f} {e:+9.4f} {e - c:+9.4f}')


if __name__ == '__main__':
    main()
