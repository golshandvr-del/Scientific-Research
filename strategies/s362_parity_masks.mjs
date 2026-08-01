/**
 * S362-PARITY — اثباتِ **عددیِ** برابریِ ماسک‌های پایتونیِ `s362_cocard_masks.py`
 * با کدِ **مستقرِ** TS که همین‌الان روی سایت اجرا می‌شود.
 *
 * چرا این فایل وجود دارد: گامِ ۳ت فیلترش را از «لایهٔ دیگرِ همان پروژه» می‌گیرد.
 * اگر بازتولیدِ پایتونی حتی کمی با لایهٔ مستقر تفاوت داشته باشد، نتیجهٔ منفیِ
 * گام بی‌اعتبار است (خطای نوعِ دوم). پس برابری **اندازه‌گیری** می‌شود نه ادعا.
 *
 * روش: توابعِ `computeXXX(candles, cfg)`ِ TS فقط برای **آخرین** کندل تصمیم
 * می‌گیرند. چون همهٔ اندیکاتورهای این چهار لایه **علّی** (causal) هستند، مقدارِ
 * اندیکاتور در اندیسِ `i` وابسته به کندل‌های `> i` نیست، پس فراخوانی روی
 * پیشوندِ `candles[0..i]` همان تصمیمِ اندیسِ `i` را می‌دهد. بنابراین یک نمونهٔ
 * تصادفیِ اندیس‌ها کافی است و هزینه O(نمونه × N) می‌ماند نه O(N²).
 *
 * اجرا:
 *   node strategies/s362_parity_masks.mjs <CARD>        # مثلاً XAUUSD-H1
 * پیش‌نیاز: بیلدِ `web_tool/dist_parity/*.js` با esbuild.
 */
import fs from 'fs'
import path from 'path'

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..')
const D = path.join(ROOT, 'web_tool', 'dist_parity')

const { computeS333, S333_CFG } = await import(path.join(D, 's333_pullback.js'))
const { computeS335, S335_CFG } = await import(path.join(D, 's335_reflex_cycle.js'))
const { computeStreakReversal, STREAK_REV_CFG } =
  await import(path.join(D, 'streak_reversal_s326.js'))
const { computeSellClimax, SELL_CLIMAX_CFG } =
  await import(path.join(D, 'sell_climax_s327.js'))

const card = process.argv[2] || 'XAUUSD-H1'
const nSample = Number(process.argv[3] || 400)
const [asset, tf] = card.split('-')

// ── دادهٔ خام، عیناً همان CSVی که پایتون می‌خواند ──
const rows = fs.readFileSync(path.join(ROOT, 'data', `${asset}_${tf}.csv`), 'utf8')
  .trim().split('\n').slice(1)
const candles = rows.map(r => {
  const [t, o, h, l, c, v] = r.split(',')
  return { time: +t, open: +o, high: +h, low: +l, close: +c, volume: +v }
})
const N = candles.length

// ── اندیس‌های آزمون ──
// ⚠️ چرا نمونهٔ تصادفیِ صرف کافی **نیست**: این چهار لایه به‌ندرت شلیک می‌کنند
// (روی H1، در ۳۰۰ نمونهٔ تصادفی فقط ۱ فعال دیده شد). با چنین نمونه‌ای، توافقِ
// «۳۰۰ از ۳۰۰» تقریباً هیچ‌چیز اثبات نمی‌کند، چون یک بازتولیدِ کاملاً خرابی که
// همیشه `false` برمی‌گرداند هم ~۹۹.۷٪ توافق می‌گیرد. پس آزمون **دوسویه** است:
//   • همهٔ اندیس‌هایی که ماسکِ **پایتون** `active` می‌گوید ⇒ آزمونِ مثبت‌ها
//     (کشفِ مثبتِ کاذبِ پایتون)
//   • به‌علاوهٔ نمونهٔ تصادفیِ قطعی ⇒ آزمونِ منفی‌ها
//     (کشفِ مثبتی که پایتون از دست داده)
// فایلِ اندیس‌ها را **پایتون** می‌سازد تا هر دو طرف در نقاطِ یکسان سنجیده شوند.
const idxFile = path.join(ROOT, '.tmp_logs', `parity_idx_${card}.json`)
let sample
if (fs.existsSync(idxFile)) {
  sample = JSON.parse(fs.readFileSync(idxFile, 'utf8')).indices
} else {
  let seed = 20250801
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff
  const lo = Math.floor(N * 0.35)
  const idx = new Set()
  while (idx.size < Math.min(nSample, N - lo)) idx.add(lo + Math.floor(rnd() * (N - lo)))
  sample = [...idx].sort((a, b) => a - b)
}

const LAYERS = [
  ['S326', computeStreakReversal, STREAK_REV_CFG[card]],
  ['S327', computeSellClimax, SELL_CLIMAX_CFG[card]],
  ['S333', computeS333, S333_CFG[card]],
  ['S335', computeS335, S335_CFG[card]],
]

const out = { card, n_bars: N, n_sample: sample.length, sample, layers: {} }
for (const [name, fn, cfg] of LAYERS) {
  if (!cfg) { out.layers[name] = null; continue }   // پیکربندیِ مستقر ندارد
  const act = []
  for (const i of sample) act.push(fn(candles.slice(0, i + 1), cfg).active ? 1 : 0)
  out.layers[name] = act
}
fs.writeFileSync(path.join(ROOT, '.tmp_logs', `parity_ts_${card}.json`),
                 JSON.stringify(out))
const summary = Object.entries(out.layers)
  .map(([k, v]) => `${k}=${v === null ? 'n/a' : v.reduce((a, b) => a + b, 0)}`)
  .join(' ')
console.log(`[TS] ${card} bars=${N} sample=${sample.length} active-counts: ${summary}`)
