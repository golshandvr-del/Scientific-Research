// ============================================================================
// journal/signal_journal.ts — دفترِ تاریخچهٔ سیگنال‌ها + حلِ نتیجه (User Note)
// ----------------------------------------------------------------------------
// مسئله (اندازه‌گیری‌شده، نه حدس — results/_signal_drought/replay.json):
//   لایه‌ها **سیگنال می‌دهند** (H4: ۴۶ رویداد در ۱۴۱ روز، H8: ۸۱ در ۲۵۱ روز، D1: ۶۹
//   در ۳۴۸ روز)، ولی تقریباً هر رویدادِ HTF فقط **یک کندل** زنده است و در ساعتِ
//   خاصی ظاهر می‌شود (D1 همیشه ۰۳:۳۰ تهران). سایت فقط «حالِ حاضر» را نشان می‌دهد ⇒
//   اگر کاربر همان لحظه صفحه را باز نکرده باشد، سیگنال **بی‌ردپا** گم می‌شود.
//
// راه‌حل: هر ENTRY روی سرور (نه مرورگر) با جزئیاتِ کامل ثبت و سپس با کندل‌های
//   بستهٔ بعدی **حل** می‌شود (TP / SL / انقضای hold). این هم تاریخچه می‌دهد و هم
//   «آمارِ زنده»ٔ مستقل از بک‌تست — همان چیزی که برای سنجشِ واقعیِ RQS2 لازم است.
//
// ⚠️ شاهدِ کاذب: لایه‌ای که رجیستری به‌عنوانِ «شاهدِ کاذب» حذف کرده (falseWitness)
//   هرگز رکوردِ جدا نمی‌گیرد؛ فقط در یادداشتِ رکوردِ برنده می‌آید. لایه‌ای که «بدیلِ
//   بین‌کارتی» است (sameEventFamily.isPrimary=false) ثبت می‌شود ولی `independent=false`
//   می‌گیرد تا آمارِ «شاهدِ مستقل» دوبار شمرده نشود.
//
// ماندگاری: روی Node/Termux ⇒ فایلِ JSON (پیش‌فرض ./data/journal/signals.json)؛ روی
//   Cloudflare ⇒ فقط حافظه (fs ندارد). importِ fs پویاست ⇒ باندلِ Cloudflare سالم.
// ============================================================================

export type JournalStatus = 'OPEN' | 'TP' | 'SL' | 'EXPIRED'

export interface JournalRecord {
  seq: number                 // شمارهٔ یکتا و صعودی (برای «از این به بعد» در نوتیف)
  id: string                  // card|layer|dir|barTime
  createdAt: number           // ms — لحظهٔ ثبت روی سرور
  card: string                // کلیدِ رجیستری (XAUUSD-M15 …)
  asset: string               // شناسهٔ کارت در UI (XAUUSD …)
  tf: string                  // M5 / M15 / … / D1
  gapSec: number              // طولِ کندلِ کارت (ثانیه)
  layer: string               // کدِ لایه (S770 …)
  layerName: string
  direction: 'LONG' | 'SHORT'
  barTime: number             // زمانِ کندلِ بسته‌ای که سیگنال روی آن نشست (s)
  priceAtSignal: number       // قیمتِ زندهٔ لحظهٔ ثبت
  entry: number
  tp: number
  sl: number
  rr?: number
  probability?: number
  maxHoldBars?: number
  independent: boolean        // false ⇒ بدیلِ بین‌کارتی (همان رویداد، کارتِ دیگر مرجع است)
  primaryCard?: string
  notes: string[]             // شاهدِ کاذبِ حذف‌شده، هم‌رویدادی و …
  role: 'primary' | 'other'   // لایهٔ اصلیِ کارت یا لایهٔ هم‌زمانِ دیگر
  // --- نتیجه ---
  status: JournalStatus
  resolvedAt?: number         // زمانِ کندلی که نتیجه را تعیین کرد (s)
  exitPrice?: number
  pips?: number               // سود/زیان بر حسبِ pip (طلا: ۱pip = ۰.۱$)
  rMultiple?: number          // سود/زیان بر حسبِ R (فاصلهٔ SL)
  barsHeld?: number
  mfePips?: number            // بیشینهٔ حرکتِ موافق
  maePips?: number            // بیشینهٔ حرکتِ مخالف
}

const PIP = 0.1                 // GOLD_PIP — همان قراردادِ revived_strategies.ts
const MAX_RECORDS = 3000
const HARD_MAX_HOLD = 500       // اگر لایه hold اعلام نکرده، سقفِ ایمنی (کندل)

let records: JournalRecord[] = []
let seqCounter = 0
let loaded: Promise<void> | null = null
let saveTimer: any = null
let fsApi: { file: string; fsp: any } | null = null

function isNode(): boolean {
  return typeof process !== 'undefined' && !!(process as any).versions?.node
}

