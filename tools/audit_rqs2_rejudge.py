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
        # ⚠️ اصلاحِ صحت (باگی که در نسخهٔ اولِ همین فایل بود):
        # ستونِ `time` در کلِ `data/` **اپاکِ ثانیه**ای عددی است
        # (نمونه: `1294012800` = 2011-01-03). اگر با `format='mixed'`
        # به‌عنوان رشته تفسیر شود، pandas عددِ ۱۰-رقمی را تاریخِ بی‌معنا
        # می‌کند ⇒ محورِ زمان خراب ⇒ `H6` (پایداریِ تقویمی) و `H10`
        # (افقِ نگه‌داری) روی زمانِ جعلی داوری می‌شوند. این جنسِ خطا
        # ساکت است: هیچ استثنایی پرتاب نمی‌شود، فقط حکم غلط می‌شود.
        s = df['dt']
        if pd.api.types.is_numeric_dtype(s):
            unit = 's' if float(s.iloc[0]) < 1e11 else 'ms'
            df['dt'] = pd.to_datetime(s, unit=unit, errors='coerce')
        else:
            df['dt'] = pd.to_datetime(s, errors='coerce', format='mixed')
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


def canonical_null(df, asset, sl_pip, tp_pip, max_hold, sides,
                   n_sig_by_side, k=PERM_K, seed=SEED):
    """
    ساختارِ کانونیِ نول **به تفکیکِ سمت** — دقیقاً همان شکلی که
    `rqs2.blend_null` انتظار دارد:

        {'long':  {'uncond_wr','perm_mean','perm_sd','perm_max','perm_k'},
         'short': {...}}

    ⚠️ چرا per-side و نه یکجا (این یک اصلاحِ صحت است، نه سلیقه):
    `blend_null` مبنا را با **وزنِ تعدادِ معاملهٔ همان سمت** ترکیب می‌کند، چون
    هدیهٔ رانش برای long و short **قرینه** است: در داراییِ صعودی، لانگِ بی‌مهارت
    مبنای بالا و شورتِ بی‌مهارت مبنای پایین دارد. اگر یک مبنای مخلوط بدهم:
      · لایهٔ لانگ‌محور مبنای مصنوعاً **پایین** می‌گیرد ⇒ لیفتِ جعلیِ مثبت ⇒
        پذیرشِ کاذب. این دقیقاً همان باگی است که کلِ RQS+ را زمین زد (§۰ اسپک:
        «عددِ ۸۴.۲ تماماً رانشِ صعودیِ هفتگیِ طلا بود، نه مهارتِ سیگنال»).
    پس مبنای هر سمت با **همان سمت** ساخته می‌شود و ترکیب را خودِ موتور می‌کند.
    """
    out = {}
    for s in ('long', 'short'):
        if s not in sides or n_sig_by_side.get(s, 0) <= 0:
            out[s] = {}
            continue
        nb = build_null(df, asset, sl_pip, tp_pip, max_hold, s,
                        n_sig_by_side[s], k=k, seed=seed)
        if nb is None:
            out[s] = {}
            continue
        out[s] = dict(uncond_wr=nb['uncond_wr'], perm_mean=nb['perm_mean'],
                      perm_sd=nb['perm_sd'], perm_max=nb['perm_max'],
                      perm_k=nb['perm_k'])
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  داوریِ یک کارت
# ═══════════════════════════════════════════════════════════════════════════
def resolve_max_hold(max_hold, n_bars: int) -> int:
    """
    ترجمهٔ «بی‌سقف» به عددی که شبیه‌ساز می‌فهمد.

    چرا لازم است: بسیاری از لایه‌های آرشیو (از جمله S382) **هیچ سقفِ
    نگه‌داری ندارند** — معامله تا برخوردِ SL یا TP باز می‌ماند. اما امضای
    `se.simulate_trades` عددِ صحیح می‌خواهد و `None` استثنا می‌دهد.

    ⚠️ حساس‌ترین نکته: این تابع در **یک** نقطه صدا زده می‌شود و مقدارش هم به
    لایه و هم به مدلِ صفر داده می‌شود. اگر افقِ لایه و افقِ نول یکی نباشند،
    `H3` بی‌معنا می‌شود: WRِ لایه با براکتِ بی‌سقف و WRِ مبنا با براکتِ
    ۱۶-کندلی سنجیده می‌شود، و لیفتِ حاصل تفاوتِ **افق** است نه مهارت.
    این همان جنسِ ناهم‌ترازیِ مبناست که §۰ اسپک آن را قاتلِ RQS+ می‌نامد.
    """
    if max_hold is None:
        return int(n_bars) + 1          # عملاً بی‌سقف
    return int(max_hold)


