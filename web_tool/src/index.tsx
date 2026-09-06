import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { serveStatic } from 'hono/cloudflare-workers'
import type { Candle } from './indicators'
import { analyze } from './signal'
import { evaluateTrade, type OpenTrade, type Side } from './trade_manager'
import { getMTF, getIntermarket, getNews, getSpotGold, yahooCandles, getLiveQuote, type SpotPrice } from './external'
// مدیریتِ معاملهٔ اسکالپِ M5 طلا (تنها بازماندهٔ روترهای قدیمی که هنوز فعال است —
//   endpointِ /api/manage-scalp از آن استفاده می‌کند؛ بقیهٔ decide*های قدیمی حذف شدند).
import { manageGoldM5Scalp } from './gold_m5_router'
import { cachedFetch } from './cache'
import { fetchWithTimeout } from './fast_fetch'
// --- گرهِ قیمت (webplan P1): توابعِ قیمتِ طلا از index.tsx استخراج و اینجا import شدند ---
//     منطق بیت‌به‌بیت یکسان است؛ فقط مرزِ ماژول رسمی شد (Strangler Fig).
import {
  _fetchGoldRaw, fetchGold, aggregateCandles,
  rebaseFuturesToSpot, mergeLiveQuote, closedBars,
} from './price/gold_source'
// --- رجیستریِ ماژولارِ لایه‌های احیاشده (تنها مغزِ تصمیمِ سایت پس از حذفِ استراتژی‌های قدیمی) ---
import { type LayerContext } from './strategy_registry'
// --- گرهِ Runtime P4 (webplan): مرزِ رسمیِ اجرای لایه‌ها (CardDecision@v1). ---
//     runCardTyped صرفاً runCard را با تایپِ رسمی می‌پیچد؛ خروجی بیت‌به‌بیت یکسان.
import { runCardTyped as runCard } from './runtime/runtime'
// --- لاگِ سیگنال (User Note): ثبتِ هر ENTRY/APPROACHING برای کشفِ سیگنال‌های متناقض ---
import { logSignal, getLog, findConflicts, clearLog } from './signal_log'
// --- گرهِ قیمت P2 (webplan): ذخیره‌سازیِ تاریخچه (سایه‌ای) + Heartbeat ---
//     افزودنی و بی‌خطر: ذخیره fire-and-forget است و هیچ تصمیمی را تغییر نمی‌دهد.
import { getHistoryStore } from './price/history_provider'
import { computeHealth } from './price/heartbeat'
// --- گرهِ رادارِ رژیم P3.5 (webplan): تشخیصِ رژیم در حالتِ *سایه‌ای* ---
//     افزودنی و بی‌خطر: فقط رژیم را گزارش می‌کند؛ هیچ لایه‌ای را خاموش نمی‌کند و
//     منطقِ runCard/تصمیم را تغییر نمی‌دهد (برابریِ بیت‌به‌بیت با snapshot طلایی).
import { detectRegime } from './regime/radar'
// --- گرهِ شورای لایه‌ها P4.5 (webplan): رأی‌گیریِ اجماعی در حالتِ *سایه‌ای* ---
//     افزودنی و بی‌خطر: فقط حکمِ اجماع را گزارش می‌کند؛ تصمیمِ کارت هنوز از runCard می‌آید.
import { convene } from './council/council'
// --- گرهِ دفترِ RQS زنده P7 (webplan): ثبتِ نتیجهٔ واقعیِ کاربر + RQS+ زنده + بایگانیِ خودکار ---
//     افزودنی و بی‌خطر: فقط از طریقِ endpointهای /api/ledger/* مصرف می‌شود؛ مسیرِ تصمیم دست‌نخورده.
import { recordOutcome, computeLiveRqs, liveRqsSummary, outcomesOf } from './ledger/rqs_live'
// --- گرهِ کاوشگرِ اندیکاتور P8 (webplan · ایدهٔ #۶): حالتِ پژوهشیِ همبستگیِ اندیکاتور با ---
//     حرکتِ آیندهٔ قیمت روی تاریخچهٔ ذخیره‌شده. خروجی «فقط برای AI/تحقیق»؛ افزودنی و بی‌خطر —
//     فقط از راهِ endpointهای /api/scanner/* مصرف می‌شود و مسیرِ /api/decision دست‌نخورده می‌ماند.
import { scanIndicators } from './scanner/scanner'

const app = new Hono()

app.use('/api/*', cors())
app.use('/static/*', serveStatic({ root: './public' }))
// ---------------------------------------------------------------------------
// 🧹 **بازنشستگیِ نسخهٔ «موتورِ پایتون» (Pyodide) — `S433`**
//
// پیش‌تر `/app` به `/static/app/index.html` ری‌دایرکت می‌شد؛ آن یک **رابطِ
// کاربریِ دوم** بود که موتورش را در مرورگر با `pyodide.js` اجرا می‌کرد
// (عنوانِ صفحه‌اش صریحاً «موتورِ پایتون» بود و پوشهٔ `pyengine/` را با
// `live_engine.py`, `backtest.py`, ... بارگذاری می‌کرد).
//
// آن مسیر از پروژه کنار گذاشته شده است. سایتِ رسمی **تنها** `GET /` است که
// موتورِ `TypeScript` را سمتِ سرور اجرا می‌کند (همان که `local-mobile` با
// `start.sh` بالا می‌آورد و همان که آزمون‌های `_smoke_card_inventory` و
// `_parity_*` اعتبارسنجی می‌کنند).
//
// چرا مسیر را کاملاً پاک نکردم و ری‌دایرکت گذاشتم:
//   نشانیِ `/app` ممکن است در تاریخچهٔ مرورگر یا بوکمارکِ گوشی مانده باشد.
//   حذفِ کاملِ مسیر ⇒ `404`؛ ری‌دایرکت به `/` ⇒ کاربر **سایتِ درست** را
//   می‌بیند. «مسیرِ کهنه» باید به حقیقت هدایت شود، نه به خطا.
// ---------------------------------------------------------------------------
app.get('/app', (c) => c.redirect('/', 301))

