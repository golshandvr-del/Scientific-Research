/* ============================================================================
 * دستیارِ تصمیمِ معاملاتِ چند-دارایی — ماشینِ حالتِ ۴-وضعیتی
 * ----------------------------------------------------------------------------
 * پیاده‌سازیِ PARADIGM v2 / User Note 2:
 *   - برای هر دارایی (XAUUSD, DXY, EURUSD, AUDUSD) یک کارتِ مستقل.
 *   - چهار حالت: خنثی → نزدیک‌شدن → ورود (TP/SL) → مدیریتِ معامله.
 *   - گذارِ «ورود → مدیریت» فقط با ثبتِ معاملهٔ کاربر (دکمه) رخ می‌دهد.
 *   - معیار: سودِ خالص. کاربر پشتِ‌صحنه را نمی‌بیند؛ فقط تصمیمِ نهایی را می‌گیرد.
 * هیچ نمودار/بخشِ تحقیق/اطلاعاتِ اضافه‌ای نمایش داده نمی‌شود.
 * ==========================================================================*/

const REFRESH_MS = 30000
const app = document.getElementById('app')

// وضعیتِ محلیِ هر دارایی (معاملهٔ ثبت‌شدهٔ کاربر) در localStorage نگه‌داری می‌شود.
const TRADE_KEY = (asset) => 'trade_' + asset
function getTrade(asset) {
  try { return JSON.parse(localStorage.getItem(TRADE_KEY(asset)) || 'null') } catch { return null }
}
function setTrade(asset, trade) {
  if (trade) localStorage.setItem(TRADE_KEY(asset), JSON.stringify(trade))
  else localStorage.removeItem(TRADE_KEY(asset))
}

// --- S67/L41: سرمایه و ریسکِ کاربر (پایدار در localStorage) ---
// کشفِ L41: سودِ خالص فقط با مدلِ سرمایه معنا دارد؛ سایت حجمِ لاتِ واقعی را از این
// دو مقدار می‌سازد و به /api/decision پاس می‌دهد.
const CAP_KEY = 'user_capital', RISK_KEY = 'user_risk'
function getCapital() { const v = parseFloat(localStorage.getItem(CAP_KEY)); return (isFinite(v) && v >= 100) ? v : 10000 }
function getRisk() { const v = parseFloat(localStorage.getItem(RISK_KEY)); return (isFinite(v) && v > 0) ? v : 1.0 }
function setCapital(v) { localStorage.setItem(CAP_KEY, String(v)) }
function setRisk(v) { localStorage.setItem(RISK_KEY, String(v)) }

// آخرین دادهٔ decision و advice برای هر دارایی
const store = {}   // { XAUUSD: { decision, adviceStatus, error } , ... }
let assetsMeta = []

const fmt = (x, d = 2) => (x == null || !isFinite(x)) ? '—' : Number(x).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
// زمانِ دریافتِ آخرین پاسخِ موفق از سرور — بر پایهٔ ساعتِ خودِ مرورگر ثبت می‌شود.
// (رفع باگِ «-۳۶۲۱ ثانیه پیش»: قبلاً lastUpdateِ سرور با Date.now()ِ مرورگر مقایسه
//  می‌شد؛ اگر ساعتِ دستگاهِ کاربر با سرور اختلاف داشت — مثلاً به‌خاطرِ تایم‌زون/ساعتِ
//  اشتباهِ سیستم — عددِ منفی می‌شد. حالا سن را نسبت به لحظهٔ دریافتِ همان پاسخ در
//  مرورگر می‌سنجیم؛ کاملاً مستقل از ساعتِ سرور و همیشه ≥ ۰.)
let lastFetchAt = 0
const timeAgoSince = (baseMs) => {
  if (!baseMs) return ''
  let s = Math.round((Date.now() - baseMs) / 1000)
  if (s < 0) s = 0                      // هرگز منفی نشود
  if (s < 60) return s + ' ثانیه پیش'
  return Math.round(s / 60) + ' دقیقه پیش'
}

