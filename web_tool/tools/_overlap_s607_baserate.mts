// ---------------------------------------------------------------------------
// آزمونِ **نرخِ پایه** برای هم‌پوشانیِ S607/H8 — پاسخ به یک پرسشِ مشخص:
//
//   اندازه‌گیریِ گامِ ۱۵ نشان داد هر ۱۱ سیگنالِ S607 روی کارتِ H8 با دستِ‌کم
//   یکی از چهار لایهٔ ساکن هم‌کندل است (۰٪ پوششِ نو)، و ۹۰.۹٪ با S770.
//   ولی S770 روی همین پنجره **۱۴۹** سیگنال دارد (هر ~۸ کندل یک‌بار).
//   ⇒ پرسش: آیا این هم‌کندلی **معنادار** است، یا صرفاً نتیجهٔ **تراکمِ بالای**
//     ساکنان است که هر کندلِ تصادفی هم با احتمالِ بالا در آن می‌افتد؟
//
// اگر پاسخ «تراکم» باشد، آن ۰٪ پوششِ نو یک **آرتیفکتِ نرخِ پایه** است و
// دلیلی برای ردِ اتصال نیست. اگر پاسخ «معنادار» باشد، S607 روی H8 عملاً
// همان رویدادهای ساکنان را دوباره می‌شمرد و اتصالش فقط سایز را متورم می‌کند.
//
// روشِ آزمون (بدونِ هیچ پارامترِ تنظیم‌شدنی):
//   ① پوششِ اتحادِ ساکنان را می‌شماریم: چند کندل از پنجره دستِ‌کم یک سیگنالِ
//      ساکن دارد ⇒ p_base = آن تعداد ÷ کلِ کندل‌های پنجره.
//   ② زیرِ فرضِ صفر «S607 بی‌ربط است»، تعدادِ هم‌کندلی‌هایش دوجمله‌ای است:
//      K ~ Binom(n=11, p=p_base). احتمالِ دیدنِ «۱۱ از ۱۱» را دقیق حساب
//      می‌کنیم (p_base^11) — بدونِ شبیه‌سازی، بدونِ بذر.
//   ③ همان کار برای جفتِ S607↔S770 با p_770 = پوششِ تنهای S770.
//
// ⚠️ صداقتِ دامنه: این آزمون **هم‌کندلیِ دقیق** را می‌سنجد (همان تعریفِ گامِ
//    ۱۵). پنجرهٔ زمانیِ معامله (maxHold) را در نظر نمی‌گیرد، پس عددِ واقعیِ
//    «تلاقیِ پوزیشن» از این بالاتر است. نتیجه‌گیریِ ما محافظه‌کارانه می‌ماند.
// ---------------------------------------------------------------------------

import fs from 'node:fs'
import path from 'node:path'
import { computeS607, S607_CFG } from '../src/engle_dual_gate_s607'
import { computeS950, S950_CFG } from '../src/jump_aftermath_s950'
import { computeS965, S965_CFG } from '../src/kyle_intrabar_s965'
import { computeS966, S966_CFG } from '../src/kyle_permanence_drift_s966'
import { computeS770, S770_CFG } from '../src/adr_expansion_s770'

type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

const ROOT = path.resolve(import.meta.dirname, '../..')
const CSV = path.join(ROOT, 'data/mt5_full/XAUUSD_H8.csv')
const WINDOW = 1200 // همان پنجرهٔ گامِ ۱۵ ⇒ اعداد مستقیماً قابلِ مقایسه‌اند

function loadCsv(p: string): Candle[] {
  const rows = fs.readFileSync(p, 'utf8').trim().split('\n')
  rows.shift()
  return rows.map((ln) => {
    const c = ln.split(',')
    return {
      time: +c[0], open: +c[1], high: +c[2], low: +c[3], close: +c[4], volume: +c[5],
    }
  })
}

