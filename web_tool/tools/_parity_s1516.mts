// ---------------------------------------------------------------------------
// آزمونِ برابریِ S1516 — پورتِ TS در برابرِ مرجعِ **پایتون** روی دادهٔ کاملِ MT5.
//
// مرجع: results/_s1516_parity/<CARD>.json (ساختهٔ tools/export_s1516_parity.py
//   که خودش ماشینِ منجمدِ حکمِ ACCEPT 87.1/84.1 را بازتولید می‌کند؛ کنترلش هر
//   پنج سنجهٔ منتشرشده را عیناً درآورد).
//
// چه چیزی سنجیده می‌شود:
//   ① مجموعهٔ **کاملِ** رویدادها روی کلِ ۱۵.۶ سال — بیت‌به‌بیت، نه نمونه‌ای.
//      شمارشِ برابر کافی نیست: پورت می‌تواند ۵۱۸ رویداد بدهد ولی بعضی را یک
//      کندل جابه‌جا بگذارد. پس **زمانِ** هر رویداد مقایسه می‌شود.
//   ② سری‌های تفکیکیِ دنبالهٔ ۴۰۰ کندلِ آخر: سدِ کف، ff، لبهٔ تازه، گیتِ درفت.
//      اگر مجموعه‌ها فرق کنند، این می‌گوید **کدام جزءِ قاعده** مقصر است.
//   ③ هندسهٔ منجمدِ هر کارت: S1516_CFG باید عیناً SL/TP مرجعِ **امروز** را
//      داشته باشد (نه عددِ سند — چون دادهٔ H4 پس از حکم عوض شد).
//   ④ maxHold باید از بیشینهٔ نگه‌داریِ واقعیِ همان کارت **بزرگ‌تر** باشد،
//      وگرنه سایت معامله‌ای را می‌بُرد که موتور شمرده بود.
//   ⑤ **شاهدِ منفیِ H3**: این کارت REJECT 16.5 گرفت ⇒ S1516_CFG **نباید**
//      آن را داشته باشد. ضدِ تعمیمِ ممنوعِ MTF — سکوت را از حکم تفکیک می‌کند.
//   ⑥ **کنترلِ منفیِ گیتِ درفت**: اگر گیت برداشته شود باید رویدادها **بیشتر**
//      شوند. اگر عددی عوض نشود یعنی گیت در پورت بی‌اثر است (همیشه-true) و
//      سبزیِ بقیهٔ آزمون‌ها بی‌معنا می‌شد.
//
// 🔴 تلهٔ اصلیِ این آزمون: سری‌ها باید روی **کلِ تاریخ** محاسبه و بعد روی دنباله
//    مقایسه شوند. سدِ کف یک بیشینهٔ غلتانِ L-کندلی است و گیتِ درفت به close[i−L]
//    نگاه می‌کند؛ بریدنِ داده از ابتدا هر دو را عوض می‌کند و آزمون دروغ می‌شود.
//
// ⚠️ کارتِ H4 دو نسخه دارد: «today» (فایلِ امروز، ۲۴٬۰۰۴ کندل — آنچه سایت
//    می‌بیند) و «verdict» (فایلِ پیش از کامیت 922b56ac، ۲۳٬۸۵۴ کندل — آنچه حکم
//    رویش صادر شد). پورت با **today** سنجیده می‌شود چون سایت با فیدِ امروز کار
//    می‌کند؛ نسخهٔ verdict فقط اعتبارِ خودِ مرجع را تضمین کرده است.
//
// اجرا: npx tsx tools/_parity_s1516.mts             (هر دو کارت + شاهدِ منفی)
//       npx tsx tools/_parity_s1516.mts XAUUSD_H6   (یک کارت)
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import { execFileSync } from 'node:child_process'
import { S1516_CFG, s1516Features, type S1516Config } from '../src/cal_fresh_floor_s1516.js'
import type { Candle } from '../src/indicators.js'

const ROOT = new URL('../../', import.meta.url).pathname
const TOL_PRICE = 1e-4
const DATA_SWAP_COMMIT = '922b56ac'

type Tail = {
  from_index: number
  time: number[]
  low: number[]
  barrier: (number | null)[]
  ff: boolean[]
  fresh: boolean[]
  drift: boolean[]
  sig: boolean[]
}
type Snap = {
  tag: string
  bars: number
  span_years: number
  L: number
  n_signals: number
  n_trades: number
  sl_pip: number
  tp_pip: number
  entry_price_field: string
  hold_bars?: { min: number; median: number; p95: number; max: number }
  all_event_times: number[]
  tail: Tail
}
type Ref = {
  published: Record<string, number>
  verdict_time_data: Snap
  today_data: Snap
  control_passed: boolean
}

