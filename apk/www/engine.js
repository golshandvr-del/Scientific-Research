/* ============================================================================
 * engine.js — موتورِ تصمیمِ زندهٔ APK به زبانِ JavaScript خالص (معماریِ افزونه‌ای)
 * ----------------------------------------------------------------------------
 * 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود):
 *    هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.
 *    تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
 *    WR فقط یک عددِ گزارشی است، نه هدف و نه قید.
 * ----------------------------------------------------------------------------
 * چرا این فایل ساخته شد (رفعِ ایرادِ اساسیِ گیرکردن روی «بارگذاریِ مفسرِ پایتون»):
 *   نسخهٔ قبلی APK از Pyodide (~۲۰MB WASM+numpy+pandas از CDN) استفاده می‌کرد که
 *   درونِ WebView کند/شکننده بود و بدونِ timeout/fallback برای همیشه معلق می‌ماند.
 *   منطقِ تصمیم صرفاً چند اندیکاتورِ سادهٔ ریاضی است؛ اینجا «بایت‌به‌بایت هم‌رفتار»
 *   با live_engine.py به JS پورت شده تا اپ فوری، آفلاین و یکسان با پایتون کار کند.
 * ----------------------------------------------------------------------------
 * 🧩 معماریِ افزونه‌ای (پاسخ به User note2 «آیا افزودنِ استراتژیِ جدید آسان است؟»):
 *   موتور اکنون یک «رجیستریِ استراتژی» است. هر استراتژی یک ماژولِ مستقل با ساختارِ
 *   استاندارد است:
 *       { id, name, asset, describe(ctx)->reasons[], evaluate(ctx)->decision|null }
 *   افزودنِ استراتژیِ جدید = ساختنِ یک فایلِ کوچک در www/strategies/ و صدا زدنِ
 *   GoldEngine.registerStrategy(obj). هیچ نیازی به دستکاریِ بدنهٔ liveDecision نیست.
 *   جزئیاتِ کامل: www/strategies/README.md
 * ==========================================================================*/
'use strict';

/* ---------------------------------------------------------------------------
 * پارامترهای رسمیِ رکورد (منبعِ حقیقت: live_engine.py — بدونِ تغییر)
 * ------------------------------------------------------------------------- */
const RECORD = { xau_long: 51880.0, xau_short: 34542.0, eurusd: 9223.0, total: 95645.0 };

// مغزِ SHORT طلا — s118 «بگذار بردها بدوند»
const SHORT_PARAMS = { sl_pip: 70, tp_pip: 800, max_hold: 48, be_trigger_pip: 6, trail_pip: 6 };
// مغزِ LONG طلا — S67/S14 (mid-MA، خروجِ رونددار)
const LONG_PARAMS  = { sl_pip: 60, tp_pip: 400, max_hold: 32, be_trigger_pip: 6, trail_pip: 12 };

// EURUSD — S73 session-open drift (ساعتِ ۰ UTC صعودی)
const EURUSD_ENTRY_HOUR = 0;
const EURUSD_SL_PIP = 25;
const EURUSD_TP_PIP = 45;

// pip هر دارایی — دقیقاً مطابقِ scalp_engine.ASSETS
const PIP = { XAUUSD: 0.10, EURUSD: 0.0001 };

/* ===========================================================================
 * اندیکاتورها — پورتِ دقیقِ engine/indicators.py (بدونِ look-ahead)
 * =========================================================================*/

// SMA ساده — معادلِ series.rolling(period).mean()  (اولین (period-1) مقدار = NaN)
function sma(values, period) {
  const out = new Array(values.length).fill(NaN);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

// EMA — معادلِ series.ewm(span=period, adjust=False).mean()
function ema(values, period) {
  const alpha = 2 / (period + 1);
  return emaAlpha(values, alpha);
}

function emaAlpha(values, alpha) {
  const out = new Array(values.length).fill(NaN);
  if (values.length === 0) return out;
  let prev = values[0];
  out[0] = prev;
  for (let i = 1; i < values.length; i++) {
    prev = alpha * values[i] + (1 - alpha) * prev;
    out[i] = prev;
  }
  return out;
}

// RSI (Wilder) — معادلِ محاسبهٔ rsi در indicators.py
function rsi(closes, period = 14) {
  const n = closes.length;
  const out = new Array(n).fill(NaN);
  if (n < period + 1) return out;
  const gains = new Array(n).fill(0);
  const losses = new Array(n).fill(0);
  for (let i = 1; i < n; i++) {
    const d = closes[i] - closes[i - 1];
    gains[i] = d > 0 ? d : 0;
    losses[i] = d < 0 ? -d : 0;
  }
  // میانگینِ اولیه (SMA روی period)
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i <= period; i++) { avgGain += gains[i]; avgLoss += losses[i]; }
  avgGain /= period; avgLoss /= period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < n; i++) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

