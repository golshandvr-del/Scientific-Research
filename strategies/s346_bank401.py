# -*- coding: utf-8 -*-
"""
S346 — جعبه‌ابزارِ **کاملِ ۴۰۱ اندیکاتوری** با معماریِ دسته‌ای (memory-safe)
================================================================================
چرا این فایل لازم شد؟ (سپرِ صریحِ اشتباهِ رایجِ #۳)
--------------------------------------------------------------------------------
`s346_stack.BANK_FEATURES` یک فهرستِ **دستی‌چینِ ۱۱۲ تایی** بود؛ یعنی عملاً
۲۸۹ اندیکاتور از بانک هرگز آزمون نشدند. این دقیقاً همان «اشتباهِ رایجِ #۳» است:
تمرکز روی چند اندیکاتورِ آشنا و بعد اعلامِ سریعِ سوخته‌بودنِ لایه.
«قانونِ جعبه‌ابزار» می‌گوید بانکِ ۴۰۱ ابزاری بهترین راهِ احیای لایهٔ سوخته است ⇒
باید **همه‌اش** غربال شود، نه یک‌چهارمش.

--------------------------------------------------------------------------------
۱) محدودیتِ سختِ حافظه و راهِ حل
--------------------------------------------------------------------------------
سندباکس ۹۸۵MB RAM دارد. ماتریسِ ۱۵۰٬۰۰۰×۴۰۱ در float64 برابرِ ۴۸۰MB است ⇒
غیرممکن. راهِ حل: **پارتیشن‌بندیِ ستونی**. بانک به قطعاتِ ۴۸ ستونیِ float32
تقسیم و روی دیسک (parquet) نوشته می‌شود؛ غربال هر بار یک قطعه را بار می‌کند و
رها می‌کند ⇒ اوجِ حافظه ≈ ۳۰MB به‌جای ۴۸۰MB.

--------------------------------------------------------------------------------
۲) تبدیلِ «مقیاس‌آزاد» — پیاده‌سازیِ قانونِ «شاید همه چیز شناور است!»
--------------------------------------------------------------------------------
مشکلِ بنیادیِ آستانه‌گذاریِ خام: برای اندیکاتورهایی که با قیمت **دریفت** می‌کنند
(مثلِ `kama`, `hl2`, `donchian_mid`, `obv`, `ad`) شرطی مثل «kama ≥ ۱۹۴۰» یک
گزارهٔ *تاریخی* است نه *ساختاری* — چون طلا صعودی است، این شرط فقط «زمان» را
تقسیم می‌کند و در نیمهٔ آیندهٔ داده بی‌معنا می‌شود.

راهِ حل (کاملاً داده‌محور، بدونِ دست‌چینِ انسانی):
   • برای هر ستون، همبستگیِ آن با شاخصِ زمان محاسبه می‌شود.
   • اگر |corr| > 0.25 ⇒ ستون «دریفتی» است ⇒ به **z-scoreِ غلتان** با پنجرهٔ
     ۲۳۳ (فیبوناچی — سپرِ اشتباهِ #۷) تبدیل می‌شود:  (v − μ₂₃₃)/σ₂₃₃
   • در غیر این صورت خام می‌ماند (RSI, CHOP, ER, الگوهای شمعی … ذاتاً کراندار).

نتیجه: هر آستانه به یک گزارهٔ **نسبی و رژیم‌سازگار** تبدیل می‌شود
(«اندیکاتور نسبت به توزیعِ اخیرِ خودش کجاست»)، که همان روحِ قانونِ شناور بودن است.

--------------------------------------------------------------------------------
۳) غربالِ دومرحله‌ای — چرا از آمارِ ارزانِ غیرصف‌آگاه استفاده می‌کنیم؟
--------------------------------------------------------------------------------
`q_stats` (صف‌آگاه) در هر فراخوان ~۱۵ms می‌برد. ۸۰۲ ستون × ۱۸ آستانه = ۱۴٬۴۰۰
فراخوان ⇒ ۳.۶ دقیقه در هر هندسه ⇒ برای ۲۴ هندسه ۱.۵ ساعت. غیرعملی.

پس:
   مرحلهٔ A (ارزان): آمارِ برداریِ بدونِ صف — فقط برای **تولیدِ فهرستِ کاندیدا**.
   مرحلهٔ B (گران):  همان کاندیداهای زنده‌مانده با `q_stats`ِ صف‌آگاه **بازآزمون**
                     می‌شوند و فقط زنده‌ها به مرحلهٔ انباشت می‌روند.

⚠️ این با باگِ روش‌شناختیِ نشستِ قبل **فرق دارد**: آن باگ این بود که *تابعِ هدفِ
بهینه‌سازی* غیرصف‌آگاه بود. اینجا تابعِ هدف (انباشت + گزارشِ نهایی + داوری) کاملاً
صف‌آگاه است و آمارِ ارزان فقط نقشِ «تورِ ماهیگیری» را دارد. هر کاندیدایی که
تورِ ارزان بگیرد، قبل از هر تصمیمی با معیارِ گران بازآزمون می‌شود.
"""
import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import indicator_bank as ib
from strategies.s346_fast import stats

