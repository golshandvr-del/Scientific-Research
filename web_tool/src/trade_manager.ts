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
  const inProfit = rawMove > 0

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

  // ---------- ۴) نزدیکی به مقاومت/حمایت (رفتار نمودار با S/R) ----------
  const res = a.resistance
  const sup = a.support
  const nearPct = 0.25 // نزدیک اگر < ~۰.۲۵٪
  if (isLong && res && distToTp > 0) {
    const dR = ((res.price - price) / price) * 100
    if (dR > 0 && dR < nearPct && res.price < t.tp) {
      advices.push({
        type: 'level', severity: 'warning',
        title: 'مقاومت پیش از TP',
        detail: `یک مقاومت با ${res.touches} برخورد در ${round2(res.price)} (فاصله ${round2(dR)}٪) درست زیرِ TP توست. احتمال برگشت از این سطح هست؛ می‌توانی TP را کمی پایین‌تر از این مقاومت (${round2(res.price - 0.1 * atr)}) بگذاری تا مطمئن‌تر پر شود.`,
        suggest: { field: 'tp', value: round2(res.price - 0.1 * atr) },
      })
    }
  }
  if (!isLong && sup && distToTp > 0) {
    const dS = ((price - sup.price) / price) * 100
    if (dS > 0 && dS < nearPct && sup.price > t.tp) {
      advices.push({
        type: 'level', severity: 'warning',
        title: 'حمایت پیش از TP',
        detail: `یک حمایت با ${sup.touches} برخورد در ${round2(sup.price)} (فاصله ${round2(dS)}٪) درست بالای TP توست. احتمال برگشت صعودی از این سطح هست؛ می‌توانی TP را کمی بالاتر از این حمایت (${round2(sup.price + 0.1 * atr)}) بگذاری.`,
        suggest: { field: 'tp', value: round2(sup.price + 0.1 * atr) },
      })
    }
  }
  // نزدیکی قیمت به سطحی که برخلاف معامله عمل می‌کند (خطر برگشت روی ضرر)
  if (isLong && res) {
    const dR = ((res.price - price) / price) * 100
    if (dR >= 0 && dR < nearPct && !inProfit) {
      advices.push({
        type: 'level', severity: 'warning',
        title: 'برخورد به مقاومت در ضرر',
        detail: `قیمت به مقاومت ${round2(res.price)} رسیده و معامله در سود نیست. اگر این مقاومت رد نشود احتمال برگشت به SL بالاست — مراقب باش یا بخشی را ببند.`,
      })
    }
  }
  if (!isLong && sup) {
    const dS = ((price - sup.price) / price) * 100
    if (dS >= 0 && dS < nearPct && !inProfit) {
      advices.push({
        type: 'level', severity: 'warning',
        title: 'برخورد به حمایت در ضرر',
        detail: `قیمت به حمایت ${round2(sup.price)} رسیده و معامله در سود نیست. اگر این حمایت نشکند احتمال برگشت به SL بالاست — مراقب باش یا بخشی را ببند.`,
      })
    }
  }

  // ---------- ۵) معکوس‌شدن روند/مومنتوم برخلاف معامله ----------
  const trendAgainst = (isLong && a.trend === 'down') || (!isLong && a.trend === 'up')
  const macdAgainst = (isLong && a.macdHist < 0) || (!isLong && a.macdHist > 0)
  if (trendAgainst) {
    advices.push({
      type: 'reversal', severity: inProfit ? 'warning' : 'critical',
      title: 'روند برخلاف معامله شد',
      detail: `روند کلی بازار اکنون ${a.trend === 'up' ? 'صعودی' : 'نزولی'} است که مخالف معاملهٔ ${isLong ? 'خرید' : 'فروش'} توست. ${inProfit ? 'سود موجود را با کشیدن SL محافظت کن.' : 'ریسک ادامهٔ ضرر بالاست؛ به بستن معامله فکر کن.'}`,
    })
  } else if (macdAgainst && !inProfit) {
    advices.push({
      type: 'momentum', severity: 'info',
      title: 'مومنتوم کوتاه‌مدت مخالف است',
      detail: `هیستوگرام MACD برخلاف جهت معامله است (${round2(a.macdHist)}). لزوماً بد نیست اما نشانهٔ ضعف کوتاه‌مدت؛ صبورانه اما با SL مشخص مدیریت کن.`,
    })
  }

  // ---------- ۶) هم‌سو/مخالف بودن سیگنال مدل با معامله ----------
  if (typeof modelProbPct === 'number' && isFinite(modelProbPct)) {
    if (isLong && a.regimeOk && modelProbPct >= 60) {
      advices.push({
        type: 'info', severity: 'good',
        title: 'مدل هم‌سو با معاملهٔ توست',
        detail: `مدل ربات احتمال ${round2(modelProbPct)}٪ برای ادامهٔ حرکت صعودی می‌دهد و رژیم صعودی برقرار است. اجازه بده معامله نفس بکشد (let it run) و SL را ترِیل کن.`,
      })
    } else if (isLong && (!a.regimeOk || modelProbPct < 45)) {
      advices.push({
        type: 'info', severity: 'warning',
        title: 'مدل، ضعف در ادامهٔ صعود می‌بیند',
        detail: `مدل احتمال پایین (${round2(modelProbPct)}٪) برای ادامهٔ صعود می‌دهد${a.regimeOk ? '' : ' و رژیم صعودی هم برقرار نیست'}. برای معاملهٔ خرید، محافظه‌کارانه‌تر مدیریت کن.`,
      })
    }
  }

  // ---------- جمع‌بندی: اقدام کلی پیشنهادی ----------
  let overallAction: TradeStatus['overallAction'] = 'hold'
  let overallNote = 'شرایط پایدار است؛ طبق برنامه با TP/SL فعلی نگه‌دار.'
  if (reachedTp) { overallAction = 'close'; overallNote = 'به هدف رسیدی — سود را ثبت کن.' }
  else if (reachedSl) { overallAction = 'close'; overallNote = 'به حد ضرر رسیدی — طبق پلن خارج شو.' }
  else if (trendAgainst && !inProfit) { overallAction = 'close'; overallNote = 'روند برخلاف تو و در ضرر هستی — بستن را جدی بگیر.' }
  else if (pnlR >= 1.5) { overallAction = 'let-run'; overallNote = 'در سود خوبی هستی — SL را ترِیل کن و بگذار سود رشد کند.' }
  else if (pnlR >= 1.0) { overallAction = 'move-sl'; overallNote = 'SL را به بریک‌ایون ببر تا معامله بی‌ریسک شود.' }
  else if (trendAgainst) { overallAction = 'tighten'; overallNote = 'روند ضعیف شده — SL را کمی محکم‌تر کن.' }

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
