// ============================================================================
// strategy_registry.ts — رجیستریِ ماژولارِ لایه‌های احیاشده (RQS+ ≥ 80)
// ----------------------------------------------------------------------------
// این فایل «مغزِ مسیریابیِ» سایتِ بازطراحی‌شده است: پس از حذفِ کاملِ استراتژی‌های
// قدیمی (طبق User Note)، تنها ۱۱ لایهٔ احیاشدهٔ ACCEPTED در سایت باقی می‌مانند و
// این رجیستری آن‌ها را به کارت‌های (جفت‌ارز × تایم‌فریم) نگاشت می‌کند.
//
// معماری (ماژولار/توسعه‌پذیر — نباید در هیچ به‌روزرسانی از بین برود):
//   • هر لایه یک تابعِ decide* مستقل دارد که RouterDecision برمی‌گرداند.
//   • CARD_LAYERS: نگاشتِ «کارت → فهرستِ لایه‌های فعال (به‌ترتیبِ اولویت)».
//   • runCard(): لایه‌های کارت را اجرا می‌کند و طبقِ اولویتِ حالت (ENTRY > APPROACHING
//     > NEUTRAL) یک تصمیمِ اصلی برمی‌گرداند؛ بقیهٔ لایه‌های فعال در otherLayers می‌آیند.
//   • افزودنِ لایهٔ جدید = فقط یک ورودی در REGISTRY + CARD_LAYERS (بدونِ دستکاریِ کارت‌ها).
//
// ۱۱ لایهٔ احیاشده:
//   زمان-محور:   S310 (EOM drift)، S312 (mid-month drift)
//   ماژولِ آماده: S313 (squeeze)، S326 (streak-rev)، S327 (sell-climax)
//   ماژولِ نو:    S321 (ribbon)، S322 (ichimoku)، S323 (S/R pullback)،
//                 S324 (liquidity-sweep)، S328 (RSI21 fade)، S330 (ORB fade)
// ============================================================================

