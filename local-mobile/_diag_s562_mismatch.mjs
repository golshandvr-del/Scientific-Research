// ============================================================================
// _diag_s562_mismatch.mjs — تشخیصِ **علّتِ** اختلافِ parity در S562
//
// چرا این فایل لازم است
// =====================
// اجرای اولِ parity برای M15 داد: only_ts=0 · only_py=5 · mismatch=5.
// نگاهِ اول به تاریخ‌ها (۲۰۱۳-۰۶ و ۲۰۱۱-۰۳) داستانِ راحتی پیشنهاد می‌کند:
// «گاردِ سلامتِ فید مسدود کرده». اما پذیرفتنِ آن داستان **بدونِ اندازه‌گیری**
// همان خطایی است که یک باگِ واقعیِ پورت را زیرِ توضیحی خوش‌ظاهر پنهان می‌کند.
//
// پس این اسکریپت برای هر زمانِ اختلافی، **همهٔ** اجزای تصمیم را جدا-جدا
// گزارش می‌کند تا معلوم شود کدام جزء «نه» گفته است:
//     dataHealthy · baseActive · volPass · volRef/volThr · gap/thr
//
// معیارِ قبولیِ این تشخیص: هر ۵ اختلاف باید **فقط** با dataHealthy=false
// توضیح داده شوند. اگر حتی یکی از آن‌ها dataHealthy=true داشته باشد و به‌دلیلِ
// دیگری رد شده باشد، پورت باگ دارد و حقِ اتصال ندارد.
// ============================================================================
import { readFileSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'
const TF = process.argv.find(a => a.startsWith('--tf='))?.slice(5) ?? 'M15'
const WIN_DAYS = 40

const { build } = await import(
  pathToFileURL(`${ROOT}/web_tool/node_modules/esbuild/lib/main.js`).href)

const outfile = `/tmp/_s562_diag_${TF}.mjs`
await build({
  entryPoints: [`${ROOT}/web_tool/src/gap_open_volfilter_s562.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error',
})
const { computeS562Signal, S562_CFG } = await import(pathToFileURL(outfile).href)
const cfg = S562_CFG[`XAUUSD-${TF}`]

const lines = readFileSync(`${ROOT}/data/mt5_full/XAUUSD_${TF}.csv`, 'utf8').trim().split('\n')
const header = lines[0].split(',')
const iT = header.indexOf('time'), iO = header.indexOf('open')
const iH = header.indexOf('high'), iL = header.indexOf('low'), iC = header.indexOf('close')
const candles = new Array(lines.length - 1)
for (let k = 1; k < lines.length; k++) {
  const p = lines[k].split(',')
  const ts = p[iT]
  candles[k - 1] = {
    time: /^\d+$/.test(ts) ? parseInt(ts, 10)
      : Math.floor(new Date(ts.replace(' ', 'T') + 'Z').getTime() / 1000),
    open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC],
  }
}
const byTime = new Map()
for (let i = 0; i < candles.length; i++) byTime.set(candles[i].time, i)

const parity = JSON.parse(readFileSync(`${ROOT}/results/_s562_arms/parity_ts_${TF}.json`, 'utf8'))
const ref = JSON.parse(readFileSync(`${ROOT}/results/_s562_arms/signal_bars_${TF}.json`, 'utf8'))

// بازسازیِ فهرستِ کاملِ اختلاف‌ها (نه فقط ۱۲ نمونهٔ ذخیره‌شده)
const brkThr = Math.max(1800, 1.5 * cfg.tfSec)
const breaks = []
for (let i = 0; i < candles.length - 1; i++) {
  if (candles[i + 1].time - candles[i].time > brkThr) breaks.push(i)
}
// 🔴 اصلاحِ BUG-HARNESSWINDOW (همان اصلاحِ مرحلهٔ ۲۰ در _parity_s562.mjs):
//    پنجره با **شمارشِ مرزهای روز** گرفته می‌شود، نه «۴۰ × کندل‌در‌روزِ نظری».
//    وگرنه در فیدِ کم‌تراکمِ ۲۰۱۱ پنجره <۱۴ روزِ کامل می‌شد و ماژول درست ولی
//    بی‌ربط رد می‌کرد. هر دو هارنس باید **یک** تعریفِ پنجره داشته باشند، وگرنه
//    تشخیص و parity دو واقعیتِ متفاوت را گزارش می‌کنند.
const brkIdxOf = new Map()
breaks.forEach((b, i) => brkIdxOf.set(b, i))
const winFrom = (brk) => {
  const bi = brkIdxOf.get(brk)
  if (bi === undefined) return Math.max(0, brk + 1 - WIN_DAYS * Math.ceil(86400 / cfg.tfSec))
  return bi - WIN_DAYS >= 0 ? breaks[bi - WIN_DAYS] + 1 : 0
}
const tsSet = new Set()
for (const brk of breaks) {
  if (brk + 1 >= candles.length) continue
  const from = winFrom(brk)
  const slice = candles.slice(from, brk + 2)
  if (slice.length < 3) continue
  if (computeS562Signal(slice, cfg).active) tsSet.add(candles[brk].time)
}
const refFrozen = new Set(ref.signal_times_frozen)
const onlyPy = [...refFrozen].filter(t => !tsSet.has(t))
const onlyTs = [...tsSet].filter(t => !refFrozen.has(t))

const iso = t => new Date(t * 1000).toISOString().replace('.000Z', 'Z')
const rows = []
for (const t of onlyPy) {
  const brk = byTime.get(t)
  if (brk === undefined) { rows.push({ time: iso(t), error: 'کندل یافت نشد' }); continue }
  const from = Math.max(0, brk + 1 - winBars)
  const slice = candles.slice(from, brk + 2)
  const s = computeS562Signal(slice, cfg)
  // فاصلهٔ زمانیِ سمتِ گذشتهٔ مرز — همان چیزی که گارد می‌سنجد
  const prevDt = candles[brk].time - candles[brk - 1].time
  rows.push({
    time: iso(t),
    dataHealthy: s.dataHealthy,
    prev_bar_gap_sec: prevDt,
    brk_thr_sec: brkThr,
    guard_blocked: prevDt > brkThr,
    baseActive: s.baseActive,
    gapUsd: +s.gapUsd.toFixed(3),
    thrUsd: s.thrUsd,
    isWeekend: s.isWeekend,
    volPass: s.volPass,
    volRefUsd: isFinite(s.volRefUsd) ? +s.volRefUsd.toFixed(2) : null,
    volThrUsd: s.volThrUsd,
    volDaysAvail: s.volDaysAvail,
    active: s.active,
  })
}

const guardOnly = rows.filter(r => r.guard_blocked === true && r.active === false)
const unexplained = rows.filter(r => r.guard_blocked !== true)

const out = {
  tf: TF,
  n_only_py: onlyPy.length,
  n_only_ts: onlyTs.length,
  n_explained_by_data_health_guard: guardOnly.length,
  n_unexplained: unexplained.length,
  verdict: (unexplained.length === 0 && onlyTs.length === 0)
    ? 'ALL_MISMATCHES_EXPLAINED_BY_FEED_GUARD'
    : 'UNEXPLAINED_MISMATCH_PRESENT',
  rows,
  unexplained,
}
const dest = `${ROOT}/results/_s562_arms/diag_mismatch_${TF}.json`
writeFileSync(dest, JSON.stringify(out, null, 1))
console.log(JSON.stringify(out, null, 1))
console.log(`\n→ ${dest}`)
if (out.verdict !== 'ALL_MISMATCHES_EXPLAINED_BY_FEED_GUARD') process.exitCode = 1
