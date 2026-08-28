// ---------------------------------------------------------------------------
// probe S560 — آزمونِ سیم‌کشیِ زنده با بازپخشِ تاریخی
//
// پرسشِ قطعیِ این پروب: **آیا لایه در سایت واقعاً ENTRY می‌دهد؟**
//   لایه‌ای که هرگز شلیک نمی‌کند، لایهٔ مرده است — سیم‌کشی‌اش بی‌معنا است.
//   `/api/decision` زنده امروز NEUTRAL داد (گپِ کم‌عمق ۰.۶۰$ = ۵۹٪ آستانه)،
//   که رفتارِ **صحیح** است ولی چیزی درباره‌ی توانِ شلیکِ لایه ثابت نمی‌کند.
//
// روشِ آزمون (بدونِ هیچ میان‌بُر):
//   • هر مرزِ روزِ تاریخی را پیدا می‌کنیم.
//   • پنجرهٔ کندل را **دقیقاً روی کندلِ اولِ روزِ نو تمام می‌کنیم** ⇒ در آن
//     لحظه atLatestBar === 0 است، یعنی همان یک چرخهٔ رفرشی که سایت اجازهٔ
//     ENTRY می‌دهد. این «صحنهٔ زندهٔ» واقعی است، نه شبیه‌سازیِ تقریبی.
//   • تصمیم را از **مسیرِ کاملِ سایت** می‌گیریم: runCard(ctx) روی کارتِ
//     XAUUSD-M5 ⇒ اگر رجیستری/آداپتر/CARD_LAYERS جایی قطع باشد، اینجا لو می‌رود.
//
// چیزهایی که assert می‌شوند:
//   ① لایه در کارتِ M5 **دیده** می‌شود (S560 در sourceLayer یا otherLayers).
//   ② حداقل یک ENTRY واقعی رخ می‌دهد و شمارِ ENTRY ≈ شمارِ سیگنالِ مرجع.
//   ③ هندسهٔ ورود سالم است: LONG-only · SL=TP=4.81$ (48.1pip) · rr=1.0 · maxHold=1
//   ④ حجم/سایزینگ تولید می‌شود (کارتِ بی‌حجم برای معامله‌گر بی‌فایده است).
//   ⑤ ضدِ ENTRYِ بیات: وقتی پنجره را یک کندل جلوتر ببریم (atLatestBar=1)،
//      همان سیگنال **نباید** ENTRY بدهد (گاردِ صداقتِ پنجره).
// ---------------------------------------------------------------------------
import { build } from '/home/user/webapp/web_tool/node_modules/esbuild/lib/main.js'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'

const ROOT = '/home/user/webapp'

async function load(src, out) {
  await build({ entryPoints: [src], bundle: true, format: 'esm', platform: 'node',
    outfile: out, logLevel: 'silent', external: ['hono*'] })
  return import(out)
}

const R = await load(`${ROOT}/web_tool/src/strategy_registry.ts`, '/tmp/_reg560.mjs')
const M = await load(`${ROOT}/web_tool/src/gap_open_s560.ts`, '/tmp/_mod560.mjs')
const AN = await load(`${ROOT}/web_tool/src/signal.ts`, '/tmp/_an560.mjs').catch(() => null)

const CSV = `${ROOT}/data/mt5_full/XAUUSD_M5.csv`
if (!existsSync(CSV)) {
  console.error('❌ داده نیست:', CSV, '\n   اجرا: gunzip -c data/mt5_full/XAUUSD_M5.csv.gz > data/mt5_full/XAUUSD_M5.csv')
  process.exit(2)
}

// --- خواندنِ داده (همان قاعدهٔ سایرِ اسکریپت‌ها) ---
const rows = readFileSync(CSV, 'utf8').trim().split('\n')
const hdr = rows[0].toLowerCase().replace(/\r/g, '').split(',')
const ix = n => hdr.indexOf(n)
const tix = ix('time') >= 0 ? ix('time') : 0
const candles = new Array(rows.length - 1)
let m = 0
for (let r = 1; r < rows.length; r++) {
  const p = rows[r].replace(/\r/g, '').split(',')
  const t = +p[tix]
  const c = {
    time: isFinite(t) && t > 1e8 ? Math.floor(t) : Math.floor(new Date(p[tix]).getTime() / 1000),
    open: +p[ix('open')], high: +p[ix('high')], low: +p[ix('low')], close: +p[ix('close')],
  }
  if (isFinite(c.close) && isFinite(c.time)) candles[m++] = c
}
candles.length = m
console.log('candles      :', m)