const all = loadCsv(CSV)
const start = all.length - WINDOW
console.log(`دادهٔ H8: ${all.length} کندل · پنجره: ${WINDOW} کندلِ آخر\n`)

// --- اجرای غلتان (همان الگوی گامِ ۱۵: به هر گام فقط [0..i] داده می‌شود) ---
const bars607: number[] = []
const bars950: number[] = []
const bars965: number[] = []
const bars966: number[] = []
const bars770: number[] = []

console.log('── اجرای غلتان ──')
for (let i = start; i < all.length; i++) {
  const hist = all.slice(0, i + 1)
  if (computeS607(hist, S607_CFG['XAUUSD-H8']).active) bars607.push(i)
  if (computeS950(hist, S950_CFG['XAUUSD-H8']).active) bars950.push(i)
  if (computeS965(hist, S965_CFG['XAUUSD-H8']).active) bars965.push(i)
  if (computeS966(hist, S966_CFG['XAUUSD-H8']).active) bars966.push(i)
  if (computeS770(hist, S770_CFG['XAUUSD-H8']).active) bars770.push(i)
}
console.log(
  `  S607=${bars607.length} · S950=${bars950.length} · S965=${bars965.length} · ` +
  `S966=${bars966.length} · S770=${bars770.length}\n`,
)

// --- ① پوششِ ساکنان ---
const unionSet = new Set<number>([...bars950, ...bars965, ...bars966, ...bars770])
const pBase = unionSet.size / WINDOW
const p770 = bars770.length / WINDOW

// --- ② احتمالِ دقیقِ دوجمله‌ای برای «همه هم‌کندل» ---
const n607 = bars607.length
const sameUnion = bars607.filter((i) => unionSet.has(i)).length
const set770 = new Set(bars770)
const same770 = bars607.filter((i) => set770.has(i)).length

// P(K ≥ k) زیرِ Binom(n, p) — جمعِ دقیق، بدونِ تقریب
function binomTail(n: number, k: number, p: number): number {
  // log-factorial برای پایداریِ عددی
  const lgamma = (x: number): number => {
    // Lanczos
    const g = [
      676.5203681218851, -1259.1392167224028, 771.32342877765313,
      -176.61502916214059, 12.507343278686905, -0.13857109526572012,
      9.9843695780195716e-6, 1.5056327351493116e-7,
    ]
    if (x < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * x)) - lgamma(1 - x)
    x -= 1
    let a = 0.99999999999980993
    const t = x + 7.5
    for (let i = 0; i < g.length; i++) a += g[i] / (x + i + 1)
    return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a)
  }
  const logC = (nn: number, kk: number) =>
    lgamma(nn + 1) - lgamma(kk + 1) - lgamma(nn - kk + 1)
  let s = 0
  for (let j = k; j <= n; j++) {
    s += Math.exp(logC(n, j) + j * Math.log(p) + (n - j) * Math.log(1 - p))
  }
  return s
}

const pvalUnion = binomTail(n607, sameUnion, pBase)
const pval770 = binomTail(n607, same770, p770)

console.log('── ① پوششِ ساکنان روی پنجره ──')
console.log(`  اتحادِ چهار ساکن: ${unionSet.size} کندلِ متمایز از ${WINDOW} ⇒ p_base = ${(100 * pBase).toFixed(1)}٪`)
console.log(`  فقط S770       : ${bars770.length} کندل ⇒ p_770 = ${(100 * p770).toFixed(1)}٪\n`)

console.log('── ② آزمونِ دوجمله‌ایِ دقیق (فرضِ صفر: S607 بی‌ربط است) ──')
console.log(`  S607 ↔ اتحاد: ${sameUnion}/${n607} هم‌کندل · P(K≥${sameUnion} | p=${pBase.toFixed(3)}) = ${pvalUnion.toExponential(3)}`)
console.log(`  S607 ↔ S770 : ${same770}/${n607} هم‌کندل · P(K≥${same770} | p=${p770.toFixed(3)}) = ${pval770.toExponential(3)}\n`)

