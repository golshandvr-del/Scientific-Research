// ============================================================================
// integ_s355_card.mjs — آزمونِ یکپارچگیِ end-to-end برای دروازهٔ S355 روی XAUUSD-M5
// ----------------------------------------------------------------------------
// این آزمون از سطحِ «تابع» بالاتر می‌رود و کلِ `runCard` کارت را صدا می‌زند، یعنی
// همان مسیری که سایت واقعاً طی می‌کند. سه چیز را **اندازه** می‌گیرد:
//
//   ۱) دروازه واقعاً وصل است؟  — آیا هیچ تصمیمِ ENTRY با `sourceLayer.code='S355'`
//      و برچسبِ فیلترِ ساختار تولید می‌شود؟
//   ۲) شاخهٔ «دروازهٔ بسته» درست است؟ — وقتی مولدِ پایه سیگنال دارد ولی حالت
//      `≠ −1` است، کارت باید APPROACHING بدهد (نه ENTRY و نه سکوتِ کامل)، و
//      هندسهٔ معامله (tp/sl/direction) باید خالی باشد تا کاربر گمراه نشود.
//   ۳) هیچ ENTRYِ S355 در حالتِ `≠ −1` وجود ندارد — این شرطِ **ایمنیِ** اصلی است:
//      نشتِ آن یعنی سایت معامله‌ای را پیشنهاد می‌دهد که در بک‌تست هرگز آزموده نشد.
//
// پیش‌نیاز:
//   npx esbuild src/strategy_registry.ts --bundle --format=esm --platform=node \
//       --outfile=dist_parity/strategy_registry.js
// اجرا: cd web_tool && node integ_s355_card.mjs
// ============================================================================
import fs from 'node:fs'
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'
import { runCard, CARD_LAYERS } from './dist_parity/strategy_registry.js'

const ROOT = '/home/user/webapp'
const CARD = 'XAUUSD-M5'
const WIN = 1400              // همان پنجرهٔ زندهٔ کارت (range='5d')

// حالتِ ساختار برای تفسیرِ نتیجه (از همان ماژولِ وصل‌شده)
const out = '/tmp/_s355_layer_i.mjs'
await build({ entryPoints: [`${ROOT}/web_tool/src/lpsb_state_s355.ts`], bundle: true,
              format: 'esm', platform: 'node', outfile: out, logLevel: 'error' })
const { lpsbStateNow, S355_CFG } = await import(pathToFileURL(out).href)
const cfg = S355_CFG[CARD]

// کندل‌ها از همان CSVِ بک‌تست
const csv = fs.readFileSync(`${ROOT}/data/XAUUSD_M5.csv`, 'utf8').trim().split('\n')
const hd = csv[0].split(',')
const iT = hd.indexOf('time'), iO = hd.indexOf('open'), iH = hd.indexOf('high'),
      iL = hd.indexOf('low'), iC = hd.indexOf('close')
const all = csv.slice(1).map(line => {
  const p = line.split(',')
  const ts = p[iT]
  const tsec = /^\d+$/.test(ts) ? parseInt(ts, 10)
                                : Math.floor(new Date(ts.replace(' ', 'T') + 'Z').getTime() / 1000)
  return { time: tsec, open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC], volume: 0 }
})

// بارهای ورودِ پایهٔ S333 (مرجعِ پایتون) — نقاطی که دروازه واقعاً تصمیم می‌گیرد
const baseBars = JSON.parse(fs.readFileSync('/tmp/_s355_base_bars_py.json', 'utf8'))
const probes = baseBars.filter(i => i >= WIN)
console.log(`=== ${CARD} === (${CARD_LAYERS[CARD].length} لایه) — ${probes.length} بارِ سیگنالِ پایهٔ S333`)

let entryS355 = 0, approachGated = 0, otherState = 0, leak = 0
const gateOpenSeen = { open: 0, shut: 0 }
const samples = []

for (const idx of probes) {
  const candles = all.slice(Math.max(0, idx - WIN + 1), idx + 1)
  const last = candles[candles.length - 1]
  const st = lpsbStateNow(candles, cfg.L, cfg.f)
  st === cfg.requiredState ? gateOpenSeen.open++ : gateOpenSeen.shut++

  const d = new Date(last.time * 1000)
  const ctx = {
    cardId: CARD, a: { price: last.close, adx: 0, ema: {}, rsi: 50 }, candles,
    utcHour: d.getUTCHours(), times: candles.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  let dec
  try { dec = runCard(ctx) } catch (e) { console.log('runCard threw:', e.message); continue }
  if (!dec) continue

  const isS355 = dec.sourceLayer?.code === 'S355'
  if (dec.state === 'ENTRY' && isS355) {
    entryS355++
    if (st !== cfg.requiredState) {           // ⛔ نشتِ ایمنی
      leak++
      samples.push({ kind: 'LEAK', idx, st, filters: dec.sourceLayer?.filters })
    } else if (samples.filter(s => s.kind === 'ENTRY').length < 2) {
      samples.push({ kind: 'ENTRY', idx, st, dir: dec.direction, entry: dec.entry,
                     tp: dec.tp, sl: dec.sl, rr: dec.rr, filters: dec.sourceLayer?.filters })
    }
  } else if (dec.state === 'APPROACHING' && isS355) {
    approachGated++
    if (samples.filter(s => s.kind === 'APPROACH').length < 2) {
      samples.push({ kind: 'APPROACH', idx, st, headline: dec.headline,
                     hasGeometry: !!(dec.tp || dec.sl || dec.direction), reason: dec.reason?.slice(0, 150) })
    }
  } else {
    otherState++                              // لایهٔ دیگری (اولویتِ بالاتر) کارت را برد
  }
}

console.log(`\ngate state at those bars:  open(−1)=${gateOpenSeen.open}  shut(≠−1)=${gateOpenSeen.shut}`)
console.log(`S355 ENTRY decisions:        ${entryS355}`)
console.log(`S355 APPROACHING (gate shut):${approachGated}`)
console.log(`won by another layer/neutral:${otherState}`)
console.log(`\n--- samples ---`)
for (const s of samples) console.log(JSON.stringify(s, null, 1))

const geomLeak = samples.some(s => s.kind === 'APPROACH' && s.hasGeometry)
console.log('\n=== verdict ===')
console.log(`  [${leak === 0 ? 'PASS' : 'FAIL'}] safety: no S355 ENTRY while structure state ≠ ${cfg.requiredState} (leaks=${leak})`)
console.log(`  [${entryS355 > 0 ? 'PASS' : 'FAIL'}] gate is actually wired and can fire (entries=${entryS355})`)
console.log(`  [${!geomLeak ? 'PASS' : 'FAIL'}] blocked entries expose no trade geometry`)
process.exit(leak === 0 && entryS355 > 0 && !geomLeak ? 0 : 1)
