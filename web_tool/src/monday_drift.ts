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

// ساعتِ UTC → «HH:MM به وقتِ ایران» (UTC+3:30 ثابت). همهٔ توصیه‌های زمان-محور به وقتِ ایران (User Note).
function toIran(utcHour: number): string {
  const total = ((utcHour * 60 + 210) % 1440 + 1440) % 1440
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
const MONDAY_IRAN_RANGE = `${toIran(18)}–${toIran(20)}`  // ۲۱:۳۰–۲۳:۳۰

// ============================================================================
// فیلترِ «عدم‌تقارنِ دیدِ معکوس» — S212 (Al Brooks فصلِ ۹: ETFs and Inverse Charts)
// ----------------------------------------------------------------------------
// تزِ فصل (نگاه از منظرِ معکوس): یک اصلاحِ *سالم* پیش از ادامهٔ روند باید در حرکتش
//   کُند/تخت شود؛ اگر اصلاح در نیمهٔ دومش **شتابِ نزولی بگیرد** (به‌جای کند شدن)، در
//   منظرِ معکوس یک شکست/ادامهٔ فروشِ شتابان دیده می‌شود ⇒ ستاپِ تله ⇒ ورود نکن.
//   معیارِ عملیاتی (معادلِ دقیقِ پایتون s212_brooks_inverse_view.py::inverse_view_asym،
//   با هم‌ترازیِ عددی اثبات‌شده در s212_diag_parity.py):
//   در پنجرهٔ lb کندلِ **بسته‌شده**: سقفِ محلی=argmax(high)، کفِ پس از آن=argmin(low)،
//   legِ اصلاحی به دو نیمه؛ شیبِ close هر نیمه (s1,s2)؛ asym=(s1−s2)/(range/بارها).
//   • asym>0  ⇒ نیمهٔ دوم تندتر/شتاب‌گیرندهٔ نزولی (s2 منفی‌تر از s1) ⇒ شکست ⇒ مشکوک.
//   • asym≈0  ⇒ اصلاحِ خطیِ یکنواخت (سالم).   • asym<0 ⇒ نیمهٔ دوم کند/تخت (rounding).
//   قاعدهٔ برندهٔ بک‌تست: نگه‌دار اگر asym ≤ thr ؛ رد کن اگر asym > thr (شتابِ نزولیِ فزاینده).
// بک‌تست (S212d) روی S140⁺⁺ فعالِ رکورد (XAUUSD M5): lb=12, thr=0.5 ⇒
//   net $+8,625→$+11,191 (Δ+$2,566)، WR ۴۴٪→۴۶.۲٪، WF ۴/۴ مثبت. رکورد → +$261,375.
export const MONDAY_INVVIEW_LB = 12       // پنجرهٔ نگاه (کندلِ بسته‌شده)
export const MONDAY_INVVIEW_THR = 0.5     // آستانه؛ asym>thr ⇒ رد (اصلاحِ شتاب‌گیرندهٔ نزولی=تله)

function slope(y: number[]): number {
  // شیبِ خطِ کمترین‌مربعات (معادلِ np.polyfit(x, y, 1)[0] با x=0..n-1).
  const n = y.length
  if (n < 2) return 0
  let sx = 0, sy = 0, sxx = 0, sxy = 0
  for (let i = 0; i < n; i++) { sx += i; sy += y[i]; sxx += i * i; sxy += i * y[i] }
  const denom = n * sxx - sx * sx
  if (denom === 0) return 0
  return (n * sxy - sx * sy) / denom
}

// asymِ اصلاحِ «اخیرِ بسته‌شده» را برمی‌گرداند (NaN اگر اصلاحی نبود ⇒ خنثی/مجاز).
// ورودی: آرایه‌های close/high/low تا کندلِ جاری. lb = طولِ پنجره.
// نکتهٔ causal: مثلِ shift(1) پایتون، فقط تا کندلِ ماقبلِ آخر نگاه می‌کنیم (idx تا len-1).
export function inverseViewAsymRecent(
  close: number[], high: number[], low: number[], lb: number = MONDAY_INVVIEW_LB,
): number {
  const n = close.length
  if (n < lb + 2) return NaN
  // پنجرهٔ بسته‌شده = [n-1-lb, n-1) ⇒ معادلِ asym[i] با i=n-1 و shift(1) (تا کندلِ i-1).
  const hi = high.slice(n - 1 - lb, n - 1)
  const lo = low.slice(n - 1 - lb, n - 1)
  const cl = close.slice(n - 1 - lb, n - 1)
  const m = cl.length
  if (m < lb) return NaN
  // سقفِ محلی
  let pk = 0
  for (let i = 1; i < m; i++) if (hi[i] > hi[pk]) pk = i
  if (pk >= lb - 3) return NaN          // سقف باید فضای اصلاح داشته باشد
  // کفِ پس از سقف
  let tr = pk
  for (let i = pk; i < m; i++) if (lo[i] < lo[tr]) tr = i
  if (tr - pk < 4) return NaN            // legِ اصلاحی باید ≥۴ کندل باشد
  const leg = cl.slice(pk, tr + 1)
  const mm = leg.length
  const half = Math.floor(mm / 2)
  const first = leg.slice(0, half)
  const second = leg.slice(half)
  if (first.length < 2 || second.length < 2) return NaN
  const s1 = slope(first)
  const s2 = slope(second)
  const rng = Math.max(hi[pk] - lo[tr], 1e-9)
  return (s1 - s2) / (rng / mm)
}

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
      reason: `اکنون دوشنبه ساعتِ ${toIran(utcHour)} به وقتِ ایران است — درست در پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
        `(عصرِ دوشنبه، ${MONDAY_IRAN_RANGE} به وقتِ ایران — نسخهٔ S140⁺⁺ روی M5). دوشنبه قوی‌ترین روزِ هفته برای طلاست ` +
        `(t=+۶.۱۱)؛ با بازتنظیمِ TP/SL مخصوصِ M5 (SL100/TP200) و حذفِ ساعتِ زیان‌دهِ ${toIran(21)} به وقتِ ایران، ` +
        `WR به ۴۴.۵٪ و سودِ افزایشی به +$1,553 رسید (تأییدشده روی M15). ` +
        `طبقِ قانونِ شمارهٔ ۱ هدف سودِ خالص است نه وین‌ریت. به شمارشِ معکوسِ «تا پایانِ فرصتِ ورود» توجه کنید.`,
    }
  }

  if (isMonday && utcHour === MONDAY_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', utcDay, utcHour, slDist, tpDist,
      reason: `اکنون دوشنبه ساعتِ ${toIran(utcHour)} به وقتِ ایران است — پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
        `(S140⁺⁺: ${MONDAY_IRAN_RANGE} به وقتِ ایران) در حالِ باز شدن است. با ورودِ ساعتِ ${toIran(18)} به وقتِ ایران آماده‌باشِ سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  const dayName = isMonday ? 'دوشنبه' : 'روزی غیر از دوشنبه'
  return {
    state: 'NEUTRAL', utcDay, utcHour, slDist, tpDist,
    reason: `اکنون ${dayName}، ساعتِ ${toIran(utcHour)} به وقتِ ایران است — خارج از پنجرهٔ «درایوِ ابتدای هفتهٔ طلا» ` +
      `(S140⁺⁺: دوشنبه ${MONDAY_IRAN_RANGE} به وقتِ ایران). این لایه صرفاً زمان-محور (روز×ساعت) است و فقط در آن پنجره ورود می‌کند.`,
  }
}
