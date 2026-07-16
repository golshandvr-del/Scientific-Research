// ============================================================================
// منابع داده «خارج از OHLCV طلا» + تحلیل چند-تایم‌فریمی.
// پاسخ به User Note:
//   #2 «تحلیل چند-تایم‌فریمی (H1/H4/D1) و نمایش هم‌راستایی روندها»
//   #3 «افزودن منبع داده خارج از OHLCV (DXY، بازده اوراق، تقویم اخبار)»
//
// همهٔ داده‌ها از منابع رایگان و بدون کلید:
//   - Yahoo Finance: طلا (GC=F)، شاخص دلار (DX-Y.NYB)، بازده ۱۰سالهٔ آمریکا (^TNX)
//   - ForexFactory (nfs.faireconomy.media): تقویم اقتصادی هفتهٔ جاری (USD, High/Med/Low)
//
// این ماژول در Cloudflare Worker (سمت سرور) اجرا می‌شود چون fetch از این منابع
// نیاز به عبور از CORS مرورگر دارد.
// ============================================================================
import type { Candle } from './indicators'
import { ema, rollingSlope } from './indicators'

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

// ============================================================================
// قیمت spot لحظه‌ای طلا (XAU/USD) از gold-api.com — بدون کلید، تأخیر < چند ثانیه.
// این منبع تأخیر داده را از ~۱۳ دقیقهٔ Yahoo GC=F به کمتر از ۱ دقیقه می‌رساند
// (پاسخ به مشکل «تأخیر داده باید < ۵ دقیقه باشد»).
// ============================================================================
export interface SpotPrice {
  price: number          // قیمت spot XAU/USD (mid)
  bid?: number
  ask?: number
  updatedAt: string      // زمان به‌روزرسانی منبع (ISO)
  ageSec: number         // چند ثانیه از آخرین به‌روزرسانی گذشته
  source: string
}

// --- منبع ۱: Swissquote (نزدیک‌ترین به TradingView/OANDA spot، bid/ask زنده) ---
async function spotFromSwissquote(): Promise<SpotPrice> {
  const res = await fetch('https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD', {
    headers: { 'User-Agent': UA, 'Accept': 'application/json' },
    cf: { cacheTtl: 10, cacheEverything: true } as any,
  })
  if (!res.ok) throw new Error(`Swissquote error: ${res.status}`)
  const arr: any = await res.json()
  // نزدیک‌ترین اسپرد (elite) را ترجیح می‌دهیم؛ mid = (bid+ask)/2
  let bid = NaN, ask = NaN, ts = Date.now()
  for (const tier of arr) {
    const prices = tier?.spreadProfilePrices || []
    // elite کمترین اسپرد → نزدیک‌ترین به قیمت مرجع
    const p = prices.find((x: any) => x.spreadProfile === 'elite') || prices[0]
    if (p && isFinite(p.bid) && isFinite(p.ask)) { bid = p.bid; ask = p.ask; ts = tier.ts || ts; break }
  }
  if (!isFinite(bid) || !isFinite(ask)) throw new Error('Swissquote: no valid quote')
  const price = (bid + ask) / 2
  const updatedAt = new Date(ts).toISOString()
  const ageSec = Math.max(0, Math.round((Date.now() - ts) / 1000))
  return { price, bid, ask, updatedAt, ageSec, source: 'Swissquote (XAU/USD spot)' }
}

// --- منبع ۲: gold-api.com (fallback) ---
async function spotFromGoldApi(): Promise<SpotPrice> {
  const res = await fetch('https://api.gold-api.com/price/XAU', {
    headers: { 'User-Agent': UA, 'Accept': 'application/json' },
    cf: { cacheTtl: 20, cacheEverything: true } as any,
  })
  if (!res.ok) throw new Error(`gold-api error: ${res.status}`)
  const d: any = await res.json()
  const updatedAt = d.updatedAt || new Date().toISOString()
  const ageSec = Math.max(0, Math.round((Date.now() - new Date(updatedAt).getTime()) / 1000))
  return { price: Number(d.price), updatedAt, ageSec, source: 'gold-api.com (XAU spot)' }
}

