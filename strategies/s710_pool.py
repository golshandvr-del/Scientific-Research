# -*- coding: utf-8 -*-
"""
S710-POOL — استخرِ نجاتِ پیش‌ثبت‌شده برای کارت‌های هم‌جهتِ خانوادهٔ S710
==========================================================================
مجوز: بندِ ۳ پیش‌ثبتِ S710 (commit 6ce8e14b): «اگر کارتی POWER-LIMITED شد،
تنها مسیرِ نجاتِ مجاز، استخرِ رسمیِ rqs2_pool.pool_cards روی اعضای خانوادهٔ
همین پیش‌ثبت است — نه هیچ فیلتر یا پارامترِ تازه.»

اعضای نامزد: همهٔ ۵ کارتِ خانواده {M1,M5,M15,M30,H1} — pool_cards خودش
هم‌جهتی (lift>0) و همگنی (ضدِ رقیق‌شدن، درسِ S351) را قضاوت می‌کند؛ من
دستی هیچ کارتی را حذف یا اضافه نمی‌کنم. کارت‌های اطلاعاتی H4/D1 طبق
پیش‌ثبت **بیرون** از استخرند.

مدلِ صفرِ استخر: ترکیبِ وزنیِ نول‌های اندازه‌گیری‌شدهٔ اعضا با وزنِ سهمِ
پس-از-FIFO — همان `blend_pool_null` مسیرِ اثبات‌شدهٔ S431.

n_trials: 7 (خانواده) + 1 (خودِ آزمونِ استخر) = 8 — صادقانه.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2                                            # noqa: E402
from engine.rqs2_pool import pool_cards                            # noqa: E402
from tools import s434_fast_data as fd                             # noqa: E402
from strategies.s431_lpsb_multicard_pool import blend_pool_null    # noqa: E402

# درسِ S431 — سه باگِ مستندِ محور: BUG-QUANT (محورِ درشت ⇒ برخوردِ
# کاذبِ concurrency)، BUG-SPAN (محورِ فایلِ کوتاه ⇒ کلیپ به صفر)، و
# bar_time=t_entry (طولِ غلط). اصلاحِ اثبات‌شده: شبکهٔ مصنوعیِ ۵دقیقه‌ای
# روی افقِ کاملِ استخر + بازنویسیِ entry/exit_bar روی آن.

ASSET = 'XAUUSD'
FAMILY = ['M1', 'M5', 'M15', 'M30', 'H1']
OUT = 'results/_scan_S710'
N_TRIALS_POOL = 8         # ۷ کارتِ خانواده/اطلاعاتی + ۱ آزمونِ استخر
SPLIT_FRAC = 0.70


def load_member(tf):
    p = f'{OUT}/{tf}.json'
    if not os.path.exists(p):
        print(f'  [skip] {tf}: json missing')
        return None
    d = json.load(open(p))
    trp = f'{OUT}/{tf}_trades.csv'
    tr = pd.read_csv(trp)
    # lift نسبت به مبنای بی‌قیدِ وزنی — همان تعریفِ S431
    wr = d['wr']
    refs, wts = [], []
    for side, cnt in (('long', d['n_long']), ('short', d['n_short'])):
        u = d['null'][side].get('uncond_wr')
        if u is not None and cnt > 0:
            refs.append(float(u) * cnt)
            wts.append(cnt)
    ref = (sum(refs) / sum(wts)) if wts else None
    lift = (wr - ref) if ref is not None else None
    # محورِ زمان برای نگاشتِ تقویمی
    # ⚠️ BUG-EPOCH (کشفِ همین اجرا): `time` در fast-cache **ثانیهٔ یونیکس**
    # است؛ `astype('datetime64[ns]')` آن ثانیه‌ها را نانوثانیه می‌پندارد و
    # کلِ استخر به ژانویهٔ ۱۹۷۰ فرومی‌رود (محور=۴ سطل!). تبدیلِ درست:
    # اول [s] بعد [ns].
    dd = fd.load_fast(ASSET, tf)
    dt = dd['time'].astype('datetime64[s]').astype('datetime64[ns]')
    print(f'  {tf}: n={len(tr)} wr={wr:.2f}% ref={ref} lift='
          f'{None if lift is None else round(lift, 2)}')
    return dict(card=tf, tr=tr, dt=dt, lift=lift, n=len(tr),
                null=d['null'],
                sl_pip=d['sl_pip_med'], tp_pip=d['tp_pip_med'])


def main():
    print('S710-POOL — loading family members …')
    members = [m for m in (load_member(tf) for tf in FAMILY) if m]

    res_pool = pool_cards(members)
    if res_pool is None:
        print('هیچ عضوِ هم‌جهتی نماند — استخر ممکن نیست. حکم: کارت‌ها همان‌طور می‌مانند.')
        return
    pool = res_pool['pool']
    used = res_pool['used']
    print(f"\nused={[u['card'] for u in used]}  "
          f"dropped={[(x['card'], x['reason']) for x in res_pool['dropped']]}")
    print(f"n_before={res_pool['n_before']}  n_after_fifo={res_pool['n_after']}")

    members_used = [m for m in members
                    if m['card'] in {u['card'] for u in used}]
    null_pool = blend_pool_null(members_used, pool)

    # هندسهٔ میانه با وزنِ سهمِ پس-از-FIFO (همان S431)
    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by_card = {m['card']: m for m in members_used}
    sl_med = sum(by_card[c]['sl_pip'] * w for c, w in shares.items()
                 if c in by_card)
    tp_med = sum(by_card[c]['tp_pip'] * w for c, w in shares.items()
                 if c in by_card)

    # ---- محورِ مشترکِ مصنوعیِ ۵دقیقه‌ای (راهِ اثبات‌شدهٔ S431) ----
    STEP_NS = 5 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f'[axis] 5-min grid · {axis_dt[0]} → {axis_dt[-1]} · '
          f'{len(axis_t):,} buckets')

    # close هم‌راستا برای H10 — از H1 (کلِ افق را دارد)، بدون قیمتِ آینده
    dref = fd.load_fast(ASSET, 'H1')
    ref_t = dref['time'].astype('datetime64[s]').astype(
        'datetime64[ns]').astype(np.int64)
    ref_c = dref['close'].astype(np.float64)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_entry'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_exit'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # split: صدکِ ۷۰٪ِ زمانِ ورودِ معاملات (نه تقویم — درسِ BUG-SPLITDIR)
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout_mask = te_all >= split_ns
    print(f'[split {SPLIT_FRAC:.0%}] boundary={np.datetime64(split_ns, "ns")} '
          f'· explore={int((~holdout_mask).sum())} '
          f'· holdout={int(holdout_mask.sum())}')

    r = rqs2.compute_rqs2(pool, ASSET, sl_pip=float(sl_med),
                          tp_pip=float(tp_med), bar_time=axis_dt,
                          close=axis_close,
                          null=null_pool, n_trials=N_TRIALS_POOL,
                          holdout_mask=holdout_mask,
                          allow_overlap=False)
    print('')
    print(rqs2.format_rqs2('S710_CompExp_POOL', r))

    payload = dict(used=used, dropped=res_pool['dropped'],
                   n_before=res_pool['n_before'], n_after=res_pool['n_after'],
                   sl_pip_med=float(sl_med), tp_pip_med=float(tp_med),
                   n_trials=N_TRIALS_POOL, rqs2=r, null_pool=null_pool)
    with open(f'{OUT}/POOL.json', 'w') as f:
        json.dump(payload, f, ensure_ascii=False, default=str, indent=1)
    pool.to_csv(f'{OUT}/POOL_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/POOL.json')


if __name__ == '__main__':
    main()
