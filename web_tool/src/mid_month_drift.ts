// ============================================================================
// لایهٔ «Mid-Month Drift» روی طلا M15 (S312 — احیای S142) — سیگنالِ زمان-محور × کیفیت
// ----------------------------------------------------------------------------
// کشفِ بک‌تستِ رویداد-محور (strategies/s312_midmonth_revival.py + s312_finalize.py):
//   طلا در «روزهای تقویمیِ میانهٔ ماه» dom ∈ {۱۰, ۱۳, ۲۰} در سشنِ آسیا→لندن (۱–۱۲ UTC)
//   درایوِ صعودیِ ساختاری دارد (بازتوازنِ نهادی/ETF و تسویهٔ آپشن/فیوچرزِ میان‌ماه).
//   قوی‌ترین t-statِ کلِ پروژه (خوشهٔ dom{۱۰,۱۳,۲۰}، t≈+۱۶.۱۶).
//   لایهٔ S142 با معیارِ RQS+ سوخته بود چون از پارادایمِ قدیم (SL۱۰۰/TP۵۰۰، RR نامتقارنِ
//   ۱:۵) استفاده می‌کرد ⇒ WR≈۳۵–۴۲٪ ⇒ گیتِ G0 (WR۶۰) را رد می‌کرد.
//   احیا (نه دستکاریِ سطحی، بلکه بازطراحیِ ریاضیِ ساختارِ خروج):
//       ۱) RR متقارن (SL=TP)  ⇒ در یک driftِ مثبتِ واقعی، هم G1 (لبهٔ آماری) هم G0
//          (WR≥۶۰) هم‌زمان محقق می‌شوند — بدونِ تلهٔ WR مصنوعی.
//       ۲) فیلترِ کیفیتِ رژیم: close > EMA200 (فقط در روندِ ساختاریِ صعودی).
//   نتیجهٔ M15: RQS+ = ۸۹.۳ ، هر ۶ گیت ✓ ، WR=۶۰.۹٪ ، PF=۲.۵۰ ، DD=۲.۳٪ ، MCL=۵ ، p=۰.۰۰۷.
//   مولتی‌تایم‌فریم: M30 RQS+ ۹۰.۲ ، H1 RQS+ ۹۰.۲ (هر دو هر ۶ گیت). M5 = DEAD (مرزِ رزولوشن).
//   IS/OOS: هر سه TF در هر دو نیمهٔ زمانی net مثبت ⇒ لبهٔ ساختاری، نه آرتیفکت.
//   همپوشانی با S306 (اولِ ماه) = ۰.۰٪ ⇒ لبهٔ کاملاً مستقل و افزایشی.
//   تمایز از احیای قدیمیِ S221 (نامتقارن): S221 زیرِ شبیه‌سازِ رویداد-محور روی M30/H1
//     گیتِ G1 را رد می‌کند (p=۰.۴۳ و ۰.۹۵ ⇒ WRِ ۸۴٪ آرتیفکت است)؛ S312 روی هر ۳ TF
//     G1 را با p<۰.۰۱ پاس می‌کند ⇒ لبهٔ آماریِ واقعی.
//   سند: results/S312_MidMonthDrift_Xauusd_M15M30H1_89_ACCEPTED.md
//
// این لایه «بُعدِ زمانیِ روزِ ماه (میانه) × ساعتِ آسیا/لندن» را با «فیلترِ کیفیتِ رژیم»
// ترکیب می‌کند. از S306 (اولِ ماه، صبحِ لندن) و S310 (پایانِ ماه، شبِ NY) کاملاً متعامد است.
// همهٔ توصیه‌های زمانی به وقتِ ایران (UTC+3:30) نمایش داده می‌شوند (User Note).
// ============================================================================

// روزهای تقویمیِ ورودِ درایوِ میانهٔ ماه (کشفِ بک‌تست: خوشهٔ قوی).
export const MID_DOM_SET = [10, 13, 20]
// ساعاتِ UTCِ ورود (کشفِ بک‌تست: سشنِ آسیا→لندن).
export const MID_ENTRY_HOURS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
// ساعتی که «نزدیک‌شدن» اعلام می‌شود (یک ساعت پیش از پنجره).
export const MID_APPROACH_HOUR = 0
// پارامترهای برندهٔ M15 (بازتولیدِ رویداد-محور، هزینهٔ واقعی — اعدادِ غیررند از grid ریز):
export const MID_SL_PIP = 295      // RR متقارن ⇒ SL = TP
export const MID_TP_PIP = 295
export const MID_MAX_HOLD = 48     // ۱۲ ساعت (M15)
const PIP = 0.10                   // اندازهٔ pip طلا بر حسبِ قیمت

