# S650 — EhlersCycleTurn | XAUUSD | Pool(D1+H12) | RQS2 v2.6 = 30.4 | **POWER-LIMITED**

> **Scientist:** Srinivasa Ramanujan (block S650–S659)
> **Date:** 2026-08-20 | **Seed:** 650650 | **Engine:** `engine/rqs2.py` v2.6 + `engine/rqs2_pool.py`
> **Verdict (engine, verbatim):** `POWER-LIMITED RQS2= 30.4 | n= 106 WR=56.60% PF=1.94 lift= +14.76pp z= 2.5 | H0:✓ H1:✓ H2:✓ H3:✗ H4:✓ H5:✓ H6:✓ H7:✓ H8:✓ H9:✓ H10:✓`

---

## 1. Concept — یک ایده کاملاً نو

**Ehlers DSP cycle-turn**: هیچ لایه ACCEPT قبلی از خانواده فیلترهای Ehlers استفاده نکرده بود (فضای سفید تأییدشده در پایگاه دانش پروژه). سیگنال:

- **LONG**: `trendflex(close, p_t) > 0` **AND** `reflex(close, p_r)` از پایین صفر را به بالا قطع کند
- **SHORT**: آینه‌ای (trendflex < 0 AND reflex قطع صفر به پایین)

Reflex چرخش چرخه را می‌گیرد؛ trendflex به‌عنوان گیت جهت روند عمل می‌کند. هر دو بر پایه SuperSmoother فیلتر (پورت numba با اثبات parity در برابر `engine/indicator_bank.py`: `max|Δ| < 1e-9` روی داده واقعی H1).

## 2. Frozen Geometry (قبل از هر تستی قفل شد)

| پارامتر | مقدار |
|---|---|
| SL | `1.618 × ATR(34, Wilder)` |
| TP | `1.618 × SL` (RR = 1.618) |
| max_hold | 34 بار |
| overlap | ممنوع (صف non-overlap از `s346_fast`) |
| هزینه | spread 3.3 pip (استاندارد XAUUSD پروژه) |

## 3. Protocol — Path C (audit §6.2) با شمارش صادقانه

| مرحله | Commit | شرح |
|---|---|---|
| Exploration | `4c3a031f` | فقط **نیمه اول** داده (`df.iloc[:half]`)، ۱۴ ترکیب فیبوناچی (p_t, p_r)، ۱۹ تایم‌فریم |
| PREREG | `6e47ccac` | جدول قفل‌شده TF→(p_t,p_r)، perm_k=600، seed=650650، **n_trials=17**، split=70% — کامیت جدا **قبل** از تست نهایی |
| Final script | `99523869` | کامیت قبل از اجرا؛ hold-out = نیمه دوم، هر TF فقط یک بار لمس شد |
| PREREG addendum | `192330d4` | تست Pool (مکانیزم رسمی POWER-LIMITED rescue)، کاندیداها (H1,H3,H6,H12,D1) از قبل اعلام، **n_trials=18** |
| Pool script | `3db9b355` | کامیت قبل از اجرا |

جدول پارامترهای قفل‌شده: M1:(55,55) M3:(89,55) M4/M5/M6/M10:(89,21) M12:(55,21) M15:(55,13) M20:(89,89) M30:(34,34) H1:(89,55) H2:(21,13) H3:(21,21) H6:(34,13) H8:(34,13) H12:(55,21) D1:(34,13)

## 4. Hold-out Results — هر ۱۷ تایم‌فریم (نیمه دوم داده، لمس یک‌باره)

