"""
s105_dna_gated_short.py — تبدیلِ کشفِ فلسفیِ s104 به سودِ خالص (روترِ نسبت-محور)
================================================================================
> قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت): معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر»
> است، نه Win-Rate. تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD. WR فقط گزارشی است.

پُلِ فلسفه→سود:
  s104 نشان داد لایهٔ SHORTِ رکورد یک «آشکارسازِ رژیمی» است که روندهای نزولی‌ای را
  می‌گیرد که DNA مشترک دارند: در لحظهٔ سیگنال rsi پایین، dist_ema50 پایین (قیمت زیرِ
  EMA)، و ret20 منفیِ تازه. اما لایهٔ SHORTِ فعلی *بدونِ گیت* روی همهٔ شلیک‌ها فعال
  می‌شود ⇒ بخشی از شلیک‌ها در ناحیهٔ «غلطِ DNA» می‌افتند (V-recovery/بازگشتِ میانگین)
  و سیستماتیک بازنده‌اند.

فرضیهٔ سودده (پاسخِ عملیِ سوالِ فلسفی):
  اگر SHORT را *فقط* در ناحیهٔ DNA ی که برنده‌هایش آنجا زندگی می‌کنند فعال کنیم و
  ناحیهٔ بازندهٔ سیستماتیک را هرس کنیم، سودِ خالصِ لایهٔ SHORT بالا می‌رود — بدونِ
  آسیب به هم‌بستگیِ منفیِ آن با long (جریانِ غیرِهم‌بسته دست‌نخورده می‌ماند).

روشِ بدونِ look-ahead (درسِ شکستِ s103):
  • گیت چند-ویژگیِ ساده و مقاوم (نه quantileِ overfit).
  • آستانه‌ها *فقط* از نیمهٔ اولِ داده (IS) یاد گرفته می‌شوند؛ نیمهٔ دوم کاملاً OOS.
  • علاوه بر IS/OOS، walk-forward چهار-پنجره برای اطمینان از پایداری.
  • قضاوتِ نهایی روی «سودِ خالصِ سرمایه-محورِ کلِ ۱۵۰k» (همان متریکِ رکورد).
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


def short_signal(df):
    """ماشهٔ SHORTِ رکورد (بدونِ تغییر): عبورِ close از میانهٔ [EMA50,EMA100,SMA200] از بالا به پایین."""
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def build_fp(df):
    """بردارِ DNA در هر کندل (همان ویژگی‌های s104)."""
    c = df['close']
    atr14 = ind.atr(df, 14)
    fp = pd.DataFrame(index=df.index)
    adx_, _p, _m = ind.adx(df, 14)
    fp['adx'] = adx_.values
    fp['atr_pct'] = (atr14 / c * 100).values
    fp['slope50'] = (ind.rolling_slope(c, 50) / atr14).values
    fp['rsi'] = ind.rsi(c, 14).values
    fp['dist_ema50'] = ((c - ind.ema(c, 50)) / atr14).values
    fp['dist_sma200'] = ((c - ind.sma(c, 200)) / atr14).values
    fp['ret20'] = (c.pct_change(20) * 100).values
    fp['vol_z'] = ind.zscore(atr14, 100).values
    return fp


def simulate_short(df, entry_mask):
    """شبیه‌سازیِ SHORT با پارامترِ رکورد (SL40/BE8/trail8/max12)."""
    nosig = np.zeros(len(df), dtype=bool)
    ssig = np.asarray(entry_mask, dtype=bool)
    return se.simulate_trades(df, nosig, ssig, sl_pip=40, tp_pip=200,
                              asset='XAUUSD', max_hold=12, allow_overlap=False,
                              be_trigger_pip=8, trail_pip=8)


def attach_dna(df, trades, fp):
    """DNA کندلِ سیگنال (entry_bar-1) را به هر معامله می‌چسباند."""
    rows = []
    for _, t in trades.iterrows():
        sb = int(t['entry_bar']) - 1
        if sb < 0 or sb >= len(fp):
            continue
        r = fp.iloc[sb].to_dict()
        r['entry_bar'] = int(t['entry_bar'])
        r['pnl_pip'] = t['pnl_pip']
        r['win'] = 1 if t['outcome'] == 'win' else 0
        rows.append(r)
    return pd.DataFrame(rows)


def learn_gate(train_dna, feat_cols, min_keep_frac=0.45):
    """
    گیتِ DNA را از نیمهٔ اول (IS) یاد می‌گیرد — رویکردِ مقاوم:
      برای هر ویژگی، جهتِ سودده را از همبستگیِ ویژگی↔pnl کشف می‌کند و یک آستانهٔ
      *median-based* می‌گذارد (نه quantileِ overfit). ترکیبِ چند ویژگیِ برتر با
      رأی‌گیریِ نرم: معامله عبور می‌کند اگر دستِ‌کم K از M شرطِ DNA را برآورده کند.
    خروجی: تابعِ gate(dna_df)->bool mask و توضیحِ گیت.
    """
    # قوی‌ترین ویژگی‌ها بر اساس |میانگینِ pnl در نیمهٔ بالا − نیمهٔ پایین|
    scores = {}
    dirs = {}
    for f in feat_cols:
        med = train_dna[f].median()
        hi = train_dna[train_dna[f] >= med]['pnl_pip'].mean()
        lo = train_dna[train_dna[f] < med]['pnl_pip'].mean()
        scores[f] = abs(hi - lo)
        dirs[f] = 1 if hi >= lo else -1   # 1: ویژگیِ بالا سودده‌تر؛ -1: ویژگیِ پایین
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    top = [f for f, _ in ranked[:4]]
    thresholds = {f: float(train_dna[f].median()) for f in top}
    top_dirs = {f: dirs[f] for f in top}

    # K را طوری تنظیم می‌کنیم که حداقلِ کسری از معاملات نگه داشته شود (فرکانس نمیرد)
    def count_pass(dna_df, K):
        votes = np.zeros(len(dna_df), dtype=int)
        for f in top:
            if top_dirs[f] > 0:
                votes += (dna_df[f].values >= thresholds[f]).astype(int)
            else:
                votes += (dna_df[f].values < thresholds[f]).astype(int)
        return votes >= K

    best_K = 1
    for K in [3, 2, 1]:
        keep = count_pass(train_dna, K)
        if keep.mean() >= min_keep_frac:
            best_K = K
            break

    def gate(dna_df):
        return count_pass(dna_df, best_K)

    info = dict(top=top, thresholds=thresholds, dirs=top_dirs, K=best_K,
                ranked=[[f, float(s)] for f, s in ranked])
    return gate, info


def capital_net(df, entry_bars):
    """سودِ خالصِ سرمایه-محورِ مجموعه‌ای از معاملات (با ماسکِ ورودِ صریح)."""
    mask = np.zeros(len(df), dtype=bool)
    # entry_bar را به سیگنالِ کندلِ قبل تبدیل کن (چون simulate ورود را از کندلِ بعد می‌گیرد)
    for eb in entry_bars:
        if 0 < eb <= len(df):
            mask[eb-1] = True
    trades = simulate_short(df, mask)
    stats, eq = se.run_capital(trades, 'XAUUSD', initial_capital=10_000, risk_pct=1.0,
                               compounding=False)
    return stats, trades


def main():
    print("=" * 80)
    print("s105 — روترِ DNA-محور روی لایهٔ SHORT (تبدیلِ کشفِ فلسفیِ s104 به سود)")
    print("=" * 80)
    df = load()
    print(f"داده: {len(df):,} کندل XAUUSD M15")
    fp = build_fp(df)
    feat_cols = ['adx', 'atr_pct', 'slope50', 'rsi', 'dist_ema50', 'dist_sma200', 'ret20', 'vol_z']

    # --- پایه: SHORTِ رکورد بدونِ گیت (کلِ داده) ---
    base_sig = short_signal(df)
    base_trades = simulate_short(df, base_sig)
    base_stats, _ = se.run_capital(base_trades, 'XAUUSD', 10_000, 1.0, compounding=False)
    base_dna = attach_dna(df, base_trades, fp).dropna().reset_index(drop=True)
    print(f"\n[پایه] SHORT بدونِ گیت: net=${base_stats['net_profit']:,.0f}  "
          f"PF={base_stats['profit_factor']:.2f}  WR={base_stats['win_rate']:.1f}%  n={base_stats['n_trades']}")

    # --- یادگیریِ گیت روی نیمهٔ اول، تستِ OOS روی نیمهٔ دوم ---
    base_dna = base_dna.sort_values('entry_bar').reset_index(drop=True)
    mid = len(base_dna) // 2
    train = base_dna.iloc[:mid].reset_index(drop=True)
    gate_fn, info = learn_gate(train, feat_cols, min_keep_frac=0.45)
    print(f"\nگیتِ یادگرفته‌شده (فقط از نیمهٔ اول/IS):")
    print(f"  ویژگی‌های منتخب: {info['top']}")
    print(f"  جهت‌ها: {info['dirs']}   K={info['K']} (حداقل رأیِ لازم)")

    # اعمالِ گیت روی کلِ معاملات و استخراجِ entry_bar های عبورکرده
    keep_all = gate_fn(base_dna)
    kept_entrybars = base_dna.loc[keep_all, 'entry_bar'].astype(int).tolist()
    gated_stats, gated_trades = capital_net(df, kept_entrybars)
    print(f"\n[گیت‌شده] SHORT + گیتِ DNA (کلِ داده): net=${gated_stats['net_profit']:,.0f}  "
          f"PF={gated_stats['profit_factor']:.2f}  WR={gated_stats['win_rate']:.1f}%  n={gated_stats['n_trades']}")
    print(f"  کسرِ معاملاتِ نگه‌داشته: {keep_all.mean()*100:.0f}%")

    # --- OOS خالص: گیت روی نیمهٔ دوم که در یادگیری دیده نشده ---
    test = base_dna.iloc[mid:].reset_index(drop=True)
    keep_test = gate_fn(test)
    oos_base_bars = test['entry_bar'].astype(int).tolist()
    oos_gate_bars = test.loc[keep_test, 'entry_bar'].astype(int).tolist()
    oos_base_stats, _ = capital_net(df, oos_base_bars)
    oos_gate_stats, _ = capital_net(df, oos_gate_bars)
    print(f"\n[OOS نیمهٔ دوم — قضاوتِ اصلی]")
    print(f"  بدونِ گیت: net=${oos_base_stats['net_profit']:,.0f}  n={oos_base_stats['n_trades']}  WR={oos_base_stats['win_rate']:.1f}%")
    print(f"  با گیت:    net=${oos_gate_stats['net_profit']:,.0f}  n={oos_gate_stats['n_trades']}  WR={oos_gate_stats['win_rate']:.1f}%")
    oos_improve = oos_gate_stats['net_profit'] - oos_base_stats['net_profit']
    print(f"  اثرِ گیت روی OOS: {oos_improve:+,.0f}$  "
          f"{'✅ بهبود' if oos_improve > 0 else '❌ بدونِ بهبود'}")

    # --- walk-forward چهار-پنجره (پایداری) ---
    print(f"\n[Walk-Forward چهار-پنجره]")
    n4 = len(base_dna) // 4
    wf = []
    for k in range(4):
        a = k * n4
        b = (k+1) * n4 if k < 3 else len(base_dna)
        win = base_dna.iloc[a:b]
        kb = win['entry_bar'].astype(int).tolist()
        km = gate_fn(win)
        kgb = win.loc[km, 'entry_bar'].astype(int).tolist()
        bs, _ = capital_net(df, kb)
        gs, _ = capital_net(df, kgb)
        wf.append((k+1, bs['net_profit'], gs['net_profit']))
        print(f"  پنجرهٔ {k+1}: پایه=${bs['net_profit']:>8,.0f}  گیت=${gs['net_profit']:>8,.0f}  "
              f"{'✅' if gs['net_profit'] >= bs['net_profit'] else '⚠️'}")

    out = {
        'base_net_full': base_stats['net_profit'],
        'gated_net_full': gated_stats['net_profit'],
        'keep_frac': float(keep_all.mean()),
        'gate_info': info,
        'oos_base_net': oos_base_stats['net_profit'],
        'oos_gate_net': oos_gate_stats['net_profit'],
        'oos_improve': oos_improve,
        'wf': [[int(k), float(b), float(g)] for k, b, g in wf],
    }
    with open(os.path.join(RESULTS, '_s105_dna_gated.json'), 'w') as fj:
        json.dump(out, fj, ensure_ascii=False, indent=2, default=float)
    print("\nذخیره شد: results/_s105_dna_gated.json")

    # حکمِ نهایی
    print("\n" + "=" * 80)
    full_improve = gated_stats['net_profit'] - base_stats['net_profit']
    if full_improve > 0 and oos_improve > 0:
        print(f"✅ گیتِ DNA سودِ SHORT را بهبود داد: کل {full_improve:+,.0f}$، OOS {oos_improve:+,.0f}$")
    else:
        print(f"❌ گیتِ DNA سودِ SHORT را بهبود نداد (کل {full_improve:+,.0f}$، OOS {oos_improve:+,.0f}$)")
    print("=" * 80)


if __name__ == '__main__':
    main()