// -------------------------- رنگ/برچسبِ حالت --------------------------
const STATE_META = {
  NEUTRAL:     { fa: 'خنثی', icon: 'fa-circle-pause', ring: 'border-slate-600', chip: 'bg-slate-700 text-slate-200', dot: 'bg-slate-400' },
  APPROACHING: { fa: 'نزدیک‌شدن به سیگنال', icon: 'fa-hourglass-half', ring: 'border-amber-500', chip: 'bg-amber-500/20 text-amber-300', dot: 'bg-amber-400' },
  ENTRY:       { fa: 'ورود به معامله', icon: 'fa-right-to-bracket', ring: 'border-emerald-500', chip: 'bg-emerald-500/20 text-emerald-300', dot: 'bg-emerald-400' },
  MANAGE:      { fa: 'مدیریتِ معامله', icon: 'fa-gears', ring: 'border-sky-500', chip: 'bg-sky-500/20 text-sky-300', dot: 'bg-sky-400' },
}
const indStatusColor = (s) => s === 'ok' ? 'text-emerald-400' : s === 'warn' ? 'text-amber-400' : s === 'bad' ? 'text-rose-400' : 'text-slate-400'

// ============================================================================
// رندرِ کلی
// ============================================================================
function render() {
  const header = `
    <header id="page-header" class="mb-5 text-center">
      <h1 class="text-2xl md:text-3xl font-extrabold text-amber-400">
        <i class="fas fa-compass ml-2"></i>دستیارِ تصمیمِ معاملات
      </h1>
      <p class="text-slate-400 text-sm mt-1">تصمیمِ نهاییِ چند-دارایی بر پایهٔ Routerِ رژیم-محور — معیار: سودِ خالص</p>
      <div class="flex items-center justify-center gap-3 mt-2">
        <p id="last-update" class="text-slate-500 text-xs"></p>
        <button id="manual-refresh" class="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs px-3 py-1.5 transition disabled:opacity-60">
          <i class="fas fa-rotate-right"></i><span>بروزرسانیِ دستیِ داده‌ها</span>
        </button>
      </div>
      <div id="capital-panel" class="mt-3 inline-flex flex-wrap items-center justify-center gap-3 rounded-xl bg-slate-800/60 border border-slate-700 px-4 py-2.5">
        <span class="text-xs text-slate-400 font-bold"><i class="fas fa-wallet ml-1"></i>مدلِ سرمایه (L41):</span>
        <label class="flex items-center gap-1.5 text-xs text-slate-300">
          سرمایه ($)
          <input id="cap-input" type="number" min="100" step="100" value="${getCapital()}"
            class="w-24 rounded bg-slate-900 border border-slate-600 px-2 py-1 text-amber-200 font-bold text-center tabular-nums focus:outline-none focus:border-amber-500" dir="ltr">
        </label>
        <label class="flex items-center gap-1.5 text-xs text-slate-300">
          ریسک هر معامله (٪)
          <input id="risk-input" type="number" min="0.1" max="5" step="0.1" value="${getRisk()}"
            class="w-16 rounded bg-slate-900 border border-slate-600 px-2 py-1 text-rose-200 font-bold text-center tabular-nums focus:outline-none focus:border-rose-500" dir="ltr">
        </label>
        <button id="cap-apply" class="rounded bg-amber-500/90 hover:bg-amber-400 text-slate-900 font-bold text-xs px-3 py-1.5 transition">
          اعمال
        </button>
      </div>
      <p class="text-[11px] text-slate-500 mt-1.5 max-w-xl mx-auto">حجمِ لاتِ پیشنهادی طوری محاسبه می‌شود که اگر SL بخورد، دقیقاً همین درصدِ ریسک از سرمایه‌تان کم شود. (بک‌تستِ برنده S67: با ۱۰٬۰۰۰$ و ریسکِ ۱٪ ⇒ سودِ خالص +۳۷٬۱۵۶$)</p>
    </header>`

  const cards = assetsMeta.map(a => renderCard(a)).join('')
  app.innerHTML = header +
    `<main id="asset-grid" class="grid grid-cols-1 lg:grid-cols-2 gap-4">${cards}</main>` +
    `<footer class="mt-6 text-center text-xs text-slate-600">
       این ابزار برای تحقیقِ علمی است و توصیهٔ مالی نیست. بازار ریسک دارد.
     </footer>`
  bindEvents()
}

