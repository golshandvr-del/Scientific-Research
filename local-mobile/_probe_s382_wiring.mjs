// بازرسِ اتصال: آیا S382 در کارتِ زندهٔ XAUUSD-H4 واقعاً اجرا می‌شود؟
// پرسشِ قطعی: صفر بودنِ otherLayers «باگِ اتصال» است یا «رفتارِ صحیحِ حالت»؟
import { build } from '/home/user/webapp/web_tool/node_modules/esbuild/lib/main.js'
import { readFileSync } from 'node:fs'
const ROOT = '/home/user/webapp'

async function load(src, out) {
  await build({ entryPoints: [src], bundle: true, format: 'esm', platform: 'node',
    outfile: out, logLevel: 'silent', external: ['hono*'] })
  return import(out)
}
const R  = await load(`${ROOT}/web_tool/src/strategy_registry.ts`, '/tmp/_reg.mjs')
const AN = await load(`${ROOT}/web_tool/src/signal.ts`, '/tmp/_an.mjs').catch(() => null)

const rows = readFileSync(`${ROOT}/data/XAUUSD_H4.csv`, 'utf8').trim().split('\n')
const hdr = rows[0].toLowerCase().replace(/\r/g, '').split(',')
const ix = n => hdr.indexOf(n)
const tix = ix('time') >= 0 ? ix('time') : (ix('date') >= 0 ? ix('date') : 0)
const candles = rows.slice(1).map(r => {
  const p = r.replace(/\r/g, '').split(',')
  const t = +p[tix]
  return { time: isFinite(t) && t > 1e8 ? Math.floor(t) : Math.floor(new Date(p[tix]).getTime() / 1000),
           open: +p[ix('open')], high: +p[ix('high')], low: +p[ix('low')], close: +p[ix('close')] }
}).filter(c => isFinite(c.close) && isFinite(c.time))

console.log('candles      :', candles.length)
console.log('H4 layers    :', (R.CARD_LAYERS['XAUUSD-H4'] || []).length)
console.log('analysis mod :', AN && AN.analyze ? 'OK' : 'MISSING')

function mkCtx(sub) {
  const a = AN && AN.analyze ? AN.analyze(sub) : { price: sub[sub.length - 1].close }
  return { cardId: 'XAUUSD-H4', a, candles: sub, utcHour: 12,
           times: sub.map(k => k.time), capital: 10000, riskPct: 1 }
}

const found = { ENTRY: 0, APPROACHING: 0, NEUTRAL: 0 }
let err = 0, reps = 0, sample = null
for (let i = candles.length - 2100; i < candles.length; i += 7) {
  const sub = candles.slice(0, i + 1)
  if (sub.length < 140) continue
  reps++
  try {
    const d = R.runCard(mkCtx(sub))
    const rows2 = [{ code: (d.sourceLayer || {}).code, state: d.state, d },
      ...((d.otherLayers || []).map(x => ({ code: x.code, state: x.state, d })))]
    const mine = rows2.find(x => x.code === 'S382')
    if (mine) {
      found[mine.state] = (found[mine.state] || 0) + 1
      if (mine.state === 'ENTRY' && !sample) sample = mine
    }
  } catch (e) { err++; if (err <= 2) console.log('  ERR:', e.message) }
}
console.log()
console.log('replays      :', reps, '| errors:', err)
console.log('S382 visible :', JSON.stringify(found))
if (sample) {
  console.log('ENTRY sample :', String(sample.d.headline).slice(0, 95))
  console.log('  entry/tp/sl:', sample.d.entry, sample.d.tp, sample.d.sl, '| rr:', sample.d.rr)
}
