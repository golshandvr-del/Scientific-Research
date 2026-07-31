"""کالبدشکافیِ دروازه‌به‌دروازه — کدام دروازهٔ RQS2 واقعاً گلوگاهِ پروژه است؟

روش: همهٔ رکوردهای حکمِ ثبت‌شده در `results/**/*.json` را می‌خوانَد (هر رکوردی که
هم‌زمان `gates` و `metrics` دارد)، یکتاسازی می‌کند، و برای هر دروازه می‌شمارد:

  • چند بار FAIL شد، چند بار UNKNOWN، چند بار PASS
  • چند بار **تنها قاتل** بود (یعنی لایه فقط همان یک دروازه را شکست داد) —
    این ستون مهم‌ترین است، چون «نامزدهای نجات» را نشان می‌دهد.

و سه پرسشِ ساختاری را کمّی می‌کند:

  ۱. توزیعِ `n_trials`ِ خوداظهاری و سدِ H5 که هر مقدار ایجاد می‌کند
     (آیا معیار، کم‌اعلام‌کردنِ فضای جست‌وجو را پاداش می‌دهد؟)
  ۲. مسیرِ `H10 = UNKNOWN` در برابر اندازهٔ نمونه
     (آیا لایه‌های گزینشی **ساختاراً** از ACCEPT محروم‌اند؟)
  ۳. توزیعِ نهاییِ احکام (چند ACCEPT معتبر تا امروز؟)

این ابزار فقط اندازه می‌گیرد؛ هیچ چیزی در معیار تغییر نمی‌کند.
"""
import json
import glob
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.rqs2 import expected_max_z  # noqa: E402

GATES = ['H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10']
OUT = 'results/_audit_H3/gate_autopsy.json'


def harvest():
    """همهٔ رکوردهای (gates, metrics) را از درختِ results بیرون می‌کشد."""
    recs = []

    def walk(o, fname):
        if isinstance(o, dict):
            g, m = o.get('gates'), o.get('metrics')
            if isinstance(g, dict) and isinstance(m, dict) and 'H3' in g:
                recs.append((fname, g, m, o))
            for v in o.values():
                walk(v, fname)
        elif isinstance(o, list):
            for v in o:
                walk(v, fname)

    for fp in sorted(glob.glob('results/**/*.json', recursive=True)):
        try:
            d = json.load(open(fp))
        except Exception:
            continue
        walk(d, os.path.relpath(fp, 'results'))

    # یکتاسازی روی امضای عددیِ لایه
    seen, uniq = set(), []
    for f, g, m, o in recs:
        key = (f, round(m.get('win_rate') or -1, 2),
               round(m.get('n_trades') or -1, 2),
               round(m.get('skill_z') or -99, 2))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((f, g, m, o))
    return uniq