// ATR (Wilder) — معادلِ atr در indicators.py
function atr(highs, lows, closes, period = 14) {
  const n = closes.length;
  const out = new Array(n).fill(NaN);
  if (n < period + 1) return out;
  const tr = new Array(n).fill(0);
  tr[0] = highs[0] - lows[0];
  for (let i = 1; i < n; i++) {
    tr[i] = Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i] - closes[i - 1])
    );
  }
  let prev = 0;
  for (let i = 1; i <= period; i++) prev += tr[i];
  prev /= period;
  out[period] = prev;
  for (let i = period + 1; i < n; i++) {
    prev = (prev * (period - 1) + tr[i]) / period;
    out[i] = prev;
  }
  return out;
}

// میانهٔ سه‌MA (mid-MA) — پورتِ دقیقِ live_engine._mid_ma:
//   میانگینِ EMA50, EMA100, SMA200 با np.nanmean (یعنی NaNها نادیده گرفته می‌شوند،
//   و فقط اگر هر سه NaN باشند خروجی NaN است).
function midMA(closes) {
  const e50 = ema(closes, 50);
  const e100 = ema(closes, 100);
  const s200 = sma(closes, 200);
  const n = closes.length;
  const out = new Array(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    let sum = 0, cnt = 0;
    if (!Number.isNaN(e50[i]))  { sum += e50[i];  cnt++; }
    if (!Number.isNaN(e100[i])) { sum += e100[i]; cnt++; }
    if (!Number.isNaN(s200[i])) { sum += s200[i]; cnt++; }
    out[i] = cnt > 0 ? sum / cnt : NaN;
  }
  return out;
}

/* ===========================================================================
 * ابزارِ کمکی
 * =========================================================================*/
function distancePips(price, level, pip) { return Math.abs(price - level) / pip; }
const r2 = (x) => Math.round(x * 100) / 100;
const r5 = (x) => Math.round(x * 1e5) / 1e5;

/* ===========================================================================
 * ساختنِ «کانتکستِ» مشترک — همهٔ اندیکاتورها یک‌بار محاسبه و به استراتژی‌ها داده می‌شوند.
 * این ctx ورودیِ استانداردِ هر استراتژی است.
 * =========================================================================*/
function buildContext(candles, asset) {
  const closes = candles.map(c => c.close);
  const highs  = candles.map(c => c.high);
  const lows   = candles.map(c => c.low);
  const n = candles.length;

  const p = closes[n - 1];
  const pPrev = closes[n - 2];
  const mid = midMA(closes);
  const midNow = mid[n - 1];
  const midPrev = mid[n - 2];

  const e50arr = ema(closes, 50);
  const s200arr = sma(closes, 200);
  const e50 = e50arr[n - 1];
  const e200 = s200arr[n - 1];
  const rsiArr = rsi(closes, 14);
  const rsiVal = rsiArr[n - 1];
  const atrArr = atr(highs, lows, closes, 14);
  const atrVal = !Number.isNaN(atrArr[n - 1]) ? atrArr[n - 1] : Math.abs(p) * 0.002;
  const pip = PIP[asset] != null ? PIP[asset] : (asset === 'XAUUSD' ? 0.1 : 0.0001);

  const indicators = {
    price: r5(p),
    mid_ma3: r5(midNow),
    ema50: r5(e50),
    sma200: r5(e200),
    rsi14: (rsiVal === rsiVal) ? Math.round(rsiVal * 10) / 10 : null,
    atr14: r5(atrVal),
    dist_to_mid_pips: Math.round(distancePips(p, midNow, pip) * 10) / 10,
  };

  const crossUp = pPrev <= midPrev && p > midNow;   // ماشهٔ LONG
  const crossDn = pPrev >= midPrev && p < midNow;   // ماشهٔ SHORT

  return {
    asset, candles, closes, highs, lows, n, pip,
    price: p, pricePrev: pPrev,
    midNow, midPrev, e50, e200, rsiVal, atrVal,
    crossUp, crossDn, indicators,
    // helperهای در دسترسِ استراتژی‌ها
    distancePips, r2, r5,
    SHORT_PARAMS, LONG_PARAMS,
    EURUSD_ENTRY_HOUR, EURUSD_SL_PIP, EURUSD_TP_PIP,
  };
}

