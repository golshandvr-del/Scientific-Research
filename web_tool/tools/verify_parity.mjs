// اعتبارسنجی هم‌ارزی TS در برابر مرجع پایتون:
//  ۱) buildFeatures(TS) == features.py برای کندل‌های مرجع
//  ۲) ensemble ONNX روی feature‌های TS == ensemble_proba پایتون
// این تضمین می‌کند سیگنال مرورگر «دقیقاً معادل ربات» است.
import * as ort from 'onnxruntime-web'
ort.env.wasm.numThreads = 1
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { buildFeatures, FEATURE_ORDER } from '../src/features.ts'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..', '..')
const ref = JSON.parse(fs.readFileSync(path.join(__dirname, 'parity_reference.json'), 'utf8'))

// خواندن CSV کامل
const csv = fs.readFileSync(path.join(ROOT, 'data', 'XAUUSD_M15.csv'), 'utf8').trim().split('\n')
const candles = []
for (let i = 1; i < csv.length; i++) {
  const [t, o, h, l, c, v] = csv[i].trim().split(',').map(Number)
  candles.push({ time: t, open: o, high: h, low: l, close: c, volume: v })
}
console.log('کندل‌های خوانده‌شده:', candles.length)

const fm = buildFeatures(candles)

// ---- تست ۱: هم‌ارزی feature ----
let maxFeatDiff = 0
let worstName = ''
for (const row of ref.rows) {
  const idx = row.idx
  const tsVec = fm.rows[idx]
  for (let j = 0; j < FEATURE_ORDER.length; j++) {
    const name = FEATURE_ORDER[j]
    const py = row.features[name]
    const ts = tsVec[j]
    const d = Math.abs(py - ts)
    if (d > maxFeatDiff) { maxFeatDiff = d; worstName = `${name}@${idx}` }
  }
}
console.log(`\n[تست ۱] حداکثر اختلاف feature TS↔Python: ${maxFeatDiff.toExponential(3)} (بدترین: ${worstName})`)

// ---- تست ۲: ensemble ONNX روی feature TS ----
const modelPaths = [0, 1, 2].map(i => path.join(ROOT, 'mt5_robot', `xauusd_s14_model_${i}.onnx`))
const sessions = []
for (const mp of modelPaths) {
  sessions.push(await ort.InferenceSession.create(fs.readFileSync(mp), { executionProviders: ['wasm'] }))
}

async function ensembleProba(vec) {
  const tensor = new ort.Tensor('float32', vec, [1, 57])
  let sum = 0
  for (const s of sessions) {
    const feeds = {}; feeds[s.inputNames[0]] = tensor
    const out = await s.run(feeds)
    const prob = out['probabilities'] || out[Object.keys(out).find(k => out[k].dims.length === 2)]
    sum += prob.data[1] // کلاس ۱
  }
  return sum / sessions.length
}

let maxProbaDiff = 0
console.log('\n[تست ۲] احتمال ensemble (TS-feature+ONNX-wasm) vs Python:')
for (const row of ref.rows) {
  const p = await ensembleProba(fm.rows[row.idx])
  const d = Math.abs(p - row.ensemble_proba)
  if (d > maxProbaDiff) maxProbaDiff = d
  console.log(`  idx=${row.idx} py=${row.ensemble_proba.toFixed(6)} ts=${p.toFixed(6)} diff=${d.toExponential(2)}`)
}
console.log(`\nحداکثر اختلاف احتمال: ${maxProbaDiff.toExponential(3)}`)
console.log(maxFeatDiff < 1e-3 && maxProbaDiff < 1e-4
  ? '\n✅ PARITY تأیید شد — سیگنال مرورگر دقیقاً معادل ربات است.'
  : '\n⚠️ اختلاف قابل‌توجه — نیاز به بررسی.')
