// ============================================================================
// S374 — «دروازهٔ شکستِ Kennedy» — ماژولِ مستقلِ لایهٔ پذیرفته‌شدهٔ H4
// ----------------------------------------------------------------------------
// منبعِ کشف: Telegram-Resource/.../1101 Trading the Line Excerpt.pdf  (فصلِ ۲،
//   صفحاتِ ۱۳–۱۵ — Jeffrey Kennedy، تحلیلگرِ ارشدِ Elliott Wave International)
// پیش‌ثبت : results/S374_PREREG_kennedy_break_gate.md
// حکمِ نهایی: results/S374_KennedyBreakGate_XauEur_H4_rqs2-ACCEPTED.md
// یافتهٔ ساختاری: results/S374_FINDING_not_subset_but_delay.md
//
// ══════════════════════════════════════════════════════════════════════════
// تزِ محوری (نقلِ مستقیم، شکلِ ۲-۱۹)
// ══════════════════════════════════════════════════════════════════════════
//   «بعضی فکر می‌کنند **بسته‌شدن** بالای/زیرِ خطِ روند نشانهٔ شکست است. من ترجیح
//    می‌دهم حرکتِ قیمت را بر مبنای **high یا low** ببینم... تا وقتی high کندل
//    زیرِ خطِ روند نباشد، شکستِ واقعیِ خطِ روندِ قبلی رخ نداده است.»
//
//   | جهت          | تعریفِ رایج (ردشده) | تعریفِ Kennedy |
//   |--------------|---------------------|----------------|
//   | شکستِ نزولی  | close < line        | **high < line**|
//   | شکستِ صعودی  | close > line        | **low  > line**|
//
// ⚠️ یافتهٔ ساختاریِ حیاتی (که ماهیتِ این لایه را بازتعریف کرد):
//   این **فیلترِ ردِ سیگنال نیست، قاعدهٔ زمان‌بندیِ ورود است.** اثباتِ زیرمجموعه‌بودن
//   در سطحِ بولیِ خام برقرار است، ولی پس از قاعدهٔ «اولین شکستِ هر کانال» نقض
//   می‌شود: شرطِ close زودتر در همان کانال شلیک می‌کند، پس بازوی close کندلِ
//   زودتر و بازوی Kennedy کندلِ دیرتر را می‌گیرد (تأخیرِ اندازه‌گیری‌شده ۱ تا ۷
//   کندل). هر دو در بازوی خودشان «اولین»‌اند ولی کندل‌های متفاوتی هستند.
//   ⇒ همپوشانی: فضای کانال ≈ کامل · فضای کندل ≈ صفر.
//
// ══════════════════════════════════════════════════════════════════════════
// نتیجهٔ بک‌تستِ رویدادمحور — چرا فقط H4 اینجاست
// ══════════════════════════════════════════════════════════════════════════
//   قانونِ MTF: هر ۵ تایم‌فریمِ مشترک آزموده شد. **۴ کارت رد** (همه روی بندِ
//   اقتصاد: e_pip < هزینه) و **فقط H4 پذیرفته** شد:
//
//     z = +4.100  در برابرِ سدِ 2.570 (N=112 آزمون، پیش از اجرا تثبیت‌شده)   ✅
//     n = 1,062   در برابرِ n_needed = 417                                  ✅
//     طلا e_pip = 11.67 → 32.97  (c=3.3) · یورو 1.57 → 6.44 (c=1.6)         ✅
//     تکرارپذیری: h1 = +0.0933 · h2 = +0.1696  (هر دو مثبت)                 ✅
//
//   ⭐ بندِ تکرارپذیری همان بندی است که لایهٔ پایه (S373) را کشته بود
//      (h1=−0.0134 ، h2=+0.0537 — تغییرِ علامت). دروازهٔ Kennedy آن را حل کرد.
//
//   📉 روندِ یکنواختِ کاملِ اثر روی تایم‌فریم (ρ_Spearman = +1.000، شانس 1/120):
//        M5: −0.0208 → M15: −0.0082 → M30: +0.0085 → H1: +0.0688 → H4: +0.1399
//      ⇒ **قانونِ عمومی:** علامتِ اثرِ این دروازه تابعِ تایم‌فریم است. هرچه
//        تایم‌فریم بالاتر، نسبتِ نویزِ درون‌کندلی به سیگنال کمتر ⇒ شرطِ «کلِ کندل
//        باید عبور کند» اطلاعاتِ بیشتری حمل می‌کند. در M5 دامنهٔ کندل عمدتاً نویزِ
//        ریزساختاری است و شرط **زیان‌بار** می‌شود.
//      ⛔ به همین دلیل این ماژول **فقط روی H4** فعال است و روی M5/M15/M30/H1
//        عمداً غیرفعال — نه از روی غفلت، بلکه طبقِ اندازه‌گیری.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠️ محدودیتِ اجباریِ استقرار (صادقانه، بدونِ پنهان‌کاری)
// ══════════════════════════════════════════════════════════════════════════
//   اعضای خانواده مستقل نیستند — همان کانال‌ها را با براکت‌های مختلف دوباره
//   معامله می‌کنند. واحدِ استقلالِ درست **کانال** است نه معامله. روی طلای H4 لایه
//   روی **۴۳ کندلِ مجزا در ۱۰.۸ سال** استوار است ⇒ ~۴ رویدادِ مستقل در سال.
//
//   بوت‌استرپِ خوشه‌ای (بازنمونه‌گیری از کانال‌ها، نه معاملات):
//     پایه (close):  CI۹۵٪ = [−0.0794, +0.1133]  ⇒ P(≤0)=36.2٪  ← شاملِ صفر
//     Kennedy     :  CI۹۵٪ = [+0.0014, +0.2544]  ⇒ P(≤0)= 2.5٪  ← صفر را رد
//
//   ⇒ لبه واقعی است ولی **حاشیه نازک** ⇒ رتبهٔ «محافظه‌کارانه» + برچسبِ
//     «کم‌بسامد» + اجبارِ خویشتن‌داری در حجم. این در متنِ کارت به کاربر گفته
//     می‌شود، چون اطلاعِ لازم برای تصمیم است (نه اطلاعِ اضافه).
//
// 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» (XAUUSD + EURUSD).
//    این ماژول کاملاً مستقل است ⇒ افزودن/تغییرش هیچ لایهٔ دیگری را دست نمی‌زند.
// ============================================================================

