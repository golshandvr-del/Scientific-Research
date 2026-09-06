// ============================================================================
// strategy_registry.ts — رجیستریِ ماژولارِ لایه‌های **پذیرفته‌شدهٔ RQS2 v2.4**
// ----------------------------------------------------------------------------
// این فایل «مغزِ مسیریابیِ» سایت است.
//
// 🔴 پاک‌سازیِ حاکمیتیِ نشستِ S396 (طبقِ User Note): «فقط لایه‌هایی بمانند که
//    RQS2 را پاس کرده‌اند.» ممیزیِ کاملِ ۱۸۱ لایه (دفترِ رسمی:
//    `results/_audit_rename/AUDIT_LEDGER.json`) نشان داد **تنها ۵ لایه** حکمِ
//    `ACCEPT` دارند. سایت از **۲۹ اتصال روی ۱۰ کارت** به **۵ اتصال روی ۵ کارت**
//    کوچک شد. سندِ شواهد:
//    `results/S396_SiteLayerPurgeAudit_XauusdEurusd_M5M15M30H1H4_rqs2_NA_AUDIT.md`
//
//    ⚠️ چرا این پاک‌سازی لازم بود (اندازه‌گیری‌شده، نه سلیقه‌ای): ۲۵ اتصال از ۲۹
//    اتصالِ پیشین با معیارِ **بازنشسته‌شدهٔ `RQS+`** مجوز گرفته بودند — همان
//    معیاری که `docs/RQS2_SPEC.md` §۰ اثبات کرد **رانشِ صعودیِ طلا را با مهارت
//    اشتباه می‌گیرد** (لانگِ بی‌سیگنال روی D1 رایگان ۵۲.۴٪ و روی W1 رایگان
//    ۵۸.۲٪ می‌بَرد و RQS+ آن هدیه را «مهارت» می‌شمرد). هیچ‌یک از آن ۲۵ اتصال
//    زیرِ RQS2 زنده نماند ⇒ **۸۶٪ از سطحِ سایت بر معیارِ آلوده بنا شده بود.**
//
// 🔑 قاعدهٔ اتصالِ حاکم بر این فایل (غیرقابلِ مذاکره):
//    «یک لایه فقط روی کارتی وصل می‌شود که **همان کارت** حکمِ `ACCEPT` گرفته باشد.»
//    نامِ فایلِ نتیجه **منبعِ حقیقت نیست**: `tools/audit_runner.py:136` همهٔ
//    کارت‌های *آزموده‌شده* را در نام می‌آورد (حتی REJECTها)، درحالی‌که
//    `pick_headline` فقط **بهترین** کارت را سرتیتر می‌کند. پس
//    `S355_..._M5M15M30H1_..._ACCEPT.md` **به‌معنیِ چهار کارتِ پاس‌شده نیست.**
//    منبعِ حقیقت فقط `cards[]`ِ دفترِ ممیزی است.
//
// معماری (ماژولار/توسعه‌پذیر — نباید در هیچ به‌روزرسانی از بین برود):
//   • هر لایه یک تابعِ decide* مستقل دارد که RouterDecision برمی‌گرداند.
//   • CARD_LAYERS: نگاشتِ «کارت → فهرستِ لایه‌های فعال (به‌ترتیبِ اولویت)».
//   • runCard(): لایه‌های کارت را اجرا می‌کند و طبقِ اولویتِ حالت (ENTRY > APPROACHING
//     > NEUTRAL) یک تصمیمِ اصلی برمی‌گرداند؛ بقیهٔ لایه‌های فعال در otherLayers می‌آیند.
//   • افزودنِ لایهٔ جدید = فقط یک ورودی در import + CARD_LAYERS (بدونِ دستکاریِ کارت‌ها).
//   • 🧩 **ماژول‌های لایه‌های حذف‌شده در مخزن باقی می‌مانند** و فقط سیم‌کشی‌شان
//     برداشته می‌شود — همان روشی که برای S341/S323/S327 به‌کار رفت. حذفِ فایل،
//     بازتولیدپذیریِ علمی را نابود می‌کرد؛ و اگر لایه‌ای با بهبود احیا شد،
//     بازگرداندنش **یک خط** است. این عینِ فلسفهٔ ROS2 است: گره‌ها می‌مانند،
//     گراف عوض می‌شود.
//
// ۵ لایهٔ باقی‌مانده (هر کدام دقیقاً یک کارت — قاعدهٔ MTF در جهتِ عکسش):
//   XAUUSD-M5  ← S355  (LPSB state-gate روی مولدِ S333)   · بدهیِ باز، بندِ ۳ سندِ S396
//   XAUUSD-M15 ← S344  (Brooks trend-from-open، SHORT)    · ACCEPT 89.0 · n=92
//   XAUUSD-M30 ← S312  (Mid-Month Drift، زمان-محور)       · ACCEPT 87.7 · n=289
//   XAUUSD-H1  ← S356  (Brooks trend-resumption، causal)  · ACCEPT 79.6 · n=117
//   XAUUSD-H4  ← S382  (مومنتومِ Williams %R، صفر فیلتر)   · ACCEPT 79.2 · n=869
//
//   ⚠️ **هیچ کارتِ EURUSD نمی‌ماند.** نتیجهٔ اندازه‌گیری است نه سلیقه: هیچ لایه‌ای
//      روی هیچ کارتِ یورویی `ACCEPT` نگرفت (تنها کاندیدا، S374/EURUSD-H4،
//      حکمِ `REJECT/15.7` گرفت).
// ============================================================================

import type { Candle } from './indicators'
// `ema` برای اصلاحِ `BUG-S312-FILTGATE` لازم است (فیلترِ کیفیتِ close>EMA200).
import { ema } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'

// --- ماژول‌های آمادهٔ قبلی ---
import { decideS313, S313_M30, S313_H1 } from './squeeze_revival_s313'
import { computeStreakReversal, STREAK_REV_CFG, type StreakRevConfig } from './streak_reversal_s326'
import { computeSellClimax, SELL_CLIMAX_CFG, type SellClimaxConfig } from './sell_climax_s327'
import {
  computeEndOfMonth, EOM_ENTRY_HOURS, EOM_APPROACH_HOUR, EOM_SL_PIP, EOM_TP_PIP, EOM_MAX_HOLD,
} from './end_of_month_drift'
import {
  computeMidMonth, MID_ENTRY_HOURS, MID_APPROACH_HOUR, MID_SL_PIP, MID_TP_PIP, MID_MAX_HOLD,
} from './mid_month_drift'

