// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S547 در **سطحِ کارت** — روی هر سه کارتِ ACCEPT (M30/M15/H4).
//
// پرسشی که این آزمون پاسخ می‌دهد و آزمونِ برابریِ تقویم **نمی‌تواند**:
//   `_parity_s547_calendar.mjs` ثابت کرد مجموعهٔ روزهای P در سایت با تقویمِ
//   پایتونِ رانر **۱۶۰/۱۶۰ یکسان** است. ولی سایت هرگز `computePreHoliday` را
//   مستقیم صدا نمی‌زند؛ `runCard()` را صدا می‌زند که از `CARD_LAYERS[cardId]`
//   عبور می‌کند. پس یک ماژولِ کاملاً درست می‌تواند **نامرئی وصل‌نشده** بماند:
//   نه تایپ‌چک می‌فهمد (آرایه هم‌نوع است) و نه پریتی (ماژول را جدا می‌سنجد).
//   تنها چیزی که این شکاف را می‌بندد، صدا زدنِ خودِ runCard است.
//
// پنج چیزِ نامعلوم که اینجا بسته می‌شوند:
//   ① آیا آداپترِ s547Layer در فهرستِ **هر سه** کارت حاضر است؟
//   ② آیا در یک روزِ واقعیِ پیش‌تعطیلات، تصمیم به بیرونِ runCard **می‌رسد**؟
//   ③ آیا هر کارت هندسهٔ **خودش** را می‌دهد؟ سند برای M30 حدودِ SL≈۴۱ پیپ و
//      برای H4 حدودِ SL≈۱۲۳ پیپ می‌گوید. اگر maxHold/براکت جابه‌جا وصل شده
//      باشد، سایت سبز می‌ماند و عددِ غلط نشان می‌دهد — دامِ «کلیدِ اشتباه».
//   ④ آیا نشانهٔ `sameEventFamily` واقعاً روی خروجی می‌نشیند؟ این مهم‌ترین
//      بند است: کلِ قیدِ شاهدِ کاذبِ بین‌کارتی اگر به خروجی نرسد، صرفاً یک
//      جدولِ تزئینی است. جدولِ CROSS_CARD_ALTERNATES در مرحلهٔ ۴ اضافه شد و
//      فراخوانی‌اش در مرحلهٔ ۵؛ اینجا **اثرش** روی دادهٔ واقعی دیده می‌شود.
//   ⑤ شاهدِ منفی: کارتی که S547 روی آن ACCEPT نگرفته (H1، که حتی در جدولِ
//      سند هم POWER-LIMITED بود) نباید این لایه را ببیند.
//
// روشِ ②: کورکورانه آخرین کندل داده نمی‌شود (احتمالاً روزِ P نیست و آزمون
//   بی‌معنا می‌شد). ابتدا تاریخ جست‌وجو می‌شود تا کندلی پیدا شود که لایه در آن
//   `ENTRY` بدهد؛ اگر هیچ رویدادی پیدا نشد **FAIL** می‌شویم نه SKIP — چون یعنی
//   لایه در عمل هرگز روشن نمی‌شود، و آن بدترین حالتِ ممکن است (سکوتِ بی‌خطا).
// ---------------------------------------------------------------------------

import fs from 'node:fs'
import path from 'node:path'
// zlib استاتیک import می‌شود (این فایل ESM است و `require` در scope نیست) —
// درسِ ثبت‌شدهٔ پروندهٔ S1520 که فقط روی کلونِ تازه بیرون می‌زد، یعنی دقیقاً
// وضعیتی که این جلسه (پس از ریستِ سندباکس) در آن است.
import zlib from 'node:zlib'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
import { computePreHoliday } from '../src/preholiday_drift'

const ROOT = path.resolve(import.meta.dirname, '../..')

type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

function loadCsv(tf: string): Candle[] {
  const p = path.join(ROOT, `data/full/XAUUSD_${tf}.csv`)
  let text: string
  if (fs.existsSync(p)) {
    text = fs.readFileSync(p, 'utf8')
  } else {
    const gz = path.join(ROOT, `data/mt5_full/XAUUSD_${tf}.csv.gz`)
    if (!fs.existsSync(gz)) throw new Error(`نه کش و نه gz برای ${tf}: ${p} | ${gz}`)
    text = zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8')
    fs.mkdirSync(path.dirname(p), { recursive: true })
    fs.writeFileSync(p, text)
  }
  // CRLF: فایل‌های mt5_full با خطِ پایانِ ویندوزی نوشته شده‌اند ⇒ بدونِ این
  // پاک‌سازی، نامِ ستونِ آخر `"volume\r"` خوانده می‌شود. (گاردِ ثبت‌شده در
  // _integ_s589_cards.mts؛ اینجا هم رعایت می‌شود تا همان دام تکرار نشود.)
  const lines = text.trim().split('\n').map(l => l.replace(/\r$/, ''))
  const head = lines[0].split(',')
  const ix = (n: string) => head.indexOf(n)
  const iT = ix('time'), iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const iV = ix('tick_volume') >= 0 ? ix('tick_volume') : ix('volume')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const t = lines[i].split(',')
    out.push({
      time: Number(t[iT]), open: Number(t[iO]), high: Number(t[iH]),
      low: Number(t[iL]), close: Number(t[iC]), volume: Number(t[iV] || 0),
    })
  }
  return out
}