// ---------------------------------------------------------------------------
// پیکربندیِ قفل‌شدهٔ لایه — عیناً از خانوادهٔ پیش‌ثبت‌شدهٔ پایتون (تغییرپذیر نیست).
//   FAM_K = (2,3,5) · FAM_M = (0.618,1.0) · FAM_S = (0.5,0.786)
//   ⇒ همه غیررند/فیبوناچی — هیچ عددِ رندی (۵۰/۱۰۰/۲۰۰) در این لایه نیست.
// ---------------------------------------------------------------------------
export interface KennedyConfig {
  id: string
  tfFa: string
  /** بازوی pivot (نیم‌پنجره) — عضوِ خانواده */
  k: number
  /** TP = m × ارتفاعِ کانال (measured-move) */
  m: number
  /** SL = s × ارتفاعِ کانال */
  s: number
  /** منطقِ «پله‌های کوچک‌شونده» — طلا false ، یورو true (قفلِ ابزارمحور) */
  gate: boolean
  /** حداکثر نگهداری (کندل) — از میانهٔ مدتِ کانالِ همان کارت */
  maxHoldBars: number
  /** میانگینِ R اندازه‌گیری‌شدهٔ همین عضو در بک‌تست (مستندسازیِ داخلی) */
  meanR: number
  /** تعدادِ معاملهٔ همین عضو در بک‌تست */
  nTrades: number
}

