// =============================================================================
//  server.mjs — سرورِ لوکالِ سایتِ کامل روی Node/Termux (بدونِ هیچ npm install)
// =============================================================================
//  این فایل باندلِ آماده (app.bundle.mjs) را که «کلِ منطقِ سایت» را دارد بارگذاری
//  و روی شبکهٔ محلی (LAN) سرو می‌کند. هیچ وابستگیِ خارجی لازم نیست: فقط ماژول‌های
//  داخلیِ Node (node:http, node:fs) استفاده می‌شوند تا روی گوشی/ترموکس بدونِ
//  `npm install` هم اجرا شود.
//
//  اجرا:
//      node server.mjs
//  یا با پورت/هاست دلخواه:
//      PORT=8080 HOST=0.0.0.0 node server.mjs
//
//  چرا node:http خام؟ چون @hono/node-server یک وابستگیِ اضافه است؛ با تبدیلِ
//  دستیِ IncomingMessage → Web Request و Web Response → ServerResponse، اپِ Hono
//  (که app.fetch(request) دارد) بدونِ هیچ پکیجِ اضافه اجرا می‌شود.
// =============================================================================

import { createServer } from 'node:http'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { networkInterfaces } from 'node:os'
import { existsSync } from 'node:fs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = parseInt(process.env.PORT || '8080', 10)
const HOST = process.env.HOST || '0.0.0.0' // 0.0.0.0 = قابل‌دسترس در کلِ شبکهٔ محلی

// مسیرِ پوشهٔ public سایت را به shim می‌دهیم تا /static/* درست سرو شود.
const PUBLIC = join(__dirname, '..', 'web_tool', 'public')
process.env.WEBTOOL_PUBLIC = PUBLIC

// باندلِ آماده (کلِ منطقِ سایت). اگر نبود، راهنماییِ ساخت می‌دهیم.
const BUNDLE = join(__dirname, 'app.bundle.mjs')
if (!existsSync(BUNDLE)) {
  console.error('❌ فایلِ app.bundle.mjs یافت نشد.')
  console.error('   اگر روی کامپیوتر/سندباکس هستید، یک‌بار بسازید:')
  console.error('     cd local-mobile && node build.mjs')
  console.error('   (روی گوشی نیازی به ساخت نیست؛ فقط git pull بزنید تا باندلِ آماده بیاید.)')
  process.exit(1)
}

const mod = await import('./app.bundle.mjs')
const app = mod.default
if (!app || typeof app.fetch !== 'function') {
  console.error('❌ باندل، اپِ Hono معتبری export نکرد (app.fetch یافت نشد).')
  process.exit(1)
}

// --- تبدیلِ درخواستِ Node به Web Request -----------------------------------
function toWebRequest(req) {
  const proto = 'http'
  const host = req.headers.host || `${HOST}:${PORT}`
  const url = `${proto}://${host}${req.url}`
  const headers = new Headers()
  for (const [k, v] of Object.entries(req.headers)) {
    if (Array.isArray(v)) v.forEach((x) => headers.append(k, x))
    else if (v != null) headers.set(k, v)
  }
  const method = req.method || 'GET'
  const hasBody = method !== 'GET' && method !== 'HEAD'
  return new Promise((resolve) => {
    if (!hasBody) {
      resolve(new Request(url, { method, headers }))
      return
    }
    const chunks = []
    req.on('data', (c) => chunks.push(c))
    req.on('end', () => {
      const body = Buffer.concat(chunks)
      resolve(new Request(url, { method, headers, body }))
    })
  })
}

// --- نوشتنِ Web Response در پاسخِ Node --------------------------------------
async function sendWebResponse(res, webRes) {
  res.statusCode = webRes.status
  webRes.headers.forEach((value, key) => res.setHeader(key, value))
  if (webRes.body) {
    const buf = Buffer.from(await webRes.arrayBuffer())
    res.end(buf)
  } else {
    res.end()
  }
}

const server = createServer(async (req, res) => {
  try {
    const webReq = await toWebRequest(req)
    const webRes = await app.fetch(webReq, {}, {})
    await sendWebResponse(res, webRes)
  } catch (err) {
    console.error('[خطای سرور]', err)
    res.statusCode = 500
    res.setHeader('content-type', 'text/plain; charset=utf-8')
    res.end('Internal Server Error: ' + (err?.message || err))
  }
})

// --- یافتنِ IP محلی برای نمایش به کاربر (تا دوستش هم وصل شود) ---------------
function localIPs() {
  const nets = networkInterfaces()
  const ips = []
  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      if (net.family === 'IPv4' && !net.internal) ips.push(net.address)
    }
  }
  return ips
}