// --- ③ تفسیرِ ماشینی ---
// آستانهٔ ۰.۰۵ **قبل** از دیدنِ عدد نوشته می‌شود (قاعدهٔ پروژه: پیش‌ثبت).
const ALPHA = 0.05
const unionSignificant = pvalUnion < ALPHA
const s770Significant = pval770 < ALPHA

let verdict: string
if (!unionSignificant) {
  verdict =
    `✅ آرتیفکتِ نرخِ پایه: پوششِ ساکنان ${(100 * pBase).toFixed(1)}٪ از کلِ کندل‌هاست، ` +
    `پس «۱۱ از ۱۱ هم‌کندل» با p=${pvalUnion.toExponential(2)} ≥ ${ALPHA} از تصادف ` +
    `قابلِ تفکیک نیست. ⇒ ۰٪ پوششِ نو **دلیلِ ردِ اتصال نیست**، ولی هم‌خانوادگی ` +
    `در سایزِ پرتفوی باید ثبت شود.`
} else {
  verdict =
    `⚠️ هم‌پوشانیِ معنادار: p=${pvalUnion.toExponential(2)} < ${ALPHA} ⇒ S607 روی H8 ` +
    `همان رویدادهای ساکنان را می‌بیند، نه رویدادهای نو. اتصالش سایز را روی ` +
    `رویدادهای تکراری متورم می‌کند ⇒ اگر وصل شود، **باید** زیرِ ساکنان و با ` +
    `هشدارِ صریحِ صفِ FIFO بیاید (همان رویه‌ای که S966 با آن وصل شد).`
}
console.log(verdict)

const out = {
  what: 'آزمونِ نرخِ پایه برای هم‌پوشانیِ S607/H8 با چهار لایهٔ ساکن',
  why:
    'گامِ ۱۵ نشان داد ۰٪ پوششِ نو. ولی S770 روی همین پنجره ۱۴۹ سیگنال دارد ' +
    '(هر ~۸ کندل) ⇒ باید سنجید که هم‌کندلی معنادار است یا آرتیفکتِ تراکم.',
  method:
    'اتحادِ ساکنان ⇒ p_base؛ سپس آزمونِ دقیقِ دوجمله‌ای P(K≥k | Binom(n_s607, p_base)). ' +
    'بدونِ شبیه‌سازی، بدونِ بذر، بدونِ پارامترِ تنظیم‌شدنی. آستانهٔ α=0.05 پیش‌ثبت.',
  scope_limit:
    'هم‌کندلیِ **دقیق** سنجیده شد (نه تلاقیِ پنجرهٔ maxHold) ⇒ تلاقیِ واقعیِ ' +
    'پوزیشن‌ها از این بیشتر است؛ نتیجه محافظه‌کارانه است. پنجره ۱۲۰۰ کندلِ H8، ' +
    'عیناً همان پنجرهٔ results/_s607_overlap/h8.json.',
  window: { bars: WINDOW, tf: 'H8', source: 'data/mt5_full/XAUUSD_H8.csv' },
  counts: {
    s607: n607, s950: bars950.length, s965: bars965.length,
    s966: bars966.length, s770: bars770.length,
    incumbent_union_distinct_bars: unionSet.size,
  },
  base_rates: { p_base: +pBase.toFixed(4), p_770: +p770.toFixed(4) },
  tests: {
    alpha: ALPHA,
    s607_vs_union: { same: sameUnion, n: n607, p_value: pvalUnion, significant: unionSignificant },
    s607_vs_s770: { same: same770, n: n607, p_value: pval770, significant: s770Significant },
  },
  verdict,
}

const outDir = path.join(ROOT, 'results/_s607_overlap')
fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, 'h8_baserate.json'), JSON.stringify(out, null, 1))
console.log(`\n[saved] results/_s607_overlap/h8_baserate.json`)