// ---------------------------------------------------------------------------
// 🟦 گرهِ قیمت (webplan P1): توابعِ _fetchGoldRaw / fetchGold / aggregateCandles /
//   rebaseFuturesToSpot / mergeLiveQuote / closedBars اکنون در ماژولِ مستقلِ
//   ./price/gold_source.ts زندگی می‌کنند و در بالای همین فایل import شده‌اند.
//   منطق بیت‌به‌بیت یکسان است (Strangler Fig) — فقط مرزِ ماژول رسمی شد.
// ---------------------------------------------------------------------------

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
      // 🔴 **تعمیرِ S396 (BUG-TFM):** پیش‌تر اینجا `fetchGold('15m','1mo')` و
      //    `rebaseFuturesToSpot(..., 900)` هارد-کد بود ⇒ توصیهٔ مدیریتِ معامله
      //    برای **هر پنج کارت** با کندلِ M15 ساخته می‌شد. حالا از همان
      //    `GOLD_TF` تغذیه می‌شود که مسیرِ تصمیم استفاده می‌کند.
      //
      //    چرا مهم است: `evaluateTrade` بر پایهٔ `a.atr` و `a.trend` می‌گوید
      //    SL/TP را کجا بگذار یا معامله را ببند. ATRِ M15 روی طلا حدودِ یک‌چهارمِ
      //    ATRِ H4 است ⇒ کارتِ H4 با SLِ چهاربرابر تنگ‌تر مدیریت می‌شد و معاملهٔ
      //    سالم را با نوسانِ معمولی بیرون می‌انداخت. برای S382 (که SL آن
      //    ۱.۵×ATR(100)=۱۲۲.۹ pip است) این یعنی نابودیِ کاملِ هندسهٔ لایه.
      //
      //    H4 نکتهٔ خاص دارد: Yahoo کندلِ ۴ساعته **نمی‌دهد**؛ عیناً مثلِ مسیرِ
      //    تصمیم، H1 گرفته و با `aggregateCandles(·,4)` تجمیع می‌شود.
      const mtf = GOLD_TF[meta_asset.id] || GOLD_TF['XAUUSD']
      const { candles } = await fetchGold(mtf.interval, mtf.range)
      // کفِ دادهٔ لازم: H4 پس از تجمیع ۱/۴ کندل دارد ⇒ آستانهٔ آن پایین‌تر است
      // (همان ۶۰ کندلی که مسیرِ تصمیم برای H4 می‌پذیرد).
      // H8 (S950) همان الگو: H1×8. کفِ خامِ H1 متناسب با فاکتور (۱۱۰ کندلِ H8 = ۸۸۰ H1).
      // S800 کارت‌های D1/H12 را افزود: H1×24 و H1×12 (Yahoo هیچ‌کدام را مستقیم
      // نمی‌دهد و کندلِ ۱-روزهٔ GC=F در ۰۴:۰۰ UTC باز می‌شود — ناهم‌تراز با D1ِ
      // نیمه‌شبِ MT5). کفِ خام = ۱۰۲ کندلِ گرم‌شدنِ لایه × فاکتورِ تجمیع.
      const aggF = meta_asset.id === 'XAUUSD-H4' ? 4 : meta_asset.id === 'XAUUSD-H8' ? 8
        : meta_asset.id === 'XAUUSD-H12' ? 12 : meta_asset.id === 'XAUUSD-D1' ? 24 : 1
      const minBars = aggF === 4 ? 240 : aggF === 8 ? 880
        : aggF === 12 ? 1300 : aggF === 24 ? 2500 : 220
      if (candles.length < minBars) return c.json({ ok: false, error: 'داده کافی برای تحلیل نیست' }, 400)
      let spot: SpotPrice | null = null
      try { spot = await getSpotGold() } catch {}
      const merged = rebaseFuturesToSpot(candles, spot, mtf.gap)
      a = analyze(aggF > 1 ? aggregateCandles(merged.candles, aggF) : merged.candles)
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
    // BUG-003: ارزشِ دلاریِ هر واحدِ حرکت به‌ازای ۱ لات (طلا=۱۰۰=CONTRACT_SIZE؛ فارکس=۱۰۰٬۰۰۰).
    const valuePerPrice = meta_asset.isGold ? 100 : 100_000
    const trade: OpenTrade = { side, entry, tp, sl, openedAt: tr.openedAt, barsHeld, managePlan, valuePerPrice }
    const modelProbPct = typeof body.modelProbPct === 'number' ? body.modelProbPct : undefined

    // 🛡 نگهبانِ برگشت (User Note trade-mgmt): جهتِ زندهٔ موتورِ همان کارت را می‌گیریم
    // تا اگر موتور در پس‌زمینه سیگنالِ جهتِ مخالف می‌دهد، مدیریتِ معامله آن را ببیند.
    // شکست در این مرحله نباید کلِ advice را خراب کند (fail-safe: بدونِ reversal ادامه بده).
    let oppSignal: { state: any; direction?: string; sourceLayer?: any } | undefined
    try {
      const live = await decideAsset(meta_asset)
      const d: any = live.decision
      oppSignal = { state: d.state, direction: d.direction, sourceLayer: d.sourceLayer || null }
    } catch { oppSignal = undefined }

    const status = evaluateTrade(trade, a, modelProbPct, oppSignal)

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

// ============================================================================
// 📒 دفترِ RQS زنده (P7 · ایدهٔ #۳) — endpointهای افزودنی/سایه‌ای.
//    ثبتِ نتیجهٔ واقعیِ معاملهٔ کاربر و محاسبهٔ RQS+ زنده. مسیرِ /api/decision
//    دست‌نخورده می‌ماند؛ این‌ها فقط یک دفترِ مشاهده‌گر/یادگیرنده‌اند.
// ============================================================================

// ثبتِ نتیجهٔ یک معاملهٔ بسته‌شده. بدنه: {cardId, layerCode, dir, entry, exit, tpDist, slDist, pnl?}
app.post('/api/ledger/outcome', async (c) => {
  try {
    const body = await c.req.json().catch(() => null) as any
    if (!body) return c.json({ ok: false, error: 'داده ارسال نشده' }, 400)
    const rec = recordOutcome(body)
    const live = computeLiveRqs(rec.cardId, rec.layerCode)
    return c.json({ ok: true, recorded: rec, live })
  } catch (e: any) {
    return c.json({ ok: false, error: e?.message || 'خطا در ثبت' }, 400)
  }
})

// RQS+ زندهٔ یک لایهٔ مشخص.
app.get('/api/ledger/rqs/:cardId/:layer', (c) => {
  try {
    const cardId = c.req.param('cardId')
    const layer = c.req.param('layer')
    const live = computeLiveRqs(cardId, layer)
    return c.json({ ok: true, live, outcomes: outcomesOf(cardId, layer).length })
  } catch (e: any) {
    return c.json({ ok: false, error: e?.message || 'خطا' }, 400)
  }
})

// خلاصهٔ RQS+ زندهٔ همهٔ لایه‌های دارای داده (برای دفتر/گزارش).
app.get('/api/ledger/summary', (c) => {
  try {
    const rows = liveRqsSummary()
    const archived = rows.filter(r => r.shouldArchive).map(r => `${r.cardId}::${r.layerCode}`)
    return c.json({ ok: true, count: rows.length, archived, rows })
  } catch (e: any) {
    return c.json({ ok: false, error: e?.message || 'خطا' }, 400)
  }
})