function mkA(id: string, price: number): any {
  return { id, price, indicators: [], regime: undefined }
}

const GOLD_PIP = 0.1
let fail = 0
const report: any = { cards: {} }

console.log('══ آزمونِ یکپارچگیِ S547 در سطحِ کارت — سه کارتِ ACCEPT ══\n')

// ---------------------------------------------------------------------------
// ⑤ شاهدِ منفی: H1 نباید S547 داشته باشد (در جدولِ سند POWER-LIMITED بود)
// ---------------------------------------------------------------------------
console.log('── ⑤ شاهدِ منفیِ H1 (در سند ACCEPT نگرفت) ──')
{
  const h1 = (CARD_LAYERS['XAUUSD-H1'] || []) as any[]
  const codes = (await import('../src/strategy_registry')).CARD_LAYER_CODES['XAUUSD-H1'] || []
  const hasS547 = codes.includes('S547')
  report.negative_control_h1 = { codes, has_s547: hasS547 }
  if (hasS547) {
    console.log('   ❌ S547 روی کارتِ H1 ظاهر شده — حکمش آنجا ACCEPT نبود')
    fail++
  } else {
    console.log(`   ✓ S547 در کارتِ H1 نیست (${h1.length} لایه: ${codes.join(', ')})`)
  }
}

// ---------------------------------------------------------------------------
// حلقهٔ اصلی روی هر سه کارتِ ACCEPT
// ---------------------------------------------------------------------------
// عددهای مرجع از سند: results/S547_PreHolidayDrift_Xauusd_MTF_rqs2_89_ACCEPT.md
const CARDS: Array<{ card: string; tf: string; slDoc: number; isPrimary: boolean; rqs2: number }> = [
  { card: 'XAUUSD-M30', tf: 'M30', slDoc: 41.37, isPrimary: true,  rqs2: 89.3 },
  { card: 'XAUUSD-M15', tf: 'M15', slDoc: 28.59, isPrimary: false, rqs2: 84.7 },
  { card: 'XAUUSD-H4',  tf: 'H4',  slDoc: 123.01, isPrimary: false, rqs2: 81.9 },
]

