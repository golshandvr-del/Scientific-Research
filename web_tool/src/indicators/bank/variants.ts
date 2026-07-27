// ============================================================================
// indicators/bank/variants.ts — دستهٔ بسطِ پارامتریِ علمی (Variant Expansion)
// ----------------------------------------------------------------------------
// طبقِ قانونِ «همه‌چیز شناور است» و اصلِ variant-instancing در TA-Lib/pandas-ta،
// هر خانوادهٔ اندیکاتورِ تک-پارامتری در چند دورهٔ **غیررند** (فیبوناچی و لوکاس، متناسب
// با تایم‌فریم‌های XAUUSD: M5/M15/H1/H4/D1) به یک instanceِ مجزا تبدیل می‌شود.
// این مستقیماً اشتباهِ رایج #۷ (اجتناب از اعدادِ رند مثل 50/100/200) را رفع می‌کند.
// همهٔ variantها active:false ثبت می‌شوند و فقط با صداکردنِ یک لایه فعال می‌شوند.
// منطق کاملاً verbatim از bank.ts.
// ============================================================================

import * as I from '../../indicators'
import {
  makeKit, closes, highs, lows, emaArr, rmaArr, wmaArr, smaArr, stdArr, trArr,
  NaNArr, asSeries, highest, lowest, FIB_PERIODS, LUCAS_PERIODS,
} from './kit'

const K = makeKit()
const { expandPeriodFamily } = K

