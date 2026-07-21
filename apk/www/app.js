/* ============================================================================
 * app.js — منطقِ اپلیکیشنِ APK (WebView + موتورِ JS خالص، بدونِ گیرِ Pyodide)
 * ----------------------------------------------------------------------------
 * 🎯 قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.
 *    تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
 * ----------------------------------------------------------------------------
 * رفعِ ایرادِ اساسیِ «گیر روی بارگذاریِ مفسرِ پایتون»:
 *
 *   نسخهٔ قبلی هنگامِ startup منتظرِ دانلود و راه‌اندازیِ Pyodide (~۲۰MB WASM از CDN)
 *   می‌ماند؛ درونِ WebView این کار شکننده بود و اپ برای همیشه معلق می‌شد.
 *
 *   حالا موتورِ تصمیم (engine.js) صددرصد JS خالص است و بلافاصله آماده می‌شود.
 *   Pyodide فقط و فقط به‌صورتِ «اختیاری و با تأخیر» بارگذاری می‌شود — تنها اگر
 *   کاربر خودش عمداً یک فایلِ موتورِ .py آپلود کند (با timeout و پیامِ خطای روشن).
 * ==========================================================================*/
'use strict';

// ---------------------------------------------------------------------------
// پیکربندی و وضعیت
// ---------------------------------------------------------------------------
const CFG_KEY = 'gold_apk_cfg_v1';
const DEFAULT_CFG = {
  apiBase: '',            // خالی ⇒ Yahoo مستقیم
  capital: 10000,
  risk: 1.0,
  interval: 30,           // به‌روزرسانیِ خودکار (ثانیه)
};
let CFG = loadCfg();

// دارایی‌های تحتِ پوشش — دقیقاً مطابقِ تعریفِ رسمیِ سودِ خالص: XAUUSD + EURUSD
const ASSETS = [
  { id: 'XAUUSD', label: 'طلا (XAU/USD)', yahoo: 'GC=F', icon: 'fa-coins', color: 'text-amber-400' },
  { id: 'EURUSD', label: 'یورو/دلار (EUR/USD)', yahoo: 'EURUSD=X', icon: 'fa-euro-sign', color: 'text-blue-400' },
];

let engineReady = false;                       // موتورِ JS آماده است؟
let activeEngineName = 'موتورِ داخلی (JS خالص — پورتِ live_engine.py)';
let autoTimer = null;

// موتورِ پایتونِ سفارشیِ کاربر (فقط با آپلودِ عمدیِ کاربر، به‌صورتِ lazy)
let pyodide = null;
let userPyEngineActive = false;

// وضعیتِ معاملاتِ ثبت‌شدهٔ کاربر (برای ورود به MANAGE)
const openPositions = JSON.parse(localStorage.getItem('gold_apk_positions') || '{}');

// ---------------------------------------------------------------------------
// ابزارهای کمکی
// ---------------------------------------------------------------------------
function loadCfg() {
  try { return { ...DEFAULT_CFG, ...JSON.parse(localStorage.getItem(CFG_KEY) || '{}') }; }
  catch { return { ...DEFAULT_CFG }; }
}
function saveCfg() { localStorage.setItem(CFG_KEY, JSON.stringify(CFG)); }
function $(id) { return document.getElementById(id); }
function setStatus(t) { const el = $('engine-status'); if (el) el.textContent = t; }
function log(msg) {
  const el = $('engine-log');
  if (el) { el.textContent += (msg + '\n'); el.scrollTop = el.scrollHeight; }
  console.log('[APK]', msg);
}

// ---------------------------------------------------------------------------
// راه‌اندازیِ موتور (JS خالص — فوری و آفلاین، بدونِ هیچ دانلودِ سنگین)
// ---------------------------------------------------------------------------
function initEngine() {
  if (!window.GoldEngine || typeof window.GoldEngine.liveDecision !== 'function') {
    setStatus('خطا: engine.js بارگذاری نشد');
    log('❌ engine.js پیدا نشد. مطمئن شوید فایل کنارِ app.js وجود دارد.');
    return false;
  }
  engineReady = true;
  setStatus('موتور آماده است ✅ (JS خالص — آفلاین)');
  $('footer-engine').textContent = 'JS';
  $('active-engine-name').textContent = activeEngineName;
  log('موتورِ داخلیِ JS آماده شد (پورتِ دقیقِ live_engine.py؛ EMA/SMA/RSI/ATR + ماشینِ حالتِ ۴-وضعیتی).');
  log('این موتور بدونِ اینترنت و بدونِ مفسرِ پایتون کار می‌کند — دیگر روی «بارگذاریِ پایتون» گیر نمی‌کند.');
  return true;
}

