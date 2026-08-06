# -*- coding: utf-8 -*-
"""
ماموریتِ ممیزی — **بازداوریِ هر لایهٔ آرشیو با معیارِ RQS2 و تغییرِ نامِ فایل**
================================================================================
User Note این نشست صریح است و دامنه‌اش را خودش بسته:

    «تو مجاز به هیچ تغییری در سایت یا ثبتِ هیچ لایهٔ استراتژیِ جدیدی نیستی.
     تو مامورِ ممیزی هستی. وارد بخشِ استراتژی‌های گیتهاب می‌شوی، از اولین لایه
     شروع می‌کنی، طبقِ معیارِ جدیدِ rqs2 تستش می‌کنی، بعد اسمش را با فرمتِ
     جدید تغییر می‌دهی. فقط همین.»

پس این ابزار **هیچ لایه‌ای نمی‌سازد، هیچ پارامتری بهینه نمی‌کند و هیچ بهبودی
پیشنهاد نمی‌دهد.** فقط سه کار: (۱) لایهٔ آرشیو را بازتولید می‌کند، (۲) با
موتورِ رسمیِ `engine/rqs2.py` داوری می‌کند، (۳) حکم و نمره را برای تغییرِ نام
برمی‌گرداند.

════════════════════════════════════════════════════════════════════════════
چهار تصمیمِ طراحی، هرکدام بر ضدِ یک خطای مشخص
════════════════════════════════════════════════════════════════════════════

① **داورْ موتورِ رسمی است، نه بازپیاده‌سازیِ من.**
   `from engine import rqs2` — همان کدی که اسپکِ v2.4/v2.5/v2.6 را پیاده کرده و
   ۱۷ موردِ سلف‌تستش پاس است. اگر معیار را دوباره می‌نوشتم، هر اختلافِ حکم بین
   «اشتباهِ لایه» و «اشتباهِ داورِ من» تفکیک‌ناپذیر می‌شد. پروژه یک‌بار از این
   آسیب دید (دانشِ سربه‌سر در یک ابزار بود و در ابزارِ حسابرسی نبود).

② **هر لایه روی هر کارتی که خودش ادعا کرده، *مجزا* داوری می‌شود** (قانونِ MTF).
   نامِ فایلِ نو همهٔ تایم‌فریم‌های آزموده را حمل می‌کند، و نمره‌ای که در نام
   می‌نشیند **بدترین کارت** نیست و **بهترین** هم نیست: نمرهٔ کارتی است که حکمِ
   نهایی از آن آمده (سلسله‌مراتبِ حکم پایین‌تر تعریف شده). این تصمیم صریح ثبت
   می‌شود چون قابلِ بحث است.

③ **مدلِ صفر برای هر (کارت، سمت، هندسه، افق) از نو ساخته می‌شود.**
   درسِ قاطعِ S384/S385: `perm_sd` تابعِ **تعدادِ معامله** است، نه ثابتِ کارت.
   بازاستفاده از نولِ یک لایهٔ پرمعامله برای لایه‌ای کم‌معامله، سقفِ شانس را
   کم‌برآورد می‌کند و **پذیرشِ کاذب** می‌سازد. پس هیچ نولی بازاستفاده نمی‌شود.

④ **`n_trials` صادقانه از خودِ سندِ لایه استخراج می‌شود.**
   کم‌شمردنِ سابقهٔ جست‌وجو دقیقاً «دور زدنِ معیارِ پروژه» است (اشتباهِ رایجِ ۸).
   اگر سند عددِ جاروب را نگفته باشد، فالبکِ محافظه‌کارانهٔ `N_TRIALS_FALLBACK`
   به کار می‌رود که **بزرگ** است، یعنی به نفعِ REJECT خطا می‌کند نه ACCEPT.

════════════════════════════════════════════════════════════════════════════
سلسله‌مراتبِ حکمِ چند-کارتی (تصمیمِ صریح، نه ضمنی)
════════════════════════════════════════════════════════════════════════════
یک لایه روی ۴ کارت می‌تواند ۴ حکمِ متفاوت بگیرد. نامِ فایل یک حکم می‌خواهد.
قاعده: **بهترین حکمی که لایه روی *هر* کارتی گرفته**، چون سؤالِ پروژه این است
که «آیا این لایه جایی زنده است؟» — و اگر روی یک کارت ACCEPT شود، لایه زنده
است حتی اگر روی سه کارتِ دیگر بمیرد (قانونِ MTF: هر کارت منطقِ خودش را دارد).
ترتیب: ACCEPT > POWER-LIMITED > UNPROVEN > REJECT > INCOMPLETE
⚠️ INCOMPLETE پایین‌ترین است چون «نتوانستم بسنجم» ضعیف‌ترین ادعاست، نه بهترین.
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rqs2 as R                      # noqa: E402
from engine import scalp_engine as se             # noqa: E402

DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'results', '_audit_rename')

SEED = 20260806
PERM_K = 600            # ≥ PERM_K_MIN=500 تا H3 قابلِ داوری باشد (نه UNKNOWN)
N_TRIALS_FALLBACK = 2000  # محافظه‌کارانه: به نفعِ REJECT خطا می‌کند

VERDICT_RANK = {'ACCEPT': 5, 'POWER-LIMITED': 4, 'UNPROVEN': 3,
                'REJECT': 2, 'INCOMPLETE': 1}


# ═══════════════════════════════════════════════════════════════════════════
#  بارگذاریِ داده
# ═══════════════════════════════════════════════════════════════════════════
_CACHE: dict = {}


def load_card(pair: str, tf: str):
    """کارتِ (جفت‌ارز، تایم‌فریم) را از `data/` می‌خواند و کش می‌کند."""
    key = f'{pair}_{tf}'
    if key in _CACHE:
        return _CACHE[key]
    path = os.path.join(DATA, f'{key}.csv')
    if not os.path.exists(path):
        _CACHE[key] = None
        return None
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    ren = {}
    for want in ('open', 'high', 'low', 'close'):
        if want in cols:
            ren[cols[want]] = want
    for cand in ('time', 'datetime', 'date', 'timestamp'):
        if cand in cols:
            ren[cols[cand]] = 'dt'
            break
    df = df.rename(columns=ren)
    if 'dt' in df.columns:
        df['dt'] = pd.to_datetime(df['dt'], errors='coerce', format='mixed')
        df = df.dropna(subset=['dt']).reset_index(drop=True)
    _CACHE[key] = df
    return df


def bar_time_of(df):
    """محورِ زمان بر حسبِ ثانیهٔ اپاک — لازمِ پنجره‌بندیِ تقویمیِ H6 و افقِ H10."""
    if 'dt' not in df.columns:
        return None
    return (df['dt'].astype('int64') // 10 ** 9).to_numpy()


def atr(df, p=14):
    """ATR وایلدر، کاملاً causal."""
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.full(len(tr), np.nan)
    if len(tr) <= p:
        return out
    out[p - 1] = tr[:p].mean()
    a = 1.0 / p
    for i in range(p, len(tr)):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  مدلِ صفرِ کانونی — بازتولیدِ همان چیزی که اسپک §H3 می‌خواهد
# ═══════════════════════════════════════════════════════════════════════════
def build_null(df, asset, sl_pip, tp_pip, max_hold, side, n_sig,
               k=PERM_K, seed=SEED, stride=3):
    """
    دو خطِ مبنا که `H3`/`H4`/`H5` به آن نیاز دارند:

      ① **بی‌قید** — همان براکت روی *هر* کندل (با stride برای کارآمدی؛ چون قیدِ
         عدمِ هم‌پوشانی به‌هرحال بیشترِ ورودها را حذف می‌کند، stride اثرِ ناچیزی
         روی WRِ مبنا دارد ولی صریح گزارش می‌شود).
      ② **جای‌گشتِ زمانی** — همان تعدادِ سیگنال، در موقعیت‌های تصادفی. این خط
         `sd` را می‌دهد که مخرجِ `z` است. `k ≥ 500` اجباریِ v2.4 است وگرنه
         `perm_sd` همگرا نیست و `H3` می‌شود `UNKNOWN`.

    ⚠️ مبنا **ترکیبِ سمتِ لایه را حفظ می‌کند** (`side`)، چون هدیهٔ رانش برای
    long و short متفاوت است و مخلوط‌کردنشان سدِ مهارت را جابه‌جا می‌کند.
    """
    n = len(df)
    rng = np.random.default_rng(seed)
    lo, hi = 210, n - 2

    def wr_of(mask):
        ls = mask if side in ('long', 'both') else np.zeros(n, bool)
        ss = mask if side in ('short', 'both') else np.zeros(n, bool)
        tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset,
                                max_hold=max_hold, allow_overlap=False)
        if len(tr) < 10:
            return None, 0
        return 100.0 * float((tr['outcome'] == 'win').mean()), len(tr)

    m = np.zeros(n, bool)
    m[lo:hi:stride] = True
    uncond_wr, uncond_n = wr_of(m)

    n_sig = max(1, min(int(n_sig), hi - lo - 1))
    wrs = []
    for _ in range(k):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        mm = np.zeros(n, bool)
        mm[pos] = True
        w, cnt = wr_of(mm)
        if w is not None:
            wrs.append(w)
    if len(wrs) < 50:
        return None
    a = np.asarray(wrs, float)
    return {
        'uncond_wr': uncond_wr, 'uncond_n': uncond_n, 'stride': stride,
        'perm_mean': float(a.mean()), 'perm_sd': float(a.std(ddof=1)),
        'perm_max': float(a.max()), 'perm_k': int(len(a)),
        'side': side,
    }


def null_struct(nb, wr_obs):
    """
    ترجمهٔ مبناها به ساختارِ کانونیِ نولی که `compute_rqs2` می‌خواهد.
    `ref_wr` = بدترین (سخت‌ترین) مبنا، چون اسپک می‌گوید مهارت باید نسبت به
    **قوی‌ترین** توضیحِ بی‌مهارت سنجیده شود، نه ضعیف‌ترینش.
    """
    if nb is None:
        return None
    refs = [x for x in (nb['uncond_wr'], nb['perm_mean']) if x is not None]
    ref = max(refs) if refs else None
    if ref is None:
        return None
    sd = nb['perm_sd']
    lift = wr_obs - ref
    return {
        'ref_wr': ref, 'perm_mean': nb['perm_mean'], 'perm_sd': sd,
        'perm_max': nb['perm_max'], 'perm_k': nb['perm_k'],
        'uncond_wr': nb['uncond_wr'], 'lift': lift,
        'z': (lift / sd) if sd and sd > 0 else None,
    }
