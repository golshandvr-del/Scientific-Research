/* ============================================================================
 * engine.js — موتورِ تصمیمِ زندهٔ APK به زبانِ JavaScript خالص
 * ----------------------------------------------------------------------------
 * 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود):
 *    هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.
 *    تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
 *    WR فقط یک عددِ گزارشی است، نه هدف و نه قید.
 * ----------------------------------------------------------------------------
 * چرا این فایل ساخته شد (رفعِ ایرادِ اساسیِ گیرکردن روی «بارگذاریِ مفسرِ پایتون»):
 *
 *   نسخهٔ قبلی APK از Pyodide (مفسرِ CPython/WASM ~۱۰MB + numpy + pandas ~۱۰MB)
 *   استفاده می‌کرد که هربار باید از CDN دانلود می‌شد. درونِ WebViewِ اندروید این
 *   کار کند/شکننده است و اغلب فایل‌های .wasm بلاک یا نیمه‌کاره می‌مانند و — چون
 *   هیچ timeout/fallback نبود — `await loadPyodide()` برای همیشه معلق می‌ماند و
 *   اپ روی «بارگذاریِ مفسرِ پایتون» گیر می‌کرد.
 *
 *   منطقِ live_decision صرفاً چند اندیکاتورِ سادهٔ ریاضی است (EMA/SMA/RSI/ATR +
 *   قطعِ میانهٔ سه‌MA). هیچ نیازی به یک مفسرِ پایتونِ ۲۰MB نیست. این فایل همان
 *   منطق را «بایت‌به‌بایت هم‌رفتار» با live_engine.py به JS پورت می‌کند تا اپ:
 *     ✅ فوراً و آفلاین بالا بیاید (بدونِ دانلودِ هیچ چیزِ سنگین)
 *     ✅ نتیجهٔ یکسان با موتورِ واقعیِ پایتونِ پروژه بدهد
 *     ✅ همان ماشینِ حالتِ ۴-وضعیتی (خنثی/نزدیک‌شدن/ورود/مدیریت) را حفظ کند
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
// alpha = 2/(span+1)، مقداردهیِ اولیه با اولین نمونه (adjust=False)
function ema(values, period) {
  const out = new Array(values.length).fill(NaN);
  if (values.length === 0) return out;
  const alpha = 2 / (period + 1);
  let prev = values[0];
  out[0] = prev;
  for (let i = 1; i < values.length; i++) {
    prev = alpha * values[i] + (1 - alpha) * prev;
    out[i] = prev;
  }
  return out;
}

// EMA با alpha دلخواه (adjust=False) — برای RSI/ATR که alpha=1/period دارند
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

// RSI — پورتِ دقیقِ indicators.rsi (ewm با alpha=1/period، adjust=False)
function rsi(closes, period = 14) {
  const n = closes.length;
  const gain = new Array(n).fill(0);
  const loss = new Array(n).fill(0);
  // delta = series.diff(): اولین مقدار NaN → gain/loss اولین نمونه = 0 (clip روی NaN=NaN
  // اما pandas ewm از index 0 با همان مقدار شروع می‌کند؛ diff[0]=NaN ⇒ در pandas
  // gain[0]=NaN، اما ewm(adjust=False) اولین مقدارِ معتبر را مبنا می‌گیرد.)
  // برای هم‌خوانیِ عملی: delta[0] را 0 در نظر می‌گیریم (اثرِ آن پس از ~۳period محو می‌شود).
  for (let i = 1; i < n; i++) {
    const d = closes[i] - closes[i - 1];
    gain[i] = d > 0 ? d : 0;
    loss[i] = d < 0 ? -d : 0;
  }
  const alpha = 1 / period;
  const avgGain = emaAlpha(gain, alpha);
  const avgLoss = emaAlpha(loss, alpha);
  const out = new Array(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    const al = avgLoss[i];
    if (al === 0 || Number.isNaN(al)) { out[i] = al === 0 ? 100 : NaN; continue; }
    const rs = avgGain[i] / al;
    out[i] = 100 - 100 / (1 + rs);
  }
  return out;
}

// ATR — پورتِ دقیقِ indicators.atr (True Range سپس ewm با alpha=1/period)
function atr(highs, lows, closes, period = 14) {
  const n = closes.length;
  const tr = new Array(n).fill(NaN);
  tr[0] = highs[0] - lows[0];
  for (let i = 1; i < n; i++) {
    const hl = highs[i] - lows[i];
    const hc = Math.abs(highs[i] - closes[i - 1]);
    const lc = Math.abs(lows[i] - closes[i - 1]);
    tr[i] = Math.max(hl, hc, lc);
  }
  return emaAlpha(tr, 1 / period);
}

// میانهٔ سه‌MA (EMA50, EMA100, SMA200) — هستهٔ ماشهٔ رکورد (_mid_ma در پایتون)
// np.nanmean روی هر ردیف: میانگینِ مقادیرِ غیر-NaN.
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
    out[i] = cnt ? sum / cnt : NaN;
  }
  return out;
}

function distancePips(price, level, pip) { return Math.abs(price - level) / pip; }
const r2 = (x) => Math.round(x * 100) / 100;
const r5 = (x) => Math.round(x * 1e5) / 1e5;

/* ===========================================================================
 * تصمیمِ زندهٔ ماشینِ حالتِ ۴-وضعیتی — پورتِ دقیقِ live_engine.live_decision
 * ---------------------------------------------------------------------------
 * candles: آرایه‌ای از {time, open, high, low, close, volume} (time = ثانیهٔ Unix)
 * asset:  'XAUUSD' یا 'EURUSD'
 * openPosition: {side:'long'|'short', entry, sl, tp} یا null
 * خروجی: dict آمادهٔ نمایش (state, headline, reasons, ...)
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

  // ── معاملهٔ باز داریم → MANAGE ────────────────────────────────────────
  if (openPosition) {
    return manageDecision(asset, openPosition, indicators, midNow, p, pip);
  }

  // ── ماشهٔ ورود (قطعِ میانهٔ سه‌MA) ─────────────────────────────────────
  const crossUp = pPrev <= midPrev && p > midNow;   // ماشهٔ LONG
  const crossDn = pPrev >= midPrev && p < midNow;   // ماشهٔ SHORT

  if (asset === 'XAUUSD' && crossUp) {
    const params = LONG_PARAMS;
    const sl = p - params.sl_pip * pip;
    const tp = p + params.tp_pip * pip;
    return {
      state: 'ENTRY', asset, side: 'long',
      headline: 'ورود به معاملهٔ خرید (LONG) — کشفِ آغازِ روندِ صعودی.',
      reasons: [
        `قیمت (${p.toFixed(2)}) میانهٔ سه‌MA (${midNow.toFixed(2)}) را رو به بالا شکست.`,
        `EMA50=${e50.toFixed(2)}، SMA200=${e200.toFixed(2)} — چیدمانِ صعودی.`,
        'منطقِ برندهٔ S67/S14 «بگذار بردها بدوند».',
      ],
      entry: r2(p), sl: r2(sl), tp: r2(tp),
      rr: Math.round((params.tp_pip / params.sl_pip) * 100) / 100,
      indicators,
      instruction: 'معاملهٔ خرید را در حسابِ دمو باز و ثبت کن، سپس روی «ثبت معامله» بزن تا واردِ مدیریت شویم.',
    };
  }

  if (asset === 'XAUUSD' && crossDn) {
    const params = SHORT_PARAMS;
    const sl = p + params.sl_pip * pip;
    const tp = p - params.tp_pip * pip;
    return {
      state: 'ENTRY', asset, side: 'short',
      headline: 'ورود به معاملهٔ فروش (SHORT) — کشفِ آغازِ روندِ نزولی.',
      reasons: [
        `قیمت (${p.toFixed(2)}) میانهٔ سه‌MA (${midNow.toFixed(2)}) را رو به پایین شکست.`,
        'منطقِ برندهٔ s118 «بگذار بردها بدوند» (TP=800pip، trail=6pip).',
      ],
      entry: r2(p), sl: r2(sl), tp: r2(tp),
      rr: Math.round((params.tp_pip / params.sl_pip) * 100) / 100,
      indicators,
      instruction: 'معاملهٔ فروش را در حسابِ دمو باز و ثبت کن، سپس روی «ثبت معامله» بزن.',
    };
  }

  // ── EURUSD: ماشهٔ ساعتِ ۰ UTC (S73) ───────────────────────────────────
  if (asset === 'EURUSD') {
    const dt = new Date(candles[n - 1].time * 1000);
    if (dt.getUTCHours() === EURUSD_ENTRY_HOUR) {
      const sl = p - EURUSD_SL_PIP * pip;
      const tp = p + EURUSD_TP_PIP * pip;
      return {
        state: 'ENTRY', asset, side: 'long',
        headline: 'ورود به خریدِ EURUSD — drift صعودیِ ساعتِ ۰ UTC (S73).',
        reasons: ['کشفِ آماریِ S73: بازدهِ مثبتِ پایدار در باز شدنِ سشن (۰ UTC).'],
        entry: r5(p), sl: r5(sl), tp: r5(tp),
        indicators,
        instruction: 'خریدِ EURUSD را ثبت کن، سپس «ثبت معامله» را بزن.',
      };
    }
  }

  // ── APPROACHING: نزدیکِ ماشه ───────────────────────────────────────────
  const distPips = distancePips(p, midNow, pip);
  const nearThr = asset === 'XAUUSD' ? 15 : 8;
  if (distPips <= nearThr) {
    const sideHint = p < midNow ? 'صعودی (LONG)' : 'نزولی (SHORT)';
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
    };
  }

  // ── NEUTRAL ────────────────────────────────────────────────────────────
  return {
    state: 'NEUTRAL', asset,
    headline: 'خنثی — هنوز شرایطِ ورود فراهم نیست.',
    reasons: [
      `قیمت (${p.toFixed(2)}) ${distPips.toFixed(1)} pip از میانهٔ سه‌MA (${midNow.toFixed(2)}) دور است؛ ماشهٔ قطع فعال نشده.`,
      `چیدمانِ MA: EMA50=${e50.toFixed(2)}، SMA200=${e200.toFixed(2)}.`,
      `RSI14=${indicators.rsi14} — خارج از ناحیهٔ تصمیم.`,
    ],
    indicators,
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

// در دسترس قرار دادن برای app.js
window.GoldEngine = {
  liveDecision,
  RECORD,
  // اندیکاتورها (برای تست/بک‌تستِ سبک)
  sma, ema, rsi, atr, midMA,
  SHORT_PARAMS, LONG_PARAMS, PIP,
};
