# -*- coding: utf-8 -*-
"""
S176-HIGH2-STOPENTRY — کاربردِ «مکانیزمِ ورودِ stop-entry» (فصلِ ۴ کتابِ Al Brooks)
                       روی لایهٔ موجودِ High-2 (S168) — راهِ اولِ پروژه: «بهبودِ وضعیت».

قانونِ شمارهٔ ۱: هدف سودِ خالصِ بیشتر (XAUUSD+EURUSD)؛ WR کفِ ۴۰٪ هر لایه.

انگیزه (از finalizeِ S176): سیگنالِ signal-bar فصل ۴ ۹۶٪ با High-2 همپوشان است، و
مکانیزمِ تأییدِ stop-entry به‌طورِ سیستماتیک WR↑/PF↑/net↑ داد. طبقِ قانونِ همپوشانی،
همین مکانیزم را مستقیماً روی خودِ High-2 (S168) اعمال می‌کنیم:

  • BASE (S168 اصلی): ورود market-on-next-open روی کندلِ رخدادِ High-2.
  • CONF (بهبودِ فصل ۴): ورود فقط اگر کندلِ *بعد از* رخدادِ High-2، high آن را با ≥۱ تیک
    رد کند (follow-through). در غیرِ این صورت سفارش لغو ⇒ تلهٔ High-2ی ناموفق حذف می‌شود.

گیتِ پذیرشِ «بهبود»: باید **هم net↑ و هم WR≥base و WR≥40** و هر دو نیمه مثبت و
walk-forward ۴/۴ باشد (بهبودِ واقعی، نه صرفاً کاهشِ پوشش).
"""
import os, sys, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import s172_brooks_two_legs as S
import s168_brooks_high2_low2 as H2
from engine import indicators as ind

TICK = {'XAUUSD': 0.01, 'EURUSD': 0.00001}
WR_FLOOR = 40.0


def high2_entry(df, asset, ef, es, confirm):
    """آرایهٔ سیگنالِ ورودِ long برای High-2؛ confirm=True ⇒ stop-entry فصل ۴."""
    long_evt, _ = H2.count_high2_low2(df, ef, es)
    h = df['high'].to_numpy()
    n = len(df)
    if not confirm:
        return long_evt.copy()
    tick = TICK[asset]
    sig = np.zeros(n, dtype=bool)
    idx = np.where(long_evt)[0]
    for i in idx:
        j = i + 1
        if j >= n:
            continue
        if h[j] > h[i] + tick:      # follow-through: کندلِ بعد high رخداد را رد کرد
            sig[j] = True           # سیگنالِ ورود روی j ⇒ sim واردِ open[j+1]
    return sig


def metrics(df, sig, asset, sl, tp, mh):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return None
    hv = S.halves(df, sig, z, sl, tp, mh, asset)
    # walk-forward ۴ پنجره
    wf = []
    n = len(df)
    for k in range(4):
        a = int(n * k / 4); b = int(n * (k + 1) / 4)
        sub = df.iloc[a:b].reset_index(drop=True)
        s2 = high2_entry(sub, asset, EF, ES, sig is not None and CONFIRM_FLAG)
        z2 = np.zeros(len(sub), bool)
        if s2.sum() < 8:
            wf.append((0.0, 0.0, 0)); continue
        t2 = S.sim(sub, s2, z2, sl, tp, mh, asset)
        st2 = S.stats(t2, asset)
        wf.append((round(st2['net'], 1), round(st2['wr'], 1), int(st2['n'])))
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    return dict(net=round(r['net'], 1), wr=round(r['wr'], 2), n=int(r['n']),
                pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=wf, wf_ok=wf_ok, both_ok=both_ok)


# متغیرهای سراسری برای walk-forward داخلِ metrics
EF, ES, CONFIRM_FLAG = 20, 50, False


def run_pair(df, asset, ef, es, sl, tp, mh):
    global EF, ES, CONFIRM_FLAG
    EF, ES = ef, es
    CONFIRM_FLAG = False
    base = metrics(df, high2_entry(df, asset, ef, es, False), asset, sl, tp, mh)
    CONFIRM_FLAG = True
    conf = metrics(df, high2_entry(df, asset, ef, es, True), asset, sl, tp, mh)
    return base, conf


def main():
    print("=" * 100)
    print("S176-HIGH2-STOPENTRY — بهبودِ High-2 (S168) با مکانیزمِ ورودِ stop-entry (فصلِ ۴)")
    print("گیتِ بهبود: net↑ و WR≥base و WR≥40 و هر دو نیمه + WF ۴/۴.")
    print("=" * 100)

    # پیکربندی‌های آزمون: config رسمیِ S168 + چند SL/TP/mh نزدیک
    configs = [
        (20, 50, 300, 450, 32),   # config رسمیِ S168
        (20, 50, 300, 450, 48),
        (20, 50, 250, 375, 32),
        (20, 50, 250, 375, 48),
        (20, 50, 300, 450, 96),
        (10, 30, 300, 450, 32),
    ]
    results = []
    for asset in ('XAUUSD', 'EURUSD'):
        df = S.lastn(S.load(f'{asset}_M15'))
        print(f"\n### {asset} (rows={len(df)}) ###")
        for (ef, es, sl, tp, mh) in configs:
            base, conf = run_pair(df, asset, ef, es, sl, tp, mh)
            if base is None or conf is None:
                print(f"  ema{ef}/{es} SL{sl}/TP{tp} mh{mh}: n<30 (رد)")
                continue
            d_net = conf['net'] - base['net']
            improve = (conf['net'] > base['net'] and conf['wr'] >= base['wr']
                       and conf['wr'] >= WR_FLOOR and conf['both_ok'] and conf['wf_ok'])
            mark = '✅بهبود' if improve else '  '
            print(f"  {mark} ema{ef}/{es} SL{sl}/TP{tp} mh{mh}:")
            print(f"       BASE net=${base['net']:+,.0f} WR={base['wr']}% n={base['n']} PF={base['pf']} WFok={base['wf_ok']}")
            print(f"       CONF net=${conf['net']:+,.0f} WR={conf['wr']}% n={conf['n']} PF={conf['pf']} WFok={conf['wf_ok']}  Δnet=${d_net:+,.0f}")
            results.append(dict(asset=asset, ef=ef, es=es, sl=sl, tp=tp, mh=mh,
                                base=base, conf=conf, d_net=round(d_net, 1),
                                improve=bool(improve)))

    os.makedirs('results', exist_ok=True)
    with open('results/_s176_high2_stopentry.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("\n" + "=" * 100)
    imp = [r for r in results if r['improve']]
    if imp:
        best = max(imp, key=lambda r: r['d_net'])
        print(f"✅ بهبودِ معتبر یافت شد: {best['asset']} ema{best['ef']}/{best['es']} "
              f"SL{best['sl']}/TP{best['tp']} mh{best['mh']} ⇒ Δnet=${best['d_net']:+,.0f} "
              f"(WR {best['base']['wr']}→{best['conf']['wr']})")
    else:
        print("⛔ هیچ بهبودِ معتبری (net↑ و WR≥base و گیتِ کامل) یافت نشد.")
    print("✅ ذخیره شد: results/_s176_high2_stopentry.json")


if __name__ == '__main__':
    main()
