// ============================================================================
// reversal_guard.ts — «نگهبانِ برگشتِ روند» برای بخشِ مدیریتِ معامله (User Note)
// ----------------------------------------------------------------------------
// ایدهٔ کاربر: وقتی کاربر در یک معاملهٔ LONG است و موتورِ سایت در پس‌زمینه شروع به
// تولیدِ سیگنالِ SHORT (جهتِ مخالف) می‌کند، سایت باید به کاربر کمک کند — اما کاربر
// خودش هشدار داد که «خطرناک است؛ نباید مدام باعثِ بستنِ معامله در ضرر شود».
//
// طراحیِ ضدِ ضرر (سه‌سطحیِ درجه‌بندی‌شده) — پاسخِ مستقیم به همان نگرانی:
//   • هیچ‌وقت «کورکورانه ببند» نمی‌گوییم.
//   • «برگشت» فقط وقتی معتبر است که موتور یک سیگنالِ جهتِ مخالفِ *واقعی* بدهد
//     (ENTRY = active، یا دستِ‌کم approaching)، نه یک اندیکاتورِ خامِ زودگذر.
//   • تثبیتِ زمانیِ برگشت در فرانت‌اند (مثلِ صفِ سیگنال) انجام می‌شود؛ این ماژول
//     فقط «شدتِ لحظه‌ای» را می‌سنجد و فرانت با پایداریِ چند-نمونه‌ای آن را قطعی می‌کند.
//
// سطوح:
//   none          → موتور هم‌سو یا خنثی است؛ چیزی نگو.
//   soft          → نشانهٔ اولیهٔ برگشت (approaching مخالف). فقط «مراقب باش».
//   defend-profit → برگشتِ فعال (ENTRY مخالف) و کاربر «در سود» است → SLِ سود را قفل
//                   کن (بی‌ریسک/تریلِ محکم). چون در سودی، ریسکِ بستن صفر است.
//   defend-close  → برگشتِ فعال (ENTRY مخالف) و کاربر «در ضررِ واقعی» است → به‌جای
//                   «فوراً ببند»، پیشنهادِ هوشمند: SL را به یک حدِ نزدیک‌ترِ منطقی
//                   بیاور. اگر واقعاً برگشت، با ضررِ کمتر خارج می‌شوی؛ اگر برگشتِ
//                   کاذب بود و قیمت به‌نفعت چرخید، هنوز در معامله‌ای. این دقیقاً از
//                   «بستنِ کورکورانهٔ در ضرر» جلوگیری می‌کند.
// ============================================================================

export type ReversalLevel = 'none' | 'soft' | 'defend-profit' | 'defend-close'

// شکلِ کمینه‌ای از خروجیِ runCard که این ماژول به آن نیاز دارد (بدونِ وابستگیِ سنگین).
export interface OppSignalView {
  state: 'NEUTRAL' | 'APPROACHING' | 'ENTRY'
  direction?: 'LONG' | 'SHORT' | string
  sourceLayer?: { code?: string; name?: string } | null
}

export interface ReversalInput {
  side: 'long' | 'short'      // جهتِ معاملهٔ باز کاربر
  opp: OppSignalView          // خروجیِ زندهٔ موتورِ همان کارت (runCard)
  inProfit: boolean           // آیا کاربر (خارج از ناحیهٔ اسپرد) در سود است؟
  inRealLoss: boolean         // آیا در ضررِ واقعی است؟
  pnlR: number                // سود/زیان بر حسبِ R
  price: number               // قیمتِ فعلی
  entry: number
  atr: number
  trendAgainst: boolean       // آیا روندِ خامِ بازار هم مخالفِ معامله است؟ (تاییدِ مضاعف)
}

export interface ReversalResult {
  level: ReversalLevel
  // آیا جهتِ سیگنالِ موتور واقعاً مخالفِ معاملهٔ کاربر است؟ (LONG↔SHORT)
  opposed: boolean
  // متنِ آمادهٔ نمایش (اگر level !== none)
  title?: string
  detail?: string
  // پیشنهادِ قابلِ‌اعمال روی SL (کاربر با یک کلیک اعمال کند) — فقط در سطوحِ دفاعی.
  suggestSl?: number
  // برچسبِ لایهٔ مخالف برای شفافیت (کاربر بداند این هشدار از کجاست).
  oppLayer?: string
}

const round2 = (x: number) => Math.round(x * 100) / 100

// جهتِ سیگنالِ موتور را به long/short نگاشت می‌کند (اگر جهت نداشته باشد null).
function dirOf(opp: OppSignalView): 'long' | 'short' | null {
  const d = (opp.direction || '').toUpperCase()
  if (d === 'LONG') return 'long'
  if (d === 'SHORT') return 'short'
  return null
}

/**
 * شدتِ لحظه‌ایِ برگشت را می‌سنجد. تثبیتِ زمانی در فرانت‌اند انجام می‌شود.
 */