// آخرین spot معتبر در حافظهٔ isolate (fallback در صورت قطعی هر دو منبع)
let _spotMemCache: { at: number; spot: SpotPrice } | null = null

// ============================================================================
// قیمت spot لحظه‌ای طلا (XAU/USD) — سازگار با TradingView (OANDA spot).
// استراتژی مقاوم:
//   ۱) Swissquote (نزدیک‌ترین به مرجع، bid/ask زنده)
//   ۲) در صورت خطا: gold-api.com
//   ۳) اعتبارسنجی محدوده (۵۰۰..۱۵۰۰۰) تا از داده خراب جلوگیری شود
//   ۴) در صورت قطعی هر دو: آخرین مقدار معتبر < ۵ دقیقه از کش حافظه
// این تابع دیگر قیمت futures (GC=F) را برنمی‌گرداند؛ خروجی همیشه spot است.
// ============================================================================
export async function getSpotGold(): Promise<SpotPrice> {
  const validate = (s: SpotPrice) => isFinite(s.price) && s.price > 500 && s.price < 15000
  const sources = [spotFromSwissquote, spotFromGoldApi]
  for (const src of sources) {
    try {
      const s = await src()
      if (validate(s)) { _spotMemCache = { at: Date.now(), spot: s }; return s }
    } catch { /* منبع بعدی */ }
  }
  // fallback: آخرین مقدار معتبر تازه
  if (_spotMemCache && Date.now() - _spotMemCache.at < 5 * 60 * 1000) {
    const s = _spotMemCache.spot
    return { ...s, ageSec: Math.round((Date.now() - _spotMemCache.at) / 1000) + s.ageSec, source: s.source + ' (cache)' }
  }
  throw new Error('Spot gold unavailable from all sources')
}

