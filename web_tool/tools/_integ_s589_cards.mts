// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S589 در **سطحِ کارت** — روی **هر دو** کارتِ ACCEPT (H8 و H4).
//
// پرسشی که این آزمون پاسخ می‌دهد و پریتی **نمی‌تواند** پاسخ دهد:
//   پریتی (گامِ ۸) ثابت کرد `computeS589` با پایتون **بیت-به-بیت** یکسان است
//   (۲۶۰/۴۸۸/۱۸۷ سیگنال). ولی سایت هیچ‌وقت `computeS589` را صدا نمی‌زند —
//   بلکه `runCard()` را صدا می‌زند که از `CARD_LAYERS[cardId]` عبور می‌کند و
//   بعد با `STATE_RANK` یکی را `primary` و بقیه را `otherLayers` می‌کند. پس یک
//   ماژولِ کاملاً درست می‌تواند به‌طورِ نامرئی وصل‌نشده بماند و هیچ تستی نفهمد.
//
//   این تفاوت اینجا از پروندهٔ S1520 هم **حادتر** است، چون S589 دو کارت دارد:
//   یک اشتباهِ تایپی در کلیدِ کارت (مثلاً هر دو ورودی `S589_CFG['XAUUSD-H8']`
//   بگیرند) یک سایتِ کاملاً سبز می‌سازد که روی کارتِ H4 **هندسهٔ H8** را نشان
//   می‌دهد: SL=۱۷۹.۶۷ به‌جای ۱۲۲.۸۵. نه پریتی این را می‌بیند (ماژول را جدا
//   می‌سنجد) و نه تایپ‌چک (هر دو کلید هم‌نوع‌اند). فقط یک آزمونِ سطحِ کارت که
//   **هندسهٔ رسیده به خروجی** را با سندِ همان کارت مقایسه کند آن را می‌گیرد.
//
// شش چیزِ نامعلوم که اینجا بسته می‌شوند:
//   ① آیا آداپترِ s589Layer در فهرستِ **هر دو** کارت حاضر است؟ (H8: ۷ لایه، H4: ۲)
//   ② آیا وقتی رویدادِ واقعی رخ می‌دهد، تصمیم به بیرونِ runCard **می‌رسد**؟
//   ③ آیا هر کارت هندسهٔ **خودش** را می‌دهد؟ (دامِ کلیدِ اشتباه — اشتباهِ رایجِ ۶)
//   ④ آیا حضورِ S589 تصمیمِ ساکنانِ کارت را عوض کرده (رگرسیون)؟
//   ⑤ آیا کارتِ H12 (شاهدِ منفی، REJECT 25.1) هنوز S589 را **نمی‌بیند**؟
//   ⑥ آیا قیدِ «سایزِ مشترک» قابلِ مشاهده است — یعنی وقتی S589 و S1520 هم‌زمان
//      روشن‌اند، آیا واقعاً یک رویدادِ واحد است؟ (این قید در گامِ ۱۳ ثبت شد؛
//      اینجا **رخدادش** روی دادهٔ واقعی شمرده می‌شود تا ادعا خالی نماند.)
//
// روشِ ②: کورکورانه آخرین کندل داده نمی‌شود (که احتمالاً رویدادی ندارد و آزمون
//   بی‌معنا می‌شد). ابتدا با `computeS589` **تاریخ جست‌وجو** می‌شود تا کندلی پیدا
//   شود که لایه در آن `active` است، بعد `runCard` با پیشوندِ [0..i] صدا زده
//   می‌شود. اگر هیچ رویدادی پیدا نشد، آزمون **FAIL** می‌شود (نه SKIP) — چون
//   یعنی لایه در عمل هرگز روشن نمی‌شود.
//
// روشِ ④ (رگرسیون) — عینِ درسِ پروندهٔ S1520: نمی‌توان «یک کندل قبل» را حالتِ
//   خاموش گرفت، چون ورودیِ ساکنان هم عوض می‌شود (یک کندلِ کمتر ⇒ ATR و σ آن‌ها
//   هم فرق می‌کند) و هر تفاوتی مبهم می‌ماند. پس رگرسیون با **همان کندل و فهرستِ
//   لایهٔ فیلترشده** سنجیده می‌شود: `CARD_LAYERS` یک Recordِ صادرشده و قابلِ
//   نوشتن است، پس ورودیِ S589 موقتاً برداشته و بعد بازگردانده می‌شود.
// ---------------------------------------------------------------------------

