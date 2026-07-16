// ============================================================================
// ماژول کلاینت (مرورگر) — Regime-Router سه‌مغزی (پاسخ به User Note کاربر)
// ============================================================================
// معماری جدید طبق درخواست کاربر: ابتدا روند تشخیص داده می‌شود، سپس بسته به روند
// یکی از سه مغز تخصصی فعال می‌گردد:
//
//   ۱) مغز صعودی  (Bull, S25) : وقتی price > EMA50 > EMA200 → فقط LONG
//       مدل ONNX ensemble S25 (WR=61.6٪) با THR=0.68، TP1.0/SL1.5×ATR.
//
//   ۲) مغز نزولی  (Bear, S31) : وقتی price < EMA50 < EMA200 → فقط SHORT
//       مدل ONNX ensemble Bear (PF=1.49, exp=+1.71$, WR=58.4٪, p=0.015)
//       با THR=0.66، TP1.4/SL1.7×ATR. این مغز پاسخ مستقیم به User Note است:
//       دیگر در روند نزولی سکوت نمی‌کنیم.
//
//   ۳) رنج/بدون‌روند : وقتی هیچ‌کدام از دو شرط بالا برقرار نیست → NONE
//       (مغز رنج S32 هیچ edge معناداری نداشت؛ تصمیم علمیِ صحیح در رنج = سکوت).
//
// هر دو مغز دقیقاً از همان ۵۹ feature (buildFeatures / FEATURE_ORDER) استفاده
// می‌کنند، پس فقط یک بار feature ساخته می‌شود و بین دو مغز مشترک است.
// onnxruntime-web از CDN (global `ort`) بارگذاری می‌شود تا باندل سبک بماند.
// ============================================================================
import type { Candle } from '../indicators'
import { buildFeatures, FEATURE_ORDER } from '../features'

declare const ort: any // از CDN لود می‌شود (onnxruntime-web)

const N_FEATURES = FEATURE_ORDER.length  // ۵۹ (مشترک S25 و Bear)

// --- پارامترهای مغز صعودی (S25) ---
const BULL = {
  thr: 0.68, tp: 1.0, sl: 1.5, be: 60.0,
  urls: [
    '/static/models/xauusd_s25_model_0.onnx',
    '/static/models/xauusd_s25_model_1.onnx',
    '/static/models/xauusd_s25_model_2.onnx',
  ],
}

// --- پارامترهای مغز نزولی (Bear, S31 — model_meta_bear.txt) ---
const BEAR = {
  thr: 0.66, tp: 1.4, sl: 1.7, be: 54.84,
  urls: [
    '/static/models/xauusd_bear_model_0.onnx',
    '/static/models/xauusd_bear_model_1.onnx',
    '/static/models/xauusd_bear_model_2.onnx',
  ],
}

// کش سشن‌های هر مغز
const cache: Record<string, any[]> = {}
const loading: Record<string, Promise<any[]>> = {}

function setupWasm() {
  if (ort?.env?.wasm) {
    ort.env.wasm.numThreads = 1
    ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/'
  }
}

// بارگذاری یک‌بارهٔ ۳ مدل ensemble یک مغز (با کش)
async function loadBrain(key: string, urls: string[]): Promise<any[]> {
  if (cache[key]) return cache[key]
  if (loading[key]) return loading[key]
  loading[key] = (async () => {
    setupWasm()
    const loaded: any[] = []
    for (const url of urls) {
      const buf = await (await fetch(url)).arrayBuffer()
      loaded.push(await ort.InferenceSession.create(buf, { executionProviders: ['wasm'] }))
    }
    cache[key] = loaded
    return loaded
  })()
  return loading[key]
}

// احتمال ensemble کلاس ۱ (win) برای یک بردار feature
async function ensembleProba(sessions: any[], vec: Float32Array): Promise<number> {
  const tensor = new ort.Tensor('float32', vec, [1, N_FEATURES])
  let sum = 0
  for (const sess of sessions) {
    const feeds: any = {}
    feeds[sess.inputNames[0]] = tensor
    const out = await sess.run(feeds)
    const probKey = out['probabilities'] ? 'probabilities'
      : Object.keys(out).find((k: string) => out[k].dims && out[k].dims.length === 2)!
    sum += out[probKey].data[1]
  }
  return sum / sessions.length
}

export type Regime = 'bull' | 'bear' | 'range'