OUT = 'results/_scan_S346'
PART_SIZE = 48          # ستون در هر قطعه ⇒ اوجِ حافظه ≈ ۳۰MB
DRIFT_CORR = 0.25       # آستانهٔ تشخیصِ دریفت با زمان
ZWIN = 233              # پنجرهٔ z-scoreِ غلتان (فیبوناچی، نه رند)


# ------------------------------------------------------------------------------
def _drift_fix(v, tidx):
    """
    اگر ستون با زمان دریفت دارد، به z-scoreِ غلتان تبدیلش کن (مقیاس‌آزاد).
    خروجی: (آرایهٔ float32, برچسبِ نوعِ تبدیل)
    """
    finite = np.isfinite(v)
    if finite.sum() < 100:
        return v.astype(np.float32), 'raw'
    vv, tt = v[finite], tidx[finite]
    sv, st = vv.std(), tt.std()
    if sv <= 0 or st <= 0:
        return v.astype(np.float32), 'raw'
    corr = float(np.corrcoef(vv, tt)[0, 1])
    if not np.isfinite(corr) or abs(corr) <= DRIFT_CORR:
        return v.astype(np.float32), 'raw'
    s = pd.Series(v)
    mu = s.rolling(ZWIN, min_periods=55).mean()
    sd = s.rolling(ZWIN, min_periods=55).std()
    z = ((s - mu) / sd.where(sd > 0)).values
    return z.astype(np.float32), 'z233'


def part_paths(card):
    man = f"{OUT}/{card}_bank401_manifest.json"
    if not os.path.exists(man):
        return None
    return json.load(open(man))


