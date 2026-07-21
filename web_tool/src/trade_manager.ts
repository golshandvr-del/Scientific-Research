// ============================================================================
// مدیریت معامله (Trade Manager) — پاسخ به User Note
// کاربر یک معامله‌ی باز (long/short) را با ورود/TP/SL وارد می‌کند و این ماژول
// با توجه به تحلیل زندهٔ بازار (قیمت فعلی، S/R، روند، ATR، سیگنال مدل) توصیه‌های
// مدیریتی می‌دهد: جابه‌جایی SL (تریل/بریک‌ایون)، جابه‌جایی TP، هشدار نزدیکی به
// حمایت/مقاومت، هشدار معکوس‌شدن روند، و پیشنهاد بستن پیش‌هنگام.
//
// این ماژول کاملاً «بی‌حالت» (stateless) است: خودِ معامله در مرورگر کاربر
// (localStorage) نگه‌داری می‌شود و فقط برای دریافت advice به سرور فرستاده می‌شود.
// ============================================================================
import type { AnalysisResult } from './signal'

export type Side = 'long' | 'short'

export interface OpenTrade {
  side: Side
  entry: number          // قیمت ورود کاربر
  tp: number             // حد سود اولیه
  sl: number             // حد ضرر اولیه
  openedAt?: number      // زمان باز کردن (ثانیه) — اختیاری
  barsHeld?: number      // تعداد کندلِ M15 که معامله باز بوده (برای سقفِ نگه‌داریِ SHORT s118)
}

export interface Advice {
  type: 'sl' | 'tp' | 'level' | 'reversal' | 'momentum' | 'close' | 'info' | 'target-hit'
  severity: 'critical' | 'warning' | 'good' | 'info'
  title: string
  detail: string
  suggest?: { field: 'tp' | 'sl'; value: number }   // پیشنهاد مقدار جدید (کاربر با یک کلیک اعمال کند)
}

export interface TradeStatus {
  side: Side
  price: number                 // قیمت فعلی بازار
  entry: number
  tp: number
  sl: number
  // وضعیت لحظه‌ای
  inProfit: boolean
  pnlUsd: number                // سود/زیان فعلی به ازای ۱ لات پایه (نسبت به فاصله)
  pnlR: number                  // سود/زیان بر حسب R (ریسک اولیه)
  progressToTp: number          // درصد پیشرفت از ورود به سمت TP (۰..۱۰۰، منفی اگر برخلاف)
  distToSlPct: number           // فاصله تا SL بر حسب درصد قیمت
  distToTpPct: number           // فاصله تا TP بر حسب درصد قیمت
  riskReward: string
  reachedTp: boolean
  reachedSl: boolean
  // توصیه‌ها
  advices: Advice[]
  overallAction: 'hold' | 'move-sl' | 'take-partial' | 'close' | 'tighten' | 'let-run'
  overallNote: string
}

const round2 = (x: number) => Math.round(x * 100) / 100

/**
 * تولید وضعیت + توصیه‌های مدیریت معامله بر اساس تحلیل زنده.
 * @param t     معاملهٔ باز کاربر
 * @param a     خروجی analyze() روی داده‌ی زنده (قیمت/ATR/S/R/روند/سیگنال مدل)
 * @param modelProbPct احتمال کلاس «برد» مدل ONNX (٪) در صورت وجود — برای هم‌سو/مخالف بودن با معامله
 */
