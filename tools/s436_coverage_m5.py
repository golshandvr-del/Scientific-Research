# -*- coding: utf-8 -*-
"""
s436_coverage_m5.py — سنجشِ پوششِ نامزدِ `S214` در برابرِ اجتماعِ **زندهٔ
امروزِ** کارتِ `XAUUSD-M5`.

پرسشِ مرکزی
-----------
ماژولِ `s214b` (خطِ ۹) نوشته: نسخهٔ **بدونِ قابِ تقویمیِ** `S214` روی `M5`
خام ‎+$۳٬۱۵۳‎ می‌ساخت ولی **۶۳.۸٪ همپوشانی** داشت ⇒ سهمِ مستقل ‎+$۲۳۷‎ ⇒ رد.

آن اجتماع از پنج لایهٔ تقویمی ساخته شده بود: `S142` · `S140` · `S139` ·
`S141` · `S144`. در گامِ ۱۰۹ از رجیستریِ `local-mobile/app.bundle.mjs`
خواندم که **هیچ‌کدام** امروز روی `M5` زنده نیستند و تنها لایهٔ زندهٔ این
کارت `S355` است.

پس مثلِ `S435`، اجتماع باید **از نو** ساخته شود.

⚠️ چهار محافظ که عمداً به **زیانِ** فرضیهٔ خودم گذاشته‌ام
---------------------------------------------------------
۱. **واحد = روزِ تقویمی، عیناً مثلِ `S214`.** اگر واحد را عوض کنم، بهبودِ
   ظاهری ممکن است صرفاً اثرِ تغییرِ واحد باشد نه تغییرِ پرتفوی. عددِ نو باید
   با ۶۳.۸٪ **قابلِ مقایسه** بماند.

۲. **بدهیِ بازِ `S355` (گامِ ۱۰۹).** خودِ باندل هشدار می‌دهد برچسبِ کارتِ
   `S355` مشکوک است: دفترِ ممیزیِ `S396` می‌گوید `H1 · n=1298`، سندِ خودِ
   لایه می‌گوید `M5 · n=47`. **به هیچ‌کدام اعتماد نمی‌کنم** — الگویِ شلیک را
   از پیکربندیِ commit‌شده **محاسبه** می‌کنم و `n` واقعی را گزارش می‌دهم.
   اگر `n` بزرگ درآید، اجتماع ۲۷× بزرگ‌تر است و تخمینِ من به‌شدت خوش‌بینانه
   بوده.

۳. **کفِ محافظه‌کارانه.** اگر `S355` به هر دلیلی صفر سیگنال بدهد، این را
   **شکستِ اندازه‌گیری** اعلام می‌کنم نه «پوششِ صفر». دقیقاً `BUG-DAYSET` و
   `BUG-BUNDLEPATH` همین‌طور بی‌صدا جوابِ دلخواهِ من را دادند.

۴. **پنجرهٔ زمانیِ مشترک.** پوشش فقط روی بازه‌ای سنجیده می‌شود که هر دو طرف
   داده دارند.

اجرا:
    cd /home/user/webapp && PYTHONPATH=. python3 tools/s436_coverage_m5.py
"""
from __future__ import annotations

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as se                       # noqa: E402
from strategies import s333_s79_pullback_revival as s333    # noqa: E402
from strategies.s351_lpsb import lpsb_signals               # noqa: E402
from strategies.s351_verdict import CENTRAL                 # noqa: E402
import s214b_late_entry_as_filter as B                      # noqa: E402

OUT = 'results/_s436_coverage'
CARD = 'XAUUSD-M5'
ASSET = 'XAUUSD'
DATA = 'data/XAUUSD_M5.csv'
WARMUP = 200

# ── نامزد: پیکربندیِ ارثیِ `S214` (خوانده‌شده از
#    `strategies/s214c_final_independent_layer.py`، حدس‌زده نشده) ──────────
CAND = {
    'ef': 20, 'es': 50, 'n_run': 4, 'br': 0.5, 'clx': 1.5, 'look': 12,
    'sl': 150.0, 'tp': 300.0, 'max_hold': 96,
    'night_hours': [19, 20, 21, 22, 23],   # ساعاتِ کنارگذاشته‌شده در S214
}

# ── اجتماعِ زندهٔ M5 — S355 = S333(M5) & (LPSB_state == -1) ───────────────
#
# 🔴 گامِ ۱۱۱ — `BUG-CFGKEYS`: اینجا اول پیکربندی را **بازنویسی** کرده بودم
#    (`ema_fast=20, ema_slow=100, …`) چون از باندلِ جاوااسکریپت خوانده بودمش.
#    ولی ماژولِ پایتون کلیدهای `ef/es/rp/rth/hurst/er` می‌خواهد ⇒ `KeyError`.
#    **کرش نجاتم داد**: اگر `build_layer` به‌جای کرش مقدارِ پیش‌فرض
#    برمی‌گرداند، اتحادیهٔ غلطی می‌ساخت و پوشش را **به نفعِ من** پایین
#    می‌آورد، بی‌صدا. همان الگویِ «موفقیتِ خاموش» برای بارِ هشتم.
#
#    ⇒ رفع: پیکربندی از **منبعِ commit‌شده** خوانده می‌شود، بازنویسی نمی‌شود.
#    ⚠️ نامِ کارت در `BEST_CFG` با **زیرخط** است (`XAUUSD_M5`)، نه خط‌تیره.
#    `BEST_CFG.get('XAUUSD-M5')` بی‌صدا `None` می‌دهد — تلهٔ دوم در یک خط.
S355_CARD_KEY = 'XAUUSD_M5'
S355_CFG = s333.BEST_CFG[S355_CARD_KEY]      # KeyError اگر غایب باشد ⇒ خوب