function renderCard(a) {
  const s = store[a.id] || {}
  const d = s.decision
  const trade = getTrade(a.id)
  // اگر کاربر معامله‌ای ثبت کرده، حالت = MANAGE (فارغ از اینکه Router چه می‌گوید)
  const state = trade ? 'MANAGE' : (d ? d.state : 'LOADING')
  const sm = STATE_META[state] || STATE_META.NEUTRAL

  let body = ''
  if (s.error) {
    body = `<div class="text-rose-400 text-sm p-3"><i class="fas fa-triangle-exclamation ml-1"></i>خطا در دریافت داده: ${s.error}</div>`
  } else if (!d && !trade) {
    body = `<div class="text-slate-500 text-sm p-4 text-center"><i class="fas fa-spinner fa-spin ml-2"></i>در حال تحلیل...</div>`
  } else if (trade) {
    body = renderManage(a, trade, s)
  } else if (state === 'ENTRY') {
    body = renderEntry(a, d)
  } else if (state === 'APPROACHING') {
    body = renderApproaching(a, d)
  } else {
    body = renderNeutral(a, d)
  }

  return `
    <section class="asset-card bg-slate-900 rounded-2xl border-2 ${sm.ring} overflow-hidden shadow-lg" data-asset="${a.id}">
      <div class="flex items-center justify-between px-4 py-3 bg-slate-800/60 border-b border-slate-700/60">
        <div class="flex items-center gap-2">
          <span class="inline-block w-2.5 h-2.5 rounded-full ${sm.dot} animate-pulse"></span>
          <h2 class="font-bold text-slate-100">${a.name}</h2>
          ${a.layer === 'scalp'
            ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-fuchsia-500/20 text-fuchsia-300 font-bold" title="سبک: اسکالپِ کوتاه‌مدت روی M5"><i class="fas fa-bolt"></i> اسکالپ</span>'
            : '<span class="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-bold" title="سبک: معاملهٔ نوسانی روی M15"><i class="fas fa-wave-square"></i> نوسانی</span>'}
        </div>
        <span class="text-xs px-2.5 py-1 rounded-full font-bold ${sm.chip}">
          <i class="fas ${sm.icon} ml-1"></i>${sm.fa}
        </span>
      </div>
      <div class="p-4">
        <div class="flex items-baseline justify-between mb-3">
          <span class="text-slate-400 text-xs">قیمتِ فعلی <span id="price-age-${a.id}" class="text-slate-600"></span></span>
          <span id="price-${a.id}" class="text-lg font-bold text-slate-100 tabular-nums" dir="ltr">${d || trade ? fmt(s.price ?? (d && d.price) ?? (trade && trade.entry), a.decimals) : '—'}</span>
        </div>
        ${body}
      </div>
    </section>`
}

// -------------------------- حالت ۱: خنثی --------------------------
function renderNeutral(a, d) {
  return `
    <div class="rounded-lg bg-slate-800/40 p-3 mb-3">
      <p class="font-bold text-slate-200 mb-1"><i class="fas fa-circle-pause ml-1 text-slate-400"></i>${d.headline}</p>
      <p class="text-sm text-slate-400 leading-relaxed">${d.reason}</p>
    </div>
    ${renderIndicators(d)}`
}