export function evaluateTrade(t: OpenTrade, a: AnalysisResult, modelProbPct?: number): TradeStatus {
  const price = a.price
  const atr = a.atr || 1
  const isLong = t.side === 'long'

  // ریسک اولیه (فاصلهٔ ورود تا SL) و پاداش اولیه (ورود تا TP)
  const riskDist = Math.abs(t.entry - t.sl) || atr
  const rewardDist = Math.abs(t.tp - t.entry) || atr

  // سود/زیان فعلی بر حسب دلار (جهت‌دار) و بر حسب R
  const rawMove = isLong ? (price - t.entry) : (t.entry - price)
  const pnlUsd = round2(rawMove)
  const pnlR = round2(rawMove / riskDist)

  // ==========================================================================
  // 🔧 رفعِ باگِ User Note #3 (توصیه‌های گمراه‌کننده «فوراً ببند»)
  // --------------------------------------------------------------------------
  // شکایتِ کاربر: «همین که معامله را باز کردم گفت ببند، در حالی‌که فقط به‌خاطرِ
  // اسپرد کمی در ضرر بودم!» دو ریشه داشت:
  //   ۱) هیچ «ناحیهٔ خنثیِ نویز/اسپرد» نبود؛ افتِ ناچیزِ اول = «ضرر» تلقی می‌شد.
  //   ۲) هیچ «دورهٔ تنفس (grace)» بعد از ورود نبود؛ توصیهٔ بحرانی فوراً فعال می‌شد.
  //
  // راه‌حل:
  //   • ناحیهٔ خنثی = max(نصفِ اسپردِ تخمینی، ~۰.۱۲R). داخلِ این ناحیه معامله
  //     «تازه/نزدیکِ ورود» است، نه «در سود» و نه «در ضرر». هیچ توصیهٔ ترس‌آور نمی‌دهیم.
  //   • دورهٔ تنفس: تا ۳ کندلِ اول (۴۵ دقیقه) یا تا وقتی حرکت از ناحیهٔ خنثی خارج نشده،
  //     فقط پیام «به معامله فرصت بده» می‌دهیم؛ هیچ «ببند/بستنِ بخشی» صادر نمی‌شود.
  // ==========================================================================
  // اسپردِ تخمینیِ هر دارایی بر حسبِ واحدِ قیمت (برای XAUUSD ~۰.۳$؛ فارکس ~۰.۰۰۰۲).
  // اگر ATR بزرگ باشد اسپرد نسبیِ کوچکی است؛ ناحیهٔ خنثی را از هر دو می‌گیریم.
  const spreadEst = price >= 100 ? 0.35 : price >= 5 ? 0.03 : 0.0002
  // ناحیهٔ خنثی: بزرگ‌ترِ (اسپرد، ۰.۱۲R، ۰.۱۵×ATR) — تا نویز/اسپرد «ضرر» شمرده نشود.
  const neutralBand = Math.max(spreadEst, 0.12 * riskDist, 0.15 * atr)
  // فاصلهٔ زمانی از باز شدنِ معامله (ثانیه) — برای دورهٔ تنفس.
  const ageSec = t.openedAt ? Math.max(0, Math.floor(Date.now() / 1000) - t.openedAt) : Infinity
  const withinGraceTime = ageSec < 45 * 60         // < ۴۵ دقیقه (۳ کندلِ M15)
  const withinNeutralBand = Math.abs(rawMove) <= neutralBand
  // «تازه‌بودنِ معامله»: هم زمانِ کوتاه و هم هنوز داخلِ ناحیهٔ خنثی → فرصت بده.
  const isFresh = withinGraceTime && withinNeutralBand
  // «در سود/ضررِ واقعی» فقط وقتی از ناحیهٔ خنثی خارج شده‌ایم.
  const inProfit = rawMove > neutralBand
  const inRealLoss = rawMove < -neutralBand

  // پیشرفت به سمت TP (۱۰۰٪ یعنی رسیده به TP)
  const progressToTp = round2((rawMove / rewardDist) * 100)

  // فاصله تا SL / TP بر حسب درصد قیمت
  const distToSl = isLong ? (price - t.sl) : (t.sl - price)   // مثبت = هنوز نرسیده
  const distToTp = isLong ? (t.tp - price) : (price - t.tp)   // مثبت = هنوز نرسیده
  const distToSlPct = round2((distToSl / price) * 100)
  const distToTpPct = round2((distToTp / price) * 100)

  const reachedTp = isLong ? price >= t.tp : price <= t.tp
  const reachedSl = isLong ? price <= t.sl : price >= t.sl

  const advices: Advice[] = []

  // ---------- ۰) دورهٔ تنفسِ ابتدایی (رفعِ باگِ «فوراً ببند») ----------
  // اگر معامله تازه است و هنوز داخلِ ناحیهٔ خنثی/اسپرد مانده (و به TP/SL نرسیده)،
  // هیچ توصیهٔ ترس‌آوری نمی‌دهیم — فقط توضیح می‌دهیم که این افت/نوسانِ ناچیز طبیعی است.
  if (isFresh && !reachedTp && !reachedSl) {
    const moveTxt = rawMove < 0
      ? `افتِ فعلی (${round2(Math.abs(rawMove))} واحدِ قیمت) در حدِ اسپرد/نویزِ طبیعیِ ورود است`
      : `حرکتِ فعلی هنوز ناچیز است`
    advices.push({
      type: 'info', severity: 'info',
      title: 'معامله تازه باز شده — به آن فرصت بده',
      detail: `${moveTxt}. این یعنی «ضرر» نیست؛ صرفاً معامله هنوز از محدودهٔ ورود فاصله نگرفته. ` +
        `تا وقتی قیمت از این ناحیه خارج نشده، طبقِ پلن با همان TP/SLِ اولیه صبور بمان — بستنِ زودهنگام فقط اسپرد را ضرر می‌کند.`,
    })
    return {
      side: t.side, price: round2(price), entry: round2(t.entry), tp: round2(t.tp), sl: round2(t.sl),
      inProfit, pnlUsd, pnlR, progressToTp,
      distToSlPct: round2(((isLong ? price - t.sl : t.sl - price) / price) * 100),
      distToTpPct: round2(((isLong ? t.tp - price : price - t.tp) / price) * 100),
      riskReward: `R:R اولیه ≈ 1:${round2(rewardDist / riskDist)}`,
      reachedTp: false, reachedSl: false,
      advices,
      overallAction: 'hold',
      overallNote: 'معامله تازه باز شده و هنوز در محدودهٔ ورود است — طبقِ پلن صبور بمان، عجله برای بستن نکن.',
    }
  }

  // ---------- ۱) رسیدن به TP یا SL ----------
  if (reachedTp) {
    advices.push({
      type: 'target-hit', severity: 'good',
      title: 'به حد سود (TP) رسید 🎯',
      detail: `قیمت ${round2(price)} به TP شما (${round2(t.tp)}) رسیده است. اگر بروکر به‌صورت خودکار نبسته، معامله را ببندید و سود را ثبت کنید.`,
    })
  }
  if (reachedSl) {
    advices.push({
      type: 'target-hit', severity: 'critical',
      title: 'به حد ضرر (SL) رسید',
      detail: `قیمت ${round2(price)} به SL شما (${round2(t.sl)}) رسیده است. معمولاً بروکر خودکار می‌بندد؛ در غیر این‌صورت برای کنترل ریسک ببندید.`,
    })
  }

  // ---------- ۲) بریک‌ایون: وقتی به ~۱R سود رسیدیم، SL را به ورود ببر ----------
  const slAtEntry = Math.abs(t.sl - t.entry) < 0.05
  if (!reachedTp && !reachedSl && pnlR >= 1.0 && !slAtEntry && !isSlBeyondEntry(t)) {
    advices.push({
      type: 'sl', severity: 'good',
      title: 'حالا معامله را بی‌ریسک کن (بریک‌ایون)',
      detail: `به ${pnlR}R سود رسیده‌ای. پیشنهاد: SL را به قیمت ورود (${round2(t.entry)}) منتقل کن تا معامله بدون‌ریسک شود.`,
      suggest: { field: 'sl', value: round2(t.entry) },
    })
  }

  // ---------- ۳) تریلینگ استاپ با ATR (وقتی سود >1.5R شد) ----------
  if (!reachedTp && !reachedSl && pnlR >= 1.5) {
    const trail = isLong ? round2(price - 1.5 * atr) : round2(price + 1.5 * atr)
    const better = isLong ? trail > t.sl : trail < t.sl
    if (better) {
      advices.push({
        type: 'sl', severity: 'good',
        title: 'حد ضرر را دنبال کن (Trailing Stop)',
        detail: `سود ${pnlR}R شده. SL را به ${trail} (≈۱.۵×ATR پشت قیمت) بکش تا بخش بیشتری از سود قفل شود.`,
        suggest: { field: 'sl', value: trail },
      })
    }
  }

  // ==========================================================================
  // ۳الف) مدیریتِ SHORT-MA-Confluence «بگذار بردها بدوند» (بازطراحیِ s118)
  // --------------------------------------------------------------------------
  // کشفِ MFE (s117): منطقِ قدیمی (BE۸/trail۸/۱۲کندل، SL۴۰pip) بردهای بزرگِ نزولی را
  // زودهنگام قطع می‌کرد؛ میانگین فقط +۴.۸pip می‌گرفت درحالی‌که MFE=۶۹.۳pip در دسترس بود.
  // منطقِ رکورد (s118، سهمِ SHORT +$34,542):
  //   • SL ثابت ۷۰pip (~۷$).
  //   • پس از ~۶pip (۰.۶$) سود  → بریک‌ایون.
  //   • سپس trailing ۶pip، اما **اجازه بده معامله تا ۴۸ کندل بدود** (نه بستنِ زودهنگام).
  //   • تنها وقتی می‌بندیم که trailing بخورد یا حداکثرِ نگه‌داری (۴۸ کندل) برسد.
  // این «بگذار بردها بدوند» کلیدِ افزایشِ رکورد از +۸۸٬۹۵۵$ به +۹۵٬۶۴۵$ بود.
  // ==========================================================================
  const isGoldPrice = price >= 100
  // SLِ رکوردِ s118 = ۷۰pip = ۷$؛ بازهٔ تشخیص را حولِ آن می‌گیریم (۵$..۹$).
  const isMaShort = !isLong && isGoldPrice && riskDist >= 5.0 && riskDist <= 9.0
  if (isMaShort && !reachedTp && !reachedSl) {
    const profitDollars = rawMove            // برای short: entry - price
    const BE_TRIG = 0.6                       // ۶pip سود → بریک‌ایون
    const TRAIL = 0.6                         // trailing ۶pip
    const MAX_HOLD_BARS = 48                  // «بگذار بردها بدوند» تا ۴۸ کندل
    if (profitDollars >= BE_TRIG && !isSlBeyondEntry(t) && Math.abs(t.sl - t.entry) >= 0.05) {
      advices.push({
        type: 'sl', severity: 'good',
        title: '🟢 SHORT (بگذار بردها بدوند): بی‌ریسک کن (بریک‌ایون)',
        detail: `به ${round2(profitDollars)}$ (~${Math.round(profitDollars * 10)}pip) سود رسیدی. ` +
          `SL را به قیمتِ ورود (${round2(t.entry)}) ببر تا معامله بدون‌ریسک شود؛ ولی **معامله را نبند** — ` +
          `طبقِ کشفِ MFE (s117) بردهای بزرگِ نزولی زودهنگام قطع می‌شدند. بگذار حرکت ادامه یابد.`,
        suggest: { field: 'sl', value: round2(t.entry) },
      })
    }
    if (profitDollars >= BE_TRIG + TRAIL) {
      const trail = round2(price + TRAIL)
      if (trail < t.sl) {
        advices.push({
          type: 'sl', severity: 'good',
          title: '🟢 SHORT: trailingِ ۶pip — بگذار برد بدود',
          detail: `شتابِ نزولی ادامه دارد. SL را به ${trail} (۶pip پشتِ قیمت) بکش و همین کار را تکرار کن. ` +
            `تا وقتی قیمت پایین می‌رود، اجازه بده معامله ادامه یابد (تا ۴۸ کندل)؛ فقط با برخوردِ trailing خارج شو. ` +
            `این «اجازه‌دادن به بردها» کلیدِ رکوردِ +۹۵٬۶۴۵$ است — دیگر سودِ کوچکِ زودهنگام نمی‌گیریم.`,
          suggest: { field: 'sl', value: trail },
        })
      }
    }
    // تنها محرکِ بستن: رسیدن به حداکثرِ نگه‌داری (۴۸ کندل). شتابِ کند دیگر دلیلِ بستن نیست.
    if (typeof t.barsHeld === 'number' && t.barsHeld >= MAX_HOLD_BARS) {
      advices.push({
        type: 'close', severity: 'warning',
        title: '⏱ SHORT: به حداکثرِ نگه‌داری (۴۸ کندل) رسید — ببند',
        detail: `این معامله ${t.barsHeld} کندل باز بوده و به سقفِ نگه‌داریِ منطقِ رکورد (۴۸ کندل) رسیده است. ` +
          `طبقِ s118 اینجا معامله را می‌بندیم تا سرمایه آزاد شود؛ سودِ فعلی ${round2(profitDollars)}$.`,
      })
    }
  }

  // ---------- ۴) معکوس‌شدن روند/مومنتوم برخلاف معامله ----------
  // نکتهٔ طراحی (User Note): توصیه‌های مبتنی بر خطوطِ حمایت/مقاومت حذف شدند.
  // استراتژی‌های واقعیِ این پروژه (S67, Squeeze, Overnight Drift, ...) هیچ‌کدام
  // از S/R استفاده نمی‌کنند؛ نمایشِ آن‌ها فقط اطلاعاتِ نامرتبط و استرس‌زا بود.
  // مدیریتِ معامله اکنون فقط بر پایهٔ سیگنال‌های واقعیِ همان استراتژی است:
  // روند/مومنتوم، سود/زیانِ R، تریلِ SL و سقفِ نگه‌داری.
  const trendAgainst = (isLong && a.trend === 'down') || (!isLong && a.trend === 'up')
  const macdAgainst = (isLong && a.macdHist < 0) || (!isLong && a.macdHist > 0)
  if (trendAgainst) {
    // شدت: در سود → هشدار (سود را حفظ کن)؛ در ضررِ واقعی → بحرانی (بستن را جدی بگیر)؛
    // در ناحیهٔ خنثی (تازه/نزدیکِ ورود) → فقط اطلاع‌رسانی، نه ترساندن.
    advices.push({
      type: 'reversal',
      severity: inProfit ? 'warning' : (inRealLoss ? 'critical' : 'info'),
      title: 'روند کلی برخلاف جهتِ معامله شد',
      detail: `روند کلی بازار اکنون ${a.trend === 'up' ? 'صعودی' : 'نزولی'} است که مخالف معاملهٔ ${isLong ? 'خرید' : 'فروش'} توست. ` +
        (inProfit
          ? 'در سود هستی — SL را جلو بکش تا سود قفل شود.'
          : inRealLoss
            ? 'و در ضرر هستی؛ اگر با SLِ خودت هم‌خوان نیست، بستن را جدی بگیر.'
            : 'اما هنوز نزدیکِ نقطهٔ ورودی و ضررِ معناداری نداری — چند کندل واکنشِ قیمت را ببین، عجله برای بستن نکن.'),
    })
  } else if (macdAgainst && inRealLoss) {
    advices.push({
      type: 'momentum', severity: 'info',
      title: 'مومنتوم کوتاه‌مدت مخالف است',
      detail: `هیستوگرام MACD برخلاف جهت معامله است (${round2(a.macdHist)}). لزوماً بد نیست اما نشانهٔ ضعف کوتاه‌مدت؛ صبورانه اما با SL مشخص مدیریت کن.`,
    })
  }

  // ---------- ۶) هم‌سو/مخالف بودن سیگنال مدل با معامله ----------
  // نکته: مدل ONNX فقط برای جهت LONG آموزش دیده و آستانهٔ ورودش THR=۶۸٪ است
  //   (model_meta.txt / signal_client.ts). پس معیار قضاوت باید همان ۶۸٪ باشد،
  //   نه ۶۰٪ یا ۴۵٪. مقادیر بالای ۶۸٪ = احتمال «بالا»، زیر آن = «کمتر از آستانه».
  //   همچنین از a.regimeOk سرور استفاده نمی‌کنیم چون رژیمِ آن با رژیمِ خودِ مدل
  //   (که در مرورگر با EMA50/200 لنگرشده محاسبه می‌شود) فرق دارد و باعث می‌شد
  //   این باکس همیشه (به‌غلط) به‌عنوان «ضعف» ظاهر شود.
  const MODEL_THR = 68 // آستانهٔ ورود مدل (٪)
  if (isLong && typeof modelProbPct === 'number' && isFinite(modelProbPct)) {
    if (modelProbPct >= MODEL_THR) {
      advices.push({
        type: 'info', severity: 'good',
        title: 'مدل هم‌سو با معاملهٔ توست',
        detail: `مدل ربات احتمال ${round2(modelProbPct)}٪ (بالای آستانهٔ ورود ${MODEL_THR}٪) برای ادامهٔ حرکت صعودی می‌دهد — هم‌سو با معاملهٔ خرید تو. اجازه بده معامله نفس بکشد (let it run) و SL را ترِیل کن.`,
      })
    } else if (modelProbPct < 50) {
      advices.push({
        type: 'info', severity: 'warning',
        title: 'مدل، ضعف در ادامهٔ صعود می‌بیند',
        detail: `مدل احتمال ${round2(modelProbPct)}٪ (زیر ۵۰٪) برای ادامهٔ صعود می‌دهد؛ یعنی تمایل بیشتر به توقف/برگشت است. برای معاملهٔ خرید، محافظه‌کارانه‌تر مدیریت کن.`,
      })
    }
    // بازهٔ ۵۰٪..۶۸٪ = خنثی؛ نه هشدار می‌دهیم نه تأیید (از باکس گمراه‌کننده پرهیز می‌کنیم).
  }

  // ---------- جمع‌بندی: اقدام کلی پیشنهادی ----------
  // مهم (رفع باگ تناقض): جمع‌بندی باید با هشدارهای فعال هم‌خوان باشد. اگر باکس‌های
  // هشدار (warning/critical) وجود دارند، نباید بگوییم «شرایط پایدار است».
  const hasCritical = advices.some(x => x.severity === 'critical')
  const hasWarning = advices.some(x => x.severity === 'warning')

  let overallAction: TradeStatus['overallAction'] = 'hold'
  let overallNote = 'شرایط پایدار است؛ طبق برنامه با TP/SL فعلی نگه‌دار.'
  if (reachedTp) { overallAction = 'close'; overallNote = 'به هدف رسیدی — سود را ثبت کن.' }
  else if (reachedSl) { overallAction = 'close'; overallNote = 'به حد ضرر رسیدی — طبق پلن خارج شو.' }
  // «بستن» فقط وقتی روند معکوس شده و در ضررِ واقعی (خارج از ناحیهٔ اسپرد) هستیم.
  else if (trendAgainst && inRealLoss) { overallAction = 'close'; overallNote = 'روند برخلاف تو شده و در ضررِ واقعی هستی — بستن را جدی بگیر.' }
  else if (pnlR >= 1.5) { overallAction = 'let-run'; overallNote = 'در سود خوبی هستی — SL را ترِیل کن و بگذار سود رشد کند.' }
  else if (pnlR >= 1.0) { overallAction = 'move-sl'; overallNote = 'SL را به بریک‌ایون ببر تا معامله بی‌ریسک شود.' }
  else if (trendAgainst && inProfit) { overallAction = 'tighten'; overallNote = 'روند ضعیف شده ولی در سودی — SL را جلو بکش تا سود حفظ شود.' }
  // اگر هیچ اقدام قوی‌ای فعال نشد اما هشدار داریم، جمع‌بندی را با هشدارها هم‌سو کن
  // تا با باکس‌های زیرین تناقض نداشته باشد.
  else if (hasCritical) { overallAction = 'tighten'; overallNote = 'هشدار مهم فعال است (پایین را بخوان) — مراقب باش و SL را محکم‌تر کن.' }
  else if (inRealLoss && trendAgainst) {
    overallAction = 'tighten'
    overallNote = 'در ضرری و روند مساعد نیست — SL را محکم‌تر کن یا طبقِ پلن آماده خروج باش.'
  }
  else if (hasWarning) {
    overallAction = 'hold'
    overallNote = 'یک نکتهٔ هشداری فعال است (پایین را بخوان)؛ با احتیاط و طبق پلن مدیریت کن.'
  }
  else if (!inProfit && !inRealLoss) {
    // ناحیهٔ خنثی (نزدیکِ ورود، بعد از دورهٔ تنفس): پیامِ آرامش‌بخش، نه ترس.
    overallAction = 'hold'
    overallNote = 'قیمت هنوز نزدیکِ نقطهٔ ورودِ توست (در محدودهٔ اسپرد/نویز) — این ضرر نیست؛ طبقِ پلن با TP/SLِ فعلی صبور بمان.'
  }

  return {
    side: t.side, price: round2(price), entry: round2(t.entry), tp: round2(t.tp), sl: round2(t.sl),
    inProfit, pnlUsd, pnlR, progressToTp,
    distToSlPct, distToTpPct,
    riskReward: `R:R اولیه ≈ 1:${round2(rewardDist / riskDist)}`,
    reachedTp, reachedSl,
    advices, overallAction, overallNote,
  }
}

// آیا SL از قبل فراتر از ورود (در سود) است؟ (بریک‌ایون یا تریل انجام شده)
function isSlBeyondEntry(t: OpenTrade): boolean {
  return t.side === 'long' ? t.sl >= t.entry : t.sl <= t.entry
}
