#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سرورِ لوکالِ فوق‌سبک برای اجرای «دستیارِ تصمیمِ معاملاتی» روی اندروید (Termux) یا هر لینوکس.

فلسفهٔ طراحی (پاسخ به User Note دربارهٔ سنگین‌شدنِ سایتِ کلادفلر):
  - هیچ Node / Vite / Wrangler / Workerd لازم نیست  ⇒ مصرفِ رم ~۲۰–۴۰MB به‌جای ۲GB.
  - فقط کتابخانهٔ استانداردِ پایتون (http.server + urllib). صفر pip install سنگین.
  - موتورِ تصمیم همان JS خالصِ اثبات‌شدهٔ پروژه (apk/www/engine.js) است که در مرورگرِ
    گوشی اجرا می‌شود؛ سرور فقط «فایل می‌دهد» و «پروکسیِ Yahoo» است تا CORS مانع نشود.

اجرا در Termux:
    pkg install python
    python server.py
سپس در مرورگرِ گوشی: http://localhost:8080

پارامترها (اختیاری، از طریقِ متغیرِ محیطی):
    PORT   پیش‌فرض 8080
    HOST   پیش‌فرض 127.0.0.1  (برای دسترسی از دستگاه‌های دیگرِ شبکه: 0.0.0.0)
