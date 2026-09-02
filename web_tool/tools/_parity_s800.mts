// آزمونِ برابریِ S800 — پورتِ TS در برابرِ مرجعِ پایتون روی دادهٔ کاملِ MT5.
// نتیجهٔ اجرا (۲۰۲۶-۰۹-۰۲): صفر اختلاف روی هر دو تایم‌فریم —
//   D1 : long=77  short=51  atrPct=14.851485 atrSl=99.63423798
//   H12: long=252 short=184 atrPct=33.663366 atrSl=63.10033782
// اجرا: npx tsx tools/_parity_s800.mts D1   |   ... H12
import { s800Features, S800_CFG } from '../src/squeeze_expansion_s800.js'
import fs from 'node:fs'
import zlib from 'node:zlib'
const tf = process.argv[2] || 'D1'
const csv = zlib.gunzipSync(fs.readFileSync(`../data/mt5_full/XAUUSD_${tf}.csv.gz`)).toString()
const lines = csv.trim().split('\n'); lines.shift()
const candles = lines.map(l => { const p = l.split(','); return {
  time: +p[0], open: +p[1], high: +p[2], low: +p[3], close: +p[4], volume: +p[5] } })
const cfg = S800_CFG[tf === 'D1' ? 'XAUUSD-D1' : 'XAUUSD-H12']
const f = s800Features(candles as any, cfg)
const n = candles.length
let nl = 0, ns = 0
for (let t = 0; t < n; t++) {
  if (!(Number.isFinite(f.sqz[t]) && Number.isFinite(f.donchHi[t]) && f.sqz[t] < cfg.sqzQ)) continue
  if (candles[t].close > f.donchHi[t]) nl++
  else if (candles[t].close < f.donchLo[t]) ns++
}
console.log(`TS ${tf}: bars=${n} long=${nl} short=${ns} total=${nl+ns}`)
console.log(`TS ${tf}: atrPct_last=${f.atrPct[n-1].toFixed(6)} atrSl_last=${f.atrSl[n-1].toFixed(8)}`)