def judge_card(pair, tf, long_sig, short_sig, sl_pip, tp_pip, max_hold,
               n_trials, k=PERM_K, seed=SEED, holdout_frac=0.30):
    """
    یک (لایه × کارت) را کاملاً می‌آزماید و حکمِ رسمیِ RQS2 را برمی‌گرداند.

    چهار ورودیِ اجباریِ اسپک که **هیچ‌کدام حدس زده نمی‌شوند**:
      · `tp_pip` صریح  ⇒ وگرنه `H2 = UNKNOWN` (اسپک §نقصِ ۳: RQS+ به‌غلط
        `tp = sl` فرض می‌کرد و سپرِ ضدِتقلبِ TP<SL خودبه‌خود خاموش می‌شد).
      · `null`         ⇒ وگرنه `H3/H4/H5 = UNKNOWN`.
      · `n_trials`     ⇒ وگرنه `H5 = UNKNOWN`.
      · `holdout`      ⇒ وگرنه `H7 = UNKNOWN`.
    نبودِ هرکدام ⇒ `INCOMPLETE`، **نه** ACCEPT. این خودِ سیاستِ اسپک است:
    «نبودِ آزمونِ کنترل، شاهدِ وجودِ مهارت نیست.»

    تقسیمِ holdout **تقویمی** است (۷۰٪ اولِ *زمان*، نه ۷۰٪ اولِ معاملات)، چون
    تقسیم بر تعدادِ معامله می‌تواند کلِ holdout را در یک بازهٔ کوتاهِ پرسیگنال
    بچپاند — همان نقصِ ۶ که اسپک برای `H6` رفعش کرد.
    """
    df = load_card(pair, tf)
    if df is None or len(df) < 500:
        return {'card': f'{pair}-{tf}', 'verdict': 'INCOMPLETE',
                'rqs2_score': 0.0, 'reason': 'no data / too short'}

    asset = pair
    if asset not in se.ASSETS:
        return {'card': f'{pair}-{tf}', 'verdict': 'INCOMPLETE',
                'rqs2_score': 0.0, 'reason': f'asset {asset} not in cost model'}

    ls = np.asarray(long_sig, bool)
    ss = np.asarray(short_sig, bool)
    # افق **یک‌بار** حل می‌شود و همین مقدار به نول هم می‌رود (هم‌ترازیِ مبنا)
    mh = resolve_max_hold(max_hold, len(df))
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return {'card': f'{pair}-{tf}', 'verdict': 'REJECT', 'rqs2_score': 0.0,
                'reason': 'zero trades', 'n_trades': 0}

    bt = bar_time_of(df)
    n_by_side = {s: int((tr['direction'] == s).sum()) for s in ('long', 'short')}
    sides = tuple(s for s in ('long', 'short') if n_by_side[s] > 0)
    n_sig_by_side = {'long': int(ls.sum()), 'short': int(ss.sum())}

    nul = canonical_null(df, asset, sl_pip, tp_pip, mh, sides,
                         n_sig_by_side, k=k, seed=seed)

    # holdout تقویمی: مرزِ زمانی روی (1-holdout_frac) از دهانهٔ داده
    split_bar = int(len(df) * (1.0 - holdout_frac))

    tp_arr = tp_pip if np.isscalar(tp_pip) else None
    r = R.compute_rqs2(
        tr, asset,
        sl_pip=(sl_pip if np.isscalar(sl_pip) else float(np.median(tr['sl_pip']))),
        tp_pip=(tp_arr if tp_arr is not None else None),
        bar_time=bt, null=nul, n_trials=n_trials,
        split_bar=split_bar, close=df['close'].to_numpy(float))
    r['card'] = f'{pair}-{tf}'
    r['n_signals'] = n_sig_by_side
    return r


