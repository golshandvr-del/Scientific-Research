// ============================================================================
// لایهٔ «Pre-Holiday Drift» روی طلا (S547 — اثرِ Ariel 1990) — لنگرِ برون‌بازاری
// ----------------------------------------------------------------------------
// سندِ حکم: results/S547_PreHolidayDrift_Xauusd_MTF_rqs2_89_ACCEPT.md
//   داور: RQS2 v2.6 · پیش‌ثبت 9f36ee8f (قبل از هر عدد) · داده: ۱۵.۵۹ سال mt5_full
//   (2011-01-03 → 2026-08-07) · ۱۲/۱۲ کارت منتشر · صفر تیون · n_trials=24
//
//   | کارت | n | WR% | BE% | lift | z | RQS2 | حکم |
//   |---|---|---|---|---|---|---|---|
//   | M15 | 146 | 53.42 | 44.62 | +8.81 | 3.48 | ۸۴.۷ | ✅ ACCEPT (۱۱/۱۱) |
//   | M30 | 146 | 55.48 | 43.19 | +12.29 | 4.00 | ۸۹.۳ | ✅ ACCEPT (۱۱/۱۱) ← قله |
//   | H4 | 144 | 54.17 | 41.07 | +13.09 | 3.09 | ۸۱.۹ | ✅ ACCEPT (۱۱/۱۱) |
//   (H1 z=2.80 ⇒ REJECT · D1 z=0.15 ⇒ براکتِ ۳۴۹پیپی اثرِ یک‌روزه را می‌بلعد)
//   M20 هم ACCEPT شد (۸۹.۱) ولی کارتِ M20 در سایت وجود ندارد ⇒ وصل نمی‌شود.
//
// مکانیسم (نه صرفاً همبستگی): پیش از تعطیلیِ COMEX/NYSE عرضهٔ فروشندگان و ظرفیتِ
// پوشش‌ریسک کم می‌شود؛ پوششِ شورت و خریدِ محتاطانه درفتِ مثبتی با WR≈۵۵٪ در برابرِ
// پایهٔ ≈۳۹–۴۱٪ می‌سازد. این نخستین لایهٔ بلوکِ S540 است که از سد گذشت — هفت لایهٔ
// «ساختارِ درون‌بازاری» همه در سقفِ z≈۲.۲ مردند؛ تفاوتِ این یکی **لنگرِ قطعیِ
// برون‌بازاری (تقویم)** است. قانونِ S547: لبهٔ طلا در *زمان* است، نه در شکلِ کندل.
//
// ⚠️ **قیدِ هم‌رویدادی (سندِ §۸ + قانونِ S605).** هر سه کارتِ ACCEPT **همان ۱۴۶
//    روز** را معامله می‌کنند (رویداد روزانه است ⇒ n مستقل از تایم‌فریم). پس M15/
//    M30/H4 سه شاهدِ مستقل نیستند؛ سه *بدیلِ* یک رویدادند و «هم‌زمان معامله نشوند».
//    این قید در `strategy_registry.ts` به‌صورتِ داده ثبت شده (CROSS_CARD_ALTERNATES)،
//    نه فقط در این نثر — چون نثر هیچ‌چیز را اجرا نمی‌کند.
//
// همهٔ ساعت‌ها به وقتِ ایران (UTC+3:30) نمایش داده می‌شوند (User Note).
// ============================================================================

const PIP = 0.10                     // اندازهٔ pip طلا بر حسبِ قیمت

// هندسهٔ براکت — عیناً از قاعدهٔ منجمدِ سند: SL = ۱.۵×median(ATR100)، TP = ۱.۵×SL.
export const PRE_SL_ATR_MULT = 1.5
export const PRE_TP_RR = 1.5

// ---------------------------------------------------------------------------
// تقویمِ تعطیلاتِ بازارِ آمریکا — بازتولیدِ `USFederalHolidayCalendar`
// منهای Columbus/Veterans، بعلاوهٔ Good Friday (عیناً انتخابِ رانرِ S547).
// ---------------------------------------------------------------------------
// چرا قاعده‌محور و نه فهرستِ دستیِ تاریخ‌ها: فهرست در تاریخِ آخرینش منقضی می‌شود و
// آن‌وقت لایه **بی‌صدا** خاموش می‌شود — بدترین حالتِ خرابی، چون شبیهِ «سیگنال نیست»
// است نه شبیهِ خطا. قاعده برای هر سالِ آینده هم معتبر است.

