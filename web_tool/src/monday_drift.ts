// ============================================================================
// لایهٔ «Monday Week-Start Drift» روی طلا M15 (S140) — سیگنالِ زمان-محورِ روز×ساعت
// ----------------------------------------------------------------------------
// کشفِ بک‌تست (strategies/s140_gold_monday_effect.py):
//   طلا در «عصرِ دوشنبه» (۱۸–۲۱ UTC) — ابتدای هفتهٔ معاملاتی — درایوِ صعودیِ
//   ساختاری دارد (اثرِ روزِ هفته: Cross 1973، Ball–Torous–Tschoegl 1982).
//   محورِ خالصِ روزِ هفته: دوشنبه t=+6.11 (قوی‌ترین و پایدارترین روز).
//   خانوادهٔ خروجِ SL/TP/max_hold: هر ۱۸ ترکیب سودده و both-halves-positive.
//   سودِ رسمیِ (محافظه‌کارانهٔ) لایه = +$3,508 (میانگینِ ۱۸ ترکیب، نه max).
//   گیت‌ها: both-halves + هر ۴ WF مثبت + IS/OOS مثبت (OOS +$2,858)،
//   corr روزانه +0.214 با Overnight و +0.149 با S67 (هر دو <0.35 ⇒ افزایشی).
//   ⇒ رکوردِ کل از +$171,738 به +$175,246.
//
// این لایه هیچ اندیکاتور یا خطِ حمایت/مقاومتی ندارد — «فقط بُعدِ زمانیِ روز×ساعت».
// از بُعدِ «ساعتِ روزِ» Overnight هم متعامد است (Overnight هر روز؛ Monday فقط دوشنبه
// و در ساعاتِ متفاوت) ⇒ ناهمبسته و افزایشی.
// معیارِ پروژه: سودِ خالص = XAUUSD + EURUSD (نه Win-Rate).
// ============================================================================

// روزِ هفته (۰=دوشنبه ... ۶=یکشنبه، مطابقِ Date.getUTCDay است؟ نه — getUTCDay: 0=Sun).
// در پایتون dayofweek: 0=Mon. اینجا از getUTCDay استفاده می‌کنیم (0=Sun..1=Mon).
export const MONDAY_UTC_DAY = 1            // Date.getUTCDay(): 1 = Monday
// ساعاتِ UTCِ ورودِ درایوِ ابتدای هفته (کشفِ بک‌تست).
export const MONDAY_ENTRY_HOURS = [18, 19, 20, 21]
// ساعتی که «نزدیک‌شدن» اعلام می‌شود (یک ساعت پیش از پنجره، فقط دوشنبه).
export const MONDAY_APPROACH_HOUR = 17
// پارامترهای خروجِ محافظه‌کارانه (بر حسبِ pip؛ ۱pip طلا = ۰.۱۰$).
export const MONDAY_SL_PIP = 150
export const MONDAY_TP_PIP = 500
export const MONDAY_MAX_HOLD = 96   // ۲۴ ساعت (M15)
const PIP = 0.10                    // اندازهٔ pip طلا بر حسبِ قیمت

export type MondayState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface MondaySignal {
  state: MondayState
  utcDay: number
  utcHour: number
  slDist: number   // فاصلهٔ SL بر حسبِ قیمت ($)
  tpDist: number   // فاصلهٔ TP بر حسبِ قیمت ($)
  reason: string
}

// ارزیابیِ لایهٔ Monday بر اساسِ روز و ساعتِ UTCِ کندلِ جاری.
export function computeMonday(utcDay: number, utcHour: number): MondaySignal {
  const slDist = MONDAY_SL_PIP * PIP
  const tpDist = MONDAY_TP_PIP * PIP
  const isMonday = utcDay === MONDAY_UTC_DAY

  if (isMonday && MONDAY_ENTRY_HOURS.includes(utcHour)) {
    return {
      state: 'ENTRY', utcDay, utcHour, slDist, tpDist,
      reason: `اکنون دوشنبه ساعتِ ${utcHour}:00 UTC است — درست در پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
        `(عصرِ دوشنبه، ۱۸–۲۱ UTC). بک‌تستِ ۱۵۰٬۰۰۰ کندل نشان می‌دهد دوشنبه قوی‌ترین روزِ هفته ` +
        `برای طلاست (t=+۶.۱۱)؛ سهمِ مستقلِ محافظه‌کارانهٔ +۳٬۵۰۸$، جریانی افزایشی و ناهمبسته. ` +
        `طبقِ قانونِ شمارهٔ ۱ هدف سودِ خالص است نه وین‌ریت: TP دور نگه داشته می‌شود تا بردها بدوند ` +
        `(WR ~۴۰–۵۴٪ اما سودِ خالصِ مثبتِ پایدار در هر دو نیمهٔ داده).`,
    }
  }

  if (isMonday && utcHour === MONDAY_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', utcDay, utcHour, slDist, tpDist,
      reason: `اکنون دوشنبه ساعتِ ${utcHour}:00 UTC است — پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
        `(۱۸–۲۱ UTC) در حالِ باز شدن است. با ورودِ ساعتِ ۱۸ UTC آماده‌باشِ سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  const dayName = isMonday ? 'دوشنبه' : 'روزی غیر از دوشنبه'
  return {
    state: 'NEUTRAL', utcDay, utcHour, slDist, tpDist,
    reason: `اکنون ${dayName}، ساعتِ ${utcHour}:00 UTC است — خارج از پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
      `(دوشنبه ۱۸–۲۱ UTC). این لایه صرفاً زمان-محور (روز×ساعت) است و فقط در آن پنجره ورود می‌کند.`,
  }
}
