# -*- coding: utf-8 -*-
"""
s436_filter_test.py — بندِ سومِ **قانونِ همپوشانی** برای نامزدِ `S214`
================================================================================

قانونِ پروژه صریح است و موکول‌کردنش را ممنوع کرده:

> «از درصدی از لایهٔ جدید که همپوشانی دارد، می‌شود به‌عنوانِ راهِ اولِ رسیدن
>  به هدف، یعنی بهبود، استفاده کرد … حتماً امکانِ استفاده از بخشِ همپوشان را
>  به‌عنوانِ فیلتر بررسی کن و بعد برو سراغِ مرحلهٔ بعد. این را به مراحلِ بعد
>  موکول نکن هرگز.»

── چرا این آزمون **معنا دارد** (و نه صرفاً تشریفات) ─────────────────────────
گامِ ۱۱۲ اندازه گرفت: نامزد ۲۴۰ روز دارد، لایهٔ زندهٔ `S355` ۴۵ روز، و
**۱۹ روز مشترک**. یعنی نامزد **۴۲.۲٪ از روزهای `S355`** را لمس می‌کند.
این عدد نه آن‌قدر کوچک است که آزمون بی‌معنا باشد، و نه آن‌قدر بزرگ که
فیلتر عملاً چیزی حذف نکند. پس آزمون **قدرتِ تفکیک** دارد.

── جهتِ فیلتر: **دو حالت، هر دو آزموده می‌شوند** ─────────────────────────────
یک فیلتر می‌تواند در دو جهت کار کند و **از قبل نمی‌دانم کدام**:

* `CONFIRM` — فقط معاملاتِ `S355` که نامزد هم آن روز فعال است نگه داشته شوند.
  (فرضیه: توافقِ دو لایه ⇒ سیگنالِ قوی‌تر)
* `VETO`    — فقط معاملاتِ `S355` که نامزد آن روز فعال **نیست** نگه داشته شوند.
  (فرضیه: نامزد نشانگرِ رژیمی است که `S355` در آن بد کار می‌کند)

⚠️ **هر دو گزارش می‌شوند، چه پاس شوند چه نشوند.** انتخابِ جهت **پس از** دیدنِ
نتیجه، خودش جست‌وجوی پنهان است — همان چیزی که در S435 گامِ ۹۵ مرزش را کشیدم.
هر دو جهت در `n_trials` شمرده می‌شوند (۱۹۲۸ → ۱۹۳۰).

── معیارِ موفقیت، **پیش‌ثبت‌شده در همین فایل، پیش از اجرا** ──────────────────
فیلتر فقط وقتی «مفید» است که **هر سه** شرط برقرار باشد:

1. `RQS2` نسخهٔ فیلترشده > `RQS2` نسخهٔ پایهٔ `S355`
2. `n` باقی‌مانده ≥ ۳۰ (وگرنه حکم صادر نمی‌شود — همان قیدِ ۲)
3. لیفت نسخهٔ فیلترشده > لیفت پایه (وگرنه فیلتر فقط نمونه را کوچک کرده)

شرطِ ۳ مهم‌ترین است: **فیلتری که فقط `n` را کم کند و لیفت را بالا نبرد،
تصادف است نه لبه.** با کوچک‌کردنِ نمونه، `perm_sd` باد می‌کند و `z` می‌افتد —
همان پویاییِ خودشکنی که در S434 گامِ ۶۶ اندازه گرفتم (پنجرهٔ کاربردیِ فیلتر
تقریباً ۱۰–۳۰٪ حذف است؛ اینجا حذف ۵۷.۸٪ است ⇒ **از قبل بدبینم**).

── محافظ‌ها ─────────────────────────────────────────────────────────────────
* مدلِ صفر برای هر نسخه **جداگانه** ساخته می‌شود، با **همان هندسهٔ `S355`**
  (`SL=TP=120`, `mh=96`) — نه هندسهٔ نامزد. `BUG-NULLUNCOND`.
* `perm_k = pa.size` — `BUG-PERMK`.
* پیکربندیِ `S355` از `s333.BEST_CFG` **خوانده** می‌شود — `BUG-CFGKEYS`.
* نامِ کارت با **زیرخط** (`XAUUSD_M5`) — تلهٔ گامِ ۱۱۱.
* اگر `S355` پایه صفر معامله بدهد ⇒ **شکستِ اندازه‌گیری**، نه «فیلترِ عالی».
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, os.path.join(ROOT, 'strategies'), os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2 import compute_rqs2                       # noqa: E402
import s333_s79_pullback_revival as s333                   # noqa: E402
# 🔴 گامِ ۱۱۹ — `BUG-LPSBIMPORT`: اول `CENTRAL` را از `s351_lpsb` وارد کردم
#    چون **حدس زدم** کنارِ `lpsb_signals` زندگی می‌کند. در واقع در ماژولِ
#    جداگانهٔ `s351_verdict` است، و `WARMUP` اصلاً ثابتِ ماژول نیست بلکه
#    مقداری است که خودم در `s436_coverage_m5.py` تعریف کردم.
#    ⇒ الگوی **دقیقاً یکسان** با ابزارِ پوششِ گامِ ۱۱۰ کپی می‌شود تا هر دو
#      ابزار *همان* لایهٔ `S355` را بسازند. اگر واردکردن‌ها واگرا شوند،
#      «پوشش» و «فیلتر» دو لایهٔ متفاوت را می‌سنجند بی‌آنکه خطایی رخ دهد.
from strategies.s351_lpsb import lpsb_signals              # noqa: E402
from strategies.s351_verdict import CENTRAL                # noqa: E402

WARMUP = 200                                                # مطابقِ گامِ ۱۱۰

import importlib.util                                       # noqa: E402
_spec = importlib.util.spec_from_file_location(
    'adj', os.path.join(HERE, 's436_adjudicate.py'))
adj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adj)

ASSET = 'XAUUSD'
OUT = 'results/_s436_filter'
SEED = 11

# 🔒 پیش‌ثبت — دو جهتِ فیلتر ⇒ ۲ آزمونِ جدید روی ۱۹۲۸
N_TRIALS = 1930
N_PERM = 500

S355_KEY = 'XAUUSD_M5'
S355_CFG = s333.BEST_CFG[S355_KEY]          # KeyError اگر غایب ⇒ خوب است


def s355_mask(df: pd.DataFrame) -> np.ndarray:
    """لایهٔ زندهٔ `S355` = `s333.build_layer(df, cfg) & (lpsb_state == -1)`."""
    base = s333.build_layer(df, S355_CFG)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    return np.asarray(base, bool) & (np.asarray(state) == -1)


def day_index(df: pd.DataFrame) -> np.ndarray:
    """🔴 گامِ ۱۲۱ — `BUG-DAYDTYPE`.

    نسخهٔ قبلی روزها را به‌صورت مجموعه‌ای از `pandas.Timestamp` نگه می‌داشت و
    سپس `np.isin(day_datetime64, list(timestamps))` می‌زد. `numpy` آن لیست را
    به آرایهٔ `object` تبدیل می‌کند و مقایسه با `datetime64[ns]` **هیچ‌گاه**
    تطبیق نمی‌دهد ⇒ `in_cand.sum() == 0` **بدونِ هیچ خطا یا هشداری**.

    پیامدِ دقیق: `CONFIRM = live & in_cand` تهی شد («no trades») و
    `VETO = live & ~in_cand` **کلِ** لایه را نگه داشت (n=47، دقیقاً برابرِ
    `BASE`). یعنی هر دو جهتِ فیلتر **جعلی** بودند: یکی هیچ‌چیز و دیگری
    همه‌چیز. بندِ سومِ قانونِ همپوشانی صوری اجرا می‌شد و پاسخش را یک باگ
    می‌داد — همان شکلِ خطای `BUG-DAYSET`/`BUG-BUNDLEPATH`: نتیجهٔ
    مطلوب‌نما بدونِ استثنا.

    درمان: همه‌جا روزها را به‌صورتِ **عددِ صحیحِ روزِ اپوک** (`int64`) نگه
    می‌داریم، پس هر دو طرفِ `np.isin` هم‌نوع‌اند و تطبیق ممکن است.
    """
    ns = df['dt'].dt.normalize().to_numpy().astype('datetime64[D]')
    return ns.astype('int64')


def days_of(df: pd.DataFrame, mask: np.ndarray) -> set:
    """مجموعهٔ روزهای فعالِ یک ماسک، به‌صورتِ `int` (روزِ اپوک)."""
    return set(int(x) for x in np.unique(day_index(df)[np.asarray(mask, bool)]))


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """مدلِ صفرِ اختصاصیِ همین نسخه با **هندسهٔ `S355`**."""
    n = len(df)
    z = np.zeros(n, bool)
    rng = np.random.default_rng(seed)
    valid = np.zeros(n, bool)
    valid[200:n - mh - 2] = True
    vidx = np.flatnonzero(valid)

    um = np.zeros(n, bool)
    um[vidx] = True
    tu = se.simulate_trades(df, um, z, sl, tp, ASSET, max_hold=mh,
                            allow_overlap=True)
    wr_unc = _wr(tu)

    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, ASSET, max_hold=mh,
                               allow_overlap=False)
        w = _wr(t)
        if w is not None:
            perm.append(w)
    pa = np.array(perm, float)
    return {
        'long': dict(uncond_wr=wr_unc,
                     perm_mean=float(pa.mean()) if pa.size else None,
                     perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                     perm_max=float(pa.max()) if pa.size else None,
                     perm_k=int(pa.size)),      # BUG-PERMK
        'short': {}}


def judge(df, mask, label, extra=None):
    sl, tp = float(S355_CFG['sl']), float(S355_CFG['tp'])
    mh = int(S355_CFG['mh'])
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, ASSET, max_hold=mh,
                            allow_overlap=False)
    if tr is None or len(tr) == 0:
        return {'variant': label, 'error': 'no trades'}
    if len(tr) < 30:
        return {'variant': label, 'error': f'n<30 (n={len(tr)})',
                'n_trades': int(len(tr))}

    null = null_for(df, mask, sl, tp, mh)
    split = int(len(df) * 0.70)
    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=split,
                       close=df['close'].to_numpy(), allow_overlap=False)
    m = res.get('metrics') or {}
    # 🔴 گامِ ۱۲۰ — `BUG-SCOREKEY`: اینجا `res.get('score')` نوشته بودم و
    #    موتور کلیدِ `rqs2_score` برمی‌گرداند ⇒ **`None` بی‌صدا**. همچنین
    #    `failed`/`unknown` کلیدِ موتور نیستند و از `gates` مشتق می‌شوند.
    #    ⚠️ چرا خطرناک بود: داورِ سه‌شرطی `(r['rqs2_score'] or 0) > (base or 0)`
    #    را می‌سنجد؛ با `None` هر دو صفر می‌شوند و شرطِ ۱ **همیشه False**.
    #    یعنی هر فیلتری، حتی یک فیلترِ عالی، «بی‌فایده» گزارش می‌شد.
    #    این بار جهتِ خطا **علیهِ** فرضیه‌ام بود — ولی همان‌قدر غلط است.
    g = res.get('gates') or {}
    return {
        'variant': label, 'card': 'XAUUSD-M5', 'geometry': dict(sl=sl, tp=tp, mh=mh),
        'n_trials': N_TRIALS, 'n_perm': N_PERM,
        'verdict': res.get('verdict'), 'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': sorted(k for k, v in g.items() if v is False),
        'unknown_gates': sorted(k for k, v in g.items() if v is None),
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share')},
        'null': null['long'], 'extra': extra or {},
    }


def main() -> int:
    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    df = adj.load_card('M5')
    print(f'[S436 فیلتر] XAUUSD-M5 · n_trials={N_TRIALS} · سد z≈3.89')

    live = s355_mask(df)
    cand = adj.build_arm_mask(df, 'B0')          # بهترین بازو = B0
    if int(live.sum()) == 0:
        print('  ⛔ شکستِ اندازه‌گیری: S355 صفر سیگنال')
        with open(os.path.join(ROOT, OUT, 'MEASUREMENT_FAILED.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'reason': 'live layer produced zero signals'}, f)
        return 2

    cd, ld = days_of(df, cand), days_of(df, live)
    inter = cd & ld
    print(f'  روزها: S355={len(ld)} · نامزد={len(cd)} · مشترک={len(inter)} '
          f'({100.0*len(inter)/max(1,len(ld)):.1f}% از S355)')

    day = df['dt'].dt.normalize().to_numpy()
    in_cand = np.isin(day, list(cd))

    variants = {
        'BASE':    live,
        'CONFIRM': live & in_cand,
        'VETO':    live & ~in_cand,
    }
    out = {}
    for lbl, m in variants.items():
        r = judge(df, m, lbl, extra={'n_signal_bars': int(m.sum())})
        out[lbl] = r
        p = os.path.join(ROOT, OUT, f'variant_{lbl}.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
        if r.get('error'):
            print(f'  ⛔ [{lbl}] {r["error"]}')
            continue
        mm = r['metrics']
        print(f'  ═══ [{lbl}] {r["verdict"]} · RQS2={r["rqs2_score"]}')
        print(f'      n={mm.get("n_trades")} WR={mm.get("win_rate")} '
              f'lift={mm.get("skill_lift_pp")} z={mm.get("skill_z")} '
              f'PF={mm.get("profit_factor")} net={mm.get("net_profit")}')

    # ── داوریِ سه‌شرطیِ پیش‌ثبت‌شده ─────────────────────────────────────
    base = out.get('BASE') or {}
    bm = base.get('metrics') or {}
    verdicts = {}
    for lbl in ('CONFIRM', 'VETO'):
        r = out.get(lbl) or {}
        if r.get('error'):
            verdicts[lbl] = {'useful': False, 'reason': r['error']}
            continue
        rm = r['metrics']
        c1 = (r.get('rqs2_score') or 0) > (base.get('rqs2_score') or 0)
        c2 = (rm.get('n_trades') or 0) >= 30
        c3 = (rm.get('skill_lift_pp') or -99) > (bm.get('skill_lift_pp') or -99)
        verdicts[lbl] = {'useful': bool(c1 and c2 and c3),
                         'cond1_rqs2_up': bool(c1),
                         'cond2_n_ge_30': bool(c2),
                         'cond3_lift_up': bool(c3)}
    with open(os.path.join(ROOT, OUT, 'filter_verdict.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'step': 118, 'base_rqs2': base.get('rqs2_score'),
                   'base_lift': bm.get('skill_lift_pp'),
                   'base_n': bm.get('n_trades'),
                   'verdicts': verdicts}, f, ensure_ascii=False, indent=1)
    print('\n  حکمِ فیلتر:', json.dumps(verdicts, ensure_ascii=False))
    print('\n[done]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
