// ============================================================================
// لایهٔ «End-of-the-Month Drift» روی طلا M15 (S310 — احیای S144) — سیگنالِ زمان-محور
// ----------------------------------------------------------------------------
// کشفِ بک‌تستِ رویداد-محور (strategies/s310_eom_drift_revival.py):
//   طلا در «هفتمین روزِ مانده به پایانِ ماه» (rel=-7)، در سشنِ نیویورک، درایوِ
//   صعودیِ ساختاری دارد (بازتوازنِ پرتفویِ ماهانه / month-end rebalancing).
//   لایهٔ S144 با معیارِ RQS+ سوخته بود (فقط G2 با اختلافِ ۰.۰۱ رد می‌شد: PF=1.29).
//   احیا با «فیلترِ کیفیتِ ورود» (نه دستکاریِ TP/SL):
//       ATR ≥ ۱.۰×میانه  +  close_pos ≥ ۰.۵  +  close > EMA200
//   نتیجهٔ M15: RQS+ = ۸۷.۳ ، هر ۶ گیت ✓ ، WR=۶۰٪ ، PF=۱.۷۴ ، DD=۱.۹٪ ،
//       walk-forward هر ۴ پنجره مثبت [+۶۳.۲, +۱۵.۸, +۲۵۱.۶, +۲۶۶.۴].
//   همپوشانی با S306 (Turn-of-Month): ۰.۰٪ (نه روز مشترک، نه ساعت مشترک) ⇒ لبهٔ مستقل.
//   سند: results/S310_EndOfMonthDriftRevival_Xauusd_M15_87.md
//
// این لایه «بُعدِ زمانیِ روزِ ماه (پایان) × ساعتِ NY» را با «فیلترِ کیفیتِ رژیم/کندل»
// ترکیب می‌کند. از S306 (اولِ ماه، صبحِ لندن) کاملاً متعامد و ناهمبسته است.
// همهٔ توصیه‌های زمانی به وقتِ ایران (UTC+3:30) نمایش داده می‌شوند (User Note).
// ============================================================================

// ساعاتِ UTCِ ورودِ درایوِ پایانِ ماه (کشفِ بک‌تست: سشنِ نیویورک).
export const EOM_ENTRY_HOURS = [20, 21, 22, 23]
// ساعتی که «نزدیک‌شدن» اعلام می‌شود (یک ساعت پیش از پنجره).
export const EOM_APPROACH_HOUR = 19
// «هفتمین روزِ مانده به پایانِ ماه» (rel=-7). پنجرهٔ نرمِ ±۱ روز برای پوششِ تقویمی.
export const EOM_REL_DAY = 7
// پارامترهای برندهٔ M15 (بازتولیدِ رویداد-محور، هزینهٔ واقعی):
export const EOM_SL_PIP = 170
export const EOM_TP_PIP = 250
export const EOM_MAX_HOLD = 32     // ۸ ساعت (M15)
// فیلترهای کیفیت (کشفِ فاز ۲–۴):
export const EOM_ATR_MIN_MULT = 1.0    // ATR جاری ≥ ۱.۰×میانهٔ ATR (ضدِ رنجِ مرده)
export const EOM_CLOSE_POS_MIN = 0.5   // موقعیتِ close در رنجِ کندلِ ورود ≥ ۰.۵
const PIP = 0.10                       // اندازهٔ pip طلا بر حسبِ قیمت

