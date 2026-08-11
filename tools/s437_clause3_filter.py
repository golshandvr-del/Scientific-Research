# -*- coding: utf-8 -*-
"""
s437_clause3_filter.py — **بندِ سومِ قانونِ همپوشانی** برای نامزدِ `SoS`

┌──────────────────────────────────────────────────────────────────────────┐
│ چرا این ابزار **الان** ساخته می‌شود و نه بعد از حکم                       │
│                                                                          │
│ قانونِ پروژه صریح است: اگر لایهٔ نو با لایه‌های موجود همپوشانی داشت،      │
│ باید امکانِ استفاده از بخشِ همپوشان **به‌عنوانِ فیلتر** بررسی شود، و این  │
│ بررسی **هرگز** به مرحلهٔ بعد موکول نمی‌شود.                              │
│                                                                          │
│ نکتهٔ منطقیِ مهم: لایه‌ای که لبه‌اش صفر یا **منفی** است، هنوز می‌تواند    │
│ فیلترِ ارزشمندی باشد. لبهٔ منفی یعنی «این وضعیت پیش‌بینیِ بد می‌دهد» —    │
│ و اگر همان وضعیت روزهای بدِ یک لایهٔ زنده را هم نشان دهد، **وتو** کردنِ  │
│ آن روزها لایهٔ زنده را بهتر می‌کند. پس یک `REJECT` مستقل، بندِ سوم را    │
│ بی‌موضوع نمی‌کند؛ برعکس، جهتِ `VETO` را **محتمل‌تر** می‌کند.             │
└──────────────────────────────────────────────────────────────────────────┘

کارت: `XAUUSD-M5` — تنها کارتی که هم نامزد رویش داوری شده و هم لایهٔ
زنده دارد. (باندلِ زنده **هیچ** کارتِ یورویی ندارد ⇒ روی یورو موضوعی
برای فیلتر شدن وجود ندارد.)

لایهٔ زنده: `S355` = `s333.build_layer(df, cfg) & (lpsb_state == -1)`
— دقیقاً همان فرمولِ باندل، و **همان بلوکِ واردکردنی** که در `S436`
گامِ ۱۱۹ تثبیت شد (`BUG-LPSBIMPORT`).

دو جهتِ فیلتر، هر دو آزموده و هر دو گزارش می‌شوند:
  • `CONFIRM` — فقط معاملاتِ `S355` در روزهایی که نامزد **هم** فعال است
  • `VETO`    — فقط معاملاتِ `S355` در روزهایی که نامزد فعال **نیست**

انتخابِ جهت **پس از** دیدنِ نتیجه = جست‌وجوی پنهان. پس هر دو از پیش
تعریف و هر دو گزارش می‌شوند.

معیارِ موفقیت — **پیش از اجرا** قفل می‌شود، هر سه شرط لازم:
  ① `RQS2` بالاتر از پایهٔ `S355`
  ② نمونهٔ بازمانده ≥ ۳۰ معامله (قیدِ ۲)
  ③ **لیفت** بالاتر از لیفتِ پایه
شرطِ ③ حیاتی است: فیلتری که فقط `n` را کم کند و لیفت را بالا نبرد، چیزی
نیافته — فقط تصادفی معامله حذف کرده. و چون کوچک‌شدنِ نمونه انحرافِ
معیارِ جای‌گشت را باد می‌کند، `z` حتی با `WR` بهترْ افت می‌کند.
⚠️ و درسِ `S436` گامِ ۱۲۲: `PF` و `maxDD` **هر دو** می‌توانند با حذفِ
   چند برندهٔ کوچک و یک بازندهٔ بزرگ بهتر شوند بی‌آنکه لبه‌ای اضافه شود.
   ⇒ اشتباهِ رایجِ ۸ با لباسِ نسبت. تنها شرطِ ③ آن را می‌گیرد.

گاردها (همه با نامِ باگی که تولیدشان کرد):
  `BUG-DAYDTYPE`  — روزها **همه‌جا** `int64`ِ روزِ اپوک؛ هر دو طرفِ
                    `np.isin` هم‌نوع، و گاردِ افراز `C+V==BASE` صدادار.
  `BUG-NULLUNCOND`— نال با هندسهٔ **خودِ `S355`** ساخته می‌شود، نه هندسهٔ
                    نامزد. امتیازدهی به یک لایه با هندسهٔ دیگری = سنجشِ
                    تغییرِ هندسه به‌جای مهارتِ سیگنال.
  `BUG-PERMK`     — `perm_k = pa.size` (تعدادِ جای‌گشت)، نه اندازهٔ نمونه.
  `BUG-SCOREKEY`  — نگاشتِ خروجیِ موتور **عیناً** از `s437_adjudicate`.
  `BUG-ZBARNEST`  — سد از `res['metrics']['z_luck_bound']` خوانده می‌شود.
  `BUG-CFGKEYS`   — پیکربندیِ `S355` از `s333.BEST_CFG` **خوانده** می‌شود.
  گاردِ پایهٔ صفر — اگر `S355` صفر سیگنال داد، «شکستِ اندازه‌گیری» اعلام
                    می‌شود نه «فیلترِ عالی» (پایهٔ صفر هر فیلتری را
                    بی‌نهایت خوب نشان می‌دهد).

هزینهٔ چندگانگی: دو نسخه ⇒ `n_trials` از ۴۱۲ به ۴۱۴.
(هر دو زیرِ آستانهٔ ۵۶۷ ⇒ سد همچنان `H3=3.09` می‌ماند ⇒ رایگان.)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'strategies'), os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                        # noqa: E402
from engine.rqs2 import compute_rqs2                         # noqa: E402
import s333_s79_pullback_revival as s333                     # noqa: E402
# بلوکِ واردکردنیِ تثبیت‌شده در `S436` گامِ ۱۱۹ (`BUG-LPSBIMPORT`)
from strategies.s351_lpsb import lpsb_signals                # noqa: E402
from strategies.s351_verdict import CENTRAL                  # noqa: E402
import tools.s435_coverage_union as cov                      # noqa: E402
import tools.s437_adjudicate as adj                          # noqa: E402

WARMUP = 200
CARD = 'XAUUSD-M5'
CARD_KEY = 'XAUUSD_M5'
N_TRIALS = 414
N_PERM = 500
SEED = 20260811
OUT = os.path.join(ROOT, 'results', '_s437_clause3')


def s355_cfg():
    """`BUG-CFGKEYS` — پیکربندی **خوانده** می‌شود، رونویسی نمی‌شود."""
    best = getattr(s333, 'BEST_CFG', None)
    if not isinstance(best, dict):
        raise RuntimeError('s333.BEST_CFG یافت نشد')
    cfg = best.get(CARD_KEY) or best.get(CARD)
    if cfg is None:
        raise RuntimeError(f'کلیدِ {CARD_KEY}/{CARD} در BEST_CFG نیست: '
                           f'{sorted(best)[:8]}')
    return cfg


def s355_mask(df: pd.DataFrame) -> np.ndarray:
    cfg = s355_cfg()
    base = s333.build_layer(df, cfg)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    return np.asarray(base, bool) & (np.asarray(state) == -1)


def day_index(df: pd.DataFrame) -> np.ndarray:
    """`BUG-DAYDTYPE` — روزها به‌صورتِ `int64`ِ روزِ اپوک."""
    return df['dt'].dt.normalize().to_numpy().astype('datetime64[D]').astype('int64')


def days_of(df: pd.DataFrame, mask: np.ndarray) -> set:
    return set(int(x) for x in np.unique(day_index(df)[np.asarray(mask, bool)]))


def geom_of_s355():
    """هندسهٔ **خودِ `S355`** — `BUG-NULLUNCOND`.

    🔴 گامِ ۱۴۷ — `BUG-CFGKEYS` **دوباره**. کلیدها را `sl_pip`/`slPip`
    حدس زده بودم؛ کلیدهای واقعیِ `s333.BEST_CFG` کوتاه‌اند: `sl`/`tp`/`mh`.
    نسخهٔ باندل (`S333_CFG` در `app.bundle.mjs`) نامِ `slPip`/`tpPip` دارد،
    و من نامِ **باندل** را در ماژولِ **پایتون** جست‌وجو کردم.
    ⇒ همان الگو: مقدار از حافظه بازسازی شد، نه از منبع خوانده.
    خوش‌شانسی: `float(None)` استثنا داد. اگر ماژول تصادفاً `sl_pip`ِ
    دیگری داشت، هندسهٔ غلط **بی‌صدا** اجرا می‌شد — همان `BUG-GEOMDRIFT`.
    ⇒ حالا کلیدهای موجود بررسی و در صورتِ نبود، خطای **صریح** با فهرستِ
      کلیدهای واقعی پرتاب می‌شود تا حدسِ بعدی هم بی‌صدا نماند.
    """
    cfg = s355_cfg()
    miss = [k for k in ('sl', 'tp', 'mh') if cfg.get(k) is None]
    if miss:
        raise RuntimeError(f'کلیدهای {miss} در BEST_CFG نیستند. '
                           f'کلیدهای موجود: {sorted(cfg)}')
    return float(cfg['sl']), float(cfg['tp']), int(cfg['mh'])


def judge(df, mask, label, sl, tp, mh, extra=None):
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return {'variant': label, 'error': f'n<30 (n={0 if tr is None else len(tr)})'}

    # 🔴 گامِ ۱۴۸ — `BUG-NULLKEYS`. نسخهٔ نخست، دیکشنریِ نال را **از
    #    حافظه** ساخت: `{'ref_wr','sd','max','perm_k'}`. موتور کلیدهای
    #    `{'uncond_wr','perm_mean','perm_sd','perm_max','perm_k'}` می‌خواهد
    #    ⇒ سه کلید غلط و `uncond_wr` اصلاً غایب.
    #    پیامدِ **بی‌صدا**: موتور خطا نداد، ولی `null_ref_wr=None`،
    #    `skill_lift_pp=None`، `skill_z=None` و چهار دروازهٔ `H3/H4/H5/H6`
    #    **نامعلوم** ماندند. یعنی شرطِ ③ِ معیارِ من (لیفت↑) اصلاً
    #    قابلِ ارزیابی نبود و `None > None` آن را `False` گزارش کرد —
    #    دقیقاً فروپاشیِ `BUG-SCOREKEY`.
    #    ⇒ به‌جای تصحیحِ کلیدها، **تابعِ کارآمد** فراخوانی می‌شود تا
    #      امکانِ واگرایی حذف شود (همان درسِ `BUG-GEOMDRIFT`).
    #    🔴 گامِ ۱۵۲ — `BUG-NULLUNWRAP`. در گامِ ۱۴۸b تابعِ درست را صدا
    #    زدم ولی خروجی‌اش را **باز کردم**: `...['long']`. موتور نال را
    #    **به تفکیکِ سمت** می‌خواهد (`blend_null` در `engine/rqs2.py:812`
    #    روی `null.get('long')` و `null.get('short')` حلقه می‌زند تا
    #    مبنا را با سهمِ واقعیِ long/shortِ خودِ لایه وزن کند).
    #    با بازکردن، موتور `null['long']` را نیافت ⇒ `blend_null` مقدارِ
    #    `None` برگرداند ⇒ `skill_lift_pp` و `skill_z` هر دو `None`.
    #    ⇒ سه گامِ متوالی (۱۴۸b, ۱۵۰, ۱۵۱) روی یک نشانه تعمیر کردند و
    #      هر سه تعمیر **درست** بود؛ علت هر بار یک لایه عمیق‌تر رفت.
    #      درس: «تعمیرِ درستی که نشانه را برطرف نمی‌کند» یعنی علتِ دیگری
    #      هم هست — نه اینکه تعمیر اشتباه بوده.
    null = adj.null_for(df, np.asarray(mask, bool), sl, tp, mh, 'XAUUSD',
                        n_perm=N_PERM, seed=SEED)
    _pk = (null.get('long') or {}).get('perm_k', 0)
    if _pk < N_PERM:
        return {'variant': label, 'error': f'perm_k={_pk} < {N_PERM}'}

    split = int(len(df) * 0.70)
    # 🔴 گامِ ۱۵۰ — `BUG-CALLARGS`. نسخهٔ قبلی `bar_time` و
    #    `initial_capital` را **پاس نمی‌داد**. موتور خطا نداد؛ فقط
    #    `wr=None`، `null_ref_wr=None`، `skill_lift_pp=None`، `skill_z=None`
    #    برگرداند و `H3/H4/H5/H6` را **نامعلوم** گذاشت.
    #    نکتهٔ تشخیصی: در گامِ ۱۴۸b نال را تعمیر کردم و نال **درست شد**
    #    (`uncond_wr=48.854`, `perm_k=500`) ولی خروجی عوض نشد ⇒ نشانهٔ
    #    اینکه علت جای دیگری است. `wr=None` سرنخِ قطعی بود: نرخِ برد به
    #    نال ربطی ندارد، پس نقص باید در **ورودیِ** موتور باشد نه نال.
    #    الگوی ریشه‌ای، نهمین تکرار: نگاشتِ **خروجی** را کپی کردم ولی
    #    امضای **فراخوانی** را از حافظه بازسازی کردم. کپی‌کردنِ نیمی از
    #    یک واسط، محافظت نمی‌کند.
    #    ⇒ حالا دقیقاً همان فراخوانیِ `s437_adjudicate.py:240` است.
    res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=split,
                       initial_capital=10000.0, allow_overlap=False)
    # 🔴 گامِ ۱۵۱ — `BUG-GUARDKEY`. گاردی که در گامِ ۱۵۰ برای گرفتنِ
    #    `BUG-CALLARGS` ساختم، خودش کلیدِ **حدسی** `wr` را می‌خواند.
    #    موتور چنین کلیدی **ندارد**؛ نامِ واقعی `win_rate` است.
    #    ⇒ گارد همیشه `None` می‌دید و **همیشه** خطا می‌داد — حتی وقتی
    #      تعمیرِ گامِ ۱۵۰ **درست کار کرده بود**.
    #    ⚠️ خطرناک‌ترین شکلِ این خانواده: گاردی که برای گرفتنِ یک باگ
    #      ساخته شده، خودش قربانیِ همان باگ می‌شود و یک **نتیجهٔ منفیِ
    #      جعلی** می‌سازد. دقیقاً همان اتفاقی که در `BUG-ZBARNEST` افتاد.
    #    ⇒ حالا کلیدها از **فهرستِ واقعیِ خروجی** خوانده شده‌اند:
    #      ['breakeven_wr_cost','cost_pip','expectancy_pip', ... ,'win_rate', ...]
    _m = res.get('metrics') or {}
    _need = ('win_rate', 'skill_lift_pp', 'skill_z')
    _miss = [k for k in _need if _m.get(k) is None]
    if _miss:
        raise RuntimeError(f'{_miss} = None ⇒ موتور ورودی را نپذیرفت '
                           f'(BUG-CALLARGS). کلیدهای موجود: {sorted(_m)}')
    m = res.get('metrics') or {}
    g = res.get('gates') or {}
    return {
        'variant': label, 'card': CARD, 'geometry': dict(sl=sl, tp=tp, mh=mh),
        'n_trials': N_TRIALS, 'n_perm': N_PERM,
        'verdict': res.get('verdict'), 'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': sorted(k for k, v in g.items() if v is False),
        'unknown_gates': sorted(k for k, v in g.items() if v is None),
        'z_luck_bound': m.get('z_luck_bound'),                 # BUG-ZBARNEST
        'z_margin': m.get('z_margin'),
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'recovery_factor', 'skill_lift_pp', 'skill_z', 'null_ref_wr',
            'breakeven_wr_cost', 'rr', 'top_win_share',
            'z_luck_bound', 'z_margin', 'skill_p_perm', 'perm_k')},
        'null': null,
        'extra': extra,
    }


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    df, asset = adj.load_card(CARD)
    sl, tp, mh = geom_of_s355()

    # 🔴 گامِ ۱۴۹ — گاردِ `BUG-DATASETDRIFT` (کشفِ گامِ ۱۴۸c).
    #    دو ابزار در همین مخزن، کارتِ هم‌نامِ `XAUUSD-M5` را از **دو فایلِ
    #    متفاوت** می‌خواندند: `s436_adjudicate` از `data/XAUUSD_M5.csv`
    #    (۲۰۰٬۰۰۰ میله ≈ ۲.۸ سال) و `s437_adjudicate` از
    #    `data/mt5_full/XAUUSD_M5.csv.gz` (۱٬۰۸۹٬۵۷۴ میله ≈ ۱۵.۶ سال).
    #    هیچ‌چیز این واگرایی را اعلام نمی‌کرد؛ فقط وقتی دو عددی که
    #    **باید** توافق کنند (n=47 و n=160) توافق نکردند، دیده شد.
    #    ⇒ از این پس مسیرِ فایل، تعدادِ ردیف و بازهٔ تاریخ **بلند** چاپ
    #      می‌شوند تا خواننده هرگز پایهٔ ۱۵.۶ ساله را با ۲.۸ ساله اشتباه
    #      نگیرد. عددی که فقط در ذهنِ نویسنده «معلوم» است، مستند نیست.
    ds_rel = adj.CARDS[CARD][0]
    ds_span = (str(df['dt'].iloc[0])[:10], str(df['dt'].iloc[-1])[:10])
    ds_years = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    print(f'[S437 بندِ ۳] {CARD} · n_trials={N_TRIALS} · هندسهٔ S355 '
          f'SL={sl}/TP={tp}/mh={mh}')
    print(f'  دیتاست: {ds_rel} · ردیف={len(df):,} · '
          f'{ds_span[0]}→{ds_span[1]} ({ds_years:.1f} سال)')

    live = s355_mask(df)
    cand = cov.sos_edge(df)
    if int(live.sum()) == 0:
        print('  ⛔ شکستِ اندازه‌گیری: لایهٔ زنده صفر سیگنال داد')
        return 2

    ld, cd = days_of(df, live), days_of(df, cand)
    inter = ld & cd
    print(f'  روزها: S355={len(ld)} · نامزد={len(cd)} · مشترک={len(inter)} '
          f'({100.0*len(inter)/max(1,len(ld)):.1f}% از S355)')

    in_cand = np.isin(day_index(df),
                      np.fromiter(cd, dtype='int64', count=len(cd)))
    variants = {'BASE': live, 'CONFIRM': live & in_cand, 'VETO': live & ~in_cand}

    # گاردِ افرازِ صدادار (`BUG-DAYDTYPE`، گامِ ۱۲۱)
    nb = int(live.sum()); nc = int(variants['CONFIRM'].sum())
    nv = int(variants['VETO'].sum())
    if nc + nv != nb:
        print(f'  ⛔ گاردِ افراز شکست: {nc}+{nv} != {nb}')
        return 3
    if len(inter) > 0 and nc == 0:
        print(f'  ⛔ گاردِ dtype شکست: {len(inter)} روزِ مشترک ولی ۰ میله')
        return 3
    print(f'  ✅ گاردِ افراز: {nb} = CONFIRM {nc} + VETO {nv}')

    out = {}
    for lbl, m in variants.items():
        r = judge(df, m, lbl, sl, tp, mh, extra={'n_signal_bars': int(m.sum())})
        out[lbl] = r
        with open(os.path.join(OUT, f'variant_{lbl}.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
        if r.get('error'):
            print(f'  ⛔ [{lbl}] {r["error"]}')
        else:
            mm = r['metrics']
            print(f'  [{lbl}] n={mm["n_trades"]} WR={mm["win_rate"]} '
                  f'lift={mm["skill_lift_pp"]} z={mm["skill_z"]} '
                  f'PF={mm["profit_factor"]} net=${mm["net_profit"]} '
                  f'RQS2={r["rqs2_score"]}')

    base = out.get('BASE') or {}
    bq = (base.get('rqs2_score') or 0)
    bl = ((base.get('metrics') or {}).get('skill_lift_pp') or 0)
    verdicts = {}
    for lbl in ('CONFIRM', 'VETO'):
        r = out.get(lbl) or {}
        if r.get('error'):
            verdicts[lbl] = {'useful': False, 'reason': r['error']}
            continue
        mm = r['metrics']
        c1 = (r.get('rqs2_score') or 0) > bq
        c2 = (mm.get('n_trades') or 0) >= 30
        c3 = (mm.get('skill_lift_pp') or 0) > bl
        verdicts[lbl] = {'useful': bool(c1 and c2 and c3),
                         'cond1_rqs2_up': bool(c1), 'cond2_n_ok': bool(c2),
                         'cond3_lift_up': bool(c3)}
    summary = {'card': CARD, 'live_days': len(ld), 'cand_days': len(cd),
               'overlap_days': len(inter),
               'overlap_pct_of_live': round(100.0*len(inter)/max(1, len(ld)), 2),
               'partition': {'base_bars': nb, 'confirm_bars': nc, 'veto_bars': nv},
               'verdicts': verdicts}
    with open(os.path.join(OUT, 'clause3_summary.json'), 'w',
              encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print('  حکمِ فیلتر:', json.dumps(verdicts, ensure_ascii=False))
    print('\n[done]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
