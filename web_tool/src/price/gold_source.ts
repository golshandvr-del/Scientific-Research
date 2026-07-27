// ============================================================================
// price/gold_source.ts — گرهِ قیمت (منطقِ دریافت/تبدیلِ کندلِ طلا)  [webplan P1]
// ----------------------------------------------------------------------------
// این توابع «عیناً» از index.tsx استخراج شده‌اند (Strangler Fig) تا مرزِ گرهِ قیمت
// رسمی شود، بدونِ هیچ تغییرِ رفتاری. index.tsx اکنون این‌ها را import می‌کند.
//
// شاملِ: _fetchGoldRaw, fetchGold (کش‌دار), aggregateCandles, rebaseFuturesToSpot,
//         mergeLiveQuote, closedBars.
//
// ⚠️ هیچ منطقی اینجا تغییر نکرده — خروجیِ endpointها باید بیت‌به‌بیت مثلِ قبل بماند.
//    (تستِ برابریِ P1 همین را تضمین می‌کند.)
// ============================================================================

import type { Candle } from '../indicators'
import type { SpotPrice } from '../external'
import { cachedFetch } from '../cache'
import { fetchWithTimeout } from '../fast_fetch'

// ---------------------------------------------------------------------------
// دریافت داده زنده طلا از Yahoo Finance (GC=F = طلای آتی COMEX، بدون نیاز به کلید)
// symbol پیش‌فرض GC=F است؛ interval و range قابل تنظیم.
// ---------------------------------------------------------------------------
// هستهٔ fetchِ طلا (بدونِ کش). خروجی دقیقاً مثلِ قبل.
export async function _fetchGoldRaw(interval: string, range: string): Promise<{ candles: Candle[]; meta: any }> {
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
export async function fetchGold(interval: string, range: string): Promise<{ candles: Candle[]; meta: any }> {
  return cachedFetch(`gold:${interval}:${range}`, () => _fetchGoldRaw(interval, range),
    { freshMs: 30_000, staleMs: 600_000 })
}

// ---------------------------------------------------------------------------
// تجمیعِ کندل‌ها به تایم‌فریمِ بزرگ‌تر (مثلِ H1×4 ⇒ H4). Yahoo تایم‌فریمِ ۴ساعته را
// مستقیم نمی‌دهد؛ پس از کندل‌های H1 آن را می‌سازیم. گروه‌بندی بر اساسِ مرزِ ساعتیِ
// UTC (۰/۴/۸/۱۲/۱۶/۲۰) انجام می‌شود تا کندل‌ها با استانداردِ متعارفِ H4 هم‌تراز باشند.
// O=اولین open ، H=بیشینهٔ high ، L=کمینهٔ low ، C=آخرین close ، V=جمعِ volume.
// ---------------------------------------------------------------------------
export function aggregateCandles(candles: Candle[], factorHours: number): Candle[] {
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
export function rebaseFuturesToSpot(candles: Candle[], spot: SpotPrice | null, intervalSec = 900): {
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
export function mergeLiveQuote(candles: Candle[], livePrice: number | null, intervalSec = 900): {
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

// ---------------------------------------------------------------------------
// closedBars — رفعِ باگِ حیاتیِ «repainting سیگنال روی کندلِ ناتمام».
// ----------------------------------------------------------------------------
// مشکل: rebaseFuturesToSpot/mergeLiveQuote آخرین کندل را با قیمتِ زنده «در حالِ
//   شکل‌گیری» به‌روز می‌کنند (برای نمایشِ قیمتِ لحظه‌ای). اگر همین آرایه به منطقِ
//   ماشهٔ سیگنال داده شود، سیگنال روی کندلِ نهایی‌نشده صادر می‌شود و با هر تیک
//   عوض می‌شود (repaint) — دقیقاً همان «۴۰۵۰ buy ← رفرش ← خنثی»ِ گزارشِ کاربر.
// راه‌حل: اگر کندلِ آخر در سطلِ زمانیِ جاری باشد (هنوز بسته نشده) آن را حذف کن و
//   آرایهٔ «فقط-کندل‌های-بسته‌شده» را برگردان. این معادلِ shift(1)ِ بک‌تست است:
//   شرطِ سیگنال روی کندلِ بستهٔ قبلی سنجیده می‌شود، ورودِ واقعی روی قیمتِ زندهٔ
//   «open کندلِ بعد» (که همان result.price است) انجام می‌شود.
// ⚠️ فقط برای منطقِ تصمیم/ماشه؛ نمایشِ قیمت و مدیریتِ معاملهٔ باز از کندلِ زنده
//   استفاده می‌کنند (آن‌ها ذاتاً باید لحظه‌ای باشند).
// ---------------------------------------------------------------------------
export function closedBars(candles: Candle[], intervalSec: number): Candle[] {
  if (candles.length < 2) return candles
  const nowSec = Math.floor(Date.now() / 1000)
  const curBucketStart = Math.floor(nowSec / intervalSec) * intervalSec
  const last = candles[candles.length - 1]
  // اگر کندلِ آخر متعلق به سطلِ زمانیِ جاری است (هنوز در حالِ شکل‌گیری) ⇒ حذفش کن.
  if (last.time >= curBucketStart) return candles.slice(0, -1)
  return candles
}