// ============================================================================
// 🔬 کاوشگرِ اندیکاتور (P8 · ایدهٔ #۶) — endpointِ پژوهشیِ افزودنی/سایه‌ای.
//    همبستگیِ هر اندیکاتورِ رجیستری با «حرکتِ بعدیِ قیمت» را روی تاریخچهٔ ذخیره‌شده
//    (یا در نبودِ آن، کندلِ زندهٔ کافی) می‌سنجد و کاندیدهای فیلترِ احیا را به AI گزارش
//    می‌کند. خروجی «فقط برای تحقیق» است و هیچ تصمیمی را تغییر نمی‌دهد (مسیرِ تصمیم دست‌نخورده).
// ============================================================================

// کندل‌های موردِ کاوش را از تاریخچهٔ ذخیره‌شده می‌گیرد؛ اگر ناکافی بود، از منبعِ زندهٔ
// همان دارایی (طلا: fetchGold؛ یورو: yahooCandles) پُر می‌کند تا کفِ نمونه تأمین شود.
async function candlesForScan(asset: string, tf: string, want: number): Promise<Candle[]> {
  // ۱) تاریخچهٔ ذخیره‌شده (ترجیح: داده‌ی درازِ روی دیسک).
  try {
    const store = await getHistoryStore()
    const stored = await store.load(asset, tf, want)
    if (stored.length >= want) return stored
  } catch { /* بی‌اثر — سراغِ منبعِ زنده */ }

  // ۲) fallbackِ زنده.
  if (asset === 'XAUUSD') {
    const intervalMap: Record<string, string> = { M5: '5m', M15: '15m', M30: '30m', H1: '1h', H4: '1h', H8: '1h' }
    const interval = intervalMap[tf] || '15m'
    const range = tf === 'M5' ? '5d' : tf === 'M15' ? '1mo' : tf === 'H8' ? '1y' : '3mo'
    const { candles } = await fetchGold(interval, range)
    return candles
  } else {
    // یورو و بقیه از یاهو.
    const intervalMap: Record<string, string> = { M5: '5m', M15: '15m', M30: '30m', H1: '1h' }
    const interval = intervalMap[tf] || '15m'
    const range = tf === 'M5' ? '5d' : '1mo'
    const symbol = asset === 'EURUSD' ? 'EURUSD=X' : `${asset}=X`
    const { candles } = await yahooCandles(symbol, interval, range)
    return candles
  }
}

// کاوشِ یک (asset,tf) با افقِ اختیاری. خروجی ScanReport@v1.
//   /api/scanner/:asset?tf=M5&horizon=5&limit=1500
app.get('/api/scanner/:asset', async (c) => {
  const asset = (c.req.param('asset') || '').toUpperCase()
  const tf = (c.req.query('tf') || 'M15').toUpperCase()
  const horizon = Math.max(1, Math.min(50, parseInt(c.req.query('horizon') || '5', 10)))
  const limit = Math.max(200, Math.min(5000, parseInt(c.req.query('limit') || '1500', 10)))
  try {
    const candles = await candlesForScan(asset, tf, limit)
    if (!candles || candles.length < 30) {
      return c.json({ ok: false, error: `کندلِ کافی برای کاوش نیست (${candles?.length || 0})` }, 422)
    }
    const report = scanIndicators(asset, tf, candles, horizon)
    return c.json({ ok: true, report })
  } catch (e: any) {
    return c.json({ ok: false, error: e?.message || 'خطا در کاوش' }, 502)
  }
})

