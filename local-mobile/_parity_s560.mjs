// ---------------------------------------------------------------------------
// parity S560 — computeS560Signal (TS/esbuild) vs مرجعِ پایتون (adjudicate.build)
//
// چه چیزی را ثابت می‌کند؟
//   پورتِ TypeScript **همان مجموعهٔ مرزهای روز، همان گپ‌ها، همان برچسبِ آخرهفته**
//   و — با آستانهٔ منجمد — **همان مجموعهٔ سیگنال** را روی دادهٔ ۱۵.۶ سالهٔ mt5_full
//   تولید می‌کند که مرجعِ پایتون تولید کرد.
//
// روشِ شبیه‌سازیِ زنده (مهم):
//   computeS560Signal فقط «آخرین مرزِ روزِ آرایه» را ارزیابی می‌کند (چون هندسه
//   ۱-کندلی است). پس برای هر مرزِ روزِ تاریخی i، پنجره‌ای می‌سازیم که **به کندلِ
//   i+1 ختم شود** (یعنی: تا همان لحظه‌ای که معامله‌گرِ زنده open روزِ نو را دیده و
//   هیچ کندلِ آینده‌ای در دست ندارد). سپس active باید با cond پایتون یکی باشد.
//   این دقیقاً سناریوی زندهٔ سایت است ⇒ هر مچ‌نشدنی، باگِ واقعیِ زنده است.
//
// خروجی: صفر اختلاف در مرزها/گپ‌ها/آخرهفته/سیگنال ⇒ PARITY OK.
// ---------------------------------------------------------------------------
import { readFileSync, writeFileSync } from 'node:fs'
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'

