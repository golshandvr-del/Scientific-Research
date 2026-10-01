"""S1516 — ممیزیِ شاهدِ کاذبِ **بین‌کارتی** (H6 ↔ H4)، پیش از سیم‌کشی.

چرا: ممیزیِ `s1516_false_witness_audit.py` فقط پرسید «آیا S1516 با ساکنانِ
**همان کارت** یک رویداد است؟». پرسشِ دومی هم هست که مکانیزمِ نمایش
(`dropFalseWitnesses`، فقط ctx.cardId جاری) ساختاراً نمی‌بیند: S1516 روی **دو**
کارت ACCEPT است و رویدادش «کفِ تازهٔ ۳۰ روزِ معاملاتی» است — یک افقِ **تقویمی**
که مستقل از تایم‌فریم تعریف شده. اگر H6(L=120) و H4(L=180) همان روزها را
علامت بزنند، کاربر دو کادرِ سبز روی دو کارت می‌بیند و دو شاهد می‌پندارد ⇒ همان
الگوی S547 (۱۴۶=۱۴۶=۱۴۶) که در CROSS_CARD_ALTERNATES ثبت شده.

روش: زمان‌های رویدادِ **هر دو** کارت از مرجعِ پریتیِ کامیت‌شده
(`results/_s1516_parity/XAUUSD_{H6,H4}.json::today_data.all_event_times`، همان
مجموعه‌ای که پورتِ TS بیت‌به‌بیت با آن برابر است) خوانده و در سطحِ **روزِ UTC**
مقایسه می‌شوند (کندل‌های H6 و H4 هم‌مرز نیستند، پس مقایسهٔ اندیسِ کندل بی‌معناست).
همان آستانه‌های ارثیِ ریپو: jaccard ≥ 0.60 و size_ratio ≥ 0.75 ⇒ FALSE-WITNESS.
یک سنجهٔ مکملِ مستقل از مرزِ روز هم گزارش می‌شود: سهمِ رویدادهای هر کارت که
رویدادی از کارتِ دیگر در فاصلهٔ ±۱۲ ساعت دارند.

کنترل: تعدادِ رویدادها باید ۴۱۳ (H6) و ۵۱۸ (H4، دادهٔ امروز) باشد، وگرنه خروج.

اجرا:  python3 tools/s1516_cross_card_audit.py
خروجی: results/_s1516/cross_card_h6_h4.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JACCARD_FALSE_WITNESS = 0.60
SIZE_RATIO_COMPARABLE = 0.75
EXPECTED = {'XAUUSD_H6': 413, 'XAUUSD_H4': 518}
TOL_SEC = 12 * 3600


def events(card: str) -> np.ndarray:
    p = os.path.join(ROOT, 'results', '_s1516_parity', f'{card}.json')
    with open(p) as f:
        d = json.load(f)
    t = np.array(sorted(d['today_data']['all_event_times']), dtype=np.int64)
    if len(t) != EXPECTED[card]:
        sys.exit(f'CONTROL FAIL {card}: {len(t)} != {EXPECTED[card]}')
    return t


def near_share(a: np.ndarray, b: np.ndarray) -> float:
    idx = np.searchsorted(b, a)
    lo = np.abs(a - b[np.clip(idx - 1, 0, len(b) - 1)])
    hi = np.abs(b[np.clip(idx, 0, len(b) - 1)] - a)
    return float(np.mean(np.minimum(lo, hi) <= TOL_SEC))


def main() -> None:
    h6, h4 = events('XAUUSD_H6'), events('XAUUSD_H4')
    d6, d4 = set((h6 // 86400).tolist()), set((h4 // 86400).tolist())
    inter, union = d6 & d4, d6 | d4
    jac = len(inter) / len(union)
    size_ratio = min(len(d6), len(d4)) / max(len(d6), len(d4))
    out = {
        'thresholds': {'jaccard_false_witness': JACCARD_FALSE_WITNESS,
                       'size_ratio_comparable': SIZE_RATIO_COMPARABLE,
                       'unit': 'UTC day'},
        'control': {'H6_events': int(len(h6)), 'H4_events': int(len(h4)), 'passed': True},
        'days': {'H6': len(d6), 'H4': len(d4), 'shared': len(inter),
                 'share_of_H6': round(100 * len(inter) / len(d6), 1),
                 'share_of_H4': round(100 * len(inter) / len(d4), 1),
                 'jaccard': round(jac, 4), 'size_ratio': round(size_ratio, 4)},
        'within_12h': {'H6_with_H4_neighbor': round(near_share(h6, h4), 4),
                       'H4_with_H6_neighbor': round(near_share(h4, h6), 4)},
        'false_witness': bool(jac >= JACCARD_FALSE_WITNESS and size_ratio >= SIZE_RATIO_COMPARABLE),
        'primary_card': 'XAUUSD-H6',
        'why_primary': 'H6: RQS2 87.1, independent value (+11.5pp without same-card fresh high); '
                       'H4: RQS2 84.1, ACCEPT doc §5.3 = portfolio value, not independent (+2.6pp, 3 negative years)',
    }
    os.makedirs(os.path.join(ROOT, 'results', '_s1516'), exist_ok=True)
    dst = os.path.join(ROOT, 'results', '_s1516', 'cross_card_h6_h4.json')
    with open(dst, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print('saved ->', dst)


if __name__ == '__main__':
    main()
