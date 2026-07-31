// ============================================================================
// parity_s355_window.mjs — آزمونِ **حساسیتِ پنجره** برای دروازهٔ S355
// ----------------------------------------------------------------------------
// چرا این آزمون حیاتی است (و چرا صرفِ parityِ کل-سری کافی نیست):
//
// حکمِ RQS2=83.9 روی **کلِ سریِ ۲۰۰٬۰۰۰ کندلی** محاسبه شد، ولی سایتِ زنده هرگز
// کلِ تاریخ را ندارد: کارتِ `XAUUSD-M5` از Yahoo با `range='5d'` داده می‌گیرد
// ⇒ پنجره‌ای ≈۱٤۰۰ کندلی. حالتِ ساختارِ LPSB یک **ماشینِ حالتِ تجمعی** است:
// `cur` تا وقتی یک شکستِ تازه رخ ندهد، از گذشته حمل می‌شود. پس این سؤال باید
// **اندازه‌گیری** شود، نه فرض:
//
//     آیا state در آخرین کندلِ یک پنجرهٔ W کندلی، همان state در همان کندل
//     وقتی از کندلِ صفر محاسبه شود، هست؟
//
// اگر در پنجره هیچ شکستی رخ نداده باشد، پنجره با `cur=0` شروع می‌شود و ممکن است
// `0` بدهد در حالی که حالتِ واقعی `±1` است. جهتِ خطا **محافظه‌کارانه** است
// (`0 ≠ −1` ⇒ دروازه بسته ⇒ سیگنالِ ازدست‌رفته، نه سیگنالِ کاذب) — اما نرخش
// باید معلوم باشد، چون سایت باید همان لایه‌ای را نشان دهد که آزموده شد.
//
// اجرا:  node web_tool/parity_s355_window.mjs
//        (نیاز به /tmp/_s355_state_py.json — همان مرجعِ parity_s355_state.mjs)
// ============================================================================
import { readFileSync } from 'node:fs'
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'
const outfile = '/tmp/_s355_layer_w.mjs'
await build({
  entryPoints: [`${ROOT}/web_tool/src/lpsb_state_s355.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error',
})
const { lpsbStateNow, LPSB_CENTRAL } = await import(pathToFileURL(outfile).href)

const csv = readFileSync(`${ROOT}/data/XAUUSD_M5.csv`, 'utf8').trim().split('\n')
const h = csv[0].split(',')
const iT = h.indexOf('time'), iO = h.indexOf('open'), iH = h.indexOf('high'),
      iL = h.indexOf('low'), iC = h.indexOf('close')
const candles = csv.slice(1).map(line => {
  const p = line.split(',')
  const ts = p[iT]
  const tsec = /^\d+$/.test(ts) ? parseInt(ts, 10)
                                : Math.floor(new Date(ts.replace(' ', 'T') + 'Z').getTime() / 1000)
  return { time: tsec, open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC], volume: 0 }
})
const full = JSON.parse(readFileSync('/tmp/_s355_state_py.json', 'utf8'))   // مرجعِ کل-سری
console.log('candles:', candles.length, '| full-series reference:', full.length)

// پنجره‌های آزمون: ≈پنجرهٔ واقعیِ سایت (۱٤۰۰) + کوچک‌تر/بزرگ‌تر برای دیدنِ روند
const WINDOWS = [300, 700, 1400, 3000, 6000]
// ۴٬۰۰۰ نقطهٔ آزمون با فاصلهٔ یکنواخت روی کلِ تاریخ (نه فقط انتهای داده)
const PROBES = 4000
const start = 20000
const step = Math.floor((candles.length - start - 10) / PROBES)

console.log('\n W      agree     disagree  |  breakdown of disagreements')
console.log('-------------------------------------------------------------------')
const rows = []
for (const W of WINDOWS) {
  let agree = 0, dis = 0
  const kinds = {}          // 'trueState->windowState'
  for (let k = 0; k < PROBES; k++) {
    const i = start + k * step
    const lo = Math.max(0, i - W + 1)
    const win = candles.slice(lo, i + 1)
    const sw = lpsbStateNow(win, LPSB_CENTRAL.L, LPSB_CENTRAL.f)
    const st = full[i]
    if (sw === st) agree++
    else { dis++; const key = `${st}→${sw}`; kinds[key] = (kinds[key] || 0) + 1 }
  }
  const pct = (100 * agree / PROBES).toFixed(2)
  rows.push({ W, agree, dis, pct, kinds })
  console.log(` ${String(W).padEnd(6)} ${pct.padStart(6)}%   ${String(dis).padStart(6)}    |  ${JSON.stringify(kinds)}`)
}

// آیا واگراییِ باقی‌مانده «محافظه‌کارانه» است؟ یعنی هرگز state واقعیِ +1 را
// به −1 (حالتِ مجازِ ورود) تبدیل نکند — چون آن سیگنالِ **کاذب** می‌ساخت.
console.log('\nsafety check — a disagreement is SAFE unless it invents the entry state (−1):')
let unsafe = 0
for (const r of rows) {
  for (const [k, v] of Object.entries(r.kinds)) {
    const [, ws] = k.split('→')
    if (ws === '-1') { unsafe += v; console.log(`  ⚠️ W=${r.W}: ${v}× produced −1 while truth was ${k.split('→')[0]}`) }
  }
}
console.log(unsafe === 0
  ? '  ✅ SAFE — no window length ever fabricated the entry state; every disagreement only suppresses a signal.'
  : `  ❌ UNSAFE — ${unsafe} fabricated entry states.`)

const live = rows.find(r => r.W === 1400)
console.log(`\nLIVE WINDOW (M5 range=5d ≈ 1400 bars): agreement = ${live.pct}%`)