// -------------------------- حالت ۲: نزدیک‌شدن --------------------------
function renderApproaching(a, d) {
  const confs = (d.confirmations || []).map(c => `
    <li class="flex items-start gap-2 text-sm">
      <i class="fas ${c.met ? 'fa-circle-check text-emerald-400' : 'fa-circle-dot text-amber-400'} mt-0.5"></i>
      <span><span class="${c.met ? 'text-emerald-300' : 'text-amber-200'} font-medium">${c.label}</span>
      — <span class="text-slate-400">${c.detail}</span></span>
    </li>`).join('')
  return `
    <div class="rounded-lg bg-amber-500/10 border border-amber-500/30 p-3 mb-3">
      <p class="font-bold text-amber-300 mb-1"><i class="fas fa-hourglass-half ml-1"></i>${d.headline}</p>
      <p class="text-sm text-slate-300 leading-relaxed mb-2">${d.reason}</p>
      <p class="text-xs text-amber-200/80 font-bold mb-1">تأییدهایِ موردِ انتظار:</p>
      <ul class="space-y-1.5">${confs}</ul>
    </div>
    ${renderIndicators(d)}`
}

// -------------------------- حالت ۳: ورود --------------------------
function renderEntry(a, d) {
  const isLong = d.direction === 'LONG'
  const dirColor = isLong ? 'text-emerald-400' : 'text-rose-400'
  const dirBg = isLong ? 'bg-emerald-500/15 border-emerald-500/40' : 'bg-rose-500/15 border-rose-500/40'
  const dirFa = isLong ? 'خرید (LONG)' : 'فروش (SHORT)'
  return `
    <div class="rounded-lg ${dirBg} border p-3 mb-3">
      <p class="font-bold ${dirColor} mb-1 text-base">
        <i class="fas ${isLong ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down'} ml-1"></i>${d.headline}
      </p>
      <p class="text-sm text-slate-300 leading-relaxed mb-3">${d.reason}</p>
      <div class="grid grid-cols-3 gap-2 text-center" dir="ltr">
        <div class="bg-slate-800/70 rounded-lg p-2">
          <div class="text-[11px] text-slate-400">ورود</div>
          <div class="font-bold text-slate-100 tabular-nums">${fmt(d.entry, a.decimals)}</div>
        </div>
        <div class="bg-emerald-900/30 rounded-lg p-2">
          <div class="text-[11px] text-emerald-400">TP</div>
          <div class="font-bold text-emerald-300 tabular-nums">${fmt(d.tp, a.decimals)}</div>
        </div>
        <div class="bg-rose-900/30 rounded-lg p-2">
          <div class="text-[11px] text-rose-400">SL</div>
          <div class="font-bold text-rose-300 tabular-nums">${fmt(d.sl, a.decimals)}</div>
        </div>
      </div>
      <div class="flex items-center justify-between mt-2 text-xs text-slate-400">
        <span>ریسک به ریوارد: ${d.rr || '—'}</span>
        <span>احتمالِ مدل: ${fmt(d.probability, 1)}%</span>
      </div>
      ${d.sizing ? `
      <div class="mt-3 rounded-lg bg-amber-500/10 border border-amber-500/30 p-2.5">
        <div class="flex items-center justify-between">
          <span class="text-xs text-amber-300 font-bold"><i class="fas fa-coins ml-1"></i>حجمِ پیشنهادی (اهرمِ سودِ خالص)</span>
          <span class="text-sm font-extrabold text-amber-200 tabular-nums">${d.sizing.label}</span>
        </div>
        ${d.sizing.lots != null ? `
        <div class="mt-2 grid grid-cols-2 gap-2">
          <div class="rounded bg-amber-500/15 px-2 py-1.5 text-center">
            <div class="text-[10px] text-amber-300/80">حجمِ لاتِ واقعی</div>
            <div class="text-base font-extrabold text-amber-100 tabular-nums" dir="ltr">${fmt(d.sizing.lots, 2)} <span class="text-[10px] font-normal">لات</span></div>
          </div>
          <div class="rounded bg-rose-500/15 px-2 py-1.5 text-center">
            <div class="text-[10px] text-rose-300/80">ریسکِ دلاری (اگر SL بخورد)</div>
            <div class="text-base font-extrabold text-rose-100 tabular-nums" dir="ltr">${fmt(d.sizing.riskDollars, 2)}$</div>
          </div>
        </div>
        <p class="text-[11px] text-amber-100/70 leading-relaxed mt-1.5">${d.sizing.capitalNote}</p>
        ` : `<p class="text-[11px] text-amber-100/70 leading-relaxed mt-1">${d.sizing.note}</p>`}
      </div>` : ''}
      ${d.tpPlan ? `
      <div class="mt-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-2.5">
        <div class="flex items-center justify-between">
          <span class="text-xs text-emerald-300 font-bold"><i class="fas fa-bullseye ml-1"></i>هدفِ سودِ رژیم-محور</span>
          <span class="text-sm font-extrabold text-emerald-200 tabular-nums" dir="ltr">${d.tpPlan.multiplier}×ATR</span>
        </div>
        <p class="text-[11px] text-emerald-100/70 leading-relaxed mt-1">${d.tpPlan.note}</p>
      </div>` : ''}
      ${d.slPlan ? `
      <div class="mt-2 rounded-lg bg-rose-500/10 border border-rose-500/30 p-2.5">
        <div class="flex items-center justify-between">
          <span class="text-xs text-rose-300 font-bold"><i class="fas fa-shield-halved ml-1"></i>حدِ ضررِ رژیم-محور (اهرمِ چهارم)</span>
          <span class="text-sm font-extrabold text-rose-200 tabular-nums" dir="ltr">${d.slPlan.multiplier}×ATR</span>
        </div>
        <p class="text-[11px] text-rose-100/70 leading-relaxed mt-1">${d.slPlan.note}</p>
      </div>` : ''}
    </div>
    ${renderIndicators(d)}
    <button class="btn-register mt-3 w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 font-bold text-white transition"
      data-asset="${a.id}"
      data-dir="${d.direction}" data-entry="${d.entry}" data-tp="${d.tp}" data-sl="${d.sl}" data-prob="${d.probability || ''}">
      <i class="fas fa-check ml-2"></i>معامله را در دمو باز و ثبت کردم
    </button>
    <p class="text-[11px] text-slate-500 mt-1.5 text-center">تا معامله را ثبت نکنی، به مرحلهٔ مدیریت نمی‌رویم.</p>`
}

