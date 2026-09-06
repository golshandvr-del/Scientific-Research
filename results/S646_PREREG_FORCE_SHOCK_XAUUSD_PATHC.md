# S646 — PREREG — ForceShock (Elder Force Index shock, continuation) — XAUUSD — Path C

**نویسنده:** امی نوتر · **دکاد:** S640–S649 · **تاریخ:** 2026-09-04
**وضعیت:** پیش‌ثبت — **پیش از هر محاسبه روی نیمهٔ دوم**. پس از commit این فایل هیچ پارامتری تغییر نمی‌کند.

## ۰. بازبینیِ موازی و ممیزیِ برخورد
- fetch شد؛ لایه‌های جدید: S966 **ACCEPT 85.8** (کایل، ماندگاریِ شوکِ کندلی × درفتِ ۱۸۰ کندل H8)، S992/S993 REJECT، S948/S949 REJECT، S975 REJECT.
- grep خانوادهٔ Force Index / `efi` در S500–S980: **۰ فایل**. S965/S966 (کایل) روی range/ATR و نسبتِ بدنه هستند، بدونِ حجم؛ S616 (VWMA-accumulation) و S740 (absorption/MFI/Chaikin) هندسهٔ متفاوت دارند. خانواده بکر است.

## ۱. فرضیهٔ منجمد
- **Force Index خام (Elder 1993):** `f_t = volume_t × (close_t − close_{t−1})`.
- **رویدادِ شوک:** `|f_t| ≥ 6 × median(|f|)` روی ۱۰۰ کندلِ **قبلی** (`rolling(100).median().shift(1)` — کندلِ جاری در نول نیست).
- **جهت (cont):** لانگ اگر `close_t > close_{t−1}`؛ شورت اگر `close_t < close_{t−1}`. **هر دو سمت** فعال.
- ورود: open کندلِ بعد (رفتارِ `scalp_engine.simulate_trades`). بدونِ فیلترِ دیگر. صفر پارامترِ آزاد.

## ۲. کارت‌ها و استخر
- TFها: **{H3, H4, H6, H8, H12}** (ثابتِ دکاد) — منبع `data/mt5_full/` (H4: `data/XAUUSD_H4.csv`، همان فید).
- SL = `1.5 × median(ATR100)` روی نیمهٔ دوم، به pip (PIP=0.1)؛ TP = SL؛ max_hold=64.
- نول: هر کارت uncond از N_UNCOND=20000 ورودِ تصادفی + K=500 جایگشتِ n_side با همان هندسه، به‌تفکیکِ سمت (الگوی S670؛ قانونِ S385).
- استخر: `rqs2_pool.pool_cards` (الگوی S431)، محورِ ۵ دقیقه‌ای، holdout_mask = چندکِ ۵۰٪ زمانِ ورود، `compute_rqs2(..., n_trials=1, allow_overlap=False)`.
- seed = **646646**. حکم فقط از `engine.rqs2.compute_rqs2`.

## ۳. کد و خروجی
`strategies/s646_final_holdout.py` — پس از این commit، **یک بار**. خروجی: `results/S646_ForceShock_Xauusd_H3H4H6H8H12_rqs2_<score>_<VERDICT>.md` + `results/_s646_final/pool_verdict.json`.

## ۴. شواهدِ نیمهٔ اول (فقط برای ثبتِ صداقت؛ `results/_s646_explore/*.json`)
K=6/cont: H3 S +3.10 (n=752) · H4 S +3.07 (n=509) · H6 S +2.54 (n=295) · H8 S +3.19 (n=193) · H12 L +3.95 (n=108)، H12 S −0.78.
سمتِ لانگ روی H3–H6 حدودِ +1pp با exp_pip منفی. pooled lsn در-نمونه ≈ 120.

## ۵. پیش‌بینیِ صادقانه
با قانونِ S641 (lsn برون‌نمونه ≈ نصف) → ≈ 60 < 78. **REJECT** محتمل‌ترین حکم؛ P(ACCEPT) < 5٪، P(POWER-LIMITED) ≈ 10٪.
ابطال‌گر: اگر سمتِ شورت در نیمهٔ دوم lift ≤ 0 داشت، «عدمِ تقارنِ شوکِ فروشِ حجمی» به‌عنوانِ مکانیسم رد می‌شود.
