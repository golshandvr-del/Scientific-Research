// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S1520 در **سطحِ کارت** (نه سطحِ ماژول).
//
// پرسشی که این آزمون پاسخ می‌دهد و پریتی **نمی‌تواند** پاسخ دهد:
//   پریتی (گامِ ۵) ثابت کرد `computeS1520` با پایتون **بیت-به-بیت** یکسان است.
//   ولی سایت هیچ‌وقت `computeS1520` را صدا نمی‌زند — بلکه `runCard()` را صدا
//   می‌زند که از `CARD_LAYERS[cardId]` عبور می‌کند و بعد با `STATE_RANK` یکی را
//   `primary` و بقیه را `otherLayers` می‌کند. پس یک ماژولِ کاملاً درست می‌تواند
//   به‌طورِ نامرئی وصل‌نشده بماند. چهار چیزِ نامعلوم:
//     ① آیا آداپترِ s1520Layer در فهرستِ کارتِ H8 **حاضر** است؟ (۶ لایه، نه ۵)
//     ② آیا وقتی رویدادِ واقعی رخ می‌دهد، تصمیمِ لایه به بیرونِ runCard
//        **می‌رسد** — به‌عنوانِ primary یا داخلِ otherLayers؟
//     ③ آیا حضورِ S1520 تصمیمِ پنج لایهٔ **ساکن** را عوض کرده (رگرسیون)؟
//     ④ آیا کارت‌های H4/H12 (شاهدِ منفی) هنوز S1520 را **نمی‌بینند**؟
//
// روشِ ②: کورکورانه آخرین کندل را نمی‌دهیم (که احتمالاً رویدادی ندارد و آزمون
//   بی‌معنا می‌شد). ابتدا با `computeS1520` **تاریخ را جست‌وجو** می‌کنیم تا کندلی
//   پیدا شود که لایه در آن `active` است، بعد `runCard` را با پیشوندِ [0..i] صدا
//   می‌زنیم. اگر هیچ رویدادی پیدا نشد، آزمون **FAIL** می‌شود (نه SKIP) — چون
//   یعنی لایه در عمل هرگز روشن نمی‌شود.
//
// روشِ ③ (رگرسیون) — نکتهٔ ظریفی که مخصوصِ همین لایه است: نمی‌توان «یک کندل
//   قبل» را به‌عنوانِ حالتِ خاموش گرفت و بعد خروجیِ کاملِ دو حالت را مقایسه کرد،
//   چون ورودیِ ساکنان هم عوض می‌شود (یک کندلِ کمتر ⇒ ATR و σ آن‌ها هم فرق
//   می‌کند) و هر تفاوتی مبهم می‌ماند. پس رگرسیون را **همان کندل، با فهرستِ
//   لایهٔ فیلترشده** می‌سنجیم: `CARD_LAYERS` یک `Record<string, LayerFn[]>`
//   صادرشده و **قابلِ نوشتن** است، پس ورودیِ S1520 را موقتاً برمی‌داریم،
//   runCard را صدا می‌زنیم، و بعد بازمی‌گردانیم. این تنها راهی است که ورودیِ
//   ساکنان **کاملاً ثابت** بماند و تفاوت فقط از حضور/غیبتِ S1520 بیاید.
//   (حذفِ موقت با آرایهٔ کوتاه‌ترِ همان کارت انجام می‌شود؛ چون آداپترها بی‌نام‌اند،
//   لایهٔ S1520 را با تطبیقِ `sourceLayer.code` روی خروجیِ خودش شناسایی می‌کنیم.)
// ---------------------------------------------------------------------------

import fs from 'node:fs'
import path from 'node:path'
// ⚠️ zlib به‌صورت **استاتیک** import می‌شود، نه با `require`. این فایل یک ماژولِ
//    ESM است (پسوندِ .mts) و در ESM هیچ `require`ای در scope وجود ندارد ⇒
//    `require('node:zlib')` با ReferenceError می‌مرد. خطا فقط در مسیرِ «کش نبود»
//    ظاهر می‌شد، پس روی ماشینی که کشِ data/full را داشت پنهان می‌ماند و تنها
//    روی کلونِ تازه (همان حالتی که گامِ ۱۲ می‌خواست درست کند) بیرون می‌زد.
import zlib from 'node:zlib'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
import { computeS1520, S1520_CFG } from '../src/informed_fresh_high_s1520'

const ROOT = path.resolve(import.meta.dirname, '../..')

type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