// ساعتِ UTC → «HH:MM به وقتِ ایران» (UTC+3:30 ثابت).
function toIran(utcHour: number): string {
  const total = ((utcHour * 60 + 210) % 1440 + 1440) % 1440
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
const MID_IRAN_RANGE = `${toIran(1)}–${toIran(12)}`  // ۰۴:۳۰–۱۵:۳۰

export type MidState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface MidSignal {
  state: MidState
  isMidWindow: boolean       // آیا امروز یکی از روزهای dom ∈ {۱۰,۱۳,۲۰} است؟
  utcHour: number
  slDist: number
  tpDist: number
  reason: string
}

// آیا روزِ تقویمیِ کندلِ جاری در خوشهٔ میانهٔ ماه {۱۰,۱۳,۲۰} است؟
// از آخرین timestampِ داده (زمانِ کندلِ جاری) استفاده می‌کنیم. forward-safe.
export function isMidMonthWindow(times: number[]): boolean {
  if (times.length < 1) return false
  const now = new Date(times[times.length - 1] * 1000)
  const dom = now.getUTCDate()
  return MID_DOM_SET.includes(dom)
}

// فیلترِ کیفیتِ ورود (کشفِ فاز grid): تنها روندِ کلانِ صعودی.
// این تنها فیلتری است که در بک‌تستِ رویداد-محور RQS+ را از ۸۵.۵ به ۸۹.۳ ارتقا داد.
export interface MidFilter {
  aboveEma: boolean    // close > EMA200 (روندِ کلانِ صعودی)
}

function midFiltersPass(f?: MidFilter): boolean {
  if (!f) return true
  return f.aboveEma
}

// ارزیابیِ لایهٔ Mid-Month: پنجرهٔ روزِ ماه × ساعتِ آسیا/لندن + فیلترِ کیفیت (اختیاری).
export function computeMidMonth(times: number[], utcHour: number, filt?: MidFilter): MidSignal {
  const slDist = MID_SL_PIP * PIP
  const tpDist = MID_TP_PIP * PIP
  const inWindow = isMidMonthWindow(times)

  if (inWindow && MID_ENTRY_HOURS.includes(utcHour)) {
    if (!midFiltersPass(filt)) {
      return {
        state: 'APPROACHING', isMidWindow: true, utcHour, slDist, tpDist,
        reason: `اکنون در یکی از «روزهای درایوِ میانهٔ ماه» (روزهای ۱۰، ۱۳ یا ۲۰ تقویمی) و ساعتِ ` +
          `${toIran(utcHour)} به وقتِ ایران (${MID_IRAN_RANGE}) هستیم. ` +
          `اما هنوز شرایطِ ورود کامل نیست. برای صدورِ سیگنالِ خرید باید: روندِ کلان صعودی شود (قیمت بالای EMA200).`,
      }
    }
    return {
      state: 'ENTRY', isMidWindow: true, utcHour, slDist, tpDist,
      reason: `اکنون در یکی از «روزهای درایوِ میانهٔ ماه» (روزهای ۱۰، ۱۳ یا ۲۰ تقویمی) و ساعتِ ` +
        `${toIran(utcHour)} به وقتِ ایران هستیم و شرایطِ ورود (روندِ کلانِ صعودی بالای EMA200) تأیید شد. ` +
        `این پنجره حرکتِ صعودیِ معمولِ میانهٔ ماه را هدف می‌گیرد ⇒ سیگنالِ خرید (LONG).`,
    }
  }

  if (inWindow && utcHour === MID_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', isMidWindow: true, utcHour, slDist, tpDist,
      reason: `اکنون یکی از «روزهای درایوِ میانهٔ ماه» (۱۰/۱۳/۲۰ تقویمی) است و ساعتِ ${toIran(utcHour)} ` +
        `به وقتِ ایران — پنجرهٔ «درایوِ میانهٔ ماهِ طلا» (${MID_IRAN_RANGE} به وقتِ ایران، سشنِ آسیا→لندن) در حالِ باز شدن است. ` +
        `با ورود به ساعتِ ${toIran(1)} و تأییدِ فیلترِ کیفیت (روندِ صعودیِ کلان)، سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  return {
    state: 'NEUTRAL', isMidWindow: inWindow, utcHour, slDist, tpDist,
    reason: inWindow
      ? `اکنون یکی از «روزهای درایوِ میانهٔ ماه» (۱۰/۱۳/۲۰) است اما ساعتِ ${toIran(utcHour)} به وقتِ ایران خارج از ` +
        `پنجرهٔ قویِ ${MID_IRAN_RANGE} (سشنِ آسیا→لندن) است. این لایه فقط در آن پنجرهٔ روز ورود می‌کند.`
      : `اکنون از «روزهای درایوِ میانهٔ ماه» (۱۰/۱۳/۲۰ تقویمی) نیستیم (ساعتِ ${toIran(utcHour)} به وقتِ ایران). ` +
        `این لایه صرفاً زمان-محور × کیفیت است و فقط در روزهای ۱۰، ۱۳ و ۲۰ هر ماه، ساعاتِ ${MID_IRAN_RANGE} به وقتِ ایران، ` +
        `با تأییدِ فیلترِ کیفیت (روندِ صعودیِ کلان) ورود می‌کند.`,
  }
}