/** روزِ هفته (۰=یکشنبه) برای یک تاریخِ UTC. */
function dow(y: number, m: number, d: number): number {
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay()
}

/** n-اُمین «روزِ هفتهٔ مشخص» در ماه (مثلاً سومین دوشنبهٔ ژانویه). */
function nthWeekday(y: number, m: number, weekday: number, n: number): number {
  const first = dow(y, m, 1)
  return 1 + ((weekday - first + 7) % 7) + (n - 1) * 7
}

/** آخرین «روزِ هفتهٔ مشخص» در ماه (مثلاً آخرین دوشنبهٔ مِی). */
function lastWeekday(y: number, m: number, weekday: number): number {
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate()
  const wl = dow(y, m, last)
  return last - ((wl - weekday + 7) % 7)
}

/**
 * قاعدهٔ جابه‌جاییِ تعطیلاتِ «تاریخِ ثابت» در تقویمِ فدرال: اگر شنبه شد ⇒ جمعهٔ
 * قبل، اگر یکشنبه شد ⇒ دوشنبهٔ بعد. (تعطیلاتِ «n-اُمین دوشنبه» نیازی ندارند.)
 */
function observed(y: number, m: number, d: number): [number, number, number] {
  const w = dow(y, m, d)
  if (w === 6) {                                   // شنبه ⇒ جمعهٔ قبل
    const dt = new Date(Date.UTC(y, m - 1, d - 1))
    return [dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate()]
  }
  if (w === 0) {                                   // یکشنبه ⇒ دوشنبهٔ بعد
    const dt = new Date(Date.UTC(y, m - 1, d + 1))
    return [dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate()]
  }
  return [y, m, d]
}

/** الگوریتمِ Gauss برای عیدِ پاکِ غربی ⇒ Good Friday = دو روز قبل. */
function easterMonthDay(y: number): [number, number] {
  const a = y % 19, b = Math.floor(y / 100), c = y % 100
  const d = Math.floor(b / 4), e = b % 4
  const f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4), k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const month = Math.floor((h + l - 7 * m + 114) / 31)
  const day = ((h + l - 7 * m + 114) % 31) + 1
  return [month, day]
}

const ymd = (y: number, m: number, d: number) =>
  `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`

/** مجموعهٔ تعطیلاتِ یک سال به شکلِ 'YYYY-MM-DD' (UTC). */
export function holidaysOfYear(y: number): Set<string> {
  const out = new Set<string>()
  const add = (m: number, d: number) => { const [yy, mm, dd] = observed(y, m, d); out.add(ymd(yy, mm, dd)) }

  add(1, 1)                                                     // New Year's Day
  out.add(ymd(y, 1, nthWeekday(y, 1, 1, 3)))                    // MLK — سومین دوشنبهٔ ژانویه
  out.add(ymd(y, 2, nthWeekday(y, 2, 1, 3)))                    // Presidents' — سومین دوشنبهٔ فوریه
  const [em, ed] = easterMonthDay(y)                            // Good Friday = پاک − ۲ روز
  const gf = new Date(Date.UTC(y, em - 1, ed - 2))
  out.add(ymd(gf.getUTCFullYear(), gf.getUTCMonth() + 1, gf.getUTCDate()))
  out.add(ymd(y, 5, lastWeekday(y, 5, 1)))                      // Memorial — آخرین دوشنبهٔ مِی
  if (y >= 2021) add(6, 19)                                     // Juneteenth — فدرال از ۲۰۲۱
  add(7, 4)                                                     // Independence Day
  out.add(ymd(y, 9, nthWeekday(y, 9, 1, 1)))                    // Labor — اولین دوشنبهٔ سپتامبر
  out.add(ymd(y, 11, nthWeekday(y, 11, 4, 4)))                  // Thanksgiving — چهارمین پنجشنبهٔ نوامبر
  add(12, 25)                                                   // Christmas
  return out
}

/** آیا این تاریخِ UTC تعطیلِ بازارِ آمریکا است؟ */
function isHoliday(dt: Date): boolean {
  const key = ymd(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate())
  return holidaysOfYear(dt.getUTCFullYear()).has(key)
}

/** روزِ کاریِ قبلی (شنبه/یکشنبه رد می‌شوند) — معادلِ `pd.offsets.BDay(1)` رو به عقب. */
function prevBDay(dt: Date): Date {
  const d = new Date(dt.getTime())
  do { d.setUTCDate(d.getUTCDate() - 1) } while (d.getUTCDay() === 0 || d.getUTCDay() === 6)
  return d
}

