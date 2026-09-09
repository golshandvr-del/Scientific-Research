// integ_s1911_card.mjs — آزمونِ یکپارچگیِ end-to-end برای S1911 روی کارتِ XAUUSD-H8.
//
// چرا این آزمون لازم است (و چرا پریتی کافی نیست):
//   پریتی ثابت کرد «ماژول» عینِ مرجعِ پایتون است، ولی چیزی دربارهٔ **مسیرِ واقعیِ
//   سایت** نمی‌گوید. سایت لایه را از طریقِ runCard صدا می‌زند، که همهٔ لایه‌های
//   کارت را اجرا و طبقِ اولویتِ حالت مرتب می‌کند. سه چیز فقط از این مسیر معلوم
//   می‌شود:
//     ① آیا S1911 اصلاً در CARD_LAYERS['XAUUSD-H8'] هست و اجرا می‌شود؟
//     ② آیا روی کندلِ رویدادِ شناخته‌شده، ENTRY می‌دهد (نه اینکه گاردِ داده
//        خفه‌اش کند)؟
//     ③ آیا قیدِ (الف) ممیزیِ شاهدِ کاذب واقعاً برقرار است — یعنی در تلاقی،
//        تصمیمِ اصلیِ کارت از **S965** بیاید و S1911 در otherLayers بنشیند؟
//        این تنها چیزی است که «دو کادر ≠ دو ریسک» را تضمین می‌کند.
//
// نکتهٔ ③ مهم‌ترین است: چون هر ۸۲ رویدادِ S1911 داخلِ S965 است، هر ENTRYِ S1911
// حتماً یک ENTRYِ همزمانِ S965 دارد. اگر ترتیبِ آرایه اشتباه بود، کارت ممکن بود
// S1911 را primary کند و کاربر گمان کند شاهدِ تازه‌ای دارد.
//
// اجرا: cd web_tool && node integ_s1911_card.mjs
import fs from 'fs'
import { runCard, CARD_LAYERS } from './dist_parity/strategy_registry.js'

const CARD = 'XAUUSD-H8'
const FIX = '../results/_s1911_ckpt/parity_h8_fixture.json'
const WIN = 1500          // پنجرهٔ دنباله‌دار — راحت بالای کفِ ۲۸۵ کندلیِ لایه

const fx = JSON.parse(fs.readFileSync(FIX, 'utf8'))
const tail = fx.candles.map(c => ({
  time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
}))
const off = fx.offset            // نگاشتِ اندیسِ کلِ تاریخ → اندیسِ پنجرهٔ دنباله
const long = fx.py.idx_long || []
const short = fx.py.idx_short || []

// رویدادهایی که در پنجرهٔ دنباله هستند **و** پیش از خود به‌قدرِ کفِ لایه کندل دارند.
// کفِ واقعی ۲۸۵ کندل است (میانهٔ σ روی ۲۳۳ + گرم‌شدنِ σ)؛ ۴۰۰ را می‌گیریم تا
// حاشیه داشته باشیم ولی رویدادهای معرف را دور نریزیم.
const MIN_HIST = 400
const inTail = (i) => (i - off) >= MIN_HIST
const picks = []
for (const [dir, arr] of [['LONG', long], ['SHORT', short]]) {
  const av = arr.filter(inTail)
  // نمونهٔ معرف: اول / یک‌سوم / دوسوم / آخر
  for (const k of [0, Math.floor(av.length / 3), Math.floor(2 * av.length / 3), av.length - 1]) {
    const v = av[k]
    if (v != null && !picks.some(p => p.i === v)) picks.push({ i: v, dir })
  }
}

console.log(`\n=== ${CARD} === ${CARD_LAYERS[CARD].length} لایه روی کارت`)
console.log(`رویدادهای آزمون: ${picks.length} (از ${long.length} LONG + ${short.length} SHORT مرجع)\n`)

let fired = 0, primaryS965 = 0, s1911InOthers = 0, dirOk = 0, primaryS1911 = 0
const rows = []