/**
 * اعضای **پذیرفته‌شدهٔ** H4 — نمایندهٔ هر ارز، انتخاب‌شده بر پایهٔ
 * `m = 1.0` (همان measured-moveِ متن) و `s = 0.5`، که در هر دو ارز
 * قوی‌ترین عضوِ خانواده بود. این انتخاب **پس از** پذیرشِ کلِ خانواده انجام شد
 * و معیارِ پذیرش را عوض نمی‌کند (خانواده به‌عنوان یک کل پاس شد).
 */
export const KENNEDY_CFG: Record<string, KennedyConfig> = {
  'XAUUSD-H4': {
    id: 'XAUUSD-H4', tfFa: 'H4 (چهارساعته)',
    k: 3, m: 1.0, s: 0.5, gate: false,
    maxHoldBars: 59, meanR: 0.6082, nTrades: 20,
  },
  'EURUSD-H4': {
    id: 'EURUSD-H4', tfFa: 'H4 (چهارساعته)',
    k: 2, m: 1.0, s: 0.5, gate: true,
    maxHoldBars: 50, meanR: 0.2362, nTrades: 88,
  },
}

/** افقِ زندگیِ زمینهٔ کانال — ثابتِ ساختاری، سوئپ نشد (عیناً از S366). */
const HORIZON_MULT = 2.0

export type KennedyState = 'ENTRY' | 'APPROACHING' | 'NEUTRAL'

export interface KennedyResult {
  state: KennedyState
  side: 'LONG' | 'SHORT' | null
  hasChannel: boolean
  isBear: boolean
  /** خطِ پایینِ کانال در آخرین کندلِ بسته‌شده */
  lowerLine: number
  /** خطِ بالای کانال (موازی) */
  upperLine: number
  /** ضخامتِ عمودیِ کانال (واحدِ قیمت) */
  chanHeight: number
  /** پله‌های کوچک‌شونده؟ */
  shrink: boolean
  /** ⭐ آیا شرطِ Kennedy برقرار است؟ (high<lower یا low>upper) */
  kennedyBreak: boolean
  /** آیا شرطِ رایجِ close برقرار است؟ (برای شفاف‌سازیِ «چرا هنوز وارد نشدیم») */
  closeBreak: boolean
  /** فاصلهٔ باقی‌مانده تا برقراریِ شرطِ Kennedy (واحدِ قیمت؛ ۰ = برقرار) */
  distToKennedy: number
  slDist: number
  tpDist: number
  /** آیا قیدِ ریزساختاری (TP ≥ ۲×هزینه) پاس شد؟ */
  feasible: boolean
  reason: string
}

const EMPTY: KennedyResult = {
  state: 'NEUTRAL', side: null, hasChannel: false, isBear: false,
  lowerLine: NaN, upperLine: NaN, chanHeight: NaN, shrink: false,
  kennedyBreak: false, closeBreak: false, distToKennedy: NaN,
  slDist: NaN, tpDist: NaN, feasible: false,
  reason: 'زمینهٔ کانالِ معتبری روی این افق شکل نگرفته است.',
}

// ---------------------------------------------------------------------------
// pivot_flags — بازتولیدِ دقیقِ نسخهٔ پایتون:
//   ph[i] = high[i] > max(high[i-k..i-1])  AND  high[i] >= max(high[i+1..i+k])
//   pl[i] = low[i]  < min(low[i-k..i-1])   AND  low[i]  <= min(low[i+1..i+k])
// نامتقارنیِ `>` و `>=` عمدی است و از پایتون کپی شده (بندِ برابری).
// ---------------------------------------------------------------------------
export function pivotFlags(high: number[], low: number[], k: number): { ph: boolean[]; pl: boolean[] } {
  const n = high.length
  const ph = new Array<boolean>(n).fill(false)
  const pl = new Array<boolean>(n).fill(false)
  for (let i = k; i < n - k; i++) {
    let lmax = -Infinity, rmax = -Infinity, lmin = Infinity, rmin = Infinity
    for (let j = 1; j <= k; j++) {
      lmax = Math.max(lmax, high[i - j]); rmax = Math.max(rmax, high[i + j])
      lmin = Math.min(lmin, low[i - j]);  rmin = Math.min(rmin, low[i + j])
    }
    ph[i] = high[i] > lmax && high[i] >= rmax
    pl[i] = low[i] < lmin && low[i] <= rmin
  }
  return { ph, pl }
}