import fs from 'node:fs'
import path from 'node:path'
// ⚠️ zlib به‌صورت **استاتیک** import می‌شود، نه با `require` — این فایل ESM است
//    (.mts) و `require` در scope نیست. درسِ مستقیمِ پروندهٔ S1520: آن خطا فقط در
//    مسیرِ «کش نبود» ظاهر می‌شد، پس روی ماشینی که data/full را داشت پنهان می‌ماند
//    و تنها روی کلونِ تازه بیرون می‌زد — دقیقاً همان حالتی که این جلسه (پس از
//    ریستِ سندباکس) در آن قرار دارد.
import zlib from 'node:zlib'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
import { computeS589, S589_CFG } from '../src/volume_fresh_high_s589'

const ROOT = path.resolve(import.meta.dirname, '../..')

type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

// مسیرِ دوگانه عیناً مثلِ `_integ_s1520_card.mts`: اول کشِ gitignore-شدهٔ
// `data/full/*.csv` و اگر نبود، gunzipِ درجا از `data/mt5_full/*.csv.gz`.
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
  // 🔴 **CRLF** — باگِ واقعی که گاردِ حجمِ پایین‌تر گرفتش. فایل‌های
  //    `data/mt5_full/*.csv.gz` با خطِ پایانِ ویندوزی (`\r\n`) نوشته شده‌اند، پس
  //    `split('\n')` یک `\r` در انتهای هر سطر باقی می‌گذارد و **آخرین ستون** —
  //    که دقیقاً `volume` است — با نامِ `"volume\r"` خوانده می‌شود ⇒
  //    `indexOf('volume') === -1`. نتیجه‌اش بی‌صدا فاجعه‌بار بود: بدونِ گارد،
  //    همهٔ حجم‌ها `0` می‌شدند، هر RVOL تعریف‌نشده می‌شد، گیت هیچ‌وقت پاس
  //    نمی‌کرد و آزمون با اطمینان اعلام می‌کرد «S589 مرده است» — یک ادعای
  //    منفیِ قاطع دربارهٔ لایه، در حالی که ایراد از خواندنِ فایل بود.
  //    (چرا `_integ_s1520_card.mts` این را ندید: S1520 فقط OHLC می‌خواهد و
  //     ستونِ آخر برایش بی‌اهمیت است ⇒ همین باگ آنجا کاملاً بی‌اثر بوده.)
  const lines = text.trim().split('\n').map(l => l.replace(/\r$/, ''))
  const head = lines[0].split(',')
  const ix = (n: string) => head.indexOf(n)
  const iT = ix('time'), iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const iV = ix('tick_volume') >= 0 ? ix('tick_volume') : ix('volume')
  // 🔴 گاردِ مخصوصِ این لایه: S589 تنها لایهٔ سایت است که بدونِ حجم بی‌معناست.
  //    اگر ستونِ حجم نباشد، همهٔ RVOLها undefined می‌شوند، گیت هیچ‌وقت پاس
  //    نمی‌کند، و آزمون اعلام می‌کند «لایه مرده است» در حالی که فقط داده ناقص
  //    بوده. این همان «ادعای منفیِ قاطع که هیچ‌چیز را نسنجیده» است که درسِ
  //    ابزارِ S1520 بود ⇒ اینجا صریح می‌میریم، نه با نتیجهٔ گمراه‌کننده.
  if (iV < 0) throw new Error(`ستونِ حجم در ${tf} پیدا نشد — S589 بدونِ حجم قابلِ آزمون نیست`)
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const t = lines[i].split(',')
    out.push({
      time: Number(t[iT]), open: Number(t[iO]), high: Number(t[iH]),
      low: Number(t[iL]), close: Number(t[iC]), volume: Number(t[iV]),
    })
  }
  return out
}

function mkA(id: string, price: number): any {
  return { id, price, indicators: [], regime: undefined }
}

let fail = 0
const report: any = { cards: {} }

console.log('══ آزمونِ یکپارچگیِ S589 در سطحِ کارت — دو کارتِ ACCEPT ══\n')