/** روزِ کاریِ بعدی. */
function nextBDay(dt: Date): Date {
  const d = new Date(dt.getTime())
  do { d.setUTCDate(d.getUTCDate() + 1) } while (d.getUTCDay() === 0 || d.getUTCDay() === 6)
  return d
}

/**
 * آیا `dt` یک «روزِ P» است؟ P = آخرین روزِ کاریِ **قبل** از یک تعطیلی.
 * عیناً منطقِ رانر: از تعطیلی یک روزِ کاری عقب می‌رویم و تا وقتی خودش تعطیل است
 * عقب‌تر می‌رویم (زنجیرهٔ تعطیلاتِ پشت‌سرهم مثلِ کریسمس/سالِ‌نو).
 */
export function isPreHolidayDay(dt: Date): boolean {
  if (dt.getUTCDay() === 0 || dt.getUTCDay() === 6) return false
  if (isHoliday(dt)) return false                  // خودِ روزِ تعطیل، روزِ P نیست
  let probe = nextBDay(dt)
  // اگر روزِ کاریِ بعدی تعطیل بود ⇒ امروز همان P است.
  if (!isHoliday(probe)) return false
  // و باید مطمئن شویم که «آخرین» روزِ کاریِ قبل از آن تعطیلی هستیم:
  let p = prevBDay(probe)
  while (isHoliday(p)) p = prevBDay(p)
  return p.getUTCFullYear() === dt.getUTCFullYear()
    && p.getUTCMonth() === dt.getUTCMonth()
    && p.getUTCDate() === dt.getUTCDate()
}

/** نامِ تعطیلیِ پیش‌رو (برای توضیحِ کاربر). */
export function upcomingHolidayName(dt: Date): string {
  const probe = nextBDay(dt)
  const y = probe.getUTCFullYear(), m = probe.getUTCMonth() + 1, d = probe.getUTCDate()
  const key = ymd(y, m, d)
  const table: [string, string][] = [
    [ymd(y, 1, 1), 'سالِ نو'],
    [ymd(y, 1, nthWeekday(y, 1, 1, 3)), 'روزِ مارتین لوتر کینگ'],
    [ymd(y, 2, nthWeekday(y, 2, 1, 3)), 'روزِ رؤسای جمهور'],
    [ymd(y, 5, lastWeekday(y, 5, 1)), 'روزِ یادبود'],
    [ymd(y, 6, 19), 'جون‌تینث'],
    [ymd(y, 7, 4), 'روزِ استقلال'],
    [ymd(y, 9, nthWeekday(y, 9, 1, 1)), 'روزِ کارگر'],
    [ymd(y, 11, nthWeekday(y, 11, 4, 4)), 'شکرگزاری'],
    [ymd(y, 12, 25), 'کریسمس'],
  ]
  for (const [k, name] of table) if (k === key) return name
  const [em, ed] = easterMonthDay(y)
  const gf = new Date(Date.UTC(y, em - 1, ed - 2))
  if (ymd(gf.getUTCFullYear(), gf.getUTCMonth() + 1, gf.getUTCDate()) === key) return 'جمعهٔ نیک'
  return 'تعطیلیِ بازارِ آمریکا'
}

export type PreState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface PreSignal {
  state: PreState
  isPreHoliday: boolean       // آیا امروز روزِ P است؟
  holidayName: string
  utcHour: number
  slDist: number
  tpDist: number
  reason: string
}

/**
 * ATR ساده (میانگینِ TR روی پنجرهٔ n) — فقط برای **اندازهٔ براکت**، نه برای
 * تصمیمِ ورود. سند: «ATR فقط برای اندازهٔ براکت (median کل)». اینجا median
 * روی پنجرهٔ اخیر گرفته می‌شود تا با مقیاسِ فعلیِ بازار هم‌خوان باشد.
 */
export function medianAtr(
  candles: { high: number; low: number; close: number }[],
  n = 100,
): number {
  if (candles.length < 2) return NaN
  const trs: number[] = []
  for (let i = 1; i < candles.length; i++) {
    const c = candles[i], p = candles[i - 1]
    trs.push(Math.max(c.high - c.low, Math.abs(c.high - p.close), Math.abs(c.low - p.close)))
  }
  const win = trs.slice(-n)
  if (win.length === 0) return NaN
  const s = [...win].sort((x, y) => x - y)
  const mid = Math.floor(s.length / 2)
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}

