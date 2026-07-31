# -*- coding: utf-8 -*-
"""S346 — **مرحلهٔ دومِ پروتکل C**: تستِ یک‌بارهٔ پیکربندیِ قفل‌شده روی نیمهٔ دومِ
دست‌نخورده، زیرِ معیارِ RQS2 v2.4.

جایگاهِ این اسکریپت در زنجیره
-----------------------------
`strategies/s346_holdout_c.py` مرحلهٔ **کشف** را اجرا کرد: شبکهٔ ۳۶-نقطه‌ای را
**فقط روی ۶۰٪ اولِ** `XAUUSD_D1` جاروب کرد، پیکربندیِ برنده را در
`results/_scan_S346/holdout_c_XAUUSD-D1.json` قفل کرد و آن فایل در commit
`fe91bc0` **پیش‌ثبت** شد — پیش از آنکه نیمهٔ دوم هرگز ارزیابی شود. مُهرِ زمانیِ
git همان مدرکِ قابلِ راستی‌آزمایی است که تست از قفل تبعیت می‌کند، نه برعکس.

این اسکریپت مرحلهٔ **تست** است و طبقِ قانونِ ۳ پروتکل C، نیمهٔ دوم را **یک بار**
لمس می‌کند. هیچ پارامتری اینجا جست‌وجو نمی‌شود؛ همهٔ اعداد از فایلِ قفل خوانده
می‌شوند (`er_thr`, `cg_thr`, `std_thr` به‌صورتِ **مقادیرِ مطلق**، نه چارک — چون
چارک‌ها روی نیمهٔ اول به عدد تبدیل شده‌اند و بازمحاسبهٔ چارک روی نیمهٔ دوم خودش
یک نشتِ اطلاعاتی بود).

سه نکتهٔ روش‌شناختی
-------------------
۱) **محاسبهٔ اندیکاتور روی کلِ سری، ارزیابیِ سیگنال فقط در ناحیهٔ holdout.**
   اندیکاتورهای این لایه (`cg_fib_13`, `std_fib_55`, ATR کانال) همه **علّی**
   (backward-looking) هستند، پس محاسبه روی کلِ df هیچ نگاهِ آینده‌ای ایجاد
   نمی‌کند؛ در عوض از تلفِ warm-up در ابتدای نیمهٔ دوم جلوگیری می‌کند. ورودها با
   ماسک به `entry_bar >= split` محدود می‌شوند.

۲) **H7 در معیار به یک تقسیمِ کشف/خارج‌ازنمونه نیاز دارد** وگرنه UNKNOWN می‌دهد و
   حکم INCOMPLETE می‌شود. راهِ صادقانه: یک تقسیمِ **تودرتوی** ۶۰/۴۰ *درونِ خودِ*
   holdout. این معیار را **سخت‌تر** می‌کند نه آسان‌تر (لایه باید در آخرین ۴۰٪ از
   آخرین ۴۰٪ هم دوام بیاورد).

۳) **`n_trials = 1`** — روی دادهٔ هرگز-دیده‌نشده تعدادِ فرضیهٔ واقعی یک است؛ این
   دقیقاً همان چیزی است که §۶.۲ حسابرسی به‌عنوانِ صرفهٔ آماریِ مسیر C توضیح داد
   (سدِ ۱.۶۴۵σ به‌جای ~۳.۹σ). نول با `K=500` ساخته می‌شود تا کفِ همگراییِ v2.4
   برآورده شود.

اجرا:  PYTHONPATH=. python3 strategies/s346_holdout_c_test.py
خروجی: results/_scan_S346/holdout_c_TEST_XAUUSD-D1.json
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from engine import rqs2 as R2
from strategies.s346_holdout_c import (
    build_signal, net_of, build_null_perm,
    BASE, CARD, PATH, ASSET, OUT,
)

LOCK_FILE = f'{OUT}/holdout_c_XAUUSD-D1.json'
TEST_FILE = f'{OUT}/holdout_c_TEST_XAUUSD-D1.json'


def main():
    print('=' * 78)
    print('S346 protocol-C  ·  STAGE 2 = ONE-SHOT HOLDOUT TEST  ·  RQS2 v2.4')
    print('=' * 78)

    if not os.path.exists(LOCK_FILE):
        print(f'ABORT: locked pre-registration file missing: {LOCK_FILE}')
        return
    lock = json.load(open(LOCK_FILE))
    L = lock['locked']
    print(f"locked (pre-registered) config : er_thr={L['er']}  "
          f"cg_fib_13>={L['cg_thr']:.6f}  std_fib_55<={L['std_thr']:.4f}")
    print(f"discovery half (first 60%)     : WR={L['is_wr']}%  n={L['is_n']}  "
          f"net={L['is_net']}  (grid N={lock['discovery_grid_N']})")

    df = se.load_data(PATH)
    N = len(df)
    split = int(N * 0.60)
    print(f'bars total={N}  discovery=[0,{split})  HOLDOUT=[{split},{N})')

    # --- سیگنال با پیکربندیِ قفل‌شده، اندیکاتورها علّی روی کلِ سری ---
    ls, ss, sl_pip, tp_pip = build_signal(df, L['er'], L['cg_thr'], L['std_thr'])

    # --- ورودها فقط در ناحیهٔ holdout ---
    keep = np.zeros(N, bool)
    keep[split:] = True
    ls_h = ls & keep
    ss_h = ss & keep
    n_sig = int((ls_h | ss_h).sum())
    print(f'holdout signals: long={int(ls_h.sum())} short={int(ss_h.sum())} '
          f'total={n_sig}')

    tr, wr, n = net_of(df, ls_h, ss_h, sl_pip, tp_pip)
    if tr is None or n == 0:
        print('ABORT: locked config produced no trades on the holdout half')
        return
    print(f'holdout trades : n={n}  WR={wr:.2f}%  net_pip={tr["pnl_pip"].sum():.1f}')

    # --- نولِ جای‌گشت با K=500 (کفِ همگراییِ v2.4) ---
    null = build_null_perm(df, ls_h, ss_h, sl_pip, tp_pip, K=500, seed=12345)
    if null is None:
        print('WARN: null could not be built (n<30) — H3 will be UNKNOWN')

    # --- تقسیمِ تودرتوی ۶۰/۴۰ درونِ holdout برای H7 ---
    inner_split = split + int((N - split) * 0.60)
    print(f'nested H7 split inside holdout : bar {inner_split}')

    med_sl = float(np.median(tr['sl_pip'])) if 'sl_pip' in tr else None
    med_tp = float(np.median(tr['tp_pip'])) if 'tp_pip' in tr else None
    bar_time = df['time'].values if 'time' in df else None
    close = df['close'].values.astype(float)

    r = R2.compute_rqs2(tr, ASSET, n_trials=1,
                        sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=bar_time, null=null,
                        split_bar=inner_split, close=close)

    print()
    print(R2.format_rqs2(f'{CARD} HOLDOUT-C', r))
    print()
    for nt in r.get('notes', []):
        print('  ·', nt)

    out = dict(card=CARD, protocol='C_holdout_v2.4_stage2_test',
               lock_source=LOCK_FILE, locked=L, base=BASE,
               n_trials=1, perm_k=500, inner_split=inner_split,
               holdout_bar_range=[split, N],
               n_holdout_trades=n, holdout_wr=round(wr, 2),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    os.makedirs(OUT, exist_ok=True)
    with open(TEST_FILE, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f'\n[checkpoint] {TEST_FILE}')
    print('NOTE: protocol C rule 3 — this holdout must NOT be re-tested after '
          'any retune. The verdict above is final for this configuration.')


if __name__ == '__main__':
    main()