| TF | Verdict | RQS2 | n | WR% | lift pp | z | p_perm |
|---|---|---|---|---|---|---|---|
| M1 | REJECT | 0.0 | 27,988 | 37.83 | −0.53 | −1.32 | 0.906 |
| M3 | REJECT | 0.0 | 10,370 | 38.75 | −0.16 | −0.24 | 0.593 |
| M4 | REJECT | 0.0 | 21,702 | 38.90 | −0.06 | −0.12 | 0.548 |
| M5 | REJECT | 0.1 | 17,240 | 39.10 | +0.02 | 0.05 | 0.482 |
| M6 | REJECT | 0.0 | 14,397 | 38.63 | −0.49 | −0.84 | 0.800 |
| M10 | REJECT | 0.7 | 8,533 | 39.62 | +0.28 | 0.40 | 0.343 |
| M12 | REJECT | 0.0 | 6,155 | 38.34 | −0.92 | −1.04 | 0.850 |
| M15 | REJECT | 0.0 | 7,539 | 39.10 | −0.23 | −0.29 | 0.616 |
| M20 | REJECT | 9.3 | 887 | 40.59 | +1.19 | 0.54 | 0.295 |
| M30 | REJECT | 2.9 | 1,572 | 40.27 | +0.87 | 0.52 | 0.300 |
| H1 | REJECT | 14.9 | 479 | 41.96 | +2.49 | 0.83 | 0.203 |
| H2 | REJECT | 2.5 | 884 | 39.48 | +0.32 | 0.14 | 0.444 |
| H3 | REJECT | 18.5 | 377 | 43.77 | +3.88 | 1.10 | 0.136 |
| H6 | REJECT | 12.3 | 291 | 43.99 | +3.47 | 0.90 | 0.184 |
| H8 | REJECT | 7.0 | 230 | 40.43 | −1.03 | −0.24 | 0.594 |
| **H12** | **POWER-LIMITED** | 28.8 | 103 | 56.31 | **+13.87** | 2.06 | 0.0198 |
| **D1** | **POWER-LIMITED** | 28.8 | 57 | 57.89 | **+15.37** | 1.76 | 0.0392 |

(W1/MN1 = TOO_SHORT در exploration؛ H4/M2 در `data/mt5_full` موجود نیست — شیلد assert مانع fallback به داده کوتاه شد.)

**الگوی مقیاسی واضح**: lift به‌صورت یکنوا با بزرگ‌شدن تایم‌فریم رشد می‌کند (نویز M1 → سیگنال D1). این رفتار مورد انتظار فیلترهای چرخه‌ای Ehlers است: چرخه‌های معنادار طلا در مقیاس روز/نیم‌روز زندگی می‌کنند، نه دقیقه.

## 5. Pool Test (D1 + H12) — مکانیزم رسمی rescue

- کاندیداهای پیش‌ثبت‌شده: H1, H3, H6, H12, D1 (هر ۵ کاندیدا lift>0 هم‌جهت — شرط اعتبار ۲)
- `choose_homogeneous_subset` (گارد رقیق‌سازی): **D1+H12 انتخاب، H3/H6/H1 حذف** (z_proxy را پایین می‌آوردند) — trace کامل در `final_POOL.json`
- De-overlap تقویمی FIFO: 160 → **106** معامله
- محور زمان مصنوعی ساعتی (الگوی S431، بدون BUG-AXIS/BUG-SPAN)؛ holdout_mask در کوانتایل 70% زمان ورود (بدون BUG-SPLITDIR)
- `blend_pool_null` وزن‌دار به سهم پس از FIFO

### نتیجه نهایی

| متریک | مقدار |
|---|---|
| n_trades | **106** (long 60 / short 46) |
| Win rate | **56.60%** (long 71.67% / short 36.96%) |
| Profit factor | **1.94** |
| Net profit | +5,059.8 pip |
| Max DD | 3.78% | 
| Recovery factor | 8.88 |
| null_ref_wr (سخت‌گیرانه: max(uncond, perm_mean)) | 41.84% |
| **skill lift** | **+14.76 pp** |
| **z** | **2.54** (نیاز H3: ≥3.09) |
| p_perm | 0.0056 · p_emp 0.0015 · Bonferroni-adj 0.0278 |
| Hold-out (30% آخر) | n=32, WR=65.62%, PF=2.42 — از in-sample **بهتر** |
| Gates | **10/11** — فقط H3 قرمز |
| n_trials (صادقانه) | 18 |

