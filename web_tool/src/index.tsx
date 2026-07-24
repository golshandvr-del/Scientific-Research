import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { serveStatic } from 'hono/cloudflare-workers'
import type { Candle } from './indicators'
import { analyze } from './signal'
import { evaluateTrade, type OpenTrade, type Side } from './trade_manager'
import { getMTF, getIntermarket, getNews, getSpotGold, yahooCandles, getLiveQuote, type SpotPrice } from './external'
import { decide, assetSpec } from './router'
import type { RouterDecision } from './router'
import { decideEurusd, decideEurusdM15 } from './eurusd_router'
import { decideGoldM5, manageGoldM5Scalp } from './gold_m5_router'
import { decideGoldM30, decideGoldM30TrendLine } from './gold_m30_router'
import { decideGoldH1, decideGoldH4, decideGoldD1 } from './gold_htf_router'
import { trendLineDecision, TREND_LINE_CFG } from './gold_trend_line'
import { channelDecision, CHANNEL_CFG } from './gold_channel'
import { probeSecondaryLayers } from './secondary_layers'
import { cachedFetch } from './cache'
import { fetchWithTimeout } from './fast_fetch'

const app = new Hono()

app.use('/api/*', cors())
app.use('/static/*', serveStatic({ root: './public' }))
// نسخهٔ وبِ اپلیکیشنِ APK زیرِ /static/app/ سرو می‌شود (مسیرِ استاتیکِ کارآمد).
// میان‌بر: /app ⇒ ری‌دایرکت به صفحهٔ اپ.
app.get('/app', (c) => c.redirect('/static/app/index.html'))