"""

import json
import os
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# مسیرِ فایل‌های اپ. به‌صورتِ پیش‌فرض از پوشهٔ apk/www پروژه سرو می‌شود (اپِ
# خودکفای موجود). اگر کاربر پوشهٔ webroot محلی داشته باشد، آن اولویت دارد.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATE_ROOTS = [
    os.path.join(HERE, "webroot"),            # نسخهٔ اختصاصیِ موبایل (اگر ساخته شود)
    os.path.abspath(os.path.join(HERE, "..", "apk", "www")),  # اپِ خودکفای موجود
]
WEBROOT = next((p for p in CANDIDATE_ROOTS if os.path.isdir(p)), CANDIDATE_ROOTS[-1])

PORT = int(os.environ.get("PORT", "8080"))
HOST = os.environ.get("HOST", "127.0.0.1")

# نگاشتِ داراییِ اپ ⇒ نمادِ Yahoo (هماهنگ با apk/www/app.js)
YAHOO_SYMBOL = {
    "XAUUSD": "GC=F",
    "EURUSD": "EURUSD=X",
}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".map": "application/json",
}


def yahoo_fetch(symbol: str, interval: str, rng: str) -> dict:
    """دریافتِ کندل از Yahoo با User-Agent مرورگری (سرور CORS ندارد)."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval={interval}&range={rng}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0 Safari/537.36",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    # لاگِ کم‌حجم (روی موبایل مزاحمِ کارایی نباشد)
    def log_message(self, fmt, *args):
        sys.stderr.write("[srv] " + (fmt % args) + "\n")

    def _send(self, code, body: bytes, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ---- API: پروکسیِ خامِ Yahoo  /api/proxy?url=<yahoo-url> ----
        # اپ (apk/www/app.js تابعِ fetchYahoo) این را در اولویت می‌گذارد و فرمتِ
        # خامِ Yahoo (chart.result[0]) را انتظار دارد. این مسیر مشکلِ CORS را روی
        # موبایل کاملاً حل می‌کند (سرورِ لوکال CORS ندارد) — برای هر دو ارز.
        if path == "/api/proxy":
            qs = parse_qs(parsed.query)
            target = qs.get("url", [""])[0]
            if not target.startswith("https://query1.finance.yahoo.com") and \
               not target.startswith("https://query2.finance.yahoo.com"):
                self._send(403, json.dumps({"error": "only yahoo urls allowed"}).encode("utf-8"), MIME[".json"])
                return
            try:
                req = urllib.request.Request(target, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read()
                self._send(200, raw, MIME[".json"])
            except Exception as e:
                self._send(502, json.dumps({"error": str(e)}).encode("utf-8"), MIME[".json"])
            return

        # ---- API: کندلِ آمادهٔ XAUUSD  /api/candles?interval=15m&range=2mo ----
        # اپ این را فقط برای XAUUSD و در مسیرِ اول صدا می‌زند و فرمتِ
        # {ok:true, candles:[...]} را انتظار دارد (app.js خط ۲۱۳).
        if path == "/api/candles":
            qs = parse_qs(parsed.query)
            asset = (qs.get("asset", ["XAUUSD"])[0]).upper()
            interval = qs.get("interval", ["15m"])[0]
            rng = qs.get("range", ["60d"])[0]
            # Yahoo برای interval=15m مقدارِ «2mo» را نمی‌پذیرد (خطای 422)؛ به
            # «60d» که معتبر است نگاشت می‌شود تا مسیرِ اول هم پایدار بماند.
            RANGE_FIX = {"2mo": "60d", "1mo": "30d", "3mo": "90d"}
            rng = RANGE_FIX.get(rng, rng)
            symbol = YAHOO_SYMBOL.get(asset, asset)
            try:
                data = yahoo_fetch(symbol, interval, rng)
                r = (data.get("chart", {}).get("result") or [None])[0]
                if not r:
                    raise ValueError("no result")
                ts = r.get("timestamp") or []
                q = (r.get("indicators", {}).get("quote") or [{}])[0]
                o, h, l, c = q.get("open"), q.get("high"), q.get("low"), q.get("close")
                vol = q.get("volume") or []
                candles = []
                for i in range(len(ts)):
                    if not (o and h and l and c):
                        break
                    if o[i] is None or h[i] is None or l[i] is None or c[i] is None:
                        continue
                    candles.append({
                        "time": ts[i],
                        "open": o[i], "high": h[i], "low": l[i], "close": c[i],
                        "volume": (vol[i] if i < len(vol) and vol[i] else 0),
                    })
                out = {"ok": True, "candles": candles, "source": "yahoo", "symbol": symbol}
                self._send(200, json.dumps(out).encode("utf-8"), MIME[".json"])
            except Exception as e:
                self._send(502, json.dumps({"ok": False, "error": str(e)}).encode("utf-8"), MIME[".json"])
            return

        # ---- API: سلامت ----
        if path == "/api/health":
            self._send(200, json.dumps({"ok": True, "webroot": WEBROOT}).encode("utf-8"), MIME[".json"])
            return

        # ---- فایلِ استاتیک ----
        if path == "/" or path == "":
            path = "/index.html"
        # جلوگیری از path traversal
        rel = os.path.normpath(path).lstrip("/\\")
        full = os.path.join(WEBROOT, rel)
        if not os.path.abspath(full).startswith(os.path.abspath(WEBROOT)):
            self._send(403, b"forbidden")
            return
        if not os.path.isfile(full):
            self._send(404, b"not found")
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        try:
            with open(full, "rb") as f:
                self._send(200, f.read(), ctype)
        except Exception as e:
            self._send(500, str(e).encode("utf-8"))


def main():
    if not os.path.isdir(WEBROOT):
        sys.stderr.write(f"[FATAL] webroot یافت نشد: {WEBROOT}\n")
        sys.exit(1)
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 60)
    print("  دستیارِ تصمیمِ معاملاتی — سرورِ لوکالِ سبک")
    print("=" * 60)
    print(f"  webroot : {WEBROOT}")
    print(f"  آدرس    : http://{HOST}:{PORT}")
    if HOST in ("127.0.0.1", "localhost"):
        print(f"  (در مرورگرِ همین گوشی باز کنید: http://localhost:{PORT})")
    else:
        print(f"  (از دستگاه‌های دیگرِ همین شبکه هم قابل‌دسترس است)")
    print("  توقف: Ctrl+C")
    print("=" * 60)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nمتوقف شد.")
        srv.shutdown()


if __name__ == "__main__":
    main()
