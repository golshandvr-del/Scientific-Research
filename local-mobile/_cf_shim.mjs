// Shim: جایگزینِ 'hono/cloudflare-workers' برای اجرا روی Node.
// فقط serveStatic لازم است؛ نسخهٔ Node را از @hono/node-server می‌دهیم و
// ریشه را به پوشهٔ public سایت اشاره می‌دهیم.
import { serveStatic as nodeServeStatic } from '@hono/node-server/serve-static'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
// public سایت در web_tool/public است (نسبت به این پوشه: ../web_tool/public)
const PUBLIC_ROOT = join(__dirname, '..', 'web_tool')

export function serveStatic(opts = {}) {
  // اپ با { root: './public' } صدا می‌زند؛ ما root واقعی را به web_tool می‌دهیم
  // تا './public' نسبت به آن درست حل شود.
  return nodeServeStatic({
    root: PUBLIC_ROOT,
    rewriteRequestPath: opts.rewriteRequestPath,
  })
}