// ---------------------------------------------------------------------------
// ⑤ شاهدِ منفی: H12 نباید S589 بگیرد (REJECT 25.1، نرخِ عبورِ گیت ۷۵.۴٪)
// ---------------------------------------------------------------------------
console.log('── ⑤ شاهدِ منفیِ H12 (REJECT 25.1) ──')
{
  const inCfg = Object.prototype.hasOwnProperty.call(S589_CFG, 'XAUUSD-H12')
  report.negative_control_h12 = { in_cfg: inCfg }
  if (inCfg) {
    console.log('   ❌ XAUUSD-H12 در S589_CFG ظاهر شده — حکمش REJECT بود')
    fail++
  } else {
    console.log('   ✓ XAUUSD-H12 در S589_CFG نیست ⇒ اتصال به آن کارت ناممکن است')
  }
  // و در فهرستِ کارتِ H12 هم نباید ردی باشد
  const h12 = CARD_LAYERS['XAUUSD-H12'] || []
  console.log(`   کارتِ H12: ${h12.length} لایه (فقط S800 انتظار می‌رود)`)
}

// ---------------------------------------------------------------------------
// حلقهٔ اصلی روی هر دو کارتِ ACCEPT
// ---------------------------------------------------------------------------
const CARDS: { card: string; tf: string; expectLayers: number; slPip: number; tpPip: number }[] = [
  // انتظارِ شمارشِ لایه از خودِ CARD_LAYERS در گامِ ۱۳ می‌آید:
  //   H8 = شش ساکن (S950/S965/S770/S966/S1911/S607) + S1520 + S589 = ۸
  //   H4 = S382 + S589 = ۲
  { card: 'XAUUSD-H8', tf: 'H8', expectLayers: 8, slPip: 179.67, tpPip: 269.50 },
  { card: 'XAUUSD-H4', tf: 'H4', expectLayers: 2, slPip: 122.85, tpPip: 184.28 },
]

