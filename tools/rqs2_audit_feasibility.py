"""حسابرسیِ ارضاپذیری (satisfiability) معیارِ RQS2 — آیا اصلاً قابلِ پاس شدن است؟

پرسشِ کاربر: «آیا معیاری است که ظاهرش درست است اما باطنش تناقض دارد و
غیرقابلِ پاس شدن است؟»

روشِ پاسخ — تحلیلِ **کرانِ بالای قابلِ دستیابی** در برابر **کرانِ پایینِ لازم**:

▸ سدِ آماری که لایه باید بشکند (بیشینهٔ سه شرطِ هم‌زمان):
      z_req = max( SKILL_Z_MIN=3.0 ,                       # H3 شرطِ صریح
                   c_K · (σ_p/σ_b)  با c_K≈√(2 ln K) ,      # H3 شرطِ پنهانِ perm_max
                   z_bar(N) = E[max_N نرمالِ استاندارد] )   # H5 قضیهٔ استراتژیِ کاذب

▸ z ای که **حداکثر** می‌توان به دست آورد روی یک کارت، برای لبهٔ حقیقیِ L (pp):
      z_att = L·√n / (100·√(p₀q₀))
  و `n` خودش سقف دارد: معاملاتِ **ناهم‌پوشان** (H0 هم‌زمانی=۱ را الزام می‌کند)
  ⇒ n ≤ bars / max_hold.  این کرانِ **مطلق** است (لایه در هر فرصت وارد شود)؛
  یک لایهٔ گزینشی با نرخِ سیگنالِ f کسری از آن را می‌گیرد: n ≈ f · bars/max_hold.

▸ ⇒ لبهٔ **لازم** برای پاس‌شدن:   L_req = z_req · 100·√(p₀q₀) / √n
  اگر L_req از هر لبهٔ **باورپذیری** بزرگ‌تر باشد، آن کارت ریاضیاً
  غیرقابلِ‌پاس‌شدن است — مستقل از نبوغِ محقق.

⚠️ این ابزار هیچ چیزی را در معیار تغییر نمی‌دهد — فقط اندازه‌گیری و اشتقاق.
"""
import json
import os
import sys
from math import log, sqrt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.rqs2 import expected_max_z          # noqa: E402
from engine.rqs2 import SKILL_Z_MIN             # noqa: E402

OUT = 'results/_audit_H3/feasibility.json'

# افقِ نگهداریِ متعارفِ پروژه (از TF_MAX_HOLD لایه‌های موجود)
MAX_HOLD = {'M1': 200, 'M5': 96, 'M15': 40, 'M30': 28, 'H1': 20, 'H4': 10,
            'D1': 5, 'W1': 13}

CARDS = [('XAUUSD', 'M5', 200000), ('XAUUSD', 'M15', 150000),
         ('XAUUSD', 'M30', 181383), ('XAUUSD', 'H1', 90950),
         ('XAUUSD', 'H4', 23755), ('XAUUSD', 'D1', 3989),
         ('XAUUSD', 'W1', 810),
         ('EURUSD', 'M1', 200000), ('EURUSD', 'M5', 200000),
         ('EURUSD', 'M15', 200000), ('EURUSD', 'M30', 200000),
         ('EURUSD', 'H1', 100070), ('EURUSD', 'H4', 25133),
         ('EURUSD', 'D1', 4195), ('EURUSD', 'W1', 843)]

# نرخِ سیگنالِ گزینشی — یک لایهٔ واقعی در هر فرصت وارد نمی‌شود
SEL = {'every': 1.00, 'selective': 0.10, 'rare': 0.02}

# لبهٔ باورپذیر: بزرگ‌ترین لیفتِ **اندازه‌گیری‌شدهٔ** تاریخِ پروژه ۲۵.۳pp بوده
PLAUSIBLE_LIFT = 15.0      # لبهٔ قوی ولی متعارف
EXCEPTIONAL_LIFT = 25.0    # سقفِ تاریخیِ مشاهده‌شدهٔ پروژه


def z_required(n_trials, K=2000, sp_over_sb=1.0):
    """سدِ مؤثرِ آماری = بیشینهٔ سه شرطِ هم‌زمانِ H3 و H5."""
    cK = sqrt(2.0 * log(K)) * sp_over_sb
    return max(SKILL_Z_MIN, cK, expected_max_z(n_trials))