for (const { i, dir } of picks) {
  const end = i - off                       // اندیسِ رویداد در پنجرهٔ دنباله
  const lo = Math.max(0, end - WIN + 1)
  const candles = tail.slice(lo, end + 1)   // ورود در t+1 ⇒ کندلِ رویداد آخرین است
  const last = candles[candles.length - 1]
  const d = new Date(last.time * 1000)
  const ctx = {
    cardId: CARD,
    a: { price: last.close, adx: 0, ema: {}, rsi: 50 },
    candles,
    utcHour: d.getUTCHours(),
    times: candles.map(c => c.time),
    capital: 10000, riskPct: 1.0,
  }
  const dec = runCard(ctx)
  const src = dec?.sourceLayer?.code || '—'
  const others = dec?.otherLayers || []
  const mine = others.find(o => o.code === 'S1911')
  const isPrimaryMine = src === 'S1911'
  // S1911 «حاضر» است اگر primary باشد یا در otherLayers دیده شود
  const present = isPrimaryMine || !!mine
  const myState = isPrimaryMine ? dec.state : mine?.state
  const myDir = isPrimaryMine ? dec.direction : mine?.direction

  if (present && myState === 'ENTRY') fired++
  if (src === 'S965') primaryS965++
  if (isPrimaryMine) primaryS1911++
  if (mine) s1911InOthers++
  if (present && myDir === dir) dirOk++

  rows.push({
    idx: i, refDir: dir, primary: src, primaryState: dec?.state,
    s1911_present: present, s1911_state: myState || null, s1911_dir: myDir || null,
    others: others.map(o => o.code),
  })
  console.log(`idx=${i} ref=${dir.padEnd(5)} primary=${src.padEnd(7)}(${dec?.state}) ` +
              `S1911: present=${present} state=${myState || '—'} dir=${myDir || '—'} ` +
              `| others=[${others.map(o => o.code).join(',')}]`)
}

// ── داوری ──────────────────────────────────────────────────────────────────
const nPick = picks.length
const checks = {
  // ⓿ گاردِ آزمونِ پوچ: اگر هیچ رویدادی آزمون نشود، بقیهٔ چک‌ها بی‌معنا سبز
  //   می‌شوند (a === b روی مجموعهٔ خالی همیشه درست است). اجرای اولِ همین اسکریپت
  //   دقیقاً به این تله افتاد و GREENِ دروغین داد. پس «چیزی آزمون شد» خودش یک چک است.
  someEventsTested: nPick > 0,
  // ① لایه روی کارت ثبت شده
  wired: CARD_LAYERS[CARD].length > 0,
  // ② روی هر رویدادِ مرجع، S1911 حاضر و ENTRY است (گاردِ داده خفه‌اش نکرده)
  firesOnEveryRefEvent: fired === nPick,
  // ③ جهت با مرجع یکی است
  directionMatches: dirOk === nPick,
  // ④ قیدِ (الف): S1911 هرگز primary نیست — چون زیرمجموعهٔ S965 است و S965 بالاتر
  //    است، پس در تلاقی همیشه S965 تصمیمِ اصلی را می‌دهد
  neverPrimary: primaryS1911 === 0,
  // ⑤ و عملاً S965 primary شده (شاهدِ تلاقیِ واقعی، نه خالی‌بودنِ کارت)
  supersetIsPrimary: primaryS965 === nPick,
}
const green = Object.values(checks).every(Boolean)

const out = {
  what: 'آزمونِ یکپارچگیِ S1911 از مسیرِ واقعیِ runCard · XAUUSD-H8',
  why: ('پریتی فقط ماژول را می‌سنجد. این آزمون می‌سنجد که سایت لایه را اجرا می‌کند، '
      + 'روی رویدادِ مرجع ENTRY می‌دهد، و مهم‌تر: قیدِ (الف) ممیزیِ شاهدِ کاذب '
      + 'برقرار است — S1911 زیرِ S965 است پس در تلاقی primary نمی‌شود و کاربر '
      + 'یک تصمیم می‌بیند نه دو شاهدِ ظاهراً مستقل.'),
  card: CARD,
  layers_on_card: CARD_LAYERS[CARD].length,
  events_tested: nPick,
  s1911_entry_count: fired,
  s1911_direction_match: dirOk,
  s1911_as_primary: primaryS1911,
  s1911_in_other_layers: s1911InOthers,
  s965_as_primary: primaryS965,
  checks,
  rows,
  verdict: green ? 'GREEN' : 'RED',
}
fs.mkdirSync('../results/_s1911_ckpt', { recursive: true })
fs.writeFileSync('../results/_s1911_ckpt/integ_card_s1911.json',
                 JSON.stringify(out, null, 1))
console.log('\n' + JSON.stringify({ checks, verdict: out.verdict }, null, 1))
if (!green) process.exit(1)
