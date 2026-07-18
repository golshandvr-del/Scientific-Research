"""
s114_short_stress_audit.py — استرس‌تستِ صداقتِ نامزدِ s113 (SL60/trail6/mh8)
================================================================================
نامزدِ s113 سودِ ۳-ساله را از $33,844 به $70,595 برد (trail=6، تنگ‌ترین). این
جهشِ بزرگ + trailِ بسیار تنگ + WR=۳٪ دقیقاً الگوییست که L55 دربارهٔ باگِ
look-ahead هشدار داد. پیش از هر ادعای رکورد، این اسکریپت صداقتِ عددی را می‌سنجد:

  1. توزیعِ bars_held: چند درصدِ سود از معاملاتِ bars_held=0 یا 1 می‌آید؟
     (اگر عمدهٔ سود از bars_held=0 باشد ⇒ مشکوک به look-ahead ⇒ رد).
  2. حساسیت به اسپرد: اسپرد را ۴→۶→۸→۱۲ pip افزایش می‌دهیم؛ اگر سود سریع
     فرو بریزد ⇒ لبهٔ شکننده/غیرواقعی.
  3. حساسیت به اسلیپیج: slip را ۰.۵→۱→۲ pip.
  4. مقایسهٔ trail=6 با trail=8/12 (اگر فقط trail=6 سود می‌دهد و بقیه نه ⇒
     overfit به مکانیکِ درون‌کندلی).
  5. سودِ *کلِ ۱۵۰k* با پارامترِ جدید (برای مقایسه با سهمِ SHORTِ رکورد +14,979$).

فقط اگر از همهٔ این آزمون‌ها سربلند بیرون بیاید، نامزدِ رکوردِ جدید است.

قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود):
  فقط و فقط دنبالِ «سودِ خالصِ بیشتر» هستیم — WR مهم نیست.
  تعریفِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')


def load(years=None):
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    if years:
        cut = df['dt'].max() - pd.Timedelta(days=365 * years)
        df = df[df['dt'] >= cut].reset_index(drop=True)
    return df


def short_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def run(df, sig, p):
    long_sig = np.zeros(len(df), bool)
    trades = se.simulate_trades(df, long_sig, sig, asset='XAUUSD', **p)
    if trades is None or len(trades) == 0:
        return None, None
    stats, _ = se.run_capital(trades, asset='XAUUSD')
    return stats, trades


def main():
    print("=" * 80)
    print("s114 — استرس‌تستِ صداقتِ نامزدِ s113 (SL60/BE6/trail6/mh8)")
    print("=" * 80)
    df3 = load(years=3)
    sig3 = short_signal(df3)
    cand = dict(sl_pip=60, tp_pip=200, max_hold=8, be_trigger_pip=6, trail_pip=6)

    # ─── آزمونِ ۱: توزیعِ bars_held ───
    print("\n[۱] توزیعِ bars_held (کلیدِ تشخیصِ look-ahead):")
    stats, trades = run(df3, sig3, cand)
    bh = trades['bars_held'].values
    pnl = trades['pnl_pip'].values
    total_win_pip = pnl[pnl > 0].sum()
    for k in [0, 1, 2, 3]:
        m = bh == k
        share = pnl[m & (pnl > 0)].sum() / total_win_pip * 100 if total_win_pip else 0
        print(f"    bars_held={k}: {m.sum():5d} معامله  |  سهمِ سودِ برد: {share:5.1f}%")
    m_ge = bh >= 4
    share_ge = pnl[m_ge & (pnl > 0)].sum() / total_win_pip * 100 if total_win_pip else 0
    print(f"    bars_held>=4: {m_ge.sum():5d} معامله  |  سهمِ سودِ برد: {share_ge:5.1f}%")
    bh0_share = pnl[(bh == 0) & (pnl > 0)].sum() / total_win_pip * 100 if total_win_pip else 0
    suspicious = bh0_share > 40
    print(f"    ⇒ سهمِ سودِ bars_held=0: {bh0_share:.1f}%  "
          f"{'⚠️ مشکوک به look-ahead!' if suspicious else '✅ سالم (عمدهٔ سود از نگه‌داریِ واقعی)'}")

    # ─── آزمونِ ۲: حساسیت به اسپرد ───
    print("\n[۲] حساسیت به اسپرد (اسپردِ واقعیِ طلا در بروکرها متغیر است):")
    orig_spread = se.ASSETS['XAUUSD']['spread_pip']
    base3 = None
    for sp in [4.0, 6.0, 8.0, 12.0]:
        se.ASSETS['XAUUSD']['spread_pip'] = sp
        st, _ = run(df3, sig3, cand)
        if base3 is None:
            base3 = st['net_profit']
        print(f"    spread={sp:>4.0f}pip:  net=${st['net_profit']:>10,.0f}   n={st['n_trades']}   WR={st['win_rate']:.0f}%")
    se.ASSETS['XAUUSD']['spread_pip'] = orig_spread

    # ─── آزمونِ ۳: حساسیت به اسلیپیج ───
    print("\n[۳] حساسیت به اسلیپیج:")
    orig_slip = se.ASSETS['XAUUSD']['slip_pip']
    for sl in [0.5, 1.0, 2.0, 3.0]:
        se.ASSETS['XAUUSD']['slip_pip'] = sl
        st, _ = run(df3, sig3, cand)
        print(f"    slip={sl:>4.1f}pip:  net=${st['net_profit']:>10,.0f}   n={st['n_trades']}")
    se.ASSETS['XAUUSD']['slip_pip'] = orig_slip

    # ─── آزمونِ ۴: مقایسهٔ trail (اگر فقط trail=6 سود می‌دهد ⇒ overfit) ───
    print("\n[۴] پایداری نسبت به عرضِ trailing (نباید فقط trail=6 کار کند):")
    for tr in [6, 8, 10, 12, 16, 20]:
        p = dict(cand); p['trail_pip'] = tr
        st, _ = run(df3, sig3, p)
        print(f"    trail={tr:>3}pip:  net=${st['net_profit']:>10,.0f}   n={st['n_trades']}   WR={st['win_rate']:.0f}%")

    # ─── آزمونِ ۵: سودِ کلِ ۱۵۰k با پارامترِ جدید ───
    print("\n[۵] سودِ کلِ ۱۵۰k با پارامترِ جدید (مقایسه با سهمِ SHORTِ رکورد +$14,979):")
    df_all = load(years=None)
    sig_all = short_signal(df_all)
    st_all, tr_all = run(df_all, sig_all, cand)
    st_base_all, _ = run(df_all, sig_all,
                         dict(sl_pip=40, tp_pip=200, max_hold=12, be_trigger_pip=8, trail_pip=8))
    print(f"    baselineِ رکورد (کلِ ۱۵۰k): ${st_base_all['net_profit']:,.0f}")
    print(f"    نامزدِ جدید   (کلِ ۱۵۰k): ${st_all['net_profit']:,.0f}   n={st_all['n_trades']}")

    # ─── جمع‌بندی ───
    print("\n" + "=" * 80)
    spread_robust = base3 > 0
    verdict_ok = (not suspicious) and spread_robust
    print("جمع‌بندیِ استرس‌تست:")
    print(f"  • look-ahead (bars_held=0): {'⚠️ مشکوک' if suspicious else '✅ سالم'}")
    print(f"  • مقاومت به اسپرد: {'✅' if spread_robust else '⚠️'}")
    print(f"  • سودِ کلِ ۱۵۰k نامزد: ${st_all['net_profit']:,.0f}  (baseline ${st_base_all['net_profit']:,.0f})")
    print("=" * 80)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s114_stress.json'), 'w') as f:
        json.dump({'candidate': cand,
                   'bars_held0_win_share_pct': round(bh0_share, 1),
                   'suspicious_lookahead': bool(suspicious),
                   'net_150k_candidate': st_all['net_profit'],
                   'net_150k_baseline': st_base_all['net_profit'],
                   'net_3y_candidate': stats['net_profit']},
                  f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s114_stress.json")


if __name__ == '__main__':
    main()