function readRef(card: string): Ref {
  const p = `${ROOT}results/_s1516_parity/${card}.json`
  if (!fs.existsSync(p)) {
    throw new Error(`مرجع نیست: ${p} — اول tools/export_s1516_parity.py را اجرا کن`)
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'))
}

/** فایلِ امروز از mt5_full. */
function loadToday(card: string): Candle[] {
  const p = `${ROOT}data/mt5_full/${card}.csv.gz`
  const txt = zlib.gunzipSync(fs.readFileSync(p)).toString('utf8')
  return parseCsv(txt)
}

/** فایلِ زمانِ حکم، مستقیم از گیت (برای H4 که پس از حکم عوض شد). */
function loadVerdict(card: string): Candle[] {
  const blob = execFileSync(
    'git', ['show', `${DATA_SWAP_COMMIT}~1:data/mt5_full/${card}.csv.gz`],
    { cwd: ROOT, maxBuffer: 1 << 28, encoding: 'buffer' },
  )
  return parseCsv(zlib.gunzipSync(blob).toString('utf8'))
}

function parseCsv(txt: string): Candle[] {
  const lines = txt.trim().split('\n')
  const head = lines[0].split(',').map(s => s.trim())
  const ix = (k: string) => head.indexOf(k)
  const [it, io, ih, il, ic] = [ix('time'), ix('open'), ix('high'), ix('low'), ix('close')]
  const iv = ix('volume') >= 0 ? ix('volume') : ix('tick_volume')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const p = lines[i].split(',')
    if (p.length < 5) continue
    out.push({
      time: Number(p[it]), open: Number(p[io]), high: Number(p[ih]),
      low: Number(p[il]), close: Number(p[ic]),
      volume: iv >= 0 ? Number(p[iv]) : 0,
    } as Candle)
  }
  return out
}

let failures = 0
function check(ok: boolean, label: string, detail = ''): void {
  if (ok) {
    console.log(`  ✅ ${label}`)
  } else {
    failures++
    console.log(`  ❌ ${label}${detail ? ` — ${detail}` : ''}`)
  }
}

