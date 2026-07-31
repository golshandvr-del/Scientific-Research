// overlap_probe_h1.ts — ممیزیِ اجباریِ همپوشانی برای کارتِ `XAUUSD-H1`
// ============================================================================
// قانونِ همپوشانیِ پروژه: پیش از افزودنِ هر لایه باید بدانیم «دقیقاً با کدام
// لایه/لایه‌های موجود همپوشانی دارد و چند درصد»، و بندِ چهارم می‌گوید این
// همپوشانی «از طریقِ شبیه‌سازِ رویداد-محور» سنجیده شود.
//
// ### چرا TS و نه بازسازیِ پایتونی
// ممیزیِ همپوشانیِ قبلیِ پروژه (`strategies/s341_multitf_overlap_audit.py`)
// لایه‌های موجود را **تقریبی** در پایتون بازسازی می‌کرد («بازسازیِ تقریبیِ
// S333»). یک تقریب، همپوشانی را هم می‌تواند بیش‌برآورد کند و هم کم‌برآورد، و
// در هر دو حالت نتیجه‌گیریِ «لبهٔ نو» بی‌پشتوانه می‌شود.
//
// اینجا مستقیماً همان توابعِ خالصی صدا زده می‌شوند که **خودِ سایت** اجرا می‌کند
// (`computeS341` … `computeMidMonth`). یعنی مجموعهٔ ورودی که با آن مقایسه
// می‌کنیم، دقیقاً همان چیزی است که کاربر روی کارت می‌بیند — نه شبیهِ آن.
//
// ### چرا `active` (و نه `approaching`)
// همپوشانیِ عملی یعنی «دو لایه هم‌زمان به کاربر بگویند وارد شو». حالتِ
// `approaching` یک هشدارِ انتظار است و معامله‌ای نمی‌سازد، پس در شمارشِ
// همپوشانی نمی‌آید. با این حال `approaching` هم شمرده و گزارش می‌شود، چون
// اگر همپوشانیِ `active` صفر بود، همپوشانیِ `approaching` می‌گوید آیا دو لایه
// «نزدیکِ هم» فعال می‌شوند یا در نواحیِ کاملاً متفاوتی از بازار زندگی می‌کنند.
//
// ### پنجرهٔ دنباله‌دار
// برای هر کندلِ i یک پنجرهٔ `[i-WIN+1 … i]` ساخته و به لایه داده می‌شود. این
// causal است (هیچ کندلِ آینده‌ای در پنجره نیست) و WIN=1500 از همان استدلالِ
// `parity_s345_signal.mjs` می‌آید: بلندترین پنجرهٔ اندیکاتوریِ این لایه‌ها
// (EMA200 و بازه‌های ~۵۵–۱۰۰) خیلی کوچک‌تر از ۱۵۰۰ است، پس همهٔ آن‌ها همگرا
// شده‌اند و پنجرهٔ بلندتر عدد را تغییر نمی‌دهد.
import fs from 'fs'
import type { Candle } from './src/indicators'
import { computeS341, S341_CFG } from './src/swing_fade_s341'
import { computeS333, S333_CFG } from './src/s333_pullback'
import { computeS313, S313_H1 } from './src/squeeze_revival_s313'
import { computeS328, S328_CFG, computeS323, S323_CFG } from './src/revived_strategies'
import { computeSellClimax, SELL_CLIMAX_CFG } from './src/sell_climax_s327'
import { computeMidMonth } from './src/mid_month_drift'
import { computeS335, S335_CFG } from './src/s335_reflex_cycle'

const CARD = 'XAUUSD-H1'
const WIN = 1500

type Probe = { code: string; kind: string; fn: (w: Candle[], t: number[], h: number) => { active: boolean; approaching?: boolean } }

// ترتیب و پیکربندی عیناً از `CARD_LAYERS['XAUUSD-H1']` در `strategy_registry.ts`.
const PROBES: Probe[] = [
  { code: 'S341', kind: 'swing-fade در رنج (LONG)', fn: (w) => computeS341(w, S341_CFG[CARD]) },
  { code: 'S333', kind: 'pullback احیای S79 (LONG)', fn: (w) => computeS333(w, S333_CFG[CARD]) },
  {
    code: 'S313', kind: 'squeeze-breakout (LONG)',
    fn: (w) => computeS313(w.map(c => c.open), w.map(c => c.high), w.map(c => c.low), w.map(c => c.close), S313_H1),
  },
  { code: 'S328', kind: 'RSI21 mean-reversion', fn: (w) => computeS328(w, S328_CFG[CARD]) },
  { code: 'S327', kind: 'sell-climax reversal', fn: (w) => computeSellClimax(w, SELL_CLIMAX_CFG[CARD]) },
  { code: 'S323', kind: 'S/R pullback', fn: (w, t, h) => computeS323(w, S323_CFG[CARD], h) },
  { code: 'S335', kind: 'reflex dip-turn (LONG)', fn: (w) => computeS335(w, S335_CFG[CARD]) },
  { code: 'S312', kind: 'mid-month drift (زمان-محور)', fn: (w, t, h) => computeMidMonth(t, h) },
]

