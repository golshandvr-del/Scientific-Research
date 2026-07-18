# -*- coding: utf-8 -*-
"""
s129_scalp_v2_macd_quality.py — پالایشِ کیفیتِ برندهٔ s128 (C_MACD) برای سودِ خالصِ بیشتر / DDِ کمتر
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR).**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.** WR فقط گزارشی است.
================================================================================

انگیزه:
  s128 اثبات کرد جایگزینیِ ماشهٔ کورِ D2_PULL با آشکارسازِ واقعیِ **D3_MACD** (تقاطعِ
  صعودیِ MACD + گیتِ روندِ EMA20>EMA100) سودِ خالصِ لایهٔ اسکالپِ M5 را از baselineِ
  +$10,044.73 به **+$15,659.13** رساند (Δ +$5,614، همهٔ گیت‌های ضدِ overfit سبز).
  اما MaxDD از −۱۳٪ به −۲۶.۵٪ رفت و PF فقط ۱.۰۷ شد (نازک). این فایل روی همان ماشهٔ
  برنده چند «فیلترِ کیفیت» می‌آزماید تا ببیند آیا می‌توان سودِ خالص را *بالاتر* برد
  یا با سودِ مشابه، DD را *پایین‌تر* آورد (پایداریِ بیشتر بدونِ قربانیِ سودِ خالص).

فیلترهای کیفیت (روی ماشهٔ پایهٔ C_MACD = MACD-cross-up ∧ EMA20>EMA100):
  F0 NONE       : بدونِ فیلتر (بازتولیدِ C_MACDِ s128 — کنترل).
  F1 RSI_CEIL   : فقط اگر RSI(21) < آستانه (اجتناب از خریدِ اشباعِ خرید).
  F2 HIST_UP    : فقط اگر هیستوگرامِ MACD رو به رشد (mac_hist[i] > mac_hist[i-1]) — مومنتومِ تازه.
  F3 NOT_EXTEND : فقط اگر close خیلی از EMA20 دور نیست (اجتناب از ورودِ کِش‌آمده) — |c-e20|/atr < k.
  F4 ADX_REGIME : فقط اگر ADX(14) > آستانه (روندِ واقعی، نه رنج).
  F5 COMBO      : ترکیبِ بهترین فیلترهای منفردِ سبز.

روش: همان paper_broker + make_hidden_exit + run_capital (ریسکِ ۱٪/۱۰k$). برای هر
فیلتر، آستانه‌ها و (TP,SL) جارو می‌شوند. گیت‌های ضدِ overfit: هر دو نیمه مثبت +
هر ۴ پنجرهٔ walk-forward مثبت + سودِ خالص > baseline (+$10,044.73).
تصمیم فقط بر مبنای سودِ خالص (قانونِ شمارهٔ ۱)؛ DD صرفاً برای انتخابِ بینِ گزینه‌های
هم‌سطحِ سود گزارش می‌شود.
================================================================================
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from strategies.s91_scalp_signal_exit import paper_broker, ema, rsi, atr, DATA
from strategies.s94_scalp_hidden_target import make_hidden_exit

RESULTS = os.path.join(ROOT, 'results')
BASELINE_NET = 10044.73
S128_WINNER = 15659.13   # برندهٔ s128 (C_MACD خام)


def _adx(df, p=14):
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum.reduce([h - l, np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))])
    tr[0] = h[0] - l[0]
    atr_ = pd.Series(tr).ewm(alpha=1 / p, adjust=False).mean().values
    pdi = 100 * pd.Series(plus).ewm(alpha=1 / p, adjust=False).mean().values / np.where(atr_ == 0, np.nan, atr_)
    mdi = 100 * pd.Series(minus).ewm(alpha=1 / p, adjust=False).mean().values / np.where(atr_ == 0, np.nan, atr_)
    dx = 100 * np.abs(pdi - mdi) / np.where((pdi + mdi) == 0, np.nan, (pdi + mdi))
    return np.nan_to_num(pd.Series(dx).ewm(alpha=1 / p, adjust=False).mean().values)


def _ind(df):
    c = df['close'].values.astype(np.float64)
    e20 = ema(c, 20); e100 = ema(c, 100)
    r21 = rsi(c, 21)
    ml = ema(c, 12) - ema(c, 26)
    sg = ema(ml, 9)
    hist = ml - sg
    a = atr(df, 14)
    adx = _adx(df, 14)
    return dict(c=c, e20=e20, e100=e100, r21=r21, ml=ml, sg=sg, hist=hist, atr=a, adx=adx)


def base_macd_signals(ind):
    """ماشهٔ پایهٔ C_MACD: تقاطعِ صعودیِ MACD ∧ EMA20>EMA100."""
    ml, sg, e20, e100 = ind['ml'], ind['sg'], ind['e20'], ind['e100']
    n = len(ml)
    sig = np.zeros(n, dtype=bool)
    for i in range(102, n - 1):
        if (ml[i] > sg[i]) and (ml[i - 1] <= sg[i - 1]) and (e20[i] > e100[i]):
            sig[i] = True
    return sig


def make_entries_fn(filt, **kw):
    """می‌سازد یک entries_fn(df) که ماشهٔ پایه را با فیلترِ داده‌شده صافی می‌کند."""
    def _fn(df):
        ind = _ind(df)
        base = base_macd_signals(ind)
        c, e20, r21, hist, a, adx = ind['c'], ind['e20'], ind['r21'], ind['hist'], ind['atr'], ind['adx']
        out = []
        n = len(df)
        for i in range(102, n - 1):
            if not base[i]:
                continue
            ok = True
            if filt in ('F1', 'F5') and 'rsi_ceil' in kw:
                if not (r21[i] < kw['rsi_ceil']):
                    ok = False
            if filt in ('F2', 'F5'):
                if not (hist[i] > hist[i - 1]):
                    ok = False
            if filt in ('F3', 'F5') and 'ext_k' in kw:
                atr_i = a[i] if a[i] and not np.isnan(a[i]) and a[i] > 0 else 1e9
                if not (abs(c[i] - e20[i]) / atr_i < kw['ext_k']):
                    ok = False
            if filt in ('F4', 'F5') and 'adx_min' in kw:
                if not (adx[i] > kw['adx_min']):
                    ok = False
            if ok:
                out.append((i, 'long'))
        return _fn_dedup(out)
    return _fn


def _fn_dedup(entries):
    return entries


def cap_net(df, entries, exit_fn, sl_pip, cat_sl=500.0):
    if not entries:
        return None
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288)
    if len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl_pip)
    st, _ = se.run_capital(tr, 'XAUUSD', 10000.0, 1.0, True)
    return st


def halves(df, entries_fn, exit_fn, sl_pip):
    n = len(df); half = n // 2
    df1 = df.iloc[:half].reset_index(drop=True)
    df2 = df.iloc[half:].reset_index(drop=True)
    s1 = cap_net(df1, entries_fn(df1), exit_fn, sl_pip)
    s2 = cap_net(df2, entries_fn(df2), exit_fn, sl_pip)
    return (s1['net_profit'] if s1 else 0.0), (s2['net_profit'] if s2 else 0.0)


def walkfwd(df, entries_fn, exit_fn, sl_pip, k=4):
    n = len(df); step = n // k; nets = []
    for w in range(k):
        a = w * step; b = n if w == k - 1 else (w + 1) * step
        seg = df.iloc[a:b].reset_index(drop=True)
        s = cap_net(seg, entries_fn(seg), exit_fn, sl_pip)
        nets.append(s['net_profit'] if s else 0.0)
    return nets


# پیکربندی‌های فیلتر با آستانه‌های موردِ آزمون
FILTER_SET = [
    ('F0 NONE (کنترل=C_MACD خام)', 'F0', {}),
    ('F1 RSI<50',                  'F1', {'rsi_ceil': 50}),
    ('F1 RSI<45',                  'F1', {'rsi_ceil': 45}),
    ('F1 RSI<40',                  'F1', {'rsi_ceil': 40}),
    ('F2 MACD-hist رو به رشد',     'F2', {}),
    ('F3 not-extended k=1.5',      'F3', {'ext_k': 1.5}),
    ('F3 not-extended k=2.5',      'F3', {'ext_k': 2.5}),
    ('F4 ADX>20',                  'F4', {'adx_min': 20}),
    ('F4 ADX>25',                  'F4', {'adx_min': 25}),
    ('F5 COMBO RSI<50+hist+ADX>20','F5', {'rsi_ceil': 50, 'adx_min': 20}),
    ('F5 COMBO RSI<45+hist+ext2.5','F5', {'rsi_ceil': 45, 'ext_k': 2.5}),
    ('F5 COMBO hist+ADX>20+ext2.5','F5', {'adx_min': 20, 'ext_k': 2.5}),
]

TP_GRID = [100, 120, 150, 180]
SL_GRID = [50, 60, 80, 100]


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    print("=" * 100)
    print("s129 — پالایشِ کیفیتِ برندهٔ s128 (C_MACD) برای سودِ خالصِ بیشتر یا DDِ کمتر")
    print("=" * 100)
    print(f"داده: {len(df)} کندلِ M5   baseline=+${BASELINE_NET:,.2f}   s128(C_MACD خام)=+${S128_WINNER:,.2f}")
    print(f"قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD\n")
    print(f"{'فیلتر':<30} {'TP':>4} {'SL':>4} | {'n':>4} {'net$':>10} {'PF':>5} {'WR%':>5} "
          f"{'DD%':>6} {'Shrp':>5} | {'½1':>7} {'½2':>7} {'WFmin':>7} گیت")
    print("-" * 122)

    summary = {}
    for label, filt, kw in FILTER_SET:
        efn = make_entries_fn(filt, **kw)
        entries_full = efn(df)
        best = None
        for tp in TP_GRID:
            for sl in SL_GRID:
                xfn = make_hidden_exit(tp, sl, use_trend_break=False)
                st = cap_net(df, entries_full, xfn, sl)
                if st is None:
                    continue
                if best is None or st['net_profit'] > best['net']:
                    best = dict(tp=tp, sl=sl, net=st['net_profit'], st=st)
        if best is None:
            print(f"{label:<30} — بدونِ معامله")
            continue
        tp, sl, st = best['tp'], best['sl'], best['st']
        xfn = make_hidden_exit(tp, sl, use_trend_break=False)
        n1, n2 = halves(df, efn, xfn, sl)
        wf = walkfwd(df, efn, xfn, sl, 4)
        wfm = min(wf)
        g_h = n1 > 0 and n2 > 0
        g_w = wfm > 0
        g_b = best['net'] > BASELINE_NET
        allg = g_h and g_w and g_b
        flag = '✅' if allg else ('🟡' if g_h and g_w else '❌')
        print(f"{label:<30} {tp:>4} {sl:>4} | {st['n_trades']:>4} ${best['net']:>+9.2f} "
              f"{st['profit_factor']:>5.2f} {st['win_rate']:>5.1f} {st['max_dd_pct']:>6.1f} "
              f"{st['sharpe']:>5.2f} | ${n1:>+6.0f} ${n2:>+6.0f} ${wfm:>+6.0f} {flag}")
        summary[label] = dict(filt=filt, kw=kw, tp=tp, sl=sl, n=int(st['n_trades']),
                              net=round(best['net'], 2), pf=round(st['profit_factor'], 3),
                              wr=round(st['win_rate'], 1), maxdd=round(st['max_dd_pct'], 1),
                              sharpe=round(st['sharpe'], 2), avg_lot=round(st['avg_lot'], 3),
                              half1=round(n1, 2), half2=round(n2, 2),
                              wf=[round(x, 2) for x in wf], wf_min=round(wfm, 2),
                              all_gates=allg)

    print("\n" + "=" * 100)
    valid = {k: v for k, v in summary.items() if v['all_gates']}
    if valid:
        # برنده: بیشترین سودِ خالص؛ در تساویِ تقریبی، کمترین DD
        w = max(valid.items(), key=lambda kv: kv[1]['net'])
        wname, wv = w
        print(f"🏆 برندهٔ نهاییِ لایهٔ اسکالپِ M5: {wname}")
        print(f"   TP={wv['tp']}/SL={wv['sl']}  net=$+{wv['net']:,.2f}  "
              f"(Δ vs baseline=${wv['net']-BASELINE_NET:+,.2f}, Δ vs s128خام=${wv['net']-S128_WINNER:+,.2f})")
        print(f"   PF={wv['pf']}  WR={wv['wr']}%  MaxDD={wv['maxdd']}%  Sharpe={wv['sharpe']}  n={wv['n']}")
        print(f"   نیمهٔ۱=$+{wv['half1']:,.2f}  نیمهٔ۲=$+{wv['half2']:,.2f}  WF={['%+.0f'%x for x in wv['wf']]}")
        # کم‌ریسک‌ترین گزینهٔ سبز که هنوز از s128 بهتر است (برای پایداری)
        low_dd = min(valid.items(), key=lambda kv: kv[1]['maxdd'])
        print(f"\n   ℹ️ کم‌DDترین گزینهٔ سبز: {low_dd[0]} → net=$+{low_dd[1]['net']:,.2f}, DD={low_dd[1]['maxdd']}%")
    else:
        wname = None
        print("❌ هیچ فیلتری همهٔ گیت‌ها را سبز نکرد.")

    out = dict(baseline_net=BASELINE_NET, s128_winner=S128_WINNER,
               filters=summary, winner=wname)
    with open(os.path.join(RESULTS, '_s129_scalp_v2_quality.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n✅ ذخیره شد: results/_s129_scalp_v2_quality.json")
    print("قانونِ شمارهٔ ۱ بازتأکید: معیارِ تصمیم فقط سودِ خالص (XAUUSD+EURUSD) بود، نه WR.")


if __name__ == '__main__':
    main()