// --- ماژولِ لایه‌های نو ---
import {
  decideS321, S321_CFG, decideS322, S322_CFG, decideS323, S323_CFG,
  decideS324, S324_CFG, decideS328, S328_CFG, decideS330, S330_CFG,
  decideS334, S334_CFG,
  rawToDecision, type RawSignal, type DecideMeta,
} from './revived_strategies'
import { assetSpec, computeLots, type RegimeInfo } from './router'
// --- ماژولِ نوِ این نشست: احیای squeeze روی H4 (ADX/DI) و M15 (r2+hurst) ---
import { decideS332, S332_CFG } from './squeeze_s332'
// --- ماژولِ نوِ این نشست: احیای S79 (Trend-Pullback) با هندسهٔ منصفانه TP≥SL
//     روی XAU M5/M15/M30/H1 — WR واقعی از دقتِ ورود (rsi_turn/price_turn) + رژیمِ Hurst/ER ---
import { decideS333, S333_CFG } from './s333_pullback'
// --- ⭐ لایهٔ S355 — نخستین لایهٔ پروژه با **۱۱/۱۱ دروازهٔ RQS2 (v2.4)** ---
//     «دروازهٔ حالتِ ساختارِ لگ-متناسب» (LPSB, L=8 f=0.33) روی مولدِ S333/M5:
//     ورودِ لانگ فقط اگر ساختارِ خُرد نزولی باشد (state=−1) — جهتِ ضدِ شهود، اندازه‌گیری‌شده.
//     XAUUSD-M5: RQS2=83.9 · WR 72.34% · PF 3.951 · lift +25.27pp · z 3.47 · p_perm 0.000259
//     holdout ۴۰٪ دست‌نخورده: WR 81.25% · maxDD 1.98% · Δسودِ خالص +$2,469
//     منشأ: منبعِ تلگرامیِ Market_Structure_Break_and_Order_Block_v3 (MT4/GPL) — بازسازیِ **علّی**
//     (نسخهٔ اصلی repaint داشت). پورتِ verbatim تأیید شد: mismatch=0 روی ۲۰۰٬۰۰۰ کندل
//     (web_tool/parity_s355_state.mjs). همپوشانی: زیرمجموعهٔ اکیدِ S333 (۷۳.۴٪ از ورودهایش).
//     ⚠️ تا پیش از S431 فقط روی M5 وصل می‌شد؛ M15/M30/H1 در دروازهٔ H3 (توان)
//        مانده بودند ⇒ حقِ اتصال نداشتند.
//     ✅ **رفعِ محدودیت در S431:** آن سه کارت با تجمیعِ تقویمی در یک جمعیتِ
//        واحد (n=۱۶۸) هر ۱۱ دروازه را پاس کردند ⇒ RQS2=93.9 · z=4.706.
//        شکستِ قبلی‌شان **کمبودِ نمونه** بود نه نبودِ لبه (n=۳۸/۲۸/۶۶ در برابرِ
//        n_required_h3=۷۲.۴؛ lift هر سه مثبت: +۱۷.۴/+۱۹.۵/+۱۶.۲).
//     سند: results/S355_LPSBStateFilterRevival_Xauusd_M5_rqs2-84.md
//           results/S431_LpsbMulticardPool_Xauusd_M5M15M30H1_rqs2_93_ACCEPT.md
import { withLpsbGate, S355_CFG, S431_CFG } from './lpsb_state_s355'
// --- لایهٔ نوِ این نشست: S335 Reflex-TrendFlex Cycle-Turn (چرخهٔ DSP اِهلرز) ---
//     خریدِ کفِ چرخه درونِ روندِ صعودیِ کم‌تأخیر روی XAU M5/M15/H1 —
//     همپوشانیِ صفر با S333؛ RQS+ = 92.2/89.7/89.7 ---
import { decideS335, S335_CFG } from './s335_reflex_cycle'
// --- لایهٔ نوِ این نشست: S340 Brooks «Micro Channel» (فصلِ ۱۶) ---
//     ادامهٔ روند/failed-pullback روی XAUUSD-H4 — RQS+ = 92.6 (WR 65.6% · PF 2.13 · +$1,080)
//     همپوشانی: S327=0% ، S332=8.2% ⇒ لبهٔ مستقل (نه فیلتر). پورتِ verbatim تأییدشد (64/64 سیگنال یکسان).
import { decideS340, S340_CFG } from './micro_channel_s340'
// --- ⚰️ S341 Brooks «Swing Points / Horizontal Lines» (فصلِ ۱۷) — **حذف‌شده / DEAD** ---
//     این لایه با نمرهٔ **RQS+** (94.7 / 89.8 / 89.7 / 94.5) وصل شده بود، نه با RQS2.
//     بازداوریِ کامل زیرِ **RQS2 v2.4** ⇒ بهترین نمرهٔ اندازه‌گیری‌شده = **28.6** (سد = 70).
//     هر چهار پروتکلِ بهبودِ پیش‌ثبت‌شده شکست خوردند (S357 · S358 · S359 · S360 · S362):
//       · خانوادهٔ ۷۲ عضوی و رأیِ اجماعی تا **۳۸× نمونه** ⇒ لبه ناپدید شد، نه تیزتر.
//       · فیلترِ رژیمِ Hurst/Entropy: درون‌نمونه +10.84pp ⇒ **خارج‌نمونه −3.70pp**.
//       · هندسهٔ شناورِ ATR-محور: OOS lift ≈ صفر در هر ۴ کارت.
//       · همپوشانی با لایه‌های هم‌کارت **< ۱.۸٪** ⇒ فیلترِ همپوشان حساباً no-op.
//     ⇒ طبقِ «قانونِ مرگِ ابدی» حکم **DEAD** و از هر ۴ کارت **حذف** شد.
//     سند: results/S341_BrooksSwingFadeRejudged_Xauusd_M5M15M30H1_rqs2-28.md
//     ماژولِ ./swing_fade_s341 در مخزن **باقی می‌ماند** (رکوردِ تاریخی + منبعِ بازتولید)
//     ولی دیگر import/سیم‌کشی نمی‌شود — این همان روشِ ماژولارِ ROS2-مانند است.
// --- لایهٔ نوِ این نشست: S344 Brooks «Trend from the Open & Small Pullback Trends» (فصلِ ۲۳) ---
//     open-extreme first-pullback continuation روی XAUUSD-M15 SHORT — RQS+=91.4 (WR 64.1% · PF 2.08 · +$1,571).
//     لبهٔ مستقل خارج از پنجره‌های زمان-محورِ S139..S144: RQS+=92.9 (n=57) ⇒ لبهٔ نو (نه فیلتر).
//     نخستین لبهٔ SHORT روی کارتِ XAUUSD-M15. پورتِ verbatim تأیید شد (۹۲/۹۲ سیگنال یکسان، mismatch=0).
import { decideS344, S344_CFG } from './trend_from_open_s344'
// --- لایهٔ نوِ این نشست: S345 Brooks «Reversal Day» (فصلِ ۲۴) ---
//     چرخشِ روندِ درون‌روزی: روندِ اولیهٔ روز + اسپایکِ ضدِ روندِ قوی + شکستِ خطِ روندِ روز
//     + تأییدِ lower-high/higher-low، در پنجرهٔ میانه/اواخرِ روز و رژیمِ چرخش‌پذیر r2(34)≤0.55.
//     • XAUUSD-M15 LONG  — RQS+=90.7 (WR 62.4% · PF 2.30 · +$2,422.8) + فیلترِ بهبود «حذفِ ابتدای ماه»
//     • EURUSD-M30 SHORT — RQS+=91.7 (WR 62.5% · PF 2.38 · +$2,281.6) — نخستین لایهٔ SHORT این کارت
//     همپوشانی: XAU-M15=48.5% با زمان-محورِ S139..S144 اما بخشِ مستقل کیفیتِ بالاتر (WR 65.0/PF 2.56)
//     ⇒ لبهٔ نو، نه بازتولیدِ زمان-محور. EUR-M30=30.6% (خوش‌خیم).
//     پورتِ verbatim تأیید شد (۱۹۳/۱۹۳ سیگنال یکسان روی هر دو کارت، mismatch=0).
import { decideS345, S345_CFG } from './reversal_day_s345'
// --- S356 = احیای S354 Brooks «Trend Resumption Day» (فصلِ ۲۵) — ✅ WIRED ---
//     تاریخچه: نسخهٔ non-causal (پنجرهٔ پایانی = ۰.۶۸ × طولِ **کلِ** روز) look-ahead
//     داشت و کنار گذاشته شد؛ سپس نسخهٔ causal (ساعتِ ثابتِ UTC ≥ ۱۶) با معیارِ
//     RQS2 نسخهٔ قدیم در دروازهٔ H3 رد شد — اما آن H3 با شرطِ بازنشسته‌شدهٔ
//     `WR > perm_max` داوری می‌کرد که با تعدادِ قرعه بزرگ می‌شود، پس حکمش به seed
//     وابسته و بی‌معنا بود.
//     بازداوری با معیارِ اصلاح‌شدهٔ **v2.4**: ACCEPT در هر ۱۱ دروازه و در هر ۳ seed
//     (RQS2 = ۸۱.۱/۸۱.۳/۸۱.۵) · n=۱۱۷ · WR=۵۱.۲۸٪ · lift=+۱۵.۰ نقطه · z=۳.۳۶
//     · جریمهٔ سخت‌گیرانهٔ ۲۸۸-آزمونی هم ACCEPT.
//     نالِ رزولوشن‌بالا (۲۰۰٬۰۰۰ قرعه × ۳ seed، با آستانهٔ محافظه‌کارانه):
//     کرانِ بالای ۹۵٪ برای p = ۷.۲e-۴ < ۱e-۳ ⇒ مرزِ p قطعی حل شد.
//     همپوشانی: ۲۵.۶٪ (۳۰/۱۱۷) — فقط با S313 (۲۵) و S335 (۵)؛ ۸۷ ورودِ بی‌همپوشان
//     خودشان lift=+۱۵.۲۴ دارند ⇒ لبه در بخشِ همپوشان نیست.
//     ⚠️ فقط روی XAUUSD-H1 وصل می‌شود؛ در سوییپِ ۱۶-کارتی، ۹ کارت REJECT و ۶ کارت
//     بی‌سیگنال/بی‌داده بودند ⇒ هیچ کارتِ دیگری حقِ اتصال ندارد.
//     parity سیگنال: ۱۱۷/۱۱۷ با mismatch=0 (results/_scan_S356/parity_causal_after.json)
//     سند: results/S356_BrooksTrendResumptionCausal_Xauusd_H1_rqs2-81.md
import { decideS354, S354_CFG } from './trend_resumption_s354'
// --- ⭐ لایهٔ نوِ این نشست: S374 «دروازهٔ شکستِ Kennedy» — ✅ ACCEPTED روی H4 ---
//     منشأ: منبعِ تلگرامیِ `1101 Trading the Line Excerpt.pdf` (Jeffrey Kennedy، فصلِ ۲):
//     «شکستِ خطِ روند را با close نسنجید — تا وقتی **کلِ دامنهٔ** کندل از خط عبور
//     نکرده، شکستِ مشروعی رخ نداده.» ⇒ `high < line` (نزولی) / `low > line` (صعودی).
//     این تنها تغییرِ لایه است؛ هارنسِ S373 (کانالِ Stairs) عیناً حفظ شد.
//     • احیای S373 که **تنها** در بندِ تکرارپذیری مرده بود (h1=−0.0134 / h2=+0.0537
//       ⇒ تغییرِ علامت). با دروازهٔ Kennedy: h1=+0.0933 / h2=+0.1696 ⇒ هر دو مثبت.
//     • XAUUSD+EURUSD-H4: z=+4.100 (سد=2.570 · N=112) · n=1,062 (نیاز=417)
//       · e_pip طلا ۱۱.۶۷→۳۲.۹۷ (c=3.3) · یورو ۱.۵۷→۶.۴۴ (c=1.6) ⇒ هر دو مستقل بالای هزینه.
//     • آزمونِ علامت (مصون از هر وزن‌دهی): ۱۷/۲۰ عضوِ مشترک بهبود · p_exact=0.00129.
//     • سوگیریِ انتخابِ عضو وجود دارد ولی **محافظه‌کارانه** است (دلتای هم‌سنگ +0.1399
//       بزرگ‌تر از خام +0.1131) چون اعضای حذف‌شده در پایه قوی‌ترین بودند.
//     ⚠️ فقط H4 وصل می‌شود. هر ۵ تایم‌فریمِ مشترک آزموده شد و M5/M15/M30/H1 در بندِ
//        اقتصاد رد شدند. علامتِ اثر **تابعِ تایم‌فریم** است (ρ_Spearman=+1.000، شانسِ
//        تصادفی 1/120): M5 −0.0208 → M15 −0.0082 → M30 +0.0085 → H1 +0.0688 → H4 +0.1399.
//        مکانیزم: هرچه TF بالاتر، نسبتِ نویزِ درون‌کندلی به سیگنال کمتر.
//     ⚠️ ماهیت: این **فیلتر نیست، قاعدهٔ زمان‌بندیِ ورود است**. اثباتِ زیرمجموعه در سطحِ
//        بولیِ خام برقرار است ولی پس از `_first_per_seg` نقض می‌شود، چون شرطِ close
//        زودتر شلیک می‌کند ⇒ دو بازو **کندل‌های متفاوتی** می‌گیرند (تأخیرِ ۱..۷ کندل).
//        همپوشانی در دو فضا: فضای کانال ≈ کامل · فضای کندل ≈ صفر.
//     ⚠️ رتبهٔ محافظه‌کارانه + کم‌بسامد: طلا ~۴ رویدادِ مستقل در سال (۴۳ کندلِ مجزا در
//        ۱۰.۸ سال). بوت‌استرپِ خوشه‌ای (بازنمونه از **کانال‌ها**): بازوی پایه CI شاملِ صفر
//        (P(≤0)=36.2٪) ولی Kennedy `[+0.0014, +0.2544]` ⇒ عبور از صفر، اما به‌سختی.
//     parity سیگنال: طلا ۲۰/۲۰ و یورو ۸۹/۸۹ با mismatch=0 روی پنجره‌های رو-به-جلو
//     (results/_parity/s374_parity_PASS.txt) ⇒ هم صحتِ عددی، هم نبودِ نشتِ آینده.
//     سند: results/S374_KennedyBreakGate_XauEur_H4_rqs2-ACCEPTED.md
import { computeKennedy, KENNEDY_CFG } from './kennedy_break_s374'
// --- ⭐ لایهٔ S382 «مومنتومِ Williams %R» — ✅ ACCEPTED روی XAUUSD-H4 ---
//     تنها لایهٔ پروژه که با **صفر فیلتر** هر ۱۱ دروازهٔ RQS2 را پاس کرد،
//     و نخستین لایه‌ای که **پیش از آزمون** توانِ آماریِ کافی داشت (n=۸۶۹ > ۷۸۴).
//     قاعده: `Williams %R(14)` **گذر** به بالای −۱۳ ⇒ قیمت در ۱۳٪ بالاییِ دامنه
//     (اشباعِ خرید) و ما همان‌جا **می‌خریم** ⇒ لایهٔ **مومنتومی** نه بازگشتی.
//     خلافِ خواندنِ کلاسیک؛ فقط چون جاروب هر دو جهت را آزمود کشف شد.
//     • RQS2 = **۸۳.۵** · هر ۱۱ دروازه ✅ · rank_tier = A
//     • n=۸۶۹ (۵۵.۹/سال) · WR=۴۸.۹۱٪ · سربه‌سر=۴۱.۰۷٪ · lift=**+۷.۸۳**
//     • PF=۱.۴۶۷ · سودِ خالص=**$۵۴٬۰۹۸.۸** · maxDD=۵.۶٪ · رشتهٔ باخت ۱۲ (مجاز ۱۶)
//     • انتظار=۲۷.۳۶ pip؛ در **۲× هزینه** هم ۲۴.۰۶ pip ⇒ حاشیهٔ ایمنیِ اسپرد
//     • هندسه: SL=۱.۵×ATR(۱۰۰)=۱۲۲.۸۵ pip · TP=۱.۵×SL=۱۸۴.۲۸ pip (TP>SL)
//     • مدلِ صفر: سه مرجعِ کورِ نسبت‌به‌هم روی ~۴۱٪ همگرا (۴۱.۰۷ / ۴۰.۵۴ / ۴۰.۹۸)
//       و ۲۰۰۰ جایگشت **هرگز** به ۴۸.۹۱ نرسید (بهترین ۴۴.۵۹) · z=۴.۷۵۴ (سد ۴.۰۶۷)
//     • خارج‌نمونهٔ ۳۰٪ دست‌نخورده: WR=۴۹.۷۳٪ · PF=۱.۴۸۱ ⇒ **بهتر** از درون‌نمونه
//     • هر ۴ ربعِ تقویمی سودِ مثبت (cal_positive = 4/4)
//     ⚠️ بازداوریِ S395 زیرِ کرانِ نو (M_eff=۲۷۸٬۴۴۷ ⇒ سد=۴.۶۰۸۶): z=۵.۰۲۳۶
//        ⇒ **هنوز پاس** با حاشیهٔ +۰.۴۱۵۰. اتصال با معیارِ حاکمِ فعلی معتبر است.
//     ⚠️ فقط XAUUSD-H4 وصل می‌شود. در جاروبِ ۸-کارتی، بهترین کارتِ بعدی
//        (XAUUSD-H1 با قاعدهٔ خواهر cci20) در دروازهٔ H5 مرد (S389 DEAD)
//        ⇒ هیچ کارتِ دیگری حقِ اتصال ندارد.
//     همپوشانی: با S389 ژاکاردِ زمانی ۰.۰۳۰۱ ⇒ عملاً مستقل؛ با S374/S340/S332
//        اندیکاتورِ پایهٔ متفاوت و «گذر»محور ⇒ لبهٔ نو، نه فیلترِ تأیید.
//     منبعِ حقیقت: strategies/s382_williamsr_momentum.py (پورتِ verbatim)
//     سند: results/S382_WilliamsR_Xauusd_H4_rqs2-83.md
import { decideS382, S382_CFG } from './williams_momentum_s382'
// ⭐ S950 — «پس‌لرزهٔ جهش، هم‌راستا با رانش» (Bipower jump + drift alignment) · XAUUSD-H8
//    RQS2=80 · هر ۱۱ دروازه پاس · پایدار روی ۴ seed · n=224 · WR=61.6% · maxDD=4.92%
//    سند: results/S950_JumpAftermathDriftAligned_Xauusd_H8_rqs2_80_ACCEPT.md
import { decideS950, S950_CFG } from './jump_aftermath_s950'
// ⭐ S965 — «ماندگاریِ درون-کندلیِ اثرِ قیمتیِ کایل» · XAUUSD-H8 (تنها کارتِ ACCEPT)
//    RQS2=82.2 · هر ۱۱ دروازه سبز · n=146 · WR=54.79% · lift=+12.84pp · z=3.14 · PF=1.81
//    سند: results/S965_KyleIntrabarPermanence_Xauusd_H8_rqs2_82_ACCEPT.md
import { decideS965, S965_CFG } from './kyle_intrabar_s965'
// ⭐ S966 ⭐نو — «ماندگاریِ کایل × هم‌راستاییِ درفت» · XAUUSD-H8 (تنها کارتِ ACCEPT؛
//    H6 با RQS2=۷.۸ رد شد ⇒ قانونِ MTF: هیچ تعمیمی به کارتِ دیگر نمی‌شود)
//    RQS2=85.8 · هر ۱۱ دروازه سبز · n=74 · WR=55.41% · lift=+11.99pp · z=3.21 · PF=1.87
//    ⚠️ **زیرمجموعهٔ ساختاریِ ۱۰۰٪ِ S965** (اندازه‌گیری‌شده، نه ادعا):
//       results/_scan_S966/overlap_s950_s965_s966_h8.json — ارزشش فیلترِ کیفیت است
//       (lift ۲.۶۱ → ۱۱.۹۹pp)، نه پوششِ نو ⇒ در CARD_LAYERS **زیرِ** S965/S950 می‌آید.
//    سند: results/S966_KylePermanenceDriftAligned_Xauusd_H8_rqs2_86_ACCEPT.md
import { decideS966, S966_CFG } from './kyle_permanence_drift_s966'
// ⭐⭐ S919 — «شوکِ مطلعِ هم‌راستا با قراردادِ بازار» · XAUUSD-**H6** (کارتِ نو)
//    RQS2 = **88.9** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی · n_trials=2
//    n=106 · WR=55.66٪ · null_ref=40.04٪ · lift=+15.62pp · z=3.282 (z_margin=2.762)
//    p_perm=8.42e−04 · PF=1.85 · maxDD=2.89٪ · top_win_share=8.1٪
//    قاعده = پایهٔ منجمدِ S965 (شوکِ رنج ≥ 2.618×ATR21[t−1] با ماندگاری ρ ≥ 0.618،
//    جهتِ follow) **×** گیتِ قراردادِ کینزیِ S604 (درفتِ علّیِ ۶۰ روزِ تقویمی =
//    ۲۴۰ کندلِ H6: لانگ فقط اگر close[t−1] > close[t−1−240]، شورت آینه‌ای).
//    صفر پارامترِ جست‌وجو‌شده — هر عدد از فایل‌های کامیت‌شدهٔ دیگران به ارث رسیده
//    ⇒ هیچ چندگانگیِ نو؛ کلِ ۱۵.۶ سال یک بار لمس شد.
//    ⓵ **اولین ACCEPT روی کارتِ H6** — پیش از این هیچ لایه‌ای روی H6 وصل نبود؛
//       خوشهٔ شوک (S602/S770/S950/S526/S965/S966) همه H8 بودند.
//    ⓶ ابطال‌گرِ P1 (ضدِ توان‌سوزی): بازوی بی‌گیت = بازتولیدِ مستقلِ S965 روی H6
//       ⇒ n=239/WR 48.1٪ (S965 خودش n=240 گزارش کرده بود — تطابقِ n اثباتِ
//       درستیِ پیاده‌سازی است). گیتِ قرارداد همان کارتِ REJECT را به ACCEPT برد.
//    ⓷ ابطال‌گرِ P3 (روایتِ کینزی): بازوی **خلافِ** قرارداد WR=42.1٪ (n=133) —
//       بازار شوکِ خلافِ قرارداد را «اختلالِ موقت» می‌خواند و جذب می‌کند.
//    ⓸ **قلمرو قفل: فقط H6.** کارتِ H3 با RQS2=16.0 رد شد (n=317 · WR=44.79٪ ·
//       z=1.87 · ردِ H1 H3 H7 H8 H10) ⇒ تعمیم ممنوع. H8 عامدانه از پیش‌ثبت حذف
//       شده بود چون S965/S966 آن‌جا ACCEPT دارند.
//    ⓹ هم‌پوشانی: رویدادها با کارتِ H8 ذاتاً هم‌پوشان‌اند (یک شوکِ ۸ساعته اغلب
//       شوکِ ۶ساعته هم هست) ولی **کارت‌ها متفاوت‌اند** ⇒ لایه حذف نمی‌شود؛
//       فقط صفِ FIFO/سایزِ محتاط روی حسابِ واقعی لازم است (در manageNote ثبت شد).
//    🔴 دامِ پورت: ماسکِ بک‌تست **از پیش شیفت‌شده** است (`lm[1:] = up[:-1]`) ⇒
//       ورودِ واقعی در **رویداد+۲** است. پریتی این را عددی اثبات کرد:
//       رویداد+۲ ⇒ WR=55.66٪ · رویداد+۱ ⇒ WR=48.11٪ (زیرِ سربه‌سر).
//       پس computeS919 رویداد را روی کندلِ i−1 می‌سنجد. پریتی: web_tool/parity_s919_signal.mjs
//    سند: results/S919_ConventionAlignedInformedShock_Xauusd_H6_rqs2_88.9_ACCEPT.md
import { decideS919, S919_CFG } from './convention_shock_s919'
// ⭐⭐ S800 — «فشردگی → گشایش» (Squeeze-Expansion Breakout) · XAUUSD-D1 **و** XAUUSD-H12
//    دو حکمِ **مستقلِ تک-کارتی** (نه استخری): D1 = RQS2 **91.1** · H12 = RQS2 **83.6**
//    هر کارت جداگانه با مسیر C (hold-out فیزیکی، n_trials=1) داوری شد و هر دو
//    جداگانه هر ۱۱ دروازهٔ H0..H10 را پاس کردند.
//      D1  : n=81  · WR=70.37٪ · PF=1.937 · maxDD=2.77٪ · MCL=3 · lift=+21.12pp · z=3.80
//      H12 : n=183 · WR=54.60٪ · PF=1.550 · maxDD=5.64٪ · MCL=7 · lift=+12.93pp · z=3.55
//    ⚠️ قانونِ MTF (هر دو جهت): چون **دو** کارت شاهدِ مستقل دارند، هر دو باید وصل
//       شوند؛ و چون H1/H3/H6 در آزمونِ نهایی REJECT شدند (4.9 / 20.5 / 19.7) و
//       M1..M30 + H2 اصلاً توان نداشتند (lift·√n < 78 ⇒ هرگز آزمونِ نهایی نشدند)،
//       تعمیم به هیچ تایم‌فریمِ دیگری مجاز نیست.
//    منبعِ حقیقت: strategies/s800_squeeze_expansion.py (پورتِ verbatim)
//    پیکربندیِ قفل‌شده: results/_scan_S800/{D1,H12}_locked.json
//    سند: results/S800_SqueezeExpansion_Xauusd_M1toMN1_rqs2_91_ACCEPT.md
import { decideS800, S800_CFG } from './squeeze_expansion_s800'
// ⭐⭐ S770 — «انبساطِ دامنه نسبت به ADR با تداوم» · XAUUSD · استخرِ **{D1 + H8}** · دوسویه
//    RQS2 = **82.4** · هر ۱۱ دروازهٔ H0..H10 پاس · n=689 · WR=44.70٪ · PF=1.398
//    lift=+7.23pp · z=3.91 (سد 2.897 با n_trials=**301** صادقانه) · p_perm=4.5e−05
//    maxDD=5.83٪ · net=+$29,077 · holdout: PF=1.502 (**بهتر** از نیمهٔ کشف)
//    هر دو سو لبه دارند: long +9.06pp (n=358) · short +5.25pp (n=331)
//    ⚠️ حکم روی **استخرِ دوکارتی** است (D1=266 + H8=423 معامله پس از FIFO تقویمی
//       با همزمانیِ حداکثر ۱). هر کارتِ تکی به‌تنهایی REJECT بود (D1=21.0 · H8=19.3)
//       — علتش کمبودِ n بود نه نبودِ لبه ⇒ طبقِ قانونِ MTF **هر دو** وصل می‌شوند و
//       حذفِ یکی، جمعیتی که حکم بر آن صادر شده را نابود می‌کند.
//    قاعده: frac=(close−openِ روزِ UTC)÷ADR21 و **عبورِ** آن از ±0.65 ⇒ تداوم هم‌جهت.
//    parity: mismatch=0 روی هر دو کارت (۶۳۷ سیگنال) — results/_scan_S770/parity_s770_PASS.txt
//    سند: results/S770_AdrExpansionPool_Xauusd_D1H8_rqs2_82_ACCEPT.md
import { decideS770, S770_CFG } from './adr_expansion_s770'
// ⭐ S560 — «گپِ منفیِ بازگشایی» (GapOpen Negative-Gap) · XAUUSD-M5 · LONG-only
//    RQS2=**96.0** — بالاترین نمرهٔ لایه‌های وصل‌شده تا امروز · هر ۱۱ دروازه پاس
//    n=407 · WR=71.5٪ · PF=2.514 · maxDD=2.43٪ · lift=+43.98pp · z=19.87 (z_margin=16.885)
//    آستانهٔ علّیِ q80 **منجمدشده** از ۱۵.۶ سال داده (results/_s560_arms/frozen_thresholds_M5.json)
//    parity: صفر اختلاف روی ۴۰۶۹ مرزِ روز (results/_s560_arms/parity_ts_M5.json)
//    سند: results/S560_GapOpenNegGap_Xauusd_M1M5M15M30H1_rqs2_96_ACCEPT.md
import { decideS560, S560_CFG } from './gap_open_s560'

