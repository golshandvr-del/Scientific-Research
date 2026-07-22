# -*- coding: utf-8 -*-
"""
S178→S168 AGREEMENT-FILTER — اعمالِ «فیلترِ توافقِ S178» روی لایهٔ *واقعیِ* ACCEPTED
یعنی S168 (Brooks High-2 LONG طلا). پاسخِ عملی به پرسشِ روش‌شناختیِ کاربر.
================================================================================
هدف: بیشینه‌سازیِ سودِ خالص؛ WR فقط کفِ ۴۰٪.

S168 (ثبت‌شده): High-2 LONG طلا، EMA20/50، SL300/TP450، max_hold=32،
  net=+$4,137، WR=48.8٪، n≈… (لایهٔ فعالِ رکورد).

پرسش: آیا «حضورِ اخیرِ یک two-bar-reversalِ S178» می‌تواند معاملاتِ ضعیفِ S168 را حذف کند
و WR/کیفیتِ آن را بالا ببرد؟ (راهِ اولِ پروژه: بهبود.)

سه سبد با پارامترِ *دقیقِ* S168 (EMA20/50, SL300/TP450, mh32):
  FULL    = کلِ سیگنال‌های S168 High-2
  AGREE   = S168 ∧ recent_w(S178)     (توافقِ دو لایه)
  REJECT  = S168 ∧ ¬recent_w(S178)    (بدونِ تأییدِ S178)

سنجه‌ها: net, WR, n, PF, halves, walk-forward.
تصمیم: اگر WR(AGREE) بالاتر و REJECT عمدتاً زیانده/کم‌کیفیت ⇒ فیلتر «راهِ اولِ» بهبود است.

⚠️ نکتهٔ double-counting: بخشی از AGREE ممکن است با «S178-independent» (که قبلاً +$1,533
ثبت شد) هم‌پوشان باشد. برای Δِ *قابلِ ثبتِ خالص* روی S168، فقط بهبودِ WRِ خودِ S168 و
تغییرِ net آن گزارش می‌شود؛ ثبتِ نهایی محتاطانه و پس از بررسیِ هم‌پوشانی با S178-indep.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S            # load, lastn, sim, stats, halves
import s174_brooks_sell_climax_reversal as SC   # walk_forward
import s174_finalize as F                    # brooks_high2_long, time_drift_long
import s178_brooks_two_bar_reversal as T

WR_FLOOR = 40.0

# پارامترِ دقیقِ لایهٔ ثبت‌شدهٔ S168
S168 = dict(asset='XAUUSD', ema_fast=20, ema_slow=50, sl=300, tp=450, mh=32)
# کاندیدِ فیلترِ S178 (همان برندهٔ مستقل)
S178CFG = dict(side='long', ema_fast=10, ema_slow=30, body_frac=0.6, size_tol=1.0, lb=40)


def basket(df, sig, asset, sl, tp, mh, label):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] == 0:
        return dict(label=label, n=0, ok=False)
    hv = S.halves(df, sig, z, sl, tp, mh, asset)
    wf = SC.walk_forward(df, sig, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    return dict(label=label, net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None, h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok)


def main():
    print("=" * 100)
    print("S178→S168 AGREEMENT-FILTER — «فیلترِ توافقِ S178» روی لایهٔ واقعیِ S168 (High-2 LONG طلا)")
    print("=" * 100)

    asset = S168['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})\n")

    # لایهٔ واقعیِ S168 (با پارامترِ دقیقِ ثبت‌شده)
    s168 = F.brooks_high2_long(df, ef=S168['ema_fast'], es=S168['ema_slow'])
    # سیگنالِ S178
    s178 = T.two_bar_reversal_signals(df, S178CFG['side'], S178CFG['body_frac'],
                                      S178CFG['size_tol'], S178CFG['lb'],
                                      S178CFG['ema_fast'], S178CFG['ema_slow'])
    print(f"سیگنال‌ها: S168 High-2={int(s168.sum())}  S178 two-bar={int(s178.sum())}\n")

    full = basket(df, s168, asset, S168['sl'], S168['tp'], S168['mh'], 'FULL=S168')
    print(f"FULL   (کلِ S168) : net={full.get('net'):+.0f} WR={full.get('wr')}% n={full['n']} "
          f"PF={full.get('pf')} WF_ok={full.get('wf_ok')}")

    print("\nاسکنِ پنجرهٔ توافق w ∈ {6,12,24,48}:")
    scan = []
    best = None
    for w in (6, 12, 24, 48):
        recent = pd.Series(s178.astype(float)).rolling(w, min_periods=1).max().to_numpy() > 0
        agree = s168 & recent
        reject = s168 & (~recent)
        na, nr = int(agree.sum()), int(reject.sum())
        a = basket(df, agree, asset, S168['sl'], S168['tp'], S168['mh'], f'AGREE(w={w})') if na >= 30 else dict(label=f'AGREE(w={w})', n=na, ok=False)
        rj = basket(df, reject, asset, S168['sl'], S168['tp'], S168['mh'], f'REJECT(w={w})') if nr >= 30 else dict(label=f'REJECT(w={w})', n=nr, ok=False)
        d_wr = round(a['wr'] - full['wr'], 2) if a.get('wr') is not None else None
        keep = round(na / max(1, na + nr) * 100, 1)
        # آیا فیلتر بهبود می‌دهد؟ (WR بالاتر، AGREE هنوز net مثبت و WR≥40)
        improves = bool(a.get('wr') is not None and a['wr'] >= full['wr'] and a['wr'] >= WR_FLOOR and a['net'] > 0)
        rej_worse = bool(rj.get('wr') is not None and rj['wr'] < full['wr'])
        flag = '✅ بهبود' if improves else '—'
        awr = a.get('wr'); anet = a.get('net'); rwr = rj.get('wr'); rnet = rj.get('net')
        print(f"  w={w:2d}: AGREE net={_f(anet)} WR={_f(awr,'%')} n={na} | "
              f"REJECT net={_f(rnet)} WR={_f(rwr,'%')} n={nr} | ΔWR={d_wr} keep={keep}% {flag}")
        rec = dict(w=w, agree=a, reject=rj, d_wr=d_wr, keep_frac=keep,
                   improves=improves, rej_worse=rej_worse)
        scan.append(rec)
        if improves and (best is None or a['wr'] > best['agree']['wr']):
            best = rec

    print("\n" + "=" * 100)
    if best:
        a = best['agree']; rj = best['reject']
        # Δ net نسبت به FULL (اگر معاملاتِ REJECT حذف شوند)
        d_net = round(a['net'] - full['net'], 1)
        print(f"✅ فیلترِ توافقِ S178 روی S168 بهبود می‌دهد (w={best['w']}):")
        print(f"   WR: {full['wr']}% → {a['wr']}% (ΔWR={best['d_wr']:+.2f}pp) | "
              f"net: {full['net']:+.0f} → {a['net']:+.0f} (Δ={d_net:+.0f}) | keep={best['keep_frac']}%")
        print(f"   زیرمجموعهٔ REJECT: net={rj.get('net'):+.0f} WR={rj.get('wr')}% "
              f"({'کم‌کیفیت‌تر ✅' if best['rej_worse'] else 'مشابه'})")
        if d_net > 0:
            print(f"   ⚠️ توجه: حذفِ REJECT، net را کاهش داد (Δ={d_net:+.0f}) ⇒ فیلتر WR↑ می‌دهد اما"
                  f" اگر REJECT روی‌هم مثبت باشد، حذفش سودِ کل را کم می‌کند. تصمیم بر پایهٔ هدفِ سودِ خالص.")
    else:
        print("⛔ فیلترِ توافقِ S178 بهبودِ گیت-پاسی روی S168 نداد.")
    print("=" * 100)

    out = dict(strategy='S178_agree_on_S168', s168=S168, s178=S178CFG,
               full=full, scan=scan, best_w=(best['w'] if best else None))
    with open('results/_s178_agree_on_s168.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s178_agree_on_s168.json")


def _f(x, suf=''):
    return f"{x:+.0f}{suf}" if isinstance(x, (int, float)) else f"{x}{suf}"


if __name__ == '__main__':
    main()