def main():
    U = harvest()
    fail, unk, ok, solo = Counter(), Counter(), Counter(), Counter()
    nfail_hist = Counter()

    for f, g, m, o in U:
        fl = [h for h in GATES if g.get(h) is False]
        nfail_hist[len(fl)] += 1
        if len(fl) == 1:
            solo[fl[0]] += 1
        for h in GATES:
            v = g.get(h)
            if v is False:
                fail[h] += 1
            elif v is None:
                unk[h] += 1
            else:
                ok[h] += 1

    print(f'رکوردهای یکتا: {len(U)}\n')
    print(f'{"gate":5s} {"FAIL":>5} {"UNK":>5} {"PASS":>5} {"fail%":>7} {"SOLE-killer":>12}')
    table = {}
    for h in GATES:
        tot = fail[h] + unk[h] + ok[h]
        pct = round(100 * fail[h] / tot, 1) if tot else 0.0
        print(f'{h:5s} {fail[h]:5d} {unk[h]:5d} {ok[h]:5d} {pct:6.1f}% {solo[h]:12d}')
        table[h] = dict(fail=fail[h], unknown=unk[h], passed=ok[h],
                        fail_pct=pct, sole_killer=solo[h])

    print('\n=== توزیعِ تعدادِ دروازه‌های شکست‌خورده ===')
    for k in sorted(nfail_hist):
        print(f'  {k:2d} دروازه شکست: {nfail_hist[k]:3d} لایه')

    # ---- ۱. n_trials خوداظهاری ----
    print('\n=== n_trialsِ خوداظهاری و سدی که ایجاد می‌کند ===')
    nt = Counter(m.get('n_trials') for f, g, m, o in U if m.get('n_trials'))
    nt_table = {}
    for N, cnt in sorted(nt.items()):
        bar = round(expected_max_z(N), 3)
        print(f'  n_trials={N:9,d} → سدِ H5 = {bar:5.3f}σ  ({cnt} رکورد)')
        nt_table[str(N)] = dict(bar=bar, records=cnt)

    # ---- ۲. H10 UNKNOWN در برابر n ----
    small = [(f, g, m) for f, g, m, o in U if (m.get('n_trades') or 0) <= 80]
    big = [(f, g, m) for f, g, m, o in U if (m.get('n_trades') or 0) > 200]
    su = sum(1 for f, g, m in small if g.get('H10') is None)
    bu = sum(1 for f, g, m in big if g.get('H10') is None)
    print('\n=== مسیرِ H10=UNKNOWN در برابر اندازهٔ نمونه ===')
    print(f'  n ≤ 80 : {su}/{len(small)} = {100*su/max(len(small),1):.0f}% UNKNOWN')
    print(f'  n > 200: {bu}/{len(big)} = {100*bu/max(len(big),1):.0f}% UNKNOWN')

    # ---- ۳. احکام ----
    verd = Counter(o.get('verdict') for f, g, m, o in U)
    print(f'\n=== توزیعِ احکام ===\n  {dict(verd)}')

    zero_fail = [(f, g, m, o) for f, g, m, o in U
                 if not [h for h in GATES if g.get(h) is False]]
    print('\n=== لایه‌های صفر-شکست (اثباتِ ارضاپذیریِ تجربی) ===')
    zf = []
    for f, g, m, o in zero_fail:
        u = [h for h in GATES if g.get(h) is None]
        print(f'  {f}  verdict={o.get("verdict")}  UNKNOWN={u}  '
              f'n={m.get("n_trades")} WR={m.get("win_rate")} z={m.get("skill_z")}')
        zf.append(dict(file=f, verdict=o.get('verdict'), unknown=u,
                       n=m.get('n_trades'), wr=m.get('win_rate'),
                       z=m.get('skill_z'), rqs2=o.get('rqs2_score')))

    print('\n=== لایه‌های تک-شکست (نامزدهای نجات) ===')
    one = []
    for f, g, m, o in U:
        fl = [h for h in GATES if g.get(h) is False]
        if len(fl) == 1:
            print(f'  [{fl[0]:>3}] {f}  n={m.get("n_trades")} WR={m.get("win_rate")} '
                  f'z={m.get("skill_z")} lift={m.get("skill_lift_pp")} '
                  f'pmax={m.get("perm_max")} net={m.get("net_profit")}')
            one.append(dict(gate=fl[0], file=f, n=m.get('n_trades'),
                            wr=m.get('win_rate'), z=m.get('skill_z'),
                            lift=m.get('skill_lift_pp'),
                            perm_max=m.get('perm_max'),
                            net=m.get('net_profit'),
                            rqs2=o.get('rqs2_score')))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(n_records=len(U), gate_table=table,
                   nfail_hist={str(k): v for k, v in nfail_hist.items()},
                   n_trials_table=nt_table,
                   h10_unknown=dict(small_n_le_80=[su, len(small)],
                                    big_n_gt_200=[bu, len(big)]),
                   verdicts={str(k): v for k, v in verd.items()},
                   zero_fail=zf, single_fail=one),
              open(OUT, 'w'), ensure_ascii=False, indent=1, default=float)
    print(f'\nSAVED {OUT}')


if __name__ == '__main__':
    main()