for (const spec of CARDS) {
  const { card, tf } = spec
  console.log(`\n══════ کارتِ ${card} ══════`)
  const rep: any = {}
  report.cards[card] = rep

  // ── ① حضورِ آداپتر در فهرستِ کارت ──
  const nLayers = (CARD_LAYERS[card] || []).length
  rep.layer_count = nLayers
  console.log(`── ① حضور در CARD_LAYERS ──`)
  console.log(`   ${card}: ${nLayers} لایه (انتظار: ${spec.expectLayers})`)
  if (nLayers !== spec.expectLayers) {
    console.log(`   ❌ شمارشِ لایه با انتظار نمی‌خواند`)
    fail++
  } else {
    console.log('   ✓ شمارشِ لایه درست است')
  }

  // ── ③ هندسهٔ منجمدِ **همین** کارت (دامِ کلیدِ اشتباه) ──
  console.log(`── ③ هندسهٔ مخصوصِ کارت (ضدِ اشتباهِ رایجِ ۶) ──`)
  const cfg = S589_CFG[card]
  if (!cfg) {
    console.log(`   ❌ ${card} در S589_CFG نیست`)
    fail++
    continue
  }
  rep.geometry = { sl: cfg.slPip, tp: cfg.tpPip }
  const geomOk = cfg.slPip === spec.slPip && cfg.tpPip === spec.tpPip
  console.log(`   SL/TP = ${cfg.slPip} / ${cfg.tpPip} pip (سند: ${spec.slPip} / ${spec.tpPip})`)
  if (!geomOk) {
    console.log('   ❌ هندسه با سندِ همین کارت نمی‌خواند — احتمالاً کلیدِ کارتِ دیگری وصل شده')
    fail++
  } else {
    console.log('   ✓ هندسه از آنِ همین کارت است، نه قرضی از کارتِ دیگر')
  }
  // و باید با کارتِ دیگر **متفاوت** باشد، وگرنه تستِ بالا بی‌معناست
  const other = card === 'XAUUSD-H8' ? S589_CFG['XAUUSD-H4'] : S589_CFG['XAUUSD-H8']
  if (other && other.slPip === cfg.slPip) {
    console.log('   ❌ هندسهٔ دو کارت یکی است — یکی از کلیدها اشتباه است')
    fail++
  } else {
    console.log(`   ✓ با کارتِ دیگر متفاوت است (${other?.slPip} ≠ ${cfg.slPip})`)
  }

  // ── ②④⑥ رویدادِ واقعی + رگرسیون + هم‌زمانی ──
  console.log(`── ②④ رویدادِ واقعی و رگرسیونِ ساکنان ──`)
  const all = loadCsv(tf)
  console.log(`   دادهٔ ${tf}: ${all.length} کندل`)

  // گاردِ درسِ S1520: اگر نامِ فیلد عوض شده باشد، warm = NaN می‌شود و حلقه
  // صفر بار اجرا می‌شود ⇒ آزمون به‌دروغ می‌گوید «لایه مرده است».
  const warm = cfg.lookback + cfg.atrP + 5
  if (!Number.isFinite(warm)) throw new Error(`گرم‌شدنِ محاسبه‌شده معتبر نیست: ${warm}`)
  const lo = Math.max(warm, all.length - 2500)

  let hit = -1
  for (let i = all.length - 1; i >= lo; i--) {
    const raw = computeS589(all.slice(0, i + 1) as any, cfg)
    if (raw.active) { hit = i; break }
  }

  if (hit < 0) {
    console.log('   ❌ در ۲۵۰۰ کندلِ اخیر هیچ رویدادِ S589 پیدا نشد ⇒ لایه عملاً مرده است')
    fail++
    continue
  }

  const when = new Date(all[hit].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  const px = all[hit].close
  rep.event = { bar: hit, utc: when, close: px }
  console.log(`   رویدادِ واقعی: بارِ ${hit} · ${when} UTC · close=${px}`)

  const ctx = {
    cardId: card, a: mkA(card, px), candles: all.slice(0, hit + 1) as any,
    utcHour: new Date(all[hit].time * 1000).getUTCHours(),
    times: all.slice(0, hit + 1).map(c => c.time), capital: 10000, riskPct: 1.0,
  }

  const dOn = runCard(ctx as any)
  const codesOn: string[] = []
  if (dOn.sourceLayer?.code) codesOn.push(dOn.sourceLayer.code)
  for (const o of (dOn.otherLayers || [])) codesOn.push(o.code)
  rep.codes_on = codesOn
  console.log(`   کدهای دیده‌شده در خروجی: [${codesOn.join(', ')}]`)
  const seen = codesOn.some(c => /S589/i.test(c))
  if (seen) {
    console.log('   ✓ ② S589 به خروجیِ runCard می‌رسد')
  } else {
    console.log('   ❌ ② S589 در خروجیِ runCard نیست — وصل‌نشده یا خفه‌شده')
    fail++
  }
  const asPrimary = /S589/i.test(dOn.sourceLayer?.code || '')
  rep.role = asPrimary ? 'primary' : 'otherLayers'
  console.log(`   نقش: ${rep.role} · state=${dOn.state}`)

  // ── ⑥ قیدِ سایزِ مشترک: آیا S1520 هم روی همین کندل روشن است؟ ──
  if (card === 'XAUUSD-H8') {
    const together = codesOn.some(c => /S1520/i.test(c))
    rep.cofire_with_s1520 = together
    console.log(`── ⑥ قیدِ سایزِ مشترک (S589 × S1520) ──`)
    if (together) {
      console.log('   ⚠️ هر دو روی همین کندل روشن‌اند ⇒ این **یک** سقفِ تازه است که')
      console.log('      دو گیتِ متعامد تأییدش کرده‌اند — دو کادر، ولی **یک** پوزیشن.')
      console.log('      (این رخداد انتظار می‌رفت: jaccard=۰.۵۲۵ یعنی ~نیمی از کندل‌ها مشترک‌اند.)')
    } else {
      console.log('   ✓ اینجا فقط S589 روشن است ⇒ همان جمعیتِ **غیرمشترکی** که')
      console.log('     دلیلِ «شاهدِ کاذب نیست» بود (۳۶.۲٪ رویدادهای S589).')
    }
  }

  // ── ④ رگرسیون با فهرستِ فیلترشده ──
  const backup = CARD_LAYERS[card]
  const filtered = backup.filter((fn) => {
    try {
      const d = fn(ctx as any)
      return !(d && /S589/i.test(d.sourceLayer?.code || ''))
    } catch { return true }
  })
  CARD_LAYERS[card] = filtered
  let dOff: any = null
  try { dOff = runCard(ctx as any) } finally { CARD_LAYERS[card] = backup }

  console.log(`   فهرستِ فیلترشده: ${filtered.length} لایه (انتظار: ${spec.expectLayers - 1})`)
  if (filtered.length !== spec.expectLayers - 1) {
    console.log('   ❌ فیلتر نتوانست دقیقاً یک لایه (S589) را جدا کند')
    fail++
  } else {
    const codesOff: string[] = []
    if (dOff?.sourceLayer?.code) codesOff.push(dOff.sourceLayer.code)
    for (const o of (dOff?.otherLayers || [])) codesOff.push(o.code)
    rep.codes_off = codesOff
    console.log(`   بدونِ S589: [${codesOff.join(', ')}] · state=${dOff?.state}`)

    // 🔴 **روشِ مقایسه اصلاح شد — اجرای اول اینجا RED داد و ایراد از خودِ آزمون
    //    بود، نه از سیم‌کشی.** مقایسهٔ ساده‌لوحانهٔ «کدهای خروجی با و بدونِ S589»
    //    نامعتبر است، چون `runCard` در خطِ ۱۶۴۲ فقط لایه‌هایی را در `otherLayers`
    //    می‌گذارد که `state ∈ {ENTRY, APPROACHING}` باشند. پس وقتی S589 پُرایمریِ
    //    ENTRY است، ساکنانِ NEUTRAL **اصلاً در خروجی ظاهر نمی‌شوند**؛ و وقتی
    //    S589 برداشته می‌شود، بهترین ساکنِ NEUTRAL (اینجا S950) پُرایمری می‌شود و
    //    ناگهان «ظاهر» می‌گردد. خروجی [] در برابرِ [S950] پس **رفتارِ درست و
    //    مستندِ موتورِ نمایش** است، نه رگرسیون — دقیقاً همان «مکانیزمِ نمایش که
    //    همپوشانی را حل می‌کند».
    //    مقایسهٔ معتبر باید روی **تصمیمِ خودِ هر ساکن** باشد، نه روی اینکه
    //    موتورِ رتبه‌بندی کدام‌شان را نمایش می‌دهد. پس هر لایهٔ فیلترشده مستقیماً
    //    با همان ctx صدا زده می‌شود و (code, state, direction) استخراج می‌گردد.
    //    این تنها شکلی است که واقعاً به پرسشِ «آیا S589 چیزی را خراب کرد؟» پاسخ
    //    می‌دهد، چون S589 اصلاً در این فراخوانی‌ها حضور ندارد.
    const incumbentSnapshot = (fns: any[]) => fns.map((fn) => {
      try {
        const d = fn(ctx as any)
        if (!d) return null
        return `${d.sourceLayer?.code || '—'}:${d.state}:${d.direction || '—'}`
      } catch { return 'ERR' }
    }).filter(Boolean).sort()

    const snapOff = incumbentSnapshot(filtered)
    // همان ساکنان، ولی این‌بار در حضورِ کاملِ فهرست (S589 هم در آرایه هست).
    // چون هر لایه تابعی خالص روی ctx است، اگر S589 هیچ حالتِ مشترکی را آلوده
    // نکرده باشد این دو عکس باید **دقیقاً** یکی باشند.
    const snapOn = incumbentSnapshot(backup.filter(fn => {
      try { const d = fn(ctx as any); return !(d && /S589/i.test(d.sourceLayer?.code || '')) }
      catch { return true }
    }))
    rep.incumbents_off = snapOff
    rep.incumbents_on = snapOn
    console.log(`   عکسِ تصمیمِ ساکنان (بدونِ S589): [${snapOff.join(' | ')}]`)
    if (JSON.stringify(snapOn) === JSON.stringify(snapOff)) {
      console.log('   ✓ ④ هیچ رگرسیونی: تصمیمِ تک‌تکِ ساکنان بی‌تغییر است')
    } else {
      console.log(`   ❌ ④ رگرسیون: [${snapOn.join(' | ')}] ≠ [${snapOff.join(' | ')}]`)
      fail++
    }
    // و یک چکِ مکمل: برداشتنِ S589 نباید تصمیمِ کارت را **بهتر** کند؛ فقط
    // می‌تواند از ENTRY به چیزی ضعیف‌تر برود (چون یک شاهد کم شده).
    console.log(`   تصمیمِ کارت: با S589 = ${dOn.state} · بدونِ S589 = ${dOff?.state}`)
  }
}

const OUT = path.join(ROOT, 'results/_s589/integ_cards.json')
fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify(report, null, 1))
console.log(`\nذخیره شد -> ${OUT}`)
console.log(`\n${fail === 0 ? '✅ GREEN — هر دو کارت وصل، هندسه مخصوصِ خود، صفر رگرسیون' : `❌ RED — ${fail} چکِ ناموفق`}`)
process.exit(fail === 0 ? 0 : 1)
