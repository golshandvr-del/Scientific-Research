# -*- coding: utf-8 -*-
"""
هارنسِ **جهانیِ ضبطِ سیگنال** — راهِ مقیاس‌پذیرِ ماموریتِ ممیزی
================================================================================

## مسئله‌ای که این ابزار حل می‌کند

ماموریتِ ممیزی ۱۷۵ لایه دارد. دو راهِ قبلی هیچ‌کدام تمام نمی‌شوند:

  1. **ابزارِ دست‌سازِ هر لایه** (`audit_s69.py`, `audit_s70.py`): دقیق است ولی
     هر لایه ~۱ ساعت کارِ مهندسی می‌برد ⇒ ۱۷۵ ساعت. غیرممکن.
  2. **حدس‌زدنِ قاعده از متنِ سند**: سریع است ولی **علمی نیست** — سندها
     پارامترِ کامل را ننوشته‌اند (S71 در سند هیچ عددِ SL/TP ندارد، فقط در کد
     هست). حدس‌زدن ⇒ داوریِ یک لایهٔ *دیگر*، نه لایهٔ آرشیو.

## راهِ سوم (این ابزار)

۲۶۷ اسکریپت از ۶۲۸ اسکریپتِ آرشیو، همگی به **یک** تابعِ مشترک وصل‌اند:
`engine.scalp_engine.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip,
asset, max_hold, ...)`.

این تابع همان **گلوگاهِ اطلاعاتیِ کاملِ** یک لایه است: هر چیزی که برای داوریِ
RQS2 لازم است (سیگنالِ دقیق، هندسهٔ دقیق، افقِ دقیق، داراییِ دقیق) از همین‌جا
عبور می‌کند. پس:

    اسکریپتِ آرشیو را **بدونِ هیچ تغییر** اجرا می‌کنیم،
    ولی `simulate_trades` را قبلش وصله (monkey-patch) می‌کنیم تا
    هر فراخوانی را **ضبط** کند و بعد نتیجهٔ واقعی را برگرداند.

نتیجه: قاعدهٔ لایه **حدس زده نمی‌شود، اندازه‌گیری می‌شود**. اسکریپت خودش
سیگنال را می‌سازد؛ ما فقط گوش می‌ایستیم.

## چرا این «تقلب» نیست

  · وصله **شفاف** است: `orig(*a, **kw)` صدا زده می‌شود و نتیجهٔ اصلی
    برمی‌گردد. اسکریپت هیچ رفتارِ متفاوتی نمی‌بیند ⇒ اعدادِ چاپ‌شدهٔ اسکریپت
    باید مو‌به‌مو با سندِ آرشیو یکی باشد. این خودش **آزمونِ بازتولید** است.
  · هیچ سیگنالی توسطِ ممیز ساخته نمی‌شود.
  · داوری بعداً و **جدا** انجام می‌شود، با موتورِ رسمی روی همان سیگنالِ ضبط‌شده.

## محدودیتِ صادقانه

لایه‌هایی که موتورِ سرمایه‌محورِ خودشان را دارند (S69) یا `simulate_trades`
صدا نمی‌زنند، از این تور رد می‌شوند ⇒ برچسبِ `NO_CAPTURE` می‌گیرند و به
ابزارِ دست‌ساز یا حکمِ `INCOMPLETE` می‌روند. هیچ‌وقت ACCEPT نمی‌گیرند.
"""
from __future__ import annotations

import json
import os
import runpy
import sys
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / 'results' / '_audit_rename' / 'captures'
OUT.mkdir(parents=True, exist_ok=True)

# سقفِ زمانیِ هر اسکریپت (ثانیه) — لایه‌های ML سنگین‌اند
DEFAULT_TIMEOUT = 900