def build_parts(card, df, ch, force=False):
    """
    محاسبهٔ کلِ بانکِ ۴۰۱ + ویژگی‌های ساختاریِ کانال + زمان، در قطعاتِ ۴۸ ستونی.
    خروجی: manifest شاملِ فهرستِ قطعات و نوعِ تبدیلِ هر ستون.
    """
    os.makedirs(OUT, exist_ok=True)
    man_path = f"{OUT}/{card}_bank401_manifest.json"
    if (not force) and os.path.exists(man_path):
        man = json.load(open(man_path))
        if man.get('n_rows') == len(df) and all(os.path.exists(p) for p in man['parts']):
            print(f"  bank401: cache hit ({man['n_cols']} cols, "
                  f"{len(man['parts'])} parts)", flush=True)
            return man

    names = ib.list_indicators()
    tidx = np.arange(len(df), dtype=np.float64)
    parts, kinds = [], {}
    buf, pidx = {}, 0

    def flush(buf, pidx):
        p = f"{OUT}/{card}_bank401_p{pidx:02d}.parquet"
        pd.DataFrame(buf).to_parquet(p, compression='snappy')
        parts.append(p)
        return {}, pidx + 1

    # --- ۴۰۱ اندیکاتورِ بانک ---
    fail = []
    for i, nm in enumerate(names):
        try:
            v = ib.compute(nm, df).values.astype(np.float64)
        except Exception as e:
            fail.append((nm, str(e)[:30]))
            continue
        arr, kind = _drift_fix(v, tidx)
        col = 'B:' + nm
        buf[col] = arr
        kinds[col] = kind
        if len(buf) >= PART_SIZE:
            buf, pidx = flush(buf, pidx)
        if (i + 1) % 100 == 0:
            print(f"    bank401 {i+1}/{len(names)}", flush=True)

    # --- ویژگی‌های ساختاریِ خودِ کانالِ تطبیقی (ذاتِ منبعِ mladen) ---
    c = df['close'].values.astype(np.float64)
    atr_a, val, er = ch['atr_a'], ch['val'], ch['er']
    with np.errstate(invalid='ignore', divide='ignore'):
        den = np.where(atr_a > 0, atr_a, np.nan)
        chan = {
            'CHAN:er': er,
            'CHAN:atr_slope': np.concatenate(([np.nan], np.diff(atr_a))) / den,
            'CHAN:val_slope': np.concatenate(([np.nan], np.diff(val))) / den,
            'CHAN:pierce': np.abs(c - val) / den,
            'CHAN:body_atr': np.abs(c - df['open'].values) / den,
            'CHAN:range_atr': (df['high'].values - df['low'].values) / den,
        }
        aser = pd.Series(atr_a)
        chan['CHAN:width_rel'] = (aser / aser.rolling(233, min_periods=55).mean()).values
    for k, v in chan.items():
        buf[k] = np.asarray(v, dtype=np.float32)
        kinds[k] = 'raw'
        if len(buf) >= PART_SIZE:
            buf, pidx = flush(buf, pidx)

    # --- زمان (برچسب‌دار تا سهمش شفاف بماند — سپرِ #۱) ---
    t = pd.to_datetime(df['time'], unit='s', utc=True) if 'time' in df.columns \
        else pd.to_datetime(df.index, utc=True)
    for k, v in (('TIME:hour', t.dt.hour.values), ('TIME:dow', t.dt.dayofweek.values)):
        buf[k] = v.astype(np.float32)
        kinds[k] = 'raw'
    if buf:
        buf, pidx = flush(buf, pidx)

    man = dict(card=card, n_rows=int(len(df)), n_cols=len(kinds),
               parts=parts, kinds=kinds, failed=fail)
    json.dump(man, open(man_path, 'w'))
    nz = sum(1 for v in kinds.values() if v == 'z233')
    print(f"  bank401 built: {len(kinds)} cols in {len(parts)} parts "
          f"| drift-corrected(z233)={nz} | failed={len(fail)}", flush=True)
    return man


# ------------------------------------------------------------------------------
def cheap_stats(pnl, win, sel):
    """آمارِ ارزانِ غیرصف‌آگاه — فقط برای تورِ کاندیدا (مرحلهٔ A)."""
    n = int(sel.sum())
    if n == 0:
        return 0, 0.0, 0.0
    p = pnl[sel]
    gw = p[p > 0].sum()
    gl = -p[p <= 0].sum()
    return n, float(win[sel].mean() * 100), float(gw / gl) if gl > 0 else 999.0


