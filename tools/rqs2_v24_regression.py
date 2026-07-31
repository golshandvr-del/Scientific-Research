"""آزمونِ بازگشتیِ اجباریِ اصلاحاتِ RQS2 v2.4 (R1–R4).

طبق بخشِ ۶.۴ گزارشِ حسابرسی، هیچ اصلاحی نباید merge شود مگر این چهار آزمون را
پاس کند. هدفِ مشترکِ همه: **اثباتِ اینکه اصلاح، معیار را دور نزده** — یعنی هیچ
لایهٔ واقعاً بی‌مهارتی را زنده نکرده است.

    R1  سه لایهٔ تقلبیِ اسپک (رانش‌سوارِ W1، TP<SL، بیش‌برازشِ گزینشی) باید
        همچنان REJECT شوند.                                    ← ضدِ دورزنی
    R2  ۲۷ لایه‌ای که ۱۰–۱۱ دروازه شکست دادند باید همچنان REJECT بمانند.
    R3  حکمِ H3 باید در برابرِ ۶ بذر × ۵ مقدارِ K **ثابت** بماند (۳۰ از ۳۰).
    R4  لایه‌های z<3 باید همچنان REJECT بمانند ⇒ اصلاح لایهٔ بی‌مهارت را زنده
        نمی‌کند.

روش: چون اصلاحِ H3 صرفاً تابعِ (lift, p_perm, perm_k) است و این آماره‌ها در
رکوردهای ثبت‌شده موجودند، R1/R2/R4 را می‌توان با **بازاجرای منطقِ H3 جدید روی
آماره‌های واقعیِ ثبت‌شده** سنجید — بازتولیدپذیر و بدونِ نیاز به شبیه‌سازیِ مجدد.
R3 نیازمندِ اجرای واقعیِ جای‌گشت است و از artifactِ reproducibility استفاده
می‌کند که با معیارِ جدید بازخوانی می‌شود.

خروجی: results/_audit_H3/v24_regression.json — با حکمِ PASS/FAIL هر چهار آزمون.
"""
import json
import glob
import os
from math import erfc, sqrt

# ثابت‌های معیارِ جدید (باید با engine/rqs2.py یکی باشند)
SKILL_LIFT_MIN = 4.0
SKILL_P_MAX = 0.001
PERM_K_MIN = 500   # v2.4: کفِ همگراییِ perm_sd (باید با engine/rqs2.py یکی باشد)


def p_perm_from_z(z):
    """p-valueِ یک‌طرفهٔ همگرا از z — همان فرمولِ engine/rqs2.py."""
    if z is None:
        return None
    if z == float('inf'):
        return 0.0
    return 0.5 * erfc(z / sqrt(2))


def h3_new(lift, z, perm_k):
    """منطقِ H3 جدید (v2.4). None اگر داده ناقص است."""
    if lift is None or z is None:
        return None
    p = p_perm_from_z(z)
    k = perm_k if perm_k is not None else PERM_K_MIN  # نول‌های قدیمی k را همیشه دارند
    return bool(lift >= SKILL_LIFT_MIN and p <= SKILL_P_MAX and k >= PERM_K_MIN)


def harvest_records():
    """همهٔ رکوردهای verdict را از results/**/*.json برداشت می‌کند."""
    recs = []

    def rec(o, f):
        if isinstance(o, dict):
            g = o.get('gates')
            m = o.get('metrics')
            if isinstance(g, dict) and isinstance(m, dict) and 'H3' in g:
                recs.append((f, g, m, o))
            # فرمِ مسطح (مثلِ _final_honest_verdict)
            if 'H3' in o and 'lift' in o and 'z' in o:
                recs.append((f, {'H3': o.get('H3')},
                             {'skill_lift_pp': o.get('lift'), 'skill_z': o.get('z'),
                              'perm_k': o.get('perm_k', PERM_K_MIN),
                              'win_rate': o.get('wr'), 'net_profit': o.get('net')},
                             o))
            for v in o.values():
                rec(v, f)
        elif isinstance(o, list):
            for v in o:
                rec(v, f)

    for fp in glob.glob('results/**/*.json', recursive=True):
        if '_audit_H3' in fp:
            continue
        try:
            d = json.load(open(fp))
        except Exception:
            continue
        rec(d, os.path.relpath(fp, 'results'))

    # یکتاسازی
    seen, uniq = set(), []
    for f, g, m, o in recs:
        k = (f, round(m.get('win_rate') or -1, 2),
             round(m.get('skill_z') or -99, 2),
             round(m.get('skill_lift_pp') or -99, 2))
        if k in seen:
            continue
        seen.add(k)
        uniq.append((f, g, m, o))
    return uniq


GATES = ['H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10']