def lift_required(z_req, n, p0):
    """لبهٔ لازم (pp) برای رسیدن به z_req با n معامله و مبنای p0."""
    if n <= 0:
        return float('inf')
    return z_req * 100.0 * sqrt(p0 * (1.0 - p0) / n)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # p0 = مبنای بی‌مهارت ≈ 1/(1+RR)؛ RR=2 قراردادِ رایجِ لایه‌های اخیر
    scenarios = {'RR=1 (p0=0.50)': 0.50, 'RR=2 (p0=0.33)': 1 / 3,
                 'RR=3 (p0=0.25)': 0.25}
    n_trials_cases = {'declared_S346=56,499': 56499,
                      'modest=1,296': 1296,
                      'full_bank=5,196,960': 1296 * 401 * 10}

    out = {'z_bar_table': {}, 'cards': [], 'notes': []}
    for label, N in n_trials_cases.items():
        out['z_bar_table'][label] = round(expected_max_z(N), 3)

    print('=== سدِ مؤثرِ z (بیشینهٔ سه شرط) برای سه سطحِ وسعتِ جست‌وجو ===')
    for label, N in n_trials_cases.items():
        zr = z_required(N)
        print(f'  n_trials={label:24s} z_bar={expected_max_z(N):5.3f}  '
              f'=> z_req(با perm_max K=2000) = {zr:5.3f}')
    print()

    zr_main = z_required(56499)          # سدِ عملیاتیِ پروژه
    out['z_req_operational'] = round(zr_main, 3)

    print(f'=== لبهٔ لازم L_req برای عبور، با z_req={zr_main:.2f} ===')
    print(f'(FEASIBLE اگر L_req <= {PLAUSIBLE_LIFT}pp · MARGINAL تا '
          f'{EXCEPTIONAL_LIFT}pp · INFEASIBLE بالاتر)')
    print()
    for sc_label, p0 in scenarios.items():
        print(f'--- سناریو {sc_label} ---')
        hdr = f'{"card":14s} {"bars":>8} {"n_max":>7}'
        for k in SEL:
            hdr += f' {"L_req/" + k:>14}'
        print(hdr)
        for asset, tf, bars in CARDS:
            mh = MAX_HOLD[tf]
            n_max = bars // mh
            row = dict(card=f'{asset}-{tf}', bars=bars, max_hold=mh,
                       n_max=n_max, p0=round(p0, 4), z_req=round(zr_main, 3))
            line = f'{asset + "-" + tf:14s} {bars:8d} {n_max:7d}'
            for k, f in SEL.items():
                n = int(n_max * f)
                L = lift_required(zr_main, n, p0)
                verdict = ('FEASIBLE' if L <= PLAUSIBLE_LIFT else
                           'MARGINAL' if L <= EXCEPTIONAL_LIFT else 'INFEASIBLE')
                row[f'n_{k}'] = n
                row[f'Lreq_{k}'] = round(L, 2)
                row[f'verdict_{k}'] = verdict
                line += f' {L:8.2f}pp {verdict[:4]:>4}'
            print(line)
            if sc_label == 'RR=2 (p0=0.33)':
                out['cards'].append(row)
        print()

    # ────────────────────────────────────────────────────────────────────
    # آزمونِ کلیدی: سقفِ z قابلِ دستیابی روی هر کارت با لبهٔ باورپذیر
    # ────────────────────────────────────────────────────────────────────
    print('=== سقفِ z قابلِ دستیابی (با لبهٔ ۱۵pp و گزینشیِ ۱۰٪) در برابر سدها ===')
    p0 = 1 / 3
    zb_full = expected_max_z(1296 * 401 * 10)
    rows = []
    for asset, tf, bars in CARDS:
        mh = MAX_HOLD[tf]
        n = int((bars // mh) * SEL['selective'])
        if n <= 0:
            continue
        z_att = PLAUSIBLE_LIFT / (100 * sqrt(p0 * (1 - p0) / n))
        rows.append((f'{asset}-{tf}', n, z_att))
    print(f'{"card":14s} {"n":>7} {"z_att":>7}  vs z_req={zr_main:.2f}  '
          f'vs z_bar(full bank)={zb_full:.2f}')
    for c, n, z in rows:
        v1 = 'PASS' if z > zr_main else 'FAIL'
        v2 = 'PASS' if z > zb_full else 'FAIL'
        print(f'{c:14s} {n:7d} {z:7.2f}   {v1:4s}                {v2}')
    out['z_att_selective_15pp'] = [dict(card=c, n=n, z_att=round(z, 3))
                                   for c, n, z in rows]
    out['z_bar_full_bank'] = round(zb_full, 3)

    json.dump(out, open(OUT, 'w'), indent=1, default=float)
    print(f'\nSAVED {OUT}')


if __name__ == '__main__':
    main()
