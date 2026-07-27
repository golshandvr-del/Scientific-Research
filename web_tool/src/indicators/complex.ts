// ============================================================================
// indicators/complex.ts — اندیکاتورهای پیچیدهٔ کمیاب  [webplan P3 · اشتباهِ رایج #۳]
// ----------------------------------------------------------------------------
// webplan §۳ (گره ۲) صریحاً می‌گوید خانهٔ رسمیِ اندیکاتورهای کمیاب اینجاست:
//   Alligator (Bill Williams)، GMMA/Ribbon، Ichimoku، Vortex، Kaufman-ER، …
// این مستقیماً علیهِ «اشتباهِ رایجِ #۳» است: «تمرکز روی چند اندیکاتور ساده مثل ma
// و غفلت از اندیکاتورهای فوق‌العادهٔ پیچیده (مثل alligator)».
//
// همه بدونِ look-ahead: فقط از دادهٔ تا اندیسِ i استفاده می‌شود.
// این فایل *افزودنی* است (P3 Strangler Fig)؛ منطقِ تصمیمِ فعلی را تغییر نمی‌دهد.
// ============================================================================

import type { Candle } from '../indicators'

const NaNArr = (n: number) => new Array<number>(n).fill(NaN)

// ---------------------------------------------------------------------------
// SMMA (Smoothed Moving Average) — پایهٔ ریاضیِ Alligator. معادلِ Wilder:
//   SMMA[i] = (SMMA[i-1]×(p-1) + x[i]) / p ؛ بذرِ اولیه = میانگینِ p مقدارِ اول.
// ---------------------------------------------------------------------------
export function smma(x: number[], period: number): number[] {
  const n = x.length
  const out = NaNArr(n)
  if (n < period) return out
  let sum = 0
  for (let i = 0; i < period; i++) sum += x[i]
  let prev = sum / period
  out[period - 1] = prev
  for (let i = period; i < n; i++) {
    prev = (prev * (period - 1) + x[i]) / period
    out[i] = prev
  }
  return out
}

// شیفتِ آرایه به جلو (forward) با n واحد — معادلِ shift مثبتِ متاتریدر برای Alligator.
// out[i] = x[i-shift]؛ ابتدای سری NaN. این «فک‌های آینده» را روی کندلِ جاری می‌آورد
// به‌گونه‌ای که فقط از دادهٔ گذشته ساخته شده باشد (forward-safe).
function shiftFwd(x: number[], shift: number): number[] {
  const n = x.length
  const out = NaNArr(n)
  for (let i = shift; i < n; i++) out[i] = x[i - shift]
  return out
}

// ---------------------------------------------------------------------------
// Alligator (Bill Williams) — سه SMMA روی «median price» با شیفتِ رو به جلو:
//   Jaw   (فک)  = SMMA(13) shift +8   (آبی)
//   Teeth (دندان)= SMMA(8)  shift +5   (قرمز)
//   Lips  (لب)  = SMMA(5)  shift +3   (سبز)
// median price = (high+low)/2. کاربردِ کیفی: چیدمانِ باز (روند) در برابرِ درهم‌تنیده
// (خوابِ تمساح = رنج). مرجع: «Trading Chaos», Bill Williams.
// ---------------------------------------------------------------------------
export interface AlligatorOut { jaw: number[]; teeth: number[]; lips: number[] }
export function alligator(c: Candle[], jawP = 13, jawS = 8, teethP = 8, teethS = 5, lipsP = 5, lipsS = 3): AlligatorOut {
  const median = c.map(k => (k.high + k.low) / 2)
  return {
    jaw: shiftFwd(smma(median, jawP), jawS),
    teeth: shiftFwd(smma(median, teethP), teethS),
    lips: shiftFwd(smma(median, lipsP), lipsS),
  }
}

/**
 * «gatorState»: کمّی‌سازیِ وضعیتِ تمساح در آخرین کندل.
 *   +1 = بیدارِ صعودی (lips>teeth>jaw و باز شونده)، −1 = بیدارِ نزولی، 0 = خواب/درهم.
 * spread = (max−min خطوط)/price ⇒ بازبودنِ دهانِ تمساح (قدرتِ روند).
 */
export function gatorState(c: Candle[]): { state: number; spread: number } {
  const { jaw, teeth, lips } = alligator(c)
  const i = c.length - 1
  const j = jaw[i], t = teeth[i], l = lips[i], p = c[i].close
  if (![j, t, l, p].every(Number.isFinite) || p === 0) return { state: 0, spread: NaN }
  const hi = Math.max(j, t, l), lo = Math.min(j, t, l)
  const spread = (hi - lo) / p
  let state = 0
  if (l > t && t > j) state = 1
  else if (l < t && t < j) state = -1
  return { state, spread }
}