// اجرای تصمیم با موتورِ فعال (JS پیش‌فرض یا پایتونِ سفارشیِ کاربر)
async function runEngineDecision(asset, candles) {
  const pos = openPositions[asset.id] || null;
  if (userPyEngineActive && pyodide) {
    // مسیرِ اختیاری: موتورِ پایتونِ کاربر داخلِ Pyodide
    return runUserPyDecision(asset, candles, pos);
  }
  // مسیرِ پیش‌فرض: موتورِ JS خالص (بدونِ تأخیر)
  return window.GoldEngine.liveDecision(candles, asset.id, pos);
}

// ---------------------------------------------------------------------------
// (اختیاری) بارگذاریِ Pyodide فقط هنگامِ آپلودِ عمدیِ فایلِ .py توسطِ کاربر
// ---------------------------------------------------------------------------
function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error(`${label} بیش از ${ms / 1000}s طول کشید (شبکه؟).`)), ms)),
  ]);
}

async function ensurePyodide() {
  if (pyodide) return pyodide;
  if (typeof loadPyodide !== 'function') {
    // اسکریپتِ Pyodide را فقط الان (lazy) تزریق کن — نه در startup
    log('در حالِ افزودنِ کتابخانهٔ Pyodide (فقط برای موتورِ سفارشیِ شما)…');
    await withTimeout(new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js';
      s.onload = resolve;
      s.onerror = () => reject(new Error('دانلودِ اسکریپتِ Pyodide ناموفق بود (اینترنت لازم است).'));
      document.head.appendChild(s);
    }), 30000, 'افزودنِ Pyodide');
  }
  log('راه‌اندازیِ مفسرِ پایتون (یک‌بار)…');
  pyodide = await withTimeout(
    loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/' }),
    60000, 'راه‌اندازیِ Pyodide');
  log('نصبِ numpy و pandas…');
  await withTimeout(pyodide.loadPackage(['numpy', 'pandas']), 90000, 'نصبِ numpy/pandas');
  return pyodide;
}

async function loadUserEngine(fileText, fileName) {
  try {
    log('⏳ بارگذاریِ موتورِ سفارشیِ پایتونِ شما نیاز به اینترنت دارد (Pyodide). لطفاً صبر کنید…');
    await ensurePyodide();
    pyodide.FS.writeFile('/user_engine.py', fileText);
    pyodide.runPython(`
import importlib, sys
sys.path.insert(0, '/')
if 'user_engine' in sys.modules:
    del sys.modules['user_engine']
import user_engine as ENGINE
assert hasattr(ENGINE, 'live_decision'), 'موتورِ شما باید تابعِ live_decision(df, asset, ...) داشته باشد.'
print('موتورِ کاربر فعال شد')
`);
    userPyEngineActive = true;
    activeEngineName = 'موتورِ سفارشیِ کاربر: ' + fileName;
    $('active-engine-name').textContent = activeEngineName;
    $('footer-engine').textContent = 'پایتونِ کاربر';
    log('✅ موتورِ پایتونِ شما بارگذاری و فعال شد: ' + fileName);
    await refreshAll();
  } catch (e) {
    log('❌ خطا در بارگذاریِ موتورِ سفارشی:\n' + e.message +
        '\nموتورِ پیش‌فرضِ JS همچنان فعال است (بدونِ نیاز به اینترنت).');
  }
}

async function runUserPyDecision(asset, candles, pos) {
  pyodide.globals.set('js_candles', pyodide.toPy(candles));
  pyodide.globals.set('js_asset', asset.id);
  pyodide.globals.set('js_pos', pos ? pyodide.toPy(pos) : null);
  const out = pyodide.runPython(`
import pandas as pd, json
_rows = js_candles.to_py() if hasattr(js_candles, 'to_py') else js_candles
_df = pd.DataFrame(_rows).dropna().reset_index(drop=True)
_pos = js_pos.to_py() if (js_pos is not None and hasattr(js_pos,'to_py')) else js_pos
_res = ENGINE.live_decision(_df, js_asset, open_position=_pos)
json.dumps(_res, default=float, ensure_ascii=False)
`);
  return JSON.parse(out);
}