def screen401(P, card, man, allow_time=False,
              qlist=(0.10, 0.15, 0.20, 0.25, 0.30, 0.70, 0.75, 0.80, 0.85, 0.90),
              min_gain_d=1.5, min_gain_h=1.0, keep_top=260, verbose=True):
    """
    غربالِ دومرحله‌ای روی کلِ بانک.
      A) تورِ ارزان روی همهٔ ستون‌ها × آستانه‌ها (بدونِ صف)
      B) بازآزمونِ صف‌آگاهِ `keep_top` کاندیدای برترِ تور

    خروجی: (base_d, base_h, cands) — سازگار با `stack_maxn`.
    مقادیرِ ستون‌های زنده‌مانده در `P['FV']` بار می‌شوند (فقط همان ستون‌ها ⇒ سبک).
    """
    from strategies.s346_stack2 import q_stats
    sb, is_d = P['sb'], P['is_d']
    pnl, win = P['pnl'], P['win']
    n_ev = len(sb)
    base_d, base_h, _ = q_stats(P, np.ones(n_ev, bool))
    # پایهٔ ارزان (برای مقایسهٔ هم‌جنس در مرحلهٔ A)
    _, cwr_d, _ = cheap_stats(pnl, win, is_d)
    _, cwr_h, _ = cheap_stats(pnl, win, ~is_d)

    pool = []
    for p in man['parts']:
        try:
            part = pd.read_parquet(p)
        except Exception:
            continue
        for col in part.columns:
            if (not allow_time) and col.startswith('TIME:'):
                continue
            v = part[col].values.astype(np.float64)[sb]
            finite = np.isfinite(v)
            if finite.sum() < 0.5 * len(v):
                continue
            vd = v[is_d & finite]
            if len(vd) < 300:
                continue
            uq = np.unique(vd[np.isfinite(vd)])
            if len(uq) < 5:          # ستونِ عملاً ثابت/دوحالته با تنوعِ ناکافی
                continue
            for q in qlist:
                thr = float(np.nanquantile(vd, q))
                for d in ('ge', 'le'):
                    m = ((v >= thr) if d == 'ge' else (v <= thr)) & finite
                    nd_, wd_, pd_ = cheap_stats(pnl, win, m & is_d)
                    if nd_ < 150:
                        continue
                    nh_, wh_, ph_ = cheap_stats(pnl, win, m & ~is_d)
                    if nh_ < 80:
                        continue
                    gd, gh = wd_ - cwr_d, wh_ - cwr_h
                    if gd >= min_gain_d and gh >= min_gain_h:
                        pool.append(dict(col=col, q=q, thr=thr, dir=d,
                                         cheap_min_gain=round(min(gd, gh), 3)))
        del part
    pool.sort(key=lambda r: -r['cheap_min_gain'])
    pool = pool[:keep_top]
    if verbose:
        print(f"    screen401[A]: cheap-net caught {len(pool)} candidates", flush=True)
    if not pool:
        return base_d, base_h, []

    # --- مرحلهٔ B: بار کردنِ فقط ستون‌های زنده‌مانده + بازآزمونِ صف‌آگاه ---
    need = set(r['col'] for r in pool)
    vals = {}
    for p in man['parts']:
        try:
            # ⚡ خواندنِ ارزانِ فهرستِ ستون‌ها از فراداده (بدونِ بار کردنِ داده)
            import pyarrow.parquet as pq
            have = [c for c in pq.ParquetFile(p).schema.names if c in need]
            if not have:
                continue
            part = pd.read_parquet(p, columns=have)
        except Exception:
            continue
        for col in part.columns:
            vals[col] = part[col].values.astype(np.float64)[sb]
        del part
    P['FV'] = pd.DataFrame(vals)

    cands = []
    for r in pool:
        v = vals.get(r['col'])
        if v is None:
            continue
        finite = np.isfinite(v)
        m = ((v >= r['thr']) if r['dir'] == 'ge' else (v <= r['thr'])) & finite
        sd, sh, _ = q_stats(P, m)
        if sd['n'] < 45 or sh['n'] < 25:
            continue
        gd, gh = sd['wr'] - base_d['wr'], sh['wr'] - base_h['wr']
        if gd >= min_gain_d and gh >= min_gain_h:
            cands.append(dict(col=r['col'], q=r['q'], thr=r['thr'], dir=r['dir'],
                              gd=round(gd, 2), gh=round(gh, 2),
                              wr_d=sd['wr'], wr_h=sh['wr'],
                              n_d=sd['n'], n_h=sh['n'],
                              exp_d=sd['exp'], exp_h=sh['exp'],
                              pf_d=sd['pf'], pf_h=sh['pf']))
    cands.sort(key=lambda r: -min(r['gd'], r['gh']))
    if verbose:
        print(f"    screen401[B]: {len(cands)} survive queue-aware re-test", flush=True)
    return base_d, base_h, cands
