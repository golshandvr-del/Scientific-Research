# -*- coding: utf-8 -*-
"""
s450_paired_s382.py — S450 · بازپخشِ جفتی روی S382 (H4 LONG) — نسخهٔ ویژهٔ H4
================================================================================
بیمارِ سوم از پیش‌ثبتِ S450. طبق §3 پیش‌ثبت، «ساعتِ اول» از H4 قابلِ استخراج
نیست ⇒ نسخهٔ «کفِ کندلِ اولِ روزِ معاملاتی» تست و **جداگانه** گزارش می‌شود.

هشدارِ صادقانهٔ داده: در XAUUSD_H4 وقفهٔ روزانهٔ بروکر (~۶۰min) درونِ گپِ
عادیِ ۲۴۰min جذب می‌شود ⇒ با لنگرِ گپ، «روز» عملاً = هفته (گپ آخرهفته
~۳۱۲۰min). پس این تست در عمل «کفِ کندلِ اولِ *هفته*» است — عیناً همین را
گزارش می‌کنیم، تعمیمِ مفت نمی‌دهیم.

بازتولیدِ پایه = عینِ خطِ لولهٔ ACCEPT (strategies/s382_williamsr_momentum.py):
  سیگنال = گذرِ Williams %R(14) به بالای −۱۳ (رویداد)
  ورود = close کندلِ سیگنال (قراردادِ خودِ اسکریپتِ رسمی)
  SL = 1.5×median(ATR100)، TP = 1.5×SL، بدونِ max_hold، تک‌معامله
  کندلِ مبهم ⇒ SL (بدبینانه)، معاملهٔ بازِ آخرِ داده حذف.

نکتهٔ هزینه: شبیه‌سازِ S382 در pnl_pip هزینه کم نمی‌کند (هزینه در لایهٔ
rqs2/سرمایه اعمال می‌شود) ⇒ برای سازگاریِ جفتی، خروجِ قاعده هم بدونِ کسرِ
هزینه محاسبه می‌شود: pnl = (open[i+1] − entry)/ps. مقایسه منصفانه است چون
هر دو بازو یک قرارداد دارند و هزینهٔ ثابتِ رفت‌وبرگشت در تفاضل حذف می‌شود.

اجرا: python3 strategies/s450_paired_s382.py
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)  # s382 با مسیرِ نسبیِ data/ کار می‌کند

from strategies import s382_williamsr_momentum as s382
from strategies.s450_mgmt_first_hour_low import day_id_and_first_hour_low
from strategies.s450_paired_replay import metrics, judge

PIP_VALUE_XAU = 10.0  # $ بر pip بر ۱ لات (هم‌ارزِ scalp_engine)


def reproduce_baseline():
    df = s382.load(s382.CARD)
    ps = s382.pip_size(s382.ASSET)
    a = s382.atr(df)
    sl_abs = float(np.nanmedian(a.to_numpy())) * s382.SL_K
    sig = s382.signals(df)
    tr = s382.simulate_trades(df, sig, sl_abs, s382.RR, True, ps)
    return df, tr, ps, sl_abs


def paired_replay(tr, df, ps, sl_abs):
    o = df['open'].values.astype(float)
    c = df['close'].values.astype(float)
    cl = df['close'].values.astype(float)
    _, fhl = day_id_and_first_hour_low(df, 'H4')

    rows = []
    for t in tr.itertuples(index=False):
        eb = int(t.entry_bar)          # کندلِ سیگنال؛ ورود = close[eb]
        xb = int(t.exit_bar)
        entry = cl[eb]
        pnl_m = float(t.pnl_pip)
        xb_m = xb
        reason_b = t.outcome           # 'win'(tp) یا 'loss'(sl)
        reason_m = reason_b
        changed = False
        # کندل‌های بسته‌شده در حینِ پوزیشن: از eb+1 (اولین کندلِ پس از ورود)
        # تا xb−1؛ در کندلِ xb خودِ SL/TP intrabar خورده ⇒ تقدم با SL/TP.
        for i in range(eb + 1, xb):
            f = fhl[i]
            if np.isfinite(f) and c[i] < f:
                pnl_m = (o[i + 1] - entry) / ps
                xb_m = i + 1
                reason_m = 'fbl_exit'  # first-bar-low (نسخهٔ H4)
                changed = True
                break
        rows.append(dict(entry_bar=eb, exit_bar=xb, exit_bar_mgmt=xb_m,
                         pnl_base=float(t.pnl_pip), pnl_mgmt=pnl_m,
                         reason_base=reason_b, reason_mgmt=reason_m,
                         changed=changed,
                         bars_held_base=xb - eb, bars_held_mgmt=xb_m - eb))
    return pd.DataFrame(rows)


def main():
    df, tr, ps, sl_abs = reproduce_baseline()
    print(f"baseline reproduced: n={len(tr)} sl_pip={sl_abs/ps:.2f} "
          f"tp_pip={sl_abs*s382.RR/ps:.2f} wr={(tr['outcome']=='win').mean()*100:.2f}%")
    pr = paired_replay(tr, df, ps, sl_abs)
    pr['usd_base'] = pr['pnl_base'] * PIP_VALUE_XAU
    pr['usd_mgmt'] = pr['pnl_mgmt'] * PIP_VALUE_XAU

    mid = len(df) // 2
    h1 = pr[pr['entry_bar'] < mid]
    h2 = pr[pr['entry_bar'] >= mid]
    out = dict(
        strategy='S382_WilliamsR_Momentum', card='XAUUSD-H4',
        rule=('S450-H4 variant: first-BAR-low exit — honest caveat: with the '
              'gap anchor, H4 day == week (daily brokerage pause absorbed by '
              'the normal 240min gap); reported separately per prereg §3'),
        n_trades=int(len(pr)), n_changed=int(pr['changed'].sum()),
        baseline=metrics(pr['usd_base']), treatment=metrics(pr['usd_mgmt']),
        judge_full=judge(metrics(pr['usd_base']), metrics(pr['usd_mgmt'])),
        halves=dict(
            h1=dict(base=metrics(h1['usd_base']), mgmt=metrics(h1['usd_mgmt']),
                    judge=judge(metrics(h1['usd_base']), metrics(h1['usd_mgmt']))),
            h2=dict(base=metrics(h2['usd_base']), mgmt=metrics(h2['usd_mgmt']),
                    judge=judge(metrics(h2['usd_base']), metrics(h2['usd_mgmt'])))),
        changed_detail=dict(
            avg_base_of_changed=round(float(pr.loc[pr['changed'], 'usd_base'].mean()), 2)
            if pr['changed'].any() else None,
            avg_mgmt_of_changed=round(float(pr.loc[pr['changed'], 'usd_mgmt'].mean()), 2)
            if pr['changed'].any() else None,
            avg_bars_saved=round(float((pr.loc[pr['changed'], 'bars_held_base']
                                        - pr.loc[pr['changed'], 'bars_held_mgmt']).mean()), 1)
            if pr['changed'].any() else None),
    )
    os.makedirs(os.path.join(ROOT, 'research', 'mgmt'), exist_ok=True)
    path = os.path.join(ROOT, 'research', 'mgmt', 'S450_paired_S382_H4.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n===== S450 paired · S382 · XAUUSD_H4 (first-BAR-low variant) =====")
    print(f"trades={out['n_trades']}  changed={out['n_changed']}")
    print("BASE :", out['baseline'])
    print("MGMT :", out['treatment'])
    print("JUDGE:", out['judge_full'])
    print("H1   :", out['halves']['h1']['judge'])
    print("H2   :", out['halves']['h2']['judge'])
    print("changed detail:", out['changed_detail'])
    print("saved:", path)


if __name__ == '__main__':
    main()
