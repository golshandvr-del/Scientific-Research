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
  // حداقل فاصلهٔ منطقی TP از ورود تا معامله معنی‌دار بماند (نصف ATR)
  const minTpGap = 0.5 * atr
  if (isLong && res && distToTp > 0) {
    const dR = ((res.price - price) / price) * 100
    // پیشنهاد پایین‌آوردن TP فقط وقتی معتبر است که مقاومت هم زیر TP فعلی باشد و
    // هم به‌قدر کافی بالاتر از ورود (وگرنه TP پیشنهادی زیر ورود می‌افتد = ضرر تضمینی).
    const suggestedTp = round2(res.price - 0.1 * atr)
    const validTpSuggestion = res.price < t.tp && suggestedTp > t.entry + minTpGap
    if (dR > 0 && dR < nearPct && validTpSuggestion) {
      advices.push({
        type: 'level', severity: 'warning',
        title: 'مقاومت پیش از TP',
        detail: `یک مقاومت با ${res.touches} برخورد در ${round2(res.price)} (فاصله ${round2(dR)}٪) درست زیرِ TP توست. احتمال برگشت از این سطح هست؛ می‌توانی TP را کمی پایین‌تر از این مقاومت (${suggestedTp}) بگذاری تا مطمئن‌تر پر شود.`,
        suggest: { field: 'tp', value: suggestedTp },
      })
    } else if (dR >= 0 && dR < nearPct && res.price <= t.entry + minTpGap) {
      // مقاومت زیر (یا بسیار نزدیکِ) ورودِ خرید است → پایین‌آوردن TP بی‌معناست
      // (TP زیر ورود = ضرر). به‌جای پیشنهاد TPِ زیانده، هشدار خطر می‌دهیم.
      advices.push({
        type: 'level', severity: 'warning',
        title: 'مقاومت زیرِ قیمت ورود توست',
        detail: `یک مقاومت با ${res.touches} برخورد در ${round2(res.price)} حتی پایین‌تر از قیمت ورود تو (${round2(t.entry)}) قرار دارد. برای رسیدن به TP باید قیمت این مقاومت را بشکند. TP را پایین نیاور (زیر ورود می‌رود و ضرر می‌شود)؛ صبر کن سطح شکسته شود، یا اگر نشکست بخشی از حجم را ببند.`,
      })
    }
  }
  if (!isLong && sup && distToTp > 0) {
    const dS = ((price - sup.price) / price) * 100
    const suggestedTp = round2(sup.price + 0.1 * atr)
    const validTpSuggestion = sup.price > t.tp && suggestedTp < t.entry - minTpGap
    if (dS > 0 && dS < nearPct && validTpSuggestion) {
      advices.push({
        type: 'level', severity: 'warning',
        title: 'حمایت پیش از TP',
        detail: `یک حمایت با ${sup.touches} برخورد در ${round2(sup.price)} (فاصله ${round2(dS)}٪) درست بالای TP توست. احتمال برگشت صعودی از این سطح هست؛ می‌توانی TP را کمی بالاتر از این حمایت (${suggestedTp}) بگذاری.`,
        suggest: { field: 'tp', value: suggestedTp },
      })
    } else if (dS >= 0 && dS < nearPct && sup.price >= t.entry - minTpGap) {
      advices.push({
        type: 'level', severity: 'warning',
        title: 'حمایت بالای قیمت ورود توست',
        detail: `یک حمایت با ${sup.touches} برخورد در ${round2(sup.price)} حتی بالاتر از قیمت ورود تو (${round2(t.entry)}) قرار دارد. برای رسیدن به TP باید قیمت این حمایت را بشکند. TP را بالا نیاور (بالای ورود می‌رود و ضرر می‌شود)؛ صبر کن سطح شکسته شود، یا بخشی را ببند.`,
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
  const nearLevelWarn = advices.some(x => x.type === 'level' && x.severity === 'warning')

  let overallAction: TradeStatus['overallAction'] = 'hold'
  let overallNote = 'شرایط پایدار است؛ طبق برنامه با TP/SL فعلی نگه‌دار.'
  if (reachedTp) { overallAction = 'close'; overallNote = 'به هدف رسیدی — سود را ثبت کن.' }
  else if (reachedSl) { overallAction = 'close'; overallNote = 'به حد ضرر رسیدی — طبق پلن خارج شو.' }
  else if (trendAgainst && !inProfit) { overallAction = 'close'; overallNote = 'روند برخلاف تو و در ضرر هستی — بستن را جدی بگیر.' }
  else if (pnlR >= 1.5) { overallAction = 'let-run'; overallNote = 'در سود خوبی هستی — SL را ترِیل کن و بگذار سود رشد کند.' }
  else if (pnlR >= 1.0) { overallAction = 'move-sl'; overallNote = 'SL را به بریک‌ایون ببر تا معامله بی‌ریسک شود.' }
  else if (trendAgainst) { overallAction = 'tighten'; overallNote = 'روند ضعیف شده — SL را کمی محکم‌تر کن.' }
  // اگر هیچ اقدام قوی‌ای فعال نشد اما هشدار داریم، جمع‌بندی را با هشدارها هم‌سو کن
  // تا با باکس‌های زیرین تناقض نداشته باشد.
  else if (hasCritical) { overallAction = 'tighten'; overallNote = 'هشدار مهم فعال است (پایین را بخوان) — مراقب باش و SL را محکم‌تر کن.' }
  else if (nearLevelWarn && !inProfit) {
    overallAction = 'tighten'
    overallNote = 'قیمت به یک سطح کلیدی (حمایت/مقاومت) در وضعیت ضرر رسیده — تا شکسته‌شدن سطح، بی‌احتیاطی نکن و به بستن بخشی از حجم فکر کن.'
  }
  else if (nearLevelWarn) {
    overallAction = 'hold'
    overallNote = 'نزدیک یک سطح کلیدی هستی (پایین را بخوان)؛ همان‌جا واکنش قیمت را رصد کن و در صورت لزوم TP/SL را تنظیم کن.'
  }
  else if (hasWarning) {
    overallAction = 'hold'
    overallNote = 'یک نکتهٔ هشداری فعال است (پایین را بخوان)؛ با احتیاط و طبق پلن مدیریت کن.'
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