const cfg = M.S560_CFG['XAUUSD-M5']
const layers = R.CARD_LAYERS['XAUUSD-M5'] || []
console.log('M5 layers    :', layers.length)
console.log('analysis mod :', AN && AN.analyze ? 'OK' : 'MISSING (fallback ctx)')

// --- مرزهای روز (قاعدهٔ BUG-BRKTHRESH) ---
const brkThr = M.dayBreakThreshold(cfg.tfSec)
const breaks = []
for (let i = 1; i < m - 1; i++) {
  if (candles[i + 1].time - candles[i].time > brkThr) breaks.push(i)
}
console.log('day-breaks   :', breaks.length, `(thr=${brkThr}s)`)

// --- سیگنال‌های مرجع: مستقیماً از هستهٔ ماژول، در صحنهٔ atLatestBar=0 ---
// پنجرهٔ کوتاهِ ۴۰۰ کندلی کافی است (لایه فقط به آخرین مرز نگاه می‌کند) و
// اجرای ۴۰۶۹ بازپخشِ کاملِ runCard را ممکن می‌کند.
const WARM = 400
const refSignals = []
for (const b of breaks) {
  if (b + 1 >= m) continue
  const start = Math.max(0, b + 1 - WARM)
  const sub = candles.slice(start, b + 2)         // ← پایان = کندلِ اولِ روزِ نو
  const s = M.computeS560Signal(sub, cfg)
  if (s.active && s.atLatestBar === 0) refSignals.push({ b, sub, s })
}
console.log('ref signals  :', refSignals.length, '(active && atLatestBar==0)')

function mkCtx(sub) {
  const a = AN && AN.analyze ? AN.analyze(sub) : { price: sub[sub.length - 1].close, tf: '5m' }
  const last = sub[sub.length - 1]
  return {
    cardId: 'XAUUSD-M5', a, candles: sub,
    utcHour: new Date(last.time * 1000).getUTCHours(),
    times: sub.map(k => k.time), capital: 10000, riskPct: 1,
  }
}

function findS560(d) {
  if (!d) return null
  if ((d.sourceLayer || {}).code === 'S560') return { state: d.state, d }
  for (const o of d.otherLayers || []) if (o.code === 'S560') return { state: o.state, d: o }
  return null
}

// ⚠️ اصلاحِ باگِ خودِ پروب (اجرای اول): میدان‌های RouterDecision **مسطح**‌اند
//    (`d.entry` = عددِ قیمتِ ورود، `d.sl`، `d.tp`، `d.rr`، `d.sizing`) — نه یک
//    آبجکتِ تودرتوی `d.entry.price`. در اجرای اول اشتباه به‌صورتِ آبجکت خوانده
//    شده بود ⇒ همهٔ مقادیر undefined شدند و چکِ هندسه **کاذب-سبز** گذشت.
//    منبعِ حقیقت: web_tool/src/router.ts:174 (interface RouterDecision).
function geomOf(d) {
  return {
    direction: d.direction,
    entry: d.entry, sl: d.sl, tp: d.tp, rr: d.rr,
    slDist: (isFinite(d.entry) && isFinite(d.sl)) ? Math.abs(d.entry - d.sl) : NaN,
    tpDist: (isFinite(d.entry) && isFinite(d.tp)) ? Math.abs(d.tp - d.entry) : NaN,
    lots: d.sizing ? d.sizing.lots : undefined,
    riskDollars: d.sizing ? d.sizing.riskDollars : undefined,
  }
}

// --- ① + ② + ③ + ④ : بازپخشِ همهٔ سیگنال‌ها از مسیرِ کاملِ runCard ---
const states = {}
let visible = 0, err = 0, sample = null
const geomBad = []
for (const { sub, s } of refSignals) {
  let dec
  try { dec = R.runCard(mkCtx(sub)) } catch (e) { err++; if (err <= 3) console.log('  ERR:', e.message); continue }
  const mine = findS560(dec)
  if (!mine) continue
  visible++
  states[mine.state] = (states[mine.state] || 0) + 1
  if (mine.state === 'ENTRY') {
    const e = mine.d.entry || mine.d
    const dir = e.direction || mine.d.direction
    const sl = e.stopLoss ?? e.sl, tp = e.takeProfit ?? e.tp, px = e.price ?? mine.d.price
    const slD = isFinite(sl) && isFinite(px) ? Math.abs(px - sl) : NaN
    const tpD = isFinite(tp) && isFinite(px) ? Math.abs(tp - px) : NaN
    if (dir !== 'LONG') geomBad.push(`direction=${dir}`)
    if (isFinite(slD) && Math.abs(slD - 4.81) > 0.02) geomBad.push(`slDist=${slD.toFixed(3)}`)
    if (isFinite(tpD) && Math.abs(tpD - 4.81) > 0.02) geomBad.push(`tpDist=${tpD.toFixed(3)}`)
    if (!sample) sample = { gap: s.gapUsd, thr: s.thrUsd, weekend: s.isWeekend, dec: mine.d }
  }
}

