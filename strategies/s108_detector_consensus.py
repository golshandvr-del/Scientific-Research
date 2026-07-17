"""
s108_detector_consensus.py — «توافقِ آشکارسازها» (بُعدِ پنهانِ سوالِ فلسفی)
================================================================================
> قانونِ شمارهٔ ۱ پروژه: معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است، نه Win-Rate.
> تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD. WR فقط گزارشی است.

بُعدِ پنهانِ سوالِ فلسفی:
  در مثالِ کاربر s1={1,3,7} و s2={1,4,6,7,8}. روندهای ۱ و ۷ را *هر دو* گرفتند.
  سوال: آیا روندهای «موردِ توافقِ چند آشکارساز» کیفیتِ بالاتری (سودِ به‌ازای معاملهٔ
  بیشتر) دارند؟ اگر بله، یک **متا-گیتِ توافق** می‌تواند precision ورود را بالا ببرد.

فرضیه (forward-safe):
  اگر در لحظهٔ ورودِ یک لایهٔ LONG، چند آشکارسازِ *مستقل* (روند، مومنتوم، ساختار)
  هم‌زمان صعودی باشند (consensus بالا)، سودِ آن معامله بیشتر از حالتِ توافقِ کم است.
  متریکِ قضاوت: سودِ خالصِ سرمایه-محور، با اعتبارسنجیِ both-halves و walk-forward.

روش:
  ۱) یک ماشهٔ پایهٔ LONG (trend-pullback؛ همان مکانیزمِ خانوادهٔ S79/S91) می‌گیریم.
  ۲) در لحظهٔ هر سیگنال، «امتیازِ توافق» = تعدادِ آشکارسازهای مستقلِ صعودیِ فعال
     (۰ تا K) را می‌شماریم (بدونِ look-ahead — همه از داده گذشته).
  ۳) سودِ خالص را به تفکیکِ سطحِ توافق می‌سنجیم ⇒ آیا توافقِ بالا = سودِ بیشتر؟
  ۴) اگر بله، آستانهٔ توافق را *فقط روی نیمهٔ اول* می‌یابیم و روی نیمهٔ دوم OOS
     می‌سنجیم که آیا سودِ خالص واقعاً بهبود می‌یابد.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def base_long_signal(df):
    """ماشهٔ پایهٔ LONG (trend-pullback): EMA20>EMA100 + RSI(21)<35."""
    c = df['close']
    e20 = ind.ema(c, 20).values; e100 = ind.ema(c, 100).values
    rsi = ind.rsi(c, 21).values
    return np.nan_to_num((e20 > e100) & (rsi < 35), nan=0).astype(bool)


def detectors(df):
    """K آشکارسازِ مستقلِ صعودی (بولی در هر کندل، همه forward-safe)."""
    c = df['close']; p = c.values
    d = {}
    # 1) روندِ بلند: close > SMA200
    d['above_sma200'] = p > ind.sma(c, 200).values
    # 2) روندِ میان: EMA50 > EMA200
    d['ema50_gt_200'] = ind.ema(c, 50).values > ind.ema(c, 200).values
    # 3) مومنتوم: MACD-hist > 0
    _ml, _sl, hist = ind.macd(c); d['macd_pos'] = hist.values > 0
    # 4) ساختار: بالاترین‌های بالاتر (close > بیشینهٔ ۲۰ کندلِ قبل که ۲ کندل عقب‌تر)
    hh = pd.Series(p).rolling(20).max().shift(2).values
    d['break_hh'] = p > hh
    # 5) شیبِ مثبتِ EMA50
    e50 = ind.ema(c, 50).values
    d['ema50_rising'] = np.r_[False, e50[1:] > e50[:-1]]
    # 6) ADX روندی (قدرتِ روند)
    adx_, pdi, mdi = ind.adx(df, 14)
    d['adx_trend'] = (adx_.values > 20) & (pdi.values > mdi.values)
    out = pd.DataFrame({k: np.nan_to_num(v, nan=0).astype(int) for k, v in d.items()})
    return out


def bt(df, sig, sl=120, tp=240, mh=48):
    nosig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, sig, nosig, sl_pip=sl, tp_pip=tp,
                                asset='XAUUSD', max_hold=mh, allow_overlap=False)
    stats, _ = se.run_capital(trades, 'XAUUSD', 10_000, 1.0, compounding=False)
    return stats


def main():
    print("=" * 80)
    print("s108 — توافقِ آشکارسازها (بُعدِ پنهانِ سوالِ فلسفی)")
    print("=" * 80)
    df = load()
    print(f"داده: {len(df):,} کندل XAUUSD M15")

    base = base_long_signal(df)
    det = detectors(df)
    consensus = det.sum(axis=1).values     # ۰..۶
    K = det.shape[1]
    print(f"تعدادِ آشکارسازها: {K}   تعدادِ سیگنالِ پایه: {base.sum()}")

    # --- سودِ خالص به تفکیکِ سطحِ توافق ---
    print("\n" + "=" * 80)
    print("سودِ خالص به تفکیکِ سطحِ توافقِ آشکارسازها (کلِ داده)")
    print("=" * 80)
    print(f"{'توافق':>6}{'n سیگنال':>10}{'net$':>12}{'PF':>7}{'WR%':>7}{'net/trade':>11}")
    rows = []
    for lvl in range(0, K+1):
        sig = base & (consensus >= lvl)
        if sig.sum() < 20:
            continue
        st = bt(df, sig)
        npt = st['net_profit'] / max(st['n_trades'], 1)
        rows.append((lvl, st['n_trades'], st['net_profit'], st['profit_factor'], st['win_rate'], npt))
        print(f"{lvl:>6}{st['n_trades']:>10}{st['net_profit']:>12,.0f}"
              f"{st['profit_factor']:>7.2f}{st['win_rate']:>7.1f}{npt:>11.1f}")

    # --- انتخابِ آستانهٔ توافق روی نیمهٔ اول، تستِ OOS روی نیمهٔ دوم ---
    n = len(df); mid = n // 2
    base1 = base.copy(); base1[mid:] = False
    print("\n" + "=" * 80)
    print("انتخابِ آستانهٔ توافق روی نیمهٔ اول (IS)، تستِ OOS روی نیمهٔ دوم")
    print("=" * 80)
    best_lvl = 0; best_net1 = -1e9
    for lvl in range(0, K+1):
        sig = base1 & (consensus >= lvl)
        if sig.sum() < 20:
            continue
        st = bt(df, sig)
        if st['net_profit'] > best_net1:
            best_net1 = st['net_profit']; best_lvl = lvl
    print(f"بهترین آستانهٔ توافق روی IS: consensus>={best_lvl}  (IS net=${best_net1:,.0f})")

    # OOS
    base2 = base.copy(); base2[:mid] = False
    st_base_oos = bt(df, base2)
    sig2 = base2 & (consensus >= best_lvl)
    st_gate_oos = bt(df, sig2)
    print(f"\n[OOS نیمهٔ دوم — قضاوتِ اصلی]")
    print(f"  پایه (بدونِ گیتِ توافق): net=${st_base_oos['net_profit']:,.0f}  n={st_base_oos['n_trades']}  WR={st_base_oos['win_rate']:.1f}%")
    print(f"  با گیتِ توافق>={best_lvl}:  net=${st_gate_oos['net_profit']:,.0f}  n={st_gate_oos['n_trades']}  WR={st_gate_oos['win_rate']:.1f}%")
    improve = st_gate_oos['net_profit'] - st_base_oos['net_profit']
    print(f"  اثرِ گیتِ توافق روی OOS: {improve:+,.0f}$  {'✅ بهبود' if improve > 0 else '❌ بدونِ بهبود'}")

    out = dict(K=int(K), by_level=[[int(l), int(nn), float(v), float(pf), float(wr), float(npt)]
                                    for l, nn, v, pf, wr, npt in rows],
               best_lvl_IS=int(best_lvl),
               oos_base=float(st_base_oos['net_profit']),
               oos_gate=float(st_gate_oos['net_profit']),
               oos_improve=float(improve))
    with open(os.path.join(RESULTS, '_s108_consensus.json'), 'w') as fj:
        json.dump(out, fj, ensure_ascii=False, indent=2, default=float)
    print("\nذخیره شد: results/_s108_consensus.json")


if __name__ == '__main__':
    main()
