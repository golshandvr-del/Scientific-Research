"""حسابرسیِ **پروتکل** — آیا مشکل در معیار است یا در روشِ تحقیق؟

یافتهٔ بخشِ ۴.۲.۱ گزارش این بود که `H5` هیچ نقصِ آماری ندارد و ردِ `S346` درست
بوده است. پس اگر معیار سالم است، **علتِ خشکسالی کجاست؟**

فرضیهٔ این اسکریپت: علت در **پروتکلِ تحقیق** است، نه در معیار.

  پروتکلِ فعلی  = «جست‌وجوی فراگیر روی همان داده، سپس جریمهٔ چندگانگی»
                  ⇒ N_eff ≈ ۵۶٬۴۹۹ ⇒ سد ۴.۲۷σ ⇒ نیاز به lift·√n ≥ ۲۰۱
                  ⇒ روی داده‌ی محدود عملاً پرداخت‌نکردنی است.

  پروتکلِ جانشین = «جست‌وجو روی نیمهٔ اول، تأییدِ **یک** برندهٔ منتخب روی نیمهٔ
                  کنارگذاشته‌شده» ⇒ روی نمونهٔ تأیید N = ۱ ⇒ سد ۱.۶۴۵σ (α=۰.۰۵)
                  ⇒ نیاز به lift·√n ≥ ۷۸ — **پرداخت‌کردنی**.

این تفاوت، نرم‌کردنِ معیار **نیست**؛ استانداردِ متعارفِ اعتبارسنجیِ کنارگذاشته
(hold-out) است. جریمهٔ چندگانگی *فقط* لازم است چون جست‌وجو و آزمون روی **یک**
داده انجام می‌شوند؛ اگر آزمون روی داده‌ای انجام شود که در جست‌وجو دیده نشده،
تعدادِ فرضیه‌های آزموده‌شده روی آن داده واقعاً ۱ است.

این اسکریپت `oos` ثبت‌شدهٔ هر رکورد را برمی‌دارد و آمارهٔ مهارتِ **خارج از نمونه**
را حساب می‌کند، سپس با سدِ درستِ `N=1` می‌سنجد.

⚠️ محدودیتِ صداقتی که باید ثبت شود: نیمهٔ `oos`ِ موجود در رکوردها **پس از**
انتخابِ پیکربندی محاسبه شده است، نه پیش از آن. پس این محاسبه یک **برآوردِ خوش‌بین**
است و اثباتِ قطعی نیست؛ اثباتِ قطعی نیازمند اجرای مجددِ جست‌وجو *فقط* روی نیمهٔ
اول و سپس یک آزمونِ واحد روی نیمهٔ دوم است. این محدودیت در گزارش صریحاً ذکر شده.

فقط اندازه‌گیری؛ هیچ تغییری در معیار.
"""
import json
import glob
import os
import sys
from math import sqrt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.rqs2 import expected_max_z  # noqa: E402

OUT = 'results/_audit_H3/protocol_fix.json'
Z_ALPHA05 = 1.645   # یک‌طرفه، α=۰.۰۵، برای N=۱
Z_ALPHA01 = 2.326   # یک‌طرفه، α=۰.۰۱، برای N=۱


def z_of(lift_pp, n, ref_frac):
    """آمارهٔ مهارت روی نسبتِ برد با خطای معیارِ دوجمله‌ای در نقطهٔ مرجع."""
    if not n or n <= 0 or ref_frac <= 0 or ref_frac >= 1:
        return None
    se = 100.0 * sqrt(ref_frac * (1.0 - ref_frac) / n)
    return lift_pp / se if se > 0 else None


def harvest():
    recs = []

    def walk(o, fname):
        if isinstance(o, dict):
            m = o.get('metrics')
            if isinstance(m, dict) and isinstance(m.get('oos'), dict) \
                    and m.get('win_rate') is not None \
                    and m.get('skill_lift_pp') is not None:
                recs.append((fname, m, o))
            for v in o.values():
                walk(v, fname)
        elif isinstance(o, list):
            for v in o:
                walk(v, fname)

    for fp in sorted(glob.glob('results/**/*.json', recursive=True)):
        if '_audit_H3' in fp:
            continue
        try:
            d = json.load(open(fp))
        except Exception:
            continue
        walk(d, os.path.relpath(fp, 'results'))

    seen, uniq = set(), []
    for f, m, o in recs:
        k = (f, round(m['win_rate'], 2), m.get('n_trades'),
             round(m['skill_lift_pp'], 2))
        if k in seen:
            continue
        seen.add(k)
        uniq.append((f, m, o))
    return uniq