import type { Candle } from './indicators'
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
//     ⚠️ فقط روی M5 وصل می‌شود؛ M15/M30/H1 در دروازهٔ H3 ماندند ⇒ حق اتصال ندارند.
//     سند: results/S355_LPSBStateFilterRevival_Xauusd_M5_rqs2-84.md
import { withLpsbGate, S355_CFG } from './lpsb_state_s355'
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
function s312Layer(slPip: number, tpPip: number, maxHold: number): LayerFn {
  return (ctx) => {
    const sig = computeMidMonth(ctx.times, ctx.utcHour)
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
// ⚰️ s341Layer حذف شد — S341 زیرِ RQS2 v2.4 مرده است (بالا را ببینید).
// لایهٔ نوِ این نشست: S344 Brooks Trend-from-Open first-pullback continuation (فصلِ ۲۳) — نخستین SHORT روی XAUUSD-M15
const s344Layer = (cfg: typeof S344_CFG[string]): LayerFn => (ctx) => decideS344(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ نوِ این نشست: S345 Brooks Reversal Day — چرخشِ روندِ درون‌روزی (فصلِ ۲۴)
const s345Layer = (cfg: typeof S345_CFG[string]): LayerFn => (ctx) => decideS345(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ احیاشدهٔ این نشست: S356 = S354-causal، Brooks Trend Resumption Day (فصلِ ۲۵)
const s354Layer = (cfg: typeof S354_CFG[string]): LayerFn => (ctx) => decideS354(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)

// ---------------------------------------------------------------------------
// نگاشتِ کارت → لایه‌های فعال (به‌ترتیبِ اولویت). فقط لایه‌هایی که روی همان
// (جفت‌ارز × TF) با RQS+ ≥ 80 ACCEPTED شده‌اند. منبع: نامِ فایل‌های results/.
// افزودنِ کارت/لایهٔ جدید فقط این جدول را تغییر می‌دهد (ماژولار/توسعه‌پذیر).
//
//   کارت         لایه‌های ACCEPTED (منبعِ نامِ فایل results/)
//   XAUUSD-M5    S355=S333+LPSB(LONG·**RQS2 83.9**) · S330(FADE) · S328(SHORT) · S334(SHORT) · S335(LONG) · S327(LONG) · S326(LONG)
//   XAUUSD-M15   S345(LONG·reversal-day·RQS 90.7) · S333(LONG·pullback·RQS 91.7) · S332(LONG·squeeze r2+hurst) · S324(LONG) · S322(LONG) · S323(LONG) · S335(LONG) · S344(SHORT) · S310(LONG) · S312(LONG)
//   XAUUSD-M30   S333(LONG·pullback·RQS 91.1) · S313(LONG) · S324(SHORT) · S321(L+S) · S327(LONG) · S326(LONG) · S323(LONG) · S312(LONG)
//   XAUUSD-H1    S356(LONG·trend-resumption·**RQS2 81.5**) · S333(LONG·pullback·RQS 89.8) · S313(LONG) · S328(SHORT) · S327(LONG) · S323(LONG) · S335(LONG) · S312(LONG)
//   ⚰️ S341 از هر ۴ کارتِ بالا حذف شد (RQS2 = 28.6 در بهترین حالت، سد = 70).
//   XAUUSD-H4    S332(LONG·squeeze ADX/DI) · S327(LONG)
//   EURUSD-M15   S326(LONG)
//   EURUSD-M30   S327(LONG) · S345(SHORT·reversal-day·RQS 91.7)
//
//   ⚖️ S333 = احیای S79 با هندسهٔ منصفانه (TP≥SL، breakeven≤۵۰٪): WR واقعی از دقتِ
//      محلِ ورود (rsi_turn/price_turn) + رژیمِ Hurst/ER، نه از TP<SL. (تصحیحِ User Note)
// ---------------------------------------------------------------------------
export const CARD_LAYERS: Record<string, LayerFn[]> = {
  'XAUUSD-M5': [
    // ⚰️ S341 حذف شد (RQS2=26.3 · سد=70) — سند: results/S341_BrooksSwingFadeRejudged_…_rqs2-28.md
    // ⭐ S355 = S333/M5 **با دروازهٔ حالتِ ساختارِ LPSB** — تنها لایهٔ ۱۱/۱۱ دروازهٔ RQS2.
    //    پایهٔ بدونِ دروازه: WR 65.6% · PF 2.85 · RQS2=27.5 (POWER-LIMITED، حقِ اتصال نداشت)
    //    با دروازه:          WR 72.3% · PF 3.95 · RQS2=83.9 (ACCEPT ✓) ⇒ همین وصل می‌شود.
    withLpsbGate(s333Layer(S333_CFG['XAUUSD-M5']), S355_CFG['XAUUSD-M5']),
    s330Layer(S330_CFG['XAUUSD-M5']),
    s328Layer(S328_CFG['XAUUSD-M5']),
    s334Layer(S334_CFG['XAUUSD-M5']),    // احیای s122 — MR-fade فروش + گیتِ Hurst<0.5/Kurt<1.8 — RQS+=81.6 (WR 61.7% · PF 1.61)
    s335Layer(S335_CFG['XAUUSD-M5']),    // S335 — Reflex zero-up چرخهٔ اِهلرز، خریدِ کفِ چرخه — RQS+=92.2 (WR 62.7% · PF 2.22) · همپوشانیِ صفر با S333
    // ⚰️ S327 حذف شد (RQS2=21.5 · سد=70) — سند: results/S327_SellClimaxReversalRejudged_…_rqs2-29.md
    //    معاوضهٔ هندسه‌–شواهد: RR=0.371 ⇒ WR 88.6% ولی H2 حسابیاً رد؛ RR=0.52 ⇒ WR 75.0% ولی z افت به 2.83.
    s326Layer(STREAK_REV_CFG['XAUUSD-M5']),
  ],
  'XAUUSD-M15': [
    // ⚰️ S341 حذف شد (RQS2=24.9 · سد=70) — ضعیف‌ترین کارتِ لایه: ۵/۱۰ دروازه شکست
    s333Layer(S333_CFG['XAUUSD-M15']),   // احیای S79 — pullback (ورودِ مستقیم) — RQS+=91.7 (WR 62.8% · PF 2.30)
    s332Layer(S332_CFG['XAUUSD-M15']),   // احیای squeeze با فیلترِ آماری r2+hurst — RQS+=91.2
    s324Layer(S324_CFG['XAUUSD-M15']),
    s322Layer(S322_CFG['XAUUSD-M15']),
    // ⚰️ S323 حذف شد (بازداوریِ RQS2 v2.4). این کارت z=1.19 داشت — لیفتِ +5.86pp
    //    روی n=105؛ بسیار دورتر از سدِ 3.634. نسخهٔ مستقر حتی ضعیف‌تر: n=83، WR=55.42٪.
    //    جزئیات: results/S323_SRPullbackGolden_Xauusd_M5M15M30H1_rqs2-24_DEAD.md
    s335Layer(S335_CFG['XAUUSD-M15']),  // S335 — Reflex dip-turn + گیتِ r2>0.55 — RQS+=89.7 (WR 60.0% · PF 2.08) · همپوشانیِ صفر با S333
    s344Layer(S344_CFG['XAUUSD-M15']),  // S344 — Brooks فصلِ ۲۳ trend-from-open first-pullback SHORT — RQS+=91.4 (WR 64.1% · PF 2.08 · +$1,571) · مستقل=92.9 · نخستین SHORT این کارت
    s345Layer(S345_CFG['XAUUSD-M15']),  // S345 — Brooks فصلِ ۲۴ reversal-day چرخشِ روندِ روز LONG — RQS+=90.7 (WR 62.4% · PF 2.30 · +$2,422.8) · همپوشانی 48.5% ولی بخشِ مستقل قوی‌تر (WR 65.0/PF 2.56)
    s310Layer,
    s312Layer(295, 295, 48),
  ],
  'XAUUSD-M30': [
    // ⚰️ S341 حذف شد (RQS2=28.6 · سد=70) — بهترین کارتِ لایه، و همان هم رد شد
    s333Layer(S333_CFG['XAUUSD-M30']),   // احیای S79 — pullback با تأییدِ price_turn — RQS+=91.1 (WR 66.7% · PF 2.48)
    s313Layer(S313_M30),
    s324Layer(S324_CFG['XAUUSD-M30']),
    s321Layer(S321_CFG['XAUUSD-M30']),
    // ⚰️ S327 حذف شد (RQS2=22.2 · سد=70) — نزدیک‌ترین شکستِ H2 کلِ لایه: مازاد +2.90pp در برابرِ کفِ 3.00pp.
    s326Layer(STREAK_REV_CFG['XAUUSD-M30']),
    // ⚰️ S323 حذف شد (RQS2=24.7 · بهترین کارتِ کلِ لایه). ۱۰ دروازه پاس، تنها H5
    //    افتاد: z=3.266 در برابرِ سدِ 3.634 (درون‌کارتی) و 4.131 (سراسری). چهار
    //    مسیرِ نجات با ۱۶۸ آزمون شکست خورد ⇒ قانونِ مرگِ ابدی محقق شد.
    //    نسخهٔ مستقر لیفتِ **منفی** −4.25pp داشت (n=104، WR=55.77٪ در برابرِ مبنای 58.29٪).
    s312Layer(295, 295, 36),
  ],
  'XAUUSD-H1': [
    // S356 اول می‌آید چون تنها لایهٔ این کارت است که با معیارِ حاکمِ **RQS2 v2.4**
    // داوری شده (هر ۱۱ دروازه، هر ۳ seed)؛ بقیه با RQS+ بازنشسته پذیرفته شده‌اند.
    s354Layer(S354_CFG['XAUUSD-H1']),    // S356 — Brooks trend-resumption (causal، ساعت≥۱۶ UTC) — RQS2=81.5 (WR 51.28% · lift +15.0 · z=3.36 · n=117) · همپوشانی ۲۵.۶٪ (S313=25 · S335=5)
    // ⚰️ S341 حذف شد (RQS2=28.0 · سد=70). نکتهٔ افشاشده: نمرهٔ ۶۶.۷٪ این کارت از فصلِ ۱۷
    //    Brooks نمی‌آمد — از دو فیلترِ انتخاب‌شدهٔ stretch=0.7 / exh=0.25 می‌آمد؛ بهترین
    //    عضوِ خانوادهٔ خالصِ Brooks اینجا فقط ۵۶.۱٪ می‌برد.
    s333Layer(S333_CFG['XAUUSD-H1']),    // احیای S79 — pullback (ورودِ مستقیم + ER) — RQS+=89.8 (WR 62.2% · PF 1.85)
    s313Layer(S313_H1),
    s328Layer(S328_CFG['XAUUSD-H1']),
    // ⚰️ S327 حذف شد (RQS2=15.4 · سد=70) — شش دروازه شکست؛ z=1.81 در هندسهٔ قانونی.
    // ⚰️ S323 حذف شد. نسخهٔ مستقر بدترین کارتِ کلِ ممیزی بود: n=17، WR=35.29٪،
    //    لیفتِ −14.91pp ⇒ ۹۶٪ از قرعه‌های تصادفی از سیگنالِ سایت بهتر عمل می‌کردند.
    //    نسخهٔ بک‌تست‌شده هم z=2.40 روی n=37 داشت — زیرِ هر سه سد.
    s335Layer(S335_CFG['XAUUSD-H1']),   // S335 — Reflex dip-turn + گیتِ Chop<38.2 — RQS+=89.7 (WR 61.2% · PF 1.85) · همپوشانیِ صفر با S333
    s312Layer(395, 395, 24),
  ],
  'XAUUSD-H4': [
    // ⭐ S374 — «دروازهٔ شکستِ Kennedy»: نخستین لایهٔ این فصل که RQS2 را پاس کرد.
    //    z=+4.100 (سد 2.570) · n=1,062 · e_pip طلا ۱۱.۶۷→۳۲.۹۷ · h1/h2 هر دو مثبت.
    //    اولویتِ نخست چون کم‌بسامدترین و بالاترین لبه است؛ وقتی سیگنال بدهد باید
    //    شنیده شود. طلا ~۴ رویدادِ مستقل در سال ⇒ رتبهٔ محافظه‌کارانه/کم‌بسامد.
    s374Layer(KENNEDY_CFG['XAUUSD-H4']),
    s340Layer(S340_CFG['XAUUSD-H4']),   // S340 — Brooks Micro-Channel، ادامهٔ روند/failed-pullback — RQS+=92.6 (WR 65.6% · PF 2.13) · همپوشانی S327=0%/S332=8.2%
    s332Layer(S332_CFG['XAUUSD-H4']),   // احیای squeeze با فیلترِ ADX/DI — RQS+=92.1
    // ⚰️ S327 حذف شد (RQS2=18.8 · سد=70) — بدترین کارت: z=0.12، یعنی از ورودِ تصادفی تفکیک‌ناپذیر.
  ],
  'EURUSD-M5': [
    s334Layer(S334_CFG['EURUSD-M5']),    // احیای s122 — MR-fade فروش + گیتِ Hurst<0.52/Kurt<2.2 — RQS+=84.1 (WR 66.7% · PF 1.62)
  ],
  'EURUSD-M15': [
    s326Layer(STREAK_REV_CFG['EURUSD-M15']),
  ],
  'EURUSD-M30': [
    s345Layer(S345_CFG['EURUSD-M30']),   // S345 — Brooks فصلِ ۲۴ reversal-day چرخشِ روندِ روز SHORT — RQS+=91.7 (WR 62.5% · PF 2.38 · +$2,281.6) · همپوشانی 30.6% · نخستین SHORT این کارت
    // ⚰️ S327 حذف شد (RQS2=14.3 · سد=70) — هفت دروازه شکست؛ در خانوادهٔ قانونی لیفتِ **منفی**.
  ],
  // ⭐ کارتِ **نوساز** این نشست. پیش‌تر هیچ کارتِ EURUSD-H4 وجود نداشت چون هیچ لایه‌ای
  //    روی آن افق حقِ اتصال نگرفته بود. S374 نخستین لایه‌ای است که گرفت ⇒ کارت متولد شد.
  //    قانونِ MTF پروژه: «اگر لایه‌ای در چند تایم‌فریم پاس شد، منطقش باید در سایت برای
  //    **همهٔ** تایم‌فریم‌های تاییدشده اعمال شود». پذیرشِ S374 روی هر دو ارزِ H4 **باهم**
  //    اندازه‌گیری شد، پس وصل‌کردنش فقط به طلا نیمی از شواهد را دور می‌ریخت ⇒ نقضِ قانون.
  //    یورو e_pip ۱.۵۷→۶.۴۴ در برابرِ هزینهٔ ۱.۶ ⇒ **مستقلاً** بالای هزینه (یارانه از طلا نگرفته).
  //    یورو بسامدِ بهترِ این جفت را دارد: ۸۹ سیگنال در برابرِ ۲۰ سیگنالِ طلا (k=2 · gate=true)
  //    ⇒ همان‌جا که ضعفِ اصلیِ لایه (کم‌بودنِ رویدادِ مستقل) کم‌ترین شدت را دارد.
  'EURUSD-H4': [
    s374Layer(KENNEDY_CFG['EURUSD-H4']),
  ],
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
