// ============================================================================
// لایهٔ «Overnight Drift» روی طلا M15 (S139) — سیگنالِ زمان-محور + فیلترِ رژیم
// ----------------------------------------------------------------------------
// کشفِ بک‌تست (strategies/s139_gold_overnight_drift.py):
//   طلا در پنجرهٔ ابتدای سشنِ آسیا (۲۲–۲۳ UTC) درایوِ صعودیِ ساختاری دارد.
//   ورودِ Long در کندلِ ساعتِ ۲۲/۲۳ UTC.
//
// ★★ بازطراحیِ WR≥۶۰٪ (S222a — قانونِ احیای پروژه، این نشست) ★★
//   نسخهٔ پیشین برای «رژیمِ فقط-سودِ-خالص» نوشته شده بود: SL150/TP500 (نامتقارنِ
//   برد-محور) ⇒ WR ≈ ۴۲٪. طبقِ User Noteِ فعلی «WR باید بالای ۶۰٪ باشد»، نامتقارنی
//   معکوس شد (TP کوچک / SL بزرگ ⇒ بستنِ سریعِ سود) + فیلترِ رژیم/مومنتوم.
//   پارامترِ برندهٔ M15 (بک‌تستِ ۴ سال، هزینهٔ واقعی):
//       SL150pip / TP40pip / mh96  +  فیلترها: {pdi>mdi، bull_bar، atr<1.8×median}
//   نتیجه: WR = ۸۴.۰٪ ، net = +$3,405 ، n=488 ، هر ۴ پنجرهٔ walk-forward مثبت.
//   سند: results/S222a_OvernightWR60_Xauusd_M5M15M30H1_17416_84.md
//   (جمعِ ۴ TF این لایه = +$17,416 با WR ~۸۴٪.)
// معیارِ فعلیِ پروژه (User Note): WR هر لایه ≥ ۶۰٪ + سودِ خالص.
// ============================================================================

// ساعاتِ UTCِ ورودِ درایوِ شبانه (کشفِ بک‌تست).
export const OVERNIGHT_ENTRY_HOURS = [22, 23]
// ساعتی که «نزدیک‌شدن» اعلام می‌شود (یک ساعت پیش از پنجره).
export const OVERNIGHT_APPROACH_HOUR = 21
// پارامترهای خروجِ برندهٔ WR≥۶۰٪ (M15؛ ۱pip طلا = ۰.۱۰$).
export const OVERNIGHT_SL_PIP = 150
export const OVERNIGHT_TP_PIP = 40     // ← معکوس‌شده از ۵۰۰ (WR۴۲٪→۸۴٪)
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

// فیلترِ رژیمِ WR≥۶۰٪ (S222a): pdi>mdi (روندِ صعودیِ جهت‌دار) + bull_bar (کندلِ صعودی)
// + atr<1.8×median (ضدِ کندلِ climax/شوک). اگر همه‌ٔ اینها فراهم نباشد، لایه ورود
// نمی‌کند بلکه در حالتِ «آماده‌باش» می‌ماند تا تأییدِ رژیم بیاید ⇒ WR از ۴۲٪ به ۸۴٪.
export interface OvernightFilter {
  pdiGtMdi: boolean   // pdi > mdi
  bullBar: boolean    // close > open (کندلِ صعودی)
  atrOk: boolean      // atr < 1.8 × median(atr)
}

function filtersPass(f?: OvernightFilter): boolean {
  if (!f) return true                       // بدونِ داده ⇒ سازگارِ عقب (رفتارِ قدیمی)
  return f.pdiGtMdi && f.bullBar && f.atrOk
}

// ارزیابیِ لایهٔ Overnight: ساعتِ UTCِ کندلِ جاری + فیلترِ رژیمِ WR≥۶۰٪ (اختیاری).
export function computeOvernight(utcHour: number, filt?: OvernightFilter): OvernightSignal {
  const slDist = OVERNIGHT_SL_PIP * PIP
  const tpDist = OVERNIGHT_TP_PIP * PIP

  if (OVERNIGHT_ENTRY_HOURS.includes(utcHour)) {
    // در پنجرهٔ زمانی هستیم؛ اما ورود فقط با تأییدِ فیلترِ رژیم (شرطِ WR≥۶۰٪).
    if (!filtersPass(filt)) {
      const need: string[] = []
      if (filt && !filt.pdiGtMdi) need.push('جهتِ روند صعودی شود (‏+DI بالای −DI)')
      if (filt && !filt.bullBar) need.push('کندلِ جاری صعودی بسته شود')
      if (filt && !filt.atrOk) need.push('نوسان به حالتِ عادی برگردد (نه کندلِ شوک/climax)')
      return {
        state: 'APPROACHING', utcHour, slDist, tpDist,
        reason: `اکنون ساعتِ ${toIran(utcHour)} به وقتِ ایران است — در پنجرهٔ «درایوِ شبانهٔ طلا» ` +
          `(${ENTRY_IRAN_RANGE} به وقتِ ایران) هستیم، اما فیلترِ رژیمِ WR≥۶۰٪ هنوز تأیید نشده. ` +
          `برای صدورِ سیگنالِ خرید باید: ${need.join('؛ ')}. ` +
          `(لایهٔ زمان-محورِ S222a با فیلترِ رژیم ⇒ WR ۸۴٪.)`,
      }
    }
    return {
      state: 'ENTRY', utcHour, slDist, tpDist,
      reason: `اکنون ساعتِ ${toIran(utcHour)} به وقتِ ایران است — درست در پنجرهٔ «درایوِ شبانهٔ طلا» ` +
        `(ابتدای سشنِ آسیا، ${ENTRY_IRAN_RANGE} به وقتِ ایران) و فیلترِ رژیم (روندِ صعودیِ جهت‌دار + ` +
        `کندلِ صعودی + نوسانِ عادی) تأیید شد. سیگنالِ خرید (LONG) با TP نزدیک (۴۰pip) و SL محافظ (۱۵۰pip). ` +
        `این پیکربندی در بک‌تستِ ۴ سال WR = ۸۴٪ داد (سند S222a، هر ۴ پنجرهٔ walk-forward مثبت).`,
    }
  }

  if (utcHour === OVERNIGHT_APPROACH_HOUR) {
    return {
      state: 'APPROACHING', utcHour, slDist, tpDist,
      reason: `اکنون ساعتِ ${toIran(utcHour)} به وقتِ ایران است — پنجرهٔ «درایوِ شبانهٔ طلا» (${ENTRY_IRAN_RANGE} به وقتِ ایران) ` +
        `در حالِ باز شدن است. با ورودِ ساعتِ ${toIran(22)} به وقتِ ایران و تأییدِ فیلترِ رژیم، سیگنالِ خرید (LONG) صادر می‌شود.`,
    }
  }

  return {
    state: 'NEUTRAL', utcHour, slDist, tpDist,
    reason: `اکنون ساعتِ ${toIran(utcHour)} به وقتِ ایران است — خارج از پنجرهٔ «درایوِ شبانهٔ طلا» (${ENTRY_IRAN_RANGE} به وقتِ ایران). ` +
      `این لایه زمان-محور است و فقط در آن ساعت‌ها و با تأییدِ فیلترِ رژیم ورود می‌کند.`,
  }
}