// دادهٔ کامل عیناً مثلِ `load_full`ِ رانرِ پایتون خوانده می‌شود: اول کشِ
// `data/full/*.csv` و اگر نبود، از `data/mt5_full/*.csv.gz` باز می‌شود.
// ⚠️ چرا این مسیرِ دوگانه لازم است (درسِ ریستِ سندباکس): `data/full/` یک کشِ
//    محلیِ **gitignore-شده** است که رانرِ پایتون می‌سازد؛ پس روی یک کلونِ تازه
//    یا پس از ریستِ محیط **وجود ندارد**. آزمونی که فقط به آن نگاه کند، روی
//    ماشینِ پاک با ENOENT می‌میرد و شبیهِ «باگِ لایه» به نظر می‌رسد، در حالی که
//    فقط کش نبوده. با gunzipِ درجا، آزمون روی هر کلونِ تازه خودکفا اجرا می‌شود.
function loadCsv(tf: string): Candle[] {
  const p = path.join(ROOT, `data/full/XAUUSD_${tf}.csv`)
  let text: string
  if (fs.existsSync(p)) {
    text = fs.readFileSync(p, 'utf8')
  } else {
    const gz = path.join(ROOT, `data/mt5_full/XAUUSD_${tf}.csv.gz`)
    if (!fs.existsSync(gz)) throw new Error(`نه کش و نه gz برای ${tf}: ${p} | ${gz}`)
    const zlib = require('node:zlib') as typeof import('node:zlib')
    text = zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8')
    fs.mkdirSync(path.dirname(p), { recursive: true })
    fs.writeFileSync(p, text)   // کش را مثلِ پایتون می‌سازیم تا اجراهای بعدی سریع باشند
  }
  const lines = text.trim().split('\n')
  const head = lines[0].split(',')
  const ix = (n: string) => head.indexOf(n)
  const iT = ix('time'), iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const iV = ix('tick_volume') >= 0 ? ix('tick_volume') : ix('volume')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const t = lines[i].split(',')
    out.push({
      time: Number(t[iT]), open: Number(t[iO]), high: Number(t[iH]),
      low: Number(t[iL]), close: Number(t[iC]), volume: iV >= 0 ? Number(t[iV]) : 0,
    })
  }
  return out
}

// AnalysisResult حداقلی — decideS1520 فقط `price` را از آن می‌خواند (بررسی‌شده).
function mkA(id: string, price: number): any {
  return { id, price, indicators: [], regime: undefined }
}

const CARD = 'XAUUSD-H8'
let fail = 0
const report: any = {}

console.log('══ آزمونِ یکپارچگیِ S1520 در سطحِ کارت ══\n')

// ---------------------------------------------------------------------------
// ① حضورِ آداپتر در فهرستِ کارتِ H8
// ---------------------------------------------------------------------------
console.log('── ① حضورِ لایه در CARD_LAYERS ──')
const nLayers = (CARD_LAYERS[CARD] || []).length
console.log(`   ${CARD}: ${nLayers} لایه در فهرست (انتظار: ۶ = پنج ساکن + S1520)`)
report.layer_count = nLayers
if (nLayers !== 6) {
  console.log(`   ❌ انتظارِ ۶ لایه بود، ${nLayers} یافت شد`)
  fail++
} else {
  console.log('   ✓ شمارشِ لایه درست است')
}

// ---------------------------------------------------------------------------
// ④ شاهدِ منفی: H4/H12 نباید S1520 بگیرند (حکمشان REJECT/اثبات‌نشده بود)
// ---------------------------------------------------------------------------
console.log('\n── ④ شاهدِ منفیِ H4/H12 ──')
const negs = ['XAUUSD-H4', 'XAUUSD-H12']
report.negative_control = {}
for (const nc of negs) {
  const inCfg = Object.prototype.hasOwnProperty.call(S1520_CFG, nc)
  report.negative_control[nc] = { in_cfg: inCfg }
  if (inCfg) {
    console.log(`   ❌ ${nc} در S1520_CFG ظاهر شده — حکمش ACCEPT نبود`)
    fail++
  } else {
    console.log(`   ✓ ${nc} در S1520_CFG نیست ⇒ اتصال به آن کارت ناممکن است`)
  }
}

// ---------------------------------------------------------------------------
// ② رسیدنِ تصمیم به خروجیِ runCard روی یک رویدادِ **واقعی**
// ③ رگرسیونِ ساکنان با فهرستِ لایهٔ فیلترشده (ورودیِ یکسان)
// ---------------------------------------------------------------------------
console.log('\n── ②③ رویدادِ واقعی + رگرسیونِ ساکنان ──')
const all = loadCsv('H8')
const cfg = S1520_CFG[CARD]
console.log(`   دادهٔ H8: ${all.length} کندل`)

// جست‌وجوی آخرین کندلی که S1520 در آن active است
let hit = -1
const lo = Math.max(cfg.lookback + cfg.atrWin + 5, all.length - 2500)
for (let i = all.length - 1; i >= lo; i--) {
  const raw = computeS1520(all.slice(0, i + 1) as any, cfg)
  if (raw.active) { hit = i; break }
}