/* ===========================================================================
 * 🧩 رجیستریِ استراتژی‌ها
 * ---------------------------------------------------------------------------
 * هر استراتژی: { id, name, asset, enabled?, describe?(ctx), evaluate(ctx) }
 *   • asset: 'XAUUSD' | 'EURUSD' | '*' (برای همه)
 *   • evaluate(ctx): یا یک decision با state==='ENTRY' برمی‌گرداند، یا null.
 *     اگر چند استراتژی هم‌زمان ENTRY بدهند، ترتیبِ ثبت (priority) تعیین‌کننده است.
 * =========================================================================*/
const STRATEGIES = [];

function registerStrategy(strat) {
  if (!strat || !strat.id || typeof strat.evaluate !== 'function') {
    throw new Error('registerStrategy: استراتژی باید {id, evaluate} داشته باشد.');
  }
  // جلوگیری از ثبتِ تکراری با همان id
  const idx = STRATEGIES.findIndex(s => s.id === strat.id);
  if (idx >= 0) STRATEGIES[idx] = strat; else STRATEGIES.push(strat);
  return STRATEGIES.length;
}

function listStrategies(asset) {
  return STRATEGIES
    .filter(s => s.enabled !== false)
    .filter(s => !asset || s.asset === '*' || s.asset === asset)
    .map(s => ({ id: s.id, name: s.name, asset: s.asset }));
}

function clearStrategies() { STRATEGIES.length = 0; }

/* ===========================================================================
 * تصمیمِ زندهٔ ماشینِ حالتِ ۴-وضعیتی — اکنون بر پایهٔ رجیستری
 * =========================================================================*/
function liveDecision(candles, asset = 'XAUUSD', openPosition = null) {
  if (!candles || candles.length < 210) {
    return {
      state: 'NEUTRAL', asset,
      headline: 'داده کافی نیست (کمتر از ۲۱۰ کندل).',
      reasons: ['برای MA200 و ATR به تاریخچهٔ بیشتری نیاز است.'],
      indicators: {},
    };
  }

  const ctx = buildContext(candles, asset);
  const { indicators, midNow, price, pip } = ctx;

  // ── معاملهٔ باز داریم → MANAGE ────────────────────────────────────────
  if (openPosition) {
    return manageDecision(asset, openPosition, indicators, midNow, price, pip);
  }

  // ── اجرای همهٔ استراتژی‌های فعالِ این دارایی؛ اولین ENTRY برنده است ──────
  const activeIds = [];
  for (const strat of STRATEGIES) {
    if (strat.enabled === false) continue;
    if (strat.asset !== '*' && strat.asset !== asset) continue;
    activeIds.push(strat.id);
    let dec = null;
    try { dec = strat.evaluate(ctx); } catch (e) { dec = null; }
    if (dec && dec.state === 'ENTRY') {
      dec.asset = asset;
      dec.indicators = indicators;
      dec.strategy_id = strat.id;
      dec.strategy_name = strat.name;
      return dec;
    }
  }

  // ── APPROACHING: نزدیکِ ماشه (منطقِ عمومیِ mid-MA) ─────────────────────
  const distPips = distancePips(price, midNow, pip);
  const nearThr = asset === 'XAUUSD' ? 15 : 8;
  if (distPips <= nearThr) {
    const sideHint = price < midNow ? 'صعودی (LONG)' : 'نزولی (SHORT)';
    return {
      state: 'APPROACHING', asset,
      headline: `احتمالِ نزدیک‌شدن به سیگنالِ ${sideHint}.`,
      reasons: [
        `قیمت تنها ${distPips.toFixed(1)} pip با میانهٔ سه‌MA (${midNow.toFixed(2)}) فاصله دارد.`,
        'منتظرِ «قطعِ قطعیِ» میانه با بسته‌شدنِ کندل باش (تأییدِ ماشه).',
      ],
      waiting_for: [
        'بسته‌شدنِ یک کندل آن‌سوی میانهٔ سه‌MA.',
        `RSI فعلی=${indicators.rsi14} — تأییدِ جهت.`,
      ],
      indicators,
      active_strategies: activeIds,
    };
  }

  // ── NEUTRAL ────────────────────────────────────────────────────────────
  return {
    state: 'NEUTRAL', asset,
    headline: 'خنثی — هنوز شرایطِ ورود فراهم نیست.',
    reasons: [
      `قیمت (${price.toFixed(2)}) ${distPips.toFixed(1)} pip از میانهٔ سه‌MA (${midNow.toFixed(2)}) دور است؛ ماشهٔ قطع فعال نشده.`,
      `چیدمانِ MA: EMA50=${ctx.e50.toFixed(2)}، SMA200=${ctx.e200.toFixed(2)}.`,
      `RSI14=${indicators.rsi14} — خارج از ناحیهٔ تصمیم.`,
    ],
    indicators,
    active_strategies: activeIds,
  };
}