// ---------------------------------------------------------------------------
// GMMA / Ribbon — مجموعه‌ای از EMAها با دوره‌های فیبوناچی. هندسه‌اش «قدرت/جهتِ
// روند از واگرایی/همگرایی» را می‌دهد (بازتولیدِ engine/ma_ribbon.py، تک-تایم‌فریم).
//   order = +1 اگر کاملاً صعودی مرتب، −1 اگر کاملاً نزولی، کسری بینِ آن‌ها.
//   spread = (max−min EMAها)/price (واگرایی = روندِ قوی).
// ---------------------------------------------------------------------------
export const RIBBON_PERIODS = [8, 13, 21, 34, 55, 89, 144]
function emaLocal(x: number[], period: number): number[] {
  const out = NaNArr(x.length); const alpha = 2 / (period + 1); let prev = NaN
  for (let i = 0; i < x.length; i++) {
    const v = x[i]; if (isNaN(v)) { out[i] = prev; continue }
    prev = isNaN(prev) ? v : alpha * v + (1 - alpha) * prev; out[i] = prev
  }
  return out
}
export function ribbonState(close: number[], periods: number[] = RIBBON_PERIODS): { order: number; spread: number } {
  const i = close.length - 1
  const vals: number[] = []
  for (const p of periods) { const e = emaLocal(close, p); vals.push(e[i]) }
  if (!vals.every(Number.isFinite) || close[i] === 0) return { order: NaN, spread: NaN }
  // order: چند جفتِ مجاورِ متوالی به‌ترتیبِ صعودی‌اند؟ (کوتاه بالای بلند)
  let asc = 0, desc = 0
  for (let k = 0; k < vals.length - 1; k++) {
    if (vals[k] > vals[k + 1]) asc++
    else if (vals[k] < vals[k + 1]) desc++
  }
  const total = vals.length - 1
  const order = (asc - desc) / total   // +1 کاملاً صعودی، −1 کاملاً نزولی
  const spread = (Math.max(...vals) - Math.min(...vals)) / close[i]
  return { order, spread }
}

// ---------------------------------------------------------------------------
// Ichimoku Kinko Hyo — forward-safe (بازتولیدِ engine/ichimoku.py، بدونِ look-ahead).
//   Tenkan = (HH9  + LL9 )/2 ,  Kijun = (HH26 + LL26)/2
//   spanA_raw = (Tenkan+Kijun)/2 , spanB_raw = (HH52+LL52)/2  (ساخته از دادهٔ تا i)
//   ابرِ قابل‌مشاهده در i: spanA/spanB که از i-shift شیفت شده‌اند (forward-safe).
// ---------------------------------------------------------------------------
export interface IchimokuOut {
  tenkan: number[]; kijun: number[]
  spanA: number[]; spanB: number[]           // ابرِ قابل‌مشاهده در i (شیفت‌شده)
  spanARaw: number[]; spanBRaw: number[]      // خام (برای رنگِ آیندهٔ ابر)
  cloudTop: number[]; cloudBot: number[]
}
function rollHH(high: number[], p: number): number[] {
  const out = NaNArr(high.length)
  for (let i = p - 1; i < high.length; i++) { let m = -Infinity; for (let k = i - p + 1; k <= i; k++) if (high[k] > m) m = high[k]; out[i] = m }
  return out
}
function rollLL(low: number[], p: number): number[] {
  const out = NaNArr(low.length)
  for (let i = p - 1; i < low.length; i++) { let m = Infinity; for (let k = i - p + 1; k <= i; k++) if (low[k] < m) m = low[k]; out[i] = m }
  return out
}
export function ichimoku(c: Candle[], tenkanP = 9, kijunP = 26, senkouBP = 52, shift = 26): IchimokuOut {
  const high = c.map(k => k.high), low = c.map(k => k.low)
  const tenkan = rollHH(high, tenkanP).map((h, i) => (h + rollLL(low, tenkanP)[i]) / 2)
  // بازمحاسبهٔ کارآمد (یک‌بار):
  const hh9 = rollHH(high, tenkanP), ll9 = rollLL(low, tenkanP)
  const hh26 = rollHH(high, kijunP), ll26 = rollLL(low, kijunP)
  const hh52 = rollHH(high, senkouBP), ll52 = rollLL(low, senkouBP)
  const n = c.length
  const tk = NaNArr(n), kj = NaNArr(n), spanARaw = NaNArr(n), spanBRaw = NaNArr(n)
  for (let i = 0; i < n; i++) {
    tk[i] = (hh9[i] + ll9[i]) / 2
    kj[i] = (hh26[i] + ll26[i]) / 2
    spanARaw[i] = (tk[i] + kj[i]) / 2
    spanBRaw[i] = (hh52[i] + ll52[i]) / 2
  }
  const spanA = shiftFwd(spanARaw, shift)
  const spanB = shiftFwd(spanBRaw, shift)
  const cloudTop = NaNArr(n), cloudBot = NaNArr(n)
  for (let i = 0; i < n; i++) {
    if (Number.isFinite(spanA[i]) && Number.isFinite(spanB[i])) {
      cloudTop[i] = Math.max(spanA[i], spanB[i]); cloudBot[i] = Math.min(spanA[i], spanB[i])
    }
  }
  return { tenkan: tk, kijun: kj, spanA, spanB, spanARaw, spanBRaw, cloudTop, cloudBot }
}

/** موقعیتِ قیمت نسبت به ابرِ ایچیموکو در آخرین کندل: +1 بالای ابر، −1 زیرِ ابر، 0 داخلِ ابر. */
export function ichimokuCloudPos(c: Candle[]): number {
  const ich = ichimoku(c)
  const i = c.length - 1
  const p = c[i].close, top = ich.cloudTop[i], bot = ich.cloudBot[i]
  if (![p, top, bot].every(Number.isFinite)) return NaN
  if (p > top) return 1
  if (p < bot) return -1
  return 0
}