if (hit < 0) {
  console.log('   ❌ در ۲۵۰۰ کندلِ اخیر هیچ رویدادِ S1520 پیدا نشد ⇒ لایه عملاً مرده است')
  fail++
} else {
  const when = new Date(all[hit].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  const px = all[hit].close
  console.log(`   رویدادِ واقعی: بارِ ${hit} · ${when} UTC · close=${px}`)

  const ctx = {
    cardId: CARD, a: mkA(CARD, px), candles: all.slice(0, hit + 1) as any,
    utcHour: new Date(all[hit].time * 1000).getUTCHours(),
    times: all.slice(0, hit + 1).map(c => c.time), capital: 10000, riskPct: 1.0,
  }

  // ② با فهرستِ کاملِ لایه
  const dOn = runCard(ctx as any)
  const codesOn: string[] = []
  if (dOn.sourceLayer?.code) codesOn.push(dOn.sourceLayer.code)
  for (const o of (dOn.otherLayers || [])) codesOn.push(o.code)
  const seen = codesOn.some(c => /S1520/i.test(c))
  console.log(`   کدهای دیده‌شده در خروجی: [${codesOn.join(', ')}]`)
  if (seen) {
    console.log('   ✓ ② S1520 به خروجیِ runCard می‌رسد')
  } else {
    console.log('   ❌ ② S1520 در خروجیِ runCard نیست — وصل‌نشده یا خفه‌شده')
    fail++
  }
  const asPrimary = /S1520/i.test(dOn.sourceLayer?.code || '')
  console.log(`   نقش: ${asPrimary ? 'primary' : 'داخلِ otherLayers'} · state=${dOn.state}`)

  // ③ رگرسیون: همان ورودی، ولی فهرستِ لایه بدونِ S1520
  const backup = CARD_LAYERS[CARD]
  const filtered = backup.filter((fn) => {
    try {
      const d = fn(ctx as any)
      return !(d && /S1520/i.test(d.sourceLayer?.code || ''))
    } catch { return true }
  })
  CARD_LAYERS[CARD] = filtered
  let dOff: any = null
  try { dOff = runCard(ctx as any) } finally { CARD_LAYERS[CARD] = backup }

  console.log(`   فهرستِ فیلترشده: ${filtered.length} لایه (انتظار: ۵)`)
  if (filtered.length !== 5) {
    console.log('   ❌ فیلتر نتوانست دقیقاً یک لایه (S1520) را جدا کند')
    fail++
  }

  const codesOff: string[] = []
  if (dOff?.sourceLayer?.code) codesOff.push(dOff.sourceLayer.code)
  for (const o of (dOff?.otherLayers || [])) codesOff.push(o.code)
  console.log(`   کدهای ساکنان بدونِ S1520: [${codesOff.join(', ')}]`)

  // هر کدی که در حالتِ «بدونِ S1520» بود، باید در حالتِ «با S1520» هم باشد،
  // و تصمیمِ همان کد نباید عوض شده باشد (state/entry/sl/tp).
  const mapOn = new Map<string, any>()
  if (dOn.sourceLayer?.code) mapOn.set(dOn.sourceLayer.code, { state: dOn.state, entry: dOn.entry, sl: dOn.sl, tp: dOn.tp })
  for (const o of (dOn.otherLayers || [])) mapOn.set(o.code, { state: o.state, entry: o.entry, sl: o.sl, tp: o.tp })
  const mapOff = new Map<string, any>()
  if (dOff?.sourceLayer?.code) mapOff.set(dOff.sourceLayer.code, { state: dOff.state, entry: dOff.entry, sl: dOff.sl, tp: dOff.tp })
  for (const o of (dOff?.otherLayers || [])) mapOff.set(o.code, { state: o.state, entry: o.entry, sl: o.sl, tp: o.tp })

  let reg = 0
  for (const [code, v] of mapOff) {
    if (!mapOn.has(code)) {
      console.log(`   ❌ ③ لایهٔ ساکنِ ${code} با افزودنِ S1520 از خروجی **حذف** شد`)
      reg++; continue
    }
    const w = mapOn.get(code)
    const same = v.state === w.state
      && Math.abs((v.entry ?? 0) - (w.entry ?? 0)) < 1e-9
      && Math.abs((v.sl ?? 0) - (w.sl ?? 0)) < 1e-9
      && Math.abs((v.tp ?? 0) - (w.tp ?? 0)) < 1e-9
    if (!same) {
      console.log(`   ❌ ③ تصمیمِ ساکنِ ${code} عوض شد: ${JSON.stringify(v)} ⇒ ${JSON.stringify(w)}`)
      reg++
    }
  }
  if (reg === 0) {
    console.log(`   ✓ ③ هر ${mapOff.size} لایهٔ ساکنِ حاضر، بی‌تغییر ماندند (بی‌رگرسیون)`)
  } else { fail += reg }

  report.event = { bar: hit, time: all[hit].time, when, price: px,
    codes_on: codesOn, codes_off: codesOff, as_primary: asPrimary,
    state: dOn.state, regressions: reg,
    entry: dOn.entry, sl: dOn.sl, tp: dOn.tp, rr: dOn.rr }
}

// ---------------------------------------------------------------------------
const outDir = path.join(ROOT, 'results/_s1520_parity')
fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, 'integ_card.json'), JSON.stringify(report, null, 1))

console.log(`\n${'═'.repeat(58)}`)
if (fail === 0) {
  console.log('✅ یکپارچگیِ سطحِ کارت: GREEN — لایه از مسیرِ واقعیِ runCard می‌گذرد،')
  console.log('   ساکنان بی‌تغییرند، و شاهدِ منفیِ H4/H12 برقرار است.')
} else {
  console.log(`❌ یکپارچگی: ${fail} ایراد`)
  process.exit(1)
}