interface Chan {
  bear: boolean
  a: number       // مقدارِ خطِ پایین در t_ref
  b: number       // شیب
  tRef: number
  h: number       // ضخامتِ عمودی
  shrink: boolean
  t0: number
  tLast: number
}

type Piv = { typ: 'H' | 'L'; idx: number; px: number }

/**
 * ساختِ کانال از ۵ پیوتِ آخر (بازتولیدِ `_build_channel` پایتون).
 *   خرسی: [L,H,L,H,L]  با L1>L2>L3 ، H1>H2 ، H2>L1 (قیدِ همپوشانیِ متن)
 *   گاوی: [H,L,H,L,H]  با H1<H2<H3 ، L1<L2 ، L2<H1
 */
function buildChannel(piv: Piv[]): Chan | null {
  if (piv.length < 5) return null
  const last5 = piv.slice(-5)
  const tps = last5.map(p => p.typ).join('')
  const ix = last5.map(p => p.idx)
  const px = last5.map(p => p.px)

  if (tps === 'LHLHL') {
    const [L1, H1, L2, H2, L3] = px
    const [iL1, , iL2, iH2, iL3] = ix
    if (!(L1 > L2 && L2 > L3 && H1 > H2 && H2 > L1)) return null
    if (iL3 <= iL2) return null
    const b = (L3 - L2) / (iL3 - iL2)
    const hgt = H2 - (L3 + b * (iH2 - iL3))
    if (!(hgt > 0)) return null
    return { bear: true, a: L3, b, tRef: iL3, h: hgt, shrink: (L2 - L3) < (L1 - L2), t0: iL1, tLast: iL3 }
  }

  if (tps === 'HLHLH') {
    const [H1, L1, H2, L2, H3] = px
    const [iH1, , iH2, iL2, iH3] = ix
    if (!(H1 < H2 && H2 < H3 && L1 < L2 && L2 < H1)) return null
    if (iH3 <= iH2) return null
    const b = (H3 - H2) / (iH3 - iH2)
    const hgt = (H3 + b * (iL2 - iH3)) - L2
    if (!(hgt > 0)) return null
    return { bear: false, a: H3, b, tRef: iH3, h: hgt, shrink: (H3 - H2) < (H2 - H1), t0: iH1, tLast: iH3 }
  }

  return null
}

/**
 * زمینهٔ کانالِ زندهٔ آخرین کندلِ بسته‌شده.
 * پیوتِ بارِ i فقط در بارِ i+k **تأییدشده** تلقی می‌شود ⇒ بدونِ نشتِ آینده
 * (عیناً همان `ev = (i+k, i, …)` پایتون).
 */
