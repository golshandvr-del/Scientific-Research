import { fetchGold, aggregateCandles } from '../src/price/gold_source'
const { candles } = await fetchGold('1h', '1y')
const h8 = aggregateCandles(candles, 8)
console.log('raw H1 bars:', candles.length)
console.log('aggregated H8 bars:', h8.length)
console.log('S1520 requirement (90 fresh-high + 100 Wilder ATR):', 190)
console.log('margin:', (h8.length / 190).toFixed(2) + 'x')
console.log('current H8 minBars floor in index.tsx: 880 H1 =', 880/8, 'H8 bars')
console.log('=> floor is', 880/8 >= 190 ? 'SUFFICIENT' : 'TOO LOW — must be raised to ' + 190*8 + ' H1')
