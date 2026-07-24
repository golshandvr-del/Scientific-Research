// ============================================================================
// fast_fetch.ts — «سریع‌ترین منبع، خودکار» (پاسخِ ایدهٔ کاربر: چند API همزمان)
// ----------------------------------------------------------------------------
// ایدهٔ کاربر: «نمی‌شود همزمان از چند API استفاده کنیم و سریع‌ترین خودکار انتخاب شود؟»
// پاسخ: بله — اما با ظرافت. دو حالت داریم:
//
//   الف) داده‌های *همگون* (قیمتِ لحظه‌ای/spot): چند منبع عملاً یک عدد می‌دهند، پس
//        می‌توان واقعاً «مسابقه» گذاشت و اولین پاسخِ سالم را برد ⇒ raceOk().
//        این دقیقاً همان «سریع‌ترین API خودکار» است.
//
//   ب) داده‌های *ناهمگون* (کندل‌های OHLC): منابعِ مختلف دقت/زمان‌بندی/نماد متفاوت
//        دارند. اگر وسطِ کار منبع عوض شود، ممکن است منطقِ تصمیم با داده‌ای کمی
//        متفاوت تغذیه شود. چون قانونِ پروژه «دست‌نزدن به منطقِ تصمیم» است، برای
//        کندل از الگویِ *fallback با timeout* استفاده می‌کنیم: اول منبعِ اصلی
//        (Yahoo، همان دادهٔ همیشگی) را با یک مهلتِ کوتاه امتحان می‌کنیم؛ فقط اگر
//        کند/خطا بود، به منبعِ دوم می‌رویم ⇒ fetchWithTimeout + fallbackChain.
//        این «داده را عوض نمی‌کند»، فقط جلویِ هنگِ ۲-دقیقه‌ای را می‌گیرد.
//
// نکتهٔ IP بروکر (MT5): آن IP فقط به سرورِ باینریِ همان بروکر سرعت می‌دهد، نه به
// این endpointهایِ HTTP عمومی. پس در این مسیر بی‌اثر است؛ راهِ درست همین چند-منبعیِ
// HTTP است.
// ============================================================================

// fetch با مهلتِ زمانی (AbortController) — جلویِ هنگِ نامحدودِ یک منبعِ کند را می‌گیرد.
export async function fetchWithTimeout(url: string, init: RequestInit = {}, timeoutMs = 6000): Promise<Response> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    return await fetch(url, { ...init, signal: ctrl.signal })
  } finally {
    clearTimeout(timer)
  }
}

// raceOk — چند producer را هم‌زمان اجرا می‌کند و «اولین پاسخِ سالم» را برمی‌گرداند.
// مناسبِ دادهٔ همگون (قیمتِ spot/live). اگر همه شکست خوردند، آخرین خطا را می‌اندازد.
export async function raceOk<T>(producers: Array<() => Promise<T>>): Promise<T> {
  const errors: any[] = []
  return await new Promise<T>((resolve, reject) => {
    let pending = producers.length
    if (pending === 0) return reject(new Error('no producers'))
    producers.forEach(p => {
      p().then(
        v => resolve(v),
        e => { errors.push(e); if (--pending === 0) reject(errors[0] ?? new Error('all failed')) }
      )
    })
  })
}

// fallbackChain — منابع را «به‌ترتیب» امتحان می‌کند تا اولین موفق. برای دادهٔ
// ناهمگون (کندل): منبعِ اصلی همیشه اولویت دارد؛ منبعِ دوم فقط پشتیبان است.
export async function fallbackChain<T>(producers: Array<() => Promise<T>>): Promise<T> {
  let lastErr: any
  for (const p of producers) {
    try { return await p() } catch (e) { lastErr = e }
  }
  throw lastErr ?? new Error('all sources failed')
}

// ----------------------------------------------------------------------------
// منبعِ دومِ کندل: Stooq (رایگان، بدونِ کلید، CSV). فقط به‌عنوانِ *پشتیبانِ* Yahoo.
// Stooq نمادِ خودش را دارد؛ نگاشتِ نمادِ Yahoo → Stooq در زیر. فقط برای دارایی‌هایی
// که معادلِ مطمئن دارند نگاشت می‌کنیم؛ بقیه پشتیبان ندارند (فقط Yahoo).
// interval نگاشت: Stooq فقط d/w/m (روزانه به بالا) رایگان می‌دهد؛ برای اینترادی
// معتبر نیست، پس Stooq را فقط برای تایم‌فریم‌های روزانه‌به‌بالا پشتیبان می‌کنیم.
// ----------------------------------------------------------------------------
export interface SimpleCandle { time: number; open: number; high: number; low: number; close: number; volume: number }

const STOOQ_SYMBOL: Record<string, string> = {
  'GC=F': 'xauusd',        // طلا
  'EURUSD=X': 'eurusd',
  'GBPUSD=X': 'gbpusd',
  'AUDUSD=X': 'audusd',
  'USDJPY=X': 'usdjpy',
}

// آیا این interval برای Stooq (روزانه‌به‌بالا) مناسب است؟
export function stooqSupports(symbol: string, interval: string): boolean {
  if (!STOOQ_SYMBOL[symbol]) return false
  return interval === '1d' || interval === '1wk' || interval === '1mo'
}

// دریافتِ کندلِ روزانه از Stooq (CSV) — پشتیبانِ Yahoo برای تایم‌فریم‌های بلند.
export async function stooqDaily(symbol: string, timeoutMs = 6000): Promise<SimpleCandle[]> {
  const s = STOOQ_SYMBOL[symbol]
  if (!s) throw new Error(`Stooq: no mapping for ${symbol}`)
  const url = `https://stooq.com/q/d/l/?s=${s}&i=d`
  const res = await fetchWithTimeout(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, timeoutMs)
  if (!res.ok) throw new Error(`Stooq ${symbol} error: ${res.status}`)
  const text = await res.text()
  const lines = text.trim().split('\n')
  if (lines.length < 2) throw new Error('Stooq: empty')
  // header: Date,Open,High,Low,Close,Volume
  const out: SimpleCandle[] = []
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(',')
    if (parts.length < 5) continue
    const t = Date.parse(parts[0] + 'T00:00:00Z') / 1000
    const o = parseFloat(parts[1]), h = parseFloat(parts[2]), l = parseFloat(parts[3]), c = parseFloat(parts[4])
    const v = parts[5] ? parseFloat(parts[5]) : 0
    if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(c)) continue
    out.push({ time: t, open: o, high: h, low: l, close: c, volume: isFinite(v) ? v : 0 })
  }
  if (!out.length) throw new Error('Stooq: no rows')
  return out
}
