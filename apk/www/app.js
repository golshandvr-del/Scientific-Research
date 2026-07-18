/* ============================================================================
 * app.js — منطقِ اپلیکیشنِ APK (WebView + Pyodide + موتورِ واقعیِ پروژه)
 * ----------------------------------------------------------------------------
 * 🎯 قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.
 *    تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
 * ----------------------------------------------------------------------------
 * این فایل:
 *   1) Pyodide (CPython/WASM) را داخلِ WebView بالا می‌آورد.
 *   2) numpy + pandas را «داخلِ APK» لود می‌کند (طبقِ درخواستِ کاربر).
 *   3) موتورِ واقعیِ پروژه (pyengine/: engine/ + s118 + s73 + numba-shim) را
 *      بدونِ تغییرِ یک خط در فایل‌سیستمِ مجازیِ Pyodide می‌نویسد و import می‌کند.
 *   4) دادهٔ زندهٔ کندل را آنلاین می‌گیرد (سرورِ سایت یا Yahoo مستقیم).
 *   5) ماشینِ حالتِ ۴-وضعیتیِ live_decision را روی دستگاه اجرا و رندر می‌کند.
 *   6) به کاربر اجازه می‌دهد «فایلِ پایتونِ موتورِ برندهٔ خودش» را وارد کند و
 *      اپ همان کد را واقعاً اجرا کند (تابعِ live_decision / reproduce_record).
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
  interval: 15,           // به‌روزرسانیِ لحظه‌ای (طبقِ User Note) — پیش‌فرضِ ۱۵ ثانیه
};
let CFG = loadCfg();

// دارایی‌های تحتِ پوشش (طبقِ User Note: فقط دو ارزِ دارای لبهٔ اثبات‌شده،
// دقیقاً مطابقِ سایت — XAUUSD و EURUSD. DXY/AUDUSD حذف شدند چون لبهٔ سوددهی
// نداشتند و تعریفِ رسمیِ سودِ خالصِ پروژه = XAUUSD + EURUSD است.)
const ASSETS = [
  { id: 'XAUUSD', label: 'طلا (XAU/USD)', yahoo: 'GC=F', icon: 'fa-coins', color: 'text-amber-400' },
  { id: 'EURUSD', label: 'یورو/دلار (EUR/USD)', yahoo: 'EURUSD=X', icon: 'fa-euro-sign', color: 'text-blue-400' },
];

let pyodide = null;
let engineReady = false;
let activeEngineName = 'داخلی (live_engine.py — موتورِ واقعیِ پروژه)';
let autoTimer = null;
// وضعیتِ معاملاتِ ثبت‌شدهٔ کاربر (برای ورود به MANAGE) — به‌ازای هر دارایی
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
// راه‌اندازیِ Pyodide + لودِ موتورِ واقعی
// ---------------------------------------------------------------------------
async function initPyodide() {
  setStatus('در حالِ بارگذاریِ مفسرِ پایتون…');
  pyodide = await loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/' });

  setStatus('نصبِ numpy و pandas داخلِ اپ…');
  log('لودِ بسته‌های علمی (numpy, pandas) در APK…');
  await pyodide.loadPackage(['numpy', 'pandas']);   // ← پیش‌نیازها داخلِ APK

  setStatus('بارگذاریِ موتورِ واقعیِ پروژه…');
  await mountRealEngine();

  engineReady = true;
  setStatus('موتور آماده است ✅');
  $('footer-engine').textContent = 'واقعی (Pyodide)';
  log('موتورِ واقعیِ پروژه آماده شد. numpy/pandas فعال، shimِ numba فعال.');
}

// نوشتنِ فایل‌های موتورِ واقعی در FSِ مجازیِ Pyodide و import
async function mountRealEngine() {
  const manifest = await fetch('pyengine/manifest.json').then(r => r.json());
  // ساختِ پوشه‌ها
  pyodide.FS.mkdirTree('/pyengine/engine');
  pyodide.FS.mkdirTree('/pyengine/strategies');

  async function put(relPath, fsPath) {
    const src = await fetch('pyengine/' + relPath).then(r => r.text());
    pyodide.FS.writeFile(fsPath, src);
  }
  // فایل‌های ریشه (shim + live_engine)
  for (const f of manifest.root_files) await put(f, '/pyengine/' + f);
  for (const f of manifest.engine)     await put('engine/' + f, '/pyengine/engine/' + f);
  for (const f of manifest.strategies) await put('strategies/' + f, '/pyengine/strategies/' + f);
  log(`فایل‌های موتور نوشته شد: ${manifest.root_files.length} ریشه + ${manifest.engine.length} engine + ${manifest.strategies.length} strategy`);

  // تنظیمِ sys.path و import (shim قبل از هر چیز)
  pyodide.runPython(`
import sys
for p in ['/pyengine', '/pyengine/engine', '/pyengine/strategies']:
    if p not in sys.path:
        sys.path.insert(0, p)
# اطمینان از اینکه numba واقعی لود نشده (تا shim استفاده شود)
for _m in [m for m in list(sys.modules) if m == 'numba' or m.startswith('numba.')]:
    del sys.modules[_m]
import numba  # ← shimِ ما
import live_engine as ENGINE
print('live_engine imported; numba shim =', numba.__version__)
`);
  log('live_engine.py با موفقیت import شد (موتورِ واقعی، بدونِ بازنویسی).');
}

// جایگزینیِ موتور با فایلِ .py واردشده توسطِ کاربر
async function loadUserEngine(fileText, fileName) {
  if (!pyodide) { log('موتور هنوز آماده نیست.'); return; }
  try {
    pyodide.FS.writeFile('/pyengine/user_engine.py', fileText);
    pyodide.runPython(`
import importlib, sys
sys.path.insert(0, '/pyengine')
if 'user_engine' in sys.modules:
    del sys.modules['user_engine']
import user_engine as ENGINE
# راستی‌آزماییِ رابط
assert hasattr(ENGINE, 'live_decision'), 'موتورِ شما باید تابعِ live_decision(df, asset، ...) داشته باشد.'
print('موتورِ کاربر فعال شد:', getattr(ENGINE, '__name__', 'user_engine'))
`);
    activeEngineName = 'موتورِ کاربر: ' + fileName;
    $('active-engine-name').textContent = activeEngineName;
    $('footer-engine').textContent = 'کاربر';
    log('✅ موتورِ شما بارگذاری و فعال شد: ' + fileName);
    await refreshAll();
  } catch (e) {
    log('❌ خطا در بارگذاریِ موتورِ کاربر:\n' + e.message +
        '\nموتور باید تابعِ live_decision(df, asset, open_position=None) و ترجیحاً reproduce_record(xau_df, eur_df) داشته باشد.');
  }
}

function resetToDefaultEngine() {
  if (!pyodide) return;
  pyodide.runPython(`
import sys, importlib
for _m in ['user_engine']:
    if _m in sys.modules: del sys.modules[_m]
import live_engine as ENGINE
importlib.reload(ENGINE)
`);
  activeEngineName = 'داخلی (live_engine.py — موتورِ واقعیِ پروژه)';
  $('active-engine-name').textContent = activeEngineName;
  $('footer-engine').textContent = 'واقعی';
  log('بازگشت به موتورِ پیش‌فرضِ واقعیِ پروژه.');
  refreshAll();
}

// ---------------------------------------------------------------------------
// دریافتِ دادهٔ آنلاینِ کندل
// ---------------------------------------------------------------------------
// مبنای API مؤثر: اگر کاربر apiBase نداد، origin فعلیِ صفحه را امتحان کن
// (وقتی APK کنارِ سرورِ سایت مستقر است یا در حالتِ مرورگر روی همان دامنه).
function effectiveApiBase() {
  if (CFG.apiBase) return CFG.apiBase.replace(/\/$/, '');
  try {
    const o = location.origin;
    if (o && /^https?:/.test(o)) return o;
  } catch (e) {}
  return '';
}

async function fetchCandles(asset) {
  const base = effectiveApiBase();
  // اولویت: endpointِ اختصاصیِ طلا در سرورِ سایت (با ادغامِ spot لحظه‌ای)
  if (base && asset.id === 'XAUUSD') {
    try {
      const u = base + `/api/candles?interval=15m&range=2mo`;
      const j = await fetch(u).then(r => r.json());
      if (j && j.ok && j.candles && j.candles.length) return normalizeCandles(j.candles);
    } catch (e) { log(`سرورِ سایت پاسخ نداد (${asset.id})؛ تلاش با Yahoo…`); }
  }
  // fallback: Yahoo Finance (از طریق پروکسیِ سرورِ سایت یا پروکسی‌های عمومی)
  return fetchYahoo(asset, base);
}

async function fetchYahoo(asset, base) {
  base = base != null ? base : effectiveApiBase();
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(asset.yahoo)}` +
              `?interval=15m&range=60d`;
  // در WebViewِ اندروید (APK) درخواستِ مستقیم بدونِ محدودیتِ CORS کار می‌کند.
  // در مرورگرِ معمولی از پروکسی‌ها استفاده می‌شود. سرورِ سایت بهترین منبع است.
  const proxies = [
    url,
    'https://corsproxy.io/?url=' + encodeURIComponent(url),
    'https://api.allorigins.win/raw?url=' + encodeURIComponent(url),
    'https://thingproxy.freeboard.io/fetch/' + url,
  ];
  // اگر سرورِ سایت در دسترس است، پروکسیِ CORS-safeِ آن را در اولویت بگذار
  if (base) {
    proxies.unshift(base + '/api/proxy?url=' + encodeURIComponent(url));
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
// اجرای موتورِ واقعی روی دستگاه (Pyodide)
// ---------------------------------------------------------------------------
async function runEngineDecision(asset, candles) {
  const pos = openPositions[asset.id] || null;
  pyodide.globals.set('js_candles', pyodide.toPy(candles));
  pyodide.globals.set('js_asset', asset.id);
  pyodide.globals.set('js_pos', pos ? pyodide.toPy(pos) : null);
  const code = `
import pandas as pd, json
_rows = js_candles.to_py() if hasattr(js_candles, 'to_py') else js_candles
_df = pd.DataFrame(_rows)
_df = _df.dropna().reset_index(drop=True)
_pos = js_pos.to_py() if (js_pos is not None and hasattr(js_pos,'to_py')) else js_pos
_res = ENGINE.live_decision(_df, js_asset, open_position=_pos)
json.dumps(_res, default=float, ensure_ascii=False)
`;
  const out = pyodide.runPython(code);
  return JSON.parse(out);
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

  // دلایل
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

  return `<div class="card p-4">
    <div class="flex items-center justify-between">
      <div class="font-bold text-sm"><i class="fas ${asset.icon} ${asset.color}"></i> ${asset.label}</div>
      ${stateBadge(d.state, d.side)}
    </div>
    <div class="mt-1 text-xs text-slate-200 font-semibold">${d.headline || ''}</div>
    ${body}
    ${indHtml}
  </div>`;
}

// ثبت/بستنِ معامله توسطِ کاربر (کنترلِ گذار به MANAGE)
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

  // دریافتِ موازیِ هر دو دارایی — «بدونِ کمترین تأخیر» (طبقِ User Note).
  // چون فقط دو دارایی داریم (XAUUSD + EURUSD) خطرِ نرخ‌محدودی ناچیز است، پس
  // به‌جای دریافتِ ترتیبیِ ۳۵۰ms قبلی، هر دو هم‌زمان دریافت و رندر می‌شوند.
  const results = await Promise.all(ASSETS.map(async (a) => {
    try {
      const candles = await fetchCandles(a);
      const d = await runEngineDecision(a, candles);
      return { a, d, err: null };
    } catch (e) { return { a, d: null, err: e.message }; }
  }));

  container.innerHTML = results.map(r => renderAssetCard(r.a, r.d, r.err)).join('');
  const okCount = results.filter(r => !r.err).length;
  const now = new Date().toLocaleTimeString('fa-IR');
  $('conn-status').innerHTML = okCount
    ? `<span class="text-emerald-400"><i class="fas fa-circle text-[6px]"></i> آنلاین (${okCount}/${ASSETS.length}) · ${now}</span>`
    : '<span class="text-rose-400">آفلاین (بازار احتمالاً بسته است)</span>';
}

// اجرای بک‌تستِ سودِ خالص روی دادهٔ نمونه (بازتولیدِ رکورد با موتورِ واقعی)
async function runBacktestSample() {
  if (!engineReady) { log('موتور آماده نیست.'); return; }
  log('در حالِ بازتولیدِ رکورد با موتورِ واقعی (نیاز به دادهٔ کاملِ ۱۵۰k)…');
  log('نکته: بازتولیدِ کامل روی دستگاه به دادهٔ محلیِ XAUUSD_M15.csv نیاز دارد.');
  try {
    // تلاش برای بازتولید اگر داده در دسترس باشد؛ در APK این‌کار روی زندهٔ اخیر است.
    const asset = ASSETS[0];
    const candles = await fetchCandles(asset);
    pyodide.globals.set('js_candles', pyodide.toPy(candles));
    const out = pyodide.runPython(`
import pandas as pd, json
_df = pd.DataFrame(js_candles.to_py()).dropna().reset_index(drop=True)
# بک‌تستِ سریعِ SHORT روی دادهٔ زندهٔ اخیر (نمایشی) با موتورِ واقعی
try:
    _sig = ENGINE.short_signal(_df)
    _st, _ = ENGINE._run_gold(_df, _sig, ENGINE.SHORT_PARAMS, 'short')
    _res = {'component':'XAUUSD SHORT (live sample)', 'net_profit': round(_st['net_profit'],2),
            'n_trades': _st['n_trades'], 'win_rate': round(_st.get('win_rate',0),1),
            'record_total': ENGINE.RECORD['total']}
except Exception as e:
    _res = {'error': str(e)}
json.dumps(_res, default=float, ensure_ascii=False)
`);
    const r = JSON.parse(out);
    if (r.error) { log('خطا: ' + r.error); return; }
    log(`نتیجهٔ نمونه (${r.component}):`);
    log(`  سودِ خالص = $${r.net_profit}  |  معاملات = ${r.n_trades}  |  WR = ${r.win_rate}% (فقط گزارشی)`);
    log(`  رکوردِ رسمیِ کل (روی ۱۵۰k) = $${r.record_total} = XAUUSD + EURUSD (قانونِ شمارهٔ ۱).`);
  } catch (e) { log('خطا در بک‌تست: ' + e.message); }
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
  // مقداردهیِ اولیهٔ فرم
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
// ورودِ اصلی
// ---------------------------------------------------------------------------
async function main() {
  setupTabs();
  setupEvents();
  startClock();
  try {
    await initPyodide();
  } catch (e) {
    setStatus('خطا در بارگذاریِ موتور');
    log('❌ خطا در راه‌اندازیِ Pyodide: ' + e.message);
    return;
  }
  await refreshAll();
  setupAutoRefresh();
}

document.addEventListener('DOMContentLoaded', main);