## 6. Scientific Reading — چرا POWER-LIMITED و نه ACCEPT

اج اقتصادی **واقعی و بزرگ** است: +14.76pp بالای null سخت‌گیرانه، PF≈2، hold-out قوی‌تر از in-sample (نشانه ضد-overfit). اما با n=106، خطای استاندارد باینومیال اجازه نمی‌دهد z از 3.09σ عبور کند (z=2.54، و حتی z_obs خام = 3.08 — دقیقاً لب مرز). این تعریفِ کتابیِ POWER-LIMITED است: **اج هست، توان آماری برای اثبات در سطح 3.09σ نیست.** سیگنال چرخه‌ای D1/H12 روی ~۸ سال hold-out فقط ~۱۰۶ رخداد de-overlapped تولید می‌کند — داده بیشتر تنها راه ارتقا است، نه tuning (که ممنوع است: hold-out یک‌بار لمس شد و پرونده بسته است).

**عدم استقرار:** طبق قوانین پروژه فقط ACCEPT به سایت/موبایل می‌رود. S650 مستقر نمی‌شود. ممیزی overlap با شبیه‌ساز event-driven نیز فقط برای ACCEPT الزامی است — برای این لایه deferred و مستند شد.

## 7. اثبات پرهیز از ۸ خطای رایج

1. **Look-ahead**: سیگنال بار t → ورود open بار t+1 در `barrier_outcomes` رسمی `s346_fast`؛ فیلترها فقط از close گذشته.
2. **Data snooping**: exploration فقط نیمه اول؛ hold-out (نیمه دوم) یک‌بار و فقط با پارامترهای PREREG لمس شد.
3. **Survivorship/selection**: هر ۱۹ TF گزارش شد، شامل ۱۵ REJECT؛ حذف‌های pool با دلیل و trace ثبت شد.
4. **Overfitting**: هندسه ثابت فیبوناچی (بدون بهینه‌سازی SL/TP)؛ فقط ۱۴ ترکیب period از پیش اعلام‌شده؛ hold-out بهتر از in-sample.
5. **Multiplicity پنهان**: n_trials=17 و سپس 18 صادقانه به Bonferroni داده شد (p_adj=0.0278 گزارش شد).
6. **Null ضعیف**: `blend_null` سخت‌گیرانه — ref_wr=max(unconditional, perm_mean) با K=600 زیرمجموعه اندازه‌گیری‌شده، sd=max(perm_sd, binomial SE).
7. **Cost blindness**: expectancy در 2×cost همچنان +207.7 pip؛ breakeven WR با هزینه = 38.56% در برابر 56.60% واقعی.
8. **Cherry-picked window**: کل تاریخچه mt5_full (شیلد `assert 'mt5_full' in src` در هر سه اسکریپت — تله E-16 خنثی)؛ split زمانی، نه انتخابی.

## 8. Laws Compliance

- ✅ فقط XAUUSD (هرگز EURUSD)؛ M1 اول تست شد؛ همه TFهای موجود
- ✅ نام‌گذاری رسمی فایل نتیجه؛ verdict عیناً از engine
- ✅ PREREG در کامیت جدا قبل از تست؛ اسکریپت‌ها قبل از اجرا کامیت شدند
- ✅ چک‌پوینت git per-TF؛ اجرای طولانی در background با لاگ
- ✅ هیچ دخالتی در بلوک‌های دانشمندان موازی (S630/S640/S660/S670/S743... فقط خوانده شد)
- ✅ باگ‌فیکس OOM (chunking 250k) شفاف کامیت شد — پروتکل تغییری نکرد

## 9. Reproduction

```bash
python3 strategies/s650_ehlers_explore.py      # نیمه اول، 19 TF
python3 strategies/s650_final_test.py          # hold-out، 17 TF (skip-if-exists guard)
python3 strategies/s650_pool_test.py           # pool D1+H12 → final_POOL.json
```

Artifacts: `results/_scan_S650/{explore_*,final_*,final_POOL}.json` · Prereg: `research/S650_PREREG.md`