export function assessReversal(inp: ReversalInput): ReversalResult {
  const oppDir = dirOf(inp.opp)
  const opposed = oppDir !== null && oppDir !== inp.side
  const oppLayer = inp.opp.sourceLayer?.code
    ? `${inp.opp.sourceLayer?.name || inp.opp.sourceLayer?.code}`
    : undefined

  // اگر جهتِ موتور مخالفِ معامله نیست → هیچ برگشتی نداریم.
  if (!opposed) return { level: 'none', opposed: false, oppLayer }

  const oppFa = inp.side === 'long' ? 'فروش (SHORT)' : 'خرید (LONG)'
  const myFa = inp.side === 'long' ? 'خرید (LONG)' : 'فروش (SHORT)'
  const layerTag = oppLayer ? `لایهٔ «${oppLayer}» ` : 'موتورِ سایت '

  // ---- سطحِ soft: برگشت هنوز فقط «در حالِ شکل‌گیری» است (approaching مخالف) ----
  if (inp.opp.state === 'APPROACHING') {
    return {
      level: 'soft', opposed: true, oppLayer,
      title: 'نشانهٔ اولیهٔ برگشتِ روند (هنوز قطعی نیست)',
      detail: `${layerTag}در پس‌زمینه شروع به شکل‌دادنِ یک سیگنالِ ${oppFa} کرده که مخالفِ معاملهٔ ${myFa}ِ توست. ` +
        `هنوز تثبیت نشده؛ عجله نکن — فقط آماده باش و حرکتِ چند کندلِ بعد را دقیق ببین. ` +
        `اگر این سیگنال تثبیت شد، آن‌وقت پیشنهادِ دفاعی می‌دهم.`,
    }
  }

  // از این‌جا به بعد: موتور یک سیگنالِ ENTRYِ فعالِ مخالف دارد (برگشتِ واقعی‌تر).
  if (inp.opp.state !== 'ENTRY') return { level: 'none', opposed: true, oppLayer }

  // ---- سطحِ defend-profit: در سود هستیم → سود را قفل کن (ریسکِ این کار صفر است) ----
  if (inp.inProfit) {
    // SL را به بریک‌ایون یا کمی داخلِ سود ببر (نصفِ راهِ بینِ ورود و قیمتِ فعلی).
    const half = inp.side === 'long'
      ? round2(inp.entry + Math.max(0, (inp.price - inp.entry) * 0.5))
      : round2(inp.entry - Math.max(0, (inp.entry - inp.price) * 0.5))
    return {
      level: 'defend-profit', opposed: true, oppLayer,
      title: '🛡 برگشتِ فعال شناسایی شد — سودت را قفل کن',
      detail: `${layerTag}اکنون یک سیگنالِ ${oppFa}ِ فعال می‌دهد که مخالفِ معاملهٔ سودآورِ ${myFa}ِ توست ` +
        `(سود ${round2(inp.pnlR)}R). چون در سودی، ریسکِ این کار صفر است: SL را به ${half} بکش تا اگر ` +
        `برگشت واقعی بود بخشِ خوبی از سود قفل شود، و اگر برگشت کاذب بود همچنان در معامله بمانی. ` +
        `**نبند** — فقط سود را بیمه کن.`,
      suggestSl: half,
    }
  }

  // ---- سطحِ defend-close: در ضررِ واقعی + برگشتِ فعال ----
  // پاسخِ مستقیم به نگرانیِ کاربر: به‌جای «کورکورانه ببند»، SL را نزدیک‌تر بیاور.
  // فقط وقتی «بستن» را قاطعانه پیشنهاد می‌کنیم که تاییدِ مضاعف باشد (روندِ خام هم مخالف).
  const tightSl = inp.side === 'long'
    ? round2(inp.price - Math.max(0.6 * inp.atr, inp.price * 0.0008))
    : round2(inp.price + Math.max(0.6 * inp.atr, inp.price * 0.0008))
  const doubleConfirmed = inp.trendAgainst
  return {
    level: 'defend-close', opposed: true, oppLayer,
    title: doubleConfirmed
      ? '⛔ برگشتِ تاییدشده و تو در ضرری — خروجِ دفاعی را جدی بگیر'
      : '⚠️ برگشتِ فعال و تو در ضرری — دفاع کن (هنوز عجله برای بستن نکن)',
    detail: `${layerTag}یک سیگنالِ ${oppFa}ِ فعال می‌دهد و تو در معاملهٔ ${myFa} در ضرر (${round2(inp.pnlR)}R) هستی. ` +
      (doubleConfirmed
        ? `روندِ خامِ بازار هم مخالفِ توست (تاییدِ مضاعف). این جدی‌ترین حالت است. ` +
          `به‌جای صبرِ کورکورانه، SL را به ${tightSl} نزدیک کن: اگر برگشت واقعی بود با ضررِ کمتر خارج می‌شوی؛ ` +
          `اگر قیمت به‌نفعت چرخید هنوز در معامله‌ای. اگر شواهدِ برگشت قوی‌تر شد، بستنِ کامل منطقی است.`
        : `اما روندِ کلیِ بازار هنوز کاملاً مخالف نشده. پیشنهادِ محافظه‌کارانه: SL را به ${tightSl} نزدیک کن ` +
          `تا اگر برگشت ادامه یافت ضررت محدود شود، بدونِ اینکه با یک نوسانِ کاذب زودهنگام بیرون بیفتی.`),
    suggestSl: tightSl,
  }
}