// -------------------------- حالت ۴: مدیریتِ معامله --------------------------
function renderManage(a, trade, s) {
  const st = s.adviceStatus
  const isLong = trade.side === 'long'
  const dirFa = isLong ? 'خرید' : 'فروش'
  let inner
  if (s.adviceError) {
    inner = `<p class="text-rose-400 text-sm p-2">${s.adviceError}</p>`
  } else if (!st) {
    inner = `<p class="text-slate-500 text-sm p-2"><i class="fas fa-spinner fa-spin ml-2"></i>در حال ارزیابیِ مدیریت...</p>`
  } else {
    const pnlColor = st.pnlR >= 0 ? 'text-emerald-400' : 'text-rose-400'
    const advList = (st.advices || []).map(ad => {
      const sev = ad.severity === 'critical' ? 'border-rose-500/50 bg-rose-500/10 text-rose-200'
        : ad.severity === 'warning' ? 'border-amber-500/50 bg-amber-500/10 text-amber-200'
        : ad.severity === 'good' ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-200'
        : 'border-slate-600 bg-slate-800/40 text-slate-300'
      const sug = ad.suggest ? `<button class="btn-apply mt-1.5 text-xs px-2 py-1 rounded bg-slate-700 hover:bg-slate-600"
          data-asset="${a.id}" data-field="${ad.suggest.field}" data-value="${ad.suggest.value}">
          اعمالِ ${ad.suggest.field.toUpperCase()} = ${fmt(ad.suggest.value, a.decimals)}</button>` : ''
      return `<div class="rounded-lg border ${sev} p-2.5 text-sm">
        <p class="font-bold mb-0.5">${ad.title}</p>
        <p class="text-xs opacity-90 leading-relaxed">${ad.detail}</p>${sug}</div>`
    }).join('') || `<p class="text-slate-500 text-sm">توصیهٔ فعالی نیست؛ معامله را طبقِ برنامه نگه‌دار.</p>`

    inner = `
      <div class="grid grid-cols-2 gap-2 text-center mb-3" dir="ltr">
        <div class="bg-slate-800/70 rounded-lg p-2">
          <div class="text-[11px] text-slate-400">سود/زیان (R)</div>
          <div class="font-bold tabular-nums ${pnlColor}">${st.pnlR >= 0 ? '+' : ''}${fmt(st.pnlR, 2)}R</div>
        </div>
        <div class="bg-slate-800/70 rounded-lg p-2">
          <div class="text-[11px] text-slate-400">پیشرفت به TP</div>
          <div class="font-bold text-slate-100 tabular-nums">${fmt(st.progressToTp, 0)}%</div>
        </div>
      </div>
      <div class="rounded-lg bg-sky-500/10 border border-sky-500/30 p-2.5 mb-3">
        <p class="text-xs text-sky-300 font-bold mb-0.5">جمع‌بندیِ اقدام</p>
        <p class="text-sm text-slate-200">${st.overallNote}</p>
      </div>
      <div class="space-y-2">${advList}</div>`
  }

  return `
    <div class="rounded-lg bg-sky-500/10 border border-sky-500/30 p-3 mb-3">
      <p class="font-bold text-sky-300 mb-1"><i class="fas fa-gears ml-1"></i>مدیریتِ معاملهٔ ${dirFa}</p>
      <div class="flex justify-between text-xs text-slate-400 mt-1" dir="ltr">
        <span>Entry ${fmt(trade.entry, a.decimals)}</span>
        <span class="text-emerald-400">TP ${fmt(trade.tp, a.decimals)}</span>
        <span class="text-rose-400">SL ${fmt(trade.sl, a.decimals)}</span>
      </div>
    </div>
    ${inner}
    <button class="btn-close mt-3 w-full py-2.5 rounded-lg bg-rose-700 hover:bg-rose-600 font-bold text-white transition" data-asset="${a.id}">
      <i class="fas fa-xmark ml-2"></i>بستنِ معامله (حذف)
    </button>`
}