function resetToDefaultEngine() {
  userPyEngineActive = false;
  activeEngineName = 'موتورِ داخلی (JS خالص — پورتِ live_engine.py)';
  $('active-engine-name').textContent = activeEngineName;
  $('footer-engine').textContent = 'JS';
  log('بازگشت به موتورِ پیش‌فرضِ JS (فوری و آفلاین).');
  refreshAll();
}

// ---------------------------------------------------------------------------
// دریافتِ دادهٔ آنلاینِ کندل
// ---------------------------------------------------------------------------
function effectiveApiBase() {
  if (CFG.apiBase) return CFG.apiBase.replace(/\/$/, '');
  try {
    const o = location.origin;
    if (o && /^https?:/.test(o)) return o;
  } catch (e) {}
  return '';
}

function isNativeApp() {
  try {
    return !!(window.Capacitor && (window.Capacitor.isNativePlatform
      ? window.Capacitor.isNativePlatform() : window.Capacitor.isNative));
  } catch (e) { return false; }
}

// آیا آخرین دریافت از دادهٔ نمونهٔ آفلاین بود؟ (برای نمایشِ برچسب)
let usedSampleData = { XAUUSD: false, EURUSD: false };
let SAMPLE_CACHE = null;

// بارگذاریِ دادهٔ نمونهٔ آفلاینِ بسته‌شده در APK (آخرین ~۴۲۰ کندلِ واقعی)
async function loadSampleData() {
  if (SAMPLE_CACHE) return SAMPLE_CACHE;
  try {
    SAMPLE_CACHE = await fetch('sample_data.json').then(r => r.json());
  } catch (e) { SAMPLE_CACHE = null; }
  return SAMPLE_CACHE;
}

async function fetchCandles(asset) {
  const base = effectiveApiBase();
  usedSampleData[asset.id] = false;
  if (base && asset.id === 'XAUUSD') {
    try {
      const u = base + `/api/candles?interval=15m&range=2mo`;
      const j = await fetch(u).then(r => r.json());
      if (j && j.ok && j.candles && j.candles.length) return normalizeCandles(j.candles);
    } catch (e) { log(`سرورِ سایت پاسخ نداد (${asset.id})؛ تلاش با Yahoo…`); }
  }
  try {
    return await fetchYahoo(asset, base);
  } catch (e) {
    // آخرین سنگر: دادهٔ نمونهٔ آفلاین تا اپ هرگز «خالی» نماند و موتور نمایش داده شود.
    const s = await loadSampleData();
    if (s && s[asset.id] && s[asset.id].length) {
      usedSampleData[asset.id] = true;
      log(`دادهٔ آنلاینِ ${asset.id} در دسترس نبود؛ نمایشِ موتور روی دادهٔ نمونهٔ آفلاین.`);
      return s[asset.id];
    }
    throw e;
  }
}

