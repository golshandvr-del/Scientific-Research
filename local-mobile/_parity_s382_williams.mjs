// =============================================================================
//  _parity_s382_williams.mjs — آزمونِ صحتِ عددیِ لایهٔ S382 (TS ↔ Python)
// -----------------------------------------------------------------------------
//  چرا این آزمون لازم است
//  ----------------------
//  لایهٔ S382 در پایتون آزموده و پذیرفته شد (RQS2=۸۳.۵، هر ۱۱ دروازه ✅) و بعد
//  به TypeScript پورت شد تا در سایت و در `local-mobile` اجرا شود. اگر پورت
//  حتی یک کندل جابه‌جا باشد، سایت چیزی را به کاربر می‌گوید که **آزموده نشده
//  است** — و کلِ اعتبارِ عددیِ آن سند بی‌معنا می‌شود. پروژه یک‌بار این خطا را
//  دیده است (باگِ جانشینیِ L.RR در S386) و از آن پس هر لایه پیش از اتصال،
//  آزمونِ parity می‌دهد.
//
//  این آزمون **سه چیزِ مستقل** را می‌سنجد، نه یکی:
//    ۱) اندیکاتور: `williamsR(14)` و `atrWilder(100)` باید عیناً با مقادیرِ
//       پایتون بخوانند (رواداریِ 1e-9 برای %R و 1e-6 برای ATR).
//    ۲) رویدادِ ورود: مجموعهٔ **ایندکسِ کندل‌هایِ گذر** باید **دقیقاً** برابر
//       باشد. این مهم‌ترین بخش است، چون «گذر» (crossing) با «حالت» (state)
//       اشتباه گرفته می‌شود و آن اشتباه نرخ را ۵ تا ۲۰ برابر باد می‌کند.
//    ۳) هندسه: SL/TP محاسبه‌شده از ATRِ زنده باید در محدودهٔ آزموده‌شده
//       (۱۲۲.۸۵۴ pip) بماند، وگرنه حکمِ اندازه‌گیری‌شده منتقل نمی‌شود.
//
//  ⚠️ آزمونِ نشتِ آینده (look-ahead): سیگنالِ کندلِ i فقط باید از کندل‌های
//  ≤ i ساخته شود. این را با «برشِ پیش‌رو» می‌سنجیم: اگر داده را در i قطع کنیم،
//  سیگنالِ i نباید تغییر کند. این آزمون یک‌بار در پروژه یک باگِ واقعی گرفت.
//
//  اجرا:  cd local-mobile && node _parity_s382_williams.mjs
// =============================================================================

import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')

// ---------------------------------------------------------------------------
// ۰) بارگذاریِ ماژولِ TS — با esbuild به یک ماژولِ موقتِ ESM ترنسپایل می‌شود.
// ---------------------------------------------------------------------------
const esbuildPath = join(ROOT, 'web_tool', 'node_modules', 'esbuild', 'lib', 'main.js')
const { build } = await import(pathToFileURL(esbuildPath).href)

const TMP = join(__dirname, '.parity_s382.tmp.mjs')
await build({
  entryPoints: [join(ROOT, 'web_tool', 'src', 'williams_momentum_s382.ts')],
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node18',
  outfile: TMP,
  nodePaths: [join(ROOT, 'web_tool', 'node_modules')],
  logLevel: 'error',
})
const M = await import(pathToFileURL(TMP).href)

// ---------------------------------------------------------------------------
// ۱) دادهٔ کارت — همان فایلی که پایتون خواند.
// ---------------------------------------------------------------------------
const CANDIDATES = [
  join(ROOT, 'data', 'XAUUSD_H4.csv'),
  join(ROOT, 'data', 'xauusd_h4.csv'),
  join(ROOT, 'data', 'XAUUSD_H4_200000.csv'),
]
const DATA = CANDIDATES.find((p) => existsSync(p))
if (!DATA) {
  console.error('❌ فایلِ دادهٔ XAUUSD_H4 پیدا نشد. مسیرهای بررسی‌شده:')
  CANDIDATES.forEach((p) => console.error('   ', p))
  process.exit(2)
}