// ساعتِ UTC → «HH:MM به وقتِ ایران» (UTC+3:30 ثابت).
function toIran(utcHour: number): string {
  const total = ((utcHour * 60 + 210) % 1440 + 1440) % 1440
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
const EOM_IRAN_RANGE = `${toIran(20)}–${toIran(23)}`  // ۲۳:۳۰–۰۲:۳۰

export type EomState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface EomSignal {
  state: EomState
  isEomWindow: boolean       // آیا امروز حوالیِ «۷ روزِ مانده به آخرِ ماه» است؟
  utcHour: number
  slDist: number
  tpDist: number
  reason: string
}

// شمارشِ روزهای معاملاتیِ (دوشنبه–جمعه) باقی‌مانده تا پایانِ ماهِ تقویمی، از تاریخِ داده‌شده
// (شاملِ خودِ آن روز). forward-safe: فقط از تقویم استفاده می‌کند، نه از داده‌های آینده.
function tradingDaysToMonthEnd(d: Date): number {
  const y = d.getUTCFullYear(), m = d.getUTCMonth()
  const lastDay = new Date(Date.UTC(y, m + 1, 0)).getUTCDate()   // آخرین روزِ تقویمیِ ماه
  let count = 0
  for (let day = d.getUTCDate(); day <= lastDay; day++) {
    const dow = new Date(Date.UTC(y, m, day)).getUTCDay()        // 0=یکشنبه … 6=شنبه
    if (dow >= 1 && dow <= 5) count++                            // فقط روزهای کاری
  }
  return count
}

// آیا امروز «۷ روزِ معاملاتیِ مانده به پایانِ ماه» (با تحملِ ±۱ روز) است؟
// از آخرین timestampِ داده استفاده می‌کنیم (زمانِ کندلِ جاری).
export function isEndOfMonthWindow(times: number[]): boolean {
  if (times.length < 1) return false
  const now = new Date(times[times.length - 1] * 1000)
  const dow = now.getUTCDay()
  if (dow < 1 || dow > 5) return false            // فقط روزهای معاملاتی
  const rem = tradingDaysToMonthEnd(now)
  // rel=-7 یعنی ۷ روزِ معاملاتی مانده (شاملِ امروز). تحملِ ±۱ برای ناهم‌ترازیِ تقویمی.
  return rem >= EOM_REL_DAY - 1 && rem <= EOM_REL_DAY + 1
}

// فیلترِ کیفیتِ ورود (کشفِ فاز ۲–۴): رژیمِ نوسانِ زنده + قدرتِ کندل + روندِ کلان.
export interface EomFilter {
  atrLive: boolean     // ATR جاری ≥ ۱.۰×میانهٔ ATR
  closeStrong: boolean // close_pos ≥ ۰.۵ (بستنِ قوی در نیمهٔ بالای کندل)
  aboveEma: boolean    // close > EMA200 (روندِ کلانِ صعودی)
}

function eomFiltersPass(f?: EomFilter): boolean {
  if (!f) return true
  return f.atrLive && f.closeStrong && f.aboveEma
}

// ارزیابیِ لایهٔ End-of-Month: پنجرهٔ روزِ ماه × ساعتِ NY + فیلترِ کیفیت (اختیاری).
export function computeEndOfMonth(times: number[], utcHour: number, filt?: EomFilter): EomSignal {
  const slDist = EOM_SL_PIP * PIP
  const tpDist = EOM_TP_PIP * PIP
  const inWindow = isEndOfMonthWindow(times)

  if (inWindow && EOM_ENTRY_HOURS.includes(utcHour)) {
    if (!eomFiltersPass(filt)) {
      const need: string[] = []
      if (filt && !filt.atrLive) need.push('نوسانِ بازار زنده شود (ATR بالای میانه — فعلاً رنجِ مرده)')
      if (filt && !filt.closeStrong) need.push('کندلِ ورود قوی ببندد (close در نیمهٔ بالای کندل)')
      if (filt && !filt.aboveEma) need.push('روندِ کلان صعودی شود (قیمت بالای EMA200)')
      return {
        state: 'APPROACHING', isEomWindow: true, utcHour, slDist, tpDist,
        reason: `اکنون در پنجرهٔ «۷ روزِ پایانیِ ماه» و ساعتِ ${toIran(utcHour)} به وقتِ ایران ` +
          `(سشنِ نیویورک، ${EOM_IRAN_RANGE}) هستیم — پنجرهٔ «درایوِ پایانِ ماهِ طلا». اما فیلترِ کیفیتِ ورود ` +
          `هنوز تأیید نشده. برای صدورِ سیگنالِ خرید باید: ${need.join('؛ ')}. ` +
          `(لایهٔ S310 با این فیلتر ⇒ RQS+ ۸۷، WR ۶۰٪، PF ۱.۷۴.)`,
      }
    }
    return {
      state: 'ENTRY', isEomWindow: true, utcHour, slDist, tpDist,
      reason: `اکنون در پنجرهٔ «۷ روزِ پایانیِ ماه» و ساعتِ ${toIran(utcHour)} به وقتِ ایران ` +
        `(سشنِ نیویورک) هستیم و فیلترِ کیفیت (نوسانِ زنده + کندلِ قوی + روندِ صعودیِ کلان) تأیید شد. ` +
        `این پنجره درایوِ صعودیِ «بازتوازنِ پرتفویِ پایانِ ماه» را شکار می‌کند. ` +
        `سیگنالِ خرید (LONG) با TP ${EOM_TP_PIP}pip و SL ${EOM_SL_PIP}pip. این پیکربندی در بک‌تستِ رویداد-محورِ ` +
        `۶.۴ ساله RQS+ = ۸۷.۳ داد (هر ۶ گیت، هر ۴ پنجرهٔ walk-forward مثبت — سند S310). ` +
        `مستقل از لایهٔ اولِ ماه (S306): همپوشانیِ صفر.`,
    }
  }

  if (inWindow && utcHour === EOM_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', isEomWindow: true, utcHour, slDist, tpDist,
      reason: `اکنون در پنجرهٔ «۷ روزِ پایانیِ ماه» و ساعتِ ${toIran(utcHour)} به وقتِ ایران است — پنجرهٔ ` +
        `«درایوِ پایانِ ماهِ طلا» (${EOM_IRAN_RANGE} به وقتِ ایران، سشنِ نیویورک) در حالِ باز شدن است. ` +
        `با ورود به ساعتِ ${toIran(20)} و تأییدِ فیلترِ کیفیت (نوسانِ زنده + کندلِ قوی + روندِ صعودی)، ` +
        `سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  return {
    state: 'NEUTRAL', isEomWindow: inWindow, utcHour, slDist, tpDist,
    reason: inWindow
      ? `اکنون در پنجرهٔ «۷ روزِ پایانیِ ماه» هستیم اما ساعتِ ${toIran(utcHour)} به وقتِ ایران خارج از پنجرهٔ ` +
        `قویِ ${EOM_IRAN_RANGE} (سشنِ نیویورک) است. این لایه فقط در آن پنجرهٔ شبانه ورود می‌کند.`
      : `اکنون در پنجرهٔ «۷ روزِ پایانیِ ماه» نیستیم (ساعتِ ${toIran(utcHour)} به وقتِ ایران). این لایه صرفاً ` +
        `زمان-محور × کیفیت است و فقط در حوالیِ ۷ روزِ پایانیِ هر ماه، ساعاتِ ${EOM_IRAN_RANGE} به وقتِ ایران، ` +
        `با تأییدِ فیلترِ کیفیت ورود می‌کند.`,
  }
}
