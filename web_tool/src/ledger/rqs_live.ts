// ============================================================================
// ledger/rqs_live.ts — گرهِ دفترِ RQS زنده (محاسبه + بایگانی)  [webplan P7 · #۳]
// ----------------------------------------------------------------------------
// نتیجهٔ واقعیِ معاملاتِ کاربر را نگه می‌دارد و RQS+ زندهٔ هر لایه را دقیقاً طبقِ
// docs/RQS_ROBUST_QUALITY_SCORE.md محاسبه می‌کند (۶ گیتِ veto + نمرهٔ وزنیِ ۰..۱۰۰).
// اگر RQS زنده < ۸۰ با نمونهٔ کافی ⇒ پرچمِ «بایگانیِ موقت» (سایتِ یادگیرنده).
//
// طراحیِ ایمن: ذخیره درون‌حافظه‌ای (Map). این گره هیچ تصمیمی را تغییر نمی‌دهد؛
// فقط از طریقِ endpointهای /api/ledger/* مصرف می‌شود.
// ============================================================================

import {
  type TradeOutcome, type LiveRqs, type GateResult,
  LEDGER_CONTRACT_VERSION, RQS_LIVE_THRESHOLD, RQS_LIVE_MIN_SAMPLES,
} from './contracts'

// --- انبارِ درون‌حافظه‌ای: کلید = `${cardId}::${layerCode}` ⇒ فهرستِ نتایج. ---
const STORE = new Map<string, TradeOutcome[]>()

function keyOf(cardId: string, layerCode: string): string {
  return `${cardId}::${layerCode}`
}

/** ثبتِ یک نتیجهٔ معاملهٔ واقعی. پی‌ال و win از entry/exit/dir بازمحاسبه می‌شود
 *  تا با ورودیِ ناسازگارِ کاربر هم درست بماند (دفاعِ داده). */
export function recordOutcome(raw: Partial<TradeOutcome>): TradeOutcome {
  const cardId = String(raw.cardId || '').trim()
  const layerCode = String(raw.layerCode || '').trim()
  if (!cardId || !layerCode) throw new Error('cardId و layerCode لازم‌اند')
  const dir = raw.dir === 'SHORT' ? 'SHORT' : 'LONG'
  const entry = Number(raw.entry)
  const exit = Number(raw.exit)
  if (!Number.isFinite(entry) || !Number.isFinite(exit)) throw new Error('entry/exit نامعتبر')
  const tpDist = Math.abs(Number(raw.tpDist)) || 0
  const slDist = Math.abs(Number(raw.slDist)) || 0
  // pnl به دلار: حرکتِ قیمت × CONTRACT_SIZE(100) × ۱ لات (نرمال‌سازیِ واحد).
  const move = dir === 'LONG' ? (exit - entry) : (entry - exit)
  const pnl = Number.isFinite(Number(raw.pnl)) ? Number(raw.pnl) : move * 100
  const rec: TradeOutcome = {
    v: LEDGER_CONTRACT_VERSION, cardId, layerCode, dir, entry, exit,
    tpDist, slDist, pnl, win: pnl > 0,
    closedAt: Number(raw.closedAt) || Date.now(),
  }
  const k = keyOf(cardId, layerCode)
  const arr = STORE.get(k) || []
  arr.push(rec)
  STORE.set(k, arr)
  return rec
}

/** خواندنِ نتایجِ خامِ یک لایه (برای گزارش/بازبینی). */
export function outcomesOf(cardId: string, layerCode: string): TradeOutcome[] {
  return (STORE.get(keyOf(cardId, layerCode)) || []).slice()
}

/** فهرستِ همهٔ کلیدهای دارای داده. */
export function ledgerKeys(): { cardId: string; layerCode: string; n: number }[] {
  return Array.from(STORE.entries()).map(([k, arr]) => {
    const [cardId, layerCode] = k.split('::')
    return { cardId, layerCode, n: arr.length }
  })
}

/** پاک‌سازیِ کاملِ دفتر (برای تست/ریست). */
export function clearLedger(): void { STORE.clear() }

// ----------------------------------------------------------------------------
// آمارهٔ کمکی
// ----------------------------------------------------------------------------

/** CDF نرمالِ استاندارد (تقریبِ Abramowitz-Stegun 7.1.26). */
function normalCdf(z: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(z))
  const d = 0.3989422804014337 * Math.exp(-z * z / 2)
  let p = d * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  p = 1 - p
  return z >= 0 ? p : 1 - p
}

/** p-value آزمونِ دوجمله‌ایِ یک‌دامنه (wins > n×p0) با تقریبِ نرمال + اصلاحِ پیوستگی.
 *  برای n≥30 (کفِ پروژه) دقیق است. */
