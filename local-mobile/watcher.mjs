// =============================================================================
//  watcher.mjs — نگهبانِ پس‌زمینه: «بدونِ باز بودنِ صفحه، هیچ سیگنالی گم نشود»
// =============================================================================
//  ریشهٔ مشکلِ «هیچ‌وقت سیگنال ندیدم» (اندازه‌گیری‌شده — results/_signal_drought):
//    لایه‌ها سیگنال می‌دهند، ولی هر رویدادِ HTF فقط **یک کندل** زنده است و در ساعتِ
//    خاصی می‌آید (D1 همیشه ۰۳:۳۰ تهران). سایت فقط «حالِ حاضر» را نشان می‌دهد و فقط
//    وقتی کسی صفحه را باز کرده تصمیم می‌گیرد ⇒ سیگنال بی‌ردپا گم می‌شد.
//
//  این ماژول داخلِ server.mjs اجرا می‌شود و:
//    ۱) هر کارت را درست **کمی پس از بسته‌شدنِ کندلش** (+۲۰ ثانیه) و یک‌بار هم هر
//       ۶۰ ثانیه (برای کارت‌های ریز) خودش صدا می‌زند ⇒ دفترِ تاریخچه پر می‌شود.
//    ۲) هر رکوردِ تازهٔ دفتر (/api/journal?since=) را با `termux-notification`
//       (صدا + لرزش) اعلام می‌کند. اگر termux-api نصب نبود، فقط در کنسول چاپ می‌کند.
//    ۳) نتیجهٔ هر سیگنال (TP/SL/انقضا) را هم اعلام می‌کند.
//
//  خاموش‌کردن: WATCH=0 node server.mjs
// =============================================================================

import { execFile } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

// طولِ کندلِ هر کارت (ثانیه) — باید با GOLD_TF/sigGap در index.tsx هم‌خوان باشد.
const CARD_GAP = {
  'XAUUSD-M5': 300, 'XAUUSD': 900, 'XAUUSD-M30': 1800, 'XAUUSD-H1': 3600,
  'XAUUSD-H4': 14400, 'XAUUSD-H6': 21600, 'XAUUSD-H8': 28800,
  'XAUUSD-H12': 43200, 'XAUUSD-D1': 86400,
}
const AFTER_CLOSE_SEC = 20     // چند ثانیه بعد از بسته‌شدن (تا Yahoo کندل را بدهد)
const TICK_MS = 15_000

function hasCmd(cmd) {
  const dirs = (process.env.PATH || '').split(':')
  return dirs.some(d => d && existsSync(join(d, cmd)))
}

const fa = (n, d = 2) => (typeof n === 'number' && isFinite(n) ? n.toFixed(d) : '—')
const dirFa = (d) => (d === 'LONG' ? '🟢 خرید' : '🔴 فروش')
const tehran = (ms) => new Date(ms + 12_600_000).toISOString().slice(11, 16)

