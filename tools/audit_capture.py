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

# ── سقفِ حافظه‌ایِ ضبط ───────────────────────────────────────────────────────
# سندباکس فقط ~۹۸۵MB رم دارد. لایه‌هایی مثلِ `S166` یک **جاروبِ پارامتری**
# هستند (۷۲ ترکیب × چند فراخوانی)؛ اگر همهٔ فراخوانی‌ها با ایندکس‌های کاملشان
# در حافظه بمانند، پروسه kill می‌شود (اندازه‌گیری‌شده: موتور روی S166 مرد).
#
# درمان: سقفِ تعدادِ فراخوانیِ **کاملاً** ضبط‌شده. فراخوانی‌های بعدی فقط
# «سرشمار» می‌شوند (متادیتای سبک، بدونِ ایندکس).
#
# ⚠️ چرا این ممیزی را خراب نمی‌کند: در جاروبِ پارامتری، نمایندهٔ لایه
# **بهترین** ترکیبِ گزارش‌شده در سند است، نه هر ۷۲ ترکیب. سقف روی ضبطِ
# کامل است نه روی مشاهده؛ شمارشِ کلِ فراخوانی‌ها حفظ می‌شود تا در حکم
# دیده شود که لایه چند ترکیب را جست‌وجو کرده (وردیِ `H5` چندگانگی).
MAX_FULL_CALLS = 40
MAX_SIG_IDX = 60000
MAX_GEOM_VALS = 20000


def pack_idx(a) -> dict:
    """
    فشرده‌سازیِ **بی‌اتلافِ** ایندکسِ سیگنال‌ها با کدگذاریِ اختلافی (delta).

    ⚠️ چرا لازم است (اندازه‌گیری‌شده، نه حدس): ذخیرهٔ خامِ ایندکس‌ها به‌صورت
    لیستِ پایتون در `s166_mtf_rescue` فایلی **۱۰۵MB** ساخت که (الف) سقفِ
    ۱۰۰MB گیت‌هاب را شکست و پوش رد شد، و (ب) هنگامِ `json.load` در مرحلهٔ
    داوری، رمِ ۹۸۵MB سندباکس را پر کرد و **دو بار** موتور را `Killed` کرد.

    ایده: سیگنال‌ها مرتب‌اند، پس `diff` آن‌ها اعدادِ کوچکی است که در JSON
    جای بسیار کمتری می‌گیرد. این **بی‌اتلاف** است: `unpack_idx` عیناً همان
    آرایه را برمی‌گرداند، پس هیچ سیگنالی گم نمی‌شود و حکمِ RQS2 دقیقاً همان
    حکمی است که با ایندکسِ خام صادر می‌شد.
    """
    a = np.asarray(a, np.int64).ravel()
    if a.size == 0:
        return {'enc': 'delta', 'first': None, 'd': [], 'n': 0}
    d = np.diff(a)
    return {'enc': 'delta', 'first': int(a[0]),
            'd': [int(x) for x in d], 'n': int(a.size)}