// --- لایهٔ نوِ این نشست: S562 «گپِ منفیِ بازگشایی + فیلترِ نوسانِ علّی» ---
//    خانوادهٔ گپِ S560 با یک **اهرمِ انتخابِ معامله**: اگر نوسانِ مرجعِ ۱۴ روزِ
//    گذشته از چندکِ qv بالاتر باشد، سیگنال **رد** می‌شود (گپ در بازارِ پرنوسان
//    نویز است، نه لبه). دو ACCEPT مستقل روی دو تایم‌فریم:
//      • XAUUSD-M15 → RQS2 = **95.3** · n=438 · WR 70.78% · maxDD 3.71%
//      • XAUUSD-H1  → RQS2 = **96.0** · n=254 · WR 68.90% · maxDD 2.07%
//    هر ۱۱ دروازهٔ RQS2 v2.6 در **هر دو** TF سبز.
//    آستانه‌ها منجمدشده از ۱۵.۶ سال داده (results/_s562_arms/frozen_thresholds_*.json)
//    ✔ اثباتِ پورت (هر دو TF): `only_ts = 0` روی ۴۰۶۷ مرزِ M15 و ۳۶۶۵ مرزِ H1 —
//      یعنی ماژول هیچ سیگنالِ ساختگی نمی‌سازد؛ و تمامِ اختلاف‌ها (۵ در M15، ۳ در
//      H1) با **گاردِ سلامتِ فید** توضیح داده شدند (`unexplained = 0`):
//      results/_s562_arms/diag_mismatch_M15.json · diag_mismatch_H1.json
//    ✔ مجوزِ انجماد: در پنجره‌ای که سایت واقعاً می‌بیند (M15 ۲۲روز، H1 ۶۵روز)
//      آستانهٔ منجمد **۱۰۰٪** همان تصمیمِ چندکِ رولینگ را می‌دهد:
//      results/_s562_arms/recency_M15.json · recency_H1.json
//    ⚠️ هم‌خانوادگی: jaccard روزانهٔ M15↔H1 = ۰.۵۶ و با S560-M5 ≈ ۰.۵۱–۰.۵۴ —
//      یک رویدادِ گپ که در چند TF دیده می‌شود؛ در سایزِ پرتفوی **هم‌خانواده**
//      حساب می‌شوند (سند §۵).
//    سند: results/S562_GapOpenVolFilter_Xauusd_M15H1_rqs2_96_ACCEPT.md
import { decideS562, S562_CFG } from './gap_open_volfilter_s562'

const GOLD_PIP = 0.1

// ---------------------------------------------------------------------------
// آداپترِ لایه: امضای یکنواخت برای همهٔ لایه‌ها
//   ورودی: کارت (asset-tf)، AnalysisResult، کندل‌ها، ساعت/زمانِ UTC، سرمایه/ریسک
//   خروجی: RouterDecision (یا null اگر لایه روی این کارت فعال نیست)
// ---------------------------------------------------------------------------
export interface LayerContext {
  cardId: string
  a: AnalysisResult
  candles: Candle[]
  utcHour: number
  times: number[]
  capital: number
  riskPct: number
}
export type LayerFn = (ctx: LayerContext) => RouterDecision | null

function lightRegime(adxVal: number, trendy: boolean, bucket: string): RegimeInfo {
  return { regime: trendy ? 'trend_up' : 'range', efficiencyRatio: 0, trendy, adx: isFinite(adxVal) ? adxVal : 0, activeStream: trendy ? 'bull' : 'none', bucket }
}

