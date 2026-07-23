// ============================================================================
// لایهٔ «Turn-of-the-Month Drift» روی طلا M15 (S141) — سیگنالِ زمان-محورِ تقویمی
// ----------------------------------------------------------------------------
// کشفِ بک‌تست (strategies/s141_gold_turn_of_month.py):
//   طلا در «اولین روزِ معاملاتیِ هر ماه» (tom_rel=1) درایوِ صعودیِ ساختاری دارد
//   (اثرِ چرخشِ ماه: Ariel 1987، Lakonishok–Smidt 1988، McConnell–Xu 2008).
//   محورِ خالصِ روزِ ماه: tom_rel=+1 با t=+9.66 (قوی‌ترین t-stat کلِ پروژه)،
//   mean=+26.5pip، both-halves ✓. قوی‌تر در سشنِ لندن ۷–۱۲ UTC.
//   خانوادهٔ خروجِ SL/TP/max_hold: هر ۱۸ ترکیب سودده و both-halves-positive.
//   سودِ رسمیِ (محافظه‌کارانهٔ) لایه = +$4,162 (میانگینِ ۱۸ ترکیب، نه max).
//   گیت‌ها: both-halves + هر ۴ WF مثبت + IS/OOS مثبت (OOS +$3,484)،
//   corr روزانه +0.09 با Overnight، +0.06 با Monday، +0.13 با S67 (همه <0.35).
//   ⇒ رکوردِ کل از +$175,246 به +$179,408.
//
// این لایه هیچ اندیکاتور یا خطِ حمایت/مقاومتی ندارد — «فقط بُعدِ زمانیِ روزِ ماه × ساعت».
// از بُعدِ «ساعتِ روزِ» Overnight و «روزِ هفتهٔ» Monday کاملاً متعامد است
// (اولین‌روزِ‌ماه در روزهای مختلفِ هفته و ساعاتِ متفاوت رخ می‌دهد) ⇒ ناهمبسته و افزایشی.
// معیارِ پروژه: سودِ خالص = XAUUSD + EURUSD (نه Win-Rate).
// ============================================================================

// ساعاتِ UTCِ ورودِ درایوِ اولِ ماه (کشفِ بک‌تست: سشنِ لندن).
export const TOM_ENTRY_HOURS = [7, 8, 9, 10, 11, 12]
// ساعتی که «نزدیک‌شدن» اعلام می‌شود (یک ساعت پیش از پنجره، در اولین روزِ ماه).
export const TOM_APPROACH_HOUR = 6
// پارامترهای خروجِ محافظه‌کارانه (بر حسبِ pip؛ ۱pip طلا = ۰.۱۰$).
export const TOM_SL_PIP = 100
export const TOM_TP_PIP = 700
export const TOM_MAX_HOLD = 96   // ۲۴ ساعت (M15)
const PIP = 0.10                 // اندازهٔ pip طلا بر حسبِ قیمت

