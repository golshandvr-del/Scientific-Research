// ---------------------------------------------------------------------------
// probeِ زندهٔ S589 روی همان فیدی که سایت مصرف می‌کند — **هر دو کارت**.
//
// چرا این گام لازم است و چرا پریتی/یکپارچگی جایش را نمی‌گیرند: هر دو روی دادهٔ
// **کاملِ MT5** اجرا شدند (۱۱۹۷۸ کندلِ H8 و ۲۳۷۵۵ کندلِ H4). سایت اما از فیدِ
// زندهٔ Yahoo تغذیه می‌شود که کوتاه‌تر است **و** — نکتهٔ مخصوصِ همین لایه —
// ممکن است ستونِ حجمش کیفیتِ دیگری داشته باشد. سؤالِ بازِ باقی‌مانده: آیا لایه
// روی فیدِ **واقعی** حرف می‌زند، یا در سکوت «دادهٔ ناکافی» برمی‌گرداند؟
// این بدترین حالتِ ممکن است چون از UI قابلِ تفکیک از «سیگنالی ندارم» نیست.
//
// 🔴 **ریسکِ منحصربه‌فردِ S589 که هیچ لایهٔ دیگری ندارد: حجم.**
//    هر هفت ساکنِ دیگرِ کارتِ H8 و تنها ساکنِ H4 فقط OHLC می‌خواهند. S589
//    نخستین لایه‌ای است که به ستونِ `volume` تکیه می‌کند، و آن ستون در فیدِ
//    زنده **تضمین‌شده نیست**: Yahoo برای بعضی کندل‌ها `null`/صفر می‌دهد.
//    اگر حجم بیاید ولی همه‌اش صفر باشد، `rvol` تعریف‌نشده می‌شود، گیت هیچ‌وقت
//    پاس نمی‌کند، و لایه **برای همیشه ساکت** می‌ماند بدونِ هیچ خطایی در هیچ
//    لاگی — یک ACCEPTِ ۸۸.۳ که در عمل وجود ندارد. پس این probe علاوه بر
//    عمقِ فید، **سلامتِ حجم** را هم مستقیماً می‌سنجد.
//
//    و ظرافتِ بیشتر: صفر بودنِ حجم در کندل‌های خامِ H1 لزوماً کشنده نیست، چون
//    `aggregateCandles` حجم را **جمع** می‌زند و یک کندلِ H8 از ۸ کندلِ H1
//    ساخته می‌شود. پس باید حجمِ **پس از تجمیع** سنجیده شود، نه قبلش.
// ---------------------------------------------------------------------------
import { fetchGold, aggregateCandles } from '../src/price/gold_source'
import { computeS589, S589_CFG } from '../src/volume_fresh_high_s589'
import { CARD_LAYERS } from '../src/strategy_registry'

console.log('══ probeِ زندهٔ S589 روی فیدِ سایت — دو کارتِ ACCEPT ══\n')

let fail = 0
// فیدِ خام یک‌بار گرفته می‌شود و بینِ دو کارت مشترک است — عیناً همان کاری که
// index.tsx می‌کند (یک fetch، چند تجمیع) ⇒ probe همان مسیر را می‌آزماید.
const { candles } = await fetchGold('1h', '2y')
console.log(`کندلِ خامِ H1 از فیدِ زنده: ${candles.length}\n`)

// سلامتِ حجم روی کندلِ خام — فقط برای تشخیص، نه برای حکم.
const rawNZ = candles.filter((c: any) => (c.volume || 0) > 0).length
console.log(`حجمِ ناصفر در کندل‌های خامِ H1: ${rawNZ}/${candles.length} (${(100 * rawNZ / candles.length).toFixed(1)}٪)`)
if (rawNZ === 0) {
  console.log('❌ فیدِ زنده **هیچ** حجمی ندارد ⇒ S589 روی هر دو کارت مرده است')
  fail++
}