async function ensureLoaded(): Promise<void> {
  if (loaded) return loaded
  loaded = (async () => {
    if (!isNode()) return
    try {
      const fsp: any = await import('node:fs/promises')
      const pathMod: any = await import('node:path')
      const dir = ((process as any).env?.JOURNAL_DIR) || './data/journal'
      await fsp.mkdir(dir, { recursive: true })
      const file = pathMod.join(dir, 'signals.json')
      fsApi = { file, fsp }
      try {
        const raw = JSON.parse(await fsp.readFile(file, 'utf8'))
        if (Array.isArray(raw?.records)) {
          records = raw.records
          seqCounter = records.reduce((m, r) => Math.max(m, r.seq || 0), 0)
        }
      } catch { /* فایلِ اول — خالی */ }
    } catch { fsApi = null /* fail-safe ⇒ حافظه */ }
  })()
  return loaded
}

function scheduleSave(): void {
  if (!fsApi || saveTimer) return
  saveTimer = setTimeout(async () => {
    saveTimer = null
    if (!fsApi) return
    try {
      const tmp = fsApi.file + '.tmp'
      await fsApi.fsp.writeFile(tmp, JSON.stringify({ version: 1, records }), 'utf8')
      await fsApi.fsp.rename(tmp, fsApi.file)   // نوشتنِ اتمی (قطعِ برق ⇒ فایلِ سالم)
    } catch { /* ثبت نباید مسیرِ تصمیم را بشکند */ }
  }, 300)
}

interface Bar { time: number; open: number; high: number; low: number; close: number }

/** حلِ نتیجهٔ یک رکوردِ باز با کندل‌های بستهٔ پس از سیگنال. محافظه‌کار: TP و SL
 *  در یک کندل ⇒ SL (ترتیبِ درون‌کندلی نامعلوم است؛ خوش‌بینی آمار را باد می‌کند). */
export function resolveRecord(r: JournalRecord, bars: Bar[]): boolean {
  if (r.status !== 'OPEN') return false
  const after = bars.filter(b => b.time > r.barTime)
  if (!after.length) return false
  const long = r.direction === 'LONG'
  const risk = Math.abs(r.entry - r.sl) || 1e-9
  const hold = r.maxHoldBars && r.maxHoldBars > 0 ? r.maxHoldBars : HARD_MAX_HOLD
  let mfe = r.mfePips || 0, mae = r.maePips || 0
  for (let i = 0; i < after.length; i++) {
    const b = after[i]
    const fav = long ? b.high - r.entry : r.entry - b.low
    const adv = long ? r.entry - b.low : b.high - r.entry
    mfe = Math.max(mfe, fav / PIP); mae = Math.max(mae, adv / PIP)
    const hitSl = long ? b.low <= r.sl : b.high >= r.sl
    const hitTp = long ? b.high >= r.tp : b.low <= r.tp
    let exit: number | null = null, st: JournalStatus | null = null
    if (hitSl) { exit = r.sl; st = 'SL' }
    else if (hitTp) { exit = r.tp; st = 'TP' }
    else if (i + 1 >= hold) { exit = b.close; st = 'EXPIRED' }
    if (st && exit != null) {
      const move = long ? exit - r.entry : r.entry - exit
      r.status = st; r.resolvedAt = b.time; r.exitPrice = exit; r.barsHeld = i + 1
      r.pips = +(move / PIP).toFixed(1); r.rMultiple = +(move / risk).toFixed(2)
      r.mfePips = +mfe.toFixed(1); r.maePips = +mae.toFixed(1)
      return true
    }
  }
  r.mfePips = +mfe.toFixed(1); r.maePips = +mae.toFixed(1); r.barsHeld = after.length
  return false
}

function mkRecord(card: string, asset: string, tf: string, gapSec: number, d: any, role: 'primary' | 'other',
  price: number, barTime: number, extraNotes: string[]): JournalRecord | null {
  const dir = d?.direction
  if (dir !== 'LONG' && dir !== 'SHORT') return null
  const entry = Number(d.entry), tp = Number(d.tp), sl = Number(d.sl)
  if (!isFinite(entry) || !isFinite(tp) || !isFinite(sl)) return null
  const code = (d.sourceLayer?.code || d.code || '—').trim()
  const fam = d.sameEventFamily
  const notes = [...extraNotes]
  if (fam && !fam.isPrimary) notes.push(`بدیلِ بین‌کارتی: همان رویدادِ ${fam.code} روی ${fam.primaryCard} (شاهدِ مستقل نیست)`)
  return {
    seq: 0, id: `${card}|${code}|${dir}|${barTime}`, createdAt: Date.now(),
    card, asset, tf, gapSec, layer: code, layerName: d.sourceLayer?.name || d.name || d.headline || code,
    direction: dir, barTime, priceAtSignal: price, entry, tp, sl,
    rr: d.rr, probability: d.probability,
    maxHoldBars: d.slPlan?.maxHoldBars ?? d.maxHoldBars,
    independent: !(fam && fam.isPrimary === false), primaryCard: fam?.primaryCard,
    notes, role, status: 'OPEN',
  }
}

