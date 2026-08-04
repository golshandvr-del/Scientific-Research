# -*- coding: utf-8 -*-
"""حسابرسیِ retro با منحنیِ توانِ کالیبره‌شده — **کدام ردها بی‌اطلاع بودند؟**

## پرسشِ این ابزار

کالیبراسیونِ `Q10` روی هر ۴ کارتِ طلا نشان داد:

```
توان(WR=65٪) ≈ ۰٪   برای n < ~۳۰۰
توان(WR=65٪) ≈ ۹۶٪   برای n ≥ ۳۲۰
```

پیامدِ فوری و اجتناب‌ناپذیر: **هر لایه‌ای که با `n` کوچک رد شد، «سوخته»
نیست — «ردِ بی‌اطلاع» است.** چون اگر لبهٔ واقعیِ ۶۵٪ هم داشت، معیار
تقریباً همیشه ردش می‌کرد.

این ابزار روی **۷۳۶ فایلِ JSONِ اجراهای واقعیِ خودِ پروژه** می‌گردد، `n` هر
آزمون را استخراج می‌کند و با **منحنیِ توانِ کالیبره‌شدهٔ همان کارت** (نه یک
عددِ حدسیِ ۳۰۰) تلاقی می‌دهد.

## چرا این کار درجهٔ آزادی خرج نمی‌کند

هیچ فرضیهٔ بازاری آزموده نمی‌شود. هیچ پارامتری جست‌وجو نمی‌شود. هیچ لایه‌ای
پاس/رد نمی‌شود. این ابزار فقط **بازخوانیِ اعدادِ قبلاً ثبت‌شده** است و آنها را
با یک منحنیِ اندازه‌گیری‌شده مقایسه می‌کند ⇒ صفر خرج از دفترِ چندگانگی.

## فنسِ صداقت — این ابزار چه چیزی را **اثبات نمی‌کند**

۱. **هیچ لایهٔ سوخته‌ای «نجات» پیدا نمی‌کند.** «ردِ بی‌اطلاع» یعنی
   *نمی‌دانیم*، نه یعنی *لبه داشت*. تفکیکِ این دو حیاتی است و هر خوانشِ
   دیگری تقلب است.
۲. **مجوزِ شل کردنِ هیچ دروازه‌ای صادر نمی‌شود.** شرطِ مشاور برای ادغامِ
   دروازه‌ها (توان<۵۰٪ با nِ کافی) روی هر ۴ کارت **برقرار نشد**.
۳. **مجوزِ بازآزماییِ خودسرانه صادر نمی‌شود.** هر بازآزمایی یک آزمونِ نو
   است و باید هزینهٔ خودش را به دفترِ چندگانگی بپردازد.
۴. آنچه **می‌دهد** فقط یک چیز است: صفِ اولویت. اگر بازآزمایی‌ای انجام شود،
   کدام لایه‌ها بیشترین احتمالِ داشتنِ لبهٔ کشف‌نشده را دارند.

## معیارِ اولویت — چرا `n` تنها ملاک نیست

یک لایه با `n=۱۰` و `WR=۵۲٪` هیچ نشانه‌ای از لبه ندارد؛ بی‌اطلاع بودنش
بی‌اهمیت است. اما لایه‌ای با `n=۸۰` و `WR=۶۸٪` هم بی‌اطلاع است و هم
**نشانهٔ لبه** دارد. پس اولویت با هر دو تعریف می‌شود:

```
اولویت  =  (۱ − توانِ کالیبره‌شده)  ×  نشانهٔ لبه
```

که در آن «نشانهٔ لبه» = لیفتِ مشاهده‌شده روی مبنای پوچِ همان کارت.
عاملِ اول یعنی «چقدر کور بودیم»، عاملِ دوم یعنی «چقدر چیزی برای دیدن بود».
"""

import json
import glob
import os
import re

