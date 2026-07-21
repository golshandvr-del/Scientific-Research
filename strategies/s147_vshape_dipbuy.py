# -*- coding: utf-8 -*-
"""
s147_vshape_dipbuy.py — استراتژی «V-Shape Dip-Buy» (کشفِ الگوشناسیِ بصری)
==========================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی):
  تنها هدف = بیشینه‌سازیِ «سودِ خالص» = مجموعِ سودِ دو ارز (XAUUSD + EURUSD).
  Win-Rate / Profit Factor / تعدادِ معامله هیچ‌کدام هدف نیستند — فقط پول.

منشأ کشف (User Note: «مثلِ یک هنرمندِ الگوشناس که سررشته‌ای از چارت ندارد اما شکلِ
بصریِ چارت‌ها را خوب الگویابی می‌کند رفتار کن»):
  چارتِ طلا در چند بازهٔ تاریخی به‌صورت خط+محدوده رندر شد و با «چشم» بررسی شد.
  یک الگوی بصریِ تکرارشونده دیده شد: **افتِ عمودیِ تیز (کندلِ بزرگِ نزولی) که پس از
  آن قیمت به‌سرعت به شکلِ V برمی‌گردد و صعود می‌کند.**

  آزمونِ اکتشافیِ (exploration) روی ۱۵۰k کندلِ M15 تأیید کرد:
    - «پرشِ عمودیِ خام» (بی‌جهت) لبه ندارد (WR≈49–51٪، mean≈0).
    - «ادامهٔ پرش» (staircase) هم لبه ندارد (mean منفی).
    - اما **«افتِ تیز ⇒ خرید (buy-the-dip)»** لبهٔ روشن دارد:
        thr=3× نرمال، افق ۳۲ کندل ⇒ mean=+8.2pip, median=+8.7pip, WR=53.8٪ (n=2826)
        thr=4× نرمال، افق ۳۲ کندل ⇒ mean=+17.9pip, median=+6.9pip (n=1141)
  علتِ اقتصادی: طلا بایاسِ صعودیِ ساختاری دارد (کلِ پروژه اثبات کرده)، پس افت‌های
  تیزِ ناشی از شوکِ نقدینگی/خبر معمولاً پس‌زده (mean-revert) و بازخرید می‌شوند.

تعریفِ الگو (forward-safe، بدونِ look-ahead):
  کندلِ i یک «افتِ تیز» است اگر:
    range[i] / median(range, 96) > jump_thr   (کندلِ غیرعادی بزرگ)
    close[i] < open[i]                          (نزولی = افت)
  ورود: خرید در open کندلِ i+1 (فقط اطلاعاتِ تا بسته‌شدنِ i استفاده می‌شود).
  خروج: SL/TP ثابت + trailing («بگذار بردها بدوند» — درسِ s118).

هزینه: از engine/market_spec (هزینهٔ واقعیِ کاربر، طلا = 0.40$/oz = 40$/لات، comm=0).
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.capital_engine import run_capital_backtest
from engine.market_spec import get_spec

SPEC = get_spec('XAUUSD')
PIP = SPEC['pip']                       # 0.10
CONTRACT = SPEC['contract_size']        # 100
COST_PRICE = SPEC['cost_price']         # 0.40 $/oz (هزینهٔ واقعی، محافظه‌کارانه)
COMMISSION = SPEC['commission_per_lot'] # 0.0
INITIAL_CAPITAL = 10000.0
RISK_PCT = 1.0


def load(symbol='XAUUSD', tf='M15'):
    df = pd.read_csv(f'{ROOT}/data/{symbol}_{tf}.csv')
    return df.reset_index(drop=True)


def atr_np(df, period=14):
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period, min_periods=1).mean().values
    return atr


def gen_signals(df, jump_thr=3.0, med_win=96, cooldown=8):
    """سیگنالِ خرید پس از افتِ تیزِ عمودی. فقط LONG (buy-the-dip)."""
    o = df['open'].values; c = df['close'].values
    h = df['high'].values; l = df['low'].values
    rng = h - l
    med = pd.Series(rng).rolling(med_win, min_periods=20).median().values
    jr = rng / (med + 1e-9)
    n = len(df)
    sig = np.zeros(n, dtype=np.int8)
    last = -10**9
    for i in range(med_win, n - 1):
        if i - last < cooldown:
            continue
        # افتِ تیزِ عمودی: کندلِ بزرگِ نزولی
        if jr[i] > jump_thr and c[i] < o[i]:
            sig[i] = 1  # خرید در کندلِ بعد
            last = i
    return sig


def backtest_trail(df, sig, atr_arr, sl_mult, tp_mult, be_trig, trail_mult, max_hold):
    """خروجِ SL/TP + trailing «بگذار بردها بدوند» برای LONG، با هزینهٔ واقعی."""
    o = df['open'].values; h = df['high'].values
    l = df['low'].values; c = df['close'].values
    n = len(df)
    idx = np.where(sig != 0)[0]
    trades = []; sl_dists = []
    for i in idx:
        eb = i + 1
        if eb >= n:
            continue
        a = atr_arr[i]
        if a <= 0 or np.isnan(a):
            continue
        entry = o[eb]
        sl = entry - sl_mult * a
        tp = entry + tp_mult * a
        be_level = entry + be_trig * a
        extreme = entry
        sl_dist = abs(entry - sl)
        xb = min(eb + max_hold, n - 1)
        ep = c[xb]; oc = 'loss'
        exited = False
        for j in range(eb, min(eb + max_hold, n)):
            hi = h[j]; lo = l[j]
            # SL اول چک می‌شود (محافظه‌کارانه)
            if lo <= sl:
                ep = sl; oc = 'win' if sl >= entry else 'loss'; xb = j; exited = True; break
            if hi >= tp:
                ep = tp; oc = 'win'; xb = j; exited = True; break
            extreme = max(extreme, hi)
            if extreme >= be_level:
                sl = max(sl, entry + 0.1 * a)
                sl = max(sl, extreme - trail_mult * a)
        if not exited:
            ep = c[min(eb + max_hold, n - 1)]
            oc = 'win' if ep > entry else 'loss'
        raw = (ep - entry) - COST_PRICE   # LONG، هزینهٔ واقعی
        trades.append({'pnl': raw, 'signal_bar': i, 'exit_bar': xb, 'outcome': oc})
        sl_dists.append(sl_dist)
    return pd.DataFrame(trades), np.array(sl_dists)


def ev(trades, sl_dist):
    if trades is None or len(trades) == 0:
        return None
    stats, _ = run_capital_backtest(
        trades, sl_dist, initial_capital=INITIAL_CAPITAL,
        risk_pct=RISK_PCT, commission_per_lot=COMMISSION,
        contract_size=CONTRACT)
    return stats


def wf_folds(trades, sl_dist, n_bars, k=4):
    edges = [int(n_bars * j / k) for j in range(k + 1)]
    out = []
    sb = trades['signal_bar'].values
    for j in range(k):
        m = (sb >= edges[j]) & (sb < edges[j + 1])
        if m.sum() == 0:
            out.append(0.0); continue
        s = ev(trades[m].reset_index(drop=True), sl_dist[m])
        out.append(s['net_profit'] if s else 0.0)
    return out


def per_year(df, trades, sl_dist):
    yrs = pd.to_datetime(df['time'], unit='s').dt.year.values
    sb = trades['signal_bar'].values
    ty = yrs[sb]
    out = {}
    for y in sorted(set(ty)):
        m = ty == y
        s = ev(trades[m].reset_index(drop=True), sl_dist[m])
        out[int(y)] = s['net_profit'] if s else 0.0
    return out


if __name__ == '__main__':
    print("=== s147 — V-Shape Dip-Buy (کشفِ الگوشناسیِ بصری) ===")
    print(f"COST_PRICE={COST_PRICE:.2f}$/oz ({COST_PRICE*CONTRACT:.0f}$/لات)  comm={COMMISSION}")
    df = load('XAUUSD', 'M15')
    atr = atr_np(df, 14)
    n = len(df); mid = n // 2
    print(f"داده: {n} کندلِ M15")

    print("\n--- جاروبِ پارامتر (jump_thr × SL/TP/trail) ---")
    best = None
    grid = []
    for jt in [2.5, 3.0, 3.5, 4.0]:
        sig = gen_signals(df, jump_thr=jt, cooldown=8)
        nsig = int(sig.sum())
        for (sl, tp, be, tr, mh) in [
            (3.0, 6.0, 2.0, 3.0, 96),
            (4.0, 8.0, 2.0, 3.0, 96),
            (3.0, 10.0, 2.0, 4.0, 128),
            (5.0, 12.0, 3.0, 4.0, 128),
        ]:
            trd, sld = backtest_trail(df, sig, atr, sl, tp, be, tr, mh)
            s = ev(trd, sld)
            if s is None:
                continue
            m1 = trd['signal_bar'] < mid
            h1 = ev(trd[m1].reset_index(drop=True), sld[m1.values]) if m1.sum() else None
            h2 = ev(trd[~m1].reset_index(drop=True), sld[(~m1).values]) if (~m1).sum() else None
            folds = wf_folds(trd, sld, n)
            both_ok = (h1 and h2 and h1['net_profit'] > 0 and h2['net_profit'] > 0)
            wf_ok = all(f > 0 for f in folds)
            rec = dict(jt=jt, sl=sl, tp=tp, be=be, tr=tr, mh=mh,
                       net=s['net_profit'], n=s['n_trades'], wr=s['win_rate'],
                       pf=s['profit_factor'], dd=s['max_dd_pct'],
                       h1=h1['net_profit'] if h1 else 0, h2=h2['net_profit'] if h2 else 0,
                       folds=folds, both_ok=both_ok, wf_ok=wf_ok)
            grid.append(rec)
            flag = "✅" if (both_ok and wf_ok) else ("½" if both_ok else "")
            print(f"jt{jt} SL{sl}/TP{tp}/be{be}/tr{tr}/mh{mh}: "
                  f"net={s['net_profit']:+.0f}$ n={s['n_trades']} WR={s['win_rate']:.0f}% "
                  f"PF={s['profit_factor']:.2f} DD={s['max_dd_pct']:.0f}% "
                  f"h1={rec['h1']:+.0f} h2={rec['h2']:+.0f} "
                  f"folds=[{','.join(f'{f:+.0f}' for f in folds)}] {flag}")

    # برنده = بیشترین net که BOTH گیت را پاس کند
    valid = [r for r in grid if r['both_ok'] and r['wf_ok']]
    if valid:
        best = max(valid, key=lambda r: r['net'])
        print(f"\n🏆 برندهٔ گیت‌پاس‌شده: jt{best['jt']} SL{best['sl']}/TP{best['tp']}/"
              f"be{best['be']}/tr{best['tr']}/mh{best['mh']} ⇒ net={best['net']:+.0f}$")
        sig = gen_signals(df, jump_thr=best['jt'], cooldown=8)
        trd, sld = backtest_trail(df, sig, atr, best['sl'], best['tp'], best['be'],
                                  best['tr'], best['mh'])
        py = per_year(df, trd, sld)
        print("per-year:", {y: round(v) for y, v in py.items()})
    else:
        print("\n⚠️ هیچ کانفیگی هر دو گیت (both-halves + walk-forward) را پاس نکرد.")