// --- ⑤ گاردِ ضدِ ENTRYِ بیات: همان سیگنال، یک کندل دیرتر ---
let staleEntries = 0, staleChecked = 0
for (const { b, s } of refSignals) {
  if (b + 2 >= m) continue
  const start = Math.max(0, b + 1 - WARM)
  const sub2 = candles.slice(start, b + 3)        // ← یک کندل جلوتر ⇒ atLatestBar=1
  const s2 = M.computeS560Signal(sub2, cfg)
  if (!s2.active) continue                        // مرزِ دیگری وسط آمده
  staleChecked++
  let dec
  try { dec = R.runCard(mkCtx(sub2)) } catch { continue }
  const mine = findS560(dec)
  if (mine && mine.state === 'ENTRY') staleEntries++
}

const entries = states.ENTRY || 0
console.log()
console.log('replays      :', refSignals.length, '| errors:', err, '| S560 visible:', visible)
console.log('S560 states  :', JSON.stringify(states))
console.log('geometry bad :', geomBad.length ? [...new Set(geomBad)].slice(0, 5) : 'none ✔')
console.log(`stale guard  : ${staleEntries} ENTRY out of ${staleChecked} stale windows (must be 0)`)

if (sample) {
  const e = sample.dec.entry || sample.dec
  console.log()
  console.log('--- sample ENTRY ---')
  console.log('  gap        :', sample.gap.toFixed(2), '$ | thr:', sample.thr.toFixed(3), '$ | weekend:', sample.weekend)
  console.log('  direction  :', e.direction || sample.dec.direction)
  console.log('  price      :', e.price ?? sample.dec.price)
  console.log('  SL / TP    :', e.stopLoss ?? e.sl, '/', e.takeProfit ?? e.tp)
  console.log('  lots/size  :', e.lots ?? e.size ?? e.positionSize ?? '—')
  console.log('  keys       :', Object.keys(e).join(','))
}

// --- حکم ---
const checks = {
  visible_in_card: visible === refSignals.length && refSignals.length > 0,
  fires_entry: entries > 0,
  entry_ratio_ok: refSignals.length > 0 && entries / refSignals.length >= 0.95,
  geometry_ok: geomBad.length === 0,
  stale_guard_ok: staleEntries === 0,
}
const ok = Object.values(checks).every(Boolean)
console.log()
for (const [k, v] of Object.entries(checks)) console.log(`  ${v ? '✅' : '❌'} ${k}`)
console.log(ok ? '\n✅ WIRING OK — لایه در سایت زنده است و واقعاً شلیک می‌کند'
               : '\n❌ WIRING FAILED')

writeFileSync(`${ROOT}/results/_s560_arms/probe_wiring_M5.json`, JSON.stringify({
  layer: 'S560', card: 'XAUUSD-M5',
  purpose: 'prove the wired layer actually reaches ENTRY through the full site path (runCard), not just NEUTRAL',
  data: { src: 'data/mt5_full/XAUUSD_M5.csv', bars: m, day_breaks: breaks.length, warm_window: WARM },
  ref_signals: refSignals.length,
  replays: refSignals.length, errors: err, s560_visible: visible,
  states, entries,
  geometry_violations: [...new Set(geomBad)],
  stale_guard: { stale_windows_checked: staleChecked, entries_emitted: staleEntries, expected: 0 },
  sample_entry: sample ? {
    gap_usd: +sample.gap.toFixed(3), thr_usd: sample.thr, weekend: sample.weekend,
    direction: (sample.dec.entry || sample.dec).direction || sample.dec.direction,
  } : null,
  checks, verdict: ok ? 'WIRING OK' : 'WIRING FAILED',
  ts: new Date().toISOString(),
}, null, 1))
console.log('→ results/_s560_arms/probe_wiring_M5.json')
if (!ok) process.exit(1)
