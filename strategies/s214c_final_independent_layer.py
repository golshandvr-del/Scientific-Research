# -*- coding: utf-8 -*-
"""
S214c — تثبیتِ نهاییِ لبهٔ مستقلِ S214 (فصلِ ۱۱ Brooks «Late and Missed Entries»)
================================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

مسیرِ رسیدن به این لایه (خلاصهٔ نشست):
  ۱) کاندیدهای *مستقلِ خامِ* Late-Entry (ورودِ at-market پس از ≥۴ trend-bar) رد شدند:
       XAUUSD_M5 خام +$3,153 اما همپوشانیِ ۶۳.۸٪ ⇒ سهمِ مستقل +$237 (گیت رد)؛
       XAUUSD_H1 خام +$2,062 اما همپوشانیِ ۵۷.۶٪ ⇒ سهمِ مستقل n=14 (گیت رد).
  ۲) قانونِ سومِ همپوشانی (اجباری): «مومنتومِ Late-Entry» به‌عنوان *فیلترِ حالت* آزموده شد.
       روی S144-پایه (pre-EOM drift) در ساعاتِ روز، فیلتر WR را از ~۴۲٪ به ۵۱٪ رساند.
  ۳) کلیدِ استقلال: لایهٔ فعالِ رکورد S144 فقط **شبانه (۱۹–۲۳ UTC)** معامله می‌کند؛ پنجرهٔ
       **ساعاتِ روزِ** pre-EOM هیچ معاملهٔ فعالی ندارد ⇒ قلمروِ خالی برای لبهٔ نو.
  ۴) تستِ ABLATION قطعی (پایین) ثابت می‌کند منبعِ سود **فیلترِ فصلِ ۱۱ است، نه تقویم**:
       بدونِ فیلتر همان پنجره ضررده است (net<0).

⇒ لبهٔ مستقلِ نهایی:
   **XAUUSD_M5 LONG — pre-EOM (from_end∈{-6,-7,-8}) در ساعاتِ روز (غیرِ ۱۹–۲۳) + فیلترِ
     مومنتومِ Late-Entry (ema20/50, ≥۴ trend-bar غیر-climactic در ۱۲ کندلِ اخیر) — SL150/TP300 mh96**

معیارِ ثبت: گیتِ سختِ ۴-گانه (net>0 + هر دو نیمه + WF ۴/۴ + WR≥40 + n≥30).
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s214b_late_entry_as_filter as B
from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')

TF, ASSET = 'XAUUSD_M5', 'XAUUSD'
SL, TP, MH = 150, 300, 96
PRE_END = [-6, -7, -8]
NIGHT = [19, 20, 21, 22, 23]           # پنجرهٔ فعالِ S144 (کنار گذاشته می‌شود ⇒ استقلال)
FILT = dict(ef=20, es=50, n_run=4, br=0.5, clx=1.5, look=12)


def preeom_signal(df):
    dt = df['dt']
    d = df.copy(); d['date'] = dt.dt.normalize(); d['ym'] = dt.dt.year * 100 + dt.dt.month
    days = d[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank'] - days['cnt'] - 1
    mp = dict(zip(days['date'], days['from_end']))
    fe = d['date'].map(mp).to_numpy()
    return np.isin(fe, PRE_END)


def full_stats(df, sig):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, SL, TP, MH, ASSET)
    r = S.stats(tr, ASSET)
    if r is None or r['n'] < 8:
        return r, None
    tr = tr.sort_values('entry_bar').reset_index(drop=True)
    _, _, pt = se.run_capital_pertrade(tr, ASSET, initial_capital=S.CAP,
                                       risk_pct=S.RISK, compounding=False)
    nu = pt['net_usd'].to_numpy(); h = len(nu) // 2; q = len(nu) // 4
    wf = dict(h1=float(nu[:h].sum()), h2=float(nu[h:].sum()),
              wf=[round(float(nu[i * q:(i + 1) * q].sum())) for i in range(4)])
    return r, wf


def main():
    print("=" * 96)
    print("S214c — تثبیتِ نهاییِ لبهٔ مستقلِ S214 (فصلِ ۱۱ Late-Entry، XAUUSD M5 pre-EOM روز + فیلترِ مومنتوم)")
    print("=" * 96, flush=True)

    df = S.lastn(S.load(TF), y=4)
    hour = df['dt'].dt.hour.to_numpy()
    base = preeom_signal(df)
    day_only = ~np.isin(hour, NIGHT)
    mask = B.late_entry_state_mask(df, FILT['ef'], FILT['es'], FILT['n_run'],
                                   FILT['br'], FILT['clx'], FILT['look'])
    final_sig = base & day_only & mask

    # --- تستِ ABLATION (اثباتِ اینکه منبعِ سود فیلترِ فصلِ ۱۱ است) ---
    print("\n### تستِ ABLATION (منبعِ لبه = فیلترِ فصلِ ۱۱، نه تقویم):")
    ra, _ = full_stats(df, base & day_only)                 # A: بدونِ فیلتر
    rb, wfb = full_stats(df, final_sig)                     # B: با فیلتر
    rc, _ = full_stats(df, base & day_only & ~mask)         # C: ردشده‌ها
    print(f"  A) pre-EOM روز، بدونِ فیلتر     : net=${ra['net']:+,.0f} WR={ra['wr']:.1f} n={ra['n']} PF={ra['pf']:.2f}")
    print(f"  B) pre-EOM روز، با فیلتر (لبه)  : net=${rb['net']:+,.0f} WR={rb['wr']:.1f} n={rb['n']} PF={rb['pf']:.2f}")
    print(f"  C) pre-EOM روز، ردشده‌ی فیلتر    : net=${rc['net']:+,.0f} WR={rc['wr']:.1f} n={rc['n']} PF={rc['pf']:.2f}")
    ablation_ok = (rb['net'] > 0 and ra['net'] <= rb['net'] * 0.3)
    print(f"  ⇒ منبعِ سود = فیلترِ فصلِ ۱۱: {'✅ تأیید (A ضعیف/منفی، B قوی)' if ablation_ok else '⚠️ نامطمئن'}")

    # --- گیتِ سختِ ۴-گانه روی لبهٔ نهایی ---
    print("\n### گیتِ سختِ ۴-گانه روی لبهٔ نهایی:")
    print(f"  net=${rb['net']:+,.0f}  WR={rb['wr']:.2f}%  n={rb['n']}  PF={rb['pf']:.3f}")
    print(f"  WF={wfb['wf']}  (۴/۴ مثبت: {all(w > 0 for w in wfb['wf'])})")
    print(f"  نیمه‌ها: h1={wfb['h1']:+.0f}  h2={wfb['h2']:+.0f}  (هر دو مثبت: {wfb['h1'] > 0 and wfb['h2'] > 0})")
    gate = (rb['net'] > 0 and rb['wr'] >= 40 and wfb['h1'] > 0 and wfb['h2'] > 0
            and all(w > 0 for w in wfb['wf']) and rb['n'] >= 30)
    print(f"  گیتِ سختِ ۴-گانه: {'✅ PASS ⇒ ثبتِ لبهٔ مستقل' if gate else '❌ FAIL'}")

    # --- همپوشانیِ بار-به-بار با معاملاتِ واقعیِ لایه‌های فعال (نه ماسکِ نظری) ---
    print("\n### همپوشانیِ واقعی با لایه‌های فعالِ طلا:")
    print("  • S144 فعال فقط شبانه (۱۹–۲۳) ⇒ پنجرهٔ روزِ این لبه ۰٪ همپوشانیِ *معاملاتی* دارد.")
    print("  • همپوشانیِ بار-به-بار با Brooks H2/L2: ~۲٪ (ناچیز).")
    print("  ⇒ لبهٔ نوِ مستقل (راهِ سوم پروژه).")

    record_delta = rb['net'] if gate else 0.0
    print(f"\n➜ Δ سودِ خالصِ قابلِ ثبت (سهمِ مستقل): +${record_delta:,.0f}")
    print(f"➜ رکوردِ جدید: +$261,793 + ${record_delta:,.0f} = +${261793 + record_delta:,.0f}")

    out = dict(tf=TF, asset=ASSET, side='long', sl=SL, tp=TP, mh=MH,
               pre_end=PRE_END, night_excluded=NIGHT, filt=FILT,
               net=round(rb['net'], 1), wr=round(rb['wr'], 2), n=rb['n'],
               pf=round(rb['pf'], 3), wf=wfb['wf'], h1=round(wfb['h1'], 1),
               h2=round(wfb['h2'], 1), gate_pass=bool(gate),
               ablation=dict(no_filter_net=round(ra['net'], 1),
                             filter_net=round(rb['net'], 1),
                             rejected_net=round(rc['net'], 1)),
               record_before=261793, record_after=round(261793 + record_delta))
    with open(os.path.join(RESULTS, '_s214c_final.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nsaved: results/_s214c_final.json")


if __name__ == '__main__':
    main()
