// ---------------------------------------------------------------------------
// اندازه‌گیریِ هم‌پوشانیِ S607/H8-DUAL با **چهار لایهٔ ساکنِ** کارتِ XAUUSD-H8
// (S950 · S965 · S966 · S770) — **پیش از** سیم‌کشی، نه بعد.
//
// چرا این آزمون لازم است؟
//   سندِ رسمیِ S607 هم‌پوشانی با لایه‌های H8 را **اندازه‌گیری نکرده** (استخرش
//   {D1,H8,H6} بود و فقط درون-استخری را سنجید). ولی کارتِ H8 در این سایت
//   شلوغ‌ترین کارتِ پروژه است: چهار لایه که همه‌شان «شوک/انبساط»ی‌اند و سندِ
//   S966 نشان داد S966 ⊂ S965 با هم‌کندلِ ۱۰۰٪. پس اگر S607 هم زیرمجموعهٔ
//   یکی از این‌ها باشد، افزودنش «پوششِ نو» نیست بلکه **سایزِ چندبرابر** روی یک
//   رویدادِ واحد است — همان اشتباهی که روشِ پروژه (METHOD_ENSEMBLE_UNION §هم‌پوشانی)
//   صریحاً ممنوع می‌کند.
//
// روش (عینِ الگوی results/_scan_S966/overlap_s950_s965_s966_h8.json):
//   · همان دادهٔ بک‌تست: data/mt5_full/XAUUSD_H8.csv (کندلِ H8ِ MT5)
//   · پنجرهٔ ۳۰۰۰ کندلِ آخر — همان پنجره‌ای که سندِ S966 استفاده کرد ⇒ اعداد
//     مستقیماً با آن سند قابلِ مقایسه‌اند.
//   · هر لایه با **منطقِ مستقرِ خودش** (همان computeXxx که سایت صدا می‌زند)
//     به‌صورتِ غلتان اجرا می‌شود: برای هر i، فقط کندل‌های [0..i] داده می‌شود
//     ⇒ صفر نگاهِ آینده، عینِ رفتارِ زندهٔ سایت.
//   · «هم‌کندل» = هر دو لایه روی همان اندیسِ i سیگنالِ ENTRY بدهند.
//
// خروجی: results/_s607_overlap/h8.json  (سندِ ماشین‌خوان برای نشست‌های بعد)
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import { computeS607, S607_CFG } from '../src/engle_dual_gate_s607'
import { computeS950, S950_CFG } from '../src/jump_aftermath_s950'
import { computeS965, S965_CFG } from '../src/kyle_intrabar_s965'
import { computeS966, S966_CFG } from '../src/kyle_permanence_drift_s966'
import { computeS770, S770_CFG } from '../src/adr_expansion_s770'

type Candle = { time: number; open: number; high: number; low: number; close: number }

const ROOT = path.resolve(import.meta.dirname, '../..')
const CSV = path.join(ROOT, 'data/mt5_full/XAUUSD_H8.csv')
const WINDOW = 3000

function loadCsv(p: string): Candle[] {
  const txt = fs.readFileSync(p, 'utf8').trim().split('\n')
  const out: Candle[] = []
  for (let i = 1; i < txt.length; i++) {
    const s = txt[i].split(',')
    out.push({
      time: Number(s[0]), open: Number(s[1]), high: Number(s[2]),
      low: Number(s[3]), close: Number(s[4]),
    })
  }
  return out
}

const all = loadCsv(CSV)
console.log(`دادهٔ H8: ${all.length} کندل · پنجرهٔ اندازه‌گیری: ${WINDOW} کندلِ آخر`)

// ---------------------------------------------------------------------------
// اجرای غلتانِ هر لایه. ⚠️ نکتهٔ کلیدی: هر لایه به **تاریخِ کاملِ قبلِ خود**
// نیاز دارد (z و σ بازگشتی‌اند، ATR وایلدر هم). پس برشِ [0..i] می‌دهیم، نه
// پنجرهٔ کوتاه — وگرنه اعداد با سایتِ زنده یکی نمی‌شد.
// ---------------------------------------------------------------------------
type Hit = { i: number; dir: string }

function rollLayer(
  name: string,
  fn: (c: Candle[]) => { active: boolean; direction: string },
): Hit[] {
  const hits: Hit[] = []
  const start = all.length - WINDOW
  for (let i = start; i < all.length; i++) {
    const slice = all.slice(0, i + 1)
    let r
    try { r = fn(slice) } catch { continue }
    if (r.active) hits.push({ i, dir: r.direction })
  }
  const nl = hits.filter((h) => h.dir === 'LONG').length
  console.log(`  ${name}: n=${hits.length} (long=${nl} short=${hits.length - nl})`)
  return hits
}

console.log('\n── اجرای غلتانِ پنج لایه روی کارتِ H8 ──')
const s607 = rollLayer('S607', (c) => computeS607(c as any, S607_CFG['XAUUSD-H8']))
const s950 = rollLayer('S950', (c) => computeS950(c as any, S950_CFG['XAUUSD-H8']))
const s965 = rollLayer('S965', (c) => computeS965(c as any, S965_CFG['XAUUSD-H8']))
const s966 = rollLayer('S966', (c) => computeS966(c as any, S966_CFG['XAUUSD-H8']))
const s770 = rollLayer('S770', (c) => computeS770(c as any, S770_CFG['XAUUSD-H8']))