// -------------------------- کمکی: fetch کندل از Yahoo --------------------------
export async function yahooCandles(symbol: string, interval: string, range: string): Promise<{ candles: Candle[]; meta: any }> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=${interval}&range=${range}`
  const res = await fetch(url, {
    headers: { 'User-Agent': UA, 'Accept': 'application/json' },
    cf: { cacheTtl: 60, cacheEverything: true } as any,
  })
  if (!res.ok) throw new Error(`Yahoo ${symbol} error: ${res.status}`)
  const data: any = await res.json()
  const r = data?.chart?.result?.[0]
  if (!r) throw new Error(`No data for ${symbol}`)
  const ts: number[] = r.timestamp || []
  const q = r.indicators?.quote?.[0] || {}
  const candles: Candle[] = []
  for (let i = 0; i < ts.length; i++) {
    const o = q.open?.[i], h = q.high?.[i], l = q.low?.[i], c = q.close?.[i]
    if (o == null || h == null || l == null || c == null) continue
    candles.push({ time: ts[i], open: o, high: h, low: l, close: c, volume: q.volume?.[i] ?? 0 })
  }
  return {
    candles,
    meta: {
      symbol: r.meta?.symbol,
      name: r.meta?.shortName,
      price: r.meta?.regularMarketPrice,
      previousClose: r.meta?.previousClose,
    },
  }
}

// ------------------- تجمیع H1 → H4 (چون Yahoo H4 مستقیم ندارد) -------------------
function resampleH4(h1: Candle[]): Candle[] {
  const out: Candle[] = []
  let bucket: Candle[] = []
  for (const k of h1) {
    // مرز بلوک ۴ساعته بر پایهٔ ساعت UTC (00,04,08,12,16,20)
    const hourUTC = new Date(k.time * 1000).getUTCHours()
    if (bucket.length > 0 && hourUTC % 4 === 0) {
      out.push(mergeBucket(bucket)); bucket = []
    }
    bucket.push(k)
  }
  if (bucket.length) out.push(mergeBucket(bucket))
  return out
}
function mergeBucket(b: Candle[]): Candle {
  return {
    time: b[0].time,
    open: b[0].open,
    high: Math.max(...b.map(x => x.high)),
    low: Math.min(...b.map(x => x.low)),
    close: b[b.length - 1].close,
    volume: b.reduce((s, x) => s + (x.volume || 0), 0),
  }
}

// --------------------- ارزیابی روند یک تایم‌فریم (rule-based) ---------------------
// معیار روند: موقعیت قیمت نسبت به EMA50/EMA200 + شیب EMA50.
export interface TFTrend {
  timeframe: string
  price: number
  ema50: number
  ema200: number
  slope50: number          // شیب نرمال‌شدهٔ EMA50 (٪ در هر کندل)
  trend: 'up' | 'down' | 'range'
  score: number            // +1 صعودی، -1 نزولی، 0 خنثی
  detail: string
}
function classifyTrend(timeframe: string, candles: Candle[]): TFTrend {
  const close = candles.map(c => c.close)
  const e50 = ema(close, 50)
  const e200 = ema(close, 200)
  const slope = rollingSlope(e50, 10)
  const i = close.length - 1
  const price = close[i]
  const ema50 = e50[i]
  const ema200 = e200[i]
  // شیب نرمال‌شده به درصد قیمت
  const slope50 = ema50 ? (slope[i] / ema50) * 100 : 0
  let trend: 'up' | 'down' | 'range' = 'range'
  let score = 0
  const aboveBoth = price > ema50 && ema50 > ema200
  const belowBoth = price < ema50 && ema50 < ema200
  if (aboveBoth && slope50 > 0.001) { trend = 'up'; score = 1 }
  else if (belowBoth && slope50 < -0.001) { trend = 'down'; score = -1 }
  else { trend = 'range'; score = 0 }
  const detail = trend === 'up' ? 'صعودی (قیمت > EMA50 > EMA200، شیب مثبت)'
    : trend === 'down' ? 'نزولی (قیمت < EMA50 < EMA200، شیب منفی)'
    : 'رنج/خنثی (ساختار EMA مبهم)'
  return {
    timeframe,
    price: Number(price.toFixed(2)),
    ema50: Number(ema50.toFixed(2)),
    ema200: Number(ema200.toFixed(2)),
    slope50: Number(slope50.toFixed(4)),
    trend, score, detail,
  }
}

// =============================== MTF (H1/H4/D1) ===============================
export interface MTFResult {
  timeframes: TFTrend[]
  alignment: 'bullish' | 'bearish' | 'mixed'
  alignmentScore: number   // مجموع score‌ها (−۳..+۳)
  agreeWithStrategy: boolean  // آیا با استراتژی long-only هم‌راستاست؟
  note: string
}
export async function getMTF(): Promise<MTFResult> {
  // H1 و D1 را از Yahoo می‌گیریم؛ H4 را از H1 می‌سازیم.
  const [h1r, d1r] = await Promise.all([
    yahooCandles('GC=F', '1h', '3mo'),   // ~۳ماه H1 برای EMA200
    yahooCandles('GC=F', '1d', '2y'),    // ~۲سال روزانه برای EMA200
  ])
  const h1 = h1r.candles
  const h4 = resampleH4(h1)
  const d1 = d1r.candles

  const timeframes: TFTrend[] = [
    classifyTrend('H1', h1),
    classifyTrend('H4', h4),
    classifyTrend('D1', d1),
  ]
  const alignmentScore = timeframes.reduce((s, t) => s + t.score, 0)
  let alignment: 'bullish' | 'bearish' | 'mixed' = 'mixed'
  if (timeframes.every(t => t.score === 1)) alignment = 'bullish'
  else if (timeframes.every(t => t.score === -1)) alignment = 'bearish'
  // استراتژی S14 فقط long است → هم‌راستایی صعودی مطلوب‌ترین حالت است.
  const agreeWithStrategy = alignmentScore > 0
  const note = alignment === 'bullish'
    ? '✅ هر سه تایم‌فریم صعودی — بهترین شرایط برای سیگنال LONG استراتژی.'
    : alignment === 'bearish'
      ? '⛔ هر سه تایم‌فریم نزولی — استراتژی long-only در این شرایط سیگنال نمی‌دهد یا باید با احتیاط.'
      : 'تایم‌فریم‌ها هم‌راستا نیستند — احتمال نوسان/رنج بالاتر است؛ کیفیت سیگنال کمتر.'
  return { timeframes, alignment, alignmentScore, agreeWithStrategy, note }
}

// ========================= داده‌های بین‌بازاری (DXY, TNX) =========================
export interface AssetSnapshot {
  symbol: string
  name: string
  price: number
  changePct: number       // درصد تغییر نسبت به کندل قبل (روزانه)
  trend: 'up' | 'down' | 'range'
}
export interface IntermarketResult {
  dxy: AssetSnapshot
  tnx: AssetSnapshot
  goldBias: 'supportive' | 'headwind' | 'neutral'  // سوگیری بنیادی برای طلا
  note: string
}
async function snapshot(symbol: string, name: string): Promise<AssetSnapshot> {
  const { candles } = await yahooCandles(symbol, '1d', '3mo')
  const close = candles.map(c => c.close)
  const e20 = ema(close, 20)
  const i = close.length - 1
  const price = close[i]
  const prev = close[i - 1] ?? price
  const changePct = prev ? ((price - prev) / prev) * 100 : 0
  const trend: 'up' | 'down' | 'range' =
    price > e20[i] * 1.001 ? 'up' : price < e20[i] * 0.999 ? 'down' : 'range'
  return { symbol, name, price: Number(price.toFixed(3)), changePct: Number(changePct.toFixed(3)), trend }
}
export async function getIntermarket(): Promise<IntermarketResult> {
  const [dxy, tnx] = await Promise.all([
    snapshot('DX-Y.NYB', 'شاخص دلار آمریکا (DXY)'),
    snapshot('^TNX', 'بازده اوراق ۱۰سالهٔ آمریکا (US10Y)'),
  ])
  // منطق بنیادی کلاسیک: طلا معمولاً با DXY و بازده اوراق رابطهٔ معکوس دارد.
  //   DXY↓ و بازده↓ → حمایت‌کننده برای طلا (supportive)
  //   DXY↑ و بازده↑ → فشار بر طلا (headwind)
  let goldBias: 'supportive' | 'headwind' | 'neutral' = 'neutral'
  const dxyDown = dxy.trend === 'down'
  const tnxDown = tnx.trend === 'down'
  const dxyUp = dxy.trend === 'up'
  const tnxUp = tnx.trend === 'up'
  if (dxyDown && tnxDown) goldBias = 'supportive'
  else if (dxyUp && tnxUp) goldBias = 'headwind'
  else if (dxyDown || tnxDown) goldBias = 'supportive'
  else if (dxyUp || tnxUp) goldBias = 'headwind'
  const note = goldBias === 'supportive'
    ? '🟢 محیط بین‌بازاری حمایت‌کنندهٔ طلا (دلار/بازده در حال کاهش) — همسو با سیگنال LONG.'
    : goldBias === 'headwind'
      ? '🔴 محیط بین‌بازاری مخالف طلا (دلار/بازده در حال افزایش) — احتیاط در LONG.'
      : '⚪ محیط بین‌بازاری خنثی.'
  return { dxy, tnx, goldBias, note }
}

// ============================= تقویم اخبار اقتصادی =============================
export interface NewsEvent {
  title: string
  country: string
  impact: 'High' | 'Medium' | 'Low' | string
  date: string            // ISO
  forecast: string
  previous: string
  minutesUntil: number    // دقیقه تا رویداد (منفی = گذشته)
}
export interface NewsResult {
  events: NewsEvent[]      // فقط USD مرتبط با طلا
  highImpactSoon: NewsEvent[]  // رویدادهای High-impact در ۱۲ ساعت آینده
  riskWindow: boolean      // آیا الان نزدیک یک خبر پرتأثیر هستیم؟
  note: string
}
// ---------------------------------------------------------------------------
// دریافت خام تقویم با مقاومت در برابر 429:
//   ۱) تلاش از چند endpoint (mirror)
//   ۲) استفاده از Cache API لبه به‌عنوان لایهٔ پایدار (حتی وقتی مبدأ 429 می‌دهد)
//   ۳) اگر KV در دسترس باشد (env.NEWS_KV)، آخرین پاسخ موفق را نگه می‌دارد
// این ساختار مشکل «Calendar error: 429» و نیز تأخیر تقویم را حل می‌کند.
// ---------------------------------------------------------------------------
const CAL_URLS = [
  'https://nfs.faireconomy.media/ff_calendar_thisweek.json',
  'https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json',
]
// کش داخل حافظهٔ ایزوله (isolate) — بین درخواست‌های نزدیک به‌هم روی همان worker می‌ماند
let _calMemCache: { at: number; data: any[] } | null = null

async function fetchCalendarRaw(env?: any): Promise<any[]> {
  // 0) کش حافظه‌ای تازه (< ۱۰ دقیقه)
  if (_calMemCache && Date.now() - _calMemCache.at < 10 * 60 * 1000) {
    return _calMemCache.data
  }
  // 1) Cache API لبه
  const cacheKey = new Request('https://cache.local/ff_calendar_thisweek')
  const edgeCache = (globalThis as any).caches?.default
  let lastErr: any = null

  // 2) تلاش از mirrorها
  for (const url of CAL_URLS) {
    try {
      const res = await fetch(url, {
        headers: {
          'User-Agent': UA,
          'Accept': 'application/json,text/plain,*/*',
          'Referer': 'https://www.forexfactory.com/',
        },
        cf: { cacheTtl: 1800, cacheEverything: true } as any,
      })
      if (res.ok) {
        const data = await res.json() as any[]
        _calMemCache = { at: Date.now(), data }
        // ذخیره در Cache API و KV برای درخواست‌های بعدی
        try {
          if (edgeCache) {
            const store = new Response(JSON.stringify(data), {
              headers: { 'Content-Type': 'application/json', 'Cache-Control': 'max-age=1800' },
            })
            await edgeCache.put(cacheKey, store)
          }
        } catch {}
        try { if (env?.NEWS_KV) await env.NEWS_KV.put('ff_thisweek', JSON.stringify({ at: Date.now(), data }), { expirationTtl: 86400 }) } catch {}
        return data
      }
      lastErr = new Error(`Calendar HTTP ${res.status}`)
    } catch (e) { lastErr = e }
  }

  // 3) مبدأ در دسترس نبود (مثلاً 429) → از کش لبه بخوان
  try {
    if (edgeCache) {
      const cached = await edgeCache.match(cacheKey)
      if (cached) { const data = await cached.json() as any[]; _calMemCache = { at: Date.now(), data }; return data }
    }
  } catch {}
  // 4) از KV بخوان (پایدارترین)
  try {
    if (env?.NEWS_KV) {
      const kv = await env.NEWS_KV.get('ff_thisweek')
      if (kv) { const p = JSON.parse(kv); _calMemCache = { at: Date.now(), data: p.data }; return p.data }
    }
  } catch {}

  throw lastErr || new Error('Calendar unavailable')
}

export async function getNews(env?: any): Promise<NewsResult> {
  const raw: any[] = await fetchCalendarRaw(env)
  const now = Date.now()
  const events: NewsEvent[] = raw
    .filter(e => e.country === 'USD')
    .map(e => {
      const t = new Date(e.date).getTime()
      return {
        title: e.title,
        country: e.country,
        impact: e.impact,
        date: new Date(e.date).toISOString(),
        forecast: e.forecast || '',
        previous: e.previous || '',
        minutesUntil: Math.round((t - now) / 60000),
      }
    })
    .sort((a, b) => a.minutesUntil - b.minutesUntil)
  const highImpactSoon = events.filter(e => e.impact === 'High' && e.minutesUntil > 0 && e.minutesUntil <= 12 * 60)
  // پنجرهٔ ریسک: خبر High-impact در ۶۰ دقیقهٔ گذشته تا ۶۰ دقیقهٔ آینده
  const riskWindow = events.some(e => e.impact === 'High' && Math.abs(e.minutesUntil) <= 60)
  const note = riskWindow
    ? '⚠️ پنجرهٔ ریسک خبری: یک رویداد پرتأثیر USD در حال حاضر/به‌زودی — نوسان شدید محتمل، از ورود پرهیز شود.'
    : highImpactSoon.length
      ? `📅 ${highImpactSoon.length} رویداد پرتأثیر USD در ۱۲ ساعت آینده — با احتیاط معامله شود.`
      : '✅ رویداد پرتأثیر USD نزدیکی در راه نیست.'
  return { events: events.slice(0, 20), highImpactSoon, riskWindow, note }
}