// ساعتِ UTC → «HH:MM به وقتِ ایران» (UTC+3:30 ثابت).
function toIran(utcHour: number): string {
  const total = ((utcHour * 60 + 210) % 1440 + 1440) % 1440
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

// پنجرهٔ ورود: سند می‌گوید ورود در **open روزِ P**. کارت‌ها درون‌روزی‌اند، پس
// ساعاتِ اولِ روزِ P پنجرهٔ ورود است (۰–۳ UTC) و پیش از آن «نزدیک‌شدن».
export const PRE_ENTRY_HOURS = [0, 1, 2, 3]
const PRE_IRAN_RANGE = `${toIran(0)}–${toIran(4)}`

/**
 * ارزیابیِ لایهٔ S547. `times` = timestampهای ثانیه‌ایِ کندل‌ها (آخرین = کندلِ جاری).
 *
 * نکتهٔ علّی: تقویمِ تعطیلات سال‌ها قبل معلوم است ⇒ هیچ نگاهِ به آینده‌ای وجود
 * ندارد. تنها ورودیِ بازاری، ATR برای اندازهٔ براکت است که از کندل‌های **گذشته**
 * گرفته می‌شود.
 */
export function computePreHoliday(
  times: number[],
  utcHour: number,
  candles: { high: number; low: number; close: number }[],
): PreSignal {
  const atr = medianAtr(candles, 100)
  const slDist = Number.isFinite(atr) ? atr * PRE_SL_ATR_MULT : NaN
  const tpDist = Number.isFinite(slDist) ? slDist * PRE_TP_RR : NaN

  if (times.length === 0) {
    return {
      state: 'NEUTRAL', isPreHoliday: false, holidayName: '—', utcHour,
      slDist, tpDist, reason: 'دادهٔ کافی برای تشخیصِ روزِ تقویمی نیست.',
    }
  }

  const now = new Date(times[times.length - 1] * 1000)
  const isPre = isPreHolidayDay(now)
  const hol = isPre ? upcomingHolidayName(now) : '—'

  // اگر ATR گرم نشده ⇒ نمی‌توان براکت ساخت. «نبودِ داده» نباید به سیگنال ترجمه شود.
  if (isPre && !Number.isFinite(tpDist)) {
    return {
      state: 'APPROACHING', isPreHoliday: true, holidayName: hol, utcHour, slDist, tpDist,
      reason: `امروز «روزِ پیش‌تعطیلات» (آخرین روزِ کاری پیش از ${hol}) است، `
        + 'اما تاریخچهٔ کافی برای محاسبهٔ اندازهٔ حد/هدف (ATR) موجود نیست ⇒ سیگنال صادر نمی‌شود.',
    }
  }

  if (isPre && PRE_ENTRY_HOURS.includes(utcHour)) {
    return {
      state: 'ENTRY', isPreHoliday: true, holidayName: hol, utcHour, slDist, tpDist,
      reason: `امروز آخرین روزِ کاریِ بازارِ آمریکا پیش از **${hol}** است. `
        + `اثرِ مستندِ «درفتِ پیش‌تعطیلات» (Ariel 1990) روی طلا با ۱۵.۶ سال داده تأیید شده: `
        + `نرخِ بردِ ≈۵۵٪ در برابرِ پایهٔ ≈۳۹–۴۳٪. سازوکار: پیش از بسته‌شدنِ COMEX/NYSE `
        + `عرضهٔ فروشندگان و ظرفیتِ پوششِ ریسک کم می‌شود و پوششِ شورت درفتِ مثبت می‌سازد. `
        + `پنجرهٔ ورود ساعاتِ ${PRE_IRAN_RANGE} به وقتِ ایران (ابتدای روزِ P) است.`,
    }
  }

  if (isPre) {
    return {
      state: 'APPROACHING', isPreHoliday: true, holidayName: hol, utcHour, slDist, tpDist,
      reason: `امروز روزِ پیش‌تعطیلاتِ ${hol} است، اما ساعتِ ورود گذشته است. `
        + `پنجرهٔ این لایه ابتدای روزِ P (${PRE_IRAN_RANGE} به وقتِ ایران) است.`,
    }
  }

  return {
    state: 'NEUTRAL', isPreHoliday: false, holidayName: '—', utcHour, slDist, tpDist,
    reason: 'امروز آخرین روزِ کاری پیش از تعطیلیِ بازارِ آمریکا نیست ⇒ این لایه خنثی است.',
  }
}