// وضعیتِ MANAGE — پورتِ دقیقِ live_engine._manage_decision
function manageDecision(asset, pos, indicators, midNow, p, pip) {
  const side = pos.side || 'long';
  const entry = +pos.entry || p;
  const sl = +pos.sl || entry;
  const tp = +pos.tp || entry;
  const profitPips = ((side === 'long' ? (p - entry) : (entry - p))) / pip;

  const actions = [];
  const regimeFlip = (side === 'long' && p < midNow) || (side === 'short' && p > midNow);
  if (regimeFlip) {
    actions.push({
      type: 'CLOSE',
      text: `⚠️ قیمت به سمتِ مخالفِ میانهٔ سه‌MA (${midNow.toFixed(2)}) برگشت — روند در حالِ تغییر است. پیشنهاد: معامله را ببند و سود/زیانِ فعلی را قطعی کن.`,
    });
  }
  const beTrigger = side === 'short' ? SHORT_PARAMS.be_trigger_pip : LONG_PARAMS.be_trigger_pip;
  if (profitPips >= beTrigger && ((side === 'long' && sl < entry) || (side === 'short' && sl > entry))) {
    actions.push({
      type: 'MOVE_SL',
      text: `✅ سود به ${profitPips.toFixed(0)} pip رسید — SL را به نقطهٔ ورود (${entry.toFixed(2)}) منتقل کن (ریسک صفر شد).`,
      new_sl: r2(entry),
    });
  }
  if (profitPips >= 40) {
    const trail = 20 * pip;
    const newSl = side === 'long' ? (p - trail) : (p + trail);
    actions.push({
      type: 'TRAIL_SL',
      text: `📈 سودِ بزرگ (${profitPips.toFixed(0)} pip) — SL را دنبال کن به ${newSl.toFixed(2)} تا سود قفل شود، ولی بگذار برد بدود (TP دور).`,
      new_sl: r2(newSl),
    });
  }
  if (actions.length === 0) {
    actions.push({
      type: 'HOLD',
      text: `معامله را نگه دار. سودِ فعلی ${profitPips.toFixed(0)} pip. هنوز نه به BE رسیده‌ایم نه رژیم تغییر کرده.`,
    });
  }

  return {
    state: 'MANAGE', asset, side,
    headline: `مدیریتِ معاملهٔ ${side === 'long' ? 'خرید' : 'فروش'} — سودِ فعلی ${profitPips.toFixed(0)} pip.`,
    position: { side, entry, sl, tp, profit_pips: Math.round(profitPips * 10) / 10 },
    actions,
    indicators,
  };
}

/* ===========================================================================
 * در دسترس قرار دادن برای app.js و برای فایل‌های استراتژی
 * =========================================================================*/
window.GoldEngine = {
  liveDecision,
  RECORD,
  // 🧩 API رجیستری (قلبِ افزونه‌پذیری)
  registerStrategy,
  listStrategies,
  clearStrategies,
  buildContext,
  // اندیکاتورها (برای تست/بک‌تستِ سبک و استفادهٔ استراتژی‌ها)
  sma, ema, rsi, atr, midMA,
  SHORT_PARAMS, LONG_PARAMS, PIP,
};