def unpack_idx(p) -> np.ndarray:
    """بازگشاییِ `pack_idx` — و پشتیبانی از فرمتِ خامِ قدیمی (لیستِ ساده)."""
    if p is None:
        return np.zeros(0, np.int64)
    if isinstance(p, list):                       # فرمتِ قدیمی
        return np.asarray(p, np.int64)
    if not isinstance(p, dict) or p.get('first') is None:
        return np.zeros(0, np.int64)
    d = np.asarray(p.get('d') or [], np.int64)
    out = np.empty(d.size + 1, np.int64)
    out[0] = p['first']
    if d.size:
        out[1:] = p['first'] + np.cumsum(d)
    return out


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
        self.n_calls_total = 0        # شمارشِ کل (حتی وقتی سقف رد شده)
        self.truncated = False

    def _budget_ok(self) -> bool:
        """آیا اجازهٔ ضبطِ کاملِ یک فراخوانیِ دیگر هست؟"""
        self.n_calls_total += 1
        if len(self.calls) < MAX_FULL_CALLS:
            return True
        self.truncated = True
        return False

    def __call__(self, orig, df, long_sig, short_sig, sl_pip, tp_pip, asset,
                 *args, **kw):
        # ۱) اجرای واقعی — هیچ رفتاری تغییر نمی‌کند
        res = orig(df, long_sig, short_sig, sl_pip, tp_pip, asset, *args, **kw)

        # ۱.۵) سقفِ حافظه — بعد از سقف فقط شمارش، بدونِ نگه‌داشتنِ ایندکس‌ها
        if not self._budget_ok():
            return res

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
                'long_idx': pack_idx(li[:MAX_SIG_IDX]),
                'short_idx': pack_idx(si[:MAX_SIG_IDX]),
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


    # ── آداپتورِ `run_backtest` (موتورِ دومِ آرشیو، ۸۶ اسکریپت) ──────────────
    def record_run_backtest(self, orig, df, entries, sl_points, tp_points,
                            direction, *args, **kw):
        """
        `run_backtest` یک‌سمته است (`direction`) و هندسه‌اش **دلاری** است نه pip.
        به شکلِ یکسان با `simulate_trades` ضبط می‌شود تا داورِ واحد بتواند
        هر دو را بخواند. تبدیلِ دلار→pip در مرحلهٔ داوری و با `pip_size`
        همان دارایی انجام می‌شود (اینجا خامش ذخیره می‌شود تا چیزی گم نشود).
        """
        res = orig(df, entries, sl_points, tp_points, direction, *args, **kw)
        if not self._budget_ok():
            return res
        try:
            ent = np.asarray(entries, bool)
            idx = np.flatnonzero(ent)
            close = np.asarray(df['close'], float)
            sl_ser = kw.get('sl_series')
            tp_ser = kw.get('tp_series')

            def geom_dollar(scalar, series):
                if series is not None:
                    arr = np.asarray(series, float)
                    vals = arr[idx] if len(idx) else np.array([])
                    fin = vals[np.isfinite(vals)]
                    return {'kind': 'series', 'unit': 'dollar',
                            'median': float(np.median(fin)) if fin.size else None,
                            'min': float(fin.min()) if fin.size else None,
                            'max': float(fin.max()) if fin.size else None,
                            'at_signals': [None if not np.isfinite(v) else round(float(v), 8)
                                           for v in vals[:20000]]}
                if scalar is None:
                    return {'kind': 'none', 'unit': 'dollar'}
                return {'kind': 'scalar', 'unit': 'dollar', 'value': float(scalar)}

            t0 = t1 = None
            for tcol in ('dt', 'time', 'Date', 'datetime'):
                if tcol in df.columns:
                    try:
                        t0 = str(df[tcol].iloc[0]); t1 = str(df[tcol].iloc[-1])
                    except Exception:
                        pass
                    break

            stats, trades = (res if isinstance(res, tuple) and len(res) == 2
                             else (res, None))
            ntr = int(len(trades)) if trades is not None else None

            self.calls.append({
                'engine': 'run_backtest',
                'asset': None,                     # run_backtest دارایی نمی‌گیرد
                'spread_dollar': kw.get('spread', args[0] if args else None),
                'direction': str(direction),
                'n_bars': int(len(df)),
                't_first': t0, 't_last': t1,
                'close_sum': float(np.nansum(close)),
                'close_first': float(close[0]), 'close_last': float(close[-1]),
                'long_idx': (pack_idx(idx[:MAX_SIG_IDX]) if direction == 'long'
                             else pack_idx([])),
                'short_idx': (pack_idx(idx[:MAX_SIG_IDX]) if direction == 'short'
                              else pack_idx([])),
                'n_long_sig': int(ent.sum()) if direction == 'long' else 0,
                'n_short_sig': int(ent.sum()) if direction == 'short' else 0,
                'sl': geom_dollar(sl_points, sl_ser),
                'tp': geom_dollar(tp_points, tp_ser),
                'max_hold': kw.get('max_hold'),
                'allow_overlap': kw.get('allow_overlap', False),
                'result_n_trades': ntr,
                'result_stats': ({k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                                  for k, v in stats.items()}
                                 if isinstance(stats, dict) else None),
            })
        except Exception:
            self.calls.append({'capture_error': traceback.format_exc()[-1500:]})
        return res