def main():
    U = harvest()
    print(f'رکوردهای دارای نیمهٔ خارج-از-نمونه: {len(U)}\n')
    print(f'{"record":40s} {"n_is":>5} {"z_is":>6} {"bar_is":>7} '
          f'{"n_oos":>5} {"lift_oos":>8} {"z_oos":>6} {"N=1 bar":>7} {"OOS verdict":>12}')

    rows = []
    for f, m, o in U:
        wr = m['win_rate']
        lift = m['skill_lift_pp']
        ref = (wr - lift) / 100.0          # نرخِ بردِ بی‌قیدِ مدلِ صفر
        oos = m['oos']
        n_oos = oos.get('n')
        wr_oos = oos.get('wr')
        if n_oos is None or wr_oos is None:
            continue
        lift_oos = wr_oos - ref * 100.0
        z_oos = z_of(lift_oos, n_oos, ref)
        nt = m.get('n_trials')
        bar_is = round(expected_max_z(nt), 3) if nt else None
        verdict = None
        if z_oos is not None:
            if z_oos > Z_ALPHA01:
                verdict = 'CONFIRM p<.01'
            elif z_oos > Z_ALPHA05:
                verdict = 'CONFIRM p<.05'
            else:
                verdict = 'not confirmed'
        print(f'{f[:40]:40s} {str(m.get("n_trades")):>5} '
              f'{str(m.get("skill_z")):>6} {str(bar_is):>7} '
              f'{n_oos:>5} {lift_oos:>8.2f} '
              f'{(f"{z_oos:.2f}" if z_oos else "-"):>6} '
              f'{Z_ALPHA05:>7} {str(verdict):>12}')
        rows.append(dict(record=f, n_is=m.get('n_trades'), wr_is=wr,
                         lift_is=lift, z_is=m.get('skill_z'),
                         n_trials=nt, bar_in_sample=bar_is,
                         ref_wr=round(ref * 100, 2),
                         n_oos=n_oos, wr_oos=wr_oos,
                         lift_oos=round(lift_oos, 2),
                         z_oos=(round(z_oos, 3) if z_oos else None),
                         net_oos=oos.get('net'), pf_oos=oos.get('pf'),
                         oos_verdict=verdict))

    conf = [r for r in rows if r['oos_verdict'] and
            r['oos_verdict'].startswith('CONFIRM')]
    print(f'\n>>> تأییدشده در خارج از نمونه با سدِ N=1: {len(conf)} از {len(rows)}')
    for r in sorted(conf, key=lambda x: -(x['z_oos'] or 0)):
        print(f'    {r["record"][:46]:46s} z_oos={r["z_oos"]:.2f} '
              f'n_oos={r["n_oos"]:4d} WR_oos={r["wr_oos"]:.2f} '
              f'net_oos={r["net_oos"]} [{r["oos_verdict"]}]')

    # سدِ لازم برای پروتکلِ hold-out در برابر پروتکلِ فعلی
    print('\n=== مقایسهٔ هزینهٔ دو پروتکل (lift·√n لازم) ===')
    for name, z in [('پروتکلِ فعلی: N_eff=56,499', 4.265),
                    ('پیش‌ثبتِ خانوادهٔ ۳۲ عضوی (E[max])', 2.100),
                    ('پیش‌ثبتِ خانوادهٔ ۳۲ عضوی (α=.05 درست)', 3.044),
                    ('تأییدِ hold-out، N=1 (α=.05)', 1.645),
                    ('تأییدِ hold-out، N=1 (α=.01)', 2.326)]:
        print(f'  {name:42s} → lift·√n ≥ {z*47.14:6.1f}')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(rows=rows, n_confirmed=len(conf),
                   z_bar_alpha05_N1=Z_ALPHA05, z_bar_alpha01_N1=Z_ALPHA01,
                   caveat=('the recorded oos half was computed after the '
                           'configuration was chosen, so these z_oos values '
                           'are optimistic estimates, not a clean prospective '
                           'hold-out proof')),
              open(OUT, 'w'), ensure_ascii=False, indent=1, default=float)
    print(f'\nSAVED {OUT}')


if __name__ == '__main__':
    main()
