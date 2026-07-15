import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { serveStatic } from 'hono/cloudflare-workers'
import type { Candle } from './indicators'
import { analyze } from './signal'
import { getMTF, getIntermarket, getNews, getSpotGold, type SpotPrice } from './external'

const app = new Hono()

app.use('/api/*', cors())
app.use('/static/*', serveStatic({ root: './public' }))

// ---------------------------------------------------------------------------
// دریافت داده زنده طلا از Yahoo Finance (GC=F = طلای آتی COMEX، بدون نیاز به کلید)
// symbol پیش‌فرض GC=F است؛ interval و range قابل تنظیم.
// ---------------------------------------------------------------------------
async function fetchGold(interval: string, range: string): Promise<{ candles: Candle[]; meta: any }> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=${interval}&range=${range}`
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept': 'application/json',
    },
    cf: { cacheTtl: 30, cacheEverything: true } as any,
  })
  if (!res.ok) throw new Error(`Yahoo API error: ${res.status}`)
  const data: any = await res.json()
  const r = data?.chart?.result?.[0]
  if (!r) throw new Error('No data from Yahoo')
  const ts: number[] = r.timestamp || []
  const q = r.indicators?.quote?.[0] || {}
  const candles: Candle[] = []
  for (let i = 0; i < ts.length; i++) {
    const o = q.open?.[i], h = q.high?.[i], l = q.low?.[i], c = q.close?.[i]
    if (o == null || h == null || l == null || c == null) continue
    candles.push({
      time: ts[i],
      open: o, high: h, low: l, close: c,
      volume: q.volume?.[i] ?? 0,
    })
  }
  return {
    candles,
    meta: {
      symbol: r.meta?.symbol,
      name: r.meta?.shortName,
      currency: r.meta?.currency,
      marketPrice: r.meta?.regularMarketPrice,
      marketTime: r.meta?.regularMarketTime,
      dayHigh: r.meta?.regularMarketDayHigh,
      dayLow: r.meta?.regularMarketDayLow,
      previousClose: r.meta?.previousClose,
    },
  }
}

// ---------------------------------------------------------------------------
// ادغام قیمت spot لحظه‌ای با کندل‌های Yahoo (رفع تأخیر داده به < ۵ دقیقه).
// منطق:
//   - آفستِ (futures - spot) از آخرین کندلِ Yahoo محاسبه می‌شود (~۵.۵$).
//   - قیمتِ معادلِ futures از spot ساخته می‌شود: spotEq = spot + offset.
//   - اگر آخرین کندل مربوط به همان بازهٔ ۱۵دقیقه‌ایِ «الان» باشد → close/high/low
//     همان کندل با spotEq به‌روز می‌شود (کندلِ در حال شکل‌گیری).
//   - در غیر این صورت یک کندلِ جدیدِ سبک برای بازهٔ جاری اضافه می‌شود.
// این کار تأخیر مؤثرِ «آخرین قیمت» را از ~۱۳ دقیقه به < ۱ دقیقه می‌رساند.
// ---------------------------------------------------------------------------
function mergeSpot(candles: Candle[], spot: SpotPrice | null, intervalSec = 900): { candles: Candle[]; spotUsed: boolean; effectiveDelaySec: number } {
  if (!spot || !candles.length || !isFinite(spot.price)) {
    const lastT = candles.length ? candles[candles.length - 1].time : 0
    return { candles, spotUsed: false, effectiveDelaySec: lastT ? Math.round(Date.now() / 1000 - lastT) : 0 }
  }
  const out = candles.slice()
  const last = out[out.length - 1]
  // آفست futures−spot از آخرین کندل واقعی
  const offset = last.close - spot.price > -50 && last.close - spot.price < 50 ? (last.close - spot.price) : 0
  const spotEq = spot.price + offset
  const nowSec = Math.floor(Date.now() / 1000)
  const curBucketStart = Math.floor(nowSec / intervalSec) * intervalSec

  if (last.time >= curBucketStart) {
    // آخرین کندل همان بازهٔ جاری است → به‌روزرسانی close/high/low
    const updated: Candle = {
      ...last,
      close: spotEq,
      high: Math.max(last.high, spotEq),
      low: Math.min(last.low, spotEq),
    }
    out[out.length - 1] = updated
  } else {
    // بازهٔ جدید شروع شده → افزودن کندلِ سبکِ جاری
    out.push({ time: curBucketStart, open: last.close, high: Math.max(last.close, spotEq), low: Math.min(last.close, spotEq), close: spotEq, volume: 0 })
  }
  return { candles: out, spotUsed: true, effectiveDelaySec: spot.ageSec }
}

// قیمت spot لحظه‌ای (تأخیر < چند ثانیه)
app.get('/api/spot', async (c) => {
  try {
    const s = await getSpotGold()
    return c.json({ ok: true, ...s })
  } catch (e: any) {
    return c.json({ ok: false, error: e.message }, 502)
  }
})

// خام: کندل‌ها برای رسم چارت (با ادغام spot لحظه‌ای)
app.get('/api/candles', async (c) => {
  const interval = c.req.query('interval') || '15m'
  const range = c.req.query('range') || '1mo'
  const intervalSec = interval === '15m' ? 900 : interval === '1h' ? 3600 : interval === '5m' ? 300 : 900
  try {
    const { candles, meta } = await fetchGold(interval, range)
    // spot را موازی می‌گیریم و در صورت موفقیت کندل جاری را به‌روز می‌کنیم
    let spot: SpotPrice | null = null
    try { spot = await getSpotGold() } catch {}
    const merged = mergeSpot(candles, spot, intervalSec)
    if (spot) { meta.marketPrice = spot.price + (merged.candles[merged.candles.length - 1].close - spot.price >= -50 ? 0 : 0) }
    return c.json({
      ok: true, meta, count: merged.candles.length, candles: merged.candles,
      spot: spot ? { price: spot.price, ageSec: spot.ageSec, source: spot.source } : null,
      effectiveDelaySec: merged.effectiveDelaySec,
    })
  } catch (e: any) {
    return c.json({ ok: false, error: e.message }, 502)
  }
})

// تحلیل کامل: سیگنال + S/R + سناریوی شکست
app.get('/api/analysis', async (c) => {
  const interval = c.req.query('interval') || '15m'
  // برای اندیکاتورها به تاریخچه کافی نیاز داریم (EMA200) → حداقل 1 ماه
  const range = c.req.query('range') || '1mo'
  try {
    const { candles, meta } = await fetchGold(interval, range)
    if (candles.length < 220) {
      return c.json({ ok: false, error: 'داده کافی برای تحلیل نیست (نیاز به حداقل ۲۲۰ کندل)' }, 400)
    }
    // ادغام spot لحظه‌ای برای رفع تأخیر
    let spot: SpotPrice | null = null
    try { spot = await getSpotGold() } catch {}
    const merged = mergeSpot(candles, spot, 900)
    const useCandles = merged.candles
    const result = analyze(useCandles)
    // فقط کندل‌های اخیر برای چارت (سبک‌تر)
    const recent = useCandles.slice(-300)
    return c.json({
      ok: true,
      meta,
      lastUpdate: new Date().toISOString(),
      lastCandleTime: useCandles[useCandles.length - 1].time,
      totalCandles: useCandles.length,
      spot: spot ? { price: spot.price, ageSec: spot.ageSec, source: spot.source } : null,
      effectiveDelaySec: merged.effectiveDelaySec,
      analysis: result,
      chart: recent.map(k => ({ t: k.time, o: k.open, h: k.high, l: k.low, c: k.close })),
    })
  } catch (e: any) {
    return c.json({ ok: false, error: e.message }, 502)
  }
})

// --- تحلیل چند-تایم‌فریمی H1/H4/D1 و هم‌راستایی روند (User Note #2) ---
app.get('/api/mtf', async (c) => {
  try {
    const mtf = await getMTF()
    return c.json({ ok: true, ...mtf, lastUpdate: new Date().toISOString() })
  } catch (e: any) {
    return c.json({ ok: false, error: e.message }, 502)
  }
})

// --- منابع داده خارج از OHLCV: DXY + بازده اوراق (User Note #3) ---
app.get('/api/intermarket', async (c) => {
  try {
    const im = await getIntermarket()
    return c.json({ ok: true, ...im, lastUpdate: new Date().toISOString() })
  } catch (e: any) {
    return c.json({ ok: false, error: e.message }, 502)
  }
})

// --- تقویم اخبار اقتصادی USD (User Note #3) ---
app.get('/api/news', async (c) => {
  try {
    const news = await getNews(c.env)
    return c.json({ ok: true, ...news, lastUpdate: new Date().toISOString() })
  } catch (e: any) {
    return c.json({ ok: false, error: e.message }, 502)
  }
})

// --- context بنیادی ترکیبی (MTF + بین‌بازاری + اخبار) در یک فراخوان ---
app.get('/api/context', async (c) => {
  const [mtf, im, news] = await Promise.allSettled([getMTF(), getIntermarket(), getNews(c.env)])
  return c.json({
    ok: true,
    lastUpdate: new Date().toISOString(),
    mtf: mtf.status === 'fulfilled' ? mtf.value : { error: (mtf as any).reason?.message },
    intermarket: im.status === 'fulfilled' ? im.value : { error: (im as any).reason?.message },
    news: news.status === 'fulfilled' ? news.value : { error: (news as any).reason?.message },
  })
})

// health
app.get('/api/health', (c) => c.json({ ok: true, service: 'xauusd-live-tool', time: Date.now() }))

// favicon (طلایی ساده به‌صورت SVG) — جلوگیری از خطای 500
app.get('/favicon.ico', (c) => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="14" fill="#f59e0b"/><text x="16" y="22" font-size="16" text-anchor="middle" fill="#0f172a" font-family="Arial" font-weight="bold">A</text></svg>`
  return c.body(svg, 200, { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=86400' })
})

// صفحه اصلی
app.get('/', (c) => {
  return c.html(PAGE)
})

const PAGE = `<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>XAUUSD Live — ابزار تحلیل زنده طلا</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.1/dist/chartjs-adapter-luxon.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-chart-financial@0.2.1/dist/chartjs-chart-financial.min.js"></script>
  <!-- onnxruntime-web: اجرای واقعی مدل ربات در مرورگر (User Note #1) -->
  <script src="https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/ort.min.js"></script>
  <link href="/static/style.css" rel="stylesheet">
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <div id="app" class="max-w-6xl mx-auto p-4"></div>
  <!-- ماژول کلاینت مدل ONNX (باندل esbuild: features + indicators + inference) -->
  <script type="module" src="/static/browser-signal.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>`

export default app