// ---------------------------------------------------------------------------
function pairStats(a: Hit[], b: Hit[], aName: string, bName: string) {
  const mb = new Map(b.map((h) => [h.i, h.dir]))
  let same = 0, opposite = 0
  for (const h of a) {
    const d = mb.get(h.i)
    if (d === undefined) continue
    same++
    if (d !== h.dir) opposite++
  }
  const pctA = a.length ? +(100 * same / a.length).toFixed(1) : 0
  const pctB = b.length ? +(100 * same / b.length).toFixed(1) : 0
  const jac = (a.length + b.length - same) > 0
    ? +(same / (a.length + b.length - same)).toFixed(4) : 0
  console.log(
    `  ${aName} ↔ ${bName}: هم‌کندل=${same} ` +
    `(${pctA}٪ از ${aName} · ${pctB}٪ از ${bName}) · ` +
    `جهتِ مخالف=${opposite} · ژاکارد=${jac}`,
  )
  return {
    same_bar_overlap_n: same, pct_of_a: pctA, pct_of_b: pctB,
    opposite_direction: opposite, jaccard: jac,
    a_only_n: a.length - same, b_only_n: b.length - same,
  }
}

console.log('\n── هم‌پوشانیِ S607 با هر لایهٔ ساکن ──')
const vs950 = pairStats(s607, s950, 'S607', 'S950')
const vs965 = pairStats(s607, s965, 'S607', 'S965')
const vs966 = pairStats(s607, s966, 'S607', 'S966')
const vs770 = pairStats(s607, s770, 'S607', 'S770')

// اتحادِ چهار لایهٔ ساکن: چند سیگنالِ S607 **هیچ** هم‌تایی ندارد؟
const incumbentBars = new Set<number>([...s950, ...s965, ...s966, ...s770].map((h) => h.i))
const novel = s607.filter((h) => !incumbentBars.has(h.i))
const pctNovel = s607.length ? +(100 * novel.length / s607.length).toFixed(1) : 0
console.log(
  `\n  S607 در برابرِ **اتحادِ** چهار لایهٔ ساکن: ` +
  `${novel.length} از ${s607.length} سیگنال (${pctNovel}٪) **هیچ هم‌کندلی ندارد** ⇒ پوششِ نو.`,
)

// ---------------------------------------------------------------------------
// حکمِ ماشینی — قاعدهٔ پروژه: اگر S607 زیرمجموعهٔ ساختاریِ ۱۰۰٪ِ یکی از
// ساکنان بود، «پوششِ نو» صفر است و اتصال باید بازنگری شود.
// ---------------------------------------------------------------------------
const subsetOf: string[] = []
for (const [nm, st] of [['S950', vs950], ['S965', vs965], ['S966', vs966], ['S770', vs770]] as const) {
  if (st.pct_of_a >= 100) subsetOf.push(nm)
}
const verdict = subsetOf.length > 0
  ? `⚠️ S607 زیرمجموعهٔ ۱۰۰٪ِ ${subsetOf.join('/')} است ⇒ پوششِ نو ندارد.`
  : `✅ S607 زیرمجموعهٔ هیچ لایهٔ ساکنی نیست؛ ${pctNovel}٪ سیگنال‌هایش کاملاً نو است.`
console.log(`\n${verdict}`)

const out = {
  what: 'همپوشانیِ S607/H8-DUAL با چهار لایهٔ ساکنِ کارتِ XAUUSD-H8 (S950·S965·S966·S770)',
  why:
    'سندِ رسمیِ S607 فقط درون-استخری {D1,H8,H6} را سنجید و هم‌پوشانی با لایه‌های ' +
    'مستقرِ کارتِ H8 را اندازه نگرفت. کارتِ H8 شلوغ‌ترین کارتِ سایت است و سندِ S966 ' +
    'نشان داد S966 ⊂ S965 با هم‌کندلِ ۱۰۰٪ ⇒ پس باید **پیش از** سیم‌کشی سنجیده شود ' +
    'که S607 پوششِ نو می‌آورد یا فقط سایزِ چندبرابر روی یک رویدادِ واحد.',
  window: {
    bars: WINDOW, tf: 'H8', aligned: true,
    source: 'اجرای غلتانِ منطقِ مستقرِ هر پنج لایه روی data/mt5_full/XAUUSD_H8.csv',
    note:
      'برای هر اندیسِ i فقط کندل‌های [0..i] به لایه داده شد ⇒ صفر نگاهِ آینده، ' +
      'عینِ رفتارِ زندهٔ سایت. برشِ تاریخِ کامل لازم است چون z/σ/ATR بازگشتی‌اند.',
  },
  counts: {
    s607: { n: s607.length, long: s607.filter((h) => h.dir === 'LONG').length },
    s950: { n: s950.length }, s965: { n: s965.length },
    s966: { n: s966.length }, s770: { n: s770.length },
  },
  s607_vs_s950: vs950, s607_vs_s965: vs965,
  s607_vs_s966: vs966, s607_vs_s770: vs770,
  s607_vs_union: {
    incumbent_union_bars: incumbentBars.size,
    s607_novel_n: novel.length, s607_novel_pct: pctNovel,
  },
  verdict,
}
const outDir = path.join(ROOT, 'results/_s607_overlap')
fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, 'h8.json'), JSON.stringify(out, null, 1))
console.log(`\n[saved] results/_s607_overlap/h8.json`)