/**
 * مشاهدهٔ یک تصمیمِ کارت: (۱) رکوردهای بازِ این کارت را با کندل‌های بسته حل کن،
 * (۲) هر ENTRYِ تازه (primary + otherLayers) را ثبت کن. یک «اپیزود» = یک رکورد:
 * تا وقتی رکوردِ بازِ همان کارت/لایه/جهت هست، ENTRYِ تکراریِ کندل‌های بعدی ثبت نمی‌شود
 * (عینِ یک پوزیشن — همان FIFOِ بک‌تست).
 */
export async function observeDecision(args: {
  card: string; asset: string; tf: string; gapSec: number
  dec: any; price: number; bars: Bar[]
}): Promise<JournalRecord[]> {
  await ensureLoaded()
  const { card, asset, tf, gapSec, dec, price, bars } = args
  let changed = false
  for (const r of records) if (r.card === card && r.status === 'OPEN' && resolveRecord(r, bars)) changed = true
  const added: JournalRecord[] = []
  const lastBar = bars.length ? bars[bars.length - 1].time : 0
  const fwNotes: string[] = (dec?.falseWitness || []).map((f: any) =>
    `شاهدِ کاذبِ حذف‌شده: ${f.code} (همان رویداد با ${f.inFavorOf}، jaccard ${f.jaccard})`)
  const cands: Array<{ d: any; role: 'primary' | 'other' }> = []
  if (dec?.state === 'ENTRY') cands.push({ d: dec, role: 'primary' })
  for (const o of dec?.otherLayers || []) if (o.state === 'ENTRY') cands.push({ d: o, role: 'other' })
  for (const { d, role } of cands) {
    const rec = mkRecord(card, asset, tf, gapSec, d, role, price, lastBar, role === 'primary' ? fwNotes : [])
    if (!rec) continue
    const dup = records.some(r => r.id === rec.id ||
      (r.card === card && r.layer === rec.layer && r.direction === rec.direction &&
        (r.status === 'OPEN' || (r.resolvedAt != null && r.resolvedAt >= rec.barTime))))
    if (dup) continue
    rec.seq = ++seqCounter
    records.push(rec); added.push(rec); changed = true
  }
  if (records.length > MAX_RECORDS) records = records.slice(-MAX_RECORDS)
  if (changed) scheduleSave()
  return added
}

export async function getJournal(opts: { sinceSeq?: number; card?: string; limit?: number } = {}): Promise<JournalRecord[]> {
  await ensureLoaded()
  let rows = records
  if (opts.sinceSeq) rows = rows.filter(r => r.seq > opts.sinceSeq!)
  if (opts.card) rows = rows.filter(r => r.card === opts.card || r.asset === opts.card)
  return rows.slice(-(opts.limit || MAX_RECORDS))
}

/** آمارِ زندهٔ هر لایه×کارت — فقط رکوردهای «مستقل» و حل‌شده در WR/PF شمرده می‌شوند. */
export async function journalStats() {
  await ensureLoaded()
  const by: Record<string, any> = {}
  for (const r of records) {
    const k = `${r.card}|${r.layer}`
    const s = (by[k] ||= { card: r.card, tf: r.tf, layer: r.layer, signals: 0, open: 0, tp: 0, sl: 0, expired: 0, alternates: 0, sumPips: 0, sumR: 0, grossWin: 0, grossLoss: 0 })
    s.signals++
    if (!r.independent) { s.alternates++; continue }
    if (r.status === 'OPEN') { s.open++; continue }
    if (r.status === 'TP') s.tp++; else if (r.status === 'SL') s.sl++; else s.expired++
    s.sumPips += r.pips || 0; s.sumR += r.rMultiple || 0
    if ((r.pips || 0) > 0) s.grossWin += r.pips!; else s.grossLoss += -(r.pips || 0)
  }
  const rows = Object.values(by).map((s: any) => {
    const closed = s.tp + s.sl + s.expired
    const wins = (records.filter(r => r.card === s.card && r.layer === s.layer && r.independent && r.status !== 'OPEN' && (r.pips || 0) > 0)).length
    // PF بی‌زیان = بی‌نهایت ⇒ null (نمایش «—»)؛ با n کوچک هیچ عددی قابلِ اتکا نیست.
    return { ...s, closed, wins, winRate: closed ? +(wins / closed * 100).toFixed(1) : null,
      pf: s.grossLoss > 0 ? +(s.grossWin / s.grossLoss).toFixed(2) : null,
      avgR: closed ? +(s.sumR / closed).toFixed(2) : null, sumPips: +s.sumPips.toFixed(1) }
  })
  return { total: records.length, persisted: !!fsApi, file: fsApi?.file || null, rows }
}

export async function clearJournal(): Promise<void> {
  await ensureLoaded(); records = []; scheduleSave()
}

/** برای تست: ری‌ستِ کاملِ وضعیتِ ماژول (بدونِ دیسک). */
export function _resetForTest(): void { records = []; seqCounter = 0; loaded = Promise.resolve(); fsApi = null }