OUT = 'results/_audit_retro_power'
CALIB_DIR = 'results/_calib_power'
os.makedirs(OUT, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) بارگذاریِ منحنی‌های توانِ کالیبره‌شده — اندازه‌گیری‌شده، نه حدسی
# ═══════════════════════════════════════════════════════════════════════════

def load_power_curves():
    """منحنیِ توان از فایل‌های `results/_calib_power/*.json`.

    ساختارِ خروجی:  `{card: {wr_target: {n: power}}}` + مبنای پوچِ هر کارت.
    """
    curves, baselines = {}, {}
    for f in sorted(glob.glob(os.path.join(CALIB_DIR, 'power_*.json'))):
        d = json.load(open(f))
        card = d['card']
        baselines[card] = d['base_wr']
        cur = {}
        for v in d['cells'].values():
            cur.setdefault(v['wr_target'], {})[v['n']] = v['power']
        curves[card] = cur
    return curves, baselines


def interp_power(curve, wr, n):
    """توانِ درون‌یابی‌شده در `(wr, n)`.

    درون‌یابیِ دوخطی روی شبکهٔ کالیبراسیون. بیرونِ شبکه **قطع** می‌شود
    (clamp) نه برون‌یابی — چون برون‌یابیِ توان می‌تواند عددِ بی‌معنا بسازد.
    """
    wrs = sorted(curve.keys())
    # ── قطع در مرزهای WR
    wr_c = min(max(wr, wrs[0]), wrs[-1])
    # دو WRِ مجاور
    lo_wr = max([w for w in wrs if w <= wr_c])
    hi_wr = min([w for w in wrs if w >= wr_c])

    def at_wr(w):
        ns = sorted(curve[w].keys())
        n_c = min(max(n, ns[0]), ns[-1])
        lo_n = max([x for x in ns if x <= n_c])
        hi_n = min([x for x in ns if x >= n_c])
        if hi_n == lo_n:
            return curve[w][lo_n]
        t = (n_c - lo_n) / (hi_n - lo_n)
        return curve[w][lo_n] * (1 - t) + curve[w][hi_n] * t

    if hi_wr == lo_wr:
        return at_wr(lo_wr)
    t = (wr_c - lo_wr) / (hi_wr - lo_wr)
    return at_wr(lo_wr) * (1 - t) + at_wr(hi_wr) * t


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) استخراجِ (n, wr, card) از JSONهای تاریخیِ پروژه
# ═══════════════════════════════════════════════════════════════════════════

N_KEYS = ('n', 'n_trades', 'trades', 'ntrades')
WR_KEYS = ('wr', 'win_rate', 'winrate', 'wr_pct')
CARD_RE = re.compile(r'(XAUUSD|EURUSD|GBPUSD|USDJPY|AUDUSD)[_\-]?(M1|M5|M15|M30|H1|H4|D1|W1)',
                     re.I)


def harvest(path, node, card_hint, out, depth=0):
    """پیمایشِ بازگشتی برای یافتنِ جفت‌های `(n, wr)` هم‌سطح.

    شرطِ پذیرش: `n` و `wr` **در همان دیکشنری** باشند — تا `n` یک آزمون با
    `wr` آزمونِ دیگری اشتباه جفت نشود.
    """
    if depth > 5:
        return
    if isinstance(node, dict):
        n_val = wr_val = None
        for k, v in node.items():
            kl = str(k).lower()
            if kl in N_KEYS and isinstance(v, (int, float)) and 0 < v < 1e6:
                n_val = int(v)
            if kl in WR_KEYS and isinstance(v, (int, float)) and 0 <= v <= 100:
                wr_val = float(v)
        # کارت را از خودِ گره یا از نامِ فایل برمی‌داریم
        card = card_hint
        p = node.get('pair')
        t = node.get('tf') or node.get('timeframe')
        if isinstance(p, str) and isinstance(t, str):
            card = f'{p.upper()}_{t.upper()}'
        if n_val is not None and wr_val is not None:
            out.append(dict(file=path, card=card, n=n_val, wr=wr_val))
        for v in node.values():
            harvest(path, v, card, out, depth + 1)
    elif isinstance(node, list):
        for v in node[:400]:
            harvest(path, v, card_hint, out, depth + 1)