def load_m5() -> pd.DataFrame:
    df = se.load_data(os.path.join(ROOT, DATA))
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df


def days_of(df: pd.DataFrame, mask: np.ndarray) -> set:
    """مجموعهٔ **روزهای تقویمی** که ماسک در آن‌ها دستِ‌کم یک بار True است.

    واحد عمداً «روز» است تا با عددِ تاریخیِ ۶۳.۸٪ِ `S214` هم‌جنس بماند
    (محافظِ ۱ در docstring).
    """
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return set()
    return set(pd.to_datetime(df['dt'].to_numpy()[idx]).normalize())


def candidate_mask(df: pd.DataFrame) -> np.ndarray:
    """بازوی `A1`: فیلترِ مومنتومِ فصلِ ۱۱ **بدونِ قابِ تقویمی**.

    ساعتِ شب همان‌طور که `S214` داشت کنار گذاشته می‌شود — چون آن قید بخشی از
    **تعریفِ لایه** است نه قابِ تقویمی، و برداشتنش یعنی لایهٔ دیگری.
    """
    m = B.late_entry_state_mask(df, CAND['ef'], CAND['es'], CAND['n_run'],
                                CAND['br'], CAND['clx'], CAND['look'])
    hour = df['dt'].dt.hour.to_numpy()
    return m & ~np.isin(hour, CAND['night_hours'])


def s355_mask(df: pd.DataFrame) -> np.ndarray:
    """بازتولیدِ لایهٔ زندهٔ `S355` روی `M5` — دقیقاً فرمولِ باندل:
        `s333.build_layer(df, cfg) & (lpsb_state == -1)`
    """
    base = s333.build_layer(df, S355_CFG)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    return np.asarray(base, bool) & (np.asarray(state) == -1)


def main() -> int:
    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    df = load_m5()
    print(f'[S436 پوشش] {CARD} · {len(df)} کندل · '
          f'{df["dt"].iloc[0].date()} → {df["dt"].iloc[-1].date()}')

    cand = candidate_mask(df)
    print(f'  نامزد (A1, بدونِ قابِ تقویمی): {int(cand.sum())} کندلِ سیگنال')

    live = s355_mask(df)
    n_live = int(live.sum())
    print(f'  S355 زنده: {n_live} کندلِ سیگنال')

    # محافظِ ۳ — صفرِ خاموش ممنوع
    if n_live == 0:
        print('  ⛔ S355 صفر سیگنال داد ⇒ شکستِ اندازه‌گیری، نه پوششِ صفر.')
        with open(os.path.join(ROOT, OUT, 'MEASUREMENT_FAILED.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'failed': True,
                       'reason': 'live union produced zero signals; a zero '
                                 'union would report 100% novelty, which is '
                                 'exactly the answer my hypothesis wants'},
                      f, ensure_ascii=False, indent=1)
        return 2

    # معاملاتِ واقعی (نه کندلِ سیگنال) ⇒ روزهای واقعیِ مواجهه
    z = np.zeros(len(df), bool)
    tr_c = se.simulate_trades(df, cand, z, CAND['sl'], CAND['tp'], ASSET,
                              max_hold=CAND['max_hold'], allow_overlap=False)
    tr_l = se.simulate_trades(df, live, z, float(S355_CFG['sl']),
                              float(S355_CFG['tp']), ASSET,
                              max_hold=int(S355_CFG['mh']),
                              allow_overlap=False)
    print(f'  معاملات: نامزد={0 if tr_c is None else len(tr_c)} · '
          f'S355={0 if tr_l is None else len(tr_l)}')

    def trade_days(df_, tr):
        if tr is None or len(tr) == 0:
            return set()
        eb = tr['entry_bar'].values
        return set(pd.to_datetime(df_['dt'].to_numpy()[eb]).normalize())

    d_cand = trade_days(df, tr_c)
    d_live = trade_days(df, tr_l)

    # محافظِ ۴ — پنجرهٔ مشترک
    if d_cand and d_live:
        lo = max(min(d_cand), min(d_live))
        hi = min(max(d_cand), max(d_live))
        d_cand_w = {d for d in d_cand if lo <= d <= hi}
        d_live_w = {d for d in d_live if lo <= d <= hi}
    else:
        lo = hi = None
        d_cand_w, d_live_w = d_cand, d_live

    inter = d_cand_w & d_live_w
    cov = 100.0 * len(inter) / max(1, len(d_cand_w))

    out = {
        'step': 110,
        'card': CARD,
        'candidate_signal_bars': int(cand.sum()),
        'live_signal_bars': n_live,
        'candidate_trades': 0 if tr_c is None else int(len(tr_c)),
        'live_trades': 0 if tr_l is None else int(len(tr_l)),
        'common_window': [str(lo), str(hi)],
        'candidate_days': len(d_cand_w),
        'live_union_days': len(d_live_w),
        'overlapping_days': len(inter),
        'coverage_pct': round(cov, 2),
        'historical_coverage_pct': 63.8,
        'novel_days': len(d_cand_w) - len(inter),
    }
    with open(os.path.join(ROOT, OUT, 'coverage.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f'\n  ═══ پوشش = {cov:.2f}%  (تاریخی: ۶۳.۸٪)')
    print(f'      روزهای نامزد={len(d_cand_w)} · اجتماع={len(d_live_w)} · '
          f'مشترک={len(inter)} · نو={len(d_cand_w) - len(inter)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
