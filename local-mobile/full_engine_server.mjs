// =============================================================================
//  سرورِ «موتورِ کامل» برای اجرای لوکالِ web_tool روی Node (بدونِ Vite/Wrangler/Workerd)
// =============================================================================
//  چرا این فایل؟
//    سایتِ کاملِ web_tool تمامِ لایه‌های رکورد (S67, S73, Overnight, Monday,
//    Turn-of-Month, Squeeze, SHORT-MA, Brooks High-2, Signs-of-Strength, و روترهای
//    مالتی‌تایم‌فریمِ طلا) را دارد — که موتورِ سادهٔ apk/www ندارد. این entry point همان
//    اپِ Hono را روی Node سبک اجرا می‌کند؛ فقط serveStatic کلادفلر را با نسخهٔ Node
//    جایگزین می‌کنیم. مصرفِ رمِ Node بسیار کمتر از زنجیرهٔ Vite+Wrangler+Workerd است.
//
//  ساختِ باندل (یک‌بار، در سندباکس یا کامپیوتر — نه روی گوشی):
//      cd web_tool
//      npx esbuild src/index.tsx --bundle --format=esm --platform=node \
//          --outfile=../local-mobile/_app_bundle.mjs \
//          --external:hono/cloudflare-workers
//  سپس:
//      node full_engine_server.mjs
//
//  توجه: چون web_tool هیچ importِ Node-specific (fs/path/process) ندارد و فقط از
//  Web Fetch API استفاده می‌کند، باندل روی Node v18+ بدونِ مشکل اجرا می‌شود.
// =============================================================================

import { serve } from '@hono/node-server'
import { serveStatic } from '@hono/node-server/serve-static'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PORT = parseInt(process.env.PORT || '8080', 10)
const HOST = process.env.HOST || '127.0.0.1'

// باندلِ ساخته‌شدهٔ اپ Hono (export default app)
const BUNDLE = join(__dirname, '_app_bundle.mjs')
if (!existsSync(BUNDLE)) {
  console.error('[FATAL] _app_bundle.mjs یافت نشد. ابتدا باندل را بسازید:')
  console.error('  cd web_tool && npx esbuild src/index.tsx --bundle --format=esm \\')
  console.error('    --platform=node --outfile=../local-mobile/_app_bundle.mjs \\')
  console.error('    --external:hono/cloudflare-workers')
  process.exit(1)
}

const mod = await import(BUNDLE)
const app = mod.default

// اپ در باندل، static را با serveStatic کلادفلر ثبت کرده که در Node کار نمی‌کند.
// ما یک لایهٔ static سازگارِ Node را «قبل از» app سوار می‌کنیم تا /static/* را بگیرد.
// چون Hono میدلورها به‌ترتیب اجرا می‌شوند، این هندلر زودتر پاسخ می‌دهد.
import { Hono } from 'hono'
const root = new Hono()
const PUBLIC = join(__dirname, '..', 'web_tool', 'public')
root.use('/static/*', serveStatic({ root: PUBLIC.replace(/\/public$/, '') , rewriteRequestPath: (p) => p }))
// همه‌چیزِ دیگر به اپِ اصلی سپرده می‌شود
root.route('/', app)

console.log('='.repeat(60))
console.log('  دستیارِ تصمیمِ معاملاتی — موتورِ کامل (Node سبک)')
console.log('='.repeat(60))
console.log(`  آدرس : http://${HOST}:${PORT}`)
console.log(`  public: ${PUBLIC}`)
console.log('  توقف: Ctrl+C')
console.log('='.repeat(60))

serve({ fetch: root.fetch, port: PORT, hostname: HOST })