// ---------------------------------------------------------------------------
// دریافت داده زنده طلا از Yahoo Finance (GC=F = طلای آتی COMEX، بدون نیاز به کلید)
// symbol پیش‌فرض GC=F است؛ interval و range قابل تنظیم.
// ---------------------------------------------------------------------------
// هستهٔ fetchِ طلا (بدونِ کش). خروجی دقیقاً مثلِ قبل.
async function _fetchGoldRaw(interval: string, range: string): Promise<{ candles: Candle[]; meta: any }> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=${interval}&range=${range}`
  const res = await fetchWithTimeout(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept': 'application/json',
    },
    cf: { cacheTtl: 30, cacheEverything: true } as any,
  }, 6000)
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

// fetchGold — نسخهٔ کش‌دار. همهٔ کارت‌های طلا (M1/M5/M15/M30/H1/H4/D1) که یک
// (interval,range) می‌خواهند، از یک fetch مشترک تغذیه می‌شوند (de-dup) و رفرش‌های
// بعدی از کش/SWR می‌آیند ⇒ بارِ Yahoo روی گوشی ۹۰٪+ کم می‌شود. خروجی مثلِ قبل.
async function fetchGold(interval: string, range: string): Promise<{ candles: Candle[]; meta: any }> {
  return cachedFetch(`gold:${interval}:${range}`, () => _fetchGoldRaw(interval, range),
    { freshMs: 30_000, staleMs: 600_000 })
}

// ---------------------------------------------------------------------------
// تجمیعِ کندل‌ها به تایم‌فریمِ بزرگ‌تر (مثلِ H1×4 ⇒ H4). Yahoo تایم‌فریمِ ۴ساعته را
// مستقیم نمی‌دهد؛ پس از کندل‌های H1 آن را می‌سازیم. گروه‌بندی بر اساسِ مرزِ ساعتیِ
// UTC (۰/۴/۸/۱۲/۱۶/۲۰) انجام می‌شود تا کندل‌ها با استانداردِ متعارفِ H4 هم‌تراز باشند.
// O=اولین open ، H=بیشینهٔ high ، L=کمینهٔ low ، C=آخرین close ، V=جمعِ volume.
// ---------------------------------------------------------------------------
function aggregateCandles(candles: Candle[], factorHours: number): Candle[] {
  if (!candles.length) return []
  const bucketSec = factorHours * 3600
  const out: Candle[] = []
  let cur: Candle | null = null
  let curBucket = -1
  for (const k of candles) {
    const b = Math.floor(k.time / bucketSec)
    if (b !== curBucket) {
      if (cur) out.push(cur)
      cur = { time: b * bucketSec, open: k.open, high: k.high, low: k.low, close: k.close, volume: k.volume || 0 }
      curBucket = b
    } else if (cur) {
      cur.high = Math.max(cur.high, k.high)
      cur.low = Math.min(cur.low, k.low)
      cur.close = k.close
      cur.volume = (cur.volume || 0) + (k.volume || 0)
    }
  }
  if (cur) out.push(cur)
  return out
}

// ---------------------------------------------------------------------------
// رفعِ باگِ اصلی «اختلاف ~۲۰ دلاری قیمت»:
//   داده کندل از Yahoo GC=F (طلای آتی COMEX) می‌آید که به‌طور ساختاری چند تا چند‌ده
//   دلار بالاتر از XAU/USD spot (مرجع TradingView/OANDA) است. قبلاً فقط «آخرین کندل»
//   با spot تنظیم می‌شد و بقیهٔ چارت + همهٔ اندیکاتورها/سطوح S/R روی مقیاس futures
//   می‌ماندند → کاربر اختلاف بزرگ می‌دید.
//
// راه‌حل صحیح (rebase کامل به مقیاس spot):
//   ۱) آفستِ پایدار = میانگینِ (close_futures − spot) روی چند کندل اخیر همتراز زمانی.
//      (اگر spot تازه است، از خودِ آخرین کندل هم استفاده می‌شود.)
//   ۲) این آفست از open/high/low/close «همهٔ کندل‌ها» کم می‌شود → کل سری روی مقیاس spot.
//   ۳) کندلِ در حال شکل‌گیری با قیمت spot لحظه‌ای به‌روز/ساخته می‌شود.
//   نتیجه: قیمت نمایشی، سطوح حمایت/مقاومت، و سیگنال همگی روی مقیاس XAUUSD spot
//   و سازگار با TradingView خواهند بود.
// ---------------------------------------------------------------------------
function rebaseFuturesToSpot(candles: Candle[], spot: SpotPrice | null, intervalSec = 900): {
  candles: Candle[]; spotUsed: boolean; effectiveDelaySec: number; offset: number
} {
  const lastT0 = candles.length ? candles[candles.length - 1].time : 0
  if (!spot || !candles.length || !isFinite(spot.price)) {
    return { candles, spotUsed: false, effectiveDelaySec: lastT0 ? Math.round(Date.now() / 1000 - lastT0) : 0, offset: 0 }
  }

  // آفستِ پایدار futures−spot: میانگینِ close آخرین N کندل منهای spot فعلی.
  // (spot لحظه‌ای است؛ close چند کندل اخیر مبنای پایدارِ سطحِ futures را می‌دهد.)
  const N = Math.min(4, candles.length)
  let sum = 0
  for (let i = candles.length - N; i < candles.length; i++) sum += candles[i].close
  let offset = sum / N - spot.price
  // محدودسازی امن: آفست معقول طلا معمولاً بین -60..+60 دلار است.
  if (!isFinite(offset) || Math.abs(offset) > 80) offset = 0

  // rebase کل سری به مقیاس spot
  const rebased: Candle[] = candles.map(k => ({
    time: k.time,
    open: k.open - offset,
    high: k.high - offset,
    low: k.low - offset,
    close: k.close - offset,
    volume: k.volume,
  }))

  // کندلِ در حال شکل‌گیری را با spot لحظه‌ای دقیق‌تر می‌کنیم
  const nowSec = Math.floor(Date.now() / 1000)
  const curBucketStart = Math.floor(nowSec / intervalSec) * intervalSec
  const last = rebased[rebased.length - 1]
  if (last.time >= curBucketStart) {
    rebased[rebased.length - 1] = {
      ...last,
      close: spot.price,
      high: Math.max(last.high, spot.price),
      low: Math.min(last.low, spot.price),
    }
  } else {
    rebased.push({
      time: curBucketStart,
      open: last.close, close: spot.price,
      high: Math.max(last.close, spot.price),
      low: Math.min(last.close, spot.price),
      volume: 0,
    })
  }
  return { candles: rebased, spotUsed: true, effectiveDelaySec: spot.ageSec, offset }
}

// ---------------------------------------------------------------------------
// به‌روزکردنِ کندلِ جاریِ هر دارایی (غیرِ طلا) با قیمتِ زندهٔ Yahoo.
// پاسخ به User Note (نکتهٔ اول): «قیمتِ سه ارزِ دیگر با قیمتِ لحظه‌ای فرق می‌کند».
// علت: کندلِ 15m چند دقیقه تأخیر دارد؛ اینجا کندلِ در حالِ شکل‌گیری با
// regularMarketPrice (تأخیر < ۲ دقیقه) به‌روز می‌شود تا سطوح/سیگنال روی قیمتِ
// واقعیِ لحظه‌ای محاسبه شوند (منطقِ سبک‌ترِ rebaseِ طلا).
// ---------------------------------------------------------------------------
function mergeLiveQuote(candles: Candle[], livePrice: number | null, intervalSec = 900): {
  candles: Candle[]; livePriceUsed: boolean
} {
  if (!candles.length || livePrice == null || !isFinite(livePrice)) {
    return { candles, livePriceUsed: false }
  }
  const nowSec = Math.floor(Date.now() / 1000)
  const curBucketStart = Math.floor(nowSec / intervalSec) * intervalSec
  const out = candles.slice()
  const last = out[out.length - 1]
  if (last.time >= curBucketStart) {
    // کندلِ جاری در حالِ شکل‌گیری است → close را با قیمتِ زنده به‌روز کن
    out[out.length - 1] = {
      ...last,
      close: livePrice,
      high: Math.max(last.high, livePrice),
      low: Math.min(last.low, livePrice),
    }
  } else {
    // کندلِ جدیدِ در حالِ شکل‌گیری بساز
    out.push({
      time: curBucketStart,
      open: last.close, close: livePrice,
      high: Math.max(last.close, livePrice),
      low: Math.min(last.close, livePrice),
      volume: 0,
    })
  }
  return { candles: out, livePriceUsed: true }
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
    // spot را موازی می‌گیریم و کل سری را به مقیاس spot می‌آوریم
    let spot: SpotPrice | null = null
    try { spot = await getSpotGold() } catch {}
    const merged = rebaseFuturesToSpot(candles, spot, intervalSec)
    // قیمت نمایشیِ متا نیز روی مقیاس spot (سازگار با TradingView)
    if (spot) { meta.marketPrice = spot.price; meta.priceScale = 'spot'; meta.futuresOffset = Number(merged.offset.toFixed(2)) }
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
    // rebase کل سری به مقیاس spot (رفع باگ اختلاف قیمت) — همهٔ اندیکاتورها/سطوح روی spot
    let spot: SpotPrice | null = null
    try { spot = await getSpotGold() } catch {}
    const merged = rebaseFuturesToSpot(candles, spot, 900)
    const useCandles = merged.candles
    if (spot) { meta.marketPrice = spot.price; meta.priceScale = 'spot'; meta.futuresOffset = Number(merged.offset.toFixed(2)) }
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

// ---------------------------------------------------------------------------
// مدیریت معاملهٔ باز کاربر (Trade Advisor) — پاسخ به User Note
// کاربر معاملهٔ باز خود (side/entry/tp/sl) را می‌فرستد؛ سرور با تحلیل زندهٔ بازار
// (همان موتور S14 + S/R) توصیه‌های مدیریتی برمی‌گرداند. کاملاً stateless است؛
// خودِ معامله در localStorage مرورگر ذخیره می‌شود (با رفرش از دست نمی‌رود).
// ---------------------------------------------------------------------------
app.post('/api/trade/advice', async (c) => {
  try {
    const body = await c.req.json().catch(() => null) as any
    if (!body || !body.trade) return c.json({ ok: false, error: 'داده‌ی معامله ارسال نشده' }, 400)
    const tr = body.trade
    const side = (tr.side === 'short' ? 'short' : 'long') as Side
    const entry = Number(tr.entry), tp = Number(tr.tp), sl = Number(tr.sl)
    if (![entry, tp, sl].every(x => isFinite(x) && x > 0)) {
      return c.json({ ok: false, error: 'ورود/TP/SL نامعتبر است' }, 400)
    }
    // اعتبارسنجی منطقی جهت TP/SL نسبت به ورود
    if (side === 'long' && !(tp > entry && sl < entry)) {
      return c.json({ ok: false, error: 'برای معاملهٔ خرید باید TP بالاتر از ورود و SL پایین‌تر از ورود باشد.' }, 400)
    }
    if (side === 'short' && !(tp < entry && sl > entry)) {
      return c.json({ ok: false, error: 'برای معاملهٔ فروش باید TP پایین‌تر از ورود و SL بالاتر از ورود باشد.' }, 400)
    }

    // دارایی هدف (پیش‌فرض طلا برای سازگاری با نسخهٔ قبل)
    const assetId = (body.asset ? String(body.asset).toUpperCase() : 'XAUUSD')
    const meta_asset = ASSETS.find(x => x.id === assetId) || ASSETS[0]

    // داده‌ی زنده + تحلیل مخصوص همان دارایی
    let a
    if (meta_asset.isGold) {
      const { candles } = await fetchGold('15m', '1mo')
      if (candles.length < 220) return c.json({ ok: false, error: 'داده کافی برای تحلیل نیست' }, 400)
      let spot: SpotPrice | null = null
      try { spot = await getSpotGold() } catch {}
      const merged = rebaseFuturesToSpot(candles, spot, 900)
      a = analyze(merged.candles)
    } else {
      const { candles } = await yahooCandles(meta_asset.symbol, '15m', '1mo')
      if (candles.length < 220) return c.json({ ok: false, error: 'داده کافی برای تحلیل نیست' }, 400)
      a = analyze(candles)
    }

    // managePlan: پلنِ مدیریتِ لایه‌ای که سیگنال را داده بود (از sourceLayer.manage).
    // فرانت‌اند هنگام ثبتِ معامله آن را ذخیره و اینجا برمی‌گرداند تا trade_manager دقیقاً
    // همان سبکِ مدیریتِ همان لایه را اجرا کند (TP/SL متحرکِ هم‌خوان با لایه — User Note #3).
    const managePlan = (tr.managePlan && typeof tr.managePlan === 'object') ? tr.managePlan : undefined
    const barsHeld = (typeof tr.barsHeld === 'number' && tr.barsHeld >= 0) ? tr.barsHeld : undefined
    const trade: OpenTrade = { side, entry, tp, sl, openedAt: tr.openedAt, barsHeld, managePlan }
    const modelProbPct = typeof body.modelProbPct === 'number' ? body.modelProbPct : undefined
    const status = evaluateTrade(trade, a, modelProbPct)

    return c.json({
      ok: true,
      lastUpdate: new Date().toISOString(),
      price: a.price,
      market: {
        // نکتهٔ طراحی (User Note): سطوحِ حمایت/مقاومت و سناریوهای شکست از این payload
        // حذف شدند؛ هیچ استراتژیِ واقعیِ پروژه از S/R استفاده نمی‌کند و UI آن‌ها را نمایش نمی‌داد.
        trend: a.trend, atr: a.atr, rsi14: a.rsi14, adx: a.adx, macdHist: a.macdHist,
        vwap: a.vwap, ema50: a.ema50, ema200: a.ema200, regimeOk: a.regimeOk,
      },
      status,
    })
  } catch (e: any) {
    return c.json({ ok: false, error: e.message }, 502)
  }
})

// --- مدیریتِ لحظه‌ایِ اسکالپِ M5 طلا (User Note) ---
// بدونِ TP/SL/حجم. خروجی فقط: take_profit / wrong / hold + پیامِ فارسی.
// ورودی: { action: 'BUY'|'SELL', refPrice: number }  (قیمتِ ورودِ کاربر)
app.post('/api/scalp/manage', async (c) => {
  try {
    const body = await c.req.json().catch(() => null) as any
    if (!body) return c.json({ ok: false, error: 'داده ارسال نشده' }, 400)
    const action = (body.action === 'SELL' ? 'SELL' : 'BUY') as 'BUY' | 'SELL'
    const refPrice = Number(body.refPrice)
    if (!isFinite(refPrice) || refPrice <= 0) {
      return c.json({ ok: false, error: 'قیمتِ ورود (refPrice) نامعتبر است' }, 400)
    }
    // آستانه‌های پنهانِ مخصوصِ لایه (اگر فرانت‌اند فرستاد) — تا هر لایه TP/SL خودش را داشته باشد.
    const tpPip = Number(body.tpPip); const slPip = Number(body.slPip)

    // دادهٔ زندهٔ M5 طلا (هم‌راستا با decideGoldM5)
    const { candles } = await fetchGold('5m', '5d')
    if (candles.length < 120) return c.json({ ok: false, error: 'داده کافی برای مدیریت نیست' }, 400)
    let spot: SpotPrice | null = null
    try { spot = await getSpotGold() } catch {}
    const merged = rebaseFuturesToSpot(candles, spot, 300)
    const close = merged.candles.map(k => k.close)
    const livePrice = spot?.price ?? close[close.length - 1]

    const res = manageGoldM5Scalp({ action, refPrice, livePrice, close,
      tpPip: isFinite(tpPip) && tpPip > 0 ? tpPip : undefined,
      slPip: isFinite(slPip) && slPip > 0 ? slPip : undefined })

    return c.json({
      ok: true,
      lastUpdate: new Date().toISOString(),
      livePrice: Number(livePrice.toFixed(2)),
      state: res.state,       // 'take_profit' | 'wrong' | 'hold'
      message: res.message,   // پیامِ فارسیِ لحظه‌ای (فقط وقتی take_profit/wrong)
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

// ---------------------------------------------------------------------------
// دستیارِ تصمیمِ چند-دارایی + ماشینِ حالتِ ۴-وضعیتی (PARADIGM v2 / User Note 2)
// ---------------------------------------------------------------------------
// rebase به spot می‌آید؛ بقیه مستقیماً از Yahoo. منطقِ تصمیم در router.ts.
// طبقِ User Note: سایت بخش‌های داراییِ دارای لبهٔ اثبات‌شده را نمایش می‌دهد.
// همهٔ اعداد با «هزینهٔ واقعیِ حسابِ کاربر» (User Note 2) بازآزمایی شده‌اند:
//   طلا اسپرد ۰.۴۰$ (۴ pip)/کمیسیون ۰ ، EURUSD اسپرد ۱.۵ pip/کمیسیون ۰.
//   • XAUUSD (M15) — موتورِ برندهٔ S67 (+۳۰٬۴۹۰$)، منطقِ decide()ِ عمومی.
//   • XAUUSD (M5)  — لایهٔ اسکالپِ نوِ S79 (Trend-Pullback، +۴٬۲۵۶$، منطقِ decideGoldM5).
//   • XAUUSD (M30) — لایهٔ نوسانیِ نوِ S81 (Swing Trend-Pullback، +۱۴٬۳۲۷$، منطقِ decideGoldM30).
//                    جایگزینِ لایهٔ H1/S80 شد (corr(M30,H1)=+۰.۷۵؛ M30 قوی‌تر).
//   • EURUSD (M15) — استراتژیِ نوِ S73 (Session-Open Drift، +۹٬۲۲۳$، منطقِ decideEurusd).
// DXY و AUDUSD حذف شدند چون هیچ لبهٔ سوددهی روی آن‌ها یافت نشد (S69–S72 زیان‌ده).
//
// 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است، نه Win-Rate.
// تعریفِ رسمیِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
// سودِ خالصِ کل (هزینهٔ واقعی) = (S67+S79+S81) + S73 = +۴۹٬۰۷۳$ + +۹٬۲۲۳$ = +۵۸٬۲۹۵$.
//
// فیلدِ `layer`: 'swing' = نوسانی/میان‌مدت (M15) ، 'scalp' = اسکالپِ کوتاه (M5) ،
//   'swing-m30' = نوسان‌گیریِ M30 (S81 — نگهداریِ تا ۳ روز، R:R بالا).
// این برچسب در UI به کاربر نشان داده می‌شود تا بداند پیشنهاد از کدام سبک آمده است.
// هر کارت داده/منطق/localStorageِ مستقل دارد ⇒ کارت‌ها هیچ تداخلی با هم ندارند.
// فیلدِ `layer`: 'swing'=M15 ، 'scalp'=M5 ، 'swing-m30'=M30 ، 'placeholder'=قالبِ خام
//   (تایم‌فریمی که هنوز استراتژیِ اثبات‌شده‌ای ندارد — فقط داده/قیمت را نشان می‌دهد و
//    صریحاً می‌گوید «در دستِ تحقیق»؛ آماده برای گسترشِ آینده بدونِ تغییرِ معماری).
// فیلدِ `tf`: تایم‌فریمِ Yahoo برای دریافتِ کندل (5m/15m/30m/1m). فقط برای کارت‌های
//   غیرطلا کاربرد دارد (طلا تایم‌فریمش را از id می‌گیرد).
const ASSETS: { id: string; name: string; symbol: string; isGold: boolean; decimals: number; layer: 'swing' | 'scalp' | 'swing-m30' | 'placeholder' | 'htf'; tf?: string }[] = [
  { id: 'XAUUSD',     name: 'طلا / دلار — نوسانی (M15)',   symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'swing' },
  { id: 'XAUUSD-M5',  name: 'طلا / دلار — اسکالپ (M5)',    symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'scalp' },
  // XAUUSD-M30: در نشستِ S215 با لایهٔ «خطِ روندِ Al Brooks» (فصلِ ۱۳) دوباره فعال شد.
  //   قبلاً S81 داشت که در S163 حذف شد؛ حالا لبهٔ trend-lineِ اثبات‌شده (+$5,599، مستقل).
  { id: 'XAUUSD-M30', name: 'طلا / دلار — میان‌مدت (M30)',  symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'swing-m30' },
  // --- تایم‌فریم‌های بالای طلا (درخواستِ User Note) — هر کارت منطقِ مستقلِ خودش را دارد ---
  //   H1/H4/D1 فعلاً در «حالتِ تحقیقِ فعال» هستند (بدونِ سیگنالِ ورودِ خام تا کشفِ لایهٔ
  //   اثبات‌شده) اما تحلیلِ روند/رژیمِ مخصوصِ همان تایم‌فریم را نمایش می‌دهند. منطق در
  //   gold_htf_router.ts (decideGoldH1/H4/D1) — کاملاً مستقل و ماژولار.
  { id: 'XAUUSD-H1',  name: 'طلا / دلار — یک‌ساعته (H1)',  symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  { id: 'XAUUSD-H4',  name: 'طلا / دلار — چهارساعته (H4)', symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  { id: 'XAUUSD-D1',  name: 'طلا / دلار — روزانه (D1)',    symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  // ⛔ S81 (XAUUSD-M30 / Swing Trend-Pullback) در نشستِ S163 طبقِ تصمیمِ صریحِ کاربر
  //    کاملاً حذف شد: WR=۲۸٪ داشت و رساندنِ آن به WR≥۴۰٪ سود را −۹٬۵۳۱$ نابود می‌کرد.
  //    کاربر خواست هر لایه‌ای که برای WR≥۴۰ ضررده می‌شود حذف شود. (روتر decideGoldM30 باقی
  //    مانده اما دیگر فراخوانی نمی‌شود.) رجوع: results/EnforceWR40_RemoveS81_NetProfit_218739.md
  // EURUSD: در S187–S189 لایهٔ S73 به تایم‌فریمِ M5 ارتقا یافت (net +$8,911/WR ۵۹.۶٪ روی M5
  //   در برابرِ +$4,224/۵۵.۳٪ روی M15؛ گیتِ سختِ کامل + قانونِ همپوشانی ⇒ ارتقا نه افزودن).
  //   منبعِ کندل حالا 5m است؛ منطقِ decideEurusd (ساعتِ ۰ UTC + pullback ۴-کندلی) دست‌نخورده.
  { id: 'EURUSD',     name: 'یورو / دلار — اسکالپ (M5)',   symbol: 'EURUSD=X', isGold: false, decimals: 5, layer: 'scalp',  tf: '5m'  },
  // --- تفکیکِ تایم‌فریمِ EURUSD (درخواستِ کاربر) — هم‌ساختار با طلا ---
  //   این کارت‌ها فعلاً استراتژیِ اثبات‌شدهٔ اختصاصیِ خود را ندارند ⇒ قالبِ خام (placeholder).
  //   داده/قیمتِ زنده را نشان می‌دهند و آماده‌ی افزودنِ منطق در تحقیقِ آینده‌اند (هر کارت مستقل).
  { id: 'EURUSD-M15', name: 'یورو / دلار — نوسانی (M15)',  symbol: 'EURUSD=X', isGold: false, decimals: 5, layer: 'scalp', tf: '15m' },
  { id: 'EURUSD-M30', name: 'یورو / دلار — میان‌مدت (M30)', symbol: 'EURUSD=X', isGold: false, decimals: 5, layer: 'placeholder', tf: '30m' },
  { id: 'EURUSD-M1',  name: 'یورو / دلار — ریز-اسکالپ (M1)', symbol: 'EURUSD=X', isGold: false, decimals: 5, layer: 'placeholder', tf: '1m' },
]

// پیوستِ لایه‌های ثانویهٔ فعال به یک تصمیم (بدونِ تغییرِ منطقِ برندهٔ آن).
// otherLayers فقط برای «نمایشِ collapsed» در فرانت‌اند است (پاسخِ User Note).
function attachSecondary(dec: any, ctx: Parameters<typeof probeSecondaryLayers>[0]) {
  try {
    const others = probeSecondaryLayers(ctx)
    if (others.length) dec.otherLayers = others
  } catch { /* کاوش اختیاری است؛ خطای آن نباید سیگنالِ اصلی را خراب کند */ }
  return dec
}

// تصمیمِ یک دارایی: کندلِ زنده → analyze → decide (۴-حالته).
async function decideAsset(a: typeof ASSETS[number], capital = 10000, riskPct = 1.0) {
  if (a.isGold) {
    // --- نگاشتِ ماژولارِ تایم‌فریمِ طلا → (interval, range, gapSec) ---
    // هر کارتِ طلا تایم‌فریمِ مستقلِ خودش را از این جدول می‌گیرد. افزودنِ تایم‌فریمِ
    // تازه فقط یک ردیف است و بقیهٔ کارت‌ها را دست نمی‌زند (ماژولار).
    // نکته: Yahoo برای interval=30m/1h فقط range محدود می‌دهد؛ مقادیرِ امن انتخاب شده.
    const GOLD_TF: Record<string, { interval: string; range: string; gap: number }> = {
      'XAUUSD':    { interval: '15m', range: '1mo', gap: 900 },
      'XAUUSD-M5': { interval: '5m',  range: '5d',  gap: 300 },
      'XAUUSD-M30':{ interval: '30m', range: '1mo', gap: 1800 },
      'XAUUSD-H1': { interval: '1h',  range: '3mo', gap: 3600 },
      'XAUUSD-H4': { interval: '1h',  range: '1y',  gap: 3600 },  // H4 از تجمیعِ H1 ساخته می‌شود
      'XAUUSD-D1': { interval: '1d',  range: '2y',  gap: 86400 },
    }
    const tfc = GOLD_TF[a.id] || GOLD_TF['XAUUSD']
    const { candles: rawCandles } = await fetchGold(tfc.interval, tfc.range)
    // H4: Yahoo تایم‌فریمِ ۴ساعته را مستقیم نمی‌دهد ⇒ از تجمیعِ کندل‌های H1 می‌سازیم.
    const candles = a.id === 'XAUUSD-H4' ? aggregateCandles(rawCandles, 4) : rawCandles
    // آستانهٔ حداقلِ کندل بسته به تایم‌فریم (D1/H4 داده کمتری دارند، اما برای EMA200 کافی است).
    const minBars = a.id === 'XAUUSD-D1' ? 60 : (a.id === 'XAUUSD-H4' ? 60 : 220)
    if (candles.length < minBars) throw new Error('داده کافی برای تحلیل نیست')
    let spot: SpotPrice | null = null
    try { spot = await getSpotGold() } catch {}
    const merged = rebaseFuturesToSpot(candles, spot, tfc.gap)
    const useCandles = merged.candles
    const result = analyze(useCandles)
    // هر تایم‌فریم منطقِ decide مخصوصِ خودش را دارد (کاملاً مستقل — ماژولار):
    //   M5→S79 ، M30→S81 ، M15→S67 (زمان-محورها) ، H1/H4/D1→gold_htf_router (حالتِ تحقیقِ فعال).
    // ساعت/روز/زمانِ کندلِ جاری — برای لایه‌های زمان-محورِ روی طلا M15 (S139/S140/S141).
    const goldUtcHour = new Date(useCandles[useCandles.length - 1].time * 1000).getUTCHours()
    const goldUtcDay = new Date(useCandles[useCandles.length - 1].time * 1000).getUTCDay()
    const goldTimes = useCandles.map(k => k.time)
    const closes = useCandles.map(k => k.close)
    let dec
    if (a.id === 'XAUUSD-M5')      dec = decideGoldM5(result, closes, capital, riskPct,
                                     useCandles.map(k => k.open), useCandles.map(k => k.high),
                                     useCandles.map(k => k.low), goldTimes)
    else if (a.id === 'XAUUSD-M30') dec = decideGoldM30TrendLine(result, closes, capital, riskPct,
                                     useCandles.map(k => k.open), useCandles.map(k => k.high), useCandles.map(k => k.low))
    else if (a.id === 'XAUUSD-H1')  dec = decideGoldH1(result, closes, capital, riskPct,
                                     useCandles.map(k => k.open), useCandles.map(k => k.high), useCandles.map(k => k.low))
    else if (a.id === 'XAUUSD-H4')  dec = decideGoldH4(result, closes, capital, riskPct,
                                     useCandles.map(k => k.open), useCandles.map(k => k.high), useCandles.map(k => k.low))
    else if (a.id === 'XAUUSD-D1')  dec = decideGoldD1(result, closes, capital, riskPct)
    else {
      // کارتِ M15 طلا (id=XAUUSD): لایه‌های زمان-محور/ML عمومی (S67/S132/S168…) اولویت دارند.
      dec = decide(result, closes, capital, riskPct, assetSpec('XAUUSD'), useCandles.map(k => k.high), useCandles.map(k => k.low), goldUtcHour, goldUtcDay, goldTimes, useCandles.map(k => k.open))
      // لایهٔ مکملِ مستقلِ S215 (خطِ روندِ Al Brooks): فقط وقتی لایه‌های اصلی خنثی‌اند
      // بررسی می‌شود (بدونِ تداخل). سهمِ مستقلِ M15 در بک‌تستِ S215b = +$2,714 (WR ۵۷.۱٪، WF-4/4).
      if (dec.state === 'NEUTRAL') {
        const tl = trendLineDecision(TREND_LINE_CFG['XAUUSD-M15'], result,
          useCandles.map(k => k.open), useCandles.map(k => k.high), useCandles.map(k => k.low), closes, capital, riskPct)
        if (tl.state === 'ENTRY' || tl.state === 'APPROACHING') dec = tl
      }
      // لایهٔ مکملِ مستقلِ S219 (کانالِ Al Brooks، position-in-channel): فقط وقتی هم لایه‌های
      // اصلی و هم S215 خنثی‌اند (بدونِ تداخل). سهمِ مستقلِ M15 در s219_finalize = +$4,028 (WR ۵۰.۱٪، WF-4/4).
      if (dec.state === 'NEUTRAL') {
        const chn = channelDecision(CHANNEL_CFG['XAUUSD-M15'], result,
          useCandles.map(k => k.open), useCandles.map(k => k.high), useCandles.map(k => k.low), closes, capital, riskPct)
        if (chn.state === 'ENTRY' || chn.state === 'APPROACHING') dec = chn
      }
    }
    // 🔎 پاسخِ User Note: «همهٔ لایه‌های نزدیک به فعال‌سازی را (collapsed) نشان بده».
    // لایه‌های ثانویهٔ فعال (ENTRY/APPROACHING) را کاوش و به تصمیمِ اصلی پیوست می‌کنیم؛
    // فرانت‌اند آن‌ها را جمع‌شونده زیرِ سیگنالِ اصلی نمایش می‌دهد. (منطقِ برندهٔ dec دست‌نخورده)
    dec = attachSecondary(dec, {
      assetId: a.id, result, open: useCandles.map(k => k.open), high: useCandles.map(k => k.high),
      low: useCandles.map(k => k.low), close: closes, capital, riskPct,
      utcHour: goldUtcHour, utcDay: goldUtcDay, times: goldTimes,
      primaryCode: dec.sourceLayer?.code,
    })
    return { asset: a.id, name: a.name, symbol: a.symbol, decimals: a.decimals, layer: a.layer,
      price: result.price, lastCandleTime: useCandles[useCandles.length - 1].time, decision: dec,
      spot: spot ? { price: spot.price, ageSec: spot.ageSec, source: spot.source } : null }
  }
  // سایر دارایی‌ها: کندلِ Yahoo + به‌روزرسانیِ کندلِ جاری با قیمتِ زنده
  // (رفعِ اختلافِ قیمتِ لحظه‌ای — User Note نکتهٔ اول)
  // تایم‌فریم از فیلدِ `tf` می‌آید (پیش‌فرض 15m). range و gap متناسب با تایم‌فریم
  // انتخاب می‌شود تا هم داده کافی باشد و هم Yahoo پاسخ دهد (M1 فقط ~۷ روز می‌دهد).
  const tf = a.tf || '15m'
  const rangeFor = (t: string) => (t === '1m' || t === '5m') ? '5d' : '1mo'
  const gapForTf = (t: string) => t === '1m' ? 60 : t === '5m' ? 300 : t === '30m' ? 1800 : 900
  const { candles } = await yahooCandles(a.symbol, tf, rangeFor(tf))
  // آستانهٔ داده برای placeholder سبک‌تر است (فقط نمایشِ قیمت/داده، نه تحلیلِ سنگین).
  const minBars = a.layer === 'placeholder' ? 30 : 220
  if (candles.length < minBars) throw new Error('داده کافی برای تحلیل نیست')
  let live: number | null = null, liveAge = 0, liveSrc = ''
  try { const q = await getLiveQuote(a.symbol); live = q.price; liveAge = q.ageSec; liveSrc = q.source } catch {}
  const merged = mergeLiveQuote(candles, live, gapForTf(tf))
  const useCandles = merged.candles
  const result = analyze(useCandles)
  // EURUSD (M5): منطقِ مخصوصِ S73 (Session-Open Drift) — نه decide()ِ عمومیِ طلا.
  // کارت‌های placeholder (EURUSD-M15/M30/M1): قالبِ خام — «در دستِ تحقیق».
  let dec
  if (a.layer === 'placeholder') {
    dec = placeholderDecision(a, result, tf)
  } else if (a.id === 'EURUSD') {
    const lastT = useCandles[useCandles.length - 1].time
    const nowUtcHour = new Date(lastT * 1000).getUTCHours()
    dec = decideEurusd(result, useCandles.map(k => k.close), nowUtcHour, capital, riskPct, lastT)
  } else if (a.id === 'EURUSD-M15') {
    // کارتِ M15 مخصوصِ لایهٔ S213 (Second-Entry SHORT، Brooks فصلِ ۱۰) — دادهٔ M15.
    dec = decideEurusdM15(result, useCandles.map(k => k.open), useCandles.map(k => k.high),
      useCandles.map(k => k.low), useCandles.map(k => k.close), capital, riskPct)
  } else {
    dec = decide(result, useCandles.map(k => k.close), capital, riskPct, assetSpec(a.id))
  }
  return { asset: a.id, name: a.name, symbol: a.symbol, decimals: a.decimals, layer: a.layer,
    price: result.price, lastCandleTime: useCandles[useCandles.length - 1].time, decision: dec,
    spot: live != null ? { price: live, ageSec: liveAge, source: liveSrc } : null }
}

// ---------------------------------------------------------------------------
// قالبِ خامِ کارت‌های بدونِ استراتژیِ اثبات‌شده (placeholder) — درخواستِ کاربر.
// همیشه NEUTRAL برمی‌گرداند و صریحاً می‌گوید «این تایم‌فریم هنوز در دستِ تحقیق است».
// چند شاخصِ پایه (RSI/ATR/ADX) را برای شفافیت نشان می‌دهد. آماده برای گسترش:
// در تحقیقِ آینده کافی است این تابع با منطقِ واقعیِ همان تایم‌فریم جایگزین شود
// (هر کارت مستقل است ⇒ افزودنِ منطق به یک تایم‌فریم بقیه را تغییر نمی‌دهد).
// ---------------------------------------------------------------------------
const TF_FA: Record<string, string> = { '1m': 'M1 (یک‌دقیقه‌ای)', '5m': 'M5 (پنج‌دقیقه‌ای)', '15m': 'M15 (پانزده‌دقیقه‌ای)', '30m': 'M30 (سی‌دقیقه‌ای)' }
function placeholderDecision(a: typeof ASSETS[number], result: any, tf: string): RouterDecision {
  const tfFa = TF_FA[tf] || tf
  return {
    state: 'NEUTRAL',
    regime: { regime: 'range', efficiencyRatio: 0, trendy: false, adx: result.adx ?? 0, activeStream: 'none', bucket: 'research' },
    headline: `${a.name} — قالبِ خام (در دستِ تحقیق)`,
    reason:
      `این کارت برای تایم‌فریمِ ${tfFa} ساخته شده اما هنوز استراتژیِ اثبات‌شده و بک‌تست‌شده‌ای ` +
      `روی این تایم‌فریم برایش تعریف نشده است. طبقِ قانونِ اصلیِ پروژه (فقط سودِ خالصِ اثبات‌شده)، ` +
      `تا وقتی لبه‌ای با WR≥۴۰٪ و سودِ خالصِ مثبت روی این تایم‌فریم کشف نشود، این کارت سیگنالِ ورود ` +
      `نمی‌دهد و صرفاً «قالبِ خامِ آمادهٔ گسترش» است. داده و قیمتِ زنده در حالِ پایش است.`,
    sourceLayer: { code: '—', name: `EURUSD ${tfFa} — بدونِ لایهٔ فعال`, kind: 'time' },
    indicators: [
      { name: 'وضعیتِ تحقیق', value: 'قالبِ خام (placeholder)', status: 'neutral' },
      { name: 'تایم‌فریم', value: tfFa, status: 'neutral' },
      { name: 'RSI(14)', value: (result.rsi14 ?? 0).toFixed(1), status: 'neutral' },
      { name: 'ATR', value: (result.atr ?? 0).toFixed(5), status: 'neutral' },
    ],
  }
}

// خواندنِ سرمایه/ریسکِ کاربر از query (پیش‌فرض ۱۰k$ ، ۱٪) — کشفِ L41 (S67)
function readCapitalParams(c: any): [number, number] {
  const cap = Math.max(50, Math.min(10_000_000, parseFloat(c.req.query('capital')) || 10000))
  const risk = Math.max(0.1, Math.min(5, parseFloat(c.req.query('risk')) || 1.0))
  return [cap, risk]
}

// ---------------------------------------------------------------------------
// endpointِ فوقِ سبکِ «فهرستِ کارت‌ها» — هیچ fetchی به Yahoo نمی‌زند.
// ----------------------------------------------------------------------------
// رفعِ مشکلِ کندیِ لود (User Note): قبلاً فرانت‌اند تا کاملِ /api/decision (هر ۱۲
// دارایی) هیچ کارتی نشان نمی‌داد؛ اگر Yahoo یک دارایی را کند/rate-limit می‌کرد،
// کلِ صفحه تا دقایق خالی می‌ماند. حالا فرانت‌اند اول این فهرستِ فوریِ متادیتا را
// می‌گیرد (میلی‌ثانیه)، کارت‌ها را فوراً با «اسکلتِ در حال تحلیل» می‌سازد، سپس هر
// کارت را مستقلاً از /api/decision/:asset پر می‌کند (کارت‌های سریع فوراً می‌آیند).
// ---------------------------------------------------------------------------
app.get('/api/assets', (c) => {
  return c.json({
    ok: true,
    assets: ASSETS.map(a => ({ id: a.id, name: a.name, decimals: a.decimals, layer: a.layer })),
  })
})

// همهٔ دارایی‌ها یک‌جا (موازی، مقاوم به خطای هر دارایی)
app.get('/api/decision', async (c) => {
  const [capital, riskPct] = readCapitalParams(c)
  const results = await Promise.allSettled(ASSETS.map(a => decideAsset(a, capital, riskPct)))
  const assets = results.map((r, i) =>
    r.status === 'fulfilled'
      ? { ok: true, ...r.value }
      : { ok: false, asset: ASSETS[i].id, name: ASSETS[i].name, symbol: ASSETS[i].symbol, error: (r as any).reason?.message || 'خطا' }
  )
  return c.json({ ok: true, lastUpdate: new Date().toISOString(), assets })
})

// یک دارایی مشخص: /api/decision/:asset
app.get('/api/decision/:asset', async (c) => {
  const id = (c.req.param('asset') || '').toUpperCase()
  const a = ASSETS.find(x => x.id === id)
  if (!a) return c.json({ ok: false, error: `دارایی ناشناخته: ${id}` }, 404)
  try {
    const [capital, riskPct] = readCapitalParams(c)
    const out = await decideAsset(a, capital, riskPct)
    return c.json({ ok: true, lastUpdate: new Date().toISOString(), ...out })
  } catch (e: any) {
    return c.json({ ok: false, asset: a.id, name: a.name, error: e.message }, 502)
  }
})

// ---------------------------------------------------------------------------
// endpointِ سبکِ قیمتِ زندهٔ همهٔ دارایی‌ها — برای پُلینگِ سریع (هر ~۲ ثانیه).
// پاسخ به User Note (نکتهٔ اول): «سایت خودکار هر ۲ ثانیه قیمت‌ها را به‌روز کند».
// این endpoint هیچ محاسبهٔ سنگینی (اندیکاتور/سیگنال) ندارد؛ فقط قیمتِ لحظه‌ای هر
// دارایی را می‌دهد تا فرانت‌اند عددِ نمایشیِ کارت‌ها را زنده نگه دارد. سیگنال/تصمیم
// همچنان با نرخِ آهسته‌تر (هر ۳۰ ثانیه) از /api/decision می‌آید.
// getLiveQuote کشِ ۱.۵ ثانیه‌ای دارد → فشارِ Yahoo کنترل‌شده می‌ماند.
// ---------------------------------------------------------------------------
app.get('/api/spots', async (c) => {
  const jobs = ASSETS.map(async (a) => {
    try {
      if (a.isGold) {
        const s = await getSpotGold()
        return { asset: a.id, ok: true, price: Number(s.price.toFixed(a.decimals)), ageSec: s.ageSec, source: s.source }
      }
      const q = await getLiveQuote(a.symbol)
      return { asset: a.id, ok: true, price: Number(q.price.toFixed(a.decimals)), ageSec: q.ageSec, source: q.source }
    } catch (e: any) {
      return { asset: a.id, ok: false, error: e?.message || 'خطا' }
    }
  })
  const spots = await Promise.all(jobs)
  return c.json({ ok: true, at: Date.now(), spots })
})

// پروکسیِ عمومیِ CORS-safe — برای APK/WebView تا دادهٔ چند-دارایی از Yahoo بگیرد
// (سرورِ سایت محدودیتِ CORS مرورگر را ندارد). فقط دامنه‌های مالیِ مجاز.
// دارای کشِ کوتاه‌مدت + retry، تا درخواست‌های همزمانِ چند-دارایی Yahoo را نرخ‌محدود نکند.
const _proxyCache = new Map<string, { at: number; status: number; body: string }>()
const _PROXY_TTL = 60_000  // ۶۰ ثانیه (کندلِ M15 تا دقایق تازه می‌ماند)

app.get('/api/proxy', async (c) => {
  const target = c.req.query('url') || ''
  const allow = ['query1.finance.yahoo.com', 'query2.finance.yahoo.com', 'finance.yahoo.com']
  let host = ''
  try { host = new URL(target).hostname } catch { return c.json({ ok: false, error: 'bad url' }, 400) }
  if (!allow.includes(host)) return c.json({ ok: false, error: 'host not allowed' }, 403)

  const cached = _proxyCache.get(target)
  const now = Date.now()
  if (cached && now - cached.at < _PROXY_TTL && cached.status === 200) {
    return new Response(cached.body, {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'X-Proxy-Cache': 'hit' },
    })
  }
  // تلاش با query1 و query2 و چند retry برای دورزدنِ نرخ‌محدودیِ لحظه‌ای
  const hosts = [target, target.replace('query1.', 'query2.')]
  for (let attempt = 0; attempt < 3; attempt++) {
    const u = hosts[attempt % hosts.length]
    try {
      const r = await fetch(u, { headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' } })
      const body = await r.text()
      if (r.status === 200) {
        _proxyCache.set(target, { at: now, status: 200, body })
        return new Response(body, {
          status: 200,
          headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'X-Proxy-Cache': 'miss' },
        })
      }
    } catch (e) { /* retry بعدی */ }
    await new Promise((res) => setTimeout(res, 250 * (attempt + 1)))
  }
  // اگر همه تلاش‌ها ناموفق بود ولی کشِ قدیمی داریم، همان را بده (stale-while-error)
  if (cached && cached.status === 200) {
    return new Response(cached.body, {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'X-Proxy-Cache': 'stale' },
    })
  }
  return c.json({ ok: false, error: 'upstream unavailable' }, 502)
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
  <title>دستیارِ تصمیمِ معاملات — چند دارایی</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css" rel="stylesheet">
  <link href="/static/style.css" rel="stylesheet">
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <div id="app" class="max-w-5xl mx-auto p-4"></div>
  <script type="module" src="/static/signal_latch.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>`

export default app