function printBanner(actualPort) {
  const line = '='.repeat(58)
  console.log(line)
  console.log('  🧭 دستیارِ تصمیمِ معاملاتی — موتورِ کاملِ سایت (لوکال)')
  console.log(line)
  console.log(`  روی همین گوشی      : http://localhost:${actualPort}`)
  const ips = localIPs()
  if (ips.length) {
    console.log('  در شبکهٔ محلی (LAN) — این آدرس را به دوستتان بدهید:')
    for (const ip of ips) console.log(`      http://${ip}:${actualPort}`)
  } else {
    console.log('  (فعلاً به شبکهٔ محلی وصل نیستید؛ فقط localhost در دسترس است.)')
  }
  console.log(line)
  console.log('  توقف: کلیدهای Ctrl+C')
  console.log(line)
}

// --- شروعِ گوش‌دادن با «تلاشِ خودکارِ پورتِ بعدی» -----------------------------
// نکته مهمِ Termux/اندروید: اگر یک سرورِ قبلی هنوز روی این پورت زنده مانده باشد
// (و kill نشده باشد)، به‌جای کرش‌کردن با EADDRINUSE، به‌طور خودکار پورتِ بعدی را
// امتحان می‌کنیم تا سرور همیشه بالا بیاید. برای همین دیگر لازم نیست حتماً سرورِ
// قدیمی را دستی بکشید.
const MAX_PORT_TRIES = 20

// --- پیش‌گرم‌سازیِ کش (Pre-warm) — ایدهٔ سرعت برای گوشی --------------------
// به‌محضِ بالا آمدنِ سرور، در *پس‌زمینه* یک‌بار همهٔ دارایی‌ها را از طریقِ خودِ اپ
// صدا می‌زنیم تا کشِ حافظه‌ایِ داخلِ باندل «گرم» شود. نتیجه: *اولین* کاربری هم که
// صفحه را باز می‌کند، کارت‌ها را تقریباً فوری می‌بیند (به‌جای انتظارِ سرد برای Yahoo).
// این کار کاملاً بی‌صداست و اگر شبکه در دسترس نباشد هیچ خطایی نشان نمی‌دهد.
async function prewarm(port) {
  try {
    const base = `http://127.0.0.1:${port}`
    // فهرستِ سبکِ کارت‌ها را می‌گیریم و برای هرکدام یک‌بار decision را گرم می‌کنیم.
    const listRes = await app.fetch(new Request(`${base}/api/assets`), {}, {})
    const list = await listRes.json().catch(() => null)
    const ids = (list && list.ok && Array.isArray(list.assets)) ? list.assets.map(a => a.id) : []
    if (!ids.length) return
    console.log(`  🔥 در حالِ پیش‌گرم‌سازیِ کش برای ${ids.length} دارایی (در پس‌زمینه)...`)
    // به‌صورتِ موازی ولی مقاوم به خطا؛ منتظرِ کاربر نمی‌مانیم.
    await Promise.allSettled(ids.map(id =>
      app.fetch(new Request(`${base}/api/decision/${id}`), {}, {}).then(r => r.arrayBuffer())
    ))
    console.log('  ✅ کش گرم شد — بارگذاریِ بعدی فوری خواهد بود.')
  } catch { /* بی‌صدا: pre-warm اختیاری است */ }
}

function startListening(port, triesLeft) {
  server.listen(port, HOST, () => {
    printBanner(port)
    // چند لحظه بعد از بالا آمدن، در پس‌زمینه کش را گرم کن (بلوکه‌کننده نیست).
    setTimeout(() => { void prewarm(port) }, 500)
  })
}

server.on('error', (err) => {
  if (err && err.code === 'EADDRINUSE') {
    const busy = err.port || PORT
    const next = busy + 1
    if (next - PORT < MAX_PORT_TRIES) {
      console.log(`  ⚠️  پورتِ ${busy} اشغال است (احتمالاً سرورِ قبلی هنوز روشن است) → امتحانِ پورتِ ${next} ...`)
      // اجازه می‌دهیم رویدادِ error تمام شود، بعد دوباره listen می‌کنیم.
      setTimeout(() => server.listen(next, HOST, () => {
        printBanner(next)
        setTimeout(() => { void prewarm(next) }, 500)   // پیش‌گرم‌سازی روی پورتِ واقعی
      }), 300)
      return
    }
    console.error(`❌ هیچ پورتِ آزادی بینِ ${PORT} تا ${PORT + MAX_PORT_TRIES} پیدا نشد.`)
    console.error('   لطفاً همهٔ سرورهای قبلی را ببندید: bash stop.sh')
    process.exit(1)
  }
  console.error('❌ خطای سرور:', err)
  process.exit(1)
})

startListening(PORT, MAX_PORT_TRIES)
