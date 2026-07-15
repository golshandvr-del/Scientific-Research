// ============================================================================
// ماژول کلاینت (مرورگر) — اجرای واقعی مدل ONNX ربات با onnxruntime-web.
// این فایل با esbuild به public/static/browser-signal.js باندل می‌شود و در
// مرورگر توسط app.js فراخوانی می‌گردد. onnxruntime-web از CDN بارگذاری می‌شود
// (به‌صورت global `ort`) تا باندل سبک بماند.
//
// جریان کار:
//   candles (از API) → buildFeatures (هم‌ارز features.py) → ۳ مدل ONNX ensemble
//   → میانگین احتمال کلاس long-win → تصمیم LONG/NONE با آستانه THR=0.68 + رژیم.
// خروجی «دقیقاً معادل ربات MT5» است (نه تقریب امتیازدهی).
// ============================================================================
import type { Candle } from '../indicators'
import { buildFeatures } from '../features'

declare const ort: any // از CDN لود می‌شود (onnxruntime-web)

const THR = 0.68           // آستانه اطمینان مدل (model_meta.txt)
const TP_M = 1.0, SL_M = 1.5, HZ = 48, BE = 60.0
const MODEL_URLS = [
  '/static/models/xauusd_s14_model_0.onnx',
  '/static/models/xauusd_s14_model_1.onnx',
  '/static/models/xauusd_s14_model_2.onnx',
]

let sessions: any[] | null = null
let loadingPromise: Promise<any[]> | null = null

// بارگذاری یک‌بارهٔ ۳ مدل ensemble (با کش مرورگر)
async function loadModels(): Promise<any[]> {
  if (sessions) return sessions
  if (loadingPromise) return loadingPromise
  loadingPromise = (async () => {
    // مسیر فایل‌های wasm از CDN
    if (ort?.env?.wasm) {
      ort.env.wasm.numThreads = 1
      ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/'
    }
    const loaded = []
    for (const url of MODEL_URLS) {
      const buf = await (await fetch(url)).arrayBuffer()
      loaded.push(await ort.InferenceSession.create(buf, { executionProviders: ['wasm'] }))
    }
    sessions = loaded
    return sessions
  })()
  return loadingPromise
}

// احتمال ensemble کلاس ۱ (long-win) برای یک بردار feature ۵۷تایی
async function ensembleProba(vec: Float32Array): Promise<number> {
  const s = await loadModels()
  const tensor = new ort.Tensor('float32', vec, [1, 57])
  let sum = 0
  for (const sess of s) {
    const feeds: any = {}
    feeds[sess.inputNames[0]] = tensor
    const out = await sess.run(feeds)
    // خروجی probabilities: [1,2] → ستون کلاس ۱
    const probKey = out['probabilities'] ? 'probabilities'
      : Object.keys(out).find((k: string) => out[k].dims && out[k].dims.length === 2)!
    sum += out[probKey].data[1]
  }
  return sum / s.length
}

export interface ModelSignal {
  ready: boolean
  probability: number         // احتمال واقعی مدل ensemble (۰..۱)
  probabilityPct: number      // درصد
  threshold: number
  regimeOk: boolean
  direction: 'LONG' | 'NONE'
  entry: number | null
  tp: number | null
  sl: number | null
  atr: number
  rr: string
  confidence: 'high' | 'medium' | 'low'
  source: 'onnx-ensemble'     // نشانگر: این سیگنالِ واقعیِ مدل است
}

// محاسبهٔ سیگنال واقعی مدل روی آخرین کندلِ معتبر
export async function computeModelSignal(candles: Candle[]): Promise<ModelSignal> {
  const fm = buildFeatures(candles)
  // آخرین کندلِ کاملاً معتبر
  let i = candles.length - 1
  while (i > 0 && !fm.valid[i]) i--
  const price = candles[i].close
  const atr = fm.atr[i]
  const regimeOk = price > fm.ema50[i] && fm.ema50[i] > fm.ema200[i]

  const p = await ensembleProba(fm.rows[i])
  const direction: 'LONG' | 'NONE' = (regimeOk && p >= THR) ? 'LONG' : 'NONE'
  const entry = direction === 'LONG' ? price : null
  const tp = direction === 'LONG' ? price + TP_M * atr : null
  const sl = direction === 'LONG' ? price - SL_M * atr : null
  let confidence: 'high' | 'medium' | 'low' = 'low'
  if (p >= 0.75) confidence = 'high'
  else if (p >= THR) confidence = 'medium'

  return {
    ready: true,
    probability: p,
    probabilityPct: Number((p * 100).toFixed(2)),
    threshold: THR,
    regimeOk,
    direction,
    entry, tp, sl, atr,
    rr: `TP ${TP_M}×ATR / SL ${SL_M}×ATR (BE=${BE}%)`,
    confidence,
    source: 'onnx-ensemble',
  }
}

// نمای سراسری برای فراخوانی از app.js
;(window as any).GoldModel = { computeModelSignal, loadModels }