// -------------------------- جدولِ شاخص‌ها (شفافیت) --------------------------
function renderIndicators(d) {
  const rows = (d.indicators || []).map(i => `
    <div class="flex justify-between py-1 border-b border-slate-800/60 last:border-0">
      <span class="text-slate-400">${i.name}</span>
      <span class="font-medium ${indStatusColor(i.status)} tabular-nums" dir="ltr">${i.value}</span>
    </div>`).join('')
  return `
    <details class="mt-1 text-sm">
      <summary class="cursor-pointer text-slate-500 hover:text-slate-300 text-xs py-1">
        <i class="fas fa-list-ul ml-1"></i>شاخص‌های تصمیم (شفافیت)
      </summary>
      <div class="mt-1 px-1">${rows}</div>
    </details>`
}

// ============================================================================
// رویدادها
// ============================================================================
function bindEvents() {
  // --- باگ #۲: دکمهٔ بروزرسانیِ دستیِ داده‌ها (User Note) ---
  // هم تصمیم/سیگنال (/api/decision) و هم قیمتِ زندهٔ کارت‌ها (/api/spots) را فوراً
  // به‌روز می‌کند و بازخوردِ بصری می‌دهد؛ مستقل از تایمرِ خودکارِ ۳۰ ثانیه.
  const refreshBtn = document.getElementById('manual-refresh')
  if (refreshBtn) {
    refreshBtn.onclick = async () => {
      const span = refreshBtn.querySelector('span')
      const icon = refreshBtn.querySelector('i')
      refreshBtn.disabled = true
      if (icon) icon.classList.add('fa-spin')
      if (span) span.textContent = 'در حال بروزرسانی…'
      try {
        await Promise.all([refreshAll(), refreshSpots()])
      } finally {
        // render() داخلِ refreshAll دوباره دکمه را می‌سازد؛ پس المانِ تازه را می‌گیریم.
        const b = document.getElementById('manual-refresh')
        if (b) {
          b.disabled = false
          const s = b.querySelector('span'), ic = b.querySelector('i')
          if (ic) ic.classList.remove('fa-spin')
          if (s) s.textContent = 'بروزرسانیِ دستیِ داده‌ها'
        }
      }
    }
  }

  // --- L41: اعمالِ سرمایه/ریسک ---
  const applyBtn = document.getElementById('cap-apply')
  if (applyBtn) {
    applyBtn.onclick = () => {
      const cap = parseFloat(document.getElementById('cap-input').value)
      const risk = parseFloat(document.getElementById('risk-input').value)
      if (isFinite(cap) && cap >= 100) setCapital(cap)
      if (isFinite(risk) && risk >= 0.1 && risk <= 5) setRisk(risk)
      applyBtn.textContent = 'در حال محاسبه…'
      refreshAll().then(() => { const b = document.getElementById('cap-apply'); if (b) b.textContent = 'اعمال' })
    }
  }
  document.querySelectorAll('.btn-register').forEach(btn => {
    btn.onclick = () => {
      const d = btn.dataset
      const trade = {
        side: d.dir === 'LONG' ? 'long' : 'short',
        entry: Number(d.entry), tp: Number(d.tp), sl: Number(d.sl),
        modelProbPct: d.prob ? Number(d.prob) : undefined,
        openedAt: Math.floor(Date.now() / 1000),
      }
      setTrade(d.asset, trade)
      store[d.asset] = store[d.asset] || {}
      store[d.asset].adviceStatus = null
      render()
      refreshAdvice(d.asset)
    }
  })
  document.querySelectorAll('.btn-close').forEach(btn => {
    btn.onclick = () => {
      if (confirm('معامله بسته و حذف شود؟')) {
        setTrade(btn.dataset.asset, null)
        const s = store[btn.dataset.asset]; if (s) { s.adviceStatus = null; s.adviceError = null }
        render()
      }
    }
  })
  document.querySelectorAll('.btn-apply').forEach(btn => {
    btn.onclick = () => {
      const asset = btn.dataset.asset
      const trade = getTrade(asset)
      if (!trade) return
      trade[btn.dataset.field] = Number(btn.dataset.value)
      setTrade(asset, trade)
      refreshAdvice(asset)
    }
  })
}