export interface ModelSignal {
  ready: boolean
  regime: Regime             // روند تشخیص‌داده‌شده
  activeBrain: 'bull' | 'bear' | 'none'  // مغز فعال
  probability: number        // احتمال مغزِ فعال (۰..۱)؛ در رنج = 0
  probabilityPct: number
  threshold: number
  regimeOk: boolean          // آیا شرط روندِ مغز فعال برقرار است
  direction: 'LONG' | 'SHORT' | 'NONE'
  entry: number | null
  tp: number | null
  sl: number | null
  atr: number
  rr: string
  confidence: 'high' | 'medium' | 'low'
  source: string
  reason: string             // توضیح فارسی برای نمایش به کاربر
}

// تشخیص روند بر اساس رابطهٔ قیمت و EMA50/EMA200
function detectRegime(price: number, ema50: number, ema200: number): Regime {
  if (price > ema50 && ema50 > ema200) return 'bull'
  if (price < ema50 && ema50 < ema200) return 'bear'
  return 'range'
}

// محاسبهٔ سیگنال روی آخرین کندلِ معتبر — با روتر سه‌مغزی
export async function computeModelSignal(candles: Candle[]): Promise<ModelSignal> {
  const fm = buildFeatures(candles)
  let i = candles.length - 1
  while (i > 0 && !fm.valid[i]) i--
  const price = candles[i].close
  const atr = fm.atr[i]
  const ema50 = fm.ema50[i]
  const ema200 = fm.ema200[i]

  const regime = detectRegime(price, ema50, ema200)

  // --- مغز رنج: سکوت (بدون edge معنادار — S32) ---
  if (regime === 'range') {
    return {
      ready: true, regime, activeBrain: 'none',
      probability: 0, probabilityPct: 0, threshold: 0,
      regimeOk: false, direction: 'NONE',
      entry: null, tp: null, sl: null, atr,
      rr: '—', confidence: 'low', source: 'regime-router',
      reason: 'بازار در حالت رنج/بدون‌روند است. طبق تحقیق (استراتژی ۳۲) هیچ مغزی در رنج edge پایدار ندارد؛ تصمیم علمیِ صحیح = عدم معامله.',
    }
  }

  // --- انتخاب مغز فعال ---
  const cfg = regime === 'bull' ? BULL : BEAR
  const brainKey = regime === 'bull' ? 'bull' : 'bear'
  const sessions = await loadBrain(brainKey, cfg.urls)
  const p = await ensembleProba(sessions, fm.rows[i])

  const passes = p >= cfg.thr
  let direction: 'LONG' | 'SHORT' | 'NONE' = 'NONE'
  let entry: number | null = null, tp: number | null = null, sl: number | null = null

  if (passes) {
    if (regime === 'bull') {
      direction = 'LONG'
      entry = price
      tp = price + cfg.tp * atr
      sl = price - cfg.sl * atr
    } else {
      direction = 'SHORT'
      entry = price
      tp = price - cfg.tp * atr
      sl = price + cfg.sl * atr
    }
  }

  let confidence: 'high' | 'medium' | 'low' = 'low'
  if (p >= cfg.thr + 0.07) confidence = 'high'
  else if (p >= cfg.thr) confidence = 'medium'

  const brainName = regime === 'bull' ? 'مغز صعودی (S25)' : 'مغز نزولی (S31)'
  let reason: string
  if (direction === 'NONE') {
    reason = `${brainName} فعال است اما اطمینان مدل (${(p * 100).toFixed(1)}٪) کمتر از آستانهٔ ${(cfg.thr * 100).toFixed(0)}٪ است — منتظر ستاپ باکیفیت‌تر.`
  } else {
    reason = `${brainName} فعال — سیگنال ${direction === 'LONG' ? 'خرید' : 'فروش'} با اطمینان ${(p * 100).toFixed(1)}٪.`
  }

  return {
    ready: true, regime, activeBrain: brainKey as 'bull' | 'bear',
    probability: p,
    probabilityPct: Number((p * 100).toFixed(2)),
    threshold: cfg.thr,
    regimeOk: true,
    direction,
    entry, tp, sl, atr,
    rr: `TP ${cfg.tp}×ATR / SL ${cfg.sl}×ATR (BE=${cfg.be.toFixed(0)}%)`,
    confidence,
    source: regime === 'bull' ? 'onnx-ensemble-s25' : 'onnx-ensemble-bear',
    reason,
  }
}

// پیش‌بارگذاری هر دو مغز (اختیاری، برای کاهش تأخیر اولین سیگنال)
async function loadAll() {
  await Promise.all([
    loadBrain('bull', BULL.urls),
    loadBrain('bear', BEAR.urls),
  ])
}

// نمای سراسری برای فراخوانی از app.js
;(window as any).GoldModel = { computeModelSignal, loadAll }
