// ============================================================================
// ui/journal.js — پنلِ «تاریخچهٔ سیگنال‌ها» + اعلانِ مرورگر (User Note)
// ----------------------------------------------------------------------------
// ماژولِ مستقل (گرهٔ UI جدا، ROS2-گونه): فقط از /api/journal می‌خواند و به app.js
// دست نمی‌زند. دکمهٔ شناور «📒 تاریخچه» یک پنل باز می‌کند:
//   «فلان لایه روی فلان کارت روی فلان قیمت فلان سیگنال را داد و گفت تا فلان قیمت می‌رود»
//   + نتیجهٔ واقعی (TP/SL/انقضا) + آمارِ زندهٔ هر لایه.
// اعلانِ مرورگر: اگر کاربر اجازه بدهد، هر رکوردِ تازه (تا وقتی تب باز است) اعلام
// می‌شود. اعلانِ پس‌زمینهٔ واقعی روی گوشی کارِ watcher.mjs (termux-notification) است.
// ============================================================================

const POLL_MS = 30000
const LS_SEEN = 'journal.lastSeenSeq.v1'
const TFS = ['M5', 'M15', 'M30', 'H1', 'H4', 'H6', 'H8', 'H12', 'D1']

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
const f2 = (n) => (typeof n === 'number' && isFinite(n) ? n.toFixed(2) : '—')
const tehran = (ms) => {
  try { return new Date(ms).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  catch { return new Date(ms).toISOString().slice(5, 16).replace('T', ' ') }
}
const statusBadge = (r) => ({
  OPEN: '<span class="text-sky-300">⏳ باز</span>',
  TP: '<span class="text-emerald-300">✅ TP</span>',
  SL: '<span class="text-rose-300">❌ SL</span>',
  EXPIRED: '<span class="text-amber-300">⌛ انقضا</span>',
}[r.status] || r.status)

let records = [], stats = null, filterTf = '', open = false, lastSeq = 0

function ensureDom() {
  if (document.getElementById('journal-fab')) return
  const fab = document.createElement('button')
  fab.id = 'journal-fab'
  fab.type = 'button'
  fab.setAttribute('aria-label', 'تاریخچهٔ سیگنال‌ها')
  fab.style.cssText = 'position:fixed;bottom:16px;left:16px;z-index:60;direction:rtl'
  fab.className = 'bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-100 rounded-full px-4 py-2 shadow-lg text-sm'
  fab.innerHTML = '📒 تاریخچه <span id="journal-badge" class="hidden ml-1 bg-emerald-500 text-black rounded-full px-2 text-xs"></span>'
  fab.onclick = () => toggle(!open)
  document.body.appendChild(fab)

  const panel = document.createElement('section')
  panel.id = 'journal-panel'
  panel.setAttribute('aria-label', 'تاریخچهٔ سیگنال‌ها')
  panel.style.cssText = 'position:fixed;inset:0;z-index:70;display:none;direction:rtl;background:rgba(2,6,23,.96);overflow:auto'
  panel.innerHTML = `
    <div class="max-w-5xl mx-auto p-4 text-slate-100">
      <header class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-bold">📒 تاریخچهٔ سیگنال‌ها</h2>
        <div class="flex gap-2">
          <button id="journal-notify" type="button" class="text-xs bg-slate-700 rounded px-3 py-1">🔔 اعلانِ مرورگر</button>
          <button id="journal-close" type="button" class="text-xs bg-slate-700 rounded px-3 py-1">✕ بستن</button>
        </div>
      </header>
      <p class="text-xs text-slate-400 mb-3">هر سیگنالِ ورود که سرور تولید کند — حتی وقتی صفحه بسته است (روی گوشی با نگهبانِ پس‌زمینه) —
        این‌جا با قیمتِ لحظه، هدف و حدِ ضرر ثبت و سپس با کندل‌های واقعی <b>حل</b> می‌شود. اگر TP و SL در یک کندل لمس شوند، محافظه‌کارانه SL حساب می‌شود.</p>
      <nav id="journal-tfs" class="flex flex-wrap gap-1 mb-3"></nav>
      <div id="journal-stats" class="mb-4"></div>
      <div id="journal-list"></div>
    </div>`
  document.body.appendChild(panel)
  panel.querySelector('#journal-close').onclick = () => toggle(false)
  panel.querySelector('#journal-notify').onclick = askNotify
}

function toggle(v) {
  open = v
  document.getElementById('journal-panel').style.display = v ? 'block' : 'none'
  if (v) { markSeen(); render() }
}

function markSeen() {
  try { localStorage.setItem(LS_SEEN, String(lastSeq)) } catch {}
  updateBadge()
}

function updateBadge() {
  const seen = parseInt(localStorage.getItem(LS_SEEN) || '0', 10) || 0
  const n = records.filter(r => r.seq > seen).length
  const b = document.getElementById('journal-badge')
  if (!b) return
  b.textContent = n ? String(n) : ''
  b.classList.toggle('hidden', !n)
}

function render() {
  if (!open) return
  const tfs = document.getElementById('journal-tfs')
  tfs.innerHTML = ['', ...TFS].map(tf =>
    `<button type="button" data-tf="${tf}" class="text-xs rounded px-2 py-1 ${filterTf === tf ? 'bg-sky-600' : 'bg-slate-700'}">${tf || 'همه'}</button>`).join('')
  tfs.querySelectorAll('button').forEach(b => { b.onclick = () => { filterTf = b.dataset.tf; render() } })

  const rows = (stats?.rows || []).filter(s => !filterTf || s.tf === filterTf)
  document.getElementById('journal-stats').innerHTML = rows.length ? `
    <h3 class="text-sm font-bold mb-1">آمارِ زنده (فقط شاهدهای مستقل)</h3>
    <div class="overflow-x-auto"><table class="w-full text-xs">
      <thead class="text-slate-400"><tr><th class="text-right">کارت</th><th>لایه</th><th>سیگنال</th><th>باز</th><th>بسته</th><th>WR</th><th>PF</th><th>R میانگین</th><th>pip جمع</th></tr></thead>
      <tbody>${rows.map(s => `<tr class="border-t border-slate-800 text-center">
        <td class="text-right">${esc(s.tf)}</td><td>${esc(s.layer)}</td><td>${s.signals}${s.alternates ? ` <span class="text-slate-500">(${s.alternates} بدیل)</span>` : ''}</td>
        <td>${s.open}</td><td>${s.closed}</td><td>${s.winRate == null ? '—' : s.winRate + '٪'}</td><td>${s.pf ?? '—'}</td>
        <td>${s.avgR ?? '—'}</td><td class="${s.sumPips >= 0 ? 'text-emerald-300' : 'text-rose-300'}">${s.sumPips}</td></tr>`).join('')}</tbody>
    </table></div>
    <p class="text-[11px] text-slate-500 mt-1">⚠️ با n کوچک این اعداد نویز است؛ معیارِ پذیرش همچنان RQS2 روی دادهٔ تاریخی است. ارزشِ این جدول، سنجشِ «زنده در برابرِ بک‌تست» در گذرِ زمان است.</p>`
    : '<p class="text-xs text-slate-500">هنوز سیگنالی ثبت نشده است.</p>'

  const list = records.filter(r => !filterTf || r.tf === filterTf).slice().reverse()
  document.getElementById('journal-list').innerHTML = list.length ? list.map(r => {
    const dir = r.direction === 'LONG' ? '<b class="text-emerald-300">خرید</b>' : '<b class="text-rose-300">فروش</b>'
    const res = r.status === 'OPEN' ? '' : ` · خروج ${f2(r.exitPrice)} · <b>${r.pips > 0 ? '+' : ''}${r.pips} pip</b> (${r.rMultiple}R) پس از ${r.barsHeld} کندل`
    const notes = (r.notes || []).map(n => `<div class="text-[11px] text-amber-300">⚠️ ${esc(n)}</div>`).join('')
    return `<article class="journal-record border border-slate-800 rounded p-2 mb-2 text-sm ${r.independent ? '' : 'opacity-70'}">
      <div class="flex justify-between"><span>${tehran(r.createdAt)} · کارتِ <b>${esc(r.tf)}</b></span>${statusBadge(r)}</div>
      <div>لایهٔ <b>${esc(r.layer)}</b> <span class="text-slate-400">(${esc(r.layerName)})</span> روی قیمتِ <b>${f2(r.priceAtSignal)}</b> سیگنالِ ${dir} داد
        و گفت تا <b>${f2(r.tp)}</b> می‌رود (ورود ${f2(r.entry)} · حدِ ضرر ${f2(r.sl)}${r.rr ? ' · RR ' + f2(r.rr) : ''}).</div>
      <div class="text-xs text-slate-400">بیشینهٔ حرکتِ موافق ${r.mfePips ?? 0} pip · مخالف ${r.maePips ?? 0} pip${res}</div>
      ${notes}</article>`
  }).join('') : ''
}

async function poll() {
  try {
    const [j, s] = await Promise.all([
      fetch('/api/journal?limit=500').then(r => r.json()),
      fetch('/api/journal/stats').then(r => r.json()),
    ])
    if (j?.ok) {
      const prev = lastSeq
      records = j.records; lastSeq = j.lastSeq || 0
      if (prev && 'Notification' in window && Notification.permission === 'granted') {
        for (const r of records.filter(x => x.seq > prev)) {
          try {
            new Notification(`${r.direction === 'LONG' ? '🟢 خرید' : '🔴 فروش'} ${r.tf} — ${r.layer}`,
              { body: `قیمت ${f2(r.priceAtSignal)} · TP ${f2(r.tp)} · SL ${f2(r.sl)}`, tag: 'sig-' + r.seq })
          } catch {}
        }
      }
    }
    if (s?.ok) stats = s
    updateBadge(); render()
  } catch { /* بی‌صدا */ }
}

async function askNotify() {
  if (!('Notification' in window)) { alert('این مرورگر اعلان را پشتیبانی نمی‌کند. روی گوشی از نگهبانِ Termux استفاده کنید.'); return }
  const p = await Notification.requestPermission()
  alert(p === 'granted' ? 'اعلانِ مرورگر فعال شد (تا وقتی این تب باز است).' : 'اجازهٔ اعلان داده نشد.')
}

ensureDom()
poll()
setInterval(poll, POLL_MS)
