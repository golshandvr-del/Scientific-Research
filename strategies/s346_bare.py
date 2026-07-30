# -*- coding: utf-8 -*-
"""
S346 — داوریِ **پایه‌های بی‌فیلتر** (bare geometry, zero filters)
================================================================================
چرا این فایل لازم شد — یک سوگیریِ ساختاری در خطِ لولهٔ خودمان
--------------------------------------------------------------------------------
کلِ مسیرِ `s346_joint → stack_maxn` این فرضِ نانوشته را داشت که «هر لایه **حتماً**
به دست‌کم یک فیلتر نیاز دارد»: انباشتگرِ حریصانه با `stack=[]` شروع می‌کند و
گامی را می‌پذیرد که کیفیت را در **هر دو** بازه بهبود دهد؛ اگر هیچ فیلتری چنین
نکند، خروجی `reached=False` است — یعنی هندسه **رد** اعلام می‌شود، حتی اگر خودِ
پایه‌اش بدونِ هیچ فیلتری از تمامِ شش دروازه بگذرد.

این باگ روی `XAUUSD-W1` آشکار شد: پیمایشِ اختصاصی ۲۴ هندسهٔ واجد یافت که
بهترینشان `base n=145، WR=62.07٪، PF=1.55` بود — یعنی **در سطحِ لایهٔ پذیرفته‌شدهٔ
D1، بدونِ هیچ فیلتری** — ولی `run_card` گزارش داد `geoms_kept=0`، چون کف‌های
نمونه (min_nd/min_nh) اجازهٔ هیچ گامِ فیلتری نمی‌دادند و پایهٔ بی‌فیلتر هرگز
داوری نمی‌شد.

درسِ روش‌شناختی (قابلِ تعمیم به کلِ پروژه): **«بهبود» شاملِ حالتِ صفر هم هست.**
اگر جست‌وجو فقط در فضای «پایه + حداقل یک فیلتر» انجام شود، سادگی از فضای فرضیه
حذف شده است. سادگی خودش یک فرضیه است و باید مثلِ بقیه آزمون شود — مخصوصاً چون
پایهٔ بی‌فیلتر **کمترین درجهٔ آزادی** را دارد ⇒ کم‌ترین خطرِ اورفیت.

آنچه این درایور می‌کند
--------------------------------------------------------------------------------
۱) پیمایشِ کش‌شدهٔ کارت را می‌خواند (`{card}_sweep.json`).
۲) هندسه‌های واجد را با قیدِ «کیفیتِ پایه در **هر دو** نیم‌بازه» برمی‌گزیند
   (نه WR کل — تکرارپذیری از همان ابتدا).
۳) هر کدام را با **صفر فیلتر** به موتورِ رسمی می‌دهد
   (`simulate_trades(allow_overlap=False)` + `compute_rqs`).
۴) ابلیشنِ اجباریِ جهت را اجرا می‌کند تا «بتای جهت‌دار» از «لبهٔ متقارن» جدا شود.
۵) پس از هر هندسه چک‌پوینت می‌زند (سندباکسِ ناپایدار).
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.s346_verdict import adjudicate_row, geom_str  # noqa: E402

OUT = 'results/_scan_S346'


def run(card, min_base_n=100, wr_min_base=58.0, top_k=8, save=True,
        prefer_symmetric=True):
    """
    داوریِ پایه‌های بی‌فیلترِ یک کارت.

    prefer_symmetric : هندسه‌های `side='both'` را در صدرِ صف قرار می‌دهد، چون
        متقارن‌بودن پیش‌شرطِ «لبهٔ ساختاری» است و بتای جهت‌دار را از ابتدا کنار
        می‌گذارد (درسِ D1: پنج کاندیدای `long` با RQS+ ۸۴–۸۶ در ابلیشن سوختند).
    """
    src = f"{OUT}/{card}_sweep.json"
    if not os.path.exists(src):
        print(f"!!! no sweep cache for {card}: {src}", flush=True)
        return []
    rows = json.load(open(src))['rows']

    elig = [r for r in rows
            if r['base_n'] >= min_base_n and r['base_wr_min'] >= wr_min_base]
    if not elig:
        print(f"!!! {card}: no bare base with n>={min_base_n} and "
              f"wr_min>={wr_min_base}", flush=True)
        return []

    # صفِ ارزیابی: اول متقارن‌ها (به‌ترتیبِ کیفیت)، بعد بقیه (به‌ترتیبِ کیفیت)
    sym = sorted([r for r in elig if r['geom']['side'] == 'both'],
                 key=lambda r: -r['base_wr_min'])
    asym = sorted([r for r in elig if r['geom']['side'] != 'both'],
                  key=lambda r: -r['base_wr_min'])
    pool = (sym + asym) if prefer_symmetric else sorted(
        elig, key=lambda r: -r['base_wr_min'])
    pool = pool[:top_k]

    print(f"=== S346 BARE-BASE ADJUDICATION :: {card} ===", flush=True)
    print(f"    eligible={len(elig)} (symmetric={len(sym)}) -> adjudicating "
          f"{len(pool)} with ZERO filters, allow_overlap=False", flush=True)

    cache = {}
    out = []
    for i, r in enumerate(pool, 1):
        g = r['geom']
        print(f"\n[{i}/{len(pool)}] {geom_str(g)}", flush=True)
        print(f"   sweep(fast): base_n={r['base_n']} WR={r['base_wr']:.2f} "
              f"PF={r['base_pf']:.3f} | D n={r['n_d']} WR={r['wr_d']:.2f} "
              f"| H n={r['n_h']} WR={r['wr_h']:.2f}", flush=True)

        rec = dict(geom=g, filters=[], sweep=r)
        rr, _ = adjudicate_row(card, g, [], name='  FORMAL(bare)', cache=cache)
        rec['formal'] = rr

        # ⭐ ابلیشنِ اجباریِ جهت — بدونِ آن، بتای روند به‌جای لبه پذیرفته می‌شود
        print("   -- side ablation --", flush=True)
        rec['ablation'] = {}
        for sd in ('long', 'short', 'both'):
            if sd == g['side']:
                continue
            ra, _ = adjudicate_row(card, g, [], side=sd,
                                   name=f'  ABL side={sd}', cache=cache)
            rec['ablation'][sd] = ra
        out.append(rec)

        if save:
            with open(f"{OUT}/{card}_bare_verdict.json", 'w') as fh:
                json.dump(dict(card=card, results=out), fh, default=float)
            print(f"   [checkpointed {i}/{len(pool)}]", flush=True)

    print(f"\n============ {card} BARE-BASE SUMMARY ============", flush=True)
    for rec in out:
        f = rec['formal']
        m = f['metrics']
        fails = [k for k, v in f['gates'].items() if not v]
        ab = rec['ablation']
        sym_ok = all(v['passed'] for v in ab.values() if v)
        print(f"  RQS={f['rqs_score']:5.1f} {f['verdict']:6s} "
              f"n={m.get('n_trades', 0):4d} WR={m.get('win_rate', 0):5.2f} "
              f"PF={m.get('profit_factor', 0):5.2f} "
              f"net=${m.get('net_profit', 0):>9,.0f} "
              f"| fail={','.join(fails) or '-':10s} "
              f"| abl_all_pass={sym_ok} | {geom_str(rec['geom'])}", flush=True)
    return out


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-W1'
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    run(card, top_k=k)
