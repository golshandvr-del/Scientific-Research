# -*- coding: utf-8 -*-
"""
داورِ **جهانیِ** ممیزی — از فایلِ ضبط تا حکمِ RQS2
================================================================================

ورودی: `results/_audit_rename/captures/<script>.capture.json` که
`tools/audit_capture.py` ساخته (سیگنالِ *اندازه‌گیری‌شدهٔ* لایه، نه حدس‌زده).

خروجی: `results/_audit_rename/verdicts/<layer>.json` با حکمِ هر کارت.

════════════════════════════════════════════════════════════════════════════
سه مسئلهٔ فنی که این ابزار حل می‌کند
════════════════════════════════════════════════════════════════════════════

① **شناساییِ کارت.** فایلِ ضبط دارایی را همیشه نمی‌داند (`run_backtest`
   پارامترِ `asset` ندارد). پس کارت از **اثرِانگشتِ داده** پیدا می‌شود:
   `(n_bars, close_first, close_last)` با همهٔ CSVهای `data/` مقایسه می‌شود.
   این تطبیق قطعی است، حدس نیست. اگر تطبیق پیدا نشود ⇒ `INCOMPLETE`.

② **واحدِ هندسه.** `simulate_trades` هندسه را pip می‌گیرد ولی `run_backtest`
   دلار. تبدیل با `pip_size` همان دارایی از مدلِ هزینهٔ رسمی انجام می‌شود
   (`engine.scalp_engine.ASSETS`)، نه با ضریبِ دستی.

③ **جمعِ دو سمت.** `run_backtest` یک‌سمته است، پس یک لایه روی یک کارت دو
   فراخوانی دارد (long و short). این‌ها باید در **یک** داوری جمع شوند، چون
   لایه در واقعیت هر دو را با هم معامله می‌کند. کلیدِ ادغام:
   `(دارایی، تایم‌فریم، هندسهٔ همسان، افقِ همسان)`.

════════════════════════════════════════════════════════════════════════════
مرزِ صداقت
════════════════════════════════════════════════════════════════════════════
هیچ پارامتری اینجا بهینه نمی‌شود. هیچ سیگنالی ساخته نمی‌شود. اگر ضبط ناقص
باشد، حکم `INCOMPLETE` است — **نه** ACCEPT. سیاستِ اسپک: «نبودِ آزمونِ کنترل،
شاهدِ وجودِ مهارت نیست.»
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import scalp_engine as se                      # noqa: E402
from tools.audit_rqs2_rejudge import (                     # noqa: E402
    load_card, bar_time_of, resolve_max_hold, PERM_K, SEED,
    N_TRIALS_FALLBACK, VERDICT_RANK, pick_headline,
)
from engine import rqs2 as R                               # noqa: E402
from tools.audit_fast_null import build_null_fast          # noqa: E402
from tools.audit_capture import unpack_idx                 # noqa: E402

CAP = ROOT / 'results' / '_audit_rename' / 'captures'
VER = ROOT / 'results' / '_audit_rename' / 'verdicts'
VER.mkdir(parents=True, exist_ok=True)
DATA = ROOT / 'data'


# ════════════════════════════════════════════════════════════════════════════
#  ① شناساییِ کارت از اثرِانگشتِ داده
# ════════════════════════════════════════════════════════════════════════════
_FP: dict | None = None
_TAIL: dict | None = None


def data_fingerprints() -> dict:
    """
    اثرِانگشتِ همهٔ CSVهای `data/` را می‌سازد.

    کلید: `(n_bars, round(close_first,6), round(close_last,6))`
    این سه‌گانه در عمل یکتاست (هر ترکیبِ جفت‌ارز-تایم‌فریم طول و لنگرهای
    قیمتیِ متفاوت دارد)، پس تطبیق **قطعی** است نه احتمالی.

    نکته: اسکریپت‌های آرشیو بعضاً دادهٔ **بریده** می‌دهند (مثلاً آخرین ۲۰۰هزار
    کندل). پس علاوه بر کلِ فایل، دنبالهٔ آخرِ آن هم اثرِانگشت می‌گیرد.
    """
    global _FP
    if _FP is not None:
        return _FP
    fp: dict = {}
    for csv in sorted(DATA.glob('*.csv')):
        stem = csv.stem                     # e.g. XAUUSD_M15
        if '_' not in stem:
            continue
        pair, tf = stem.rsplit('_', 1)
        try:
            df = pd.read_csv(csv, usecols=['close'])
        except Exception:
            continue
        c = df['close'].to_numpy(float)
        n = len(c)
        # کلِ فایل
        fp[(n, round(float(c[0]), 6), round(float(c[-1]), 6))] = (pair, tf, 0)
        # برش‌های رایجِ آرشیو (last-N)
        for cut in (200000, 150000, 130994, 120000, 100000, 60000, 50000, 40000):
            if cut < n:
                fp[(cut, round(float(c[n - cut]), 6),
                    round(float(c[-1]), 6))] = (pair, tf, n - cut)
    _FP = fp
    return fp


def _tail_index() -> dict:
    """
    نمایهٔ **عمومیِ** برش‌های دنبالهٔ آخر، به تفکیکِ جفت‌ارز.

    کلید: `(pair, close_last_rounded)` → لیستِ `(tf, close_array)`
    با این نمایه می‌توان **هر** طولِ برشی را حل کرد، نه فقط چند برشِ
    از پیش‌حدس‌زده‌شده.
    """
    global _TAIL
    if _TAIL is not None:
        return _TAIL
    idx: dict = {}
    for csv in sorted(DATA.glob('*.csv')):
        stem = csv.stem
        if '_' not in stem:
            continue
        pair, tf = stem.rsplit('_', 1)
        try:
            c = pd.read_csv(csv, usecols=['close'])['close'].to_numpy(float)
        except Exception:
            continue
        idx.setdefault(pair, []).append((tf, c))
    _TAIL = idx
    return idx


def _identify_by_asset(call: dict):
    """
    کارتِ فراخوانی‌هایی که **دیتافریم ندارند** ولی `asset` صریح دارند.

    این حالت مخصوصِ موتورِ چهارم (`rqs2.compute_rqs2`) است: دارایی معلوم
    است ولی تایم‌فریم نه. تایم‌فریم از **بلندترین ایندکسِ سیگنال** استنتاج
    می‌شود: هر تایم‌فریمی که طولش از آن ایندکس کمتر باشد، ممکن نیست.

    مرزِ صداقت: اگر بیش از یک تایم‌فریمِ آن دارایی جا شد، هیچ تصمیمی گرفته
    نمی‌شود و `None` برمی‌گردد. یعنی ابهام به `INCOMPLETE` می‌انجامد، هرگز
    به یک حدسِ داوری‌شده.
    """
    pair = call.get('asset')
    if not pair:
        return None
    tails = _tail_index()
    if pair not in tails:
        return None

    try:
        li = unpack_idx(call.get('long_idx'))
        si = unpack_idx(call.get('short_idx'))
    except Exception:
        return None
    hi = -1
    for arr in (li, si):
        if arr is not None and len(arr):
            hi = max(hi, int(np.max(arr)))
    if hi < 0:
        return None

    fits = [(tf, len(c)) for tf, c in tails[pair] if len(c) > hi]
    if len(fits) != 1:
        # مبهم (چند تایم‌فریم جا می‌شوند) یا ناممکن (هیچ‌کدام) ⇒ تصمیم نگیر
        return None
    return (pair, fits[0][0], 0)


def identify_card(call: dict):
    """
    کارتِ یک فراخوانیِ ضبط‌شده را برمی‌گرداند یا `None`.

    مرحلهٔ ①: تطبیقِ دقیقِ سه‌گانهٔ اثرِانگشت (سریع، برای کلِ فایل و
    برش‌های رایج).

    مرحلهٔ ②: **تطبیقِ عمومیِ برش** ⚠️ چرا لازم شد (اندازه‌گیری‌شده):
    `S172` دادهٔ خود را به `۹۴٬۲۱۹` کندل بریده بود — طولی که در فهرستِ
    برش‌های رایج نبود. نتیجه: کارت شناسایی نمی‌شد و لایه `INCOMPLETE`
    می‌گرفت، **در حالی که ضبطش کاملاً موفق بود** (۴۰ فراخوانی، ۱۲۶۵
    سیگنال). این یک نقصِ ابزار بود که به‌اشتباه به پای لایه نوشته می‌شد.

    تطبیق با «دارایی + طول + لنگرهای قیمتی» انجام می‌شود و بعد با
    `close_sum` **تأیید** می‌شود، پس همچنان قطعی است نه احتمالی.

    مرحلهٔ ⓪ (باگِ شانزدهم) ⚠️ چرا لازم شد (اندازه‌گیری‌شده): موتورِ چهارم
    `rqs2.compute_rqs2` **دیتافریم نمی‌گیرد** (فقط لیستِ معاملات)، پس در ضبط
    `n_bars=None` و `close_first/last=None` است — ولی `asset` را **صریح**
    دارد. کدِ قبلی بی‌قید `int(call['n_bars'])` می‌زد و همان اولین فراخوانیِ
    این‌شکلی یک `TypeError` پرتاب می‌کرد که **کلِ داوری** را از کار می‌انداخت:
    ۴ فراخوانیِ این‌شکلی، ۳۶ فراخوانیِ سالم را با خود نابود می‌کردند و لایه
    `cards=0 → INCOMPLETE` می‌گرفت. مدرک: `s350_triplelock_sweep` و
    `s348_rr_sweep` هر دو `calls=40` با `n_bars=None: 4` داشتند و حکمشان
    `INCOMPLETE/0.0` شد، در حالی که خودِ stdoutشان حکمِ کاملِ RQS2 را چاپ
    کرده بود (`EURUSD-W1 REJECT RQS2=5.4` با همهٔ دروازه‌ها).

    درمان: این فراخوانی‌ها با `_identify_by_asset` حل می‌شوند — دارایی از
    خودِ ضبط، و تایم‌فریم از **بلندترین ایندکسِ سیگنال** که فقط در یک
    تایم‌فریمِ آن دارایی جا می‌شود. اگر بیش از یک تایم‌فریم جا شد، تصمیم
    گرفته **نمی‌شود** (بازگشتِ `None`) تا حدس وارد داوری نشود.
    """
    if call.get('n_bars') is None:
        return _identify_by_asset(call)

    n = int(call['n_bars'])
    c0 = round(float(call['close_first']), 6)
    c1 = round(float(call['close_last']), 6)

    hit = data_fingerprints().get((n, c0, c1))
    if hit:
        return hit

    # ── مرحلهٔ ②: برشِ دلخواه از دنبالهٔ آخر ──────────────────────────────
    want_sum = call.get('close_sum')
    asset = call.get('asset')
    pairs = ([asset] if asset in _tail_index() else list(_tail_index()))
    for pair in pairs:
        for tf, c in _tail_index()[pair]:
            if n > len(c):
                continue
            off = len(c) - n                      # برشِ last-N
            if (round(float(c[off]), 6) == c0
                    and round(float(c[-1]), 6) == c1):
                if want_sum is not None:
                    got = float(np.nansum(c[off:]))
                    if abs(got - float(want_sum)) > max(1e-3, abs(got) * 1e-9):
                        continue
                return (pair, tf, off)
    return None


# ════════════════════════════════════════════════════════════════════════════
#  ② هندسه: دلار → pip
# ════════════════════════════════════════════════════════════════════════════
def geom_to_pip(g: dict, pair: str, n_bars: int, idx: np.ndarray):
    """
    هندسهٔ ضبط‌شده را به آرایهٔ pip هم‌طولِ داده تبدیل می‌کند.

    · `simulate_trades` ⇒ واحد از قبل pip است.
    · `run_backtest`    ⇒ واحد دلار است ⇒ تقسیم بر `pip_size` دارایی.
    """
    if g is None or g.get('kind') == 'none':
        return None
    unit = g.get('unit', 'pip')
    div = 1.0
    if unit == 'dollar':
        cfg = se.ASSETS.get(pair)
        if cfg is None:
            return None
        div = float(cfg['pip'])

    # ⚠️ BUG-20 — یک فراخوانِ بی‌هندسه، کلِ پاسِ داوری را می‌کشت.
    # فراخوان‌هایی هستند که هیچ معامله‌ای نمی‌سازند (`nL=0 nS=0`) و آرشیو در
    # آن‌ها `sl`/`tp` را با `value=None` ثبت می‌کند — برای S330 دقیقاً دو
    # فراخوانِ آخر از شش فراخوان چنین بودند. نگهبانِ پیشین فقط `g is None` و
    # `kind=='none'` را می‌گرفت، پس `float(None)` یک `TypeError` می‌داد و مثلِ
    # BUG-16 پاس را از میان می‌بُرد و کارت‌های سالم را با خود می‌بُرد.
    # اکنون هندسهٔ نامعتبر ⇒ `None` که فراخوان‌کننده با `continue` ردش می‌کند:
    # فراخوانِ معیوب کنار گذاشته می‌شود، نه کلِ لایه.
    def _num(x):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return None
        return None if (v != v) else v          # NaN را هم رد می‌کند

    if g['kind'] == 'scalar':
        v = _num(g.get('value'))
        return None if v is None else v / div

    vals = g.get('at_signals') or []
    if not vals:
        m = _num(g.get('median'))
        return None if m is None else m / div
    arr = np.full(int(n_bars), np.nan)
    k = min(len(vals), len(idx))
    for j in range(k):
        v = vals[j]
        if v is not None:
            arr[int(idx[j])] = float(v) / div
    return arr


# ════════════════════════════════════════════════════════════════════════════
#  ③ ادغامِ دو سمت و داوری
# ════════════════════════════════════════════════════════════════════════════
def geom_shape(call: dict) -> str:
    """
    اثرِانگشتِ **شکلِ** هندسه (نه مقدارِ آن) برای ادغامِ دو سمتِ یک لایه.

    چرا نه مقدار: در لایه‌های ATR-محور، میانهٔ SL سمتِ long و short طبعاً
    متفاوت است (نمونهٔ کندل‌های متفاوت). اگر مقدار را کلید کنیم، یک لایه
    مصنوعاً به دو «نیم‌لایه»ی کم‌معامله می‌شکند و این هم `H9` (کفِ نمونه) را
    ناعادلانه می‌شکند و هم نمرهٔ نهایی را خراب می‌کند.

    آنچه واقعاً باید همسان باشد، *سازوکار* است: اسکالر بودن/سری بودن، و
    نسبتِ RR. اگر دو فراخوانی RR متفاوت داشته باشند، واقعاً دو هندسهٔ
    متفاوت‌اند و باید جدا داوری شوند.
    """
    sl, tp = call.get('sl') or {}, call.get('tp') or {}
    ks, kt = sl.get('kind', 'none'), tp.get('kind', 'none')

    def rep(g):
        if g.get('kind') == 'scalar':
            return g.get('value')
        return g.get('median')

    vs, vt = rep(sl), rep(tp)
    rr = None
    if vs and vt:
        rr = round(float(vt) / float(vs), 3)
    return f'{ks}/{kt}/rr={rr}'


def judge_capture(cap: dict, n_trials: int, layer_name: str) -> dict:
    """همهٔ فراخوانی‌های یک ضبط را به کارت‌ها نگاشت و داوری می‌کند."""
    groups: dict = {}
    unmatched = 0

    for call in cap.get('calls', []):
        if 'capture_error' in call:
            continue
        ident = identify_card(call)
        if ident is None:
            unmatched += 1
            continue
        pair, tf, offset = ident
        # افق و همپوشانی و هندسه باید همسان باشند تا ادغام مجاز باشد
        # ادغام باید **دو سمتِ یک لایه روی یک کارت** را در یک داوری بگذارد.
        # پس هندسه با «شکل» (اسکالر/سری) و نسبتِ RR کلید می‌شود، نه با مقدارِ
        # میانهٔ آن سمت — چون long و short طبعاً میانهٔ ATR متفاوتی دارند و
        # کلید کردن روی میانه، لایه را مصنوعاً به دو نیم‌لایه می‌شکست.
        key = (pair, tf, offset, call.get('max_hold'),
               bool(call.get('allow_overlap')), geom_shape(call))
        groups.setdefault(key, []).append(call)

    per_card = []
    for key, calls in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        pair, tf, offset, mh_raw, ao, _shape = key
        df_full = load_card(pair, tf)
        if df_full is None:
            per_card.append({'card': f'{pair}-{tf}', 'verdict': 'INCOMPLETE',
                             'rqs2_score': 0.0, 'reason': 'card data missing'})
            continue
        df = (df_full.iloc[offset:].reset_index(drop=True)
              if offset else df_full)
        n = len(df)

        ls = np.zeros(n, bool)
        ss = np.zeros(n, bool)
        sl_arr = tp_arr = None
        for call in calls:
            # ایندکس‌ها با کدگذاریِ اختلافیِ **بی‌اتلاف** ذخیره شده‌اند
            # (`pack_idx`). `unpack_idx` فرمتِ خامِ قدیمی را هم می‌پذیرد.
            li = unpack_idx(call.get('long_idx'))
            si = unpack_idx(call.get('short_idx'))
            li = li[li < n]; si = si[si < n]
            ls[li] = True
            ss[si] = True
            idx_all = np.union1d(li, si).astype(int)
            g_sl = geom_to_pip(call.get('sl'), pair, n, idx_all)
            g_tp = geom_to_pip(call.get('tp'), pair, n, idx_all)
            # ادغامِ هندسهٔ دو سمت
            for name, g in (('sl', g_sl), ('tp', g_tp)):
                cur = sl_arr if name == 'sl' else tp_arr
                if g is None:
                    continue
                if np.isscalar(g):
                    newv = g
                else:
                    if cur is None or np.isscalar(cur):
                        newv = g
                    else:
                        newv = np.where(np.isfinite(g), g, cur)
                if name == 'sl':
                    sl_arr = newv
                else:
                    tp_arr = newv

        if sl_arr is None or tp_arr is None:
            per_card.append({'card': f'{pair}-{tf}', 'verdict': 'INCOMPLETE',
                             'rqs2_score': 0.0,
                             'reason': 'geometry not recoverable (H2 unjudgeable)'})
            continue

        mh = resolve_max_hold(mh_raw if mh_raw not in (None, 'series') else None, n)

        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, pair,
                                max_hold=mh, allow_overlap=bool(ao))
        if tr is None or len(tr) == 0:
            per_card.append({'card': f'{pair}-{tf}', 'verdict': 'REJECT',
                             'rqs2_score': 0.0, 'reason': 'zero trades',
                             'n_trades': 0})
            continue

        n_by_side = {s: int((tr['direction'] == s).sum())
                     for s in ('long', 'short')}
        sides = tuple(s for s in ('long', 'short') if n_by_side[s] > 0)
        n_sig = {'long': int(ls.sum()), 'short': int(ss.sum())}

        # مدلِ صفر: به تفکیکِ سمت، هندسه و افقِ **یکسان** با لایه
        sl_med = (float(sl_arr) if np.isscalar(sl_arr)
                  else float(np.nanmedian(sl_arr[np.union1d(np.flatnonzero(ls),
                                                            np.flatnonzero(ss))])))
        tp_med = (float(tp_arr) if np.isscalar(tp_arr)
                  else float(np.nanmedian(tp_arr[np.union1d(np.flatnonzero(ls),
                                                            np.flatnonzero(ss))])))
        parts = {}
        for side in sides:
            parts[side] = build_null_fast(
                df, pair, sl_med, tp_med, mh, side,
                max(n_sig[side], n_by_side[side]), k=PERM_K, seed=SEED)
        # ── ساختارِ **کانونیِ** نول: تودرتو به تفکیکِ سمت ────────────────────
        # اسپک (`null_from_s346`) شکلِ زیر را می‌خواهد:
        #     {'long': {uncond_wr, perm_mean, perm_sd, perm_max, perm_k},
        #      'short': {...}}
        # اگر تختِ (flat) پاس شود، `_side_null_ref` هیچ سمتی پیدا نمی‌کند و
        # H3/H4/H5 خاموش می‌شوند (`UNKNOWN`) — همان چیزی که در اجرای اولِ S71
        # دیدم. پس ادغامِ دستیِ دو سمت **غلط** بود؛ خودِ موتور باید سمت‌ها را
        # با منطقِ خودش ترکیب کند.
        nul = {}
        for side in ('long', 'short'):
            if side in parts:
                p = parts[side]
                nul[side] = {'uncond_wr': p['uncond_wr'],
                             'perm_mean': p['perm_mean'],
                             'perm_sd': p['perm_sd'],
                             'perm_max': p['perm_max'],
                             'perm_k': p['perm_k']}

        split_bar = int(n * 0.70)
        # ── `tp_pip` برای هندسهٔ متغیر ────────────────────────────────────────
        # اسپک می‌گوید نبودِ `tp_pip` ⇒ `H2 = UNKNOWN`، و هدفش جلوگیری از
        # فرضِ خودکارِ `tp = sl` است (که سپرِ ضدِتقلبِ TP<SL را خاموش می‌کرد).
        # اینجا `tp` **حدس زده نمی‌شود**: از خودِ ضبط اندازه‌گیری شده است.
        # در لایه‌های ATR-محور، RR ثابت است و فقط مقیاس با نوسان تغییر می‌کند،
        # پس میانه نمایندهٔ درستِ هندسه است و H2 قابلِ داوری می‌ماند.
        # ⚠️ این به نفعِ لایه **نیست**: با تحویلِ `tp`، سپرِ TP<SL روشن می‌شود
        # و اگر لایه WR را با براکتِ کج خریده باشد، همین‌جا لو می‌رود.
        rr_ratio = (tp_med / sl_med) if sl_med else None
        r = R.compute_rqs2(
            tr, pair,
            sl_pip=sl_med,
            tp_pip=tp_med,
            bar_time=bar_time_of(df), null=nul, n_trials=n_trials,
            split_bar=split_bar, close=df['close'].to_numpy(float))
        r['geometry_kind'] = ('scalar' if np.isscalar(tp_arr) else 'variable/ATR')
        r['card'] = f'{pair}-{tf}'
        r['n_signals'] = n_sig
        r['geometry'] = {'sl_pip_med': round(sl_med, 4),
                         'tp_pip_med': round(tp_med, 4),
                         'rr': round(tp_med / sl_med, 4) if sl_med else None,
                         'max_hold': mh, 'allow_overlap': bool(ao)}
        per_card.append(r)

        g = r.get('gates', {})
        fails = [k for k, v in g.items() if v is False]
        unk = [k for k, v in g.items() if v is None]
        print(f'  {r["card"]:<14} {r.get("verdict","?"):<14} '
              f'score={r.get("rqs2_score",0):>5.1f} n={len(tr):>5} '
              f'rr={r["geometry"]["rr"]} '
              f'fail={",".join(fails) or "-"} unk={",".join(unk) or "-"}',
              flush=True)

    verdict, score = pick_headline(per_card)
    return {'layer': layer_name, 'script': cap.get('script'),
            'n_trials': n_trials, 'perm_k': PERM_K, 'seed': SEED,
            'unmatched_calls': unmatched,
            'reproduction': [{'engine': c.get('engine', 'simulate_trades'),
                              'n_trades': c.get('result_n_trades')}
                             for c in cap.get('calls', [])
                             if 'capture_error' not in c],
            'cards': per_card,
            'headline_verdict': verdict, 'headline_score': round(score, 1)}


def main():
    if len(sys.argv) < 3:
        print('usage: audit_judge_capture.py <capture.json> <layer_md_name> '
              '[n_trials]')
        return 2
    cap_path = Path(sys.argv[1])
    layer = sys.argv[2]
    n_trials = int(sys.argv[3]) if len(sys.argv) > 3 else N_TRIALS_FALLBACK

    with open(cap_path, encoding='utf-8') as fh:
        cap = json.load(fh)

    print(f'══ judging {layer}  (n_trials={n_trials}) ══', flush=True)
    out = judge_capture(cap, n_trials, layer)
    dest = VER / (layer.replace('.md', '') + '.json')
    with open(dest, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=float)
    print(f'HEADLINE: {out["headline_verdict"]} {out["headline_score"]}')
    print(f'  -> {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
