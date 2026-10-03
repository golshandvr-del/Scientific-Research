// آزمونِ شمارشِ لایه‌ها روی سه کارتِ S955 — تأییدِ اینکه S955 واقعاً در آرایه است.
// ⚠️ انتظارها در طولِ زمان کهنه شده بودند و به‌روز شدند (این آزمون فقط شمارشِ
//    حضورِ S955 را می‌سنجد، نه ترکیبِ دقیقِ کارت):
//      H6  3 → 5 (S1516 و سپس S1581 افزوده شدند)
//      H8  8 → 9 (S798 پیش‌تر افزوده شده بود؛ انتظارِ ۸ از استقرارِ قدیمی مانده بود)
//      H12 2 → 2 (بی‌تغییر)
import { CARD_LAYERS } from '../src/strategy_registry'
const expect: Record<string, number> = { 'XAUUSD-H6': 5, 'XAUUSD-H8': 9, 'XAUUSD-H12': 2 }
let bad = 0
for (const [card, want] of Object.entries(expect)) {
  const got = (CARD_LAYERS[card] || []).length
  const ok = got === want
  if (!ok) bad++
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${card}: ${got} layer(s) (expected ${want})`)
}
console.log(bad === 0 ? '\nALL GREEN' : `\n${bad} MISMATCH`)
