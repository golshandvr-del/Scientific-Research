# -*- coding: utf-8 -*-
"""
s332_finetune_m15.py — ریز-تنظیمِ کشفِ طلاییِ M15

کشفِ فاز۲ بانک: ترکیبِ (r2>0.60 & hurst>0.55) روی XAUUSD M15 به gates=011111 رسید
(فقط G0 مانده): WR=58.5٪, PF=1.70, DD=3.2٪, MCL=3, n=41 — تنها ~۱.۵٪ WR کم داریم.

این اسکریپت آن آخرین گام را با «قانونِ شناوری» می‌بندد:
  • جستجوی ریزِ آستانه‌های r2/hurst (غیررند: 0.58..0.72 / 0.52..0.66).
  • جستجوی ریزِ TP/SL حولِ (285,190) — همه غیررند.
  • افزودنِ فیلترِ چهارمِ کیفیت (corr_t جهت‌دار، er، chop، not_overext) در صورتِ نیاز.
هدف: WR≥60 با حفظِ PF/DD/MCL/WF ⇒ RQS+≥80.

خروجی افزایشی به results/_s332_ft_m15.log
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import strategies.s332_squeeze_rqs_revival as S
import strategies.bank_filters as BF


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def fmt(name, tp, sl, r):
    m = r['metrics']
    return (f"RQS={r['rqs_score']:5.1f} {'PASS' if r['passed'] else 'fail'} {name:38s} "
            f"tp={tp} sl={sl} WR={m['win_rate']:.1f} net={m['net_profit']:.0f} PF={m['profit_factor']:.2f} "
            f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} n={m['n_trades']} {gates_str(r)}")


def main():
    sym, tf = 'XAUUSD', 'M15'
    df = S.load_tf(sym, tf)
    logf = open('results/_s332_ft_m15.log', 'w', encoding='utf-8')

    def out(s):
        print(s)
        logf.write(s + '\n')
        logf.flush()

    sig = S.build_squeeze_signal(df, sqz_pct=0.25, breakout_lookback=6)
    out(f"== {sym} {tf} finetune | squeeze={int(sig.sum())} ==")

    # مقادیرِ خامِ اندیکاتورها (یک‌بار)
    out("... محاسبهٔ اندیکاتورها ...")
    r2v = BF.r2(df, 20)
    hu = BF.hurst(df, 64)
    ct = BF.corr_t(df, 20)
    er = BF.kaufman_er(df, 10)
    ch = BF.chop(df, 14)
    eda = BF.ema_dist_atr(df)
    out("... آماده ...")

    def B(a):
        return np.nan_to_num(a.astype(float), nan=0.0).astype(bool)

    mh = 64
    best = []  # (rqs, passed, desc, tp, sl)

    # فاز A: جستجوی ریزِ آستانه‌های r2/hurst × TP/SL (بدونِ فیلترِ چهارم)
    out("\n--- فاز A: ریزتنظیمِ r2/hurst × TP/SL ---")
    tpsl_list = [(255, 170), (285, 190), (315, 210), (345, 230), (285, 205), (315, 195)]
    for r2t in [0.58, 0.62, 0.66, 0.70]:
        for hut in [0.52, 0.55, 0.58, 0.62]:
            mask = B((r2v > r2t) & (hu > hut))
            for tp, sl in tpsl_list:
                r, _ = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=mask)
                m = r['metrics']
                if m['n_trades'] < 30:
                    continue
                desc = f"r2>{r2t}&hurst>{hut}"
                if r['passed'] or (gates_str(r).count('1') >= 5 and m['win_rate'] >= 56):
                    out("  " + fmt(desc, tp, sl, r))
                best.append((r['rqs_score'], r['passed'], desc, tp, sl, m['win_rate'], gates_str(r)))

    # فاز B: افزودنِ فیلترِ چهارم روی بهترین‌های نزدیک به مرز
    out("\n--- فاز B: فیلترِ چهارمِ کمکی روی (r2>0.62 & hurst>0.55) ---")
    base = B((r2v > 0.62) & (hu > 0.55))
    fourth = {
        'corr_t>0.55': B(ct > 0.55),
        'corr_t>0.65': B(ct > 0.65),
        'er>0.35': B(er > 0.35),
        'er>0.45': B(er > 0.45),
        'chop<35': B(ch < 35),
        'chop<30': B(ch < 30),
        'not_overext<1.5': B(eda < 1.5),
        'eda_in_band': B((eda > 0.0) & (eda < 2.5)),
    }
    for fname, fmask in fourth.items():
        mask = base & fmask
        for tp, sl in [(285, 190), (315, 210), (345, 230)]:
            r, _ = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=mask)
            m = r['metrics']
            if m['n_trades'] < 30:
                continue
            desc = f"r2>0.62&hurst>0.55&{fname}"
            out("  " + fmt(desc, tp, sl, r))
            best.append((r['rqs_score'], r['passed'], desc, tp, sl, m['win_rate'], gates_str(r)))

    # خلاصه
    best.sort(reverse=True)
    out("\n=== ۱۲ نتیجهٔ برتر بر اساسِ RQS ===")
    for rq, ps, desc, tp, sl, wr, g in best[:12]:
        out(f"  RQS={rq:5.1f} {'PASS' if ps else 'fail'} WR={wr:.1f} {g} {desc} tp={tp} sl={sl}")
    passes = [b for b in best if b[1]]
    out(f"\n{'✅ '+str(len(passes))+' ترکیبِ PASS!' if passes else '❌ هنوز PASS نشد (نزدیک‌ترین بالا).'}")
    logf.close()


if __name__ == '__main__':
    main()