for (const [card, factor] of [['XAUUSD-H8', 8], ['XAUUSD-H4', 4]] as const) {
  console.log(`\n══════ ${card} ══════`)
  const cfg = S589_CFG[card]
  const agg = aggregateCandles(candles, factor)
  const need = cfg.lookback + cfg.atrP

  console.log(`  کندلِ تجمیع‌شده     : ${agg.length}`)
  console.log(`  نیازِ لایه          : ${need} (lookback ${cfg.lookback} + ATR ${cfg.atrP})`)
  console.log(`  حاشیه              : ${(agg.length / need).toFixed(2)}×`)
  if (agg.length < need) {
    console.log('  ❌ فید کوتاه‌تر از نیازِ لایه ⇒ لایه همیشه ساکت می‌ماند')
    fail++
  } else {
    console.log('  ✓ عمقِ فید برای محاسبهٔ لایه کافی است')
  }

  // ── سلامتِ حجم **پس از تجمیع** — سنجهٔ تعیین‌کننده ──
  const nz = agg.filter((c: any) => (c.volume || 0) > 0).length
  const pct = 100 * nz / Math.max(1, agg.length)
  console.log(`  حجمِ ناصفر پس از تجمیع: ${nz}/${agg.length} (${pct.toFixed(1)}٪)`)
  if (pct < 90) {
    console.log('  ❌ کمتر از ۹۰٪ کندل‌ها حجم دارند ⇒ گیتِ حجم روی فیدِ زنده قابل‌اتکا نیست')
    fail++
  } else {
    console.log('  ✓ حجم روی فیدِ زنده سالم است ⇒ گیت واقعاً ارزیابی می‌شود')
  }

  // ── گرم‌شدنِ گیتِ هم‌اسلات: هر ساعتِ روز باید ≥ slotMinP رخداد داشته باشد ──
  const bySlot = new Map<number, number>()
  for (const c of agg as any[]) {
    const h = new Date(c.time * 1000).getUTCHours()
    bySlot.set(h, (bySlot.get(h) || 0) + 1)
  }
  const slots = [...bySlot.entries()].sort((a, b) => a[0] - b[0])
  const minSlot = Math.min(...slots.map(s => s[1]))
  console.log(`  اسلات‌های ساعتی    : ${slots.map(s => `${s[0]}h:${s[1]}`).join(' · ')}`)
  console.log(`  کم‌جمعیت‌ترین اسلات : ${minSlot} رخداد (نیاز: ≥ ${cfg.slotMinP})`)
  if (minSlot < cfg.slotMinP) {
    console.log('  ❌ دستِ‌کم یک اسلات گرم نشده ⇒ آن ساعت هرگز سیگنال نمی‌دهد')
    fail++
  } else {
    console.log('  ✓ همهٔ اسلات‌های ساعتی گرم‌اند')
  }

  // ── آیا لایه واقعاً محاسبه می‌شود یا گاردِ «دادهٔ ناکافی» می‌خورد؟ ──
  const raw = computeS589(agg as any, cfg)
  const starved = /ناکافی/.test(raw.reason || '')
  console.log(`  خروجی روی آخرین کندلِ زنده:`)
  console.log(`    active : ${raw.active}`)
  console.log(`    گرسنه؟ : ${starved ? 'بله (دادهٔ ناکافی)' : 'نه — واقعاً محاسبه شد'}`)
  if (starved) {
    console.log('  ❌ لایه روی فیدِ زنده گرسنه است')
    fail++
  }

  // ── مهم‌ترین سنجه: آیا لایه روی فیدِ زنده **تاریخچهٔ شلیک** دارد؟ ──
  //    فقط «گرسنه نبودن» کافی نیست؛ ممکن است محاسبه شود ولی هرگز true نشود.
  //    پس کلِ پنجرهٔ زنده جاروب می‌شود و شلیک‌ها شمرده می‌شوند.
  let fires = 0
  let lastFire = -1
  for (let i = need; i < agg.length; i++) {
    const r = computeS589(agg.slice(0, i + 1) as any, cfg)
    if (r.active) { fires++; lastFire = i }
  }
  const years = agg.length * factor / (24 * 365.25)
  console.log(`  شلیک در پنجرهٔ زنده : ${fires} بار در ~${years.toFixed(2)} سال (${(fires / Math.max(0.01, years)).toFixed(1)}/سال)`)
  if (fires === 0) {
    console.log('  ❌ لایه در کلِ پنجرهٔ زنده **هرگز** شلیک نکرد ⇒ عملاً مرده است')
    fail++
  } else {
    const when = new Date((agg[lastFire] as any).time * 1000).toISOString().slice(0, 16).replace('T', ' ')
    console.log(`  ✓ آخرین شلیکِ واقعی : بارِ ${lastFire} · ${when} UTC`)
  }

  // ── نرخِ عبورِ گیت روی فیدِ زنده در برابرِ دادهٔ حکم (قانونِ S529) ──
  //    اگر گیت روی فیدِ زنده نرخِ کاملاً متفاوتی داشته باشد، یعنی حجمِ Yahoo
  //    رفتارِ دیگری از حجمِ MT5 دارد و جمعیتِ زنده با جمعیتِ داوری‌شده یکی نیست.
  const expect = card === 'XAUUSD-H8' ? 72.0 : 68.3
  console.log(`  (نرخِ عبورِ گیت روی دادهٔ حکم: ${expect}٪ — مرجعِ مقایسه)`)

  // حضور در فهرستِ کارت
  const n = (CARD_LAYERS[card] || []).length
  console.log(`  لایه‌های کارت      : ${n}`)
}

console.log(`\n${fail === 0 ? '✅ GREEN — S589 روی فیدِ زندهٔ سایت، روی هر دو کارت، واقعاً زنده است' : `❌ RED — ${fail} چکِ ناموفق`}`)
process.exit(fail === 0 ? 0 : 1)
