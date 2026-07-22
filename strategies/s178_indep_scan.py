# -*- coding: utf-8 -*-
"""
S178-INDEP-SCAN — جست‌وجوی کاندیدی که «سهمِ مستقلِ» آن (پس از حذفِ همپوشانی با اجتماعِ
LONGِ طلا) گیتِ کاملِ ۴-گانه را پاس کند.

منطق: finalize نشان داد کاندیدِ برتر (net +4052) سهمِ مستقلِ n=123، net=+976 دارد اما
تنها W3=−$52 (بسیار مرزی) گیتِ walk-forward را رد کرد. چون XAUUSD-LONGِ two-bar تعدادِ
زیادی کاندیدِ پذیرفته با n بالا دارد، شاید یکی از آن‌ها سهمِ مستقلِ WF-پایدار بدهد.
این اسکن برای هر کاندیدِ پذیرفته، سهمِ مستقل + گیتِ کامل را می‌سنجد و OKها را چاپ می‌کند.
(anti-overfitting: فقط کاندیدهایی که *از قبل* در گریدِ اصلی گیتِ خام را پاس کرده‌اند.)
"""
import os, sys, json
import numpy as np
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S
import s174_brooks_sell_climax_reversal as SC
import s174_finalize as F
import s178_brooks_two_bar_reversal as T
import s178_finalize as FIN

WR_FLOOR = 40.0


def main():
    df = S.lastn(S.load('XAUUSD_M15'))
    h2 = F.brooks_high2_long(df)
    td = F.time_drift_long(df)
    union = h2 | td

    d = json.load(open('results/_s178_two_bar_reversal.json'))
    acc = [x for x in d['accepted'] if x['asset'] == 'XAUUSD' and x['side'] == 'long']
    # مرتب بر اساس net نزولی؛ فقط کاندیدهای با n خامِ کافی
    acc.sort(key=lambda x: x['net'], reverse=True)

    print("=" * 100)
    print(f"S178-INDEP-SCAN — سنجشِ سهمِ مستقلِ {len(acc)} کاندیدِ پذیرفتهٔ XAUUSD-LONG")
    print("=" * 100)

    winners = []
    for x in acc:
        sig = T.two_bar_reversal_signals(df, 'long', x['body_frac'], x['size_tol'],
                                         x['lb'], x['ema_fast'], x['ema_slow'])
        indep = F.independent_share(sig, union)
        r = FIN.full_gate(df, indep, 'XAUUSD', x['sl'], x['tp'], x['mh'], 'indep')
        ov = F.bar_overlap_pct(sig, union)
        if r.get('net') is None:
            continue
        tag = 'OK ✅' if r['ok'] else 'x'
        line = (f"  [{tag}] ema{x['ema_fast']}/{x['ema_slow']} bf{x['body_frac']} st{x['size_tol']} "
                f"lb{x['lb']} SL{x['sl']}/TP{x['tp']}/mh{x['mh']} | ov={ov:.0f}% "
                f"indep: net={r['net']:+.0f} WR={r['wr']:.1f} n={r['n']} PF={r['pf']} "
                f"WF={'/'.join(f'{w[0]:+.0f}' for w in r['wf'])}")
        if r['ok']:
            winners.append(dict(cfg=x, indep=r, overlap=round(ov, 1)))
            print(line, flush=True)

    print("\n" + "=" * 100)
    if winners:
        winners.sort(key=lambda w: w['indep']['net'], reverse=True)
        print(f"✅ {len(winners)} کاندید با سهمِ مستقلِ گیت-پاس یافت شد. بهترین:")
        w = winners[0]
        print(f"   indep net=${w['indep']['net']:+,.0f} WR={w['indep']['wr']}% n={w['indep']['n']} "
              f"overlap={w['overlap']}% cfg={w['cfg']['ema_fast']}/{w['cfg']['ema_slow']} "
              f"bf{w['cfg']['body_frac']} st{w['cfg']['size_tol']} lb{w['cfg']['lb']} "
              f"SL{w['cfg']['sl']}/TP{w['cfg']['tp']}/mh{w['cfg']['mh']}")
    else:
        print("⛔ هیچ کاندیدی سهمِ مستقلِ گیت-پاس نداد (همه در ≥۱ پنجرهٔ WF منفی).")
    print("=" * 100)

    with open('results/_s178_indep_scan.json', 'w') as f:
        json.dump(dict(n_candidates=len(acc), winners=winners), f,
                  ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s178_indep_scan.json")


if __name__ == '__main__':
    main()
