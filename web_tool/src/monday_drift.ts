// ============================================================================
// لایهٔ «Monday Week-Start Drift» روی طلا — S140⁺⁺ (ارتقا به M5 + حذفِ ساعتِ ۲۱)
// ----------------------------------------------------------------------------
// کشفِ بک‌تستِ اصلی (strategies/s140_gold_monday_effect.py):
//   طلا در «عصرِ دوشنبه» — ابتدای هفتهٔ معاملاتی — درایوِ صعودیِ ساختاری دارد
//   (اثرِ روزِ هفته: Cross 1973، Ball–Torous–Tschoegl 1982). دوشنبه قوی‌ترین روز (t=+6.11).
//
// ارتقای تایم‌فریم (S190–S195 — پاسخِ User Note دربارهٔ XAUUSD M5):
//   • دادهٔ M5: ATR میانه ۲۱pip (نصفِ M15=۳۸pip) ⇒ TP دورِ M15 روی M5 دیر پُر می‌شود.
//     بازتنظیمِ TP/SL مخصوصِ M5 = SL100/TP200، mh288 (۲۴ ساعت).
//   • S194: امتحانِ فیلترِ مضاعف نشان داد اندیکاتورها (score/trend/vol) net را کم می‌کنند؛
//     اما حذفِ ساعتِ ۲۱ UTC از پنجرهٔ ورود (که به‌تنهایی زیان‌ده بود) net را بالا می‌برد.
//   • S195: آزمونِ استحکامِ **مستقل روی M15** هم تأیید کرد ساعتِ ۲۱ ضعیف‌ترین است
//     (h18-20 net +$9,071 vs h18-21 +$7,379) ⇒ الگو ساختاری است، نه overfit.
//   ⇒ S140⁺⁺ = دوشنبه، ساعتِ ۱۸/۱۹/۲۰ UTC، Long، SL100/TP200.
//     net +$9,213 / WR ۴۴.۵٪ (نسخهٔ رکوردِ قبلیِ M15: +$7,661 / ۳۹.۰٪ — زیرِ کف بود!).
//     walk-forward ۴/۴ مثبت [2248,2889,963,1058]. اثرِ افزایشی = +$1,553.
//     ⇒ رکوردِ کل از +$250,918 به +$252,471.
//
// این لایه هیچ اندیکاتور یا خطِ حمایت/مقاومتی ندارد — «فقط بُعدِ زمانیِ روز×ساعت».
// معیارِ پروژه: سودِ خالص = XAUUSD + EURUSD (نه Win-Rate).
// ============================================================================

// روزِ هفته: getUTCDay(): 0=Sun..1=Mon (پایتون dayofweek: 0=Mon).
export const MONDAY_UTC_DAY = 1            // Date.getUTCDay(): 1 = Monday
// ساعاتِ UTCِ ورود — S140⁺⁺: ساعتِ ۲۱ حذف شد (S194–S195؛ ساعتِ ۲۱ زیان‌ده و تأییدشده روی M15).
export const MONDAY_ENTRY_HOURS = [18, 19, 20]
// ساعتی که «نزدیک‌شدن» اعلام می‌شود (یک ساعت پیش از پنجره، فقط دوشنبه).
export const MONDAY_APPROACH_HOUR = 17
// پارامترهای خروجِ مخصوصِ M5 (بر حسبِ pip؛ ۱pip طلا = ۰.۱۰$) — بازتنظیم‌شده در S191/S193.
export const MONDAY_SL_PIP = 100
export const MONDAY_TP_PIP = 200
export const MONDAY_MAX_HOLD = 288   // ۲۴ ساعت روی M5 (۲۸۸×۵ دقیقه)
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
        `(عصرِ دوشنبه، ۱۸–۲۰ UTC — نسخهٔ S140⁺⁺ روی M5). دوشنبه قوی‌ترین روزِ هفته برای طلاست ` +
        `(t=+۶.۱۱)؛ با بازتنظیمِ TP/SL مخصوصِ M5 (SL100/TP200) و حذفِ ساعتِ زیان‌دهِ ۲۱ UTC، ` +
        `WR به ۴۴.۵٪ و سودِ افزایشی به +$1,553 رسید (تأییدشده روی M15). ` +
        `طبقِ قانونِ شمارهٔ ۱ هدف سودِ خالص است نه وین‌ریت.`,
    }
  }

  if (isMonday && utcHour === MONDAY_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', utcDay, utcHour, slDist, tpDist,
      reason: `اکنون دوشنبه ساعتِ ${utcHour}:00 UTC است — پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
        `(S140⁺⁺: ۱۸–۲۰ UTC) در حالِ باز شدن است. با ورودِ ساعتِ ۱۸ UTC آماده‌باشِ سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  const dayName = isMonday ? 'دوشنبه' : 'روزی غیر از دوشنبه'
  return {
    state: 'NEUTRAL', utcDay, utcHour, slDist, tpDist,
    reason: `اکنون ${dayName}، ساعتِ ${utcHour}:00 UTC است — خارج از پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
      `(S140⁺⁺: دوشنبه ۱۸–۲۰ UTC). این لایه صرفاً زمان-محور (روز×ساعت) است و فقط در آن پنجره ورود می‌کند.`,
  }
}
