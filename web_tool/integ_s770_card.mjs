// integ_s770_card.mjs — تستِ یکپارچگیِ end-to-end برای S770 روی **هر دو کارتِ
// ACCEPT** (XAUUSD-D1 و XAUUSD-H8) — یعنی کلِ استخری که حکمِ RQS2=82.4 بر آن
// صادر شده است.
//
// چرا این تست لازم است و پریتی کافی نیست: `parity_s770_signal.mjs` ثابت می‌کند
// تابعِ TS با پایتونِ مرجع بیت‌به‌بیت یکی است، ولی **ثابت نمی‌کند که سایت این
// تابع را صدا می‌زند**. سایت از `runCard(ctx)` عبور می‌کند که لایه‌های
// `CARD_LAYERS[cardId]` را اجرا و طبقِ رتبهٔ حالت مرتب می‌کند. اگر ثبتِ لایه در
// CARD_LAYERS فراموش شود، یا آداپتور آرگومان‌ها را جابه‌جا بدهد، یا کلیدِ
// S770_CFG اشتباه باشد ⇒ پریتی سبز می‌ماند و سایت خاموش. این تست همان شکاف را
// می‌بندد.
//
// ⚠️ نکتهٔ مخصوصِ S770 (که در لایه‌های قبلی نبود): متغیرِ حالتِ این لایه روی
//    **openِ روزِ تقویمیِ UTC** لنگر دارد، نه روی یک کندلِ تنها. پس این تست
//    عمداً پنجرهٔ ورودی را «برش» می‌دهد (مثلِ سایتِ زنده که فقط دمِ تاریخ را
//    دارد) تا اگر پورت به‌اشتباه به کندلِ صفرِ آرایه به‌عنوانِ «شروعِ روز» تکیه
//    کرده باشد، اینجا لو برود. پریتی این را می‌سنجد؛ اینجا از مسیرِ واقعیِ سایت.
//
// روش: کندل‌های واقعیِ هر کارت (از fixtureِ پریتی) را تا لحظهٔ سیگنال‌های
// شناخته‌شدهٔ پایتون به کلِ `runCard` می‌دهیم و می‌سنجیم که:
//   ① روی کندل‌های سیگنالیِ S770 ⇒ لایهٔ S770 در خروجی حاضر باشد و ENTRY بدهد
//      (چه لایهٔ اصلی، چه در otherLayers — چون S950/S965 در H8 و S800 در D1
//       هم‌کارت‌اند و ممکن است همان لحظه شلیک کنند و رتبهٔ اول را بگیرند).
//   ② جهتِ اعلام‌شده با جهتِ پایتون یکی باشد.
//   ③ هندسه (SL/TP) از مسیرِ سایت با پایتون یکی باشد — تلورانسِ ۱٪ برای اثرِ
//      گردکردنِ نمایشی، ولی جهتِ TP>SL باید مطلقاً برقرار باشد (قانونِ بودجه).
//   ④ روی کندل‌های بی‌سیگنال ⇒ S770 ساکت بماند (کنترلِ منفی، ضدِ سیگنالِ
//      همیشه-روشن که خطای کلاسیکِ لایه‌های «حالتی» است).
//
// اجرا: cd web_tool && node --import tsx integ_s770_card.mjs
import fs from 'fs'
import { runCard, CARD_LAYERS } from './src/strategy_registry.ts'

const CODE = 'S770'
const GOLD_PIP = 0.10

// پنجرهٔ ورودی: warmِ خودِ S770 حدودِ ۱۰۱ کندل است (ATR100)، ولی کارت‌ها لایه‌های
// سنگین‌تری هم دارند (S950 با warm=91، S800/D1 با کانالِ ۵۵ و چندکِ ۱۰۱ کندلی)
// ⇒ پنجرهٔ ۴۰۰ می‌دهیم تا هیچ لایه‌ای از کمبودِ داده نمیرد و شرایط عیناً مثلِ
// سایتِ زنده باشد (نه خوش‌بینانه‌تر).
const WIN = 400

const CARDS = [
  { card: 'XAUUSD-D1', fixture: '../results/_scan_S770/parity_D1_fixture.json' },
  { card: 'XAUUSD-H8', fixture: '../results/_scan_S770/parity_H8_fixture.json' },
]

// استخراجِ لایهٔ S770 از خروجیِ runCard — چه اصلی باشد چه در otherLayers.
function findS770(dec) {
  if (!dec) return null
  if (dec.sourceLayer?.code === CODE) {
    return { state: dec.state, direction: dec.direction, entry: dec.entry, sl: dec.sl, tp: dec.tp, where: 'primary' }
  }
  const o = (dec.otherLayers || []).find(x => x.code === CODE)
  if (o) return { state: o.state, direction: o.direction, entry: o.entry, sl: o.sl, tp: o.tp, where: 'otherLayers' }
  return null
}

const dirMatch = (d, expect) => {
  const s = String(d || '').toUpperCase()
  if (expect === 'LONG') return s.includes('LONG') || s.includes('BUY') || s.includes('خرید')
  return s.includes('SHORT') || s.includes('SELL') || s.includes('فروش')
}

let totalFail = 0
const summary = []

