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
import re
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
class _SkipParking(Exception):
    """سیگنالِ درونی: از بلوکِ کنارگذاریِ کشِ resume صرف‌نظر شود."""


MAX_FULL_CALLS = 40
# سقفِ سختِ «چند فراخوانی **بررسی** شود» (نه چند تا نگه داشته شود). بعد از این
# عدد، ساختنِ رکورد متوقف می‌شود تا هزینهٔ CPU در جاروب‌های چند-ده-هزارتایی
# منفجر نشود؛ `n_calls_total` همچنان کاملاً شمرده می‌شود.
MAX_SCANNED_CALLS = 4000
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
        """
        آیا اجازهٔ ساختنِ رکوردِ کاملِ یک فراخوانیِ دیگر هست؟

        بعد از پرشدنِ سقف هم `True` برمی‌گردد، ولی رکورد از طریقِ `_add`
        فقط در صورتی **نگه** می‌شود که از ضعیف‌ترینِ موجود بهتر باشد. سقفِ
        حافظه شکسته نمی‌شود (طولِ `self.calls` هرگز از `MAX_FULL_CALLS`
        بیشتر نمی‌شود)، ولی محتوایش به‌سمتِ پیکربندی‌های برنده می‌رود.

        برای اجرای‌های **بسیار** بزرگ یک سقفِ سختِ اضافی هم داریم تا هزینهٔ
        CPUِ ساختنِ رکورد از کنترل خارج نشود.
        """
        self.n_calls_total += 1
        if len(self.calls) < MAX_FULL_CALLS:
            return True
        self.truncated = True
        return self.n_calls_total <= MAX_SCANNED_CALLS

    def _keep_best(self, rec_new: dict) -> None:
        """
        جایگزینیِ **هوشمند** وقتی سقفِ حافظه پر شده.

        ⚠️ چرا لازم شد (اندازه‌گیری‌شده): `s222_all_timedrift_wr60.py`
        در یک اجرا `۳۰٬۸۴۰` فراخوانی زد — این یک **جاروبِ بهینه‌سازی**
        است (`SL_GRID × TP_GRID × FILTER_POOL`)، نه یک لایهٔ واحد. با
        نگه‌داشتنِ «۴۰ فراخوانیِ **اول**»، آنچه داوری می‌شد فقط
        نخستین ترکیب‌های شبکه بود — یعنی پیکربندی‌هایی که خودِ لایه
        هرگز ادعا نکرده. حکم عملاً روی لایهٔ اشتباهی صادر می‌شد.

        درمان: بعد از پرشدنِ سقف، اگر فراخوانیِ تازه از **ضعیف‌ترین**
        ضبطِ موجود بهتر باشد، جایش را می‌گیرد. معیارِ «بهتر» مجموعِ
        pip است — همان چیزی که خودِ جاروب برایش بهینه می‌کند. پس در
        پایان، ضبط شاملِ **پیکربندیِ برندهٔ جاروب** است، نه چند
        ترکیبِ تصادفیِ ابتدای شبکه.

        این کار **رفتارِ اسکریپت را تغییر نمی‌دهد** — فقط انتخاب
        می‌کند کدام فراخوانی‌ها در فایلِ ضبط بمانند.
        """
        try:
            key_new = rec_new.get('result_sum_pip')
            if key_new is None:
                return
            worst_i, worst_v = None, None
            for i, c in enumerate(self.calls):
                v = c.get('result_sum_pip')
                if v is None:
                    worst_i, worst_v = i, None
                    break
                if worst_v is None or v < worst_v:
                    worst_i, worst_v = i, v
            if worst_i is None:
                return
            if worst_v is None or float(key_new) > float(worst_v):
                self.calls[worst_i] = rec_new
        except Exception:
            pass

    def _add(self, rec_new: dict) -> None:
        """ثبتِ رکورد: افزودن اگر سقف پر نشده، وگرنه جایگزینیِ بهترین."""
        if len(self.calls) < MAX_FULL_CALLS:
            self.calls.append(rec_new)
        else:
            self._keep_best(rec_new)

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

            self._add({
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
            if len(self.calls) < MAX_FULL_CALLS:
                self.calls.append({'capture_error':
                                   traceback.format_exc()[-1500:]})

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

            self._add({
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
            if len(self.calls) < MAX_FULL_CALLS:
                self.calls.append({'capture_error':
                                   traceback.format_exc()[-1500:]})
        return res

    # ── آداپتورِ `trade_simulator.simulate` (موتورِ سومِ آرشیو، ۳۷ اسکریپت) ──
    def record_simulate(self, orig, df, strategy, asset, *args, **kw):
        """
        موتورِ سومِ آرشیو: `engine.trade_simulator.simulate`.

        ⚠️ چرا لازم شد (اندازه‌گیری‌شده): `S310`–`S313` پشتِ‌سرهم `INCOMPLETE`
        گرفتند. شمارشِ سورس گفت «صفر فراخوانیِ موتور»، ولی این **دروغِ
        ابزار** بود: این اسکریپت‌ها `from engine import trade_simulator as TS`
        می‌کنند و `TS.simulate(...)` صدا می‌زنند — موتوری که شنودگرِ ما
        **اصلاً وصله نمی‌زد**. `۳۷` اسکریپتِ آرشیو از آن استفاده می‌کنند،
        یعنی ۳۷ لایه محکوم بودند به حکمِ ناعادلانهٔ «قابل اثبات نیست».

        تفاوتِ بنیادیِ این موتور: سیگنال **پیشاپیش** به‌صورت آرایه داده
        نمی‌شود؛ `strategy` شیئی با متدِ `advise(ctx)` است و سیگنال‌ها
        **جریانی** تولید می‌شوند. پس ایندکسِ سیگنال را نمی‌توان از ورودی
        خواند — ولی می‌توان از **خروجی** بازسازی کرد: هر رکوردِ معامله
        `entry_bar` و `side` دارد، و هندسه‌اش `sl_pip`/`tp_pip` است.

        این بازسازی **محافظه‌کارانه** است: فقط سیگنال‌هایی دیده می‌شوند که
        به معاملهٔ واقعی تبدیل شدند (سیگنالِ نادیده‌گرفته‌شده در زمانِ
        پوزیشنِ باز ثبت نمی‌شود). این با نگاهِ داور سازگار است، چون داور هم
        دربارهٔ معاملاتِ **انجام‌شده** حکم می‌دهد.
        """
        res = orig(df, strategy, asset, *args, **kw)
        if not self._budget_ok():
            return res
        try:
            trades = res[0] if isinstance(res, tuple) else res
            close = np.asarray(df['close'], float)
            li: list = []
            si: list = []
            sl_vals: list = []
            tp_vals: list = []
            npip = None
            ntr = 0
            if trades is not None and len(trades) > 0:
                ntr = int(len(trades))
                sides = np.asarray(trades['side']).astype(str)
                ebar = np.asarray(trades['entry_bar'], int)
                for s, b in zip(sides, ebar):
                    (li if s.upper().startswith('L') else si).append(int(b))
                if 'sl_pip' in trades:
                    sl_vals = [float(x) for x in
                               np.asarray(trades['sl_pip'], float)]
                if 'tp_pip' in trades:
                    tp_vals = [float(x) for x in
                               np.asarray(trades['tp_pip'], float)]
                if 'pnl_pip' in trades:
                    npip = float(np.asarray(trades['pnl_pip'], float).sum())

            def geom_list(vals):
                """هندسه به همان شکلِ آداپتورهای دیگر (pip)."""
                if not vals:
                    return {'kind': 'scalar', 'value': None}
                arr = np.asarray(vals, float)
                if float(arr.max() - arr.min()) < 1e-9:
                    return {'kind': 'scalar', 'value': float(arr[0])}
                return {'kind': 'series',
                        'median': float(np.nanmedian(arr)),
                        'min': float(np.nanmin(arr)),
                        'max': float(np.nanmax(arr)),
                        'values': [float(x) for x in arr[:MAX_GEOM_VALS]]}

            t = df['time'] if 'time' in df.columns else None
            self._add({
                'engine': 'trade_simulator.simulate',
                'asset': str(asset),
                'n_bars': int(len(df)),
                't_first': (str(t.iloc[0]) if t is not None else None),
                't_last': (str(t.iloc[-1]) if t is not None else None),
                'close_sum': float(np.nansum(close)),
                'close_first': float(close[0]),
                'close_last': float(close[-1]),
                'long_idx': pack_idx(np.asarray(sorted(li)[:MAX_SIG_IDX])),
                'short_idx': pack_idx(np.asarray(sorted(si)[:MAX_SIG_IDX])),
                'n_long_sig': len(li),
                'n_short_sig': len(si),
                'sl': geom_list(sl_vals),
                'tp': geom_list(tp_vals),
                'max_hold': kw.get('max_bars_hold'),
                'allow_overlap': bool(kw.get('allow_pyramiding', False)),
                'be_trigger_pip': None,
                'trail_pip': None,
                'result_n_trades': ntr,
                'result_sum_pip': npip,
            })
        except Exception:
            if len(self.calls) < MAX_FULL_CALLS:
                self.calls.append({'capture_error':
                                   traceback.format_exc()[-1500:]})
        return res

    # ── آداپتورِ `rqs2.compute_rqs2` (خانوادهٔ «خودداور»، موتورِ چهارم) ──────
    def record_compute_rqs2(self, orig, trades, asset, *args, **kw):
        """
        خانوادهٔ «خودداورِ» آرشیو: اسکریپت‌هایی که **هیچ موتورِ شبیه‌سازیِ
        آرشیو را صدا نمی‌زنند** و در عوض خودشان معاملات را می‌سازند و
        مستقیماً `engine.rqs2.compute_rqs2(...)` — یعنی داورِ **رسمیِ**
        پروژه — را فرا می‌خوانند.

        ⚠️ چرا لازم شد (اندازه‌گیری‌شده): `S346`,`S348`,`S350` پشتِ‌سرهم
        `INCOMPLETE (not reproducible)` گرفتند، **در حالی که ضبط موفق بود**
        (`ok=True`, `seconds=37.3` و `45.3`) ولی `n_calls=0`. علت باگِ
        شنودگر نبود: خروجیِ خودِ اسکریپت نشان می‌دهد که حکم را **خودش**
        صادر کرده است، با فرمتِ کاملِ یازده‌دروازه‌ای:

            EURUSD-W1 CONS | REJECT RQS2= 5.4 | n=84 WR=47.62% PF=1.07
                           | H0:✓ H1:✗ H2:✗ H3:? ... H10:✗

        یعنی این لایه‌ها **به‌هیچ‌وجه غیرقابل‌اثبات نبودند**؛ فقط مسیرشان
        به داور از جایی می‌گذشت که شنودگر تماشا نمی‌کرد.

        چرا این آداپتور از «تجزیهٔ متنِ stdout» بهتر است: ورودیِ
        `compute_rqs2` **همان `DataFrame`ِ معاملات** است که سه آداپتورِ قبلی
        ضبط می‌کنند (ستون‌های `pnl_pip, outcome, sl_pip, entry_bar,
        exit_bar, direction`). پس هیچ عددی از متن حدس زده نمی‌شود — همان
        دادهٔ ساختاریِ اصل ضبط می‌شود و داورِ مستقلِ ما می‌تواند مثلِ بقیهٔ
        لایه‌ها رویش کار کند. `dtype`ها هم دقیقاً همان‌اند، پس هیچ مسیرِ
        داوریِ جداگانه‌ای لازم نیست.
        """
        res = orig(trades, asset, *args, **kw)
        try:
            import numpy as np
            n = int(len(trades)) if trades is not None else 0
            if n == 0:
                return res

            def col(name):
                try:
                    return np.asarray(trades[name])
                except Exception:
                    return None

            eb, dirn = col('entry_bar'), col('direction')
            li, si = [], []
            if eb is not None and dirn is not None:
                for i in range(n):
                    d = str(dirn[i]).lower()
                    (li if d.startswith('l') else si).append(int(eb[i]))

            # هندسه: `compute_rqs2` آن را به‌صورتِ آرگومانِ کلیدواژه‌ای
            # می‌گیرد (`sl_pip`/`tp_pip`) و همان چیزی است که `H2`/`H9` را
            # زنده می‌کند — پس دقیقاً همان مقدار ضبط می‌شود، بی‌حدس.
            def geom(v, fallback_col=None):
                if v is None and fallback_col is not None:
                    a = col(fallback_col)
                    v = (float(np.nanmedian(a)) if a is not None
                         and len(a) else None)
                if v is None:
                    return None
                a = np.atleast_1d(np.asarray(v, dtype=float))
                if len(a) == 1 or float(a.max() - a.min()) < 1e-9:
                    return {'kind': 'scalar', 'value': float(a.flat[0])}
                return {'kind': 'series',
                        'median': float(np.nanmedian(a)),
                        'min': float(np.nanmin(a)), 'max': float(np.nanmax(a)),
                        'values': [float(x) for x in a[:MAX_GEOM_VALS]]}

            pnl = col('pnl_pip')
            self._add({
                'engine': 'rqs2.compute_rqs2',
                'asset': str(asset),
                'n_bars': None,          # این مسیر دادهٔ کندل را عبور نمی‌دهد
                't_first': None, 't_last': None,
                'long_idx': pack_idx(np.asarray(sorted(li)[:MAX_SIG_IDX])),
                'short_idx': pack_idx(np.asarray(sorted(si)[:MAX_SIG_IDX])),
                'n_long_sig': len(li), 'n_short_sig': len(si),
                'sl': geom(kw.get('sl_pip'), 'sl_pip'),
                'tp': geom(kw.get('tp_pip')),
                'n_trials_declared': kw.get('n_trials'),
                'allow_overlap': bool(kw.get('allow_overlap', False)),
                'be_trigger_pip': None, 'trail_pip': None,
                'result_n_trades': n,
                'result_sum_pip': (float(np.nansum(pnl))
                                   if pnl is not None else None),
            })
        except Exception:
            if len(self.calls) < MAX_FULL_CALLS:
                self.calls.append({'capture_error':
                                   traceback.format_exc()[-1500:]})
        return res


def capture_script(script: str, timeout: int = DEFAULT_TIMEOUT,
                   _force_park: bool = False) -> dict:
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

    # موتورِ سوم — `۳۷` اسکریپتِ آرشیو از این استفاده می‌کنند و تا امروز
    # وصله نمی‌شد، پس همه‌شان محکوم به `INCOMPLETE`ِ ناعادلانه بودند.
    install(['engine.trade_simulator', 'trade_simulator'], 'simulate',
            lambda orig: (lambda df, strategy, asset, *a, **kw:
                          rec.record_simulate(orig, df, strategy, asset,
                                              *a, **kw)))

    # ⚠️ موتورِ چهارم — خانوادهٔ «خودداورِ» آرشیو (اندازه‌گیری‌شده):
    #   `record_compute_rqs2` در کامیتِ `3a1a7a6` نوشته و کامیت شد، ولی
    #   سیم‌کشیِ نهایی‌اش انجام نشد — یعنی تابع وجود داشت و **هرگز فعال
    #   نمی‌شد**. مدرک: فهرستِ `install(...)` فقط سه ورودی داشت، پس
    #   `S346/S348/S350` باز هم `n_calls=0` می‌گرفتند در حالی که ضبطشان
    #   موفق بود (`ok=True`, `37.3s`/`45.3s`) و خودشان یک ردیفِ حکمِ کاملِ
    #   یازده‌دروازه‌ای چاپ می‌کردند. این خانواده هیچ موتورِ شبیه‌سازیِ
    #   آرشیو را صدا نمی‌زند: معاملات را خودش می‌سازد و مستقیماً داورِ
    #   **رسمیِ** پروژه را فرا می‌خواند.
    install(['engine.rqs2', 'rqs2'], 'compute_rqs2',
            lambda orig: (lambda trades, asset, *a, **kw:
                          rec.record_compute_rqs2(orig, trades, asset,
                                                  *a, **kw)))

    path = ROOT / 'strategies' / script
    out = {'script': script, 'ok': False, 'calls': [], 'stdout_tail': '',
           'error': None, 'seconds': None}

    import io
    from contextlib import redirect_stdout, redirect_stderr
    buf = io.StringIO()
    t0 = time.time()
    old_argv = list(sys.argv)
    old_cwd = os.getcwd()

    # ── کشِ resume باید موقتاً کنار برود ────────────────────────────────────
    # ⚠️ چرا لازم شد (اندازه‌گیری‌شده): `s224_s81_swing_wr60.py` در **۰.۰
    #   ثانیه** و **بدون خطا** تمام شد و `n_calls=۰` ضبط کرد. علت باگِ ما
    #   نبود: خودِ اسکریپت قابلیتِ resume دارد —
    #       if os.path.exists(out):  ...  print('⏩ رد شد (قبلاً)')
    #   یعنی نتیجهٔ اجرای قبلی را از `results/_<sid>*.json` می‌خواند و
    #   محاسبه را **کاملاً** رد می‌کند. پس هیچ فراخوانیِ شبیه‌سازی رخ
    #   نمی‌دهد، شنودگر چیزی نمی‌بیند، و لایه ناعادلانه `INCOMPLETE`
    #   می‌گیرد در حالی که کدش کاملاً بازتولیدپذیر است.
    #
    #   درمان: کشِ **مربوط به همین اسکریپت** موقتاً به نامِ دیگری منتقل
    #   می‌شود تا اسکریپت مجبور به محاسبهٔ واقعی شود، و در `finally`
    #   بی‌قید‌و‌شرط برمی‌گردد. پس آرشیو دست‌نخورده می‌ماند حتی اگر اجرا
    #   با خطا یا تایم‌اوت بمیرد.
    stem = path.stem                      # s224_s81_swing_wr60
    parked: list[tuple[Path, Path]] = []

    # ── ترمیمِ جاماندهٔ اجرای کشته‌شده ───────────────────────────────────────
    # ⚠️ چرا لازم شد (اندازه‌گیری‌شده): بازگردانیِ `finally` وقتی پروسه با
    #   `SIGKILL` (تایم‌اوتِ سختِ موتور، یا `pkill -9`) می‌میرد **اجرا
    #   نمی‌شود**. نتیجهٔ واقعی: بعد از کشتنِ ضبطِ `s223`، فایلِ
    #   `results/_s223_structural_wr60.json` در حالتِ `.audit-parked` ماند و
    #   `git status` آن را «حذف‌شده» نشان داد — یعنی ابزارِ ممیزی آرشیو را
    #   دستکاری کرده بود، که مطلقاً غیرقابل‌قبول است.
    #   درمان: در **شروعِ** هر اجرا، هر جاماندهٔ `.audit-parked` بی‌قید‌و‌شرط
    #   به جای اصلش برمی‌گردد. پس حتی مرگِ ناگهانی هم آرشیو را آلوده
    #   نمی‌گذارد؛ ترمیم در اجرای بعدی قطعی است.
    try:
        for leftover in (ROOT / 'results').glob('*.audit-parked'):
            target = leftover.with_suffix('')          # حذفِ .audit-parked
            try:
                if target.exists():
                    target.unlink()
                leftover.rename(target)
                print(f'   (repaired leftover parked cache: {target.name})',
                      flush=True)
            except Exception:
                pass
    except Exception:
        pass

    # ── حالتِ «ادامه بده» برای جاروب‌های بسیار بزرگ ─────────────────────────
    # ⚠️ چرا لازم شد (اندازه‌گیری‌شده): `s223_structural_wr60.py` یک جاروبِ
    #   `۵ SL × ۶ TP × ترکیب‌های تا ۳ فیلتر × ۳ لایه × چند تایم‌فریم` است و
    #   حتی در بودجهٔ ۹۰۰ ثانیه تمام نمی‌شود (`S223a` دو بار `DEFERRED` شد).
    #   ولی خودِ اسکریپت **ذخیرهٔ افزایشی** دارد و کامنتش صریح است:
    #       save()  # ذخیرهٔ افزایشی: مقاوم در برابر ریستِ سندباکس
    #   یعنی بعد از هر لایه چک‌پوینت می‌زند. اگر کش را **نگه** داریم، هر
    #   اجرا یک لایهٔ ناتمام را تکمیل می‌کند و ضبط تدریجاً کامل می‌شود.
    #   بدونِ این حالت، کنارگذاشتنِ کش هر بار همه‌چیز را از صفر شروع می‌کند
    #   و لایه برای همیشه `DEFERRED` می‌ماند — یعنی نقصِ ابزار به‌جای حکم.
    #   AUDIT_KEEP_CACHE=1 python tools/audit_capture.py s223_structural_wr60.py
    #
    # ⚠️ تعارضِ کشف‌شده (اندازه‌گیری‌شده) — و چرا حالا **هوشمند** است:
    #   دو وصلهٔ ما با هم می‌جنگیدند. `AUDIT_KEEP_CACHE=1` برای جاروبِ
    #   **ناتمام** حیاتی است (تا ادامه دهد)، ولی برای کشِ **کامل** فاجعه
    #   است. مدرک: `_s224_s81_swing_wr60.json` هر ۴ تایم‌فریم را کامل دارد
    #   (`M5,M15,M30,H1`)، پس اسکریپت همه‌چیز را `⏩ رد شد (قبلاً)` کرد،
    #   `n_calls=0` شد، و لایه در تاریخِ ۲۰:۵۳ **دوباره** `INCOMPLETE` گرفت
    #   — یعنی *بعد* از رفعِ باگِ کش در ۱۹:۵۲. همان اتفاق برای
    #   `S225/S226/S223b/S223c`.
    #
    #   درمانِ درست انتخابِ دستی نیست (نمی‌دانیم کدام کش کامل است): اگر
    #   `keep_cache` روشن باشد و اجرا **صفر فراخوانی** بدهد، خودِ هارنس
    #   بی‌درنگ با کشِ **کنارگذاشته** یک‌بار دیگر اجرا می‌کند. پس هر دو
    #   حالت پوشش داده می‌شود و هیچ لایه‌ای قربانیِ انتخابِ حالت نمی‌شود.
    keep_cache = os.environ.get('AUDIT_KEEP_CACHE', '').strip() not in ('', '0')
    if _force_park:                       # پاسِ دومِ خودکار
        keep_cache = False
    if keep_cache:
        print('   (AUDIT_KEEP_CACHE=1 — resume cache KEPT so the script '
              'continues its incremental sweep instead of restarting)',
              flush=True)

    try:
        if keep_cache:
            cands = set()                 # کنارگذاری کاملاً غیرفعال می‌شود
            raise _SkipParking
        res_dir = ROOT / 'results'
        cands = set()
        # ① الگویِ رایج: results/_<stem>.json
        cands.add(res_dir / f'_{stem}.json')
        # ② هر مسیرِ json که خودِ اسکریپت در متنش نام برده باشد
        try:
            src = path.read_text(encoding='utf-8', errors='replace')
            for m in re.finditer(r"'(_[A-Za-z0-9_\-]+\.json)'", src):
                cands.add(res_dir / m.group(1))
            for m in re.finditer(r'"(_[A-Za-z0-9_\-]+\.json)"', src):
                cands.add(res_dir / m.group(1))
        except Exception:
            pass
        for c in sorted(cands):
            if c.exists() and c.is_file():
                park = c.with_suffix(c.suffix + '.audit-parked')
                try:
                    c.rename(park)
                    parked.append((c, park))
                except Exception:
                    pass
        if parked:
            print(f'   (parked {len(parked)} resume-cache file(s) so the '
                  f'script recomputes)', flush=True)
    except _SkipParking:
        pass
    except Exception:
        pass

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
        # بازگرداندنِ بی‌قید‌و‌شرطِ کشِ resume — آرشیو نباید هیچ تغییری ببیند
        for orig, park in parked:
            try:
                if orig.exists():
                    # اسکریپت خودش فایلِ تازه نوشته؛ نسخهٔ آرشیو مقدم است
                    orig.unlink()
                park.rename(orig)
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

        # ── پاسِ دومِ خودکار: صفر فراخوانی + کشِ نگه‌داشته = کشِ **کامل** ──
        # ⚠️ اندازه‌گیری‌شده: `S224/S225/S226/S223b/S223c` همه با
        #   `AUDIT_KEEP_CACHE=1` صفر فراخوانی دادند، چون کششان کامل بود
        #   (`_s224...json` هر ۴ تایم‌فریم را داشت) و اسکریپت همه‌چیز را
        #   `⏩ رد شد (قبلاً)` کرد. یک تلاشِ دومِ **خودکار** با کشِ
        #   کنارگذاشته این پنج لایه را از حکمِ ناعادلانه نجات می‌دهد،
        #   بدونِ اینکه مزیتِ حالتِ «ادامه بده» برای جاروب‌های ناتمام
        #   از دست برود.
        if (r.get('n_calls') == 0
                and os.environ.get('AUDIT_KEEP_CACHE', '').strip()
                not in ('', '0')):
            print('   ↻ zero calls with the cache kept ⇒ the cache is '
                  'COMPLETE; retrying once with it parked so the script '
                  'must recompute', flush=True)
            r2 = capture_script(script, _force_park=True)
            if (r2.get('n_calls') or 0) > 0:
                r = r2

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
