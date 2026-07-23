// =============================================================================
//  cf-shim.mjs — جایگزینِ ماژولِ 'hono/cloudflare-workers' برای اجرا روی Node/Termux
// =============================================================================
//  چرا این فایل؟
//    اپِ اصلیِ سایت (web_tool/src/index.tsx) این‌طور استاتیک را سرو می‌کند:
//        import { serveStatic } from 'hono/cloudflare-workers'
//        app.use('/static/*', serveStatic({ root: './public' }))
//    این نسخهٔ Cloudflare فقط داخلِ Workerd/Wrangler کار می‌کند و روی Node/گوشی
//    اجرا نمی‌شود. به‌جای عوض‌کردنِ کدِ اصلیِ سایت (که «منطقِ سایت» را دست‌نخورده
//    نگه می‌داریم)، هنگامِ باندل‌سازی این ماژول را «alias» می‌کنیم تا esbuild
//    importِ بالا را به این فایل نگاشت کند.
//
//    این نسخه از `hono/serve-static` (نسخهٔ عامِ Hono) استفاده می‌کند و محتوای
//    فایل را با ماژولِ `fs` نود از پوشهٔ public می‌خواند. مسیرِ پوشهٔ public از
//    متغیرِ محیطیِ WEBTOOL_PUBLIC خوانده می‌شود (server.mjs آن را تنظیم می‌کند).
// =============================================================================

import { serveStatic as honoServeStatic } from 'hono/serve-static'
import { readFile, stat } from 'node:fs/promises'
import { join, normalize } from 'node:path'

// پوشهٔ public سایت. server.mjs این را قبل از بارگذاریِ باندل تنظیم می‌کند.
// مقدارِ پیش‌فرض: ../web_tool/public نسبت به این فایل (اگر متغیر ست نشده باشد).
const PUBLIC_ROOT =
  process.env.WEBTOOL_PUBLIC ||
  new URL('../web_tool/public', import.meta.url).pathname

export function serveStatic(options = {}) {
  // اپ با { root: './public' } صدا می‌زند؛ ما آن root نسبی را نادیده می‌گیریم و
  // مسیرِ مطلقِ واقعیِ public را (PUBLIC_ROOT) مبنا قرار می‌دهیم. rewriteRequestPath
  // اگر داده شده بود، محترم شمرده می‌شود.
  const rewrite = options.rewriteRequestPath
  return honoServeStatic({
    ...options,
    // getContent محتوای فایل را برمی‌گرداند (Uint8Array) یا null اگر نبود.
    getContent: async (path /* مثلا 'public/static/style.css' */, c) => {
      try {
        // Hono مسیر را به شکلِ 'public/...'（همان root که پاس دادیم）می‌سازد؛
        // ما بخشِ 'public/' ابتدایی را حذف کرده و به PUBLIC_ROOT می‌چسبانیم.
        let rel = decodeURIComponent(path)
        if (typeof rewrite === 'function') rel = rewrite(rel)
        rel = rel.replace(/^\.?\/?public\/?/, '')
        // جلوگیری از path-traversal
        const safe = normalize(rel).replace(/^(\.\.(\/|\\|$))+/, '')
        const full = join(PUBLIC_ROOT, safe)
        const s = await stat(full)
        if (!s.isFile()) return null
        const buf = await readFile(full)
        return new Uint8Array(buf)
      } catch {
        return null
      }
    },
  })
}

export default { serveStatic }