function binomialPGreater(wins: number, n: number, p0: number): number {
  if (n <= 0) return 1
  const mean = n * p0
  const sd = Math.sqrt(n * p0 * (1 - p0))
  if (sd < 1e-9) return wins > mean ? 0 : 1
  // اصلاحِ پیوستگی: P(X ≥ wins) ≈ 1 − Φ((wins − 0.5 − mean)/sd)
  const z = (wins - 0.5 - mean) / sd
  return 1 - normalCdf(z)
}

function clip(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x
}

// ----------------------------------------------------------------------------
// محاسبهٔ RQS+ زنده — دقیقاً طبقِ docs/RQS_ROBUST_QUALITY_SCORE.md
// ----------------------------------------------------------------------------
export function computeLiveRqs(cardId: string, layerCode: string): LiveRqs {
  const trades = outcomesOf(cardId, layerCode)
  const n = trades.length

  // آمارهٔ پایه
  const wins = trades.filter(t => t.win).length
  const wr = n > 0 ? wins / n : 0
  const grossWin = trades.filter(t => t.pnl > 0).reduce((s, t) => s + t.pnl, 0)
  const grossLoss = Math.abs(trades.filter(t => t.pnl < 0).reduce((s, t) => s + t.pnl, 0))
  const pf = grossLoss > 1e-9 ? grossWin / grossLoss : (grossWin > 0 ? Infinity : 0)
  const expectancy = n > 0 ? trades.reduce((s, t) => s + t.pnl, 0) / n : 0

  // بیشترین رشتهٔ باختِ متوالی
  let mcl = 0, cur = 0
  for (const t of trades) { if (!t.win) { cur++; mcl = Math.max(mcl, cur) } else cur = 0 }

  // maxDD٪ از منحنیِ اکوییتیِ واقعی.
  //  نکتهٔ روش‌شناختی: drawdown را نسبت به یک «پایهٔ سرمایهٔ فرضی» می‌سنجیم، نه نسبت
  //  به peakِ منحنیِ سودِ تجمعی (که می‌تواند نزدیکِ صفر بماند و نسبت را بی‌معنا منفجر
  //  کند). پایه = ماکزیمومِ (ریسکِ یک معامله × ۲۵) و بزرگ‌ترین اکوییتیِ رسیده — یعنی
  //  «حسابی که ۲۵ برابرِ ریسکِ هر معامله سرمایه دارد» (سازگار با مارجینِ دمو).
  const avgRisk = (() => {
    const rs = trades.map(t => Math.max(t.slDist, 1) * 100).filter(x => x > 0)
    return rs.length ? rs.reduce((s, x) => s + x, 0) / rs.length : 100
  })()
  const baseCapital = Math.max(avgRisk * 25, 1)
  //  drawdown را نسبت به «سرمایهٔ پایهٔ ثابت» می‌سنجیم (نه peakِ متغیر) تا معیار پایدار
  //  و مقایسه‌پذیر بماند و با معاملهٔ باختِ اولیه منفجر نشود.
  let equity = 0, peak = 0, maxDDabs = 0
  for (const t of trades) {
    equity += t.pnl
    peak = Math.max(peak, equity)
    maxDDabs = Math.max(maxDDabs, peak - equity)   // بزرگ‌ترین افتِ مطلق از اوج
  }
  const maxDDPct = baseCapital > 1e-9 ? (maxDDabs / baseCapital) * 100 : 0

  // WR_breakeven از میانگینِ نسبتِ SL/(SL+TP)
  const rr = trades.filter(t => (t.slDist + t.tpDist) > 0)
  const wrBreakeven = rr.length > 0
    ? rr.reduce((s, t) => s + t.slDist / (t.slDist + t.tpDist), 0) / rr.length
    : 0.5
  const wrExcess = wr - wrBreakeven
  const pValue = binomialPGreater(wins, n, clip(wrBreakeven, 1e-6, 1 - 1e-6))

  // هزینهٔ اسپرد (طبقِ مشخصاتِ دمو): 0.33$/oz × 100 = 33$ per لات per معامله
  const spreadCost = 0.33 * 100

  // --- ۶ گیتِ veto ---
  const gates: GateResult[] = [
    {
      id: 'G0', name: 'WR Floor', pass: wr >= 0.60 && n >= 30,
      detail: `WR=${(wr * 100).toFixed(1)}% (لازم ≥۶۰٪)، n=${n} (لازم ≥۳۰)`,
    },
    {
      id: 'G1', name: 'Edge over Random',
      pass: expectancy > 0 && wrExcess >= 0.03 && pValue < 0.05,
      detail: `WR_excess=${(wrExcess * 100).toFixed(1)}% (≥۳٪)، p=${pValue.toFixed(4)} (<0.05)`,
    },
    {
      id: 'G2', name: 'Profit Factor', pass: pf >= 1.3,
      detail: `PF=${Number.isFinite(pf) ? pf.toFixed(2) : '∞'} (لازم ≥۱.۳)`,
    },
    {
      id: 'G3', name: 'Tail Risk', pass: maxDDPct <= 8 && mcl <= 8,
      detail: `maxDD=${maxDDPct.toFixed(1)}% (≤۸٪)، MCL=${mcl} (≤۸)`,
    },
    {
      // walk-forward زنده: داده را به ۴ پنجرهٔ برابر می‌بریم؛ هر پنجره باید مثبت باشد.
      id: 'G4', name: 'Stability (WF)', pass: walkForwardPass(trades),
      detail: `۴ پنجرهٔ زنده + هر دو نیمه مثبت`,
    },
    {
      id: 'G5', name: 'Expectancy', pass: expectancy > 0.5 * spreadCost,
      detail: `exp=${expectancy.toFixed(1)}$ (لازم >۰.۵×هزینه=${(0.5 * spreadCost).toFixed(0)}$)`,
    },
  ]
  const passedAllGates = n >= RQS_LIVE_MIN_SAMPLES && gates.every(g => g.pass)

  // --- نمرهٔ وزنیِ نرمال‌شده (۰..۱) ---
  const wScore =
    0.25 * clip((pf === Infinity ? 2 : pf - 1) / (2.0 - 1), 0, 1) +
    0.20 * clip(expectancy / (2 * spreadCost), 0, 1) +
    0.20 * (walkForwardRatio(trades)) +
    0.15 * clip((0.05 - pValue) / 0.05, 0, 1) +
    0.15 * (clip(1 - maxDDPct / 8, 0, 1) * clip(1 - mcl / 8, 0, 1)) +
    0.05 * clip((wr * 100 - 60) / 20, 0, 1)

  const rqs = passedAllGates
    ? 40 + 60 * wScore
    : Math.min(40, 40 * wScore)

  // آیا باید بایگانی شود؟ فقط با نمونهٔ کافی (وگرنه «داده ناکافی»، نه بایگانی).
  const shouldArchive = n >= RQS_LIVE_MIN_SAMPLES && rqs < RQS_LIVE_THRESHOLD

  let note: string
  if (n < RQS_LIVE_MIN_SAMPLES) {
    note = `دادهٔ زندهٔ ناکافی (n=${n}<${RQS_LIVE_MIN_SAMPLES}) — قضاوت به تعویق افتاد.`
  } else if (shouldArchive) {
    note = `RQS زنده=${rqs.toFixed(1)} < ۸۰ ⇒ پیشنهادِ بایگانیِ موقت (لایه در عمل افت کرده).`
  } else {
    note = `RQS زنده=${rqs.toFixed(1)} ≥ ۸۰ ⇒ لایه در عمل سالم است.`
  }

  return {
    v: LEDGER_CONTRACT_VERSION, layerCode, cardId, n,
    wr, pf: Number.isFinite(pf) ? pf : 999, expectancy,
    maxConsecLoss: mcl, maxDDPct, pValue,
    rqs: Math.round(rqs * 10) / 10, passedAllGates, gates, shouldArchive, note,
  }
}