export function startWatcher({ app, dataDir, log = console.log }) {
  if (process.env.WATCH === '0') { log('  ⏸  نگهبانِ پس‌زمینه خاموش است (WATCH=0).'); return }
  const notifyOK = hasCmd('termux-notification')
  const stateFile = join(dataDir, 'watcher-state.json')
  let state = { lastSeq: 0, notifiedOutcome: {} }
  try { mkdirSync(dataDir, { recursive: true }); state = { ...state, ...JSON.parse(readFileSync(stateFile, 'utf8')) } } catch {}
  const save = () => { try { writeFileSync(stateFile, JSON.stringify(state)) } catch {} }

  const call = async (path) => {
    const r = await app.fetch(new Request(`http://127.0.0.1${path}`), {}, {})
    return r.json()
  }

  function notify(id, title, content, urgent) {
    log(`  🔔 ${title} — ${content.replace(/\n/g, ' | ')}`)
    if (!notifyOK) return
    const args = ['--id', String(id), '--title', title, '--content', content,
      '--priority', urgent ? 'max' : 'high', '--sound', '--vibrate', urgent ? '400,200,400' : '200',
      '--led-color', urgent ? '00ff00' : 'ffaa00', '--group', 'xau-signals']
    execFile('termux-notification', args, () => {})
    if (urgent && hasCmd('termux-tts-speak') && process.env.SPEAK === '1') execFile('termux-tts-speak', ['سیگنالِ تازهٔ طلا'], () => {})
  }

  // زمانِ بررسیِ بعدیِ هر کارت (ms)
  const next = {}
  const now0 = Date.now()
  for (const [id, gap] of Object.entries(CARD_GAP)) next[id] = now0 + 3_000   // یک‌بار در شروع

  const scheduleNext = (id, now) => {
    const gap = CARD_GAP[id] * 1000
    const closeAt = Math.floor(now / gap) * gap + gap + AFTER_CLOSE_SEC * 1000
    // کارت‌های ریز (≤M30) هر ۶۰ ثانیه هم چک می‌شوند تا قیمتِ نزدیکِ TP/SL حل شود.
    next[id] = Math.min(closeAt, gap <= 1_800_000 ? now + 60_000 : closeAt)
  }

  let busy = false
  async function tick() {
    if (busy) return
    busy = true
    try {
      const now = Date.now()
      const due = Object.keys(next).filter(id => next[id] <= now)
      for (const id of due) {
        try { await call(`/api/decision/${id}`) } catch {}
        scheduleNext(id, Date.now())
      }
      if (due.length) await announce()
    } finally { busy = false }
  }

  async function announce() {
    let j
    try { j = await call(`/api/journal?since=0&limit=3000`) } catch { return }
    if (!j?.ok) return
    const fresh = j.records.filter(r => r.seq > state.lastSeq)
    for (const r of fresh) {
      const extra = r.independent ? '' : '\n⚠️ بدیل (همان رویدادِ کارتِ ' + (r.primaryCard || '?') + ') — شاهدِ دوم نیست'
      notify(1000 + (r.seq % 500),
        `${dirFa(r.direction)} ${r.tf} — ${r.layer}`,
        `قیمت ${fa(r.priceAtSignal)} · ورود ${fa(r.entry)}\nTP ${fa(r.tp)} · SL ${fa(r.sl)} · ساعتِ تهران ${tehran(r.createdAt)}${extra}`,
        r.independent)
    }
    if (fresh.length) state.lastSeq = Math.max(...fresh.map(r => r.seq), state.lastSeq)
    // اعلامِ نتیجه (یک‌بار برای هر رکورد)
    for (const r of j.records) {
      if (r.status === 'OPEN' || state.notifiedOutcome[r.seq]) continue
      if (r.seq <= state.lastSeq - 2000) continue
      state.notifiedOutcome[r.seq] = 1
      const icon = r.status === 'TP' ? '✅' : r.status === 'SL' ? '❌' : '⌛'
      notify(2000 + (r.seq % 500), `${icon} نتیجهٔ ${r.layer} ${r.tf}`,
        `${r.status} · ${r.pips > 0 ? '+' : ''}${fa(r.pips, 1)} pip (${fa(r.rMultiple)}R) · ${r.barsHeld} کندل`, false)
    }
    // جمع‌وجورکردنِ حافظهٔ اعلام‌شده‌ها
    const keys = Object.keys(state.notifiedOutcome)
    if (keys.length > 4000) for (const k of keys.slice(0, keys.length - 3000)) delete state.notifiedOutcome[k]
    save()
  }

  // اولین اجرا: رکوردهای قدیمی را «اعلام‌شده» فرض کن (سیلِ نوتیف پس از ری‌استارت نه).
  ;(async () => {
    try {
      const j = await call('/api/journal?since=0&limit=3000')
      if (j?.ok && state.lastSeq === 0) {
        state.lastSeq = j.lastSeq || 0
        for (const r of j.records) if (r.status !== 'OPEN') state.notifiedOutcome[r.seq] = 1
        save()
      }
    } catch {}
    setInterval(() => { void tick() }, TICK_MS)
    void tick()
    log(`  👁  نگهبانِ پس‌زمینه فعال شد — ${Object.keys(CARD_GAP).length} کارت، بررسی پس از بسته‌شدنِ هر کندل.`)
    log(notifyOK ? '  🔔 اعلانِ اندروید (termux-notification) آماده است.'
      : '  ℹ️  برای اعلانِ صدادار روی گوشی: pkg install termux-api  + نصبِ اپِ Termux:API')
    if (notifyOK) notify(999, '🧭 نگهبانِ سیگنال روشن شد', 'از این لحظه هر سیگنالِ تازه اعلام می‌شود.', false)
  })()
}
