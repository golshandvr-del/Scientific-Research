"""
explore_eurusd_short_sessions.py — شکارِ لبهٔ SHORT سشن‌محورِ EURUSD (متنوع‌سازِ واقعی)
================================================================================
> قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت): معیارِ موفقیت فقط و فقط **سودِ خالص** است،
> نه Win-Rate. تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.

انگیزه: S73 فقط Long ساعتِ ۰ UTC را می‌گیرد (+۹٬۲۲۳$). اما تحلیلِ DNA نشان داد
چند ساعت drift نزولیِ پایدار دارند (t: ساعت۲۲=−۵.۹۸، ۱۳=−۴.۶۱، ۲۳=−۳.۷۷، ۱۸=−۳.۶۶،
۶=−۳.۶۰). S73 فقط Short ساعت۱۳ را تست کرد (فاجعه: −۸۴۵۱$) و کلاً Short را خاموش کرد.

فرضیه: ساعت۱۳ (باز شدنِ نیویورک) پرنوسان است و Short آنجا ضرر می‌دهد؛ اما ساعاتِ
کم‌نقدینگیِ پایانِ روز (۲۲/۲۳) ممکن است drift نزولیِ تمیزتری داشته باشند. یک لایهٔ
SHORT سشن‌محورِ سودده روی EURUSD **مستقیماً** به سودِ خالص اضافه می‌شود (چون EURUSD
در تعریف هست) و **کاملاً غیرِهم‌بسته** با کلِ long-stackِ طلاست.

روش: دقیقاً همان موتور و حسابداریِ S73 (backtest + capital_engine)، فقط جهت=short و
فیلترِ «short-the-rip» (۴ کندلِ قبل صعودی بوده). آزمونِ each-hour، both-halves اجباری.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

PIP = 0.0001
EURUSD_CFG = dict(file='data/EURUSD_M15.csv', contract=100_000.0, spread=0.00010)
INITIAL_CAPITAL = 10_000.0
RISK_PCT = 1.0
COMMISSION = 7.0
EVAL_START = 24000


def run_short_hour(df, hour_arr, c, entry_hour, sl_pip, tp_pip, max_hold,
                   rip_lookback, use_rip):
    n = len(df)
    eval_mask = np.zeros(n, bool); eval_mask[EVAL_START:] = True
    # سیگنالِ short روی کندلی که کندلِ بعدش ساعتِ entry_hour است ⇒ ورود در open آن
    is_last_before = np.zeros(n, bool)
    is_last_before[:-1] = (hour_arr[1:] == entry_hour) & (hour_arr[:-1] != entry_hour)
    short_sig = is_last_before & eval_mask
    if use_rip:
        prior = np.zeros(n)
        prior[rip_lookback:] = c[rip_lookback:] - c[:-rip_lookback]
        short_sig = short_sig & (prior > 0)   # short-the-rip: قبلش صعودی بوده

    if short_sig.sum() < 40:
        return None
    sl_series = np.full(n, sl_pip * PIP)
    tp_series = np.full(n, tp_pip * PIP)
    st, tr = run_backtest(df, short_sig, None, None, 'short', spread=EURUSD_CFG['spread'],
                          max_hold=max_hold, sl_series=sl_series, tp_series=tp_series)
    if len(tr) < 40:
        return None
    sld = sl_series[tr['signal_bar'].values]
    order = tr['exit_bar'].values.argsort()
    tr = tr.iloc[order].reset_index(drop=True); sld = sld[order]
    stats, _ = run_capital_backtest(tr, sld, weights=None, initial_capital=INITIAL_CAPITAL,
                                    risk_pct=RISK_PCT, commission_per_lot=COMMISSION,
                                    compounding=False, contract_size=EURUSD_CFG['contract'])
    half = tr['exit_bar'].median()
    tr1 = tr[tr['exit_bar'] < half].reset_index(drop=True)
    tr2 = tr[tr['exit_bar'] >= half].reset_index(drop=True)
    sld1 = sld[:len(tr1)]; sld2 = sld[len(tr1):]
    def half_net(t, s):
        if len(t) < 5:
            return 0.0
        st2, _ = run_capital_backtest(t, s, weights=None, initial_capital=INITIAL_CAPITAL,
                                      risk_pct=RISK_PCT, commission_per_lot=COMMISSION,
                                      compounding=False, contract_size=EURUSD_CFG['contract'])
        return st2['net_profit']
    h1 = half_net(tr1, sld1); h2 = half_net(tr2, sld2)
    return dict(net=stats['net_profit'], n=len(tr), wr=stats['win_rate'],
                dd=stats['max_dd_pct'], h1=h1, h2=h2,
                both=(h1 > 0 and h2 > 0))


def main():
    print("#" * 100)
    print("  شکارِ لبهٔ SHORT سشن‌محورِ EURUSD (متنوع‌سازِ غیرِهم‌بسته با long-stack)")
    print("  قانونِ ۱: فقط سودِ خالص (XAUUSD+EURUSD). both-halves اجباری.")
    print("#" * 100)
    df = load_data(EURUSD_CFG['file'])
    dt = pd.to_datetime(df['time'], unit='s')
    hour_arr = dt.dt.hour.values
    c = df['close'].values

    # اول: پروفایلِ drift هر ساعت (تأییدِ ساختار روی همین دیتاست)
    print("\n  ── drift میانگینِ ۴-کندلِ بعد از ورود به هر ساعت (pip) ──")
    for h in range(24):
        mask = np.zeros(len(df), bool)
        mask[:-1] = (hour_arr[1:] == h) & (hour_arr[:-1] != h)
        idx = np.where(mask)[0]; idx = idx[idx < len(df) - 6]
        if len(idx) < 50:
            continue
        fwd = (c[idx + 4] - c[np.clip(idx + 1, 0, len(c) - 1)]) / PIP
        m = fwd.mean(); t = m / (fwd.std(ddof=1) + 1e-12) * np.sqrt(len(fwd))
        flag = "⬇SHORT?" if t < -2 else ("⬆long" if t > 2 else "")
        if abs(t) > 2:
            print(f"    hour {h:02d}: drift={m:+.2f}pip  t={t:+.2f}  n={len(idx)}  {flag}")

    print("\n  ── آزمونِ لایهٔ SHORT برای ساعاتِ کاندید ──")
    best = None
    winners = []
    for eh in [22, 23, 18, 6, 13, 21, 20]:
        for sl in [10, 14, 18]:
            for tp in [10, 14, 20]:
                for hold in [4, 6, 8]:
                    for use_rip in [True, False]:
                        r = run_short_hour(df, hour_arr, c, eh, sl, tp, hold, 4, use_rip)
                        if r is None:
                            continue
                        if r['both'] and r['net'] > 300:
                            tag = f"h{eh} SL{sl} TP{tp} hold{hold} rip{int(use_rip)}"
                            winners.append((r['net'], tag, r))
                        if best is None or r['net'] > best[0]:
                            best = (r['net'], f"h{eh} SL{sl} TP{tp} hold{hold} rip{int(use_rip)}", r)
    winners.sort(key=lambda x: -x[0])
    print(f"\n  برندگانِ both-halves-positive (>{300}$): {len(winners)}")
    for net, tag, r in winners[:12]:
        print(f"  ⭐ {tag}: net={net:+.0f}$ n={r['n']} WR={r['wr']:.0f}% "
              f"DD={r['dd']:.1f}% H1={r['h1']:+.0f} H2={r['h2']:+.0f}")
    if best:
        print(f"\n  بهترین (فارغ از both): {best[1]} net={best[0]:+.0f}$ "
              f"both={'✅' if best[2]['both'] else '❌'} "
              f"H1={best[2]['h1']:+.0f} H2={best[2]['h2']:+.0f}")
    print("#" * 100)


if __name__ == '__main__':
    main()