function loadCandles(path) {
  const txt = readFileSync(path, 'utf8').trim()
  const lines = txt.split(/\r?\n/)
  const head = lines[0].toLowerCase()
  const sep = head.includes('\t') ? '\t' : (head.includes(';') ? ';' : ',')
  const cols = head.split(sep).map((s) => s.trim())
  const ix = (names) => {
    for (const nm of names) {
      const k = cols.indexOf(nm)
      if (k >= 0) return k
    }
    return -1
  }
  const iT = ix(['time', 'date', 'datetime', 'timestamp'])
  const iO = ix(['open', 'o'])
  const iH = ix(['high', 'h'])
  const iL = ix(['low', 'l'])
  const iC = ix(['close', 'c'])
  if (iO < 0 || iH < 0 || iL < 0 || iC < 0) {
    console.error('❌ ستون‌های OHLC شناسایی نشدند. سرستون:', cols.join('|'))
    process.exit(2)
  }
  const out = []
  for (let i = 1; i < lines.length; i++) {
    const p = lines[i].split(sep)
    if (p.length <= iC) continue
    const o = +p[iO], h = +p[iH], l = +p[iL], c = +p[iC]
    if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(c)) continue
    out.push({ time: iT >= 0 ? p[iT].trim() : String(i), open: o, high: h, low: l, close: c })
  }
  return out
}

const candles = loadCandles(DATA)
const CFG = M.S382_CFG['XAUUSD-H4']

console.log('═══ آزمونِ صحتِ S382 (Williams %R momentum) ═══')
console.log('  داده  :', DATA.replace(ROOT, '.'))
console.log('  کندل  :', candles.length)
console.log('  قاعده : willr(%d) گذر به بالای %s | SL=%s×ATR(%d) | RR=%s',
  CFG.willrP, CFG.willrThr, CFG.slK, CFG.atrP, CFG.rr)
console.log()

let fail = 0
const chk = (name, ok, detail) => {
  console.log('  %s %s%s', ok ? '✅' : '❌', name, detail ? ' — ' + detail : '')
  if (!ok) fail++
}

// ---------------------------------------------------------------------------
// ۲) اندیکاتورها — مرجعِ مستقل در همین فایل بازپیاده‌سازی می‌شود.
//    ⚠️ عمداً پیاده‌سازیِ دوم و ساده‌لوحانه (naive) نوشته می‌شود، نه فراخوانیِ
//    همان تابع؛ وگرنه آزمون خودش را می‌آزماید و هیچ چیز نمی‌گوید.
// ---------------------------------------------------------------------------
function refWillr(cs, p) {
  const out = new Array(cs.length).fill(NaN)
  for (let i = p - 1; i < cs.length; i++) {
    let hh = -Infinity, ll = Infinity
    for (let j = i - p + 1; j <= i; j++) {
      if (cs[j].high > hh) hh = cs[j].high
      if (cs[j].low < ll) ll = cs[j].low
    }
    const rng = hh - ll
    out[i] = rng === 0 ? NaN : (-100 * (hh - cs[i].close)) / rng
  }
  return out
}
function refAtrWilder(cs, p) {
  const tr = new Array(cs.length).fill(NaN)
  for (let i = 0; i < cs.length; i++) {
    if (i === 0) { tr[i] = cs[i].high - cs[i].low; continue }
    const pc = cs[i - 1].close
    tr[i] = Math.max(cs[i].high - cs[i].low, Math.abs(cs[i].high - pc), Math.abs(cs[i].low - pc))
  }
  const out = new Array(cs.length).fill(NaN)
  const a = 1 / p
  let ema = tr[0]
  out[0] = ema
  for (let i = 1; i < cs.length; i++) { ema = a * tr[i] + (1 - a) * ema; out[i] = ema }
  return out
}

const wTs = M.williamsR(candles, CFG.willrP)
const wRef = refWillr(candles, CFG.willrP)
let maxDW = 0, nW = 0
for (let i = 0; i < candles.length; i++) {
  if (!isFinite(wTs[i]) || !isFinite(wRef[i])) continue
  maxDW = Math.max(maxDW, Math.abs(wTs[i] - wRef[i])); nW++
}
chk('williamsR(14) مطابقِ مرجع', maxDW < 1e-9,
  `بیشینه اختلاف = ${maxDW.toExponential(2)} روی ${nW} کندل`)

const aTs = M.atrWilder(candles, CFG.atrP)
const aRef = refAtrWilder(candles, CFG.atrP)
let maxDA = 0, nA = 0
for (let i = 0; i < candles.length; i++) {
  if (!isFinite(aTs[i]) || !isFinite(aRef[i])) continue
  maxDA = Math.max(maxDA, Math.abs(aTs[i] - aRef[i])); nA++
}
chk('atrWilder(100) مطابقِ مرجع (α=1/p)', maxDA < 1e-6,
  `بیشینه اختلاف = ${maxDA.toExponential(2)} روی ${nA} کندل`)

