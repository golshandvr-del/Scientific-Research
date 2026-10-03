// ---------------------------------------------------------------------------
// آزمونِ برابریِ S1581 — پورتِ TS در برابرِ مرجعِ **پایتون** روی XAUUSD-H6.
//
// مرجع: results/_s1581_parity/XAUUSD_H6.json (ساختهٔ tools/export_s1581_parity.py
//   که خودش ماشینِ منجمدِ حکمِ ACCEPT 88.0 را بازتولید می‌کند؛ گاردِ سلامت:
//   ۳۲۶ سیگنال / ۲۱۹ معامله / WR 52.97 / sl_abs 15.20958).
//
// چه چیزی سنجیده می‌شود:
//   ① مجموعهٔ **کاملِ** رویدادها روی کلِ ۱۵.۶ سال — بیت‌به‌بیت، نه نمونه‌ای.
//      شمارشِ برابر کافی نیست: پورت می‌تواند ۳۲۶ رویداد بدهد ولی بعضی را یک
//      کندل جابه‌جا بگذارد. پس **زمانِ** هر رویداد مقایسه می‌شود.
//   ② سری‌های تفکیکیِ دنبالهٔ ۴۰۰ کندلِ آخر: سدِ کف، ff، لبهٔ تازه، گیتِ درفت،
//      RVOL. اگر مجموعه‌ها فرق کنند، این می‌گوید **کدام جزءِ قاعده** مقصر است.
//   ③ هندسهٔ منجمد: S1581_CFG باید عیناً SL/TP مرجع را داشته باشد **و** فاصلهٔ
//      دلاری باید sl_abs_price مرجع باشد (دامِ pip ۰.۱ در برابرِ ۰.۰۱).
//   ④ maxHold باید از بیشینهٔ نگه‌داریِ واقعی بزرگ‌تر باشد، وگرنه سایت معامله‌ای
//      را می‌بُرد که موتور شمرده بود.
//   ⑤ شاهدِ منفیِ H8/H4: POWER-LIMITED بودند ⇒ S1581_CFG **نباید** آن‌ها را
//      داشته باشد (ضدِ تعمیمِ ممنوعِ MTF — سکوت را از حکم تفکیک می‌کند).
//   ⑥ کنترلِ منفیِ گیتِ حجم: با برداشتنِ گیت باید سیگنال‌ها **بیشتر** شوند.
//      اگر عددی عوض نشود یعنی گیت در پورت بی‌اثر است (همیشه-true).
//
// 🔴 تلهٔ اصلی: سری‌ها باید روی **کلِ تاریخ** محاسبه و بعد روی دنباله مقایسه
//    شوند. سدِ کف یک بیشینهٔ غلتانِ ۹۰-کندلی است و گیتِ درفت به close[i−90] و
//    RVOL به ۲۰ رخدادِ قبلیِ همان ساعت نگاه می‌کند؛ بریدنِ داده از ابتدا هر سه
//    را عوض می‌کند و آزمون دروغ می‌شود.
//
// اجرا: npx tsx tools/_parity_s1581.mts
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import { S1581_CFG, s1581Features } from '../src/volume_fresh_floor_s1581.js'
import type { Candle } from '../src/indicators.js'

const ROOT = new URL('../../', import.meta.url).pathname
const TOL_PRICE = 1e-4
const TOL_RVOL = 1e-4
const GOLD_PIP = 0.1

type Tail = {
  from_index: number
  prior_min_low: (number | null)[]
  ff: number[]
  fresh: number[]
  drift: number[]
  rvol: (number | null)[]
  sig: number[]
}
type Ref = {
  card: string
  bars: number
  frozen: {
    lookback: number; rvol_thr: number; slot_win: number; slot_minp: number
    atr_p: number; sl_k: number; rr: number
    sl_pip: number; tp_pip: number; sl_abs_price: number; pip_size: number
    entry: string; side: string
  }
  counts: { n_base_events: number; n_signals: number; n_trades: number; wr: number; pass_rate: number }
  hold_bars: { min: number; median: number; p95: number; max: number }
  signal_bars: number[]
  tail: Tail
  health_ok: boolean
}