for (const { card, fixture } of CARDS) {
  console.log(`\n══════ ${card} ══════`)
  const fx = JSON.parse(fs.readFileSync(fixture, 'utf8'))
  const candlesAll = fx.candles
  const layers = CARD_LAYERS[card] || []
  console.log(`لایه‌های ثبت‌شدهٔ کارت: ${layers.length} · کندلِ fixture: ${candlesAll.length}`)

  // ⓪ آزمونِ ثبت: بدونِ این، بقیهٔ تست بی‌معناست.
  if (layers.length === 0) {
    console.log(`❌ کارت ${card} هیچ لایه‌ای ندارد!`); totalFail++; continue
  }

  const sigL = fx.py.idx_long.filter(i => i >= WIN)
  const sigS = fx.py.idx_short.filter(i => i >= WIN)
  const sigSet = new Set([...fx.py.idx_long, ...fx.py.idx_short])

  // کنترلِ منفی: ۶ کندلِ بی‌سیگنالِ آخر (بیشتر از نمونهٔ S965 چون لایهٔ S770
  // «حالتی» است و ریسکِ همیشه-روشن بودنش بالاتر ⇒ کنترلِ سخت‌تر لازم دارد).
  const quiet = []
  for (let i = candlesAll.length - 1; i >= WIN && quiet.length < 6; i--) {
    if (!sigSet.has(i)) quiet.push(i)
  }

  const cases = [
    ...sigL.map(i => ({ idx: i, expect: 'LONG' })),
    ...sigS.map(i => ({ idx: i, expect: 'SHORT' })),
    ...quiet.map(i => ({ idx: i, expect: 'NONE' })),
  ]

  let pass = 0, fail = 0, viaPrimary = 0, viaOther = 0
  let maxSlErr = 0, maxTpErr = 0, budgetViolations = 0
  const failures = []

  for (const { idx, expect } of cases) {
    const candles = candlesAll.slice(Math.max(0, idx - WIN + 1), idx + 1)
    const last = candles[candles.length - 1]
    const a = { price: last.close, adx: 0, ema: {}, rsi: 50 }
    const ctx = {
      cardId: card, a, candles,
      utcHour: new Date(last.time * 1000).getUTCHours(),
      times: candles.map(c => c.time), capital: 10000, riskPct: 1.0,
    }

    let dec = null, err = null
    try { dec = runCard(ctx) } catch (e) { err = e }
    if (err) {
      fail++; failures.push(`idx=${idx} استثنا: ${err.message}`); continue
    }

    const s = findS770(dec)
    const entered = !!s && (s.state === 'ENTRY' || !!s.entry)

    if (expect === 'NONE') {
      if (!entered) { pass++ } else {
        fail++; failures.push(`idx=${idx} کنترلِ منفی شکست: S770 بی‌دلیل ENTRY داد`)
      }
      continue
    }

    if (!entered) {
      fail++; failures.push(`idx=${idx} انتظار ${expect} ولی S770 از مسیرِ runCard شلیک نکرد`)
      continue
    }
    if (!dirMatch(s.direction, expect)) {
      fail++; failures.push(`idx=${idx} جهتِ غلط: انتظار ${expect} · دریافت ${s.direction}`)
      continue
    }

    // ③ هندسه از مسیرِ سایت در برابرِ پایتون (بر حسبِ pip).
    const pySl = fx.py.sl_pip[String(idx)] ?? fx.py.sl_pip[idx]
    const pyTp = fx.py.tp_pip[String(idx)] ?? fx.py.tp_pip[idx]
    if (pySl != null && s.sl != null && s.entry != null) {
      const siteSl = Math.abs(s.entry - s.sl) / GOLD_PIP
      const siteTp = Math.abs(s.tp - s.entry) / GOLD_PIP
      maxSlErr = Math.max(maxSlErr, Math.abs(siteSl - pySl) / Math.max(pySl, 1e-9))
      maxTpErr = Math.max(maxTpErr, Math.abs(siteTp - pyTp) / Math.max(pyTp, 1e-9))
      // قانونِ بودجه: TP باید بزرگ‌تر از SL باشد (RR=2.058).
      if (!(siteTp > siteSl)) budgetViolations++
    }

    if (s.where === 'primary') viaPrimary++; else viaOther++
    pass++
  }

  const geomOk = maxSlErr < 0.01 && maxTpErr < 0.01 && budgetViolations === 0
  console.log(`کیس‌ها: ${cases.length} (سیگنالی=${sigL.length + sigS.length} · کنترلِ منفی=${quiet.length})`)
  console.log(`نتیجه: PASS=${pass} · FAIL=${fail}`)
  console.log(`مسیرِ نمایش: لایهٔ اصلی=${viaPrimary} · otherLayers=${viaOther}`)
  console.log(`هندسه در برابرِ پایتون: خطای SL=${(maxSlErr * 100).toFixed(4)}٪ · TP=${(maxTpErr * 100).toFixed(4)}٪ · نقضِ TP>SL=${budgetViolations} ⇒ ${geomOk ? 'PASS ✅' : 'FAIL ❌'}`)
  if (failures.length) {
    console.log('نمونهٔ شکست‌ها:'); failures.slice(0, 8).forEach(f => console.log('   · ' + f))
  }
  if (!geomOk) fail++
  totalFail += fail
  summary.push({ card, cases: cases.length, pass, fail, viaPrimary, viaOther })
}

console.log('\n════════════════════════════════════════════════')
for (const s of summary) {
  console.log(`${s.card}: ${s.pass}/${s.cases} PASS · اصلی=${s.viaPrimary} · other=${s.viaOther}`)
}
if (totalFail === 0) {
  console.log('✅ یکپارچگیِ S770 روی **هر دو کارتِ ACCEPT** کامل PASS')
  console.log('   ⇒ لایه واقعاً از مسیرِ حقیقیِ runCard() سایت شلیک می‌کند،')
  console.log('     جهت و هندسه با پایتون یکی است، و روی کندلِ بی‌سیگنال ساکت می‌ماند.')
} else {
  console.log(`❌ ${totalFail} شکست — لایه از مسیرِ سایت درست کار نمی‌کند.`)
  process.exit(1)
}
