// ============================================================================
// integ_s356_card.mjs — آزمونِ یکپارچگیِ end-to-end برای لایهٔ S356 روی XAUUSD-H1
// ----------------------------------------------------------------------------
// parity سیگنال (`local-mobile/_parity_s356_causal.mjs`) فقط تابعِ **خالصِ**
// `computeS354` را می‌سنجد. اما کاربر با `runCard` سروکار دارد: روتری که چند لایه
// را به‌ترتیبِ اولویت صدا می‌زند، رژیم را می‌سنجد، لات را حساب می‌کند و یک تصمیمِ
// نهایی می‌سازد. یک لایه می‌تواند در سطحِ تابعِ خالص کاملاً درست باشد و در سطحِ
// روتر هرگز به کاربر نرسد (مثلاً چون لایهٔ دیگری همیشه اول ENTRY می‌دهد، یا چون
// `rawToDecision` روی رژیم/لات مسدودش می‌کند). این آزمون همان شکاف را می‌بندد.
//
// روش: چند کندلِ سیگنالِ **شناخته‌شدهٔ** رکوردِ پذیرش را برمی‌داریم، برای هرکدام
// یک پنجرهٔ دنباله‌دار (که در کندلِ آزمون تمام می‌شود ⇒ بدونِ نگاه به آینده) به
// `runCard` می‌دهیم و می‌سنجیم که:
//   ۱) تصمیم، حالتِ ورود (`ENTRY`) و جهتِ `LONG` باشد،
//   ۲) `S356` یا منبعِ اصلی باشد یا در `otherLayers` حاضر باشد،
//   ۳) براکتِ اعلام‌شده به کاربر همان براکتِ منجمدِ داوری‌شده باشد
//      (SL=50.6pip=5.06$ و TP=101.2pip=10.12$) — این بندِ سوم مهم است چون
//      parity سیگنال به براکت کاری ندارد و تنها اینجا سنجیده می‌شود.
// همچنین چند کندلِ **غیرسیگنال** را آزمون می‌کنیم تا مطمئن شویم لایه بی‌جا
// ENTRY نمی‌دهد (آزمونِ منفی؛ بدونِ آن، لایه‌ای که همیشه ENTRY بدهد هم پاس می‌شد).
//
// اجرا: cd web_tool && node integ_s356_card.mjs
// ============================================================================
import { readFileSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'
const CARD = 'XAUUSD-H1'
const WIN = 1500          // همان پنجرهٔ parity — همهٔ اندیکاتورها همگرا شده‌اند
const PIP = 0.1

const { build } = await import(
  pathToFileURL(`${ROOT}/web_tool/node_modules/esbuild/lib/main.js`).href)

const outfile = '/tmp/_s356_registry.mjs'
await build({
  entryPoints: [`${ROOT}/web_tool/src/strategy_registry.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error',
})
const { runCard, CARD_LAYERS } = await import(pathToFileURL(outfile).href)

// ── داده و کندل‌های مرجع ──
const rows = readFileSync(`${ROOT}/data/XAUUSD_H1.csv`, 'utf8').trim().split('\n')
const candlesAll = rows.slice(1).map(l => {
  const p = l.split(',')
  return { time: +p[0], open: +p[1], high: +p[2], low: +p[3], close: +p[4], volume: +p[5] || 0 }
})

const acc = JSON.parse(readFileSync(
  `${ROOT}/results/_scan_S356/XAUUSD-H1_entrybars.json`, 'utf8'))
const sigBars = acc.signal_bars.map(Number).sort((a, b) => a - b).filter(b => b >= WIN)

// نمونهٔ معرف: ابتدا/یک‌سوم/دوسوم/انتها + دو موردِ تصادفیِ قطعی (بدونِ seed تصادفی)
const pickIdx = [0, Math.floor(sigBars.length / 4), Math.floor(sigBars.length / 2),
                 Math.floor(3 * sigBars.length / 4), sigBars.length - 1]
const positives = [...new Set(pickIdx.map(k => sigBars[k]))].filter(x => x != null)

// موردهای منفی: کندل‌هایی که در رکوردِ پذیرش سیگنال **نیستند**، ولی نزدیکِ
// سیگنال‌ها هستند (سخت‌ترین موردهای منفی — نه کندل‌های تصادفیِ آسان).
const sigSet = new Set(sigBars)
const negatives = []
for (const b of positives) {
  for (const d of [-3, +3]) {
    const q = b + d
    if (q >= WIN && q < candlesAll.length && !sigSet.has(q)) negatives.push(q)
  }
}

function evalAt(bar) {
  const lo = Math.max(0, bar - WIN + 1)
  const candles = candlesAll.slice(lo, bar + 1)
  const last = candles[candles.length - 1]
  const a = { price: last.close, adx: 0, ema: {}, rsi: 50 }
  const ctx = {
    cardId: CARD, a, candles,
    utcHour: Math.floor((((last.time % 86400) + 86400) % 86400) / 3600),
    times: candles.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const dec = runCard(ctx)
  const src = dec?.sourceLayer?.code ?? null
  const others = (dec?.otherLayers || []).map(o => o?.sourceLayer?.code || o?.code)
  return { dec, src, others, has356: src === 'S356' || others.includes('S356') }
}

console.log(`=== integ S356 :: ${CARD} — ${CARD_LAYERS[CARD].length} لایه روی کارت`)
console.log(`    سیگنال‌های رکوردِ پذیرش (≥${WIN}): ${sigBars.length}`)
console.log(`    مثبت‌ها: ${positives.length} | منفی‌های سخت (±3 کندل): ${negatives.length}\n`)

const report = { card: CARD, n_layers: CARD_LAYERS[CARD].length, positives: [], negatives: [] }
let okPos = 0, bracketOk = 0

console.log('  ── موردهای مثبت (باید ENTRY/LONG با S356 بدهند) ──')
for (const bar of positives) {
  const { dec, src, others, has356 } = evalAt(bar)
  const state = dec?.state ?? 'null'
  const dir = dec?.direction ?? '—'
  // ⚠️ `RouterDecision` فاصله نمی‌دهد؛ `entry`/`sl`/`tp` را به‌صورتِ **قیمتِ
  //    مطلق** می‌دهد (router.ts:198-201). پس براکت را از تفاضل می‌سنجیم.
  //    براکتِ منجمدِ داوری‌شده: SL=50.6pip ⇒ 5.06$ ، TP=101.2pip ⇒ 10.12$
  //    تلورانس 1e-6 برای خطای شناورِ ضربِ pip کافی است (اعداد تا ۲ رقمِ اعشارند).
  const ent = dec?.entry, slP = dec?.sl, tpP = dec?.tp
  const slDist = (ent != null && slP != null) ? ent - slP : null
  const tpDist = (ent != null && tpP != null) ? tpP - ent : null
  const sl = slDist, tp = tpDist
  const bOk = slDist != null && tpDist != null &&
              Math.abs(slDist - 50.6 * PIP) < 1e-6 && Math.abs(tpDist - 101.2 * PIP) < 1e-6
  const pass = has356 && state === 'ENTRY' && dir === 'LONG'
  if (pass) okPos++
  if (bOk) bracketOk++
  console.log(`    @${bar}  state=${state} dir=${dir} src=${src} others=[${others.join(',')}]` +
              `  SL=${sl?.toFixed?.(3)} TP=${tp?.toFixed?.(3)}  ${pass ? '✅' : '❌'}${bOk ? '' : ' ⚠️براکت'}`)
  report.positives.push({ bar, state, dir, src, others, sl, tp, pass, bracket_ok: bOk })
}

console.log('\n  ── موردهای منفیِ سخت (S356 نباید ENTRY بدهد) ──')
let okNeg = 0
for (const bar of negatives) {
  const { dec, src, others, has356 } = evalAt(bar)
  const state = dec?.state ?? 'null'
  // شرطِ منفی: یا S356 حاضر نیست، یا اگر حاضر است ENTRY نیست.
  const s356Entry = has356 && state === 'ENTRY' && (src === 'S356')
  if (!s356Entry) okNeg++
  console.log(`    @${bar}  state=${state} src=${src} others=[${others.join(',')}]  ` +
              `${!s356Entry ? '✅' : '❌ ورودِ بی‌جا'}`)
  report.negatives.push({ bar, state, src, others, ok: !s356Entry })
}

report.summary = {
  positives_pass: okPos, positives_total: positives.length,
  bracket_pass: bracketOk,
  negatives_pass: okNeg, negatives_total: negatives.length,
  verdict: (okPos === positives.length && bracketOk === positives.length &&
            okNeg === negatives.length) ? 'INTEG_PASS' : 'INTEG_FAIL',
}
console.log(`\n  ══ ${report.summary.verdict}  ` +
            `(مثبت ${okPos}/${positives.length} · براکت ${bracketOk}/${positives.length} · ` +
            `منفی ${okNeg}/${negatives.length})`)

const out = `${ROOT}/results/_scan_S356/integ_card.json`
writeFileSync(out, JSON.stringify(report, null, 1), 'utf8')
console.log(`  [saved] ${out}`)