// فهرستِ اندیکاتورهای قابلِ کاوش (برای مستندات/AI).
app.get('/api/scanner', (c) => {
  return c.json({ ok: true, note: 'کاوشگرِ اندیکاتور P8 — از /api/scanner/:asset?tf=&horizon= استفاده کنید', example: '/api/scanner/XAUUSD?tf=M5&horizon=5' })
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
// rebase به spot می‌آید؛ بقیه مستقیماً از Yahoo. منطقِ تصمیم در `strategy_registry.ts`.
//
// 🔴 **به‌روزرسانیِ S396 — این توضیح کاملاً بازنویسی شد.**
//    نسخهٔ پیشینِ این کامنت از دورانِ S67/S73/S79/S81 مانده بود و سه چیزِ
//    **نادرست** می‌گفت که اگر تصحیح نمی‌شد، خواننده را گمراه می‌کرد:
//      ✗ «موتورِ برندهٔ S67 (+۳۰٬۴۹۰$)» — S67 سال‌ها پیش از سایت جدا شد.
//      ✗ «EURUSD (M15) منطقِ decideEurusd» — این تابع **هرگز صدا زده نمی‌شود**؛
//         تنها مسیرِ تصمیمِ سایت `runCard()` است (تأییدشده با جست‌وجوی سراسری).
//      ✗ «اسپرد طلا ۰.۴۰$ (۴ pip)» — هزینهٔ واقعیِ حسابِ دمو **۰.۳۳$/oz
//         (۳.۳ pip = ۳۳ point)** است، کمیسیونِ جدا ندارد، مارجین ۴۰$/لات،
//         `CONTRACT_SIZE=100`. همهٔ لایه‌های زندهٔ فعلی با همین ۳.۳ pip سنجیده شده‌اند.
//
//    وضعیتِ واقعیِ فعلی — **۵ کارت، ۵ لایه، هر ۵ روی XAUUSD**:
//      • XAUUSD-M5  → S355 (LPSB state-gate روی مولدِ S333) · RQS2 83.9*
//      • XAUUSD-M15 → S344 (Brooks trend-from-open · SHORT) · RQS2 89.0
//      • XAUUSD-M30 → S312 (رانشِ میانِ ماه · زمان-محور)     · RQS2 87.7
//      • XAUUSD-H1  → S356 (Brooks trend-resumption · علّی) · RQS2 79.6
//      • XAUUSD-H4  → S382 (مومنتومِ Williams %R · صفر فیلتر) · RQS2 79.2
//      (*بدهیِ بازِ برچسبِ کارت — بندِ ۳ سندِ `results/S396_…_AUDIT.md`)
//
// 🎯 معیارِ حاکم = **RQS2 v2.4** (هر ۱۱ دروازه). «سودِ خالص» تنها **پس از**
//    پاس‌شدنِ دروازه‌ها معنا دارد؛ لایهٔ سودده ولی رد‌شده حقِ اتصال ندارد.
//    ⚠️ عمداً **هیچ رقمِ سودِ خالص/RQS2 به کاربر نشان داده نمی‌شود** — قانونِ
//    طراحیِ سایت: «هیچ اطلاعِ اضافه‌ای به کاربر نشان داده نشود».
//    این اعداد فقط برای ما (توسعه‌دهنده) در همین کامنت‌ها زندگی می‌کنند.
//
// فیلدِ `layer`: 'scalp'=M5 · 'swing'=M15 · 'swing-m30'=M30 · 'htf'=H1/H4
// این برچسب در UI به کاربر نشان داده می‌شود تا بداند پیشنهاد از کدام سبک آمده است.
// هر کارت داده/منطق/localStorageِ مستقل دارد ⇒ کارت‌ها هیچ تداخلی با هم ندارند.
// فیلدِ `layer`: 'swing'=M15 ، 'scalp'=M5 ، 'swing-m30'=M30 ، 'placeholder'=قالبِ خام
//   (تایم‌فریمی که هنوز استراتژیِ اثبات‌شده‌ای ندارد — فقط داده/قیمت را نشان می‌دهد و
//    صریحاً می‌گوید «در دستِ تحقیق»؛ آماده برای گسترشِ آینده بدونِ تغییرِ معماری).
// فیلدِ `tf`: تایم‌فریمِ Yahoo برای دریافتِ کندل (5m/15m/30m/1m). فقط برای کارت‌های
//   غیرطلا کاربرد دارد (طلا تایم‌فریمش را از id می‌گیرد).
// ---------------------------------------------------------------------------
// ASSETS — فهرستِ کارت‌های سایت.
//
// 🔴 **پاک‌سازیِ حاکمیتیِ S396:** از **۸ کارت** به **۵ کارت** رسید.
//    قاعده: کارت وجود دارد اگر و فقط اگر ≥۱ لایه در `CARD_LAYERS` داشته باشد که
//    **روی همان کارت** حکمِ `ACCEPT` از RQS2 v2.4 گرفته باشد.
//    این جدول باید **همیشه** با `CARD_LAYERS` هم‌راستا بماند؛ ناهم‌راستایی =
//    «کارتِ توخالی» (کارتی که چیزی برای گفتن ندارد ولی وانمود می‌کند دارد).
//
//   فیلدِ `card` = کلیدِ `CARD_LAYERS` در `strategy_registry.ts` (منبعِ منطقِ تصمیم).
//   هر کارت داده/منطق/localStorageِ مستقل دارد ⇒ کارت‌ها هیچ تداخلی با هم ندارند.
//
//   کارت         لایهٔ صدرِ فهرست  RQS2    n     WR       جهت
//   XAUUSD-M5    S560            96.0    407   71.50%   LONG
//   XAUUSD-M15   S562 ⭐نو        95.3    438   70.78%   LONG   (پیش از S344/S431/S432)
//   XAUUSD-M30   S312            87.7    289   61.25%   LONG
//   XAUUSD-H1    S562 ⭐نو        96.0    254   68.90%   LONG   (پیش از S356/S431/S432)
//   XAUUSD-H4    S382            79.2    869   48.22%   LONG/SHORT
//   XAUUSD-H8    S950            80.0     —      —      LONG
//                S965 ⭐نو        82.2    146   54.79%   LONG/SHORT (دومین لایهٔ این کارت)
//   XAUUSD-H12   S800 ⭐نو        83.6    183   54.60%   LONG/SHORT
//   XAUUSD-D1    S800 ⭐نو        91.1     81   70.37%   LONG/SHORT
//
//   ⚠️ S800 روی **دو** کارت (D1 و H12) ACCEPT گرفت و طبقِ قانونِ MTF روی هر دو
//      وصل شد — ولی برخلافِ S562، این‌ها **دو حکمِ کاملاً مستقلِ تک-کارتی**اند:
//      هر کارت جداگانه با مسیر C (hold-out فیزیکی، n_trials=1) داوری شد و
//      جداگانه هر ۱۱ دروازه را پاس کرد. پیکربندی‌شان هم یکی نیست
//      (D1: p=55/q=20/rr=1.0/hold=21 · H12: p=21/q=30/rr=1.618/hold=34).
//      ⚠️ ولی همپوشانیِ تقویمی با S382-H4 بالاست (D1 ≈۸۱٪ · H12 ≈۹۱٪) و
//      خودِ D1↔H12 هم رویدادهای مشترک دارند ⇒ روی حسابِ واقعی صفِ FIFO
//      (allow_overlap=false) لازم است تا ریسکِ همزمان چندبرابر نشود.
//      تعمیم به تایم‌فریمِ دیگر **ممنوع**: H1/H3/H6 در آزمونِ نهایی REJECT
//      شدند و M1..M30 + H2 اصلاً توانِ آماری نداشتند (سندِ S800 §۸).
//
//   ⚠️ S562 روی **دو** کارت (M15 و H1) ACCEPT گرفت و طبقِ قانونِ MTF روی هر دو
//      وصل شد؛ ولی این **یک خانواده** است نه دو لبهٔ مستقل: jaccardِ روزانهٔ
//      M15↔H1 = ۰.۵۶ و با S560-M5 ≈ ۰.۵۱–۰.۵۴. اگر سه کارت هم‌زمان سیگنال
//      دادند، یک رویدادِ گپ است ⇒ سایزِ مشترک (سندِ S562 §۵).
//
//   ⚰️ **سه کارتِ EURUSD حذف شدند** (`EURUSD-M15`, `EURUSD-M30`, `EURUSD-H4`):
//      هیچ‌یک لایه‌ای با ACCEPTِ RQS2 نداشتند. سایت اکنون **تک‌ارزی (XAUUSD)** است.
//      این ضعف نیست — صداقتِ آماری است: پروژه هنوز روی EURUSD لبهٔ اثبات‌شده ندارد.
//      معماری دست‌نخورده است؛ افزودنِ کارتِ یورو در آینده = یک سطر در این جدول
//      + یک سطر در `CARD_LAYERS`.
//
//   ⚠️ توجه: `id: 'XAUUSD'` (بدونِ پسوند) عمداً حفظ شده است — کلیدِ تاریخیِ
//      localStorageِ کاربران و مسیرهای API به آن وابسته‌اند. تغییرش معاملاتِ
//      ثبت‌شدهٔ کاربر را یتیم می‌کرد. `card` آن `XAUUSD-M15` است.
//
//   فیلدِ `layer`: 'scalp'=M5 · 'swing'=M15 · 'swing-m30'=M30 · 'htf'=H1/H4
//      (برچسبِ سبک، برای اینکه کاربر بداند پیشنهاد از کدام افق آمده).
// ---------------------------------------------------------------------------
const ASSETS: { id: string; card: string; name: string; symbol: string; isGold: boolean; decimals: number; layer: 'swing' | 'scalp' | 'swing-m30' | 'placeholder' | 'htf'; tf?: string }[] = [
  { id: 'XAUUSD-M5',  card: 'XAUUSD-M5',  name: 'طلا / دلار — M5 (پنج‌دقیقه‌ای)',   symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'scalp' },
  { id: 'XAUUSD',     card: 'XAUUSD-M15', name: 'طلا / دلار — M15 (پانزده‌دقیقه‌ای)', symbol: 'GC=F',   isGold: true,  decimals: 2, layer: 'swing' },
  { id: 'XAUUSD-M30', card: 'XAUUSD-M30', name: 'طلا / دلار — M30 (سی‌دقیقه‌ای)',  symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'swing-m30' },
  { id: 'XAUUSD-H1',  card: 'XAUUSD-H1',  name: 'طلا / دلار — H1 (یک‌ساعته)',      symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  { id: 'XAUUSD-H4',  card: 'XAUUSD-H4',  name: 'طلا / دلار — H4 (چهارساعته)',     symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  // ⭐⭐ کارتِ نوِ S919 — «شوکِ مطلعِ هم‌راستا با قراردادِ بازار» (کینز)
  //    تنها تایم‌فریمِ ACCEPT این لایه **H6** است (RQS2=88.9 · n=106 · WR=55.66٪).
  //    کارتِ H3 با RQS2=16.0 رد شد ⇒ فقط همین یک کارت اضافه می‌شود (تعمیم ممنوع).
  //    کندلِ H6 از تجمیعِ H1×6 ساخته می‌شود (Yahoo تایم‌فریمِ ۶ساعته ندارد) —
  //    مرزهای UTC 0/6/12/18 که با کندل‌های MT5ِ بک‌تست دقیقاً هم‌تراز است
  //    (تأییدِ عددی: هر ۱۵۹۶۶ کندلِ XAUUSD_H6.csv مضربِ ۲۱۶۰۰ ثانیه‌اند).
  { id: 'XAUUSD-H6',  card: 'XAUUSD-H6',  name: 'طلا / دلار — H6 (شش‌ساعته)',      symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  // ⭐ کارتِ نوِ S950 — تنها تایم‌فریمِ ACCEPTِ لایهٔ «پس‌لرزهٔ جهش، هم‌راستا با رانش»
  //    (RQS2=80 · پایدار روی ۴ seed). کندلِ H8 از تجمیعِ H1×8 ساخته می‌شود
  //    (عینِ الگوی H4؛ Yahoo تایم‌فریمِ ۸ساعته ندارد). مرزهای UTC 0/8/16.
  { id: 'XAUUSD-H8',  card: 'XAUUSD-H8',  name: 'طلا / دلار — H8 (هشت‌ساعته)',      symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  // ⭐⭐ دو کارتِ نوی S800 — «فشردگی → گشایش». این لایه **دو حکمِ مستقلِ
  //    تک-کارتی** دارد (نه یک حکمِ استخری)، پس طبقِ قانونِ MTF هر دو
  //    تایم‌فریم باید روی سایت باشند: D1 (RQS2 91.1) و H12 (RQS2 83.6).
  //    هر دو از تجمیعِ H1 ساخته می‌شوند (×12 و ×24) — مرزهای UTC 00/12
  //    و نیمه‌شبِ UTC، عیناً هم‌تراز با کندل‌های MT5ِ بک‌تست.
  { id: 'XAUUSD-H12', card: 'XAUUSD-H12', name: 'طلا / دلار — H12 (دوازده‌ساعته)', symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  { id: 'XAUUSD-D1',  card: 'XAUUSD-D1',  name: 'طلا / دلار — D1 (روزانه)',        symbol: 'GC=F',     isGold: true,  decimals: 2, layer: 'htf' },
  // ⚰️ حذف‌شده در S396 — بی‌ACCEPT زیرِ RQS2 v2.4:
  //   { id: 'EURUSD-M15', card: 'EURUSD-M15', … }   ← S326
  //   { id: 'EURUSD-M30', card: 'EURUSD-M30', … }   ← S345 (RQS+ 91.7، ولی بی‌ACCEPT)
  //   { id: 'EURUSD-H4',  card: 'EURUSD-H4',  … }   ← S374 (REJECT/15.7)
]

// یادداشت: پیوستِ لایه‌های ثانویه اکنون درونِ runCard (strategy_registry) انجام
// می‌شود — otherLayers مستقیماً از خودِ لایه‌های احیاشدهٔ همان کارت ساخته می‌شود.
// تابعِ قدیمیِ attachSecondary/probeSecondaryLayers حذف شد (منطق به رجیستری منتقل شد).

// ---------------------------------------------------------------------------
// 🟦 P2 (webplan): ذخیره‌سازیِ سایه‌ایِ تاریخچه.
// ----------------------------------------------------------------------------
// «سایه‌ای (shadow)» طبقِ درسِ ایمنیِ webplan §۶: محاسبه/ذخیره می‌کند اما تصمیمِ
// نهایی را عوض نمی‌کند. به‌صورتِ fire-and-forget صدا زده می‌شود؛ هر خطایی بی‌صدا
// بلعیده می‌شود تا مسیرِ بحرانیِ قیمت هرگز نشکند (برابریِ /api/decision حفظ می‌شود).
//   نکته: فقط «کندل‌های بسته‌شده» ذخیره می‌شوند (نه کندلِ در حالِ شکل‌گیری) تا
//   تاریخچهٔ ذخیره‌شده repaint نشود — هم‌راستا با closedBars.
// نگاشتِ id کارتِ طلا → برچسبِ استانداردِ تایم‌فریم (کلیدِ افرازِ ذخیره‌سازی).
// ---------------------------------------------------------------------------
// GOLD_TF — نگاشتِ ماژولارِ «کارتِ طلا → (interval, range, gapSec)».
//
// هر کارتِ طلا تایم‌فریمِ مستقلِ خودش را از این جدول می‌گیرد. افزودنِ تایم‌فریمِ
// تازه فقط یک ردیف است و بقیهٔ کارت‌ها را دست نمی‌زند (ماژولاریتیِ ROS2).
// نکته: Yahoo برای interval=30m/1h فقط range محدود می‌دهد؛ مقادیرِ امن انتخاب شده.
//
// 🔴 **جابه‌جاییِ S396:** این جدول پیش‌تر **داخلِ** `decideAsset()` تعریف شده بود
//    و بنابراین فقط مسیرِ *تصمیم* از آن استفاده می‌کرد. مسیرِ **مدیریتِ معامله**
//    (`POST /api/trade-advice`) به‌جای آن `fetchGold('15m','1mo')` را
//    **هارد-کد** کرده بود ⇒ اگر کاربر روی کارتِ `H4` معامله ثبت می‌کرد،
//    توصیهٔ مدیریت با کندل‌های **M15** ساخته می‌شد: ATRِ اشتباه، روندِ اشتباه،
//    و در نتیجه SL/TPِ متحرکِ اشتباه.
//
//    این عیناً **اشتباهِ رایجِ ۶** («تنظیمِ یکسان برای همهٔ تایم‌فریم‌ها») بود، فقط
//    در لباسِ زیرساخت نه در لباسِ استراتژی — و دقیقاً در حساس‌ترین بخشِ سایت
//    (مدیریتِ معاملهٔ باز). با انتقالِ جدول به سطحِ ماژول، **هر دو مسیر** از یک
//    منبعِ حقیقتِ واحد تغذیه می‌شوند.
// ---------------------------------------------------------------------------
const GOLD_TF: Record<string, { interval: string; range: string; gap: number }> = {
  'XAUUSD':    { interval: '15m', range: '1mo', gap: 900 },
  'XAUUSD-M5': { interval: '5m',  range: '5d',  gap: 300 },
  'XAUUSD-M30':{ interval: '30m', range: '1mo', gap: 1800 },
  'XAUUSD-H1': { interval: '1h',  range: '3mo', gap: 3600 },
  'XAUUSD-H4': { interval: '1h',  range: '1y',  gap: 3600 },  // H4 از تجمیعِ H1 ساخته می‌شود
  // H8 (S950): ۱ سالِ H1 ≈ ۶۲۰۰ کندل ⇒ ≈۷۸۰ کندلِ H8 — برای گرم‌شدنِ ۹۱کندلیِ
  // σ_BV(89)/ATR(89) و EMA200ِ analyze هر دو کافی است (حاشیه ≈۸× نیازِ لایه).
  'XAUUSD-H8': { interval: '1h',  range: '1y',  gap: 3600 },  // H8 از تجمیعِ H1×8 ساخته می‌شود
  // S800 (H12 و D1): لایه ۱۰۲ کندلِ گرم‌شدن می‌خواهد (پنجرهٔ ۱۰۱کندلیِ رتبهٔ
  // چندکیِ ATR + کانالِ دانچیانِ ۵۵) و analyze هم EMA200 می‌خواهد. با بازهٔ
  // **۲ سالهٔ H1** (≈۱۴۵۰۰ کندل): H12 ≈۱۳۳۰ کندل و D1 ≈۷۲۰ کندل ⇒ برای D1
  // حاشیهٔ ≈۷× نیازِ لایه و ≈۳.۶× نیازِ EMA200. با range='1y' کارتِ D1 فقط
  // ≈۳۶۱ کندل داشت — هنوز کافی، ولی حاشیهٔ امنیتیِ کمتری برای تعطیلی‌ها
  // و حفرهٔ دادهٔ منبع.
  'XAUUSD-H12': { interval: '1h', range: '2y', gap: 3600 },  // H12 از تجمیعِ H1×12
  'XAUUSD-D1':  { interval: '1h', range: '2y', gap: 3600 },  // D1 از تجمیعِ H1×24
}

function tfLabelForGold(id: string): string {
  switch (id) {
    case 'XAUUSD-M5': return 'M5'
    case 'XAUUSD': return 'M15'
    case 'XAUUSD-M30': return 'M30'
    case 'XAUUSD-H1': return 'H1'
    case 'XAUUSD-H4': return 'H4'
    case 'XAUUSD-H8': return 'H8'
    case 'XAUUSD-H12': return 'H12'
    case 'XAUUSD-D1': return 'D1'
    default: return 'M15'
  }
}
// نگاشتِ interval یاهو (5m/15m/30m/1h) → برچسبِ استانداردِ تایم‌فریم.
function tfLabelFromYahoo(interval: string): string {
  switch (interval) {
    case '5m': return 'M5'
    case '15m': return 'M15'
    case '30m': return 'M30'
    case '1h': return 'H1'
    default: return interval.toUpperCase()
  }
}

function persistHistoryShadow(asset: string, tf: string, closed: Candle[]): void {
  if (!closed || closed.length < 2) return
  // آخرین عضو ممکن است هنوز مرزِ کامل نداشته باشد؛ closedBars قبلاً آن را پاک کرده،
  // پس اینجا کلِ آرایه «بسته‌شده» است. ذخیرهٔ ۳۰۰ کندلِ اخیر کافی است (بقیه از قبل هست).
  const slice = closed.length > 300 ? closed.slice(closed.length - 300) : closed
  void (async () => {
    try {
      const store = await getHistoryStore()
      await store.append(asset, tf, slice)
    } catch { /* سایه‌ای: خطا بی‌اثر است */ }
  })()
}

// تصمیمِ یک دارایی: کندلِ زنده → analyze → runCard (۴-حالته، رجیستریِ ماژولار).
async function decideAsset(a: typeof ASSETS[number], capital = 10000, riskPct = 1.0) {
  if (a.isGold) {
    const tfc = GOLD_TF[a.id] || GOLD_TF['XAUUSD']
    const { candles: rawCandles } = await fetchGold(tfc.interval, tfc.range)
    // H4/H8: Yahoo تایم‌فریمِ ۴/۸ساعته را مستقیم نمی‌دهد ⇒ از تجمیعِ کندل‌های H1 می‌سازیم.
    // S800: H12 = H1×12 و D1 = H1×24 (همان الگوی اثبات‌شدهٔ H4/H8).
    const aggFactor = a.id === 'XAUUSD-H4' ? 4 : a.id === 'XAUUSD-H8' ? 8
      : a.id === 'XAUUSD-H12' ? 12 : a.id === 'XAUUSD-D1' ? 24 : 1
    const candles = aggFactor > 1 ? aggregateCandles(rawCandles, aggFactor) : rawCandles
    // آستانهٔ حداقلِ کندل بسته به تایم‌فریم (H4 داده کمتری دارد، اما برای EMA200 کافی است).
    // H8: لایهٔ S950 خودش ۹۱+۲ کندل گرم‌شدن می‌خواهد ⇒ کفِ سخت‌گیرانه‌ترِ ۱۱۰.
    // H12/D1 (S800): لایه خودش ۱۰۲ کندلِ گرم‌شدن می‌خواهد (پنجرهٔ ۱۰۱ +
    // تأخیرِ ۱) ⇒ کفِ ۱۱۰ کندل، عینِ منطقِ H8. پایین‌تر از این، خودِ لایه پیامِ
    // «دادهٔ ناکافی» می‌دهد و هیچ سیگنالی صادر نمی‌کند (رفتارِ ایمن).
    const minBars = a.id === 'XAUUSD-H4' ? 60
      : (a.id === 'XAUUSD-H8' || a.id === 'XAUUSD-H12' || a.id === 'XAUUSD-D1') ? 110 : 220
    if (candles.length < minBars) throw new Error('داده کافی برای تحلیل نیست')
    let spot: SpotPrice | null = null
    try { spot = await getSpotGold() } catch {}
    const merged = rebaseFuturesToSpot(candles, spot, tfc.gap)
    const useCandles = merged.candles
    const result = analyze(useCandles)
    // 🔧 رفعِ باگِ repainting: منطقِ ماشهٔ سیگنال روی «کندل‌های بسته‌شده» اجرا می‌شود
    //   (معادلِ shift(1)ِ بک‌تست)، نه کندلِ زندهٔ در حالِ شکل‌گیری. result.price هم‌چنان قیمتِ
    //   زنده است ⇒ entry روی «open کندلِ بعد» می‌نشیند، اما شرطِ سیگنال روی کندلِ بستهٔ قبلی.
    // ⚠️ H8 (S950): مرزِ «کندلِ بسته» برای کندلِ تجمیعی باید طولِ واقعیِ سطل (۸h) باشد،
    //   نه gapِ منبع (۱h) — وگرنه کندلِ H8ِ در حالِ شکل‌گیری پس از ساعتِ اولش
    //   «بسته» دیده می‌شد و سیگنالِ S950 روی r ناقص می‌نشست (look-ahead نسبت
    //   به بک‌تستی که فقط کندلِ کامل دید). رفتارِ کارت‌های دیگر دست‌نخورده.
    // ⚠️ همان منطق برای H12/D1 (S800): مرزِ «کندلِ بسته» باید طولِ واقعیِ سطل
    //   (۱۲h / ۲۴h) باشد، وگرنه کندلِ در حالِ شکل‌گیری پس از ساعتِ اولش «بسته»
    //   دیده می‌شد و شرطِ شکستِ دانچیان روی closeِ ناقص می‌نشست ⇒ look-ahead
    //   نسبت به بک‌تستی که فقط کندلِ کامل دید (درست مانندِ اشتباهِ رفع‌شدهٔ H8).
    const sigGap = a.id === 'XAUUSD-H8' ? tfc.gap * 8
      : a.id === 'XAUUSD-H12' ? tfc.gap * 12
      : a.id === 'XAUUSD-D1' ? tfc.gap * 24 : tfc.gap
    const sig = closedBars(useCandles, sigGap)
    const lastClosed = sig[sig.length - 1]
    const goldUtcHour = new Date(lastClosed.time * 1000).getUTCHours()
    // 🟦 P2 سایه‌ای: ذخیرهٔ تاریخچهٔ کندل‌های بسته‌شده (بی‌اثر بر تصمیم).
    persistHistoryShadow('XAUUSD', tfLabelForGold(a.id), sig)
    // --- مغزِ تصمیم: رجیستریِ ماژولار (لایه‌های احیاشدهٔ همین کارت) ---
    const ctx: LayerContext = {
      cardId: a.card, a: result, candles: sig,
      utcHour: goldUtcHour, times: sig.map(k => k.time), capital, riskPct,
    }
    const dec = runCard(ctx)
    logSignal(a.card, dec, result.price, lastClosed.time)   // 🔎 لاگِ سیگنال (User Note)
    // 🛰️ P3.5 سایه‌ای: تشخیصِ رژیم (فقط گزارش؛ بی‌اثر بر dec/تصمیم).
    const regime = safeRegime('XAUUSD', tfLabelForGold(a.id), sig)
    // 🏛️ P4.5 سایه‌ای: حکمِ شورای لایه‌ها (فقط گزارش؛ تصمیمِ کارت هنوز از dec می‌آید).
    const council = safeCouncil(a.card, dec)
    return { asset: a.id, name: a.name, symbol: a.symbol, decimals: a.decimals, layer: a.layer,
      price: result.price, lastCandleTime: useCandles[useCandles.length - 1].time, decision: dec, regime, council,
      spot: spot ? { price: spot.price, ageSec: spot.ageSec, source: spot.source } : null }
  }
  // EURUSD: کندلِ Yahoo + به‌روزرسانیِ کندلِ جاری با قیمتِ زنده (رفعِ اختلافِ لحظه‌ای).
  // تایم‌فریم از فیلدِ `tf` (M15/M30). منطقِ تصمیم = رجیستریِ ماژولار (S326/S327).
  const tf = a.tf || '15m'
  // --- نگاشتِ ماژولارِ تایم‌فریمِ یورو → (interval, range, gapSec, aggregate, minBars) ---
  // ⭐ افزوده در این نشست برای کارتِ نوسازِ EURUSD-H4. پیش‌تر این مسیر فقط
  //   M15/M30 را می‌شناخت و `range` ثابتِ '1mo' بود.
  //   Yahoo تایم‌فریمِ ۴ساعته را **مستقیم نمی‌دهد** ⇒ عیناً همان راه‌حلِ کارتِ طلای H4:
  //   کندلِ H1 با بازهٔ ۱ساله گرفته و با aggregateCandles(·,4) به H4 تجمیع می‌شود.
  //   minBars برای H4 پایین‌تر است چون هر کندل ۴ ساعت است (همان ۶۰ کندلِ کارتِ طلا).
  const EUR_TF: Record<string, { interval: string; range: string; gap: number; agg: number; minBars: number }> = {
    '5m':  { interval: '5m',  range: '5d',  gap: 300,   agg: 1, minBars: 220 },
    '15m': { interval: '15m', range: '1mo', gap: 900,   agg: 1, minBars: 220 },
    '30m': { interval: '30m', range: '1mo', gap: 1800,  agg: 1, minBars: 220 },
    '1h':  { interval: '1h',  range: '3mo', gap: 3600,  agg: 1, minBars: 220 },
    '4h':  { interval: '1h',  range: '1y',  gap: 14400, agg: 4, minBars: 60  },
  }
  const etf = EUR_TF[tf] || EUR_TF['15m']
  const gapForTf = (_t: string) => etf.gap
  const { candles: rawEur } = await yahooCandles(a.symbol, etf.interval, etf.range)
  const candles = etf.agg > 1 ? aggregateCandles(rawEur, etf.agg) : rawEur
  const minBars = etf.minBars
  if (candles.length < minBars) throw new Error('داده کافی برای تحلیل نیست')
  let live: number | null = null, liveAge = 0, liveSrc = ''
  try { const q = await getLiveQuote(a.symbol); live = q.price; liveAge = q.ageSec; liveSrc = q.source } catch {}
  const merged = mergeLiveQuote(candles, live, gapForTf(tf))
  const useCandles = merged.candles
  const result = analyze(useCandles)
  // 🔧 رفعِ باگِ repainting (هم‌سان با طلا): ماشهٔ سیگنال روی کندل‌های بسته‌شده.
  const sig = closedBars(useCandles, gapForTf(tf))
  const lastClosed = sig[sig.length - 1]
  const eurUtcHour = new Date(lastClosed.time * 1000).getUTCHours()
  // 🟦 P2 سایه‌ای: ذخیرهٔ تاریخچهٔ کندل‌های بسته‌شده (بی‌اثر بر تصمیم).
  persistHistoryShadow('EURUSD', tfLabelFromYahoo(tf), sig)
  const ctx: LayerContext = {
    cardId: a.card, a: result, candles: sig,
    utcHour: eurUtcHour, times: sig.map(k => k.time), capital, riskPct,
  }
  const dec = runCard(ctx)
  logSignal(a.card, dec, result.price, lastClosed.time)   // 🔎 لاگِ سیگنال (User Note)
  // 🛰️ P3.5 سایه‌ای: تشخیصِ رژیم (فقط گزارش؛ بی‌اثر بر dec/تصمیم).
  const regime = safeRegime('EURUSD', tfLabelFromYahoo(tf), sig)
  // 🏛️ P4.5 سایه‌ای: حکمِ شورای لایه‌ها (فقط گزارش؛ تصمیمِ کارت هنوز از dec می‌آید).
  const council = safeCouncil(a.card, dec)
  return { asset: a.id, name: a.name, symbol: a.symbol, decimals: a.decimals, layer: a.layer,
    price: result.price, lastCandleTime: useCandles[useCandles.length - 1].time, decision: dec, regime, council,
    spot: live != null ? { price: live, ageSec: liveAge, source: liveSrc } : null }
}

// 🏛️ P4.5: پوششِ ایمنِ شورای لایه‌ها — اگر شورا به هر دلیلی خطا داد، null برمی‌گرداند
//   تا تصمیم هرگز مختل نشود. حالتِ کاملاً سایه‌ای (فقط گزارش).
function safeCouncil(cardId: string, dec: any) {
  try { return convene(cardId, dec) } catch { return null }
}

// 🛰️ P3.5: پوششِ ایمنِ رادارِ رژیم — اگر رادار به هر دلیلی خطا داد (دادهٔ ناکافی و…)،
//   null برمی‌گرداند تا تصمیم هرگز مختل نشود. حالتِ کاملاً سایه‌ای.
function safeRegime(asset: string, tf: string, candles: any[]) {
  try {
    if (!Array.isArray(candles) || candles.length < 60) return null
    return detectRegime(asset, tf, candles)
  } catch { return null }
}

// یادداشت: تابعِ قدیمیِ placeholderDecision حذف شد — پس از حذفِ کارت‌های بدونِ
// لایه (EURUSD-M1 و …)، هیچ کارتی «قالبِ خام» نیست؛ هر ۷ کارت لایهٔ احیاشدهٔ
// ACCEPTED دارند و از طریقِ runCard تصمیم می‌گیرند.

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
// 🔎 لاگِ سیگنال (User Note) — مشاهدهٔ همهٔ ENTRY/APPROACHING با زمانِ دقیق و کشفِ تناقض.
//   /api/signal-log            → آخرین رویدادها (پیش‌فرض ۲۰۰)
//   /api/signal-log/conflicts  → جفت‌های خرید/فروشِ متناقضِ همان کارت در بازهٔ کوتاه
//   /api/signal-log/clear      → پاک‌کردنِ بافر (برای شروعِ تازهٔ مانیتور)
// ---------------------------------------------------------------------------
app.get('/api/signal-log', (c) => {
  const limit = Math.max(1, Math.min(800, parseInt(c.req.query('limit') || '200', 10)))
  const card = c.req.query('card')
  let rows = getLog(800)
  if (card) rows = rows.filter(r => r.card === card.toUpperCase())
  return c.json({ ok: true, count: rows.length, entries: rows.slice(-limit) })
})
app.get('/api/signal-log/conflicts', (c) => {
  const win = Math.max(1, Math.min(3600, parseInt(c.req.query('window') || '180', 10)))
  return c.json({ ok: true, windowSec: win, conflicts: findConflicts(win) })
})
app.get('/api/signal-log/clear', (c) => { clearLog(); return c.json({ ok: true, cleared: true }) })

// ---------------------------------------------------------------------------
// 🟦 P2 (webplan) — endpointهای گرهِ قیمت: تاریخچهٔ ذخیره‌شده + Heartbeat.
//   افزودنی‌اند و مسیرِ تصمیم را دست نمی‌زنند.
// ---------------------------------------------------------------------------
// خواندنِ تاریخچهٔ ذخیره‌شده (ring-buffer) برای یک (asset,tf).
//   /api/history/:asset?tf=M5&limit=500
//   asset: XAUUSD | EURUSD ؛ tf: M5|M15|M30|H1|H4
app.get('/api/history/:asset', async (c) => {
  const asset = (c.req.param('asset') || '').toUpperCase()
  const tf = (c.req.query('tf') || 'M15').toUpperCase()
  const limit = Math.max(1, Math.min(5000, parseInt(c.req.query('limit') || '500', 10)))
  if (asset !== 'XAUUSD' && asset !== 'EURUSD') {
    return c.json({ ok: false, error: `دارایی ناشناخته: ${asset}` }, 404)
  }
  try {
    const store = await getHistoryStore()
    const candles = await store.load(asset, tf, limit)
    const total = await store.count(asset, tf)
    const last = await store.lastTime(asset, tf)
    return c.json({
      ok: true, asset, tf,
      total, returned: candles.length,
      lastClosedTime: last,
      candles: candles.map(k => ({ t: k.time, o: k.open, h: k.high, l: k.low, c: k.close, v: k.volume || 0 })),
    })
  } catch (e: any) {
    return c.json({ ok: false, error: e?.message || 'خطا' }, 502)
  }
})

// Heartbeat: وضعیتِ سلامتِ قیمتِ زندهٔ یک دارایی (ایدهٔ #۷).
//   /api/price-health/:asset  → { ok, stale, liveAgeSec, source, note, storedBars }
app.get('/api/price-health/:asset', async (c) => {
  const id = (c.req.param('asset') || '').toUpperCase()
  const a = ASSETS.find(x => x.id === id)
  if (!a) return c.json({ ok: false, error: `دارایی ناشناخته: ${id}` }, 404)
  try {
    // قیمتِ زندهٔ سبک (بدونِ محاسبهٔ سنگینِ سیگنال).
    let ageSec = Infinity, source = 'unknown'
    if (a.isGold) {
      const s = await getSpotGold()
      ageSec = s.ageSec; source = s.source
    } else {
      const q = await getLiveQuote(a.symbol)
      ageSec = q.ageSec; source = q.source
    }
    const health = computeHealth(ageSec, source)
    // چند کندل برای این کارت ذخیره شده (دیدِ پوششِ تاریخچه).
    let storedBars = 0
    try {
      const store = await getHistoryStore()
      const asset = a.isGold ? 'XAUUSD' : 'EURUSD'
      const tf = a.isGold ? tfLabelForGold(a.id) : tfLabelFromYahoo(a.tf || '15m')
      storedBars = await store.count(asset, tf)
    } catch { /* بی‌اثر */ }
    return c.json({ ok: true, asset: a.id, at: Date.now(), ...health, storedBars })
  } catch (e: any) {
    return c.json({ ok: false, asset: a.id, error: e?.message || 'خطا' }, 502)
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
  <script type="module" src="/static/ui/badges.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>`

export default app