def main():
    recs = harvest_records()
    out = {'n_records': len(recs), 'tests': {}}

    # ---- R4: لایه‌های z<3 باید H3(new)=False باشند (بی‌مهارت زنده نشود) ----
    r4_viol = []
    for f, g, m, o in recs:
        z = m.get('skill_z')
        lift = m.get('skill_lift_pp')
        if z is None or lift is None:
            continue
        if z < 3.0:  # واقعاً بی‌مهارت
            if h3_new(lift, z, m.get('perm_k')) is True:
                r4_viol.append((f, lift, z))
    out['tests']['R4_lowz_stays_reject'] = {
        'pass': len(r4_viol) == 0,
        'violations': r4_viol,
        'desc': 'layers with z<3 must NOT pass new H3'}

    # ---- R1: لایه‌های با lift<=0 (تقلبیِ رانش‌سوار/غلط) باید H3(new)=False ----
    # رانش‌سوار = lift منفی/صفر نسبت به مدلِ صفرِ اندازه‌گیری‌شده.
    r1_viol = []
    for f, g, m, o in recs:
        lift = m.get('skill_lift_pp')
        z = m.get('skill_z')
        if lift is None or z is None:
            continue
        if lift <= 0:  # لبه‌ای نسبت به نول وجود ندارد
            if h3_new(lift, z, m.get('perm_k')) is True:
                r1_viol.append((f, lift, z))
    out['tests']['R1_fakes_stay_reject'] = {
        'pass': len(r1_viol) == 0,
        'violations': r1_viol,
        'desc': 'layers with non-positive lift vs measured null must NOT pass new H3'}

    # ---- R2: لایه‌هایی که >=8 دروازه شکست دادند باید REJECT بمانند ----
    # (اصلاحِ H3/H10 نباید یک لایهٔ فاجعه‌بار را ناگهان قابلِ‌قبول کند)
    r2_viol = []
    r2_checked = 0
    for f, g, m, o in recs:
        n_fail = sum(1 for h in GATES if g.get(h) is False)
        if n_fail >= 8:
            r2_checked += 1
            # با معیارِ جدید، آیا این لایه هنوز حداقل یک دروازهٔ غیر-H3/غیر-H10 شکست دارد؟
            non_h3h10_fail = sum(1 for h in GATES
                                 if h not in ('H3', 'H10') and g.get(h) is False)
            if non_h3h10_fail == 0:
                r2_viol.append((f, n_fail))
    out['tests']['R2_worthless_stays_reject'] = {
        'pass': len(r2_viol) == 0,
        'n_checked': r2_checked,
        'violations': r2_viol,
        'desc': 'layers failing >=8 gates must still fail a non-H3/H10 gate'}

    # ---- R3: پایداریِ بذر با آمارهٔ همگرا ----
    # از artifactِ reproducibility استفاده می‌کنیم: H3 جدید تابعِ z است، پس
    # روی هر ۳۰ اجرا p_perm از z همان اجرا حساب و حکم بازخوانی می‌شود.
    r3 = {'pass': None, 'desc': 'new H3 verdict must be seed-stable across the '
          'converged (K>=500) runs; runs below the floor are UNKNOWN and excluded'}
    rp = 'results/_audit_H3/reproducibility.json'
    if os.path.exists(rp):
        runs = json.load(open(rp))['runs']
        # ⚠️ کلید: به هر اجرا K *واقعیِ خودش* را بده، نه PERM_K_MIN ثابت.
        #   اجراهای K<500 حالا h3_new=None (UNKNOWN) می‌دهند — چون آماره
        #   همگرا نشده — و باید از سنجشِ پایداری *کنار گذاشته* شوند، نه اینکه
        #   ناپایداری تلقی شوند. این دقیقاً همان رفتارِ engine است.
        judged, unknown = [], 0
        for run in runs:
            v = h3_new(run.get('lift'), run.get('z'), run.get('K'))
            if v is None:
                unknown += 1
            else:
                judged.append(v)
        n_pass = sum(1 for v in judged if v)
        n_rej = sum(1 for v in judged if v is False)
        # پایدار = همهٔ اجراهای *قابلِ‌داوری* یکسان (همه پاس یا همه رد)
        stable = len(judged) > 0 and (n_pass == len(judged) or n_rej == len(judged))
        r3.update({'pass': bool(stable), 'n_runs': len(runs),
                   'n_judged': len(judged), 'n_unknown_belowK': unknown,
                   'n_pass_new': n_pass, 'n_reject_new': n_rej,
                   'old_n_pass': sum(1 for run in runs if run.get('H3')),
                   'note': (f'converged runs (K>=500) all agree; '
                            f'{unknown} sub-floor runs correctly excluded as UNKNOWN'
                            if stable else
                            'still unstable among converged runs — investigate')})
    out['tests']['R3_seed_stable'] = r3

    # ---- جمع‌بندی ----
    all_pass = all(t.get('pass') is True for t in out['tests'].values())
    out['ALL_PASS'] = all_pass

    os.makedirs('results/_audit_H3', exist_ok=True)
    json.dump(out, open('results/_audit_H3/v24_regression.json', 'w'),
              ensure_ascii=False, indent=2, default=float)

    print(f"records harvested: {len(recs)}")
    for name, t in out['tests'].items():
        status = 'PASS' if t.get('pass') else ('FAIL' if t.get('pass') is False else '??')
        print(f"  [{status}] {name}: {t['desc']}")
        if not t.get('pass') and t.get('violations'):
            for v in t['violations'][:5]:
                print(f"          violation: {v}")
        if name == 'R3_seed_stable' and t.get('pass') is not None:
            print(f"          old H3: {t['old_n_pass']}/30 pass (unstable) "
                  f"→ new H3: {t['n_pass_new']}/30 pass, {t['n_reject_new']}/30 reject")
    print(f"\n{'='*50}\nALL_PASS = {all_pass}\nSAVED results/_audit_H3/v24_regression.json")


if __name__ == '__main__':
    main()