function loadCandles(fn: string): Candle[] {
  const txt = fs.readFileSync(fn, 'utf8')
  const lines = txt.split('\n')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const L = lines[i].trim()
    if (!L) continue
    const p = L.split(',')
    out.push({
      time: Number(p[0]), open: Number(p[1]), high: Number(p[2]),
      low: Number(p[3]), close: Number(p[4]), volume: Number(p[5] || 0),
    } as Candle)
  }
  return out
}

function main() {
  const args = process.argv.slice(2)
  const strideArg = args.find(a => a.startsWith('--stride='))
  const stride = strideArg ? Number(strideArg.split('=')[1]) : 1
  const barsArg = args.find(a => a.startsWith('--bars='))
  const tagArg = args.find(a => a.startsWith('--tag='))
  const tag = tagArg ? tagArg.split('=')[1] : (barsArg ? 'atbars' : `stride${stride}`)

  const candles = loadCandles('../data/XAUUSD_H1.csv')
  const times = candles.map(c => c.time)
  const N = candles.length

  // مجموعهٔ اندیس‌های ارزیابی
  let idx: number[]
  if (barsArg) {
    const spec = JSON.parse(fs.readFileSync(barsArg.split('=')[1], 'utf8'))
    const base: number[] = spec.trade_bars || spec.bars || spec
    const tolArg = args.find(a => a.startsWith('--tol='))
    const tol = tolArg ? Number(tolArg.split('=')[1]) : 0
    const s = new Set<number>()
    for (const b of base) for (let d = -tol; d <= tol; d++) if (b + d >= WIN && b + d < N) s.add(b + d)
    idx = [...s].sort((a, b) => a - b)
  } else {
    idx = []
    for (let i = WIN; i < N; i += stride) idx.push(i)
  }

  const act: Record<string, number[]> = {}
  const app: Record<string, number[]> = {}
  const errs: Record<string, number> = {}
  for (const p of PROBES) { act[p.code] = []; app[p.code] = []; errs[p.code] = 0 }

  const t0 = Date.now()
  let done = 0
  for (const i of idx) {
    const lo = Math.max(0, i - WIN + 1)
    const win = candles.slice(lo, i + 1)
    const tw = times.slice(lo, i + 1)
    const hour = new Date(times[i] * 1000).getUTCHours()
    for (const p of PROBES) {
      try {
        const r = p.fn(win, tw, hour)
        if (r && r.active) act[p.code].push(i)
        else if (r && r.approaching) app[p.code].push(i)
      } catch { errs[p.code]++ }
    }
    if (++done % 2000 === 0) {
      const el = (Date.now() - t0) / 1000
      process.stdout.write(`  ${done}/${idx.length}  ${el.toFixed(0)}s  eta ${((el / done) * (idx.length - done)).toFixed(0)}s\n`)
    }
  }

  const rec = {
    card: CARD, bars: N, win: WIN, mode: barsArg ? 'atbars' : 'stride',
    stride, evaluated: idx.length,
    layers: PROBES.map(p => ({
      code: p.code, kind: p.kind,
      n_active: act[p.code].length, n_approaching: app[p.code].length,
      errors: errs[p.code], active_bars: act[p.code],
    })),
    elapsed_s: Math.round((Date.now() - t0) / 10) / 100,
  }
  const out = `../results/_scan_S356/overlap_h1_${tag}.json`
  fs.writeFileSync(out, JSON.stringify(rec, null, 1), 'utf8')
  console.log(`\n=== ${CARD} probe (${rec.mode}) evaluated=${idx.length} in ${rec.elapsed_s}s`)
  for (const L of rec.layers) {
    console.log(`  ${L.code}  active=${String(L.n_active).padStart(6)}  approaching=${String(L.n_approaching).padStart(6)}  err=${L.errors}   ${L.kind}`)
  }
  console.log(`[saved] ${out}`)
}

main()
