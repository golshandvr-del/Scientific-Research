# -*- coding: utf-8 -*-
"""
S178-AGREEMENT-FILTER — استفاده از «بخشِ همپوشانِ» S178 به‌عنوان فیلترِ تأیید روی
اجتماعِ LONGِ طلا (High-2 ∪ time-drift). پاسخ به پرسشِ روش‌شناختیِ کلیدیِ کاربر.
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

منشأ پرسش (کاربر):
  «استراتژی‌های زیادی داشتیم که با درصدِ ناهمپوشان سودِ خالص را بیشتر کردند (مثلِ S178).
   آیا از بخشِ *همپوشانِ* آن‌ها هم‌زمان به‌عنوان فیلتر استفاده کردیم؟»

شکافِ کشف‌شده:
  • برای S178 فقط «سهمِ مستقل» (indep = S178 ∧ ¬recent(union)) به رکورد افزوده شد (+$1,533).
  • «بخشِ همپوشان» (۵۶٪) کاملاً کنار گذاشته شد تا double-counting رخ ندهد.
  • اما آن بخش خودش یک *سیگنالِ توافق* است: معاملاتی که هم لایهٔ قدیمی (union) و هم S178
    روی آن‌ها هم‌رأی‌اند. فرضیه: این زیرمجموعهٔ توافق WRِ بالاتری از کلِ union دارد ⇒
    می‌توان S178 را به‌عنوان *فیلترِ تأییدِ* union به‌کار برد و معاملاتِ ضعیفِ union را
    حذف کرد (راهِ اولِ پروژه: بهبود ⇒ WR↑ ⇒ سودِ کیفی↑).

روشِ آزمون (بار-به-بار، causal):
  union   = High-2(S168) ∪ time-drift-LONG   (تقریبِ اجتماعِ LONGِ طلا)
  agree   = union ∧ recent_w(S178)           (توافق: union که S178 هم اخیراً تأیید کرد)
  reject  = union ∧ ¬recent_w(S178)          (معاملاتی که S178 رد می‌کند)

  سه سبد را با گیتِ یکسان (SL/TP/mh) شبیه‌سازی و مقایسه می‌کنیم:
    BASE   = کلِ union
    AGREE  = زیرمجموعهٔ توافق
    REJECT = زیرمجموعهٔ ردشده
  اگر  WR(AGREE) ≥ WR(BASE)  و  WR(AGREE) ≥ 40  و  WR(REJECT) < WR(AGREE)
  ⇒ فیلترِ توافق واقعاً «گندم را از کاه» جدا می‌کند.

  Δ net قابلِ ثبت = net(AGREE) − net(BASE_overlap_only)؟  نه — چون union خودش لایهٔ
  مستقلِ پروژه نیست (proxy است). این آزمون *اکتشافیِ روش‌شناختی* است تا نشان دهد آیا
  «فیلترِ توافق» مکانیزمِ معتبری است؛ اگر بله، روی لایه‌های *واقعیِ* ACCEPTED (گامِ بعد)
  اعمال می‌شود.

خروجی: چاپِ کنسول + results/_s178_agreement_filter.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S            # load, lastn, sim, stats, halves
import s174_brooks_sell_climax_reversal as SC   # walk_forward
import s174_finalize as F                    # high2/time-drift/overlap helpers
import s178_brooks_two_bar_reversal as T
from engine import indicators as ind

WR_FLOOR = 40.0
OVERLAP_BARS = 12

CFG = dict(asset='XAUUSD', side='long', ema_fast=10, ema_slow=30,
           body_frac=0.6, size_tol=1.0, lb=40, sl=300, tp=450, mh=96)


def basket_stats(df, sig, asset, sl, tp, mh, label):
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
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok)


def main():
    print("=" * 100)
    print("S178-AGREEMENT-FILTER — «بخشِ همپوشانِ» S178 به‌عنوان فیلترِ تأییدِ اجتماعِ LONGِ طلا")
    print("گیت: WR(AGREE)≥WR(BASE) و ≥40 و WR(REJECT)<WR(AGREE). هدف=WR↑ ⇒ سودِ کیفی↑.")
    print("=" * 100)

    asset = CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})\n")

    # سیگنالِ S178 (causal) + پنجرهٔ recent
    s178 = T.two_bar_reversal_signals(df, CFG['side'], CFG['body_frac'], CFG['size_tol'],
                                      CFG['lb'], CFG['ema_fast'], CFG['ema_slow'])

    # اجتماعِ LONGِ طلا (proxy)
    h2 = F.brooks_high2_long(df)
    td = F.time_drift_long(df)
    union = h2 | td
    print(f"سیگنال‌ها: S178={int(s178.sum())}  High-2={int(h2.sum())}  time-drift={int(td.sum())}  union={int(union.sum())}\n")

    results = {}
    base = basket_stats(df, union, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'BASE=union')
    print(f"BASE   (کلِ union)   : net={base.get('net'):+.0f} WR={base.get('wr')}% n={base['n']} PF={base.get('pf')}")
    results['base'] = base

    # اسکنِ پنجرهٔ recent برای فیلترِ توافق
    print("\nاسکنِ پنجرهٔ توافق w ∈ {3,6,12,24}:")
    best = None
    scan = []
    for w in (3, 6, 12, 24):
        recent = pd.Series(s178.astype(float)).rolling(w, min_periods=1).max().to_numpy() > 0
        agree = union & recent
        reject = union & (~recent)
        na, nr = int(agree.sum()), int(reject.sum())
        if na < 30:
            print(f"  w={w:2d}: AGREE n={na} (<30) — رد")
            scan.append(dict(w=w, agree_n=na, skip=True)); continue
        a = basket_stats(df, agree, asset, CFG['sl'], CFG['tp'], CFG['mh'], f'AGREE(w={w})')
        rj = basket_stats(df, reject, asset, CFG['sl'], CFG['tp'], CFG['mh'], f'REJECT(w={w})')
        d_wr = round(a['wr'] - base['wr'], 2)
        keep_frac = round(na / (na + nr) * 100, 1)
        # آیا فیلتر «گندم را از کاه» جدا می‌کند؟
        separates = (a['wr'] >= base['wr']) and (a['wr'] >= WR_FLOOR) and (rj.get('wr', 999) < a['wr'])
        flag = '✅ جداساز' if separates else '—'
        print(f"  w={w:2d}: AGREE net={a['net']:+.0f} WR={a['wr']}% n={na} | "
              f"REJECT net={rj.get('net'):+.0f} WR={rj.get('wr')}% n={nr} | "
              f"ΔWR={d_wr:+.2f}pp keep={keep_frac}% {flag}")
        rec = dict(w=w, agree=a, reject=rj, d_wr=d_wr, keep_frac=keep_frac, separates=separates)
        scan.append(rec)
        if separates and (best is None or a['wr'] > best['agree']['wr']):
            best = rec

    print("\n" + "=" * 100)
    if best:
        a = best['agree']; rj = best['reject']
        print(f"✅ فیلترِ توافق کار می‌کند (w={best['w']}): WR از {base['wr']}% به {a['wr']}% رفت "
              f"(ΔWR={best['d_wr']:+.2f}pp)؛ زیرمجموعهٔ ردشده WR={rj['wr']}% بسیار پایین‌تر.")
        print(f"   ⇒ مکانیزمِ «فیلترِ توافقِ S178» معتبر است ⇒ روی لایه‌های *واقعیِ* ACCEPTED آزموده می‌شود.")
    else:
        print("⛔ فیلترِ توافقِ S178 روی اجتماعِ LONGِ طلا (proxy) جداسازیِ معناداری نداد.")
    print("=" * 100)

    out = dict(strategy='S178_agreement_filter', cfg=CFG, base=base, scan=scan,
               best_w=(best['w'] if best else None))
    with open('results/_s178_agreement_filter.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s178_agreement_filter.json")


if __name__ == '__main__':
    main()