def pick_headline(per_card: list) -> tuple:
    """
    از چند حکمِ کارتی، حکم و نمرهٔ **سرتیترِ** فایل را انتخاب می‌کند.

    قاعده: بهترین حکم روی *هر* کارت (ACCEPT>POWER-LIMITED>UNPROVEN>REJECT>
    INCOMPLETE)، و نمرهٔ همان کارت. منطقش: قانونِ MTF می‌گوید هر کارت منطقِ
    خودش را دارد، پس «لایه مرده است» فقط وقتی درست است که روی **هیچ** کارتی
    زنده نباشد (قانونِ مرگِ ابدی). اگر روی یک کارت زنده باشد، همان کارت
    شخصیتِ لایه را تعیین می‌کند.
    """
    if not per_card:
        return 'INCOMPLETE', 0.0
    best = max(per_card, key=lambda x: (VERDICT_RANK.get(x.get('verdict', 'INCOMPLETE'), 0),
                                        x.get('rqs2_score', 0.0)))
    return best.get('verdict', 'INCOMPLETE'), float(best.get('rqs2_score', 0.0))


def new_filename(old: str, tfs_tested: list, verdict: str, score: float) -> str:
    """
    نامِ نو طبقِ فرمتِ صریحِ User Note:
        استراتژی_جفت‌ارز_تایم‌فریم(ها)_rqs2_score_status.md
        مثال: S20_MovingAverage_Xauusd_M15M5H1_rqs2_80_UNPROVEN.md

    شمارهٔ لایه و نامِ توصیفی از نامِ قدیم **حفظ** می‌شوند (هویتِ تاریخیِ لایه
    نباید گم شود؛ ارجاعاتِ فراوانی در مستنداتِ پروژه به آنها هست). فقط دنبالهٔ
    «جفت‌ارز_تایم‌فریم_rqs2_نمره_حکم» بازنویسی می‌شود.
    """
    stem = old[:-3] if old.endswith('.md') else old
    m = re.match(r'^(S\d+[a-z]?)_(.+)$', stem)
    if not m:
        return old
    sid, rest = m.group(1), m.group(2)

    # حذفِ دنبالهٔ قدیم: هرچیزی از اولین نشانگرِ جفت‌ارز/عدد/حکم به بعد
    tokens = rest.split('_')
    keep = []
    stop = re.compile(r'^(?:[Xx]au|XAU|[Ee]ur|EUR|Xauusd|Eurusd|XauEur|XAUUSD|EURUSD|'
                      r'NetProfit|rqs2?|rqs|ALL|[MHDW]\d|\d+|ACCEPTED|REJECTED|DEAD|'
                      r'INVALIDATED|UNPROVEN|INCOMPLETE|PL|neg\d+|\+?\d+)', )
    for t in tokens:
        if stop.match(t):
            break
        keep.append(t)
    name = '_'.join(keep) if keep else rest.split('_')[0]

    pairs = sorted({t.split('-')[0] for t in tfs_tested}) if tfs_tested else []
    pair_tag = ''.join(p.capitalize() if len(p) > 4 else p for p in
                       [('Xauusd' if p == 'XAUUSD' else
                         'Eurusd' if p == 'EURUSD' else p.capitalize())
                        for p in pairs]) or 'NA'
    tf_tag = ''.join(t.split('-')[1] for t in tfs_tested) or 'NA'
    return f'{sid}_{name}_{pair_tag}_{tf_tag}_rqs2_{int(round(score))}_{verdict}.md'
