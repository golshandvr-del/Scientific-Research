// ============================================================================
// لایهٔ «Overnight Drift» روی طلا M15 (S139) — سیگنالِ زمان-محورِ خالص
// ----------------------------------------------------------------------------
// کشفِ بک‌تست (strategies/s139_gold_overnight_drift.py):
//   طلا در پنجرهٔ ابتدای سشنِ آسیا (۲۲–۲۳ UTC) درایوِ صعودیِ ساختاری دارد.
//   ورودِ Long در کندلِ ساعتِ ۲۲/۲۳ UTC، هولد تا ۹۶ کندل، SL۱۵۰pip/TP۵۰۰pip:
//   سودِ مستقلِ +$43,413 ، both-halves + هر ۴ WF مثبت،
//   corr روزانه +0.13 با S67 و +0.27 با Squeeze (هر دو <0.35 ⇒ افزایشی).
//   ⇒ رکوردِ کل از +$128,325 به +$171,738.
//
// این لایه هیچ اندیکاتور یا خطِ حمایت/مقاومتی ندارد — «فقط زمان». به‌همین دلیل
// از تمامِ لایه‌های قیمت-محورِ موجود مستقل (ناهمبسته) است.
// معیارِ پروژه: سودِ خالص = XAUUSD + EURUSD (نه Win-Rate).
// ============================================================================

// ساعاتِ UTCِ ورودِ درایوِ شبانه (کشفِ بک‌تست).
export const OVERNIGHT_ENTRY_HOURS = [22, 23]
// ساعتی که «نزدیک‌شدن» اعلام می‌شود (یک ساعت پیش از پنجره).
export const OVERNIGHT_APPROACH_HOUR = 21
// پارامترهای خروجِ برندهٔ بک‌تست (بر حسبِ pip؛ ۱pip طلا = ۰.۱۰$).
export const OVERNIGHT_SL_PIP = 150
export const OVERNIGHT_TP_PIP = 500
export const OVERNIGHT_MAX_HOLD = 96   // ۲۴ ساعت (M15)
const PIP = 0.10                       // اندازهٔ pip طلا بر حسبِ قیمت

// ساعتِ UTC → «HH:MM به وقتِ ایران» (ایران آفستِ ثابتِ UTC+3:30 دارد، بدونِ DST).
// همهٔ توصیه‌های زمان-محورِ نمایشی به وقتِ ایران بیان می‌شوند (پاسخِ User Note).
function toIran(utcHour: number): string {
  const total = ((utcHour * 60 + 210) % 1440 + 1440) % 1440
  const hh = Math.floor(total / 60), mm = total % 60
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
}
// بازهٔ ساعتِ ورود به وقتِ ایران (مثلِ «۰۱:۳۰–۰۲:۳۰»).
const ENTRY_IRAN_RANGE = `${toIran(22)}–${toIran(23)}`

export type OvernightState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface OvernightSignal {
  state: OvernightState
  utcHour: number
  slDist: number   // فاصلهٔ SL بر حسبِ قیمت ($)
  tpDist: number   // فاصلهٔ TP بر حسبِ قیمت ($)
  reason: string
}

// ارزیابیِ لایهٔ Overnight بر اساسِ ساعتِ UTCِ کندلِ جاری.
export function computeOvernight(utcHour: number): OvernightSignal {
  const slDist = OVERNIGHT_SL_PIP * PIP
  const tpDist = OVERNIGHT_TP_PIP * PIP

  if (OVERNIGHT_ENTRY_HOURS.includes(utcHour)) {
    return {
      state: 'ENTRY', utcHour, slDist, tpDist,
      reason: `اکنون ساعتِ ${toIran(utcHour)} به وقتِ ایران است — درست در پنجرهٔ «درایوِ شبانهٔ طلا» ` +
        `(ابتدای سشنِ آسیا، ${ENTRY_IRAN_RANGE} به وقتِ ایران). بک‌تستِ ۱۳۵٬۰۰۰ کندل نشان می‌دهد طلا در این ساعت‌ها ` +
        `بایاسِ صعودیِ ساختاری دارد (سهمِ مستقلِ +۴۳٬۴۱۳$، جریانی افزایشی و ناهمبسته). ` +
        `طبقِ قانونِ شمارهٔ ۱ هدف سودِ خالص است نه وین‌ریت: TP دور (۵۰۰pip) نگه داشته می‌شود ` +
        `تا بردها بدوند (WR ~۴۴٪ اما سودِ خالصِ بالا). به شمارشِ معکوسِ «تا پایانِ فرصتِ ورود» توجه کنید.`,
    }
  }

  if (utcHour === OVERNIGHT_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', utcHour, slDist, tpDist,
      reason: `اکنون ساعتِ ${toIran(utcHour)} به وقتِ ایران است — پنجرهٔ «درایوِ شبانهٔ طلا» (${ENTRY_IRAN_RANGE} به وقتِ ایران) ` +
        `در حالِ باز شدن است. با ورودِ ساعتِ ${toIran(22)} به وقتِ ایران آماده‌باشِ سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  return {
    state: 'NEUTRAL', utcHour, slDist, tpDist,
    reason: `اکنون ساعتِ ${toIran(utcHour)} به وقتِ ایران است — خارج از پنجرهٔ «درایوِ شبانهٔ طلا» (${ENTRY_IRAN_RANGE} به وقتِ ایران). ` +
      `این لایه صرفاً زمان-محور است و فقط در آن ساعت‌ها ورود می‌کند.`,
  }
}