def capture_script(script: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    یک اسکریپتِ آرشیو را با وصلهٔ ضبط اجرا می‌کند.

    اجرا با `runpy` انجام می‌شود تا `__name__ == '__main__'` درست باشد و
    اسکریپت مثلِ اجرای معمولی رفتار کند.

    **هر دو** موتورِ آرشیو وصله می‌شوند (`simulate_trades` ۲۶۷ اسکریپت،
    `run_backtest` ۸۶ اسکریپت). چون اسکریپت‌ها موتور را با سبک‌های مختلف
    ایمپورت می‌کنند (`from engine.scalp_engine import ...` یا
    `sys.path`+`from backtest import ...`)، وصله هم روی ماژولِ اصلی و هم روی
    **همهٔ** ماژول‌هایی که ارجاعِ تابع را کپی کرده‌اند اعمال می‌شود.
    """
    rec = Recorder()
    restore = []          # (module, attr, original)

    # ── نکتهٔ حیاتی: هویتِ دوگانهٔ ماژول ─────────────────────────────────────
    # بخشی از اسکریپت‌های آرشیو `engine/` را خودشان به `sys.path` اضافه می‌کنند
    # و بعد `from backtest import run_backtest` می‌زنند. پایتون این را یک
    # ماژولِ **جدا** از `engine.backtest` می‌سازد (نامِ متفاوت ⇒ شیءِ متفاوت)،
    # پس وصلهٔ ما را نمی‌بیند و ضبط صفر می‌شود.
    #
    # درمان: `engine/` را **قبل** از نصبِ وصله در `sys.path` می‌گذاریم و
    # ماژول‌های تختِ (`backtest`, `scalp_engine`, ...) را خودمان ایمپورت
    # می‌کنیم تا در `sys.modules` کش شوند. آن‌وقت ایمپورتِ بعدیِ اسکریپت
    # همان شیءِ **وصله‌خوردهٔ** ما را می‌گیرد.
    eng_dir = str(ROOT / 'engine')
    if eng_dir not in sys.path:
        sys.path.insert(0, eng_dir)

    # ── `strategies/` هم باید در مسیر باشد ───────────────────────────────────
    # بخشی از لایه‌ها روی لایه‌های قبلی بنا شده‌اند و ماژولِ خواهر را با نامِ
    # **تخت** ایمپورت می‌کنند (`from s168_brooks_high2_low2 import ...`).
    # اندازه‌گیری‌شده: بدونِ این خط، `S170` و `S171` با
    # `ModuleNotFoundError` می‌مردند و ناعادلانه `INCOMPLETE` می‌گرفتند —
    # درحالی‌که هر دو کاملاً بازتولیدپذیرند و موتورِ مشترک را صدا می‌زنند
    # (`sim()` در `s171_..._filter.py` خودش `se.simulate_trades` است).
    str_dir = str(ROOT / 'strategies')
    if str_dir not in sys.path:
        sys.path.insert(0, str_dir)
    for _m in ('backtest', 'scalp_engine', 'dynamic_backtest',
               'capital_engine', 'trade_simulator'):
        try:
            __import__(_m)
        except Exception:
            pass

    def install(mod_names, fn_name, wrapper_factory):
        """تابع را در ماژولِ اصلی و همهٔ کپی‌های ایمپورت‌شده وصله می‌کند."""
        origs = set()
        for mn in mod_names:
            try:
                mod = __import__(mn, fromlist=['*'])
            except Exception:
                continue
            fn = getattr(mod, fn_name, None)
            if fn is None:
                continue
            origs.add(fn)
            wrapped = wrapper_factory(fn)
            setattr(mod, fn_name, wrapped)
            restore.append((mod, fn_name, fn))
        # کپی‌های موجود در ماژول‌های دیگر
        for name, mod in list(sys.modules.items()):
            if mod is None:
                continue
            try:
                cur = getattr(mod, fn_name, None)
                if cur is not None and cur in origs:
                    setattr(mod, fn_name, wrapper_factory(cur))
                    restore.append((mod, fn_name, cur))
            except Exception:
                pass
        return origs

    install(['engine.scalp_engine', 'scalp_engine'], 'simulate_trades',
            lambda orig: (lambda df, long_sig, short_sig, sl_pip, tp_pip, asset,
                          *a, **kw: rec(orig, df, long_sig, short_sig, sl_pip,
                                        tp_pip, asset, *a, **kw)))

    install(['engine.backtest', 'backtest'], 'run_backtest',
            lambda orig: (lambda df, entries, sl_points, tp_points, direction,
                          *a, **kw: rec.record_run_backtest(
                              orig, df, entries, sl_points, tp_points,
                              direction, *a, **kw)))

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
        # بازگرداندنِ همهٔ وصله‌ها (برعکسِ ترتیبِ نصب)
        for mod, attr, fn in reversed(restore):
            try:
                setattr(mod, attr, fn)
            except Exception:
                pass

    txt = buf.getvalue()
    out['stdout_tail'] = txt[-4000:]
    out['calls'] = rec.calls
    out['n_calls'] = len(rec.calls)
    # شمارشِ **کلِ** فراخوانی‌ها (حتی آن‌هایی که بخاطر سقفِ حافظه کامل ضبط
    # نشدند). این عدد شاهدِ مستقیمِ «چند ترکیب جست‌وجو شد» است و در داوریِ
    # `H5` (تصحیحِ چندگانگی) استفاده می‌شود.
    out['n_calls_total'] = rec.n_calls_total
    out['capture_truncated'] = bool(rec.truncated)
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