// خانواده‌های میانگین (روی close) — دوره‌های فیبوناچی
expandPeriodFamily('sma_fib', 'trend', 'composite', 'میانگینِ ساده', (per) => (c) => asSeries(smaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('ema_fib', 'trend', 'composite', 'میانگینِ نمایی', (per) => (c) => asSeries(emaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('wma_fib', 'trend', 'composite', 'میانگینِ وزنی', (per) => (c) => asSeries(wmaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('rma_fib', 'trend', 'composite', 'میانگینِ وایلدر', (per) => (c) => asSeries(rmaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('hma_fib', 'trend', 'composite', 'میانگینِ هال', (per) => (c) => {
  const x = closes(c), half = wmaArr(x, Math.max(1, Math.floor(per / 2))), full = wmaArr(x, per)
  return asSeries(wmaArr(half.map((v, i) => 2 * v - full[i]), Math.max(1, Math.floor(Math.sqrt(per)))))
}, FIB_PERIODS)

// خانوادهٔ RSI — دوره‌های لوکاس (غیررند)
expandPeriodFamily('rsi_lucas', 'momentum', 'composite', 'RSI', (per) => (c) => asSeries(I.rsi(closes(c), per) as unknown as number[]), LUCAS_PERIODS)

// خانوادهٔ CMO — فیبوناچی
expandPeriodFamily('cmo_fib', 'momentum', 'composite', 'مومنتومِ چاند', (per) => (c) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per; i < n; i++) { let up = 0, dn = 0; for (let k = 0; k < per; k++) { const d = x[i - k] - x[i - k - 1]; if (d > 0) up += d; else dn -= d } out[i] = (up + dn) ? (100 * (up - dn)) / (up + dn) : 0 }
  return asSeries(out)
}, FIB_PERIODS)

// خانوادهٔ ROC — فیبوناچی
expandPeriodFamily('roc_fib', 'momentum', 'composite', 'نرخِ تغییر', (per) => (c) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per; i < n; i++) out[i] = x[i - per] ? (100 * (x[i] - x[i - per])) / x[i - per] : NaN
  return asSeries(out)
}, FIB_PERIODS)

// خانوادهٔ std (نوسان) — فیبوناچی
expandPeriodFamily('std_fib', 'volatility', 'composite', 'انحرافِ معیار', (per) => (c) => asSeries(stdArr(closes(c), per)), FIB_PERIODS)

// خانوادهٔ BIAS — فیبوناچی
expandPeriodFamily('bias_fib', 'momentum', 'composite', 'نرخِ انحراف (乖离)', (per) => (c) => {
  const x = closes(c), s = smaArr(x, per)
  return asSeries(x.map((v, i) => (s[i] ? (100 * (v - s[i])) / s[i] : NaN)))
}, FIB_PERIODS)

// خانوادهٔ Kaufman ER — لوکاس
expandPeriodFamily('er_lucas', 'composite', 'composite', 'نسبتِ کاراییِ کافمن', (per) => (c) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per; i < n; i++) { const ch = Math.abs(x[i] - x[i - per]); let v = 0; for (let k = 0; k < per; k++) v += Math.abs(x[i - k] - x[i - k - 1]); out[i] = v ? ch / v : 0 }
  return asSeries(out)
}, LUCAS_PERIODS)

// خانوادهٔ z-score — فیبوناچی
expandPeriodFamily('zscore_fib', 'statistical', 'composite', 'امتیازِ Z قیمت', (per) => (c) => {
  const x = closes(c), s = smaArr(x, per), sd = stdArr(x, per)
  return asSeries(x.map((v, i) => (sd[i] ? (v - s[i]) / sd[i] : NaN)))
}, FIB_PERIODS)

// خانوادهٔ WR — فیبوناچی
expandPeriodFamily('wr_fib', 'momentum', 'composite', 'ویلیامز %R', (per) => (c) => {
  const h = highs(c), l = lows(c), x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per - 1; i < n; i++) { const hh = highest(h, i, per), ll = lowest(l, i, per); out[i] = (hh - ll) ? (100 * (hh - x[i])) / (hh - ll) : 50 }
  return asSeries(out)
}, FIB_PERIODS)

// بسطِ خانواده‌های تک-پارامتریِ بیشتر (برای پوششِ کاملِ بانک)
expandPeriodFamily('dema_fib', 'trend', 'composite', 'EMA دوگانه', (per) => (c) => { const e1 = emaArr(closes(c), per), e2 = emaArr(e1, per); return asSeries(e1.map((v, i) => 2 * v - e2[i])) }, FIB_PERIODS)
expandPeriodFamily('tema_fib', 'trend', 'composite', 'EMA سه‌گانه', (per) => (c) => { const e1 = emaArr(closes(c), per), e2 = emaArr(e1, per), e3 = emaArr(e2, per); return asSeries(e1.map((v, i) => 3 * v - 3 * e2[i] + e3[i])) }, FIB_PERIODS)
expandPeriodFamily('mom_fib', 'momentum', 'composite', 'مومنتومِ خام', (per) => (c) => { const x = closes(c), n = x.length, out = NaNArr(n); for (let i = per; i < n; i++) out[i] = x[i] - x[i - per]; return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('dpo_fib', 'momentum', 'composite', 'اسیلاتورِ بدونِ‌روند', (per) => (c) => { const x = closes(c), s = smaArr(x, per), n = x.length, out = NaNArr(n), sh = Math.floor(per / 2) + 1; for (let i = 0; i < n; i++) if (i - sh >= 0 && Number.isFinite(s[i - sh])) out[i] = x[i] - s[i - sh]; return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('trix_fib', 'momentum', 'composite', 'تریکس', (per) => (c) => { const e1 = emaArr(closes(c), per), e2 = emaArr(e1, per), e3 = emaArr(e2, per), n = e3.length, out = NaNArr(n); for (let i = 1; i < n; i++) out[i] = e3[i - 1] ? (100 * (e3[i] - e3[i - 1])) / e3[i - 1] : NaN; return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('psy_fib', 'momentum', 'composite', 'خطِ روانی', (per) => (c) => { const x = closes(c), n = x.length, out = NaNArr(n); for (let i = per; i < n; i++) { let up = 0; for (let k = 0; k < per; k++) if (x[i - k] > x[i - k - 1]) up++; out[i] = (100 * up) / per } return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('natr_fib', 'volatility', 'composite', 'ATR نرمال‌شده', (per) => (c) => { const x = closes(c), a = rmaArr(trArr(c), per); return asSeries(a.map((v, i) => (x[i] ? (100 * v) / x[i] : NaN))) }, FIB_PERIODS)
expandPeriodFamily('atr_fib', 'volatility', 'composite', 'ATR وایلدر', (per) => (c) => asSeries(rmaArr(trArr(c), per)), FIB_PERIODS)
expandPeriodFamily('chop_fib', 'volatility', 'composite', 'چاپینس', (per) => (c) => { const n = c.length, tr = trArr(c), h = highs(c), l = lows(c), out = NaNArr(n); for (let i = per; i < n; i++) { let s = 0; for (let k = 0; k < per; k++) s += tr[i - k] || 0; const rng = highest(h, i, per) - lowest(l, i, per); out[i] = rng > 0 ? (100 * Math.log10(s / rng)) / Math.log10(per) : NaN } return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('cg_fib', 'cycle', 'composite', 'مرکزِ ثقلِ اِهلرز', (per) => (c) => { const x = closes(c), n = x.length, out = NaNArr(n); for (let i = per - 1; i < n; i++) { let num = 0, den = 0; for (let k = 0; k < per; k++) { num += (1 + k) * x[i - k]; den += x[i - k] } out[i] = den ? -num / den + (per + 1) / 2 : 0 } return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('ssf_fib', 'cycle', 'composite', 'سوپر-اسموترِ اِهلرز', (per) => (c) => { const x = closes(c), n = x.length, out = NaNArr(n); const a = Math.exp(-1.414 * Math.PI / per), b = 2 * a * Math.cos(1.414 * Math.PI / per), c2 = b, c3 = -a * a, c1 = 1 - c2 - c3; for (let i = 0; i < n; i++) { if (i < 2) { out[i] = x[i]; continue } out[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2] } return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('corr_t_fib', 'statistical', 'composite', 'همبستگیِ قیمت-زمان', (per) => (c) => { const x = closes(c), n = x.length, out = NaNArr(n); for (let i = per - 1; i < n; i++) { let sx = 0, sy = 0, sxy = 0, sxx = 0, syy = 0; for (let k = 0; k < per; k++) { const t = k, y = x[i - (per - 1 - k)]; sx += t; sy += y; sxy += t * y; sxx += t * t; syy += y * y } const num = per * sxy - sx * sy, den = Math.sqrt((per * sxx - sx * sx) * (per * syy - sy * sy)); out[i] = den ? num / den : 0 } return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('r2_fib', 'statistical', 'composite', 'ضریبِ تعیین R²', (per) => (c) => { const x = closes(c), n = x.length, out = NaNArr(n); for (let i = per - 1; i < n; i++) { let sx = 0, sy = 0, sxy = 0, sxx = 0, syy = 0; for (let k = 0; k < per; k++) { const t = k, y = x[i - (per - 1 - k)]; sx += t; sy += y; sxy += t * y; sxx += t * t; syy += y * y } const num = per * sxy - sx * sy, den = (per * sxx - sx * sx) * (per * syy - sy * sy), r = den ? num / Math.sqrt(den) : 0; out[i] = r * r } return asSeries(out) }, FIB_PERIODS)
expandPeriodFamily('laguerre_g', 'cycle', 'composite', 'فیلترِ لاگر (گاما متغیر)', (per) => (c) => { const x = closes(c), n = x.length, out = NaNArr(n); const g = Math.min(0.95, 1 - 2 / (per + 1)); let L0 = 0, L1 = 0, L2 = 0, L3 = 0; for (let i = 0; i < n; i++) { const p0 = L0, p1 = L1, p2 = L2; L0 = (1 - g) * x[i] + g * L0; L1 = -g * L0 + p0 + g * L1; L2 = -g * L1 + p1 + g * L2; L3 = -g * L2 + p2 + g * L3; out[i] = (L0 + 2 * L1 + 2 * L2 + L3) / 6 } return asSeries(out) }, LUCAS_PERIODS)
expandPeriodFamily('donchmid_fib', 'trend', 'composite', 'میانیِ دونچیان', (per) => (c) => { const h = highs(c), l = lows(c), n = c.length, out = NaNArr(n); for (let i = per - 1; i < n; i++) out[i] = (highest(h, i, per) + lowest(l, i, per)) / 2; return asSeries(out) }, FIB_PERIODS)

export const VARIANTS_ITEMS = K.items