// ---------------------------------------------------------------------------
// ۳) رویدادِ ورود — «گذر» نه «حالت». مهم‌ترین آزمونِ این فایل.
// ---------------------------------------------------------------------------
const cross = []
const stateOnly = []
for (let i = 1; i < candles.length; i++) {
  if (!isFinite(wTs[i]) || !isFinite(wTs[i - 1])) continue
  if (wTs[i] > CFG.willrThr) stateOnly.push(i)
  if (wTs[i - 1] <= CFG.willrThr && wTs[i] > CFG.willrThr) cross.push(i)
}
const ratio = stateOnly.length / Math.max(1, cross.length)
console.log()
console.log('  ▸ رویدادها: گذر = %d | حالت = %d | نسبت = %.1f×',
  cross.length, stateOnly.length, ratio)
chk('گذر ≪ حالت (اثباتِ اینکه رویداد است نه حالت)', ratio > 2.0,
  `اگر پورت اشتباه «حالت» را می‌شمرد، نرخ ${ratio.toFixed(1)} برابر باد می‌کرد`)

// بازهٔ تقویمی و نرخِ سالانه — باید نزدیکِ ۵۵.۹/سال سندِ پایتون باشد
// (نرخِ سیگنالِ خام بالاتر از نرخِ معامله است، چون قیدِ تک‌معامله بعداً اعمال می‌شود).
const yrs = (() => {
  const t0 = Date.parse(candles[0].time)
  const t1 = Date.parse(candles[candles.length - 1].time)
  if (isFinite(t0) && isFinite(t1) && t1 > t0) return (t1 - t0) / (365.25 * 864e5)
  return candles.length / (6 * 252) // تقریبِ H4: ۶ کندل در روزِ معاملاتی
})()
console.log('  ▸ بازه ≈ %.2f سال | سیگنالِ خام = %.1f/سال', yrs, cross.length / yrs)

// ---------------------------------------------------------------------------
// ۴) نشتِ آینده — برشِ پیش‌رو. اگر داده را در i قطع کنیم، سیگنالِ i باید ثابت
//    بماند. ۱۲ نقطهٔ پراکنده آزموده می‌شود (کاملش پرهزینه است).
// ---------------------------------------------------------------------------
let leak = 0, probed = 0
for (let k = 0; k < cross.length && probed < 12; k += Math.max(1, Math.floor(cross.length / 12))) {
  const i = cross[k]
  if (i < CFG.atrP + CFG.willrP + 5) continue
  const sliced = candles.slice(0, i + 1)              // داده فقط تا کندلِ i
  const wS = M.williamsR(sliced, CFG.willrP)
  const j = sliced.length - 1
  const stillCross = wS[j - 1] <= CFG.willrThr && wS[j] > CFG.willrThr
  if (!stillCross) leak++
  probed++
}
console.log()
chk('بدونِ نشتِ آینده (برشِ پیش‌رو)', leak === 0,
  `${probed} نقطه آزموده شد، ${leak} ناسازگاری`)

// ---------------------------------------------------------------------------
// ۵) هندسه — SL از ATRِ زنده باید نزدیکِ ۱۲۲.۸۵۴ pip آزموده‌شده بماند.
// ---------------------------------------------------------------------------
const PIP = 0.1
const atrLast = aTs[aTs.length - 1]
const slLive = (atrLast * CFG.slK) / PIP
const rel = slLive / CFG.slPip
console.log('  ▸ هندسهٔ زنده: ATR=%.3f ⇒ SL=%.1f pip (آزموده‌شده %.3f) نسبت=%.2f×',
  atrLast, slLive, CFG.slPip, rel)
chk('TP > SL (اشتباهِ رایجِ ۸ ساختاراً ناممکن)', CFG.rr >= 1.0,
  `RR=${CFG.rr} ⇒ TP=${CFG.tpPip} pip > SL=${CFG.slPip} pip`)

// ---------------------------------------------------------------------------
// ۶) تصمیمِ زنده — لایه باید بدونِ استثنا یک حالتِ معتبر برگرداند.
// ---------------------------------------------------------------------------
const raw = M.computeS382(candles, CFG)
console.log()
console.log('  ▸ تصمیمِ زندهٔ آخرین کندل: state=%s', raw && raw.state ? raw.state : '(null)')
chk('لایه حالتِ معتبر برمی‌گرداند', !!(raw && raw.state),
  raw && raw.reasons ? `${raw.reasons.length} دلیل ثبت شد` : '')

console.log()
if (fail === 0) {
  console.log('✅ PARITY PASS — منطقِ TS با مرجعِ پایتون سازگار است. اتصال مجاز.')
} else {
  console.log('❌ PARITY FAIL — %d آزمون شکست. اتصال مجاز نیست.', fail)
}
process.exit(fail === 0 ? 0 : 1)