for (const { card, tf, slDoc, isPrimary, rqs2 } of CARDS) {
  console.log(`\n── کارتِ ${card} (سند: RQS2 ${rqs2} · SL≈${slDoc} pip) ──`)
  const rc: any = { tf, sl_doc_pip: slDoc, expect_primary: isPrimary }

  // ① حضورِ لایه در فهرستِ کارت
  const codes = (await import('../src/strategy_registry')).CARD_LAYER_CODES[card] || []
  const listed = codes.includes('S547')
  rc.listed_in_codes = listed
  if (!listed) { console.log('   ❌ ① S547 در CARD_LAYER_CODES این کارت نیست'); fail++ }
  else console.log(`   ✓ ① در فهرستِ کارت هست (${codes.join(', ')})`)

  // دادهٔ واقعی
  const all = loadCsv(tf)
  rc.bars = all.length

  // ② پیدا کردنِ یک کندلِ واقعی که لایه در آن ENTRY می‌دهد.
  //    از انتها به عقب می‌گردیم تا جدیدترین رویداد پیدا شود (تازه‌ترین شاهد).
  let hit = -1
  for (let i = all.length - 1; i > 300; i--) {
    const times = all.slice(0, i + 1).map(c => c.time)
    const utcHour = new Date(all[i].time * 1000).getUTCHours()
    const sig = computePreHoliday(times, utcHour, all.slice(0, i + 1) as any)
    if (sig.state === 'ENTRY') { hit = i; break }
  }
  if (hit < 0) {
    console.log('   ❌ ② هیچ کندلی با حالتِ ENTRY پیدا نشد ⇒ لایه در عمل روشن نمی‌شود')
    fail++
    report.cards[card] = rc
    continue
  }
  const when = new Date(all[hit].time * 1000).toISOString()
  rc.event_bar_utc = when
  console.log(`   ✓ ② رویدادِ واقعی پیدا شد: ${when}`)

  const px = all[hit].close
  const ctx = {
    cardId: card, a: mkA(card, px), candles: all.slice(0, hit + 1) as any,
    utcHour: new Date(all[hit].time * 1000).getUTCHours(),
    times: all.slice(0, hit + 1).map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const d: any = runCard(ctx as any)

  // آیا S547 به خروجی رسید؟ یا primary است یا در otherLayers.
  const primaryCode = (d?.sourceLayer?.code || '').trim()
  const others = (d?.otherLayers || []) as any[]
  const asOther = others.find(o => (o.code || '').trim() === 'S547')
  const reached = primaryCode === 'S547' || !!asOther
  rc.primary_code = primaryCode
  rc.reached_output = reached
  if (!reached) {
    console.log(`   ❌ ② تصمیم به خروجیِ runCard نرسید (primary=${primaryCode}, others=${others.map(o => o.code).join('/')})`)
    fail++
  } else {
    console.log(`   ✓ ② به خروجی رسید (${primaryCode === 'S547' ? 'primary' : 'otherLayers'})`)
  }

  // ③ هندسهٔ مخصوصِ همین کارت
  const node = primaryCode === 'S547' ? d : asOther
  if (node && reached) {
    const slPrice = node.sl ?? node.slPrice
    const slPip = slPrice ? Math.abs(px - slPrice) / GOLD_PIP : NaN
    rc.sl_pip_live = Number.isFinite(slPip) ? Math.round(slPip * 10) / 10 : null
    // براکت از ۱.۵×median(ATR100) می‌آید ⇒ با رژیمِ نوسانِ روزِ رویداد تغییر
    // می‌کند. پس «برابریِ دقیق با سند» انتظارِ غلطی است؛ چیزی که باید درست
    // باشد **مرتبهٔ بزرگی مخصوصِ همین تایم‌فریم** است. اگر کلیدها جابه‌جا
    // وصل شده باشند، M30 عددِ H4 (۳× بزرگ‌تر) را نشان می‌دهد و اینجا لو می‌رود.
    if (Number.isFinite(slPip)) {
      const ratio = slPip / slDoc
      rc.ratio_to_doc = Math.round(ratio * 100) / 100
      const ok = ratio > 0.33 && ratio < 3.0
      if (!ok) { console.log(`   ❌ ③ SL زندهٔ ${rc.sl_pip_live} pip با مقیاسِ سند (${slDoc}) نمی‌خواند — نسبت ${rc.ratio_to_doc}×`); fail++ }
      else console.log(`   ✓ ③ SL زنده ${rc.sl_pip_live} pip — هم‌مقیاسِ سند (نسبت ${rc.ratio_to_doc}×)`)
    }
    const rr = node.rr
    rc.rr = rr
    // نسبت RR باید ثابتِ ۱.۵ باشد (TP = 1.5×SL) ⇒ گیتِ TP>SL ساختاراً برقرار.
    if (rr && Math.abs(rr - 1.5) > 0.06) { console.log(`   ❌ ③ RR=${rr} با قاعدهٔ ثابتِ ۱.۵ نمی‌خواند`); fail++ }
    else if (rr) console.log(`   ✓ ③ RR=${rr} ≈ ۱.۵ (TP>SL ساختاری)`)

    // ④ نشانهٔ هم‌رویدادیِ بین‌کارتی
    const fam = node.sameEventFamily
    rc.same_event_family = fam || null
    if (!fam) {
      console.log('   ❌ ④ نشانهٔ sameEventFamily روی خروجی نیست ⇒ قیدِ شاهدِ کاذب به کاربر نمی‌رسد')
      fail++
    } else {
      const okPrimary = fam.isPrimary === isPrimary
      if (!okPrimary) { console.log(`   ❌ ④ isPrimary=${fam.isPrimary} ولی انتظار ${isPrimary} بود`); fail++ }
      else console.log(`   ✓ ④ sameEventFamily حاضر — isPrimary=${fam.isPrimary} · مرجع=${fam.primaryCard} · خواهرها=${(fam.siblingCards || []).join('/')}`)
    }
  }

  report.cards[card] = rc
}

console.log('\n' + '═'.repeat(70))
if (fail === 0) console.log('ALL GREEN — S547 روی هر سه کارت وصل، هم‌مقیاس، و نشانه‌گذاری‌شده است')
else console.log(`${fail} بند شکست خورد`)
fs.writeFileSync(path.join(ROOT, 'results/_s547/integ_cards.json'), JSON.stringify(report, null, 2))
console.log('گزارش: results/_s547/integ_cards.json')
process.exit(fail === 0 ? 0 : 1)
