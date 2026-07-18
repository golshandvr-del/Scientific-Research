# -*- coding: utf-8 -*-
"""
s128_scalp_v2_macd_mswing.py — ارتقای موتورِ اسکالپِ M5 بر مبنای آشکارسازهای واقعیِ s127
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR).**
> از این پس WR فقط یک عددِ گزارشی است؛ تعدادِ معامله و Profit Factor هم هدف نیستند.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**
================================================================================

انگیزه (پاسخِ مستقیم به User Note این نشست):
  «در نشستِ قبل تونستیم بیش از ۸۰٪ روندها رو با موتورِ اسکالپ در 5m کشف کنیم.
   حالا بر اساسِ نتایجِ اون، موتورِ m5 رو ارتقا بده و تست کن.»

نتیجهٔ اثبات‌شدهٔ نشستِ قبل (فایلِ ScalpMultiDetector_Coverage98_NetProfit_95645.md):
  ۱) موتورِ اسکالپِ *فعلیِ* سایت = D2_PULL (EMA20>EMA100 ∧ RSI(21)<35). این موتور
     برای *کشفِ روند* عملاً **کور** است: z≈−۶ در هر دو جهت (بدتر از شانس).
  ۲) آشکارسازهایی که *واقعاً* روند را می‌بینند (z>2، آماری‌معنادار):
       • D3_MACD  — تقاطعِ صعودی/نزولیِ MACD(12,26,9)  → z≈+۴ تا +۶ (قوی‌ترین)
       • D5_MSWING — ریزساختارِ higher-high پس از higher-low (و آینه برای DOWN) → z≈+۴ تا +۵
  ۳) بینشِ صریحِ بخشِ ۶ فایلِ s127: «حالا که پوشش حل شد، گلوگاهِ بعدیِ سودِ خالص
     کیفیتِ ورود و مدیریتِ خروج است — باید روی D3+D5 یک لایهٔ فیلترِ سوددهی +
     مدیریتِ خروجِ هوشمند سوار کرد و سودِ خالصِ حاصل را با رکوردِ +$95,645 مقایسه کرد.»

فرضیهٔ آزمون‌پذیرِ این فایل:
  اگر ماشهٔ ورودِ اسکالپ را از موتورِ کورِ D2_PULL به آشکارسازهای *بینایِ* D3_MACD و
  D5_MSWING تغییر دهیم (با همان paper broker، همان خروجِ «هدفِ پنهان»، همان موتورِ
  سرمایه)، سودِ خالصِ لایهٔ اسکالپِ M5 باید از baselineِ فعلی (+$10,044.73) بالاتر برود.

روش‌شناسی (کنترلِ علمی و ضدِ overfit):
  • همان زیرساختِ اثبات‌شدهٔ s91/s94/s95 بازاستفاده می‌شود (paper_broker + make_hidden_exit
    + run_capital با ریسکِ ۱٪ روی ۱۰k$، کامپاند) تا مقایسه سیب‌به‌سیب باشد.
  • فقط *ماشهٔ ورود* تغییر می‌کند. چند پیکربندیِ ورود آزمون می‌شود:
      C_BASE   : D2_PULL (بازتولیدِ baselineِ فعلی — کنترلِ منفی)
      C_MACD   : فقط D3_MACD (تقاطعِ صعودی) + گیتِ روندِ صعودی (EMA20>EMA100)
      C_MSWING : فقط D5_MSWING + گیتِ روندِ صعودی
      C_UNION  : اتحادِ D3_MACD ∪ D5_MSWING + گیتِ روند (پوششِ بالا)
      C_CONF   : هم‌گراییِ D3_MACD در پنجرهٔ اخیر ∧ D5_MSWING (کیفیتِ بالا، پوششِ کمتر)
  • برای هر پیکربندی، خروجِ «هدفِ پنهان» روی چند آستانه (TP,SL) جارو می‌شود تا فقط
    تغییرِ ماشه با بهترین خروجِ خودش مقایسه شود (نه با خروجِ منجمدِ baseline).
  • گیت‌های ضدِ overfit (همه باید سبز شوند تا یک پیکربندی «قابل‌قبول» باشد):
      (۱) هر دو نیمهٔ داده سودِ خالصِ مثبت،
      (۲) هر ۴ پنجرهٔ walk-forward سودِ خالصِ مثبت،
      (۳) سودِ خالص > baseline فعلی (+$10,044.73).
  • تصمیمِ نهایی فقط بر مبنای **سودِ خالص** گرفته می‌شود (قانونِ شمارهٔ ۱).

توجه: فقط BUY/long (مطابقِ لایهٔ اسکالپِ فعلیِ سایت که فقط long است؛ لایهٔ SHORT
جدا و در M15 است). این فایل *فقط* لایهٔ اسکالپِ M5ِ long را ارتقا می‌دهد.
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
BASELINE_NET = 10044.73   # سودِ خالصِ لایهٔ اسکالپِ فعلی (S91/D2_PULL) — عددِ هدف برای شکستن


# ==============================================================================
# ماشه‌های ورودِ اسکالپِ long (همه forward-safe؛ سیگنال روی close کندلِ i،
# ورود در open کندلِ i+1 داخلِ paper_broker اجرا می‌شود)
# ==============================================================================
def _indicators(df):
    c = df['close'].values.astype(np.float64)
    e20 = ema(c, 20)
    e100 = ema(c, 100)
    r21 = rsi(c, 21)
    # MACD(12,26,9)
    macd_line = ema(c, 12) - ema(c, 26)
    macd_sig = ema(macd_line, 9)
    return c, e20, e100, r21, macd_line, macd_sig


def entries_D2_PULL(df):
    """کنترلِ منفی: موتورِ فعلیِ سایت (کور برای کشفِ روند). EMA20>EMA100 ∧ RSI(21)<35."""
    c, e20, e100, r21, _, _ = _indicators(df)
    out = []
    n = len(df)
    for i in range(102, n - 1):
        if e20[i] > e100[i] and r21[i] < 35:
            out.append((i, 'long'))
    return out


def entries_D3_MACD(df, trend_gate=True):
    """D3_MACD: تقاطعِ صعودیِ MACD (خطِ MACD از سیگنال بالا می‌زند) + گیتِ روندِ صعودی."""
    c, e20, e100, r21, ml, sl = _indicators(df)
    out = []
    n = len(df)
    for i in range(102, n - 1):
        cross_up = (ml[i] > sl[i]) and (ml[i - 1] <= sl[i - 1])
        if not cross_up:
            continue
        if trend_gate and not (e20[i] > e100[i]):
            continue
        out.append((i, 'long'))
    return out


def entries_D5_MSWING(df, trend_gate=True):
    """D5_MSWING: higher-high پس از higher-low (ریزساختارِ price-action) + گیتِ روند."""
    c, e20, e100, r21, _, _ = _indicators(df)
    out = []
    n = len(df)
    for i in range(102, n - 1):
        # الگو (مطابقِ s127): close>close[-1] ∧ close[-1]>close[-2] ∧ close[-2]<close[-3]
        hh = (c[i] > c[i - 1]) and (c[i - 1] > c[i - 2]) and (c[i - 2] < c[i - 3])
        if not hh:
            continue
        if trend_gate and not (e20[i] > e100[i]):
            continue
        out.append((i, 'long'))
    return out


def entries_UNION(df, trend_gate=True):
    """اتحادِ D3_MACD ∪ D5_MSWING (هر دو آشکارسازِ واقعیِ s127) + گیتِ روند."""
    a = set(i for i, _ in entries_D3_MACD(df, trend_gate))
    b = set(i for i, _ in entries_D5_MSWING(df, trend_gate))
    idx = sorted(a | b)
    return [(i, 'long') for i in idx]


def entries_CONF(df, macd_lookback=6, trend_gate=True):
    """
    هم‌گرایی (Confluence): D5_MSWING فایر شود *و* در پنجرهٔ اخیر (macd_lookback کندل)
    یک تقاطعِ صعودیِ MACD رخ داده باشد. کیفیتِ بالا، پوششِ کمتر — آزمونِ فرضیهٔ
    «هم‌گراییِ دو آشکارسازِ واقعی ⇒ ورودِ باکیفیت‌تر ⇒ سودِ خالصِ بیشتر».
    """
    c, e20, e100, r21, ml, sl = _indicators(df)
    macd_cross = np.zeros(len(df), dtype=bool)
    for i in range(1, len(df)):
        macd_cross[i] = (ml[i] > sl[i]) and (ml[i - 1] <= sl[i - 1])
    out = []
    n = len(df)
    for i in range(102, n - 1):
        hh = (c[i] > c[i - 1]) and (c[i - 1] > c[i - 2]) and (c[i - 2] < c[i - 3])
        if not hh:
            continue
        recent_macd = macd_cross[max(0, i - macd_lookback):i + 1].any()
        if not recent_macd:
            continue
        if trend_gate and not (e20[i] > e100[i]):
            continue
        out.append((i, 'long'))
    return out


CONFIGS = {
    'C_BASE  (D2_PULL کنترلِ منفی)':      lambda df: entries_D2_PULL(df),
    'C_MACD  (D3_MACD + گیتِ روند)':      lambda df: entries_D3_MACD(df, True),
    'C_MSWING(D5_MSWING + گیتِ روند)':    lambda df: entries_D5_MSWING(df, True),
    'C_UNION (D3∪D5 + گیتِ روند)':        lambda df: entries_UNION(df, True),
    'C_CONF  (D5 ∧ MACD اخیر + گیت)':     lambda df: entries_CONF(df, 6, True),
}


# ==============================================================================
# ارزیابیِ سرمایه‌محور + گیت‌های ضدِ overfit
# ==============================================================================
def cap_net(df, entries, exit_fn, sl_pip, cat_sl=500.0):
    if len(entries) == 0:
        return None
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288)
    if len(tr) == 0:
        return None
    tr = tr.copy()
    tr['sl_pip'] = float(sl_pip)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=10000.0, risk_pct=1.0, compounding=True)
    return st


def eval_halves(df, entries_fn, exit_fn, sl_pip):
    """سودِ خالص در هر دو نیمهٔ داده (گیتِ ضدِ overfit شمارهٔ ۱)."""
    n = len(df)
    half = n // 2
    df1 = df.iloc[:half].reset_index(drop=True)
    df2 = df.iloc[half:].reset_index(drop=True)
    e1 = entries_fn(df1)
    e2 = entries_fn(df2)
    s1 = cap_net(df1, e1, exit_fn, sl_pip)
    s2 = cap_net(df2, e2, exit_fn, sl_pip)
    net1 = s1['net_profit'] if s1 else 0.0
    net2 = s2['net_profit'] if s2 else 0.0
    return net1, net2


def eval_walkforward(df, entries_fn, exit_fn, sl_pip, k=4):
    """سودِ خالص در k پنجرهٔ متوالی (گیتِ ضدِ overfit شمارهٔ ۲)."""
    n = len(df)
    step = n // k
    nets = []
    for w in range(k):
        a = w * step
        b = n if w == k - 1 else (w + 1) * step
        seg = df.iloc[a:b].reset_index(drop=True)
        e = entries_fn(seg)
        s = cap_net(seg, e, exit_fn, sl_pip)
        nets.append(s['net_profit'] if s else 0.0)
    return nets


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    print("=" * 88)
    print("s128 — ارتقای موتورِ اسکالپِ M5 بر مبنای آشکارسازهای واقعیِ s127 (D3_MACD + D5_MSWING)")
    print("=" * 88)
    print(f"داده: {len(df)} کندلِ M5 طلا  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    print(f"معیار: سودِ خالصِ سرمایه‌محور (ریسکِ ۱٪/۱۰k$، کامپاند). baseline فعلی = +${BASELINE_NET:,.2f}")
    print(f"قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (اینجا فقط لایهٔ M5ِ طلا ارتقا می‌یابد)\n")

    # خروجِ «هدفِ پنهان» — همان منطقِ اثبات‌شده؛ چند آستانه جارو می‌شود
    tp_grid = [100, 120, 150, 180]
    sl_grid = [50, 60, 80, 100]

    summary = {}
    print(f"{'پیکربندیِ ورود':<34} {'TP':>4} {'SL':>4} | {'n':>4} {'net$':>10} {'PF':>5} "
          f"{'WR%':>5} {'DD%':>6} | {'½1':>8} {'½2':>8} {'WF-min':>8} گیت")
    print("-" * 118)

    for cfg_name, cfg_fn in CONFIGS.items():
        entries_full = cfg_fn(df)
        best = None
        for tp in tp_grid:
            for sl in sl_grid:
                exit_fn = make_hidden_exit(tp, sl, use_trend_break=False)
                st = cap_net(df, entries_full, exit_fn, sl)
                if st is None:
                    continue
                net = st['net_profit']
                if best is None or net > best['net']:
                    best = dict(tp=tp, sl=sl, net=net, st=st)
        if best is None:
            print(f"{cfg_name:<34} — بدونِ معامله")
            continue

        tp, sl = best['tp'], best['sl']
        st = best['st']
        exit_fn = make_hidden_exit(tp, sl, use_trend_break=False)
        net1, net2 = eval_halves(df, cfg_fn, exit_fn, sl)
        wf = eval_walkforward(df, cfg_fn, exit_fn, sl, k=4)
        wf_min = min(wf)

        gate_halves = net1 > 0 and net2 > 0
        gate_wf = wf_min > 0
        gate_beat = best['net'] > BASELINE_NET
        all_gates = gate_halves and gate_wf and gate_beat
        flag = '✅' if all_gates else ('🟡' if gate_halves and gate_wf else '❌')

        print(f"{cfg_name:<34} {tp:>4} {sl:>4} | {st['n_trades']:>4} "
              f"${best['net']:>+9.2f} {st['profit_factor']:>5.2f} {st['win_rate']:>5.1f} "
              f"{st['max_dd_pct']:>6.1f} | ${net1:>+7.0f} ${net2:>+7.0f} ${wf_min:>+7.0f} {flag}")

        summary[cfg_name] = dict(
            tp=tp, sl=sl, n=int(st['n_trades']), net=round(best['net'], 2),
            pf=round(st['profit_factor'], 3), wr=round(st['win_rate'], 1),
            maxdd=round(st['max_dd_pct'], 1), sharpe=round(st['sharpe'], 2),
            avg_lot=round(st['avg_lot'], 3),
            half1=round(net1, 2), half2=round(net2, 2),
            wf=[round(x, 2) for x in wf], wf_min=round(wf_min, 2),
            gate_halves=gate_halves, gate_wf=gate_wf, gate_beat=gate_beat,
            all_gates=all_gates,
        )

    # -------- انتخابِ برنده: بیشترین سودِ خالص در میانِ پیکربندی‌هایی که همهٔ گیت‌ها سبزند
    print("\n" + "=" * 88)
    valid = {k: v for k, v in summary.items() if v['all_gates']}
    base = summary.get('C_BASE  (D2_PULL کنترلِ منفی)')
    print(f"کنترلِ منفی (بازتولیدِ baseline): net=${base['net']:+,.2f}  "
          f"(انتظار ≈ +${BASELINE_NET:,.2f}) " if base else "")

    if valid:
        winner = max(valid.items(), key=lambda kv: kv[1]['net'])
        wname, wv = winner
        delta = wv['net'] - BASELINE_NET
        print(f"🏆 برندهٔ ارتقا: {wname}")
        print(f"   TP={wv['tp']}/SL={wv['sl']}  net=${wv['net']:+,.2f}  "
              f"(Δ نسبت به baseline = ${delta:+,.2f})")
        print(f"   PF={wv['pf']}  WR={wv['wr']}%  MaxDD={wv['maxdd']}%  Sharpe={wv['sharpe']}  n={wv['n']}")
        print(f"   نیمهٔ۱=${wv['half1']:+,.2f}  نیمهٔ۲=${wv['half2']:+,.2f}  "
              f"WF={['%+.0f'%x for x in wv['wf']]}  همهٔ گیت‌ها ✅")
        improved = delta > 0
    else:
        print("❌ هیچ پیکربندی‌ای هر سه گیت را سبز نکرد (سودِ خالص > baseline + هر دو نیمه + WF).")
        winner = None
        improved = False

    out = dict(baseline_net=BASELINE_NET, configs=summary,
               winner=(winner[0] if winner else None),
               improved=bool(improved))
    path = os.path.join(RESULTS, '_s128_scalp_v2.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n✅ ذخیره شد: results/_s128_scalp_v2.json")
    print("قانونِ شمارهٔ ۱ بازتأکید: معیارِ تصمیم فقط سودِ خالص (XAUUSD+EURUSD) بود، نه WR.")


if __name__ == '__main__':
    main()
