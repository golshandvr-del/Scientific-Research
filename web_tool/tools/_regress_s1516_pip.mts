// ---------------------------------------------------------------------------
// رگرسیونِ باگِ pip در S1516 — **قبل از اصلاح باید قرمز باشد**.
//
// باگ: cal_fresh_floor_s1516.ts مقدارِ `pipSize = 0.01` داشت، در حالی که قراردادِ
// پروژه برای طلا **GOLD_PIP = 0.1** است (revived_strategies.ts:42 ·
// adr_expansion_s770.ts:60). نتیجه: فاصلهٔ دلاریِ SL/TP **۱۰ برابر تنگ‌تر** و
// سایزِ پوزیشن ۱۰× بزرگ‌تر روی سیگنالِ زندهٔ S1516 (روی H6 و H4).
//
// این آزمون روی سریِ واقعیِ H6 یک رویدادِ S1516 می‌گیرد و فاصلهٔ دلاریِ SL را
// می‌سنجد. با کدِ باگ‌دار ≈ ۱.۵۲$ می‌دهد ⇒ قرمز؛ با اصلاح ≈ ۱۵.۲۱$ ⇒ سبز.
//
// اجرا: npx tsx tools/_regress_s1516_pip.mts
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { computeS1516, S1516_CFG } from '../src/cal_fresh_floor_s1516'

const ROOT = path.resolve(import.meta.dirname, '../..')
const card = 'XAUUSD-H6'
const cfg = S1516_CFG[card]
const EXPECTED_PIP = 0.1
const EXPECTED_SL_USD = cfg.slPip * EXPECTED_PIP // 152.10 × 0.1 = 15.21

function loadCsv(tf: string) {
  const text = zlib.gunzipSync(fs.readFileSync(path.join(ROOT, `data/mt5_full/XAUUSD_${tf}.csv.gz`))).toString('utf8')
  const lines = text.trim().split('\n').map(l => l.replace(/\r$/, ''))
  const head = lines[0].split(','); const ix = (n: string) => head.indexOf(n)
  const [iT, iO, iH, iL, iC] = ['time', 'open', 'high', 'low', 'close'].map(ix)
  return lines.slice(1).map(l => { const t = l.split(',');
    return { time: Number(t[iT]), open: Number(t[iO]), high: Number(t[iH]), low: Number(t[iL]), close: Number(t[iC]), volume: 0 } })
}

const all = loadCsv('H6')
let raw: any = null
for (let i = all.length - 1; i >= Math.max(cfg.lookback + 5, all.length - 4000); i--) {
  const d: any = computeS1516(all.slice(0, i + 1) as any, cfg)
  if (d && d.active === true) { raw = d; break }
}

if (!raw) { console.log('❌ RED — هیچ رویدادِ فعالِ S1516 روی ۴۰۰۰ کندلِ اخیر پیدا نشد'); process.exit(1) }

const slUsd = raw.slDist as number
const slPip = slUsd / EXPECTED_PIP
console.log(`رویدادِ S1516 · direction=${raw.direction} slDist=${slUsd} tpDist=${raw.tpDist}`)
console.log(`  فاصلهٔ دلاریِ SL = ${slUsd.toFixed(5)}$  (منتظر ${EXPECTED_SL_USD.toFixed(5)}$)`)
console.log(`  یعنی ${slPip.toFixed(2)} pip با pip=0.1`)

const okUsd = Math.abs(slUsd - EXPECTED_SL_USD) < 0.02
if (okUsd) { console.log('\n✅ GREEN — pip=0.1 رعایت شد (SL ≈ ۱۵.۲۱$، نه ۱.۵۲$).'); process.exit(0) }
console.log(`\n❌ RED — pip اشتباه است: ${slUsd.toFixed(5)}$ به‌جای ${EXPECTED_SL_USD.toFixed(5)}$ `
  + `(نسبت ${(EXPECTED_SL_USD / slUsd).toFixed(1)}× ⇒ دامِ pipSize=0.01 در برابرِ GOLD_PIP=0.1).`)
process.exit(1)