async function fetchYahoo(asset, base) {
  base = base != null ? base : effectiveApiBase();
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(asset.yahoo)}` +
              `?interval=15m&range=60d`;
  let proxies;
  if (isNativeApp()) {
    proxies = [
      url,
      `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(asset.yahoo)}?interval=15m&range=60d`,
    ];
    if (base) proxies.push(base + '/api/proxy?url=' + encodeURIComponent(url));
  } else {
    proxies = [
      url,
      'https://corsproxy.io/?url=' + encodeURIComponent(url),
      'https://api.allorigins.win/raw?url=' + encodeURIComponent(url),
      'https://thingproxy.freeboard.io/fetch/' + url,
    ];
    if (base) proxies.unshift(base + '/api/proxy?url=' + encodeURIComponent(url));
  }
  for (const p of proxies) {
    try {
      const j = await fetch(p).then(r => r.json());
      const res = j.chart && j.chart.result && j.chart.result[0];
      if (!res) continue;
      const ts = res.timestamp || [];
      const q = res.indicators.quote[0];
      const out = [];
      for (let i = 0; i < ts.length; i++) {
        if (q.open[i] == null || q.close[i] == null) continue;
        out.push({ time: ts[i], open: q.open[i], high: q.high[i], low: q.low[i], close: q.close[i], volume: q.volume[i] || 0 });
      }
      if (out.length) return out;
    } catch (e) { /* پروکسیِ بعدی */ }
  }
  throw new Error('عدمِ دسترسی به دادهٔ آنلاین برای ' + asset.id);
}

function normalizeCandles(arr) {
  return arr.map(c => ({
    time: c.time || c.t || c.timestamp,
    open: +c.open ?? +c.o, high: +c.high ?? +c.h,
    low: +c.low ?? +c.l, close: +c.close ?? +c.c, volume: +c.volume || 0,
  }));
}

// ---------------------------------------------------------------------------
// رندرِ کارتِ ماشینِ حالتِ ۴-وضعیتی
// ---------------------------------------------------------------------------
function stateBadge(state, side) {
  const map = {
    NEUTRAL:     ['badge-neutral', 'خنثی', 'fa-circle-pause'],
    APPROACHING: ['badge-approach', 'نزدیک‌شدن به سیگنال', 'fa-hourglass-half pulse'],
    ENTRY:       [side === 'short' ? 'badge-entry-short' : 'badge-entry-long',
                  'ورود به معامله', 'fa-right-to-bracket pulse'],
    MANAGE:      ['badge-manage', 'مدیریتِ معامله', 'fa-sliders'],
  };
  const [cls, txt, icon] = map[state] || map.NEUTRAL;
  return `<span class="${cls} text-white text-[10px] px-2 py-1 rounded-full"><i class="fas ${icon}"></i> ${txt}</span>`;
}

function renderAssetCard(asset, d, err) {
  if (err) {
    return `<div class="card p-4">
      <div class="flex items-center justify-between">
        <div class="font-bold text-sm"><i class="fas ${asset.icon} ${asset.color}"></i> ${asset.label}</div>
        <span class="text-[10px] text-rose-400">خطا</span>
      </div>
      <div class="text-[11px] text-rose-300 mt-2">${err}</div>
    </div>`;
  }
  const ind = d.indicators || {};
  let body = '';
  const reasons = (d.reasons || []).map(r => `<li class="flex gap-1"><span class="text-amber-400">•</span><span>${r}</span></li>`).join('');

  if (d.state === 'ENTRY') {
    body = `
      <div class="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
        <div class="bg-slate-800 rounded-lg py-2"><div class="text-[9px] text-slate-400">ورود</div><div class="font-bold">${d.entry}</div></div>
        <div class="bg-red-950/60 rounded-lg py-2"><div class="text-[9px] text-slate-400">حدِ ضرر</div><div class="font-bold text-rose-300">${d.sl}</div></div>
        <div class="bg-emerald-950/60 rounded-lg py-2"><div class="text-[9px] text-slate-400">حدِ سود</div><div class="font-bold text-emerald-300">${d.tp}</div></div>
      </div>
      <ul class="mt-2 text-[11px] text-slate-300 space-y-1">${reasons}</ul>
      <div class="mt-2 text-[11px] text-amber-200 bg-amber-950/40 rounded-lg p-2">${d.instruction || ''}</div>
      <button onclick="confirmTrade('${asset.id}','${d.side}',${d.entry},${d.sl},${d.tp})"
        class="mt-2 w-full bg-emerald-600 hover:bg-emerald-500 rounded-lg py-2 text-xs font-bold">
        <i class="fas fa-check"></i> معامله را ثبت کردم (ورود به مدیریت)
      </button>`;
  } else if (d.state === 'MANAGE') {
    const p = d.position || {};
    const acts = (d.actions || []).map(a => `<li class="bg-slate-800 rounded-lg p-2 text-[11px]">${a.text}</li>`).join('');
    body = `
      <div class="mt-2 text-[11px] text-slate-300">پوزیشن: ${p.side === 'long' ? 'خرید' : 'فروش'} — ورود ${p.entry} | سودِ فعلی ${p.profit_pips} pip</div>
      <ul class="mt-2 space-y-1">${acts}</ul>
      <button onclick="closeTrade('${asset.id}')" class="mt-2 w-full bg-slate-700 hover:bg-slate-600 rounded-lg py-2 text-xs">
        <i class="fas fa-xmark"></i> معامله را بستم
      </button>`;
  } else if (d.state === 'APPROACHING') {
    const waits = (d.waiting_for || []).map(w => `<li class="flex gap-1"><span class="text-amber-400">⏳</span><span>${w}</span></li>`).join('');
    body = `<ul class="mt-2 text-[11px] text-slate-300 space-y-1">${reasons}</ul>
      <div class="mt-2 text-[10px] text-slate-400">تأییدهای موردِ نیاز:</div>
      <ul class="text-[11px] text-slate-300 space-y-1">${waits}</ul>`;
  } else {
    body = `<ul class="mt-2 text-[11px] text-slate-400 space-y-1">${reasons}</ul>`;
  }

  const indHtml = Object.keys(ind).length ? `
    <div class="mt-2 grid grid-cols-4 gap-1 text-[9px] text-slate-400">
      ${['price','mid_ma3','ema50','sma200','rsi14','atr14','dist_to_mid_pips'].filter(k=>ind[k]!=null).map(k =>
        `<div class="bg-slate-900/60 rounded p-1 text-center"><div class="opacity-60">${k}</div><div class="text-slate-200">${ind[k]}</div></div>`).join('')}
    </div>` : '';

  const sampleTag = usedSampleData[asset.id]
    ? `<div class="mt-1 text-[10px] text-amber-400/90"><i class="fas fa-circle-info"></i> دادهٔ نمونهٔ آفلاین (اینترنت در دسترس نیست) — منطقِ موتور واقعی است.</div>`
    : '';
  return `<div class="card p-4">
    <div class="flex items-center justify-between">
      <div class="font-bold text-sm"><i class="fas ${asset.icon} ${asset.color}"></i> ${asset.label}</div>
      ${stateBadge(d.state, d.side)}
    </div>
    ${sampleTag}
    <div class="mt-1 text-xs text-slate-200 font-semibold">${d.headline || ''}</div>
    ${body}
    ${indHtml}
  </div>`;
}

window.confirmTrade = function (assetId, side, entry, sl, tp) {
  openPositions[assetId] = { side, entry, sl, tp };
  localStorage.setItem('gold_apk_positions', JSON.stringify(openPositions));
  log(`معاملهٔ ${assetId} ثبت شد (${side} @ ${entry}). ورود به وضعیتِ مدیریت.`);
  refreshAll();
};
window.closeTrade = function (assetId) {
  delete openPositions[assetId];
  localStorage.setItem('gold_apk_positions', JSON.stringify(openPositions));
  log(`معاملهٔ ${assetId} بسته شد. بازگشت به پایشِ سیگنال.`);
  refreshAll();
};

// ---------------------------------------------------------------------------
// به‌روزرسانیِ همهٔ دارایی‌ها
// ---------------------------------------------------------------------------
async function refreshAll() {
  if (!engineReady) return;
  const container = $('asset-cards');
  container.innerHTML = ASSETS.map(a =>
    `<div class="card p-4 text-xs text-slate-400" id="loading-${a.id}"><i class="fas fa-spinner fa-spin ${a.color}"></i> دریافتِ دادهٔ ${a.label}…</div>`).join('');
  $('conn-status').innerHTML = '<span class="text-amber-400">در حالِ دریافت…</span>';

  const results = await Promise.all(ASSETS.map(async (a) => {
    try {
      const candles = await fetchCandles(a);
      const d = await runEngineDecision(a, candles);
      return { a, d, err: null };
    } catch (e) { return { a, d: null, err: e.message }; }
  }));

  container.innerHTML = results.map(r => renderAssetCard(r.a, r.d, r.err)).join('');
  const okCount = results.filter(r => !r.err).length;
  const sampleCount = ASSETS.filter(a => usedSampleData[a.id]).length;
  const now = new Date().toLocaleTimeString('fa-IR');
  if (sampleCount > 0 && okCount) {
    $('conn-status').innerHTML = `<span class="text-amber-400"><i class="fas fa-circle text-[6px]"></i> نمونهٔ آفلاین · ${now}</span>`;
  } else if (okCount) {
    $('conn-status').innerHTML = `<span class="text-emerald-400"><i class="fas fa-circle text-[6px]"></i> آنلاین (${okCount}/${ASSETS.length}) · ${now}</span>`;
  } else {
    $('conn-status').innerHTML = '<span class="text-rose-400">آفلاین (بازار احتمالاً بسته است)</span>';
  }
}

// بک‌تستِ سبک روی دادهٔ زندهٔ اخیر با موتورِ JS (نمایشی — تأییدِ سلامتِ موتور)
async function runBacktestSample() {
  if (!engineReady) { log('موتور آماده نیست.'); return; }
  log('در حالِ آزمونِ موتورِ JS روی دادهٔ زندهٔ اخیر…');
  try {
    const asset = ASSETS[0];
    const candles = await fetchCandles(asset);
    const d = window.GoldEngine.liveDecision(candles, asset.id, null);
    log(`نتیجهٔ لحظه‌ایِ ${asset.id}: وضعیت = ${d.state} — ${d.headline}`);
    if (d.indicators) {
      log(`  price=${d.indicators.price} | mid_ma3=${d.indicators.mid_ma3} | rsi14=${d.indicators.rsi14} | dist=${d.indicators.dist_to_mid_pips}pip`);
    }
    log(`  رکوردِ رسمیِ کل (روی ۱۵۰k، منبع: پروژه) = $${window.GoldEngine.RECORD.total} = XAUUSD + EURUSD (قانونِ شمارهٔ ۱).`);
    log('موتورِ JS سالم است ✅ (بدونِ نیاز به پایتون).');
  } catch (e) { log('خطا در آزمون: ' + e.message); }
}

// ---------------------------------------------------------------------------
// تب‌ها، رویدادها، ساعت
// ---------------------------------------------------------------------------
function setupTabs() {
  document.querySelectorAll('.tabbtn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tabbtn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      ['signals', 'engine', 'settings'].forEach(t =>
        $('tab-' + t).classList.toggle('hidden', t !== tab));
    });
  });
}

function setupEvents() {
  $('btn-load-engine').addEventListener('click', async () => {
    const f = $('engine-file').files[0];
    if (!f) { log('ابتدا یک فایلِ .py انتخاب کنید.'); return; }
    const text = await f.text();
    await loadUserEngine(text, f.name);
  });
  $('btn-reset-engine').addEventListener('click', resetToDefaultEngine);
  $('btn-run-backtest').addEventListener('click', runBacktestSample);
  $('btn-refresh-all').addEventListener('click', refreshAll);
  $('btn-save-settings').addEventListener('click', () => {
    CFG.apiBase = $('api-base').value.trim();
    CFG.capital = +$('cfg-capital').value || 10000;
    CFG.risk = +$('cfg-risk').value || 1;
    CFG.interval = Math.max(5, +$('cfg-interval').value || 30);
    saveCfg(); setupAutoRefresh();
    log('تنظیمات ذخیره شد.'); refreshAll();
  });
  $('api-base').value = CFG.apiBase;
  $('cfg-capital').value = CFG.capital;
  $('cfg-risk').value = CFG.risk;
  $('cfg-interval').value = CFG.interval;
  $('active-engine-name').textContent = activeEngineName;
}

function setupAutoRefresh() {
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = setInterval(refreshAll, CFG.interval * 1000);
}

function startClock() {
  setInterval(() => {
    const el = $('live-clock');
    if (el) el.textContent = new Date().toLocaleTimeString('fa-IR');
  }, 1000);
}

// ---------------------------------------------------------------------------
// ورودِ اصلی — موتورِ JS فوراً آماده می‌شود (هیچ انتظارِ شبکه‌ای در startup)
// ---------------------------------------------------------------------------
// نمایشِ لیستِ استراتژی‌های فعالِ ثبت‌شده در رجیستری (تبِ موتور)
function renderStrategyList() {
  const ul = $('strategy-list');
  if (!ul || !window.GoldEngine || typeof window.GoldEngine.listStrategies !== 'function') return;
  const list = window.GoldEngine.listStrategies();
  if (!list.length) {
    ul.innerHTML = '<li class="text-slate-500">هیچ استراتژی‌ای ثبت نشده است.</li>';
    return;
  }
  ul.innerHTML = list.map(s =>
    `<li><i class="fas fa-circle text-[6px] text-violet-400"></i> <b class="text-slate-100">${s.name}</b>
     <span class="text-slate-500">(${s.asset} · <code class="bg-slate-800 px-1 rounded">${s.id}</code>)</span></li>`
  ).join('');
}

async function main() {
  setupTabs();
  setupEvents();
  startClock();
  const ok = initEngine();           // ← فوری، بدونِ Pyodide، بدونِ گیر کردن
  if (!ok) return;
  renderStrategyList();              // نمایشِ استراتژی‌های افزونه‌ایِ فعال
  await refreshAll();                // اگر شبکه نبود، فقط کارت‌ها خطای «آفلاین» می‌دهند؛ اپ سالم می‌ماند
  setupAutoRefresh();
}

document.addEventListener('DOMContentLoaded', main);
