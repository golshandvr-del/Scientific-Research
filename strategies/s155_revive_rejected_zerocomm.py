# -*- coding: utf-8 -*-
"""
s155_revive_rejected_zerocomm.py — بازآزماییِ یافته‌های ردشدهٔ EURUSD با کمیسیونِ صفر
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله در روز.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
انگیزه (User Note جدید):
  «اگر استراتژی‌ای هست که با مشخصاتِ قبلی ضررده بوده اما با مشخصاتِ فعلی سودده است،
   شناسایی کن و به‌عنوانِ لایهٔ جدید اضافه کن.»

  چهار یافتهٔ EURUSD صریحاً «با کمیسیونِ ۷$/لات» رد شده بودند:
    • s150 Mean-Reversion Z-Score  (بهترین both-halves +$2,492 اما WF ناقص)
    • s151 H4 Mean-Reversion        (بهترین standalone +$1,980 اما both=N)
    • s152 Hour-14 Short            (بهترین −$524)
    • (s149 MA-Pullback −$9,766 — عمیقاً منفی، بعید است نجات یابد؛ برای کامل‌بودن)

  حالا با مشخصاتِ حسابِ جدید (**کمیسیون = صفر**) بازآزمایی می‌کنیم. معیارِ پذیرش
  همان گیتِ سختِ پروژه است (نه فقط سودِ مثبت):
    (۱) net کل مثبت
    (۲) هر دو نیمهٔ داده (H1, H2) مثبت
    (۳) هر ۴ پنجرهٔ walk-forward مثبت
  اگر همه سبز ⇒ کاندیدِ لایهٔ نو. اگر نه ⇒ صادقانه ثبت می‌کنیم که «سود مثبت شد اما
  گیتِ ضدِ overfit را رد نکرد» (طبقِ قانونِ پروژه، لایه اضافه نمی‌شود).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0


def load_eur_m15():
    df = pd.read_csv(os.path.join(ROOT, 'data', 'EURUSD_M15.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def resample_h4(df):
    d = df.set_index('dt')
    o = d['open'].resample('4h').first()
    h = d['high'].resample('4h').max()
    l = d['low'].resample('4h').min()
    c = d['close'].resample('4h').last()
    out = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c}).dropna().reset_index()
    out['time'] = out['dt'].astype('int64') // 10**9
    return out


def set_eur_comm(comm):
    se.ASSETS['EURUSD']['comm'] = float(comm)
    se.ASSETS['EURUSD']['spread_pip'] = 1.0
    se.ASSETS['EURUSD']['slip_pip'] = 0.3


# ---------------- سازندگانِ سیگنال (بازتولیدِ منطقِ اسکریپت‌های اصلی) ----------------
def gen_hour_short(df, hours):
    hh = df['dt'].dt.hour.values
    n = len(df)
    ss = np.isin(hh, hours)
    return np.zeros(n, bool), ss


def gen_meanrev(df, n_ma, zin, direction):
    c = df['close'].values
    s = pd.Series(c)
    ma = s.rolling(n_ma).mean().values
    sd = s.rolling(n_ma).std().values
    n = len(df)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    with np.errstate(invalid='ignore', divide='ignore'):
        z = (c - ma) / sd
    if direction == 'long':
        ls = np.nan_to_num(z <= -zin, nan=False)
    else:
        ss = np.nan_to_num(z >= zin, nan=False)
    return ls.astype(bool), ss.astype(bool)


def run_net(df, ls, ss, sl, tp, mh):
    tr = se.simulate_trades(df, ls, ss, sl, tp, 'EURUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return 0.0, 0, None, tr
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'EURUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return float(st['net_profit']), len(tr), st, tr


def gates(df, genfn, sl, tp, mh):
    """net کل + both-halves + walk-forward (4 پنجره). برمی‌گرداند dict."""
    n = len(df); half = n // 2
    ls, ss = genfn(df)
    net_all, ntr, st, tr = run_net(df, ls, ss, sl, tp, mh)

    def sub_net(a, b):
        s = df.iloc[a:b].reset_index(drop=True)
        l, sh = genfn(s)
        nn, _, _, _ = run_net(s, l, sh, sl, tp, mh)
        return nn

    h1 = sub_net(0, half); h2 = sub_net(half, n)
    edges = np.linspace(0, n, 5, dtype=int)
    wf = [round(sub_net(edges[k], edges[k+1]), 0) for k in range(4)]
    both_ok = (h1 > 0) and (h2 > 0)
    wf_ok = all(w > 0 for w in wf)
    return dict(net=net_all, n=ntr, h1=h1, h2=h2, wf=wf,
                both_ok=both_ok, wf_ok=wf_ok, pass_all=(net_all > 0 and both_ok and wf_ok))


def main():
    print("=" * 82)
    print("S155 — بازآزماییِ یافته‌های ردشدهٔ EURUSD با کمیسیونِ صفر (مشخصاتِ حسابِ جدید)")
    print("=" * 82)
    df = load_eur_m15()
    dfh4 = resample_h4(df)

    # کاندیدها: (نام، تابعِ ساخت‌کننده روی df مناسب، df، پارامترهای خروجِ بهترینِ فایلِ رکورد)
    candidates = [
        # s152 Hour-14 Short (time-exit خالص ⇒ SL/TP بزرگ، mh کوتاه). بهترین قبلی −$524.
        ('Hour14_Short (s152)', lambda d: gen_hour_short(d, [14]), df, dict(sl=40, tp=40, mh=4)),
        # s150 Mean-Reversion (short ma100 z2.5 — بهترین قبلی −$2,584؛ و long ma100 z2.5)
        ('MeanRev_Short_ma100_z2.5 (s150)', lambda d: gen_meanrev(d, 100, 2.5, 'short'), df, dict(sl=40, tp=60, mh=16)),
        ('MeanRev_Long_ma100_z2.5 (s150)',  lambda d: gen_meanrev(d, 100, 2.5, 'long'),  df, dict(sl=40, tp=60, mh=16)),
        # s151 H4 Mean-Reversion (long ma30 z1.8 — بهترین standalone +$1,980)
        ('H4_MeanRev_Long_ma30_z1.8 (s151)', lambda d: gen_meanrev(d, 30, 1.8, 'long'), dfh4, dict(sl=40, tp=80, mh=12)),
    ]

    out = {}
    for comm in [7.0, 0.0]:
        set_eur_comm(comm)
        print(f"\n{'─'*82}\n### کمیسیون = {comm}$/لات ###")
        out[f'comm{int(comm)}'] = {}
        for name, genfn, d, ekw in candidates:
            g = gates(d, genfn, ekw['sl'], ekw['tp'], ekw['mh'])
            flag = "✅ PASS همه گیت‌ها" if g['pass_all'] else \
                   ("🟡 net مثبت ولی گیت رد" if g['net'] > 0 else "❌ net منفی")
            print(f"  {name:38s}: net={g['net']:+9,.0f}$  N={g['n']:5d}  "
                  f"h1={g['h1']:+7,.0f} h2={g['h2']:+7,.0f}  WF={g['wf']}  {flag}")
            out[f'comm{int(comm)}'][name] = g

    # جمع‌بندی: کدام کاندیدها *فقط* با کمیسیونِ صفر PASS شدند؟
    print("\n" + "=" * 82)
    print("جمع‌بندی: کاندیدهایی که با مشخصاتِ جدید (کمیسیون صفر) تمامِ گیت‌ها را رد کردند")
    print("=" * 82)
    revived = []
    for name, _, _, _ in candidates:
        p7 = out['comm7'][name]['pass_all']
        p0 = out['comm0'][name]['pass_all']
        if p0 and not p7:
            revived.append(name)
            print(f"  🎉 {name}: با کمیسیون۷ رد ولی با کمیسیون۰ PASS ⇒ لایهٔ نو (net={out['comm0'][name]['net']:+,.0f}$)")
        elif p0 and p7:
            print(f"  ✅ {name}: با هر دو PASS (net={out['comm0'][name]['net']:+,.0f}$)")
        else:
            n0 = out['comm0'][name]['net']
            print(f"  — {name}: با کمیسیون۰ هم گیت را رد نکرد (net={n0:+,.0f}$) ⇒ لایه نمی‌شود")

    out['revived'] = revived
    with open(os.path.join(RESULTS, '_s155_revive_rejected.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=float)
    print(f"\n✅ ذخیره شد: results/_s155_revive_rejected.json  |  احیاشده: {len(revived)}")
    return out


if __name__ == '__main__':
    main()