function runCard(card: string): void {
  const id = card.replace('_', '-')
  const cfg = S1516_CFG[id]
  const ref = readRef(card)

  console.log(`\n═══ ${card} ═══`)
  if (!cfg) {
    check(false, 'کارت در S1516_CFG هست', 'وجود ندارد')
    return
  }
  check(ref.control_passed, 'مرجع خودش کنترلِ حکم را پاس کرده است')

  // پورت با دادهٔ **امروز** سنجیده می‌شود (همان که سایت می‌بیند).
  const snap = ref.today_data
  const candles = card === 'XAUUSD_H4' ? loadToday(card) : loadToday(card)
  check(candles.length === snap.bars, 'تعدادِ کندل با مرجع یکی است',
        `TS=${candles.length} ref=${snap.bars}`)

  check(cfg.lookback === snap.L, `L کارت = ${snap.L}`, `cfg=${cfg.lookback}`)

  const f = s1516Features(candles, cfg)

  // ── ① مجموعهٔ کاملِ رویدادها ──────────────────────────────────────────────
  const tsEvents: number[] = []
  for (let i = 0; i < candles.length; i++) if (f.sig[i]) tsEvents.push(candles[i].time)
  const refEvents = snap.all_event_times
  check(tsEvents.length === refEvents.length, `تعدادِ رویداد = ${refEvents.length}`,
        `TS=${tsEvents.length}`)

  const refSet = new Set(refEvents)
  const tsSet = new Set(tsEvents)
  const onlyTs = tsEvents.filter(t => !refSet.has(t))
  const onlyRef = refEvents.filter(t => !tsSet.has(t))
  check(onlyTs.length === 0 && onlyRef.length === 0,
        'مجموعهٔ رویدادها بیت‌به‌بیت برابرِ مرجع است',
        `فقط در TS=${onlyTs.length} (${onlyTs.slice(0, 3).map(t => new Date(t * 1000).toISOString()).join(', ')}) · ` +
        `فقط در مرجع=${onlyRef.length} (${onlyRef.slice(0, 3).map(t => new Date(t * 1000).toISOString()).join(', ')})`)

  // ── ② سری‌های تفکیکیِ دنباله ─────────────────────────────────────────────
  const t = snap.tail
  const off = t.from_index
  let dBar = 0, dFf = 0, dFresh = 0, dDrift = 0, dSig = 0
  for (let k = 0; k < t.time.length; k++) {
    const i = off + k
    if (candles[i].time !== t.time[k]) { dBar++; continue }
    const rb = t.barrier[k]
    const tb = f.priorMinLow[i]
    const bOk = rb === null ? !isFinite(tb) : (isFinite(tb) && Math.abs(tb - rb) < TOL_PRICE)
    if (!bOk) dBar++
    if (f.ff[i] !== t.ff[k]) dFf++
    if (f.fresh[i] !== t.fresh[k]) dFresh++
    if (f.drift[i] !== t.drift[k]) dDrift++
    if (f.sig[i] !== t.sig[k]) dSig++
  }
  check(dBar === 0, 'سدِ کف (بیشینهٔ غلتانِ low) روی دنباله برابر است', `${dBar} اختلاف`)
  check(dFf === 0, 'حالتِ ff روی دنباله برابر است', `${dFf} اختلاف`)
  check(dFresh === 0, 'لبهٔ تازه روی دنباله برابر است', `${dFresh} اختلاف`)
  check(dDrift === 0, 'گیتِ درفتِ علّی روی دنباله برابر است', `${dDrift} اختلاف`)
  check(dSig === 0, 'سیگنالِ نهایی روی دنباله برابر است', `${dSig} اختلاف`)

  // ── ③ هندسهٔ منجمد ───────────────────────────────────────────────────────
  check(Math.abs(cfg.slPip - snap.sl_pip) < 0.01,
        `SL کارت = ${snap.sl_pip} pip (دادهٔ امروز)`, `cfg=${cfg.slPip}`)
  check(Math.abs(cfg.tpPip - snap.tp_pip) < 0.01,
        `TP کارت = ${snap.tp_pip} pip`, `cfg=${cfg.tpPip}`)
  check(snap.entry_price_field === 'close[signal_bar]',
        'مرجع تأیید می‌کند ورود روی close کندلِ سیگنال است (نه openِ بعدی)')

  // ── ④ maxHold نباید معاملهٔ داوری‌شده را ببُرد ────────────────────────────
  const maxHold = snap.hold_bars?.max ?? 0
  check(cfg.maxHold > maxHold,
        `maxHold (${cfg.maxHold}) از بیشینهٔ نگه‌داریِ واقعی (${maxHold}) بزرگ‌تر است`,
        'سقفِ سایت معامله‌ای را می‌بُرد که موتور شمرده بود')

  // ── ⑥ کنترلِ منفیِ گیتِ درفت ─────────────────────────────────────────────
  // گیت را برمی‌داریم: رویدادها باید **بیشتر** شوند. اگر نشوند، گیت بی‌اثر است.
  let nNoGate = 0
  for (let i = 0; i < candles.length; i++) if (f.fresh[i]) nNoGate++
  check(nNoGate > tsEvents.length,
        `کنترلِ منفی: بدونِ گیتِ درفت رویدادها بیشتر می‌شوند (${nNoGate} > ${tsEvents.length})`,
        'گیت در پورت بی‌اثر است ⇒ سبزیِ بقیهٔ آزمون‌ها بی‌معنا بود')
}

function main(): void {
  const args = process.argv.slice(2)
  const cards = args.length ? args : ['XAUUSD_H6', 'XAUUSD_H4']
  console.log('آزمونِ برابریِ S1516 — پورتِ TS در برابرِ مرجعِ پایتون')
  for (const c of cards) runCard(c)

  // ── ⑤ شاهدِ منفیِ H3 (REJECT 16.5) ───────────────────────────────────────
  if (!args.length) {
    console.log('\n═══ شاهدِ منفی: XAUUSD-H3 ═══')
    check(S1516_CFG['XAUUSD-H3'] === undefined,
          'کارتِ H3 عامدانه در S1516_CFG نیست (REJECT 16.5 — دیوارِ اسپرد)',
          'وجود دارد ⇒ تعمیمِ ممنوعِ MTF')
    const ids = Object.keys(S1516_CFG).sort()
    check(ids.length === 2 && ids[0] === 'XAUUSD-H4' && ids[1] === 'XAUUSD-H6',
          'دقیقاً دو کارتِ ACCEPT پیکربندی شده‌اند (H4 و H6)', ids.join(', '))
  }

  console.log(failures === 0
    ? '\n✅ همهٔ آزمون‌ها سبز — پورت با مرجع برابر است'
    : `\n❌ ${failures} آزمون شکست خورد`)
  if (failures) process.exit(1)
}

main()
