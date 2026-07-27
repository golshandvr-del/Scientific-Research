// =============================================================================
//  tools/decision_parity.mjs — هارنسِ برابریِ بیت‌به‌بیتِ تصمیمِ کارت‌ها [webplan §۶]
// -----------------------------------------------------------------------------
//  چرا؟ webplan راهبردِ «Strangler Fig» را الزام می‌کند: بعد از هر گامِ استخراجِ گره
//  (P3, P3.5, P4, ...) خروجیِ منطقِ تصمیم باید *بیت‌به‌بیت* مثلِ قبل بماند. چون
//  /api/decision به Yahoo (شبکه/غیرقطعی) وابسته است، به‌جای آن، runCard را روی
//  برش‌های *ثابتِ* CSV در data/ اجرا می‌کنیم ⇒ نتیجه کاملاً قطعی و تکرارپذیر است.
//
//  کار:
//    node tools/decision_parity.mjs            → چاپِ hash + خلاصه (و ساختِ snapshot اگر نبود)
//    node tools/decision_parity.mjs --save     → ذخیرهٔ snapshot طلایی (baseline)
//    node tools/decision_parity.mjs --check    → مقایسه با snapshot؛ خروجِ کد ۱ اگر فرق کرد
//
//  snapshot در tools/decision_parity_snapshot.json ذخیره می‌شود.
// =============================================================================
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'
import { writeFileSync, readFileSync, existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..', '..')            // ریشهٔ مخزن (webapp/)
const SNAP = join(__dirname, 'decision_parity_snapshot.json')

// --- بارگذاریِ ماژول‌های TS از راهِ esbuild (بدونِ نیاز به build کامل) ---
async function loadTs(entry) {
  const res = await build({
    entryPoints: [entry], bundle: true, format: 'esm', write: false, platform: 'node',
  })
  const tmp = mkdtempSync(join(tmpdir(), 'parity-'))
  const modPath = join(tmp, 'mod.mjs')
  writeFileSync(modPath, res.outputFiles[0].text)
  return import(pathToFileURL(modPath).href)
}

// --- خواندنِ CSV به آرایهٔ کندل ---
function readCsv(path, maxRows) {
  const raw = readFileSync(path, 'utf8').trim().split('\n')
  const out = []
  const start = Math.max(1, maxRows ? raw.length - maxRows : 1)
  for (let i = start; i < raw.length; i++) {
    const [t, o, h, l, c, v] = raw[i].trim().split(',').map(Number)
    if ([t, o, h, l, c].every(Number.isFinite)) out[out.length] = { time: t, open: o, high: h, low: l, close: c, volume: Number.isFinite(v) ? v : 0 }
  }
  return out
}

// گِردسازیِ اعداد تا کاهشِ نویزِ ممیزِ شناور (تصمیم منطقی است، نه عددِ خام).
function round6(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) return x
  return Math.round(x * 1e6) / 1e6
}
// فقط میدان‌های *تصمیم‌ساز* را برمی‌داریم (نه متن‌های طولانی) تا hash پایدار بماند
// و به تغییرِ صرفِ متن حساس نباشد؛ اما به هر تغییرِ منطقی (state/dir/tp/sl/...) حساس است.
function pick(dec) {
  if (!dec) return null
  const sl = dec.sourceLayer || {}
  return {
    state: dec.state,
    headline: dec.headline,
    direction: dec.direction ?? null,
    entry: round6(dec.entry ?? null),
    tp: round6(dec.tp ?? null),
    sl: round6(dec.sl ?? null),
    rr: dec.rr ?? null,
    probability: dec.probability ?? null,
    layerCode: sl.code ?? null,
    layerKind: sl.kind ?? null,
    lots: round6(dec.sizing?.lots ?? null),
    others: (dec.otherLayers || []).map(o => ({
      code: o.code, state: o.state, direction: o.direction ?? null,
      entry: round6(o.entry ?? null), tp: round6(o.tp ?? null), sl: round6(o.sl ?? null),
    })),
    gates: (dec.cardTimeGates || []).map(g => ({ code: g.layerCode, open: g.windowOpen })),
    indCount: (dec.indicators || []).length,
  }
}