def main():
    curves, baselines = load_power_curves()
    if not curves:
        print('no calibrated power curves found — run power_calibration first')
        return
    print('calibrated cards:', sorted(curves.keys()))
    print('baselines       :', {k: round(v, 3) for k, v in baselines.items()})
    print()

    files = sorted(glob.glob('results/**/*.json', recursive=True))
    # فایل‌های خودِ کالیبراسیون و حسابرسی‌ها را کنار می‌گذاریم (خودارجاعی)
    files = [f for f in files
             if '_calib_power' not in f and '_audit_retro_power' not in f]

    rows = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        m = CARD_RE.search(os.path.basename(f))
        hint = f'{m.group(1).upper()}_{m.group(2).upper()}' if m else None
        harvest(f, d, hint, rows)

    print(f'harvested {len(rows):,} (n, wr) observations from {len(files):,} files')

    # ── فقط آزمون‌هایی که کارتشان کالیبره شده قابلِ داوری‌اند
    judged = []
    for r in rows:
        card = r['card']
        if card not in curves:
            continue
        base = baselines[card]
        pw = interp_power(curves[card], r['wr'], r['n'])
        lift = r['wr'] - base
        judged.append(dict(**r, base_wr=round(base, 3), lift=round(lift, 3),
                           power=round(pw, 4),
                           blindness=round(1.0 - pw, 4),
                           priority=round((1.0 - pw) * max(lift, 0.0), 3)))

    print(f'judgeable (calibrated card): {len(judged):,}')
    print()

    # ── تجمیعِ آماری
    n_blind = sum(1 for r in judged if r['power'] < 0.10)
    n_seen = sum(1 for r in judged if r['power'] >= 0.80)
    print(f'  power < 10%  (essentially blind) : {n_blind:,}  '
          f'({100*n_blind/max(len(judged),1):.1f}%)')
    print(f'  power >= 80% (adequately seen)   : {n_seen:,}  '
          f'({100*n_seen/max(len(judged),1):.1f}%)')
    print()

    # ── صفِ اولویتِ بازآزمایی
    judged.sort(key=lambda r: -r['priority'])
    print('TOP RETEST PRIORITY  (blind AND showing edge signal)')
    hdr = (f"{'card':14s} {'n':>6s} {'wr':>7s} {'base':>7s} {'lift':>7s} "
           f"{'power':>7s} {'prio':>7s}  file")
    print(hdr)
    print('-' * len(hdr))
    seen_files = set()
    shown = 0
    for r in judged:
        # یک ردیف در هر فایل ⇒ فهرست خواندنی بماند
        if r['file'] in seen_files:
            continue
        seen_files.add(r['file'])
        print(f"{r['card']:14s} {r['n']:6d} {r['wr']:7.2f} {r['base_wr']:7.2f} "
              f"{r['lift']:+7.2f} {100*r['power']:6.1f}% {r['priority']:7.2f}  "
              f"{os.path.basename(r['file'])[:48]}")
        shown += 1
        if shown >= 25:
            break

    payload = dict(
        calibrated_cards=sorted(curves.keys()),
        baselines={k: round(v, 4) for k, v in baselines.items()},
        n_files_scanned=len(files),
        n_observations=len(rows),
        n_judgeable=len(judged),
        n_power_below_10pct=n_blind,
        n_power_above_80pct=n_seen,
        note=('Retro audit. Zero degrees of freedom: no hypothesis tested, no '
              'parameter searched, no layer passed or rejected. An uninformative '
              'rejection means UNKNOWN, not VINDICATED.'),
        observations=judged,
    )
    with open(os.path.join(OUT, 'retro_power_audit.json'), 'w') as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    print(f'\nsaved → {OUT}/retro_power_audit.json')


if __name__ == '__main__':
    main()