# ════════════════════════════════════════════════════════════════════════════
#  ضبط‌کننده
# ════════════════════════════════════════════════════════════════════════════
class Recorder:
    """
    هر فراخوانیِ `simulate_trades` را ضبط می‌کند.

    برای هر فراخوانی ذخیره می‌شود:
      · شاخصِ کندل‌هایِ سیگنال (نه آرایهٔ بولینِ کامل — حجم)
      · هندسه: sl_pip/tp_pip (اسکالر یا آرایه ⇒ ذخیرهٔ per-signal)
      · افق، دارایی، allow_overlap، be/trail
      · اثرِانگشتِ دادهٔ ورودی (طول + بازهٔ زمانی + هشِ close) تا بعداً
        بتوانیم **همان** کارت را بازسازی کنیم.
      · تعدادِ معامله و مجموعِ pip که اسکریپتِ اصلی گرفت ⇒ آزمونِ بازتولید
    """

    def __init__(self):
        self.calls = []

    def __call__(self, orig, df, long_sig, short_sig, sl_pip, tp_pip, asset,
                 *args, **kw):
        # ۱) اجرای واقعی — هیچ رفتاری تغییر نمی‌کند
        res = orig(df, long_sig, short_sig, sl_pip, tp_pip, asset, *args, **kw)

        # ۲) ضبط
        try:
            ls = np.asarray(long_sig, bool)
            ss = np.asarray(short_sig, bool)
            li = np.flatnonzero(ls)
            si = np.flatnonzero(ss)

            def geom(g, idx_all):
                """هندسه را به شکلِ قابلِ بازسازی درمی‌آورد."""
                if np.isscalar(g):
                    return {'kind': 'scalar', 'value': float(g)}
                arr = np.asarray(g, float)
                if arr.ndim == 0:
                    return {'kind': 'scalar', 'value': float(arr)}
                # فقط مقادیرِ روی کندل‌های سیگنال مهم‌اند
                vals = arr[idx_all] if len(idx_all) else np.array([])
                fin = vals[np.isfinite(vals)]
                return {
                    'kind': 'series',
                    'n': int(arr.size),
                    'median': float(np.median(fin)) if fin.size else None,
                    'mean': float(fin.mean()) if fin.size else None,
                    'min': float(fin.min()) if fin.size else None,
                    'max': float(fin.max()) if fin.size else None,
                    'at_signals': [None if not np.isfinite(v) else round(float(v), 6)
                                   for v in vals[:20000]],
                }

            idx_all = np.union1d(li, si).astype(int)

            close = np.asarray(df['close'], float)
            t0 = t1 = None
            for tcol in ('dt', 'time', 'Date', 'datetime'):
                if tcol in df.columns:
                    try:
                        t0 = str(df[tcol].iloc[0])
                        t1 = str(df[tcol].iloc[-1])
                    except Exception:
                        pass
                    break

            mh = kw.get('max_hold', args[0] if args else 16)
            ao = kw.get('allow_overlap', args[1] if len(args) > 1 else False)

            npip = None
            ntr = 0
            if res is not None and len(res) > 0:
                ntr = int(len(res))
                if 'pnl_pip' in res:
                    npip = float(np.asarray(res['pnl_pip'], float).sum())

            self.calls.append({
                'asset': str(asset),
                'n_bars': int(len(df)),
                't_first': t0, 't_last': t1,
                'close_sum': float(np.nansum(close)),      # اثرِانگشتِ داده
                'close_first': float(close[0]),
                'close_last': float(close[-1]),
                'long_idx': [int(x) for x in li[:60000]],
                'short_idx': [int(x) for x in si[:60000]],
                'n_long_sig': int(ls.sum()),
                'n_short_sig': int(ss.sum()),
                'sl': geom(sl_pip, idx_all),
                'tp': geom(tp_pip, idx_all),
                'max_hold': (None if mh is None else
                             (int(mh) if np.isscalar(mh) else 'series')),
                'allow_overlap': bool(ao),
                'be_trigger_pip': kw.get('be_trigger_pip'),
                'trail_pip': kw.get('trail_pip'),
                # نتیجهٔ اسکریپتِ اصلی ⇒ آزمونِ بازتولید
                'result_n_trades': ntr,
                'result_sum_pip': npip,
            })
        except Exception:
            self.calls.append({'capture_error': traceback.format_exc()[-1500:]})

        return res


def capture_script(script: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    یک اسکریپتِ آرشیو را با وصلهٔ ضبط اجرا می‌کند.

    اجرا با `runpy` انجام می‌شود تا `__name__ == '__main__'` درست باشد و
    اسکریپت مثلِ اجرای معمولی رفتار کند.
    """
    import engine.scalp_engine as se

    rec = Recorder()
    orig = se.simulate_trades

    def patched(df, long_sig, short_sig, sl_pip, tp_pip, asset, *a, **kw):
        return rec(orig, df, long_sig, short_sig, sl_pip, tp_pip, asset, *a, **kw)

    # وصله در هر جایی که ماژول را ایمپورت کرده باشد
    se.simulate_trades = patched
    patched_mods = []
    for name, mod in list(sys.modules.items()):
        if mod is None or name.startswith('engine.'):
            continue
        try:
            if getattr(mod, 'simulate_trades', None) is orig:
                setattr(mod, 'simulate_trades', patched)
                patched_mods.append(name)
        except Exception:
            pass

    path = ROOT / 'strategies' / script
    out = {'script': script, 'ok': False, 'calls': [], 'stdout_tail': '',
           'error': None, 'seconds': None}

    import io
    from contextlib import redirect_stdout, redirect_stderr
    buf = io.StringIO()
    t0 = time.time()
    old_argv = list(sys.argv)
    old_cwd = os.getcwd()
    try:
        sys.argv = [str(path)]
        os.chdir(ROOT)
        with redirect_stdout(buf), redirect_stderr(buf):
            runpy.run_path(str(path), run_name='__main__')
        out['ok'] = True
    except SystemExit:
        out['ok'] = True
    except BaseException as e:
        out['error'] = f'{type(e).__name__}: {e}'
        out['traceback'] = traceback.format_exc()[-2500:]
    finally:
        out['seconds'] = round(time.time() - t0, 1)
        sys.argv = old_argv
        try:
            os.chdir(old_cwd)
        except Exception:
            pass
        se.simulate_trades = orig
        for name in patched_mods:
            try:
                setattr(sys.modules[name], 'simulate_trades', orig)
            except Exception:
                pass

    txt = buf.getvalue()
    out['stdout_tail'] = txt[-4000:]
    out['calls'] = rec.calls
    out['n_calls'] = len(rec.calls)
    return out


def main():
    if len(sys.argv) < 2:
        print('usage: audit_capture.py <script.py> [more.py ...]')
        return 2
    for script in sys.argv[1:]:
        print(f'── capturing {script} ...', flush=True)
        r = capture_script(script)
        dest = OUT / (script.replace('/', '_') + '.capture.json')
        with open(dest, 'w', encoding='utf-8') as fh:
            json.dump(r, fh, ensure_ascii=False, default=float)
        status = 'OK' if r['ok'] else 'ERR'
        print(f'   {status} calls={r["n_calls"]} {r["seconds"]}s '
              f'{r.get("error") or ""}')
        print(f'   -> {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