function liveChannel(high: number[], low: number[], k: number, t: number): Chan | null {
  const { ph, pl } = pivotFlags(high, low, k)
  const ev: Array<{ conf: number; idx: number; typ: 'H' | 'L'; px: number }> = []
  for (let i = 0; i < high.length; i++) {
    if (ph[i]) ev.push({ conf: i + k, idx: i, typ: 'H', px: high[i] })
    if (pl[i]) ev.push({ conf: i + k, idx: i, typ: 'L', px: low[i] })
  }
  ev.sort((a, b) => (a.conf - b.conf) || (a.idx - b.idx))

  const piv: Piv[] = []
  let cur: Chan | null = null
  let ptr = 0

  for (let bar = 0; bar <= t; bar++) {
    let changed = false
    while (ptr < ev.length && ev[ptr].conf <= bar) {
      const e = ev[ptr++]
      const tail = piv[piv.length - 1]
      if (tail && tail.typ === e.typ) {
        // پیوتِ هم‌نوعِ شدیدتر ⇒ جایگزینی (zigzag)
        if ((e.typ === 'H' && e.px > tail.px) || (e.typ === 'L' && e.px < tail.px)) {
          piv[piv.length - 1] = { typ: e.typ, idx: e.idx, px: e.px }
          changed = true
        }
      } else {
        piv.push({ typ: e.typ, idx: e.idx, px: e.px })
        changed = true
        if (piv.length > 8) piv.shift()
      }
    }
    if (changed) {
      const nw = buildChannel(piv)
      // مقایسهٔ ساختاری (معادلِ `new != cur` پایتون)
      if (JSON.stringify(nw) !== JSON.stringify(cur)) cur = nw
    }
  }

  if (cur === null) return null
  // افقِ زندگیِ زمینه: خطوط تا ابد برون‌یابی نمی‌شوند
  if (t > cur.tLast + HORIZON_MULT * Math.max(1, cur.tLast - cur.t0)) return null
  return cur
}