function readRef(): Ref {
  const p = `${ROOT}results/_s1581_parity/XAUUSD_H6.json`
  if (!fs.existsSync(p)) {
    throw new Error(`مرجع نیست: ${p} — اول tools/export_s1581_parity.py را اجرا کن`)
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'))
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

function loadToday(): Candle[] {
  const p = `${ROOT}data/mt5_full/XAUUSD_H6.csv.gz`
  return parseCsv(zlib.gunzipSync(fs.readFileSync(p)).toString('utf8'))
}

let failures = 0
const checks: { ok: boolean; label: string; detail: string }[] = []
function check(ok: boolean, label: string, detail = ''): void {
  checks.push({ ok, label, detail })
  if (ok) console.log(`  ✅ ${label}`)
  else { failures++; console.log(`  ❌ ${label}${detail ? ` — ${detail}` : ''}`) }
}

function main(): void {
  console.log('آزمونِ برابریِ S1581 — پورتِ TS در برابرِ مرجعِ پایتون (XAUUSD-H6)')
  const ref = readRef()
  const cfg = S1581_CFG['XAUUSD-H6']
  check(ref.health_ok, 'مرجع خودش گاردِ سلامتِ حکم را پاس کرده است')
  if (!cfg) { check(false, 'کارتِ H6 در S1581_CFG هست', 'وجود ندارد'); process.exit(1) }

  const candles = loadToday()
  check(candles.length === ref.bars, 'تعدادِ کندل با مرجع یکی است',
        `TS=${candles.length} ref=${ref.bars}`)

  const F = ref.frozen
  check(cfg.lookback === F.lookback, `lookback = ${F.lookback}`, `cfg=${cfg.lookback}`)
  check(cfg.rvolThr === F.rvol_thr, `rvolThr = ${F.rvol_thr}`, `cfg=${cfg.rvolThr}`)
  check(cfg.slotWin === F.slot_win && cfg.slotMinP === F.slot_minp,
        `اسلاتِ حجم = ${F.slot_win}/min${F.slot_minp}`, `cfg=${cfg.slotWin}/min${cfg.slotMinP}`)

  const f = s1581Features(candles, cfg)

  // ── ① مجموعهٔ کاملِ رویدادها ──────────────────────────────────────────────
  const tsEvents: number[] = []
  for (let i = 0; i < candles.length; i++) if (f.sig[i]) tsEvents.push(candles[i].time)
  const refSet = new Set(ref.signal_bars.map(b => candles[b].time))
  const tsSet = new Set(tsEvents)
  check(tsEvents.length === ref.counts.n_signals,
        `تعدادِ سیگنال = ${ref.counts.n_signals}`, `TS=${tsEvents.length}`)
  const onlyTs = tsEvents.filter(t => !refSet.has(t))
  const onlyRef = [...refSet].filter(t => !tsSet.has(t))
  check(onlyTs.length === 0 && onlyRef.length === 0,
        'مجموعهٔ سیگنال‌ها بیت‌به‌بیت برابرِ مرجع است',
        `فقط در TS=${onlyTs.length} · فقط در مرجع=${onlyRef.length}`)

  // ── ② سری‌های تفکیکیِ دنباله ─────────────────────────────────────────────
  const t = ref.tail
  const off = t.from_index
  let dBar = 0, dFf = 0, dFresh = 0, dDrift = 0, dRvol = 0, dSig = 0
  for (let k = 0; k < t.sig.length; k++) {
    const i = off + k
    const rb = t.prior_min_low[k]
    const tb = f.priorMinLow[i]
    const bOk = rb === null ? !isFinite(tb) : (isFinite(tb) && Math.abs(tb - rb) < TOL_PRICE)
    if (!bOk) dBar++
    if ((f.ff[i] ? 1 : 0) !== t.ff[k]) dFf++
    if ((f.fresh[i] ? 1 : 0) !== t.fresh[k]) dFresh++
    if ((f.drift[i] ? 1 : 0) !== t.drift[k]) dDrift++
    const rr = t.rvol[k]
    const tr = f.rvol[i]
    const rOk = rr === null ? !isFinite(tr) : (isFinite(tr) && Math.abs(tr - rr) < TOL_RVOL)
    if (!rOk) dRvol++
    if ((f.sig[i] ? 1 : 0) !== t.sig[k]) dSig++
  }
  check(dBar === 0, 'سدِ کف (بیشینهٔ غلتانِ low) روی دنباله برابر است', `${dBar} اختلاف`)
  check(dFf === 0, 'حالتِ ff روی دنباله برابر است', `${dFf} اختلاف`)
  check(dFresh === 0, 'لبهٔ تازه روی دنباله برابر است', `${dFresh} اختلاف`)
  check(dDrift === 0, 'گیتِ درفتِ علّی روی دنباله برابر است', `${dDrift} اختلاف`)
  check(dRvol === 0, 'RVOL هم‌اسلات روی دنباله برابر است', `${dRvol} اختلاف`)
  check(dSig === 0, 'سیگنالِ نهایی روی دنباله برابر است', `${dSig} اختلاف`)

  // ── ③ هندسهٔ منجمد (شاملِ دامِ pip) ──────────────────────────────────────
  check(Math.abs(cfg.slPip - F.sl_pip) < 0.01, `SL = ${F.sl_pip} pip`, `cfg=${cfg.slPip}`)
  check(Math.abs(cfg.tpPip - F.tp_pip) < 0.01, `TP = ${F.tp_pip} pip`, `cfg=${cfg.tpPip}`)
  check(F.pip_size === GOLD_PIP, `مرجع pip=۰.۱ (قراردادِ طلا)`, `ref=${F.pip_size}`)
  // دامِ کلیدی: فاصلهٔ دلاریِ پورت باید ۱۵.۲۱$ باشد نه ۱.۵۲$ (باگِ pip=0.01).
  const slDistTs = cfg.slPip * GOLD_PIP
  check(Math.abs(slDistTs - F.sl_abs_price) < 0.01,
        `فاصلهٔ دلاریِ SL = ${F.sl_abs_price}$ (نه ۱۰× کوچک‌تر)`,
        `TS=${slDistTs.toFixed(5)}$`)
  check(F.entry === 'close_of_signal_bar', 'مرجع: ورود روی close کندلِ سیگنال است')

  // ── ④ maxHold ────────────────────────────────────────────────────────────
  check(cfg.maxHold > ref.hold_bars.max,
        `maxHold (${cfg.maxHold}) از بیشینهٔ نگه‌داریِ واقعی (${ref.hold_bars.max}) بزرگ‌تر است`,
        'سقفِ سایت معامله‌ای را می‌بُرد که موتور شمرده بود')

  // ── ⑥ کنترلِ منفیِ گیتِ حجم ──────────────────────────────────────────────
  let nBase = 0
  for (let i = 0; i < candles.length; i++) if (f.base[i]) nBase++
  check(nBase > tsEvents.length,
        `کنترلِ منفی: بدونِ گیتِ حجم سیگنال‌ها بیشتر می‌شوند (${nBase} > ${tsEvents.length})`,
        'گیت در پورت بی‌اثر است ⇒ سبزیِ بقیهٔ آزمون‌ها بی‌معنا بود')
  check(nBase === ref.counts.n_base_events,
        `تعدادِ رویدادِ پایه (بدونِ حجم) = ${ref.counts.n_base_events}`, `TS=${nBase}`)

  // ── ⑤ شاهدِ منفیِ H8/H4 (POWER-LIMITED) ──────────────────────────────────
  console.log('\n═══ شاهدِ منفی: H8 و H4 ═══')
  check(S1581_CFG['XAUUSD-H8'] === undefined,
        'کارتِ H8 عامدانه در S1581_CFG نیست (POWER-LIMITED 26.2)',
        'وجود دارد ⇒ تعمیمِ ممنوعِ MTF')
  check(S1581_CFG['XAUUSD-H4'] === undefined,
        'کارتِ H4 عامدانه در S1581_CFG نیست (POWER-LIMITED 28.7)',
        'وجود دارد ⇒ تعمیمِ ممنوعِ MTF')
  const ids = Object.keys(S1581_CFG).sort()
  check(ids.length === 1 && ids[0] === 'XAUUSD-H6',
        'دقیقاً یک کارتِ ACCEPT پیکربندی شده است (H6)', ids.join(', '))

  const res = {
    layer: 'S1581', card: 'XAUUSD-H6',
    status: failures === 0 ? 'GREEN' : 'RED',
    fails: failures, total: checks.length,
    checks,
  }
  const outPath = `${ROOT}results/_s1581_parity/parity_result.json`
  fs.mkdirSync(`${ROOT}results/_s1581_parity`, { recursive: true })
  fs.writeFileSync(outPath, JSON.stringify(res, null, 1))
  console.log(`\nذخیره شد -> ${outPath}`)
  console.log(failures === 0
    ? `\n✅ همهٔ آزمون‌ها سبز (${checks.length - failures}/${checks.length}) — پورت با مرجع برابر است`
    : `\n❌ ${failures} آزمون شکست خورد`)
  if (failures) process.exit(1)
}

main()
