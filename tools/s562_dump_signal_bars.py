# -*- coding: utf-8 -*-
"""
s562_dump_signal_bars.py — استخراجِ **مجموعهٔ مرجعِ سیگنال** S562 برای تستِ parity

چرا این فایل لازم است
=====================
ماژولِ TS (web_tool/src/gap_open_volfilter_s562.ts) ادعا می‌کند پورتِ مو-به-موی
`tools/s562_volfilter.py::vol_filter_mask` + سیگنالِ پایهٔ S560 است. این ادعا
باید **اندازه‌گیری** شود، نه باور. برای اندازه‌گیری، یک «حقیقتِ مرجع» لازم است:
اندیس و زمانِ هر کندلی که پایتون رویش سیگنال می‌گذارد.

⚠️ نکتهٔ ظریفِ طراحی — دو ماسکِ متفاوت اینجا تولید می‌شود:

  ① `rolling` — عیناً همان چیزی که داور دید: آستانهٔ گپِ **انبساطی** +
     چندکِ نوسانِ **رولینگِ ۲۵۰روزه**. این ماسک همان n=438 (M15) و
     n=255 (H1) را می‌دهد که در judge_{M15,H1}.json ثبت است. این
     «حکمِ علمی» است.

  ② `frozen` — با هر دو آستانهٔ **منجمد** (همان اعدادی که در ماژولِ TS
     هاردکد شده‌اند). این ماسک همان چیزی است که سایت **واقعاً** اجرا
     می‌کند.

تستِ parityِ درست، TS را با ماسکِ ② مقایسه می‌کند (چون همان منطق است)، و
فاصلهٔ ①↔② را جداگانه گزارش می‌کند تا هیچ‌چیز زیرِ فرش نرود. مقایسهٔ TS با ①
غلط می‌بود: اختلاف در آن حالت از انجمادِ آستانه می‌آید نه از پورت، و ما را
به تعقیبِ باگی می‌فرستاد که وجود ندارد.

خروجی: results/_s562_arms/signal_bars_{TF}.json
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

sys.path.insert(0, ROOT)

from s560_gapopen_explore import day_breaks              # noqa: E402
# ⚠️ ماسکِ پایه **بازنویسی نمی‌شود**: عیناً همان `build` که داور استفاده کرد
#    import می‌گردد (تک‌منبعِ حقیقت). بازنویسیِ دستیِ آن، نخستین تلاشِ من بود و
#    بلافاصله با TypeError روی امضای causal_neg_gap_quantile شکست — نشانهٔ خوبی
#    که چرا نباید منطقِ داوری‌شده را دوباره نوشت: امضای واقعی روی **مرزها**
#    ایندکس می‌شود نه روی کلِ کندل‌ها، و حاشیهٔ امنِ انتها هم دارد.
from tools.s560_adjudicate import build                  # noqa: E402
from s562_volfilter import vol_filter_mask, VOL_N, ROLL_D, MIN_S      # noqa: E402

ARMS = os.path.join(ROOT, 'results', '_s562_arms')
LOCK = os.path.join(ARMS, 'locked_config.json')


def _frozen(tf: str) -> dict:
    return json.load(open(os.path.join(ARMS, f'frozen_thresholds_{tf}.json')))


def _base_mask_frozen(d, tf, thr_we, thr_wd):
    """ماسکِ پایه با آستانهٔ **منجمد** (دو عددِ ثابت) — همان منطقِ ماژولِ TS."""
    t, o, c = d['time'], d['open'], d['close']
    n = len(t)
    brk = day_breaks(t, tf)
    mask = np.zeros(n, bool)
    first = brk + 1
    keep = first < n
    brk_k, first_k = brk[keep], first[keep]
    gaps = o[first_k] - c[brk_k]
    is_we = (t[first_k] - t[brk_k]) > 86400
    thr = np.where(is_we, thr_we, thr_wd)
    cond = (gaps < 0) & (np.abs(gaps) > thr)
    mask[brk_k[cond]] = True
    return mask


def _vol_mask_frozen(d, tf, mask, vol_thr):
    """فیلترِ V با آستانهٔ **منجمد** — همان کاری که ماژولِ TS می‌کند.

    عیناً هندسهٔ vol_filter_mask: روزها از day_breaks، دامنهٔ روز = max(high) −
    min(low)، vol_ref[k] = میانگینِ ۱۴ روزِ منتهی به k (شاملِ k). تفاوتِ تنها:
    آستانه به‌جای چندکِ رولینگ، عددِ ثابت است. نبودِ vol_ref ⇒ رد (مثلِ پایتون).
    """
    t, h, l = d['time'], d['high'], d['low']
    n = len(t)
    brk = day_breaks(t, tf)
    starts = np.concatenate([[0], brk + 1])
    ends = np.concatenate([brk, [n - 1]])
    n_days = len(starts)
    rng_day = np.array([h[starts[k]:ends[k] + 1].max() - l[starts[k]:ends[k] + 1].min()
                        for k in range(n_days)])
    vol_ref = np.full(n_days, np.nan)
    csum = np.concatenate([[0.0], np.cumsum(rng_day)])
    for k in range(VOL_N - 1, n_days):
        vol_ref[k] = (csum[k + 1] - csum[k + 1 - VOL_N]) / VOL_N
    day_of_end = {int(ends[k]): k for k in range(n_days)}
    out = np.zeros(n, bool)
    for i in np.flatnonzero(mask):
        k = day_of_end.get(int(i))
        if k is None or np.isnan(vol_ref[k]):
            continue
        if vol_ref[k] <= vol_thr:
            out[i] = True
    return out


def dump(tf: str):
    lock = json.load(open(LOCK))[tf]
    q, sw = float(lock['cfg']['q']), bool(lock['cfg']['sw'])
    qv = float(lock['arms'][lock['picked']]['qv'])
    fz = _frozen(tf)
    thr_we = fz['frozen_threshold_usd']['weekend']
    thr_wd = fz['frozen_threshold_usd']['weekday']
    vol_thr = fz['frozen_vol_threshold_usd']

    d = load_fast('XAUUSD', tf)
    t = d['time']
    print(f"src={d['src']}  n={len(t)}")

    # ① حکمِ داور — انبساطی + رولینگ
    base_exp = _base_mask_expanding(d, tf, q, sw)
    roll = vol_filter_mask(d, tf, base_exp, qv)

    # ② منطقِ سایت — منجمد + منجمد
    base_fz = _base_mask_frozen(d, tf, thr_we, thr_wd)
    froz = _vol_mask_frozen(d, tf, base_fz, vol_thr)

    # assertِ BUG-DATASETDRIFT: ماسکِ ① باید همان n قفل‌شده را بدهد
    n_lock = int(lock['n_base_signals'])
    assert int(base_exp.sum()) == n_lock, \
        f'BUG-DATASETDRIFT: base={int(base_exp.sum())} != locked={n_lock}'

    idx_roll = np.flatnonzero(roll)
    idx_froz = np.flatnonzero(froz)
    inter = np.intersect1d(idx_roll, idx_froz)

    out = {
        'tf': tf,
        'cfg': {'q': q, 'sw': sw, 'qv': qv},
        'frozen_thresholds': {'weekend': thr_we, 'weekday': thr_wd, 'vol': vol_thr},
        'vol_params': {'vol_n': VOL_N, 'roll_d': ROLL_D, 'min_s': MIN_S},
        'n_base_expanding': int(base_exp.sum()),
        'n_base_frozen': int(base_fz.sum()),
        'n_rolling': int(roll.sum()),
        'n_frozen': int(froz.sum()),
        'n_overlap_rolling_frozen': int(len(inter)),
        # مجموعهٔ مرجعِ مقایسه با TS = ماسکِ ② (منطقِ سایت)
        'signal_times_frozen': [int(t[i]) for i in idx_froz],
        'signal_bars_frozen': [int(i) for i in idx_froz],
        # حکمِ داور برای ارجاع
        'signal_times_rolling': [int(t[i]) for i in idx_roll],
        'src': d['src'],
        'first_utc': d['first_utc'], 'last_utc': d['last_utc'],
    }
    os.makedirs(ARMS, exist_ok=True)
    p = os.path.join(ARMS, f'signal_bars_{tf}.json')
    json.dump(out, open(p, 'w'), indent=1)
    print(json.dumps({k: v for k, v in out.items()
                      if not k.startswith('signal_')}, indent=1, ensure_ascii=False))
    print(f'\n→ {p}')


if __name__ == '__main__':
    dump(sys.argv[1] if len(sys.argv) > 1 else 'M15')