// ۱) کامپایلِ ماژولِ S560 به باندلِ موقتِ ESM
const outfile = '/tmp/_s560_layer.mjs'
await build({
  entryPoints: [`${ROOT}/web_tool/src/gap_open_s560.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile,
  logLevel: 'error',
})
const { computeS560Signal, S560_CFG, dayBreakThreshold } = await import(pathToFileURL(outfile).href)
const cfg = S560_CFG['XAUUSD-M5']
// تعدادِ **دقیقِ** سیگنال‌هایی که گاردِ سلامتِ فید مجاز است مسدود کند.
// اندازه‌گیریِ مستقل روی کلِ ۱۵.۶ سال: ۳ مورد از ۴۲۳ (۰.۷۱٪)، هر سه در ناحیهٔ
// معیوبِ ژوئنِ ۲۰۱۳ (گپ‌های جعلیِ ۸.۷۰$ / ۸.۹۵$ / ۲۷.۳۴$). این عدد **سقفِ
// اعلام‌شده** است، نه پارامترِ قابلِ تنظیم: اگر جابه‌جا شد یعنی رفتارِ گارد
// تغییر کرده و باید دوباره داوری شود.
const EXPECT_GUARD_BLOCKS = 3
console.log('cfg:', JSON.stringify(cfg))
console.log('dayBreakThreshold(300) =', dayBreakThreshold(300), '(باید 1800 باشد)')

// ۲) بارگذاریِ همان دادهٔ پایتون: data/mt5_full/XAUUSD_M5.csv
const path = `${ROOT}/data/mt5_full/XAUUSD_M5.csv`
const raw = readFileSync(path, 'utf8').trim().split('\n')
const header = raw[0].split(',')
const iT = header.indexOf('time'), iO = header.indexOf('open'), iH = header.indexOf('high'),
      iL = header.indexOf('low'), iC = header.indexOf('close')
const candles = new Array(raw.length - 1)
for (let k = 1; k < raw.length; k++) {
  const p = raw[k].split(',')
  candles[k - 1] = {
    time: parseInt(p[iT], 10),
    open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC], volume: 0,
  }
}
const n = candles.length
console.log('candles:', n, '| first:', candles[0].time, '| last:', candles[n - 1].time)

// ۳) مرجعِ مستقلِ JS از قاعدهٔ پایتون (بازنویسیِ صریحِ day_breaks + cond)
//    این «مرجعِ دوم» است: اگر ماژول و این مرجع یکی باشند، پورت درست است.
const BRK_THR = Math.max(1800, 1.5 * 300)
const refBrk = []
for (let i = 0; i < n - 1; i++) {
  if (candles[i + 1].time - candles[i].time > BRK_THR) refBrk.push(i)
}
console.log('reference day_breaks:', refBrk.length, '(پایتون: 4069)')

// ۴) گپ/آخرهفته/سیگنالِ مرجع با آستانهٔ منجمد
const refSignals = []
for (const i of refBrk) {
  const gap = candles[i + 1].open - candles[i].close
  const wknd = (candles[i + 1].time - candles[i].time) > 86400
  const thr = wknd ? cfg.thrWeekendUsd : cfg.thrWeekdayUsd
  if (gap < 0 && Math.abs(gap) > thr) refSignals.push(i)
}
console.log('reference signals (frozen thr):', refSignals.length, '(انتظار: 412)')

// ۵) شبیه‌سازیِ زنده روی هر مرزِ روز: پنجره‌ای که به i+1 ختم می‌شود
const WARM = 400              // پنجرهٔ کافی؛ لایه warm-up ندارد ولی مرزِ روز لازم است
let checked = 0, mismatchSig = 0, mismatchGap = 0, mismatchWknd = 0, mismatchIdx = 0
// انحرافِ **عمدیِ اعلام‌شده**: سیگنالی که مرجع داشت و گاردِ سلامتِ فید مسدودش کرد.
// جدا از mismatchSig شمرده می‌شود تا در حکم با «اختلافِ واقعی» قاطی نشود.
let guardBlocked = 0
const guardCases = []
const badCases = []
const refSigSet = new Set(refSignals)

for (const i of refBrk) {
  if (i + 1 >= n) continue
  const lo = Math.max(0, i - WARM)
  const win = candles.slice(lo, i + 2)     // پنجره: ... , candles[i], candles[i+1]
  const s = computeS560Signal(win, cfg)
  checked++

  // ۵-الف) ماژول باید همان مرزِ روز را «آخرین مرز» ببیند
  const expectBrkIdx = i - lo
  if (s.brkIdx !== expectBrkIdx) {
    mismatchIdx++
    if (badCases.length < 8) badCases.push({ kind: 'brkIdx', i, got: s.brkIdx, want: expectBrkIdx })
    continue
  }

  // ۵-ب) گپ و برچسبِ آخرهفته
  const gapRef = candles[i + 1].open - candles[i].close
  const wkndRef = (candles[i + 1].time - candles[i].time) > 86400
  if (Math.abs(s.gapUsd - gapRef) > 1e-9) {
    mismatchGap++
    if (badCases.length < 8) badCases.push({ kind: 'gap', i, got: s.gapUsd, want: gapRef })
  }
  if (s.isWeekend !== wkndRef) {
    mismatchWknd++
    if (badCases.length < 8) badCases.push({ kind: 'weekend', i, got: s.isWeekend, want: wkndRef })
  }

  // ۵-ج) سیگنال
  //
  // ⚠️ انحرافِ **عمدی و اعلام‌شده** از مرجعِ پایتون (افزودهٔ همین نشست):
  //    لایه یک «گاردِ سلامتِ فید» دارد که وقتی کندلِ ماقبلِ مرزِ روز هم با
  //    وقفه‌ای بزرگ‌تر از حدِ مجاز آمده باشد، سیگنال را مسدود می‌کند — چون در
  //    آن حالت «بستهٔ روزِ قبل» قیمتی کهنه است و گپ مصنوعِ شکافِ داده.
  //    مرجعِ پایتون این گارد را ندارد، پس اختلاف **انتظار می‌رود**.
  //
  //    این آزمون ضعیف نمی‌شود: اختلاف فقط زمانی پذیرفته است که علتش
  //    **دقیقاً** ناسالم‌بودنِ داده باشد (s.dataHealthy === false) و جهتش
  //    فقط «مسدودسازی» باشد (مرجع سیگنال داشته، ما نداریم). هر اختلافِ
  //    دیگری — از جمله سیگنالی که ما بدهیم و مرجع نداده باشد — شکستِ واقعی است.
  const wantSig = refSigSet.has(i)
  if (s.active !== wantSig) {
    const intentional = wantSig && !s.active && s.dataHealthy === false
    if (intentional) {
      guardBlocked++
      if (guardCases.length < 8) guardCases.push({
        kind: 'guard-block', i,
        utc: new Date(candles[i + 1].time * 1000).toISOString(),
        gap: +gapRef.toFixed(3), thr: s.thrUsd,
        prevBarDt: candles[i].time - candles[i - 1].time,
      })
    } else {
      mismatchSig++
      if (badCases.length < 8) badCases.push({ kind: 'signal', i, got: s.active, want: wantSig, gap: gapRef, thr: s.thrUsd })
    }
  }
}

console.log('---')
console.log('checked day-breaks   :', checked)
console.log('mismatch brkIdx      :', mismatchIdx)
console.log('mismatch gap         :', mismatchGap)
console.log('mismatch weekend     :', mismatchWknd)
console.log('mismatch signal      :', mismatchSig, '(اختلافِ واقعی — باید ۰ باشد)')
console.log('guard blocked        :', guardBlocked, `(انحرافِ عمدیِ گاردِ سلامتِ فید — انتظار: ${EXPECT_GUARD_BLOCKS})`)
if (badCases.length) console.log('sample bad cases:', JSON.stringify(badCases, null, 1))
if (guardCases.length) console.log('guard-blocked cases:', JSON.stringify(guardCases, null, 1))

// حکم: منطقِ پایه باید بیت‌به‌بیت یکی باشد، و انحرافِ عمدی باید **دقیقاً** به
// اندازهٔ اعلام‌شده باشد. اگر روزی گاردْ بی‌رویه شد (مثلاً به‌خاطرِ تغییرِ brkThr
// شروع کرد سیگنال‌های سالم را هم بخورد)، همین شرط فوراً لو می‌دهد.
const baseOk  = mismatchIdx === 0 && mismatchGap === 0 && mismatchWknd === 0 && mismatchSig === 0
const guardOk = guardBlocked === EXPECT_GUARD_BLOCKS
const ok = baseOk && guardOk
console.log(ok
  ? '✅ PARITY OK — منطقِ پایه با مرجع یکی است و گارد دقیقاً در محدودهٔ اعلام‌شده عمل کرد'
  : `❌ PARITY FAILED — baseOk=${baseOk} guardOk=${guardOk}`)

const report = {
  layer: 'S560', card: 'XAUUSD-M5', src: path,
  n_candles: n, day_breaks: refBrk.length,
  ref_signals_frozen: refSignals.length,
  checked, mismatchIdx, mismatchGap, mismatchWknd, mismatchSig,
  base_logic_ok: baseOk,
  data_health_guard: {
    blocked: guardBlocked, expected: EXPECT_GUARD_BLOCKS, ok: guardOk,
    cases: guardCases,
    rationale: 'declared intentional deviation from the python reference: the live layer blocks signals whose day-break sits in a discontinuous feed region (previous-day close is stale => the gap is a data artefact). Accepted ONLY when the reference had the signal, we blocked it, and dataHealthy===false.',
    footprint: '3 of 423 signals = 0.71% over the full 15.6y, all inside the June-2013 defective region (fake gaps 8.70-27.34$) => statistical verdict untouched',
  },
  parity_ok: ok, ts: new Date().toISOString(),
}
writeFileSync(`${ROOT}/results/_s560_arms/parity_ts_M5.json`, JSON.stringify(report, null, 1))
console.log('→ results/_s560_arms/parity_ts_M5.json')
if (!ok) process.exit(1)