// ============================================================================
// دریافتِ داده
// ============================================================================
async function refreshAll() {
  try {
    const res = await fetch(`/api/decision?capital=${getCapital()}&risk=${getRisk()}`)
    const data = await res.json()
    if (!data.ok) throw new Error(data.error || 'خطای سرور')
    if (!assetsMeta.length) {
      assetsMeta = data.assets.map(a => ({ id: a.asset, name: a.name, decimals: a.decimals || 2, layer: a.layer || 'swing' }))
    }
    data.assets.forEach(a => {
      store[a.asset] = store[a.asset] || {}
      if (a.ok) {
        store[a.asset].decision = a.decision
        store[a.asset].price = a.price
        store[a.asset].error = null
      } else {
        store[a.asset].error = a.error
      }
    })
    render()
    lastFetchAt = Date.now()   // لحظهٔ دریافتِ این پاسخ (ساعتِ خودِ مرورگر)
    const lu = document.getElementById('last-update')
    if (lu) lu.textContent = 'آخرین به‌روزرسانی: ' + timeAgoSince(lastFetchAt)
    // برای دارایی‌هایی که کاربر معامله دارد، advice را هم به‌روز کن
    assetsMeta.forEach(a => { if (getTrade(a.id)) refreshAdvice(a.id) })
  } catch (e) {
    if (!assetsMeta.length) {
      app.innerHTML = `<div class="text-center text-rose-400 p-8"><i class="fas fa-triangle-exclamation text-2xl mb-2"></i><p>خطا در اتصال به سرور: ${e.message}</p></div>`
    }
  }
}