// ساعتِ UTC → «HH:MM به وقتِ ایران» (UTC+3:30 ثابت). همهٔ توصیه‌های زمان-محور به وقتِ ایران (User Note).
function toIran(utcHour: number): string {
  const total = ((utcHour * 60 + 210) % 1440 + 1440) % 1440
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
const TOM_IRAN_RANGE = `${toIran(7)}–${toIran(12)}`  // ۱۰:۳۰–۱۵:۳۰

export type TomState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface TomSignal {
  state: TomState
  isFirstTradingDay: boolean
  utcHour: number
  slDist: number
  tpDist: number
  reason: string
}

// آیا کندلِ جاری در «اولین روزِ معاملاتیِ ماه» است؟
// روش: تاریخِ (UTC روز) کندلِ جاری را با آخرین کندلی که ماهِ تقویمیِ متفاوتی داشت مقایسه
// می‌کنیم. اگر ماهِ کندلِ جاری با ماهِ کندلِ قبلیِ *روزِ متفاوت* فرق کند ⇒ امروز اولین
// روزِ معاملاتیِ این ماه است. (forward-safe: فقط از کندل‌های گذشته استفاده می‌شود.)
export function isFirstTradingDayOfMonth(times: number[]): boolean {
  if (times.length < 2) return false
  const last = new Date(times[times.length - 1] * 1000)
  const curMonth = last.getUTCFullYear() * 100 + last.getUTCMonth()
  const curDay = last.getUTCFullYear() * 10000 + last.getUTCMonth() * 100 + last.getUTCDate()
  // به عقب می‌رویم تا اولین کندلی که «روزِ تقویمیِ متفاوت» دارد را پیدا کنیم
  for (let i = times.length - 2; i >= 0; i--) {
    const d = new Date(times[i] * 1000)
    const dDay = d.getUTCFullYear() * 10000 + d.getUTCMonth() * 100 + d.getUTCDate()
    if (dDay === curDay) continue        // همان روز؛ ادامه به عقب
    // اولین روزِ تقویمیِ متفاوتِ قبلی پیدا شد
    const prevMonth = d.getUTCFullYear() * 100 + d.getUTCMonth()
    return prevMonth !== curMonth        // اگر ماهِ روزِ قبلی متفاوت بود ⇒ امروز اولین روزِ ماه است
  }
  return false
}

// ارزیابیِ لایهٔ Turn-of-the-Month بر اساسِ تاریخچهٔ زمان و ساعتِ UTCِ کندلِ جاری.
export function computeTurnOfMonth(times: number[], utcHour: number): TomSignal {
  const slDist = TOM_SL_PIP * PIP
  const tpDist = TOM_TP_PIP * PIP
  const isFirst = isFirstTradingDayOfMonth(times)

  if (isFirst && TOM_ENTRY_HOURS.includes(utcHour)) {
    return {
      state: 'ENTRY', isFirstTradingDay: true, utcHour, slDist, tpDist,
      reason: `اکنون «اولین روزِ معاملاتیِ ماه» و ساعتِ ${toIran(utcHour)} به وقتِ ایران (سشنِ لندن) است — ` +
        `درست در پنجرهٔ «درایوِ چرخشِ ماهِ طلا» (اولِ ماه، ${TOM_IRAN_RANGE} به وقتِ ایران). بک‌تستِ ۱۵۰٬۰۰۰ کندل ` +
        `نشان می‌دهد اولین روزِ ماه قوی‌ترین سیگنالِ زمانیِ کلِ پروژه است (t=+۹.۶۶، میانگین +۲۶.۵pip)؛ ` +
        `سهمِ مستقلِ محافظه‌کارانهٔ +۴٬۱۶۲$، جریانی افزایشی و ناهمبسته. طبقِ قانونِ شمارهٔ ۱ هدف ` +
        `سودِ خالص است نه وین‌ریت: TP دور نگه داشته می‌شود تا بردها بدوند (WR ~۴۲–۵۷٪ اما سودِ ` +
        `خالصِ مثبتِ پایدار در هر دو نیمهٔ داده و هر ۴ پنجرهٔ walk-forward).`,
    }
  }

  if (isFirst && utcHour === TOM_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', isFirstTradingDay: true, utcHour, slDist, tpDist,
      reason: `اکنون «اولین روزِ معاملاتیِ ماه» و ساعتِ ${toIran(utcHour)} به وقتِ ایران است — پنجرهٔ ` +
        `«درایوِ چرخشِ ماهِ طلا» (${TOM_IRAN_RANGE} به وقتِ ایران، همزمان با باز شدنِ سشنِ لندن) در حالِ باز شدن است. ` +
        `با ورودِ ساعتِ ${toIran(7)} به وقتِ ایران آماده‌باشِ سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  return {
    state: 'NEUTRAL', isFirstTradingDay: isFirst, utcHour, slDist, tpDist,
    reason: isFirst
      ? `اکنون اولین روزِ معاملاتیِ ماه است اما ساعتِ ${toIran(utcHour)} به وقتِ ایران خارج از پنجرهٔ قویِ ` +
        `${TOM_IRAN_RANGE} به وقتِ ایران (سشنِ لندن) است. این لایه فقط در آن پنجره ورود می‌کند.`
      : `اکنون اولین روزِ معاملاتیِ ماه نیست (ساعتِ ${toIran(utcHour)} به وقتِ ایران) — خارج از پنجرهٔ «درایوِ ` +
        `چرخشِ ماهِ طلا». این لایه صرفاً زمان-محور (روزِ تقویمیِ ماه × ساعت) است و فقط در ` +
        `اولین روزِ معاملاتیِ هر ماه، ساعاتِ ${TOM_IRAN_RANGE} به وقتِ ایران ورود می‌کند.`,
  }
}