async function main() {
  const mode = process.argv[2] || ''
  const signalMod = await loadTs(join(__dirname, '..', 'src', 'signal.ts'))
  const regMod = await loadTs(join(__dirname, '..', 'src', 'strategy_registry.ts'))
  const { analyze } = signalMod
  const { runCard, REGISTERED_CARDS } = regMod

  // نگاشتِ کارت → (فایلِ CSV، gapSec، آیا طلاست)
  const CARD_CSV = {
    'XAUUSD-M5':  { file: 'XAUUSD_M5.csv',  gap: 300 },
    'XAUUSD-M15': { file: 'XAUUSD_M15.csv', gap: 900 },
    'XAUUSD-M30': { file: 'XAUUSD_M30.csv', gap: 1800 },
    'XAUUSD-H1':  { file: 'XAUUSD_H1.csv',  gap: 3600 },
    'XAUUSD-H4':  { file: 'XAUUSD_H4.csv',  gap: 14400 },
    'EURUSD-M15': { file: 'EURUSD_M15.csv', gap: 900 },
    'EURUSD-M30': { file: 'EURUSD_M30.csv', gap: 1800 },
  }

  const results = {}
  // برای هر کارت، چند «برشِ زمانیِ ثابت» می‌گیریم تا حالت‌های مختلف پوشش داده شوند.
  // برش‌ها با اندیس‌های ثابت از انتهای فایل انتخاب می‌شوند (قطعی).
  const OFFSETS = [0, 500, 1500, 3000, 7000]   // چند نقطهٔ گذشته از انتها
  const WINDOW = 420                            // کندل‌های کافی برای EMA200
  for (const card of REGISTERED_CARDS) {
    const meta = CARD_CSV[card]
    if (!meta) continue
    const all = readCsv(join(ROOT, 'data', meta.file))
    const perCard = []
    for (const off of OFFSETS) {
      const end = all.length - off
      const start = end - WINDOW
      if (start < 0) continue
      const slice = all.slice(start, end)
      if (slice.length < 240) continue
      const a = analyze(slice)
      const lastClosed = slice[slice.length - 1]
      const utcHour = Math.floor(lastClosed.time / 3600) % 24
      const ctx = {
        cardId: card, a, candles: slice,
        utcHour, times: slice.map(k => k.time), capital: 10000, riskPct: 1.0,
      }
      let dec
      try { dec = runCard(ctx) } catch (e) { dec = { state: 'ERROR', headline: String(e?.message || e) } }
      perCard.push({ off, endTime: lastClosed.time, dec: pick(dec) })
    }
    results[card] = perCard
  }

  const json = JSON.stringify(results, null, 2)
  const hash = createHash('sha256').update(json).digest('hex').slice(0, 16)

  if (mode === '--save') {
    writeFileSync(SNAP, json)
    console.log(`✅ snapshot ذخیره شد → ${SNAP}\n   hash=${hash}`)
    return
  }
  if (mode === '--check') {
    if (!existsSync(SNAP)) { console.error('❌ snapshot وجود ندارد؛ اول --save بزنید.'); process.exit(2) }
    const prev = readFileSync(SNAP, 'utf8')
    const prevHash = createHash('sha256').update(prev).digest('hex').slice(0, 16)
    if (prev === json) {
      console.log(`✅ برابریِ بیت‌به‌بیت تأیید شد (hash=${hash})`)
      process.exit(0)
    } else {
      console.error(`❌ خروجیِ تصمیم تغییر کرد! prev=${prevHash} now=${hash}`)
      // نمایشِ اولین کارت/برشِ متفاوت
      const p = JSON.parse(prev), n = JSON.parse(json)
      for (const card of Object.keys(n)) {
        const ps = JSON.stringify(p[card]), ns = JSON.stringify(n[card])
        if (ps !== ns) { console.error(`   اولین تفاوت در کارت: ${card}`); break }
      }
      process.exit(1)
    }
  }
  // حالتِ پیش‌فرض: چاپِ خلاصه
  let entries = 0, approaching = 0, neutral = 0
  for (const card of Object.keys(results)) {
    for (const r of results[card]) {
      if (r.dec?.state === 'ENTRY') entries++
      else if (r.dec?.state === 'APPROACHING') approaching++
      else neutral++
    }
  }
  console.log(`hash=${hash}  کارت‌ها=${Object.keys(results).length}  ENTRY=${entries} APPROACHING=${approaching} NEUTRAL/سایر=${neutral}`)
  if (!existsSync(SNAP)) { writeFileSync(SNAP, json); console.log(`ℹ️ snapshot اولیه ساخته شد → ${SNAP}`) }
}

main().catch(e => { console.error(e); process.exit(3) })
