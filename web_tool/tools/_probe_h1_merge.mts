// آزمونِ هم‌ارزیِ ادغامِ بازه‌های H1: برشِ ابَرمجموعه در برابرِ fetchِ مستقیم.
// روی *یک* داده و *یک* لحظه مقایسه می‌کند ⇒ حرکتِ بازار نمی‌تواند نتیجه را آلوده کند
// (همان دامی که آزمونِ نقطه-به-نقطهٔ قبلی رویش افتاد و H4 را کاذباً RED نشان داد).
import { _fetchGoldRaw, fetchGold } from '../src/price/gold_source'

const RANGES = ['3mo', '1y']
let bad = 0
for (const range of RANGES) {
  const direct = await _fetchGoldRaw('1h', range)   // fetchِ واقعیِ همان بازه
  const merged = await fetchGold('1h', range)       // مسیرِ نو: برش از 2y
  // فقط کندل‌های **بسته** را مقایسه کن: آخرین کندل در حالِ تشکیل است و دو
  // درخواستِ متفاوت طبعاً مقدارِ لحظه‌ایِ متفاوت دارند — هیچ لایه‌ای آن را نمی‌خواند.
  const dMap = new Map(direct.candles.slice(0, -1).map(k => [k.time, k]))
  const mMap = new Map(merged.candles.slice(0, -1).map(k => [k.time, k]))
  let common = 0, mismatch = 0
  for (const [t, dk] of dMap) {
    const mk = mMap.get(t)
    if (!mk) continue
    common++
    if (dk.open !== mk.open || dk.high !== mk.high || dk.low !== mk.low || dk.close !== mk.close) mismatch++
  }
  const cover = dMap.size ? (common / dMap.size) * 100 : 0
  const ok = mismatch === 0 && cover > 99.5
  if (!ok) bad++
  console.log(`${ok ? 'PASS' : 'FAIL'}  1h/${range}: direct=${direct.candles.length} merged=${merged.candles.length} | closed-bar overlap=${common} (${cover.toFixed(2)}%) | OHLC mismatches=${mismatch}`)
}
console.log(bad === 0 ? '\nALL GREEN — merged slice is bit-identical on every closed bar' : `\n${bad} RANGE(S) DIVERGED`)