async function refreshAdvice(asset) {
  const trade = getTrade(asset)
  if (!trade) return
  try {
    const res = await fetch('/api/trade/advice', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset, trade: { side: trade.side, entry: trade.entry, tp: trade.tp, sl: trade.sl, openedAt: trade.openedAt }, modelProbPct: trade.modelProbPct }),
    })
    const data = await res.json()
    store[asset] = store[asset] || {}
    if (data.ok) {
      store[asset].adviceStatus = data.status
      store[asset].price = data.price
      store[asset].adviceError = null
    } else {
      store[asset].adviceError = data.error
    }
    render()
  } catch (e) {
    store[asset] = store[asset] || {}
    store[asset].adviceError = e.message
    render()
  }
}

// ============================================================================
// پُلینگِ سریعِ قیمتِ زنده (هر ~۲ ثانیه) — پاسخ به User Note (نکتهٔ اول)
// ----------------------------------------------------------------------------
// فقط عددِ قیمتِ کارت‌ها را به‌روز می‌کند (نه سیگنال/تصمیم که سنگین است). این کار
// حسِ «قیمتِ زندهٔ لحظه‌ای» را می‌دهد بدونِ فشار به سرور. سیگنال/تصمیم همچنان با
// REFRESH_MS از /api/decision می‌آید. تغییرِ قیمت با فلاشِ سبز/قرمز نشان داده می‌شود.
// ============================================================================
const SPOT_MS = 2000
const lastSpot = {}   // آخرین قیمتِ هر دارایی برای تشخیصِ جهتِ تغییر

function applySpot(asset, price, ageSec, decimals) {
  const el = document.getElementById('price-' + asset)
  if (!el || price == null || !isFinite(price)) return
  const prev = lastSpot[asset]
  el.textContent = fmt(price, decimals)
  // فلاشِ رنگ بر اساسِ جهتِ تغییر
  if (prev != null && price !== prev) {
    const up = price > prev
    el.classList.remove('price-up', 'price-down')
    void el.offsetWidth   // ری‌استارتِ انیمیشن
    el.classList.add(up ? 'price-up' : 'price-down')
  }
  lastSpot[asset] = price
  // سنِ قیمت (اگر تازه نبود هشدار بده)
  const ageEl = document.getElementById('price-age-' + asset)
  if (ageEl) {
    if (ageSec != null && ageSec > 180) ageEl.textContent = `(${Math.round(ageSec/60)} دقیقه تأخیر)`
    else ageEl.textContent = ''
  }
  // قیمتِ زنده را در store هم نگه می‌داریم تا render بعدی از آن استفاده کند
  if (store[asset]) store[asset].price = price
}

async function refreshSpots() {
  try {
    const res = await fetch('/api/spots')
    const data = await res.json()
    if (!data.ok) return
    const decMap = {}
    assetsMeta.forEach(a => { decMap[a.id] = a.decimals })
    data.spots.forEach(s => {
      if (s.ok) applySpot(s.asset, s.price, s.ageSec, decMap[s.asset] ?? 2)
    })
  } catch { /* بی‌صدا؛ پُلینگِ بعدی دوباره تلاش می‌کند */ }
}

// ============================================================================
// شروع
// ============================================================================
refreshAll()
setInterval(refreshAll, REFRESH_MS)
// پُلینگِ سریعِ قیمت (هر ۲ ثانیه) — سبک، فقط قیمت
setInterval(refreshSpots, SPOT_MS)
// هر ثانیه فقط متنِ «چند ثانیه پیش» را زنده به‌روز می‌کنیم (بدون فراخوانِ سرور).
setInterval(() => {
  const lu = document.getElementById('last-update')
  if (lu && lastFetchAt) lu.textContent = 'آخرین به‌روزرسانی: ' + timeAgoSince(lastFetchAt)
}, 1000)