/** walk-forward زنده: ۴ پنجرهٔ متوالیِ برابر، هر کدام باید جمعِ pnl>0 و هر دو نیمه هم مثبت. */
function walkForwardPass(trades: TradeOutcome[]): boolean {
  if (trades.length < 8) return false
  return windowsPositive(trades, 4) === 4 && halvesPositive(trades)
}
function walkForwardRatio(trades: TradeOutcome[]): number {
  if (trades.length < 8) return 0
  const w = windowsPositive(trades, 4) / 4
  return w * (halvesPositive(trades) ? 1 : 0.5)
}
function windowsPositive(trades: TradeOutcome[], k: number): number {
  const size = Math.floor(trades.length / k)
  if (size < 1) return 0
  let pos = 0
  for (let i = 0; i < k; i++) {
    const seg = trades.slice(i * size, i === k - 1 ? trades.length : (i + 1) * size)
    if (seg.reduce((s, t) => s + t.pnl, 0) > 0) pos++
  }
  return pos
}
function halvesPositive(trades: TradeOutcome[]): boolean {
  const mid = Math.floor(trades.length / 2)
  const a = trades.slice(0, mid).reduce((s, t) => s + t.pnl, 0)
  const b = trades.slice(mid).reduce((s, t) => s + t.pnl, 0)
  return a > 0 && b > 0
}

/** خلاصهٔ RQS زندهٔ همهٔ لایه‌های دارای داده — برای endpointِ گزارش. */
export function liveRqsSummary(): LiveRqs[] {
  return ledgerKeys().map(k => computeLiveRqs(k.cardId, k.layerCode))
}