// ---------------------------------------------------------------------------
// computeKennedy — موتورِ خالصِ لایه. ارزیابی روی آخرین کندلِ بسته‌شده (t=n-1).
//   ورودِ واقعی next-open ⇒ high/low کندلِ سیگنال **تاریخی** است، نه آینده.
//   (این همان دلیلی است که بازرسیِ نشتِ آینده منفی شد.)
// ---------------------------------------------------------------------------
export function computeKennedy(
  open: number[], high: number[], low: number[], close: number[],
  cfg: KennedyConfig, pip: number, costPip: number,
): KennedyResult {
  const n = close.length
  if (n < 4 * cfg.k + 12) return { ...EMPTY, reason: 'دادهٔ کافی برای ساختِ کانال روی این افق موجود نیست.' }

  const t = n - 1
  const ch = liveChannel(high, low, cfg.k, t)
  if (ch === null) return EMPTY

  const lower = ch.a + ch.b * (t - ch.tRef)
  const upper = lower + ch.h
  const shrink = cfg.gate ? ch.shrink : false

  // ⭐ دروازهٔ Kennedy در برابرِ تعریفِ رایج
  const kBelow = high[t] < lower     // شکستِ نزولیِ مشروع
  const kAbove = low[t] > upper      // شکستِ صعودیِ مشروع
  const cBelow = close[t] < lower    // تعریفِ رایج (ردشده توسطِ Kennedy)
  const cAbove = close[t] > upper

  // منطقِ جهت — عیناً از S366/S374:
  //   کانالِ خرسی: هم‌جهت=SHORT(شکستِ پایین) · برگشتی(shrink)=LONG(شکستِ بالا)
  //   کانالِ گاوی: هم‌جهت=LONG(شکستِ بالا)   · برگشتی(shrink)=SHORT(شکستِ پایین)
  const shortK = (ch.bear && !shrink && kBelow) || (!ch.bear && shrink && kBelow)
  const longK  = (!ch.bear && !shrink && kAbove) || (ch.bear && shrink && kAbove)
  const shortC = (ch.bear && !shrink && cBelow) || (!ch.bear && shrink && cBelow)
  const longC  = (!ch.bear && !shrink && cAbove) || (ch.bear && shrink && cAbove)

  const kennedyBreak = shortK || longK
  const closeBreak = shortC || longC

  const slDist = cfg.s * ch.h
  const tpDist = cfg.m * ch.h
  const feasible = (tpDist / pip) >= 2.0 * costPip && (slDist / pip) >= costPip

  // فاصلهٔ باقی‌مانده تا برقراریِ شرطِ Kennedy (برای حالتِ «نزدیک‌شدن»)
  let distToKennedy = NaN
  const wantDown = (ch.bear && !shrink) || (!ch.bear && shrink)
  if (wantDown) distToKennedy = Math.max(0, high[t] - lower)
  else distToKennedy = Math.max(0, upper - low[t])

  const side: 'LONG' | 'SHORT' | null = longK ? 'LONG' : shortK ? 'SHORT' : null

  if (kennedyBreak && feasible) {
    return {
      state: 'ENTRY', side, hasChannel: true, isBear: ch.bear,
      lowerLine: lower, upperLine: upper, chanHeight: ch.h, shrink,
      kennedyBreak: true, closeBreak, distToKennedy: 0,
      slDist, tpDist, feasible,
      reason: side === 'SHORT'
        ? `شکستِ مشروعِ نزولی: کلِ کندل زیرِ خطِ پایینِ کانال بسته شد (high=${high[t].toFixed(2)} < line=${lower.toFixed(2)}).`
        : `شکستِ مشروعِ صعودی: کلِ کندل بالای خطِ بالای کانال بسته شد (low=${low[t].toFixed(2)} > line=${upper.toFixed(2)}).`,
    }
  }

  // ⭐ حالتِ «نزدیک‌شدن» — دقیقاً همان وضعیتی که Kennedy آموزش می‌دهد:
  //   close عبور کرده ولی کلِ کندل نه ⇒ «شکستِ واقعی هنوز رخ نداده، صبر کن».
  if (closeBreak && !kennedyBreak) {
    return {
      state: 'APPROACHING', side: shortC ? 'SHORT' : 'LONG',
      hasChannel: true, isBear: ch.bear,
      lowerLine: lower, upperLine: upper, chanHeight: ch.h, shrink,
      kennedyBreak: false, closeBreak: true, distToKennedy,
      slDist, tpDist, feasible,
      reason: wantDown
        ? `قیمت زیرِ خطِ کانال بسته شد ولی سایهٔ بالا هنوز داخلِ کانال است (high=${high[t].toFixed(2)} در برابرِ خط=${lower.toFixed(2)}). طبقِ قاعدهٔ Kennedy این شکستِ واقعی نیست؛ باید منتظر کندلی باشیم که **کلِ دامنه‌اش** زیرِ خط باشد.`
        : `قیمت بالای خطِ کانال بسته شد ولی سایهٔ پایین هنوز داخلِ کانال است (low=${low[t].toFixed(2)} در برابرِ خط=${upper.toFixed(2)}). طبقِ قاعدهٔ Kennedy باید منتظر کندلی باشیم که **کلِ دامنه‌اش** بالای خط باشد.`,
    }
  }

  if (kennedyBreak && !feasible) {
    return {
      ...EMPTY, hasChannel: true, isBear: ch.bear,
      lowerLine: lower, upperLine: upper, chanHeight: ch.h, shrink,
      kennedyBreak: true, closeBreak, distToKennedy: 0, slDist, tpDist, feasible: false,
      reason: `شکستِ مشروع رخ داد ولی کانال آن‌قدر کم‌ارتفاع است که هدفِ اندازه‌گیری‌شده هزینهٔ رفت‌وبرگشت را پوشش نمی‌دهد (قیدِ ریزساختاری) ⇒ ورود نمی‌کنیم.`,
    }
  }

  return {
    state: 'NEUTRAL', side: null, hasChannel: true, isBear: ch.bear,
    lowerLine: lower, upperLine: upper, chanHeight: ch.h, shrink,
    kennedyBreak: false, closeBreak: false, distToKennedy,
    slDist, tpDist, feasible,
    reason: `کانالِ ${ch.bear ? 'نزولی' : 'صعودی'} زنده است و قیمت هنوز **داخلِ** آن قرار دارد `
      + `(خطِ پایین=${lower.toFixed(2)} · خطِ بالا=${upper.toFixed(2)}). `
      + `تا وقتی کلِ دامنهٔ یک کندل از یکی از دو خط عبور نکند، شکستِ مشروعی وجود ندارد.`,
  }
}