// ---- آداپترِ S326 (Streak-Reversal) ----
function s326Layer(cfg: StreakRevConfig): LayerFn {
  return (ctx) => {
    const sig = computeStreakReversal(ctx.candles, cfg)
    const price = ctx.a.price
    const raw: RawSignal = {
      active: sig.active, approaching: sig.approaching, direction: 'LONG',
      slDist: cfg.slMult * sig.atrVal, tpDist: cfg.tpMult * sig.atrVal, maxHoldBars: cfg.maxHold,
      reason: sig.reason,
      approachReason: sig.approaching ? `بازگشتِ RSI به زیرِ ${cfg.rsiMax}` : undefined,
      indicators: [
        { name: `رگهٔ نزولی (≥${cfg.streakN} کندل)`, value: `${sig.streak}` + (sig.streak >= cfg.streakN ? ' ✔' : ''), status: sig.streak >= cfg.streakN ? 'ok' : 'neutral' },
        { name: `RSI-14 اشباعِ فروش (≤${cfg.rsiMax})`, value: isFinite(sig.rsiVal) ? sig.rsiVal.toFixed(0) : '—', status: sig.rsiVal <= cfg.rsiMax ? 'ok' : 'warn' },
        { name: `روندِ کلان (EMA${cfg.emaTrend})`, value: sig.aboveTrend ? 'صعودی ✔' : 'نزولی ✘', status: sig.aboveTrend ? 'ok' : 'bad' },
      ],
    }
    const reg = lightRegime(0, sig.aboveTrend, 's326_streak')
    return rawToDecision(raw, {
      code: 'S326', name: 'Streak-Reversal بازگشتی', kind: 'mean-reversion' as any,
      manageStyle: 'fixed-tp-sl', manageNote: 'بازگشت به میانگین با TP<SL؛ هدفِ نزدیک را زود بگیر، SL جابه‌جا نشود.',
      filters: [`رگهٔ ≥${cfg.streakN}`, `RSI≤${cfg.rsiMax}`, `EMA${cfg.emaTrend} صعودی`, cfg.runMinAtr > 0 ? `شتابِ رگه≥${cfg.runMinAtr}×ATR` : 'بدونِ قیدِ شتاب'],
    }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
  }
}

// ---- آداپترِ S327 (Sell-Climax Reversal) ----
function s327Layer(cfg: SellClimaxConfig): LayerFn {
  return (ctx) => {
    const sig = computeSellClimax(ctx.candles, cfg)
    const price = ctx.a.price
    const raw: RawSignal = {
      active: sig.active, approaching: sig.approaching, direction: 'LONG',
      slDist: cfg.slMult * sig.atrVal, tpDist: cfg.tpMult * sig.atrVal, maxHoldBars: cfg.maxHold,
      reason: sig.reason,
      approachReason: sig.approaching ? `تأییدِ بازگشت (RSI≤${cfg.rsiMax} + کندلِ صعودی)` : undefined,
      indicators: [
        { name: `کندلِ کلایمکس (بدنه≥${cfg.kBody}×MA)`, value: sig.isClimax ? 'بله ✔' : 'خیر', status: sig.isClimax ? 'ok' : 'neutral' },
        { name: `RSI-14 اشباعِ فروش (≤${cfg.rsiMax})`, value: isFinite(sig.rsiVal) ? sig.rsiVal.toFixed(0) : '—', status: sig.rsiVal <= cfg.rsiMax ? 'ok' : 'warn' },
        { name: `روندِ کلان (EMA${cfg.emaTrend})`, value: sig.aboveTrend ? 'صعودی ✔' : 'نزولی ✘', status: sig.aboveTrend ? 'ok' : 'bad' },
      ],
    }
    const reg = lightRegime(0, sig.aboveTrend, 's327_climax')
    return rawToDecision(raw, {
      code: 'S327', name: 'Sell-Climax بازگشتی (Brooks)', kind: 'price-action' as any,
      manageStyle: 'fixed-tp-sl', manageNote: 'تخلیهٔ فروش (Brooks exhaustion) با TP<SL؛ هدفِ نزدیک را بگیر، SL جابه‌جا نشود.',
      filters: [`کلایمکس kBody=${cfg.kBody}`, `body/range≥${cfg.brMin}`, `RSI≤${cfg.rsiMax}`, `EMA${cfg.emaTrend} صعودی`],
    }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
  }
}

// ---- آداپترِ S310 (End-of-Month Drift) ----
const s310Layer: LayerFn = (ctx) => {
  const sig = computeEndOfMonth(ctx.times, ctx.utcHour)
  const price = ctx.a.price
  const active = sig.state === 'ENTRY'
  const approaching = sig.state === 'APPROACHING'
  const raw: RawSignal = {
    active, approaching, direction: 'LONG',
    slDist: EOM_SL_PIP * GOLD_PIP, tpDist: EOM_TP_PIP * GOLD_PIP, maxHoldBars: EOM_MAX_HOLD,
    reason: sig.reason,
    approachReason: approaching ? `ورود به ساعاتِ ${EOM_ENTRY_HOURS.join('/')} UTC در پنجرهٔ پایانِ ماه` : undefined,
    indicators: [
      { name: 'پنجرهٔ پایانِ ماه (۷ روزِ مانده)', value: sig.isEomWindow ? 'باز ✔' : 'بسته', status: sig.isEomWindow ? 'ok' : 'neutral' },
      { name: 'ساعتِ UTC', value: `${sig.utcHour}:00` + (EOM_ENTRY_HOURS.includes(sig.utcHour) ? ' (ورود)' : ''), status: EOM_ENTRY_HOURS.includes(sig.utcHour) ? 'ok' : 'neutral' },
    ],
    // 🕒 باگِ User Note #۳: دروازهٔ زمانی برای نوارِ شمارشِ معکوس زیرِ کارت.
    timeGate: {
      layerCode: 'S310', label: 'درایوِ پایانِ ماه',
      entryHoursUtc: EOM_ENTRY_HOURS,
      dayOfMonthNote: '۷ روزِ پایانیِ هر ماه',
      windowOpen: sig.isEomWindow && EOM_ENTRY_HOURS.includes(sig.utcHour),
      endHourUtc: Math.max(...EOM_ENTRY_HOURS) + 1,
    },
  }
  const reg = lightRegime(0, true, 's310_eom')
  return rawToDecision(raw, {
    code: 'S310', name: 'End-of-Month Drift', kind: 'time' as any,
    manageStyle: 'fixed-tp-sl', manageNote: `هدف/حدِ ثابت (${EOM_TP_PIP}/${EOM_SL_PIP} pip)؛ تا پایانِ پنجره یا برخورد نگه‌دار.`,
    filters: ['۷ روزِ پایانِ ماه', `ساعاتِ ${EOM_ENTRY_HOURS.join('/')} UTC`, 'فیلترِ کیفیت (ATR/close-pos/EMA200)'],
  }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
}

// ---- آداپترِ S312 (Mid-Month Drift) — SL/TP per-TF ----
//
// 🐞 **اصلاحِ `BUG-S312-FILTGATE` (کشف‌شده در S432) — عدم‌تطابقِ پورت**
// ---------------------------------------------------------------------------
// نشانه: `computeMidMonth` پارامترِ سومِ `filt?: MidFilter` دارد که فیلترِ
// کیفیتِ `close > EMA200` را اعمال می‌کند، ولی **تنها فراخوانیِ کلِ پروژه**
// (همین‌جا) آن را پاس نمی‌کرد. و `midFiltersPass(undefined)` صریحاً
// `return true` می‌دهد ⇒ دروازه **همیشه باز** بود.
//
// چرا این جدی است و نه یک ریزه‌کاری:
//   ⓵ حکمِ `ACCEPT`ِ کارتِ `XAUUSD-M30` (`RQS2 = 87.7`, `n=289`, `z=3.66`)
//      **با** این فیلتر گرفته شده است (`s312_oos_check.py`:
//      `quality_filter=True`). پس سایت لایه‌ای را می‌راند که با نسخهٔ
//      نمره‌گرفته **یکی نیست** ⇒ اعدادِ حکم ضمانتی برای رفتارِ سایت نبودند.
//   ⓶ آرایهٔ `filters` پایین‌تر صریحاً به کاربر می‌گوید
//      «فیلترِ کیفیت (روندِ کلان)» — یعنی سایت چیزی را **اعلام** می‌کرد که
//      اجرا نمی‌کرد. این از خودِ باگ بدتر است.
//   ⓷ جهتِ خطا «سخاوتمندانه» است نه محافظه‌کارانه: بدونِ فیلتر، لایه در
//      روندِ نزولیِ کلان هم `LONG` می‌دهد — دقیقاً موقعیتی که فیلتر برای
//      حذفش گذاشته شده بود.
//
// اصلاح: `close > EMA200` از خودِ `ctx.candles` محاسبه و پاس می‌شود.
// وفاداریِ عددی: `indicators.ema` با `alpha = 2/(period+1)` و بدونِ
// bias-correction پیاده شده ⇒ معادلِ `pandas.ewm(span=200, adjust=False)`
// که پایتون استفاده می‌کند ⇒ همان عدد، نه یک تقریبِ مشابه.
//
// ⚠️ اثرِ موردِ انتظار: تعدادِ سیگنال‌ها **کم** می‌شود. این «ضعیف‌ترشدن» نیست؛
//    بازگرداندنِ لایه به همان نسخه‌ای است که حکم را گرفته.
// ---------------------------------------------------------------------------
function s312Layer(slPip: number, tpPip: number, maxHold: number): LayerFn {
  return (ctx) => {
    const closes = ctx.candles.map(c => c.close)
    const e200 = ema(closes, 200)
    const iLast = closes.length - 1
    const eLast = iLast >= 0 ? e200[iLast] : NaN
    // اگر EMA هنوز گرم نشده (NaN) ⇒ فیلتر را **بسته** می‌گیریم، نه باز.
    // «نبودِ داده» هرگز نباید به «تأییدِ سیگنال» ترجمه شود.
    const aboveEma = Number.isFinite(eLast) && closes[iLast] > eLast
    const sig = computeMidMonth(ctx.times, ctx.utcHour, { aboveEma })
    const price = ctx.a.price
    const active = sig.state === 'ENTRY'
    const approaching = sig.state === 'APPROACHING'
    const raw: RawSignal = {
      active, approaching, direction: 'LONG',
      slDist: slPip * GOLD_PIP, tpDist: tpPip * GOLD_PIP, maxHoldBars: maxHold,
      reason: sig.reason,
      approachReason: approaching ? 'ورود به ساعاتِ معاملاتیِ روزِ میانِ‌ماه' : undefined,
      indicators: [
        { name: 'روزِ میانِ‌ماه (dom ∈ {۱۰,۱۳,۲۰})', value: sig.isMidWindow ? 'بله ✔' : 'خیر', status: sig.isMidWindow ? 'ok' : 'neutral' },
        { name: 'ساعتِ UTC', value: `${sig.utcHour}:00`, status: MID_ENTRY_HOURS.includes(sig.utcHour) ? 'ok' : 'neutral' },
      ],
      // 🕒 باگِ User Note #۳: دروازهٔ زمانی برای نوارِ شمارشِ معکوس زیرِ کارت.
      timeGate: {
        layerCode: 'S312', label: 'درایوِ میانهٔ ماه',
        entryHoursUtc: MID_ENTRY_HOURS,
        dayOfMonthNote: 'روزهای ۱۰، ۱۳ و ۲۰ هر ماه',
        activeDaysOfMonth: [10, 13, 20],
        windowOpen: sig.isMidWindow && MID_ENTRY_HOURS.includes(sig.utcHour),
        endHourUtc: Math.max(...MID_ENTRY_HOURS) + 1,
      },
    }
    const reg = lightRegime(0, true, 's312_mid')
    return rawToDecision(raw, {
      code: 'S312', name: 'Mid-Month Drift', kind: 'time' as any,
      manageStyle: 'fixed-tp-sl', manageNote: `هدف/حدِ متقارنِ ثابت (${tpPip}/${slPip} pip)؛ تا پایانِ پنجره یا برخورد نگه‌دار.`,
      filters: ['روزهای ۱۰/۱۳/۲۰ ماه', 'ساعاتِ معاملاتی', 'فیلترِ کیفیت (روندِ کلان)'],
    }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
  }
}

// ---------------------------------------------------------------------------
// آداپترهای نازک برای ماژول‌های دارای decide* (فقط cfg را می‌بندند)
// ---------------------------------------------------------------------------
//
// 🧩 **تصمیمِ معمارانهٔ S396 — آداپترها می‌مانند، حتی اگر هیچ کارتی صدایشان نزند.**
//
//    پس از پاک‌سازی، آداپترهای فعال در `CARD_LAYERS`:
//      `s333Layer`+`withLpsbGate` (M5) · `s344Layer` (M15) · `s312Layer` (M30)
//      `s354Layer` (H1) · `s382Layer` (H4) · `s950Layer` (H8 — افزودهٔ S950)
//    بقیه (`s313`, `s321`, `s322`, `s323`, `s324`, `s326`, `s327`, `s328`,
//    `s330`, `s332`, `s334`, `s335`, `s340`, `s345`, `s374`, `s310`) **بی‌مصرفِ
//    عمدی** هستند — «گرهِ خوابیده» به‌زبانِ ROS2.
//
//    چرا حذف نمی‌شوند (سه دلیلِ فنی، نه تنبلی):
//      ۱) **بازتولیدپذیریِ علمی:** هر آداپتر امضای دقیقِ فراخوانیِ لایه‌ای است که
//         روزی اندازه‌گیری شد. حذفش یعنی نتایجِ ثبت‌شده در `results/` دیگر از
//         خودِ کد قابلِ بازسازی نیستند.
//      ۲) **هزینهٔ احیا = یک خط:** طبق «قانونِ مرگِ ابدی»، لایهٔ رد‌شده مرده نیست؛
//         منتظرِ بهبود است. با نگه‌داشتنِ آداپتر، بازگرداندنش فقط افزودنِ یک
//         ورودی به `CARD_LAYERS` است — بدونِ لمسِ ماژول‌ها.
//      ۳) **ماژولاریتیِ ROS2:** در ROS2 گره‌ها از گراف مستقل‌اند. تغییرِ گراف
//         (کدام لایه به کدام کارت وصل است) نباید گره‌ها را نابود کند.
//
//    ⚠️ پس «وجودِ آداپتر» را با «فعال‌بودنِ لایه» اشتباه نگیرید. **تنها منبعِ
//       حقیقتِ فعال‌بودن، جدولِ `CARD_LAYERS` است.**
const s313Layer = (cfg: typeof S313_M30): LayerFn => (ctx) => {
  const o = ctx.candles.map(c => c.open), h = ctx.candles.map(c => c.high)
  const l = ctx.candles.map(c => c.low), c2 = ctx.candles.map(c => c.close)
  return decideS313(cfg, ctx.a, o, h, l, c2, ctx.capital, ctx.riskPct)
}
const s321Layer = (cfg: typeof S321_CFG[string]): LayerFn => (ctx) => decideS321(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s322Layer = (cfg: typeof S322_CFG[string]): LayerFn => (ctx) => decideS322(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s323Layer = (cfg: typeof S323_CFG[string]): LayerFn => (ctx) => decideS323(cfg, ctx.a, ctx.candles, ctx.utcHour, ctx.capital, ctx.riskPct)
const s324Layer = (cfg: typeof S324_CFG[string]): LayerFn => (ctx) => decideS324(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s328Layer = (cfg: typeof S328_CFG[string]): LayerFn => (ctx) => decideS328(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s330Layer = (cfg: typeof S330_CFG[string]): LayerFn => (ctx) => decideS330(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ نوِ این نشست: squeeze احیاشده (H4=ADX/DI · M15=r2+hurst)
const s332Layer = (cfg: typeof S332_CFG[string]): LayerFn => (ctx) => decideS332(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ نوِ این نشست: S333 Trend-Pullback (هندسهٔ منصفانه TP≥SL · WR واقعی)
const s333Layer = (cfg: typeof S333_CFG[string]): LayerFn => (ctx) => decideS333(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ نوِ این نشست: S334 Mean-Reversion Fade فروش (احیای s122 با گیتِ Hurst/Kurtosis)
const s334Layer = (cfg: typeof S334_CFG[string]): LayerFn => (ctx) => decideS334(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐ آداپترِ S374 «دروازهٔ شکستِ Kennedy» — لایهٔ پذیرفته‌شدهٔ H4 (طلا + یورو)
//   ماژول `decide*` ندارد (موتورِ خالص است) ⇒ آداپتر خودش RawSignal می‌سازد.
//   ⚠️ حالتِ APPROACHING اینجا **ذاتیِ قاعده** است، نه تزئین: وقتی close از خط عبور
//      کرده ولی کلِ دامنه نه، همان وضعیتی است که Kennedy آموزش می‌دهد ⇒ کارت صریحاً
//      می‌گوید منتظرِ چه تأییدی هستیم (کندلی که کلِ دامنه‌اش آن‌سویِ خط باشد).
const s374Layer = (cfg: typeof KENNEDY_CFG[string]): LayerFn => (ctx) => {
  const o = ctx.candles.map(c => c.open), h = ctx.candles.map(c => c.high)
  const l = ctx.candles.map(c => c.low), c2 = ctx.candles.map(c => c.close)
  const isEur = cfg.id.startsWith('EUR')
  const pip = isEur ? 0.0001 : GOLD_PIP
  const costPip = isEur ? 1.6 : 3.3            // اسپردِ حسابِ دمو (سندِ پروژه)
  const r = computeKennedy(o, h, l, c2, cfg, pip, costPip)
  if (!r.hasChannel) return null
  if (r.state === 'NEUTRAL' && !r.closeBreak) return null   // کارتِ خنثی را شلوغ نکن

  const price = ctx.a.price
  const dirFa = r.side === 'SHORT' ? 'نزولی' : 'صعودی'
  const raw: RawSignal = {
    active: r.state === 'ENTRY',
    approaching: r.state === 'APPROACHING',
    direction: (r.side ?? (r.isBear ? 'SHORT' : 'LONG')) as 'LONG' | 'SHORT',
    slDist: r.slDist, tpDist: r.tpDist, maxHoldBars: cfg.maxHoldBars,
    reason: r.reason,
    approachReason: r.state === 'APPROACHING'
      ? `قیمت با close از خطِ کانال عبور کرده ولی **کلِ دامنهٔ** کندل نه — طبقِ قاعدهٔ `
        + `Kennedy این شکستِ مشروع نیست. تأییدِ لازم: کندلی که تمامِ دامنه‌اش آن‌سویِ `
        + `خط بسته شود (فاصلهٔ باقی‌مانده: ${isFinite(r.distToKennedy) ? r.distToKennedy.toFixed(isEur ? 5 : 2) : '—'}).`
      : undefined,
    indicators: [
      {
        name: `کانالِ ${r.isBear ? 'نزولی' : 'صعودی'} (Stairs · k=${cfg.k})`,
        value: `${r.lowerLine.toFixed(isEur ? 5 : 2)} … ${r.upperLine.toFixed(isEur ? 5 : 2)}`,
        status: 'ok',
      },
      {
        name: 'شکستِ مشروع (کلِ دامنهٔ کندل آن‌سویِ خط)',
        value: r.kennedyBreak ? `بله ✔ (${dirFa})` : 'خیر',
        status: r.kennedyBreak ? 'ok' : 'neutral',
      },
      {
        name: 'شکستِ close (تعریفِ رایج — به‌تنهایی کافی نیست)',
        value: r.closeBreak ? 'بله' : 'خیر',
        status: r.closeBreak && !r.kennedyBreak ? 'warn' : 'neutral',
      },
      {
        name: `پلهٔ آخر کوچک‌شونده${cfg.gate ? '' : ' (روی این کارت بی‌اثر)'}`,
        value: r.shrink ? 'بله (برگشتی)' : 'خیر (هم‌جهت)',
        status: 'neutral',
      },
      {
        name: 'هدف در برابرِ هزینهٔ رفت‌وبرگشت',
        value: r.feasible ? `کافی ✔ (${(r.tpDist / pip).toFixed(1)} در برابرِ ${costPip} pip)` : 'ناکافی ✘',
        status: r.feasible ? 'ok' : 'bad',
      },
    ],
  }
  const reg = lightRegime(0, !r.isBear, 's374_kennedy')
  return rawToDecision(raw, {
    code: 'S374', name: 'دروازهٔ شکستِ Kennedy (خطِ کانال)', kind: 'breakout' as any,
    manageStyle: 'structural-trail',
    manageNote: `هدف = یک ارتفاعِ کانال (measured-move) و حدِ ضرر = نیمِ ارتفاع. `
      + `خطِ شکسته‌شده حالا نقشِ حمایت/مقاومت دارد ⇒ اگر کندلی با **کلِ دامنه‌اش** به `
      + `داخلِ کانال برگشت، شکست باطل شده و بهتر است معامله بسته شود. `
      + `⚠️ کم‌بسامد و رتبهٔ محافظه‌کارانه (طلا ~۴ رویداد در سال) ⇒ در حجم خویشتن‌دار باش.`,
    filters: [
      'شکست فقط با عبورِ کلِ دامنهٔ کندل (نه close)',
      'تنها نخستین شکستِ هر کانال',
      'هدفِ measured-move باید ≥ ۲× هزینهٔ رفت‌وبرگشت باشد',
      'فقط H4 (در M5..H1 اثر معکوس یا زیرِ هزینه است)',
    ],
  }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
}
// لایهٔ نوِ این نشست: S335 Reflex-TrendFlex Cycle-Turn (خریدِ کفِ چرخهٔ اِهلرز درونِ روند)
const s335Layer = (cfg: typeof S335_CFG[string]): LayerFn => (ctx) => decideS335(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s340Layer = (cfg: typeof S340_CFG[string]): LayerFn => (ctx) => decideS340(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐ S382 — مومنتومِ Williams %R (گذر به بالای −۱۳): تنها لایهٔ ۱۱/۱۱ دروازه با **صفر فیلتر**
const s382Layer = (cfg: typeof S382_CFG[string]): LayerFn => (ctx) => decideS382(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐ S950 — پس‌لرزهٔ جهشِ هم‌راستا با رانش (H8) — کندل‌های ورودیِ ctx باید H8 باشند
//    (index.tsx آن‌ها را با aggregateCandles(H1, 8) می‌سازد، عینِ الگوی H4).
const s950Layer = (cfg: typeof S950_CFG[string]): LayerFn => (ctx) => decideS950(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐ S965 — ماندگاریِ درون-کندلیِ شوکِ کایل (H8) — همان مسیرِ کندلِ H8 (H1×8).
const s965Layer = (cfg: typeof S965_CFG[string]): LayerFn => (ctx) => decideS965(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐ S966 — ماندگاریِ کایل × هم‌راستاییِ درفتِ ۱۸۰کندلی (H8) — همان مسیرِ کندلِ H8 (H1×8).
//    ⚠️ نیازِ دادهٔ این لایه از همهٔ هم‌کارتی‌هایش بیشتر است: دروازهٔ درفت به
//    close[t−1] و close[t−181] نگاه می‌کند ⇒ کفِ ۱۸۲ کندلِ H8. کفِ فعلیِ کارتِ H8
//    در index.tsx (۱۱۰ کندل) کمتر از این است، پس لایه در فیدِ کم‌عمق صادقانه
//    پیامِ «دادهٔ ناکافی» می‌دهد و هرگز سیگنالِ جعلی نمی‌سازد (خودِ ماژول گارد دارد).
const s966Layer = (cfg: typeof S966_CFG[string]): LayerFn => (ctx) => decideS966(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐⭐ S919 — شوکِ مطلعِ هم‌راستا با قرارداد (H6) — کندل‌های ورودیِ ctx باید H6 باشند
//    (index.tsx آن‌ها را با aggregateCandles(H1, 6) می‌سازد، عینِ الگوی H4/H8).
// ⚠️ کفِ داده: گیتِ قرارداد به close[t−1−240] با t = n−2 نگاه می‌کند ⇒ کفِ ۲۴۳
//    کندلِ H6. اگر فیدِ کم‌عمق باشد، خودِ ماژول صادقانه «دادهٔ ناکافی» می‌دهد و
//    هرگز سیگنالِ جعلی نمی‌سازد (گاردِ minBars در computeS919).
const s919Layer = (cfg: typeof S919_CFG[string]): LayerFn => (ctx) => decideS919(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐⭐ S800 — فشردگی → گشایش (D1 و H12) — کندل‌های ورودیِ ctx باید هم‌تایم‌فریمِ کارت باشند
//    (index.tsx آن‌ها را با aggregateCandles(H1, 24) و aggregateCandles(H1, 12)
//     می‌سازد، عینِ الگوی H4=×4 و H8=×8؛ چون Yahoo کندلِ روزانهٔ GC=F را در ساعتِ
//     ۰۴:۰۰ UTC باز می‌کند و با D1ِ نیمه‌شبِ بک‌تستِ MT5 هم‌تراز نیست).
const s800Layer = (cfg: typeof S800_CFG[string]): LayerFn => (ctx) => decideS800(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐⭐ S770 — انبساطِ دامنه نسبت به ADR با تداوم (D1 **و** H8) — استخرِ دوعضوی.
//    کندل‌های ورودیِ ctx باید هم‌تایم‌فریمِ کارت باشند (index.tsx با
//    aggregateCandles(H1, 24) برای D1 و ×8 برای H8 می‌سازد) — و این برای S770
//    **بحرانی‌تر** از بقیهٔ لایه‌هاست: متغیرِ حالتش روی openِ **روزِ تقویمیِ UTC**
//    لنگر دارد، پس مرزِ سطل‌ها باید t % 86400 == 0 باشد. تجمیعِ H1×24 عیناً همین
//    مرز را می‌سازد (کندلِ ۱-روزهٔ خودِ Yahoo در ۰۴:۰۰ UTC باز می‌شود ⇒ ناهم‌تراز
//    و برای این لایه **غلط** بود). برای H8 هم مرزهای 0/8/16 زیرمجموعهٔ مرزِ روزند.
const s770Layer = (cfg: typeof S770_CFG[string]): LayerFn => (ctx) => decideS770(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⭐ S560 — گپِ منفیِ بازگشایی (M5) — لایه به **زمانِ** کندل‌ها نیاز دارد (مرزِ روز)
//    که در Candle.time موجود است؛ ctx.candles همان closedBars(...) است ⇒ کندلِ
//    زندهٔ در حالِ شکل‌گیری (و کندلِ مصنوعیِ rebase با گپِ ذاتاً صفر) داخل نیست.
const s560Layer = (cfg: typeof S560_CFG[string]): LayerFn => (ctx) => decideS560(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ نوِ این نشست: S562 «گپِ منفی + فیلترِ نوسانِ علّی» — دو ACCEPT (M15 و H1)
const s562Layer = (cfg: typeof S562_CFG[string]): LayerFn => (ctx) => decideS562(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// ⚰️ s341Layer حذف شد — S341 زیرِ RQS2 v2.4 مرده است (بالا را ببینید).
// لایهٔ نوِ این نشست: S344 Brooks Trend-from-Open first-pullback continuation (فصلِ ۲۳) — نخستین SHORT روی XAUUSD-M15
const s344Layer = (cfg: typeof S344_CFG[string]): LayerFn => (ctx) => decideS344(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ نوِ این نشست: S345 Brooks Reversal Day — چرخشِ روندِ درون‌روزی (فصلِ ۲۴)
const s345Layer = (cfg: typeof S345_CFG[string]): LayerFn => (ctx) => decideS345(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ احیاشدهٔ این نشست: S356 = S354-causal، Brooks Trend Resumption Day (فصلِ ۲۵)
const s354Layer = (cfg: typeof S354_CFG[string]): LayerFn => (ctx) => decideS354(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)

// ---------------------------------------------------------------------------
// نگاشتِ کارت → لایه‌های فعال (به‌ترتیبِ اولویت).
//
// 🔴 **پاک‌سازیِ حاکمیتیِ S396** — این جدول از **۱۰ کارت / ۲۹ اتصال** به
//    **۵ کارت / ۵ اتصال** کوچک شد.
//
//    قاعدهٔ نگه‌داری (تنها قاعده): «اتصال می‌ماند اگر و فقط اگر **همان
//    (لایه × کارت)** در دفترِ رسمیِ ممیزی حکمِ `ACCEPT` گرفته باشد.»
//    منبعِ حقیقت: `results/_audit_rename/AUDIT_LEDGER.json` → `cards[]`
//    **نه** نامِ فایلِ نتیجه (که کارت‌های *آزموده‌شده* را فهرست می‌کند).
//
//    ⛔ هر ۲۴ اتصالِ حذف‌شده با معیارِ **بازنشستهٔ RQS+** مجوز گرفته بودند —
//       معیاری که رانشِ صعودیِ طلا را با مهارت اشتباه می‌گرفت. زیرِ RQS2 v2.4
//       هیچ‌کدام زنده نماند. نمرات در کامنتِ هر حذف ثبت شده تا احیای آینده
//       بداند از کجا شروع کند (قانونِ مرگِ ابدی: حذف ≠ ابطالِ ابدی).
//
//   ┌ کارت ────────┬ لایه ─┬ RQS2 ─┬ n ────┬ WR ─────┬ PF ────┬ maxDD ┐
//   │ XAUUSD-M5    │ S355  │ 83.9* │  47*  │ 72.34%* │ 3.951* │ 1.98%*│  ← *بدهیِ باز (بندِ ۳ سندِ S396)
//   │ XAUUSD-M15   │ S344  │ 89.0  │   92  │ 64.13%  │ 2.078  │ 3.10% │
//   │ XAUUSD-M30   │ S312  │ 87.7  │  289  │ 61.25%  │ 1.680  │ 2.55% │
//   │ XAUUSD-H1    │ S356  │ 79.6  │  117  │ 51.28%  │ 1.636  │ 4.05% │
//   │ XAUUSD-H4    │ S382  │ 79.2  │  869  │ 48.22%  │ 1.349  │ 6.60% │
//   └──────────────┴───────┴───────┴───────┴─────────┴────────┴───────┘
//
//   ✅ تطبیقِ هندسه تأیید شد (ضدِ اشتباهِ رایجِ ۶ «TP/SL یکسان برای همه TF»):
//      M15 → 220/340/32 · M30 → 295/295/36 · H1 → 50.6/101.2/20 · H4 → 122.854/184.281
//      هر چهار عدد **عیناً** همان است که ممیزی ACCEPT داد؛ هیچ کارتی هندسهٔ
//      کارتِ دیگر را قرض نگرفته، و هیچ‌کدام TP<SL ندارد (ضدِ اشتباهِ ۸).
//
//   ⚠️ **هیچ کارتِ EURUSD نمی‌ماند** — نتیجهٔ اندازه‌گیری است، نه سلیقه:
//      EURUSD-M5 (S334) · EURUSD-M15 (S326) · EURUSD-M30 (S345) · EURUSD-H4 (S374)
//      هیچ‌یک زیرِ RQS2 حکمِ ACCEPT نگرفتند (S374/EURUSD-H4 = REJECT/15.7).
//      این کارت‌ها از سایت برداشته می‌شوند، ولی ماژول‌هایشان در مخزن می‌مانند.
// ---------------------------------------------------------------------------
export const CARD_LAYERS: Record<string, LayerFn[]> = {
  'XAUUSD-M5': [
    // ⭐ S355 = مولدِ S333/M5 **با دروازهٔ حالتِ ساختارِ LPSB**.
    //    پایهٔ بدونِ دروازه: WR 65.6% · PF 2.85 · RQS2=27.5 (POWER-LIMITED)
    //    با دروازه:          WR 72.3% · PF 3.95 · RQS2=83.9 (ACCEPT ✓)
    //
    //    ⚠️ **بدهیِ بازِ ثبت‌شده** (بندِ ۳ سندِ
    //       `results/S396_SiteLayerPurgeAudit_…_AUDIT.md`): کارتِ ACCEPTِ ثبت‌شده در
    //       دفترِ ممیزی برچسبِ `XAUUSD-H1` با `n=1298 · SL=450 · RR=1.618 · hold=12`
    //       خورده، درحالی‌که سندِ خودِ لایه `XAUUSD-M5 · n=47 · SL=TP=120 · hold=96`
    //       است. علت: `identify_card()` کارت را از اثرِ انگشتِ داده حدس می‌زند و
    //       جاروبِ S355 چندکارتی بود ⇒ برچسب‌گذاری مشکوک است.
    //       این اتصال طبقِ فهرستِ صریحِ User Note نگه داشته می‌شود، ولی تا
    //       بازآزمونِ اختصاصیِ M5 **مشکوک** علامت خورده است.
    // ⚰️ S355 — **حذف‌شده به دستورِ صریحِ کاربر (۲۰۲۶-۰۸)** پس از داوریِ
    //    تأییدیِ تمام‌تاریخیِ S530 (سند:
    //    `results/S530_S355FullHistoryAdjudication_Xauusd_M5_rqs2_18_REJECT.md`):
    //    روی ۱۵.۶ سالِ کامل RQS2=18.1 (H3✗ H6✗ H8✗) · حکمِ سه‌گانه = REGIME-ONLY.
    //    دو چهره: WR اخیر (۲.۸y) = 72.34٪ ولی کلِ تاریخ = 56.88٪ و ۱۲.۵ سالِ
    //    اول **ضررده** (n=113 · WR=50.44٪ · −320pip زیرِ سربه‌سرِ هزینه‌دار).
    //    لبه مختصِ رژیمِ روندیِ ۲۰۲۳-۲۰۲۶ است ⇒ برای کاربرِ زنده قابلِ‌اتکا نیست.
    //    ماژول (`lpsb_state_s355.ts`) در مخزن می‌ماند؛ فقط اتصال قطع شد.
    //    اتصالِ سابق (برای بازگردانیِ احتمالی پس از بازآزمون):
    //      withLpsbGate(s333Layer(S333_CFG['XAUUSD-M5']), S355_CFG['XAUUSD-M5']),
    // ⚰️ حذف‌شده در S396 (همه با RQS+ بازنشسته مجوز گرفته بودند، هیچ ACCEPTِ RQS2):
    //    S330(FADE) · S328(SHORT) · S334(SHORT·RQS+81.6) · S335(LONG·RQS+92.2) · S326(LONG)
    //    و S327 که پیش‌تر با RQS2=21.5 حذف شده بود.
    //
    // ⭐⭐ S560 — «گپِ منفیِ بازگشایی» · **احیایِ این کارت** (پس از حذفِ S355 خالی بود)
    //    RQS2 = **96.0** ⇒ بالاترین نمرهٔ کلِ لایه‌های وصل‌شدهٔ سایت.
    //    n=407 · WR=71.5٪ · PF=2.514 · maxDD=2.43٪ · MCL=5 (مجاز ۸) · RF=20.05
    //    lift=+43.98pp روی نالِ بازو-محورِ 27.51٪ · z=19.87 · z_luck_bound=2.985
    //    ⇒ z_margin=16.885 · p_perm=0.0 (K=500) · n_trials=400 کسرشده (Path C).
    //    هر ۱۱ دروازهٔ H0..H10 پاس، **صفر** دروازهٔ ناموفق.
    //
    //    چرا این لایه با بقیهٔ سایت هم‌پوشانی ندارد: تنها لایهٔ **رویدادِ
    //    بازگشاییِ روز** است (روزی یک ارزیابی) و LONG-only روی گپِ منفی.
    //
    //    ⏱️ **هشدارِ صداقتِ پنجره:** هندسهٔ قفل‌شده maxHold=۱ کندلِ M5 ⇒ کلِ
    //    پنجرهٔ معامله ۵ دقیقه است. سایت (درست) سیگنال را روی کندلِ **بسته**
    //    می‌سنجد، پس ENTRY فقط در همان یک چرخه‌ای نمایش داده می‌شود که کندلِ
    //    اولِ روزِ نو تازه بسته شده؛ بعد از آن لایه صادقانه به NEUTRAL می‌رود و
    //    می‌گوید فرصت گذشته است (هیچ ورودِ تأخیریِ دروغین ساخته نمی‌شود).
    //
    //    آستانه‌ها از ۱۵.۶ سال داده **منجمد** شده‌اند (چون سایت فقط ۵ روز کندلِ
    //    M5 دارد و چندکِ انبساطی در مرورگر بازتولیدپذیر نیست):
    //      results/_s560_arms/frozen_thresholds_M5.json
    //    اثباتِ پورت: صفر اختلاف روی **۴۰۶۹ مرزِ روز** / ۱.۰۹M کندل ⇒
    //      results/_s560_arms/parity_ts_M5.json
    //    سند: results/S560_GapOpenNegGap_Xauusd_M1M5M15M30H1_rqs2_96_ACCEPT.md
    //
    //    ⚠️ تعمیم ممنوع (قانونِ Multi-TF): M1 هم ACCEPT بود (95.6) ولی کارتِ M1
    //    در سایت وجود ندارد؛ M15/M30/H1 حکمِ **REJECT** گرفتند (شکستِ H8 = DD/wall-time)
    //    ⇒ فقط همین کارت وصل می‌شود.
    s560Layer(S560_CFG['XAUUSD-M5']),
  ],
  'XAUUSD-M15': [
    // ⭐⭐ S562 ⭐نو — «گپِ منفیِ بازگشایی + فیلترِ نوسانِ علّی» · LONG
    //    RQS2 = **95.3** (بالاترین نمرهٔ این کارت) · n=438 · WR 70.78% · maxDD 3.71%
    //    هر ۱۱ دروازهٔ RQS2 v2.6 سبز · SL=TP=50.9 pip (RR 1.0) · maxHold=1
    //    ⚠️ هندسه و آستانهٔ گپ **ارثی** از S560 است (صفر پارامترِ نوِ جست‌وجو‌شده)؛
    //       تنها افزودهٔ S562 یک عددِ انتخابِ معامله است: qv=85.
    //    ⚠️ **هم‌خانواده با S560-M5 (jaccard ≈۰.۵۱–۰.۵۴) و با S562-H1 (۰.۵۶).**
    //       اگر هر سه کارت هم‌زمان سیگنال دادند، **یک رویدادِ گپ** است نه سه لبهٔ
    //       مستقل ⇒ سایزِ مشترک بگیرید (سند §۵).
    //    اولویتِ صدرِ فهرست: نمرهٔ این لایه از S344 (۸۹.۰) و S431 (۹۳.۹) بالاتر است.
    s562Layer(S562_CFG['XAUUSD-M15']),
    // ⭐ S344 — Brooks فصلِ ۲۳ «trend-from-open first-pullback» · SHORT
    //    RQS2 = **89.0** · n=92 · WR 64.13% · PF 2.078 · maxDD 3.10%
    //    SL=220 / TP=340 pip (RR 1.55 ⇒ TP>SL) · maxHold=32
    //    نکته: کارتِ H1 همین لایه REJECT/29.2 گرفت ⇒ فقط M15 وصل می‌شود
    //    (قانونِ MTF در جهتِ عکسش: تعمیم بدونِ شاهد ممنوع).
    s344Layer(S344_CFG['XAUUSD-M15']),
    // ⭐ S431 — «S333 + دروازهٔ ساختارِ LPSB» · عضوِ استخرِ چند-کارتی · LONG
    //    RQS2 = **93.9** (بالاترین نمرهٔ کلِ سایت) · هر ۱۱ دروازه پاس
    //    ⚠️ حکم روی **جمعیتِ تجمیعیِ چهار کارت** است (n=۱۶۸)، نه این کارت به‌تنهایی.
    //       سهمِ این کارت: n=۳۸ · WR ۶۵.۷۹٪ · lift +۱۷.۴۱pp · امید +۶۴.۲۹ pip
    //    هندسه: SL=200 / TP=240 pip (RR 1.2 ⇒ TP>SL) · maxHold=96 — **ارثی** از
    //    S333_CFG، صفر پارامترِ جست‌وجو‌شده ⇒ هیچ چندگانگیِ نو (ضدِ اشتباهِ ۸).
    //    مکمل بودن با S344: آن SHORT است و این LONG ⇒ دو سوی بازار پوشش می‌یابد.
    //    سند: results/S431_LpsbMulticardPool_Xauusd_M5M15M30H1_rqs2_93_ACCEPT.md
    withLpsbGate(s333Layer(S333_CFG['XAUUSD-M15']), S431_CFG['XAUUSD-M15']),
    // ⭐ S432 — «رانشِ میانِ ماه» (زمان-محورِ خالص) · عضوِ استخرِ تقویمی · LONG
    //    ♻️ **این همان `S312(M15)`ِ حذف‌شده در S396 است که در S432 احیا شد.**
    //    RQS2 = **84.7** · هر ۱۱ دروازه پاس (روی جمعیتِ تجمیعیِ H1+M15، n=۲۹۸)
    //    سهمِ این کارت: n=۱۳۸ · lift +۱۲.۱۸pp · سهمِ ۴۳٪ از استخر
    //    ⚠️ **افشای صریح — این عضو ضعیف‌ترِ استخر است.** به‌تنهایی حکمِ
    //       `REJECT` (RQS2=27.3) داشت با `z=1.71` و **دو** دروازهٔ افتاده
    //       (`H3`+`H5`)، نه یکی. پس ورودش به سایت **تنها** به‌اعتبارِ عضویت
    //       در استخری است که با `H1` هر ۱۱ دروازه را پاس کرد. کسی نباید این
    //       کارت را «مستقلاً اثبات‌شده» بخواند.
    //    چرا با این حال ارزشِ اتصال دارد: `lift` این کارت (+۱۲.۱۸pp) از
    //       `H1` (+۱۱.۶۳pp) **بیشتر** است — یعنی لبه‌اش واقعی و حتی قوی‌تر
    //       است؛ فقط نمونه‌اش (n=۱۳۸) برای اثباتِ تک‌نفره کافی نبود. حذفش
    //       استخر را به زیرِ سقفِ `H3` برمی‌گرداند و حکم را نابود می‌کند.
    //    هندسه: SL=TP=**295** pip (RR 1.0 متقارن) · maxHold=48 — ارثیِ
    //    `s312_oos_check.py`، صفر پارامترِ جست‌وجو‌شده ⇒ هیچ چندگانگیِ نو.
    //    مکمل بودن: `S344` (SHORT، ساختاری) و `S431` (LONG، ساختاری) هر دو
    //    قیمت-محورند؛ این لایه زمان-محورِ خالص است ⇒ سه منبعِ مستقل روی یک کارت.
    //    سند: results/S432_MidMonthDriftCalendarPool_Xauusd_H1M15_rqs2_84_ACCEPT.md
    s312Layer(295, 295, 48),
    // ⚰️ حذف‌شده در S396: S345(RQS+90.7) · S333(RQS+91.7) · S332(RQS+91.2) ·
    //    S324 · S322 · S335(RQS+89.7) · S310 — هیچ‌کدام ACCEPTِ RQS2 ندارند.
    //    (S312(M15) دیگر در این فهرست نیست — در S432 احیا و بالاتر وصل شد.)
    //    S312 روی **M30** ACCEPT گرفت نه M15 ⇒ اتصالِ M15 آن برداشته شد.
  ],
  'XAUUSD-M30': [
    // ⭐ S312 — «رانشِ میانِ ماه» (زمان-محورِ خالص)
    //    RQS2 = **87.7** · n=289 · WR 61.25% · PF 1.680 · maxDD 2.55%
    //    SL=TP=295 pip (RR 1.0) · maxHold=36 — هندسهٔ متقارن، هیچ تورشِ WR-سازی.
    //    بالاترین توانِ آماریِ میانِ سه لایهٔ زمان‌محورِ پروژه (n=289).
    s312Layer(295, 295, 36),
    // ⭐ S431 — «S333 + دروازهٔ ساختارِ LPSB» · عضوِ استخرِ چند-کارتی · LONG
    //    RQS2 = **93.9** · هر ۱۱ دروازه پاس (روی جمعیتِ تجمیعی، نه این کارت تنها)
    //    سهمِ این کارت: n=۲۸ · WR ۶۷.۸۶٪ · lift +۱۹.۵۵pp · امید **+۸۰.۱۸ pip**
    //    ⇒ **بالاترین امیدِ ریاضیِ هر چهار عضو**، ولی کوچک‌ترین نمونه (۱۴.۹٪ استخر).
    //       همین جفتِ «لبهٔ بزرگ + نمونهٔ کم» دقیقاً همان الگویی است که در
    //       ورودیِ E-04 دفترچه به‌عنوان نامزدِ ایدئالِ تجمیع شناسایی شد.
    //    هندسه: SL=380 / TP=420 pip (RR 1.105 ⇒ TP>SL) · maxHold=80 — ارثی از S333.
    //    مکمل بودن با S312: آن زمان-محورِ خالص است (رانشِ میانِ ماه) و این
    //    ساختار-محور ⇒ دو منبعِ اطلاعاتیِ **مستقل**، نه دو نسخه از یک ایده.
    //    سند: results/S431_LpsbMulticardPool_Xauusd_M5M15M30H1_rqs2_93_ACCEPT.md
    withLpsbGate(s333Layer(S333_CFG['XAUUSD-M30']), S431_CFG['XAUUSD-M30']),
    // ⚰️ حذف‌شده در S396: S333(RQS+91.1) · S313 · S324 · S321 · S326
    //    و S327/S323 که پیش‌تر با RQS2 حذف شده بودند.
  ],
  'XAUUSD-H1': [
    // ⭐⭐ S562 ⭐نو — «گپِ منفیِ بازگشایی + فیلترِ نوسانِ علّی» · LONG
    //    RQS2 = **96.0** (بالاترین نمرهٔ کلِ سایت) · n=254 · WR 68.90% · maxDD 2.07%
    //    هر ۱۱ دروازهٔ RQS2 v2.6 سبز · SL=TP=101.4 pip (RR 1.0) · maxHold=2
    //    ⚠️ این **همان لایهٔ کارتِ M15** است با qv=78 به‌جای ۸۵ — دو ACCEPTِ
    //       مستقل روی دو تایم‌فریم، پس طبق قانونِ MTF **هر دو** وصل می‌شوند؛
    //       ولی هم‌پوشانیِ روزانه‌شان jaccard=۰.۵۶ است ⇒ **هم‌خانواده**، سایزِ
    //       مشترک (سند §۵). همچنین ≈۰.۵۱–۰.۵۴ با S560-M5 زنده.
    //    مزیتِ H1 بر M15 در انجماد: در پنجرهٔ ۶۵روزهٔ این کارت آستانهٔ منجمد
    //       ۱۰۰٪ با چندکِ رولینگ می‌خواند و تا ۱۲۵ روز هم ۱۰۰٪ می‌مانَد
    //       (M15 در ۱۲۵ روز به ۸۹.۳٪ می‌افتد) ⇒ انجمادِ H1 ایمن‌ترِ دو تاست.
    //    اولویتِ صدرِ فهرست: ۹۶.۰ از S431 (۹۳.۹) و S356 (۷۹.۶) بالاتر است.
    s562Layer(S562_CFG['XAUUSD-H1']),
    // ⭐ S356 — احیای S354، Brooks فصلِ ۲۵ «trend-resumption day» · نسخهٔ **علّی**
    //    RQS2 = **79.6** · n=117 · WR 51.28% · PF 1.636 · maxDD 4.05%
    //    SL=50.6 / TP=101.2 pip (RR 2.0 ⇒ TP دوبرابرِ SL) · maxHold=20
    //    فیلترِ ساعت ≥۱۶ UTC (سشنِ نیویورک) — نه عددِ رند، از جاروبِ ساعتی آمده.
    s354Layer(S354_CFG['XAUUSD-H1']),
    // ⭐ S431 — «S333 + دروازهٔ ساختارِ LPSB» · عضوِ استخرِ چند-کارتی · LONG
    //    RQS2 = **93.9** · هر ۱۱ دروازه پاس (روی جمعیتِ تجمیعی، نه این کارت تنها)
    //    سهمِ این کارت: n=۶۶ · WR ۶۵.۱۵٪ · lift +۱۶.۱۷pp · امید +۶۷.۳۰ pip
    //    ⇒ **بزرگ‌ترین عضوِ استخر (۳۶.۹٪)** — و همان کارتی که انتخابگرِ خودکار
    //       «رقیق‌کننده» تشخیص داد و حذف کرد. آن حذف پس‌از‌دیدنِ نتیجه بود
    //       (نقضِ قیدِ پیش‌ثبتِ C2) ⇒ اصلاح شد و با ورودِ همین کارت نتیجه
    //       **بهتر** شد: n از ۱۰۹→۱۶۸، z از ۴.۴۲→۴.۷۰۶، RQS2 از ۹۳.۳→۹۳.۹.
    //       (شرحِ کامل: ورودیِ E-06 دفترچه، ISSUE-C2 و BUG-DEFAULTARG)
    //    هندسه: SL=450 / TP=520 pip (RR 1.156 ⇒ TP>SL) · maxHold=64 — ارثی از S333.
    //    مکمل بودن با S356: آن WR=51.28٪ دارد و لبه‌اش از هندسه (RR=2) می‌آید؛
    //    این WR=65.15٪ دارد و لبه‌اش از دقتِ ورود ⇒ دو مکانیزمِ سودآوریِ متفاوت.
    //    سند: results/S431_LpsbMulticardPool_Xauusd_M5M15M30H1_rqs2_93_ACCEPT.md
    withLpsbGate(s333Layer(S333_CFG['XAUUSD-H1']), S431_CFG['XAUUSD-H1']),
    // ⭐ S432 — «رانشِ میانِ ماه» (زمان-محورِ خالص) · عضوِ استخرِ تقویمی · LONG
    //    ♻️ **این همان `S312(H1)`ِ حذف‌شده در S396 است که در S432 احیا شد.**
    //    RQS2 = **84.7** · هر ۱۱ دروازه پاس (روی جمعیتِ تجمیعیِ H1+M15، n=۲۹۸)
    //    سهمِ این کارت: n=۲۶۶ · WR ۵۹.۴۰٪ · lift +۱۱.۶۳pp · z تنهایی ۲.۷۲
    //    چرا قبلاً افتاد و الان مجاز است: تنها دروازهٔ افتاده `H3` (**توان**) بود؛
    //    با `n=۲۶۰` در برابرِ سقفِ `n_required_h3 = ۳۳۶.۵` ⇒ شکستش **حسابی**
    //    از کمبودِ نمونه بود، نه نبودِ لبه. تجمیعِ تقویمی با `M15` آن را به
    //    `n=۲۹۸` و `z=۳.۱۸` (سد ۳.۰۹) رساند.
    //    هندسه: SL=TP=**395** pip (RR 1.0 متقارن) · maxHold=24 — ارثیِ
    //    `s312_oos_check.py`، صفر پارامترِ جست‌وجو‌شده ⇒ هیچ چندگانگیِ نو.
    //    ⚠️ `RR=1.0` عمداً متقارن است: هیچ تورشِ «TP کوچک‌تر برای WR-سازی»
    //       وجود ندارد (ضدِ اشتباهِ رایجِ ۸). سربه‌سرِ هزینه‌دار ۵۰.۴۷٪ و
    //       WR واقعی ۵۸.۳۹٪ ⇒ لبه از **دقت** می‌آید نه از هندسه.
    //    ⚠️ حکم روی جمعیتِ تجمیعی است، نه این کارت به‌تنهایی.
    //    مکمل بودن: `S356` و `S431` هر دو **قیمت/ساختار**-محورند؛ این لایه
    //    زمان-محورِ خالص است (تقویم × ساعت) ⇒ منبعِ اطلاعاتیِ **مستقل**.
    //    سند: results/S432_MidMonthDriftCalendarPool_Xauusd_H1M15_rqs2_84_ACCEPT.md
    s312Layer(395, 395, 24),
    // ⚰️ حذف‌شده در S396: S333(RQS+89.8) · S313 · S328 · S335(RQS+89.7)
    //    و S327/S323/S341 که پیش‌تر حذف شده بودند.
    //    (S312(H1) دیگر در این فهرست نیست — در S432 احیا و بالاتر وصل شد.)
  ],
  'XAUUSD-H4': [
    // ⭐⭐ S382 — «مومنتومِ Williams %R» · **صفر فیلتر**
    //    RQS2 = **79.2** · n=869 · WR 48.22% · PF 1.349 · maxDD 6.60%
    //    SL = 1.5×ATR(100) = 122.854 pip · TP = 1.5×SL = 184.281 pip
    //    ⓵ بالاترین توانِ آماریِ کلِ پروژه: n=869 و ~۵۵.۹ معاملهٔ **مستقل** در سال.
    //    ⓶ WR=48.22٪ **زیرِ ۵۰٪** و همچنان سودده ⇒ مدرکِ مستقیم که لبه از
    //       هندسه (TP>SL) می‌آید نه از WR-سازی (ضدِ اشتباهِ رایجِ ۸).
    //    ⓷ willrThr = **-13.0** (نه -20 رند) و atrP=100 ⇒ ضدِ اشتباهِ رایجِ ۷.
    //    ⓸ صفر فیلتر ⇒ بودجهٔ معامله دست‌نخورده (قانونِ هزینهٔ فیلترِ S379).
    s382Layer(S382_CFG['XAUUSD-H4']),
    // ⚰️ حذف‌شده در S396: S374(Kennedy) · S340(RQS+92.6) · S332(RQS+92.1)
    //    و S327 که پیش‌تر با RQS2=18.8 حذف شده بود.
    //    S374 مهم‌ترین حذف است: با RQS+ «ACCEPTED» اعلام شده بود، ولی زیرِ RQS2
    //    هر دو کارتش افتاد (XAUUSD-H4 و EURUSD-H4=15.7) ⇒ کارتِ EURUSD-H4 که
    //    فقط برای آن متولد شده بود، با حذفش از سایت برداشته می‌شود.
  ],
  // ═══════════════════════════════════════════════════════════════════════
  // 🆕 کارتِ H6 — **نو در این استقرار** (پیش از S919 هیچ لایه‌ای روی H6 نبود)
  // ═══════════════════════════════════════════════════════════════════════
  'XAUUSD-H6': [
    // ⭐⭐ S919 — «شوکِ مطلعِ هم‌راستا با قراردادِ بازار» (Convention-Aligned
    //    Informed Shock) · دانشمند: جان مینارد کینز · بلوکِ S910–S919
    //    RQS2 = **88.9** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی · n_trials=2
    //    n=106 · WR=55.66٪ · null_ref=40.04٪ · BE_cost=39.29٪ · lift=+15.62pp
    //    z_obs=3.282 · z_margin=2.762 · p_perm=8.42e−04 · PF=1.85 · maxDD=2.89٪
    //    (SL_med=115.8 pip · TP_med=187.3 pip · RR=1.618)
    //
    //    قاعده (صفر پارامترِ آزاد — همه به ارث):
    //      · شوک:      high−low ≥ 2.618 × ATR21[t−1]        ← پایهٔ منجمدِ S965
    //      · ماندگاری: ρ = |close−open| ÷ (high−low) ≥ 0.618 ← پایهٔ منجمدِ S965
    //      · جهت:      follow (بدنهٔ صعودی→LONG، نزولی→SHORT) ← S965
    //      · گیتِ قرارداد: drift = close[t−1] − close[t−241]؛ LONG فقط drift>0،
    //        SHORT فقط drift<0 (۶۰ روزِ تقویمی = ۲۴۰ کندلِ H6) ← قاعدهٔ S604
    //      · براکتِ شناور: SL=1.272×ATR21، TP=2.058×ATR21 (TP>SL ✓) ← S965
    //      · max_hold=16 کندلِ H6 (≈۴ روز) · allow_overlap=false · هزینه ۳.۳ pip
    //
    //    ⓵ **اولین لایهٔ کارتِ H6 در کلِ پروژه.** خوشهٔ شوک تا امروز همه H8 بود
    //       (S602/S770/S950/S526/S965/S966) و S604 استخرِ {D1، H6-درفت} داشت؛
    //       S919 خودِ کارتِ H6 را باز کرد ⇒ افزودنِ پوششِ نو، نه فشرده‌سازیِ H8.
    //    ⓶ ابطال‌گرِ P1 (ضدِ توان‌سوزی): بازوی بی‌گیت روی H6 = بازتولیدِ مستقلِ
    //       S965 ⇒ n=239 / WR=48.1٪ (S965 خودش n=240 گزارش کرده بود — تطابقِ n
    //       اثباتِ درستیِ پیاده‌سازی است). گیت همان پایهٔ REJECT را به ACCEPT برد.
    //    ⓷ ابطال‌گرِ P3 (روایتِ کینزی): بازوی **خلافِ** قرارداد WR=42.1٪ (n=133)
    //       ⇒ بازار شوکِ خلافِ قرارداد را «اختلالِ موقت» می‌خواند و جذب می‌کند.
    //    ⓸ **قلمرو قفل‌شده: فقط H6.** کارتِ H3 با RQS2=16.0 رد شد (n=317 ·
    //       WR=44.79٪ · z=1.87) ⇒ تعمیم ممنوع. H8 عامدانه از پیش‌ثبت حذف شده بود
    //       (S965/S966 آن‌جا ACCEPT دارند و دوباره‌آزمونی چندگانگیِ نو می‌ساخت).
    //    ⓹ هم‌پوشانی: رویدادها با کارتِ H8 ذاتاً هم‌پوشان‌اند (یک شوکِ ۸ساعته
    //       اغلب شوکِ ۶ساعته هم هست) ولی **کارت‌ها متفاوت‌اند** ⇒ لایه حذف
    //       نمی‌شود؛ صفِ FIFO/سایزِ محتاط روی حسابِ واقعی در manageNote ثبت شد.
    //
    //    🔴 **دامِ زمان‌بندی (مهم‌ترین نکتهٔ این استقرار):** ماسکِ بک‌تستِ
    //       داوری‌شده از پیش شیفت‌شده است (`lm[1:] = up[:-1]`) و سپس موتور ورود
    //       را در openِ کندلِ بعدِ ماسک می‌گذارد ⇒ **ورودِ واقعی = رویداد + ۲**.
    //       اندازه‌گیری روی همان داده و همان هندسه:
    //         · رویداد+۲ (کدِ داوری‌شده): n=106 · WR=55.66٪ · e=+51.93 pip ✓
    //         · رویداد+۱ (پورتِ ساده‌لوح): n=106 · WR=48.11٪ · e=+24.56 pip ✗
    //       ⇒ پورتِ ساده‌لوحانه لبه را زیرِ سربه‌سر می‌برد. پس computeS919 رویداد
    //       را روی کندلِ **i−1** می‌سنجد و سیگنال را روی کندلِ بستهٔ i می‌دهد.
    //    پریتی: web_tool/parity_s919_signal.mjs — ۷ آزمون، هر ۷ PASS، صفر اختلاف
    //       (شاملِ آزمونِ زمان‌بندیِ ورود=رویداد+۲ و آزمونِ «زود-شلیک نکردن»).
    //    سند: results/S919_ConventionAlignedInformedShock_Xauusd_H6_rqs2_88.9_ACCEPT.md
    s919Layer(S919_CFG['XAUUSD-H6']),
  ],
  'XAUUSD-H8': [
    // ⭐ S950 — «پس‌لرزهٔ جهش، هم‌راستا با رانش» (Jump-Aftermath Drift-Aligned)
    //    RQS2 = **80** · هر ۱۱ دروازه پاس · **پایدار روی ۴ seed** (79.9/80.0/80.1/80.0)
    //    n=224 · WR 61.6% (LONG 63.6% / SHORT 58.3%) · PF 1.56 · maxDD 4.92%
    //    lift=+11.15pp · z=3.34–3.37 · p_perm≈0.0004 · n_trials=33 صادقانه
    //    (سرریزِ چندگانگی تا n_trials=200 هم پاس می‌ماند — حاشیهٔ امن سنجیده شد.)
    //    قانون: جهشِ H8 (|r| > 2.6·σ_BV(89) با σ_BV واریانسِ Bipower علّی) که با
    //    رانشِ ۸۹-کندلیِ رژیم هم‌جهت باشد ⇒ ادامه. SL=TP=2.058×ATR(89) برداری
    //    (میانه ≈۲۴۲ pip) · maxHold=34 کندلِ H8 · تک‌معامله.
    //    ⓵ ساختارِ MTF یکنواخت: lift از −11pp (M4) تا +11pp (D1) ⇒ پدیدهٔ
    //       فیزیکیِ مقیاس-وابسته، نه گلچینِ تایم‌فریم. D1 خودش POWER-LIMITED
    //       (نه ACCEPT) ⇒ فقط H8 وصل می‌شود.
    //    ⓶ آزمونِ کنترل: فیلترِ مکمل (جهشِ خلافِ رانش) z=1.66 REJECT ⇒ فیلترِ
    //       رانش اطلاعاتِ واقعی دارد، انتخابِ پس‌ازدیدن نیست.
    //    ⓷ همپوشانی با هر ۵ لایهٔ سایت اندازه‌گیری شد: جاکاردِ روزانه ≤4.8٪ و
    //       overlap-as-filter بی‌اطلاع (WR 60.9 در برابرِ 61.5) ⇒ لبهٔ مستقل.
    //    ⓸ RR=1.0 متقارن ⇒ صفر تورشِ WR-سازی (ضدِ اشتباهِ رایجِ ۸)؛
    //       k=2.6 و 2.058=1.272×φ نارُند (ضدِ اشتباهِ ۷).
    //    ⚠️ کندل‌های این کارت از تجمیعِ H1×8 ساخته می‌شوند (Yahoo H8 ندارد) —
    //       عینِ H1×4ِ کارتِ H4؛ مرزهای UTC 0/8/16 با بک‌تست هم‌ترازند.
    //    سند: results/S950_JumpAftermathDriftAligned_Xauusd_H8_rqs2_80_ACCEPT.md
    s950Layer(S950_CFG['XAUUSD-H8']),
    // ⭐ S965 ⭐نو — «ماندگاریِ درون-کندلیِ اثرِ قیمتیِ کایل» (Kyle 1985) · دوسویه
    //    RQS2 = **82.2** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی
    //    n=146 · WR 54.79٪ · BE_rob 40.4٪ · lift=+12.84pp · z=3.14 · p_perm=8.33e−04
    //    PF=1.81 · net=+$7,113 · نول: K=500 جایگشت · draw=146 · uncond_n=11,711
    //    قانون: کندلِ شوک (high−low ≥ 2.618×ATR21[i−1]، ATR علّی) **که** ماندگاریِ
    //      درون-کندلی ρ=|close−open|÷(high−low) ≥ 0.618 داشته باشد ⇒ ادامه هم‌جهتِ بدنه.
    //      SL=1.272×ATR21[i−1] / TP=2.058×ATR21[i−1] (میانه ≈۱۳۸/۲۲۳ pip، TP>SL) · hold=16.
    //    ⓵ **آزمونِ تفکیک‌گرِ P1 پاس شد** (درسِ S603/S964): پایهٔ θ-only بدونِ شرطِ ρ
    //       lift=+11.81pp داشت؛ با شرطِ ρ به **+18.16pp** رسید ⇒ فیلترِ **اطلاعات‌افزا**،
    //       نه توان‌سوز. این دقیقاً وارونهٔ مرگِ S964 است.
    //    ⓶ قانونِ MTF رعایت شد: هر ۱۹ TF داوری و منتشر شد — H8 تنها ACCEPT؛ D1 با
    //       z=−3.40 و H12 با z=−2.13 لیفتِ **منفی** دارند (REJECT صریح)، H6/H3/H2/H1
    //       REJECT، و ۱۲ کارت NO-SURVIVOR ⇒ **صفر تعمیم**، فقط همین یک کارت وصل شد.
    //    ⓷ پنجمین لبهٔ مستقلِ «رویدادِ لحظه‌ای × TF درشت» روی H8، کنارِ
    //       S602/S770/S950/S526 — و نخستین ACCEPTِ بلوکِ کایل پس از ۵ REJECT (S960–S964).
    //    ⓸ مکمل بودن با S950 روی همین کارت: S950 ماشه‌اش **بازدهِ لگاریتمی** در برابرِ
    //       σ_BV است با فیلترِ رانشِ ۸۹کندلی و هندسهٔ **متقارن**؛ S965 ماشه‌اش **رنج و
    //       شکلِ درون-کندلی** است بدونِ هیچ فیلترِ رژیم و با هندسهٔ **نامتقارن TP>SL**
    //       ⇒ دو سنجهٔ متفاوت از یک خانوادهٔ فیزیکی (شوک)، نه دو نسخه از یک قانون.
    //       ⚠️ همپوشانی **اندازه‌گیری شد** (روی ۳۰۰۰ کندلِ آخرِ H8، هم‌ترازِ زمانی،
    //          با سیگنال‌های خودِ پایتونِ هر دو لایه):
    //            · هم‌کندل: **۱۱ از ۲۵** سیگنالِ S965 (۴۴٪ از S965 · ۱۸٪ از S950)
    //            · جهت: **۱۱ هم‌جهت / ۰ مخالف** ⇒ هیچ هجِ خودزنی رخ نمی‌دهد ✅
    //            · با پنجرهٔ نگه‌داری (۱۶ در برابر ۳۴ کندل): **۸۴٪** معاملاتِ S965
    //              با یک معاملهٔ بازِ S950 هم‌پوشانیِ زمانی دارد ⚠️
    //          ⇒ روی حسابِ واقعی سایزِ مشترک بگیرید (هر دو قیدِ allow_overlap=false
    //            دارند)؛ وگرنه ریسکِ هم‌زمان تا ۲× می‌شود. اندازه‌گیری:
    //            results/_scan_S965/overlap_s950_s965_h8.json
    //    سند: results/S965_KyleIntrabarPermanence_Xauusd_H8_rqs2_82_ACCEPT.md
    s965Layer(S965_CFG['XAUUSD-H8']),
    // ⭐⭐ S770 ⭐نو — «انبساطِ دامنه نسبت به ADR با تداوم» · **دوسویه** (LONG + SHORT)
    //    RQS2 = **82.4** (استخرِ {D1,H8}) · هر ۱۱ دروازهٔ H0..H10 پاس · lift=+7.23pp
    //    z=3.91 در برابرِ سدِ 2.897 (n_trials=301 صادقانه) · p_perm=4.5e−05
    //    سهمِ این کارت در استخر: n=۴۲۳ از ۶۸۹ (۶۱٪) ⇒ **عضوِ بزرگ‌ترِ استخر**.
    //    قاعده: frac = (close − openِ **روزِ تقویمیِ UTC**) ÷ ADR(21) و **عبورِ**
    //      آن از ±0.65 (عبور، نه بودن ⇒ هر روز حداکثر یک ماشه در هر سو) ⇒ تداومِ هم‌جهت.
    //    هندسه: SL=1.272×ATR(100) و TP=2.058×SL (RR=2.058 ⇒ قانونِ بودجه TP>SL برقرار)
    //      — **برداری** از کندلِ سیگنال (میانهٔ اندازه‌گیری‌شدهٔ این کارت ≈۱۵۵ pip SL)
    //      · maxHold=۱۶ کندلِ H8 · allow_overlap=false.
    //
    //    ⚠️ **افشای صریح — این حکم استخری است، نه تک‌کارتی.** کارتِ H8 به‌تنهایی
    //       `REJECT` (RQS2=19.3) داشت با lift=+4.23pp. ورودش به سایت **تنها** به
    //       اعتبارِ استخرِ {D1,H8} است که با هم هر ۱۱ دروازه را پاس کرد. کسی نباید
    //       این کارت را «مستقلاً اثبات‌شده» بخواند — عینِ همان افشایی که برای
    //       S432/M15 و S431 ثبت شد. حذفِ هر یک از دو عضو، جمعیتی که حکم بر آن
    //       صادر شده را نابود می‌کند ⇒ طبقِ قانونِ MTF **هر دو** وصل می‌شوند.
    //    چرا با این حال ارزشِ اتصال دارد: lift هر دو عضو مثبت و هم‌علامت است و
    //       ساختارِ lift با مقیاس **یکنوا** رشد می‌کند (زیرساعتی منفی → H4 +2.67
    //       → H8 +4.23 → D1 +5.70) ⇒ پدیدهٔ فیزیکیِ مقیاس-وابسته، نه گلچینِ تایم‌فریم.
    //
    //    مکمل بودن با دو لایهٔ دیگرِ همین کارت — سه ماشهٔ **متفاوت** از یک بازار:
    //      · S950 ماشه‌اش **بازدهِ لگاریتمیِ** یک کندل در برابرِ σ_BV است (جهش).
    //      · S965 ماشه‌اش **رنج و شکلِ درون-کندلیِ** یک کندل است (شوکِ کایل).
    //      · S770 ماشه‌اش **حرکتِ تجمعیِ روز نسبت به مقیاسِ روزانه (ADR)** است —
    //        یعنی تنها لایهٔ این کارت که به **روزِ تقویمی** لنگر دارد نه به یک کندل،
    //        و تنها لایه‌ای که متغیرِ حالتش **بی‌بعد** است (کسری از ADR).
    //      ⇒ سه منبعِ اطلاعاتیِ مستقل، نه سه نسخه از یک ایده.
    //
    //    ⚠️⚠️ **قیدِ سایزِ مشترک — الزامی و انباشته روی این کارت.** حکمِ S770 با
    //       `allow_overlap=false` **و** صفِ FIFOِ تقویمیِ استخری (همزمانیِ حداکثر ۱
    //       میانِ D1 و H8) اندازه‌گیری شد. پس روی حسابِ واقعی:
    //         ① اگر کارتِ D1 و همین کارت هم‌زمان S770 دادند ⇒ فقط **اولی** معامله شود.
    //         ② اگر S950 یا S965 هم‌زمان بازند ⇒ سایزِ مشترک (هشدارِ ثبت‌شدهٔ
    //            بالای همین بلوک: S950↔S965 هم‌کندل ۱۱/۲۵ و ۸۴٪ تلاقیِ پنجره).
    //       بی‌رعایتِ این قید، ریسکِ هم‌زمانِ کارت چند برابر می‌شود و حکمِ
    //       اندازه‌گیری‌شده دیگر معتبر نیست.
    //    parity: mismatch=0 · ۱۸۴ LONG + ۱۳۲ SHORT بازتولید شد + ۴۰ کنترلِ منفی
    //       (results/_scan_S770/parity_s770_PASS.txt)
    //    سند: results/S770_AdrExpansionPool_Xauusd_D1H8_rqs2_82_ACCEPT.md
    s770Layer(S770_CFG['XAUUSD-H8']),
    // ⭐ S966 ⭐نو — «ماندگاریِ کایل × هم‌راستاییِ درفت» (Kyle Permanence, Drift-Aligned)
    //    RQS2 = **85.8** · هر ۱۱ دروازهٔ H0..H10 سبز · n=74 · WR=55.41٪ · PF=1.87
    //    lift=+11.99pp · z=3.21 · p_perm=0.00066 (۱۰۰۰ جایگشت)
    //    سند: results/S966_KylePermanenceDriftAligned_Xauusd_H8_rqs2_86_ACCEPT.md
    //
    //    قاعده (یک خط): کندلِ شوکِ کایل (رنج ≥ ۲.۶۱۸·ATR21ِ علّی) **با** ماندگاریِ
    //    درون-کندلی ρ=|C−O|÷(H−L) ≥ ۰.۶۱۸ — و **تنها اگر** بدنه هم‌جهتِ درفتِ
    //    علّیِ ۱۸۰کندلی باشد (close[t−1] در برابرِ close[t−181]) ⇒ ادامهٔ جهتِ بدنه.
    //
    //    ⓵ **چرا زیرِ همهٔ لایه‌های این کارت وصل شد (نه بالای آن‌ها):**
    //       همپوشانی **اندازه‌گیری شد** (۳۰۰۰ کندلِ آخرِ H8، هم‌ترازِ زمانی):
    //       S966 **زیرمجموعهٔ ساختاریِ ۱۰۰٪ِ S965** است — ۱۱ از ۱۱ سیگنال هم‌کندل و
    //       هم‌جهت با S965، صفر موردِ مخالف. پس S966 **پوششِ نو نمی‌آورد**؛ ارزشش
    //       فیلترِ **کیفیت** است: ۱۴ سیگنالِ S965 که درفت مخالفشان بود حذف می‌شوند و
    //       lift از +۲.۶۱pp به **+۱۱.۹۹pp** می‌رسد. چون S965 مجموعهٔ بزرگ‌ترِ
    //       ACCEPT-دار است، آن تصمیمِ اصلیِ کارت می‌ماند و S966 در `otherLayers`
    //       به‌عنوان **مُهرِ تأییدِ کیفیت** دیده می‌شود: اگر هر دو ENTRY باشند،
    //       آن سیگنالِ S965 از نوعِ «درفت-هم‌راستا» است (کیفیتِ بالاتر).
    //       سند: results/_scan_S966/overlap_s950_s965_s966_h8.json
    //    ⓶ **ضدِ اشتباهِ «کلونِ لایهٔ موجود»:** پریتی یک کنترلِ اختصاصیِ دروازه دارد —
    //       ۱۳ کندلی که پایهٔ S965 شلیک کرد ولی درفت مخالف بود، **همه بلاک شدند**
    //       (leak=0) ⇒ دروازه واقعاً وصل است، نه تزئینی.
    //       سند: results/_scan_S966/parity_web_s966.json (verdict=PASS)
    //    ⓷ **قانونِ MTF رعایت شد:** از دو تایم‌فریمِ پیش‌ثبت‌شده تنها **H8** حکمِ
    //       ACCEPT گرفت؛ H6 با RQS2=۷.۸ (lift +۲.۶۱ · z=۰.۵۹) رد شد ⇒ کارتِ H6
    //       ساخته **نمی‌شود**. تعمیم بدونِ شاهد ممنوع.
    //    ⚠️ **هشدارِ سایزِ مشترکِ کارتِ H8 — اکنون سه‌لایه‌ای:** پیش‌تر برای
    //       S950↔S965 ثبت شده بود (هم‌کندل ۱۱/۲۵ · ۸۴٪ تلاقیِ پنجره). با S966:
    //       هم‌کندل با S965 = ۱۰۰٪ و با S950 = ۸۱.۸٪ (صفر جهتِ مخالف). هر سه لایه
    //       `allow_overlap=false` دارند ⇒ روی حسابِ واقعی، ENTRYِ هم‌زمانِ این سه
    //       **یک** رویدادِ شوک است و باید **یک** پوزیشن گرفته شود، نه سه.
    s966Layer(S966_CFG['XAUUSD-H8']),
  ],
  'XAUUSD-H12': [
    // ⭐⭐ S800 — «فشردگی → گشایش» (Squeeze-Expansion Breakout) · **کارتِ نو**
    //    RQS2 = **83.6** · هر ۱۱ دروازهٔ H0..H10 پاس · حکمِ **مستقلِ تک-کارتی**
    //    n=183 · WR 54.60٪ (LONG 99 معامله +15.9pp / SHORT 84 معامله +9.5pp)
    //    PF=1.550 · maxDD=5.64٪ · MCL=7 · lift=+12.93pp · z_obs=3.546 · p_perm=1.95e−04
    //    پیکربندیِ قفل‌شده (results/_scan_S800/H12_locked.json — پیش از دیدنِ حکم):
    //      p=21 (کانالِ دانچیان) · q=30.0٪ (چندکِ فشردگی) · filter=none
    //      k=2.058 (SL=k×ATR(21)) · rr=1.618 · hold=34 کندلِ H12
    //    قانون: نوسان در چندکِ پایینِ ۳۰٪ (رتبهٔ چندکیِ ATR در ۱۰۱ کندلِ اخیر، با
    //      تأخیرِ ۱ کندل) **و** بسته‌شدن بیرونِ کانالِ دانچیانِ ۲۱ ⇒ ادامهٔ گشایش.
    //    ⓵ مسیرِ چندگانگی C: جست‌وجوی خانوادهٔ ۹۷۲تایی فقط روی **نیمهٔ اول**
    //       (split_bar=3999 از 7998)، سپس یک داوریِ نهاییِ تک‌شات با n_trials=1.
    //    ⓶ ساختارِ MTF صادقانه: H1/H3/H6 آزمونِ نهایی شدند و **REJECT** خوردند
    //       (4.9 / 20.5 / 19.7)؛ M1..M30 و H2 توانِ کافی نداشتند و هرگز داوری
    //       نشدند ⇒ فقط D1 و H12 حقِ اتصال دارند (تعمیمِ بدونِ شاهد ممنوع).
    //    ⓷ همپوشانی با S382-H4: تقویمِ روزانه ۹۰.۶٪ همپوشان است، ولی **هر دو**
    //       زیرمجموعهٔ همپوشان و مستقل سوددهند ⇒ فیلترِ حذفی لازم نیست.
    //       ⚠️ روی حسابِ واقعی صفِ FIFO لازم است (قیدِ allow_overlap=false).
    //    ⚠️ کندل‌های این کارت از تجمیعِ H1×12 ساخته می‌شوند (Yahoo H12 ندارد) —
    //       مرزهای UTC 00/12 با کندل‌های MT5 هم‌ترازند (t % 43200 == 0).
    //    سند: results/S800_SqueezeExpansion_Xauusd_M1toMN1_rqs2_91_ACCEPT.md
    s800Layer(S800_CFG['XAUUSD-H12']),
  ],
  'XAUUSD-D1': [
    // ⭐⭐ S800 — «فشردگی → گشایش» (Squeeze-Expansion Breakout) · **کارتِ نو**
    //    RQS2 = **91.1** ⇒ از بالاترین نمرات سایت · هر ۱۱ دروازهٔ H0..H10 پاس
    //    n=81 (~۵.۲ معامله در سال) · WR 70.37٪ (LONG 49 معامله +24.21pp /
    //      SHORT 32 معامله +16.37pp ⇒ **هر دو سو** لبه دارند، نه فقط یک جهت)
    //    PF=1.937 · maxDD=2.77٪ · MCL=3 (مجاز ۸) · lift=+21.12pp
    //    z_obs=3.801 در برابرِ z_luck_bound=0.520 · p_perm=7.2e−05 · cal_positive=4/4
    //    پیکربندیِ قفل‌شده (results/_scan_S800/D1_locked.json — پیش از دیدنِ حکم):
    //      p=55 (کانالِ دانچیان) · q=20.0٪ (چندکِ فشردگی) · filter=none
    //      k=1.272 (SL=k×ATR(21)) · rr=1.0 (متقارن ⇒ صفر تورشِ WR-سازی) · hold=21
    //    ⓵ کم‌بسامد و کم‌ریسک: ۸۱ معامله در ۱۵.۶ سال با maxDD زیرِ ۳٪ —
    //       بالاترین کیفیتِ ریسکِ کلِ لایه‌های تایم‌فریمِ بالای سایت.
    //    ⓶ هر ۴ چهارکِ تقویمی مثبت (cal_positive=4/4) ⇒ لبه به یک دورهٔ خاص
    //       (مثلاً رژیمِ روندیِ ۲۰۲۳-۲۰۲۶) گره نخورده است.
    //    ⓷ همپوشانی با S382-H4: ۸۱.۴٪ تقویمی، ولی هر دو زیرمجموعه سودده
    //       ⇒ لایه حذف نمی‌شود؛ فقط صفِ FIFO روی حسابِ واقعی لازم است.
    //    ⚠️ کندل‌های این کارت از تجمیعِ H1×24 ساخته می‌شوند و **نه** از کندلِ
    //       ۱-روزهٔ Yahoo: کندلِ روزانهٔ GC=F در ۰۴:۰۰ UTC باز می‌شود، در حالی
    //       که D1ِ بک‌تستِ MT5 نیمه‌شبِ UTC است (t % 86400 == 0). تجمیعِ H1
    //       دقیقاً همان مرزها را بازتولید می‌کند.
    //    سند: results/S800_SqueezeExpansion_Xauusd_M1toMN1_rqs2_91_ACCEPT.md
    s800Layer(S800_CFG['XAUUSD-D1']),
    // ⭐⭐ S770 ⭐نو — «انبساطِ دامنه نسبت به ADR با تداوم» · **دوسویه** (LONG + SHORT)
    //    ⇒ **عضوِ دومِ همان استخرِ {D1,H8}**؛ نسخهٔ H8 در کارتِ بالاتر وصل شد.
    //    RQS2 = **82.4** (حکمِ استخری) · هر ۱۱ دروازهٔ H0..H10 پاس · n=689
    //    WR=44.70٪ · PF=1.398 · maxDD=5.83٪ · net=+$29,077 · lift=+7.23pp
    //    z=3.91 در برابرِ سدِ 2.897 (n_trials=301 صادقانه) · p_perm=4.5e−05
    //    holdout: PF=1.502 ⇒ **بهتر** از نیمهٔ کشف (نشانهٔ نبودِ بیش‌برازش)
    //    سهمِ این کارت در استخر: n=۲۶۶ از ۶۸۹ (۳۹٪).
    //    قاعده: frac = (close − openِ **روزِ تقویمیِ UTC**) ÷ ADR(21) و **عبورِ**
    //      آن از ±0.65 ⇒ تداومِ هم‌جهت. روی D1 هر کندل خودش یک روز است ⇒ ADR
    //      همان میانگینِ دامنهٔ ۲۱ کندلِ اخیر با یک کندل تأخیر (علّی).
    //    هندسه: SL=1.272×ATR(100) و TP=2.058×SL (RR=2.058 ⇒ TP>SL برقرار)
    //      — **برداری** از کندلِ سیگنال (میانهٔ اندازه‌گیری‌شدهٔ این کارت ≈۲۸۶ pip SL)
    //      · maxHold=۱۶ کندلِ D1 · allow_overlap=false.
    //
    //    ⚠️ **افشای صریح — حکم استخری است، نه تک‌کارتی.** کارتِ D1 به‌تنهایی
    //       `REJECT` (RQS2=21.0) داشت با lift=+5.70pp — بالاترین liftِ استخر ولی
    //       با n=۲۲۵ کم‌توان. علتِ REJECT **کمبودِ n بود نه نبودِ لبه**؛ استخر
    //       دقیقاً برای همین ساخته شد. پس این کارت «مستقلاً اثبات‌شده» نیست و
    //       اعتبارش با عضوِ H8 گره خورده است ⇒ حذفِ هر یک، جمعیتِ حکم را نابود
    //       می‌کند (قانونِ MTF: همهٔ تایم‌فریم‌های پاس‌شده باید وصل شوند).
    //    ساختارِ liftِ یکنوا با مقیاس: زیرساعتی منفی → H4 +2.67 → H8 +4.23 →
    //       D1 +5.70 ⇒ پدیدهٔ فیزیکیِ مقیاس-وابسته (هرچه ADR معنادارتر، لبه بیشتر)،
    //       نه گلچینِ تایم‌فریم. **D1 نقطهٔ اوجِ این ساختار است.**
    //
    //    مکمل بودن با S800 در همین کارت — دو ماشهٔ متقابلِ آینه‌ای:
    //      · S800 از **فشردگیِ** نوسان (چندکِ پایینِ ATR) + شکستِ دانچیان می‌آید
    //        ⇒ ورود در *آغازِ* بیدارشدنِ بازار از خواب.
    //      · S770 از **انبساطِ** دامنه نسبت به ADR می‌آید ⇒ ورود در *میانهٔ* یک
    //        حرکتِ بزرگِ همان‌روز که قبلاً بیدار شده است.
    //      ⇒ دو فازِ متفاوت از چرخهٔ نوسان (کم‌نوسان→شکست در برابر پرنوسان→تداوم)
    //        و دو مقیاسِ ATR متفاوت (۲۱ در برابرِ ۱۰۰) ⇒ منابعِ اطلاعاتیِ مستقل.
    //
    //    ⚠️⚠️ **قیدِ صفِ FIFOِ استخری — الزامی.** حکم با همزمانیِ حداکثر ۱ معامله
    //       میانِ **کلِ استخر** اندازه‌گیری شد (max_concurrency=1.0 در متریک‌ها).
    //       پس اگر این کارت و کارتِ H8 هم‌زمان S770 دادند ⇒ فقط **اولی به ترتیبِ
    //       زمانِ تقویمی** معامله شود، نه هر دو. همچنین با S800-D1 و S382-H4
    //       (۸۱.۴٪ همپوشانیِ تقویمیِ ثبت‌شده) سایزِ مشترک لازم است.
    //    همپوشانی **اندازه‌گیری شد** نه چشمی: بخشِ هم‌زمان با لایه‌های زنده
    //       WR=۴۸.۶٪ در برابرِ بخشِ مستقل ۳۶.۰٪ — بخشِ مستقل هم بالای سربه‌سرِ
    //       هزینه‌دارِ ۳۳.۲٪ می‌ماند و سودده است ⇒ **فیلترِ حذف لازم نیست**، فقط صف‌بندی.
    //    ⚠️ کندل‌های این کارت از تجمیعِ H1×24 می‌آیند (مرزِ t % 86400 == 0) — و این
    //       برای S770 **بحرانی‌تر** از هر لایهٔ دیگرِ سایت است، چون متغیرِ حالتش
    //       مستقیماً روی openِ روزِ UTC لنگر دارد؛ کندلِ ۱-روزهٔ ۰۴:۰۰ UTCِ Yahoo
    //       فرضِ لایه را می‌شکند. زیرساختِ موجودِ کارت عیناً همین مرز را می‌سازد ✔
    //    parity: mismatch=0 · ۱۸۰ LONG + ۱۴۱ SHORT بازتولید شد + ۴۰ کنترلِ منفی
    //       (results/_scan_S770/parity_s770_PASS.txt)
    //    سند: results/S770_AdrExpansionPool_Xauusd_D1H8_rqs2_82_ACCEPT.md
    s770Layer(S770_CFG['XAUUSD-D1']),
  ],
  // ⚰️⚰️ **چهار کارتِ حذف‌شده در S396** (هیچ اتصالِ ACCEPT نداشتند):
  //    'EURUSD-M5'  ← S334 (RQS+ 84.1) — بی‌ACCEPT زیرِ RQS2
  //    'EURUSD-M15' ← S326          — بی‌ACCEPT زیرِ RQS2
  //    'EURUSD-M30' ← S345 (RQS+ 91.7) — بی‌ACCEPT زیرِ RQS2
  //    'EURUSD-H4'  ← S374          — REJECT/15.7 صریح
  //
  //    این یعنی سایت فعلاً **تک‌ارزی (فقط XAUUSD)** است. صادقانه‌ترین بازنماییِ
  //    شواهدِ موجود است: پروژه هنوز هیچ لبهٔ اثبات‌شده‌ای روی EURUSD ندارد.
  //    ماژول‌های یورو (`streak_reversal_s326.ts`, `reversal_day_s345.ts`,
  //    `kennedy_break_s374.ts`, …) در مخزن **دست‌نخورده** می‌مانند ⇒ اگر لایه‌ای
  //    با بهبود احیا شد، بازگرداندنِ کارت **یک خط** است (فلسفهٔ ROS2:
  //    گره‌ها می‌مانند، گراف عوض می‌شود).
}

export const REGISTERED_CARDS = Object.keys(CARD_LAYERS)

// ---------------------------------------------------------------------------
// اجرای یک کارت: همهٔ لایه‌های فعالِ آن را صدا می‌زند و طبقِ اولویتِ حالت
// (ENTRY > APPROACHING > NEUTRAL) تصمیمِ اصلی را انتخاب می‌کند. سایرِ لایه‌های
// فعال در otherLayers جمع می‌شوند (نمایشِ collapsed زیرِ سیگنالِ اصلی).
// ---------------------------------------------------------------------------
const STATE_RANK: Record<string, number> = { ENTRY: 3, APPROACHING: 2, NEUTRAL: 1 }

export function runCard(ctx: LayerContext): RouterDecision {
  const layers = CARD_LAYERS[ctx.cardId] || []
  const decisions: RouterDecision[] = []
  for (const fn of layers) {
    try {
      const d = fn(ctx)
      if (d) decisions.push(d)
    } catch (e) {
      // لایهٔ مشکل‌دار نباید کلِ کارت را بشکند (پایداری)
      console.error(`[registry] layer error on ${ctx.cardId}:`, (e as Error)?.message)
    }
  }
  if (decisions.length === 0) {
    return {
      state: 'NEUTRAL',
      regime: lightRegime(0, false, 'no_layer'),
      headline: 'خنثی — لایهٔ فعالی برای این کارت نیست',
      reason: 'برای این ترکیبِ جفت‌ارز/تایم‌فریم لایهٔ احیاشده‌ای ثبت نشده است.',
      indicators: [],
    }
  }
  // مرتب‌سازی: بالاترین رتبهٔ حالت، سپس بالاترین probability (اگر بود)
  decisions.sort((x, y) => {
    const r = (STATE_RANK[y.state] || 0) - (STATE_RANK[x.state] || 0)
    if (r !== 0) return r
    return (y.probability || 0) - (x.probability || 0)
  })
  const primary = decisions[0]
  const others = decisions.slice(1).filter(d => d.state === 'ENTRY' || d.state === 'APPROACHING')
  if (others.length > 0) {
    // 🔧 باگِ User Note #۴: هر لایهٔ همزمانِ فعال، اعدادِ کاملِ معاملهٔ خودش را حمل می‌کند
    //   تا کاربر بتواند *همزمان چند لایه* را مستقل معامله کند (نه فقط لایهٔ اصلی را).
    primary.otherLayers = others.map(d => ({
      code: d.sourceLayer?.code || '—',
      name: d.sourceLayer?.name || d.headline,
      kind: (d.sourceLayer?.kind as string) || 'unknown',
      state: d.state as 'ENTRY' | 'APPROACHING',
      direction: d.direction,
      reason: d.reason,
      confirmations: d.confirmations,
      // اعدادِ معامله فقط وقتی state=ENTRY است معنا دارند:
      entry: d.state === 'ENTRY' ? d.entry : undefined,
      tp: d.state === 'ENTRY' ? d.tp : undefined,
      sl: d.state === 'ENTRY' ? d.sl : undefined,
      rr: d.state === 'ENTRY' ? d.rr : undefined,
      probability: d.probability,
      sizing: d.state === 'ENTRY' ? d.sizing : undefined,
      tpPlan: d.state === 'ENTRY' ? d.tpPlan : undefined,
    }))
  }
  // 🕒 باگِ User Note #۳: جمع‌آوریِ دروازه‌های زمانیِ *همهٔ* لایه‌های این کارت (نه فقط
  //   primary) برای نوارِ شمارشِ معکوسِ مستقلِ ۲۴ساعته. حذفِ تکراری بر پایهٔ layerCode.
  const gates = decisions
    .map(d => d.timeGate)
    .filter((g): g is NonNullable<RouterDecision['timeGate']> => !!g)
  if (gates.length > 0) {
    const seen = new Set<string>()
    primary.cardTimeGates = gates.filter(g => {
      if (seen.has(g.layerCode)) return false
      seen.add(g.layerCode)
      return true
    })
  }
  return primary
}
