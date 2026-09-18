// آزمونِ شمارشِ لایه‌ها روی سه کارتِ S955 — تأییدِ اینکه S955 واقعاً در آرایه است.
import { CARD_LAYERS } from '../src/strategy_registry'
const expect: Record<string, number> = { 'XAUUSD-H6': 3, 'XAUUSD-H8': 8, 'XAUUSD-H12': 2 }
let bad = 0
for (const [card, want] of Object.entries(expect)) {
  const got = (CARD_LAYERS[card] || []).length
  const ok = got === want
  if (!ok) bad++
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${card}: ${got} layer(s) (expected ${want})`)
}
console.log(bad === 0 ? '\nALL GREEN' : `\n${bad} MISMATCH`)
