# -*- coding: utf-8 -*-
"""
S214b — راهِ سومِ همپوشانی: «مومنتومِ Late-Entry» به‌عنوان *فیلترِ تأیید* روی لایه‌های
        زمان-محورِ LONG طلا (فصلِ ۱۱ کتابِ Trading Price Action: TRENDS)
================================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

پس‌زمینه (چرا این نشست به مسیرِ فیلتر رسید):
  کاندیدهای *مستقلِ* S214 (Late-Entry، ورودِ at-market پس از ≥۴ trend-bar) هر دو رد شدند:
    • XAUUSD_M5 : خام +$3,153 اما همپوشانیِ ۶۳.۸٪ با اجتماعِ طلا ⇒ سهمِ مستقل +$237 (گیت رد).
    • XAUUSD_H1 : خام +$2,062 اما همپوشانیِ ۵۷.۶٪ ⇒ سهمِ مستقل n=14 (زیرِ کف) (گیت رد).
  ⇒ روندهای قویِ طلا عمدتاً در همان پنجره‌های زمانیِ لایه‌های calendar رخ می‌دهند.

قانونِ سومِ همپوشانی (اجباری، همین‌جا پیش از فصلِ بعد):
  «از بخشِ همپوشان به‌عنوان فیلتر استفاده کن.» ⇒ آیا «مومنتومِ always-in-long» (تزِ فصلِ ۱۱)
  می‌تواند سیگنال‌های LONGِ زمان-محورِ *مرزیِ* طلا را تصفیه کرده و WR/سود را بالا ببرد؟

تعریفِ فیلترِ حالت‌محورِ Late-Entry (causal، همه با اطلاعاتِ کندلِ i-1):
  فیلتر[i] = True  اگر در `look` کندلِ اخیر (تا i-1) دستِ‌کم یک «run کاملِ ≥n_run trend-barِ
             صعودیِ غیر-climactic» رخ داده باشد  AND  رژیمِ ema_fast>ema_slow برقرار باشد.
  ⇒ یعنی «بازار به‌تازگی قدرتِ روندِ صعودیِ تأییدشده نشان داده» — دقیقاً شرطِ ورودِ دیرهنگامِ
    Brooks. سیگنالِ زمان-محور فقط وقتی پذیرفته می‌شود که این تأییدِ مومنتوم حاضر باشد.

هدف‌های فیلتر (لایه‌های LONGِ زمان-محورِ طلا با WRِ مرزی، از README):
  • S142  Mid-Month Drift  (days=[10,13,20]) — پایهٔ خام
  • S140  Monday Drift
  • S139  Overnight Drift (22–23 UTC)
  • S141  Turn-of-Month
  • S144  End-of-Month Pre-End
روی TFهای موجودِ طلا: M5, M15, M30, H1.

معیارِ پذیرشِ فیلتر: WR بالاتر رود  AND  net همچنان مثبت و ترجیحاً بالاتر یا نزدیک، و WF/halves
نشکند. اگر فیلتر net را زیاد کم کند ولی WR را نجات دهد (لایهٔ سوخته‌ای که زیرِ ۴۰٪ بود)، آن هم
یک بردِ پروژه است (زنده‌کردنِ لایهٔ سوخته).
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0


# ---------------------------------------------------------------------------
#  فیلترِ حالت‌محورِ Late-Entry (مومنتومِ always-in-long تأییدشده)
# ---------------------------------------------------------------------------
def late_entry_state_mask(df, ema_fast=20, ema_slow=50, n_run=4, br=0.5,
                          clx=1.5, look=12, atr_len=14):
    """ماسکِ حالت: در `look` کندلِ اخیر (تا i-1، causal) یک run کاملِ ≥n_run
    trend-barِ صعودیِ غیر-climactic رخ داده و رژیمِ صعودی برقرار است."""
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    rng = np.maximum(h - l, 1e-9)
    body = c - o
    atr = ind.atr(df, atr_len).to_numpy()
    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()

    trend_bar = (body > 0) & (np.abs(body) >= br * rng)
    regime = ef > es

    # لبهٔ رویداد: کندلی که run دقیقاً به n_run می‌رسد و غیر-climactic است
    run_evt = np.zeros(n, bool)
    run = 0
    for i in range(n):
        run = run + 1 if trend_bar[i] else 0
        if run == n_run and not np.isnan(atr[i]) and atr[i] > 0:
            avg_run_rng = rng[i - n_run + 1:i + 1].mean()
            if avg_run_rng <= clx * atr[i]:
                run_evt[i] = True

    # حالت: آیا در look کندلِ اخیر (i-look .. i-1) رویدادی رخ داده؟ (causal ⇒ تا i-1)
    recent = np.zeros(n, bool)
    csum = np.concatenate([[0], np.cumsum(run_evt.astype(int))])  # csum[k]=sum(run_evt[:k])
    for i in range(n):
        lo = max(0, i - look)
        # رویدادها در [lo, i-1]
        recent[i] = (csum[i] - csum[lo]) > 0
    return recent & regime


# ---------------------------------------------------------------------------
#  سازندهٔ سیگنال‌های پایهٔ زمان-محورِ LONG طلا (بازتولیدِ مستقل، causal)
# ---------------------------------------------------------------------------
def calendar_signals(df, kind):
    dt = df['dt']
    hour = dt.dt.hour.to_numpy()
    dow = dt.dt.dayofweek.to_numpy()
    dom = dt.dt.day.to_numpy()
    # tom_rel: روزِ کاری از انتهای ماه
    d = df.copy()
    d['date'] = dt.dt.normalize()
    d['ym'] = dt.dt.year * 100 + dt.dt.month
    days = d[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank'] - days['cnt'] - 1
    mp = dict(zip(days['date'], days['from_end']))
    from_end = d['date'].map(mp).to_numpy()

    if kind == 'S142_midmonth':
        return np.isin(dom, [10, 13, 20])
    if kind == 'S140_monday':
        return (dow == 0) & np.isin(hour, [18, 19, 20, 21])
    if kind == 'S139_overnight':
        return np.isin(hour, [22, 23])
    if kind == 'S141_turnmonth':
        return dom <= 3
    if kind == 'S144_preeom':
        return (from_end >= -8) & (from_end <= -6)
    raise ValueError(kind)


def eval_layer(df, asset, long_sig):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, long_sig, z, SL, TP, MH, asset)
    r = S.stats(tr, asset)
    if r is None or r['n'] == 0:
        return None, None
    return r, tr


def wf_halves(df, asset, long_sig):
    """h1/h2 + چهارک‌های walk-forward از per-trade net (هم‌ترازِ finalize)."""
    from engine import scalp_engine as se
    z = np.zeros(len(df), bool)
    tr = S.sim(df, long_sig, z, SL, TP, MH, asset)
    if tr is None or len(tr) < 8:
        return None
    tr = tr.sort_values('entry_bar').reset_index(drop=True)
    _, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=S.CAP,
                                       risk_pct=S.RISK, compounding=False)
    nu = pt['net_usd'].to_numpy()
    h = len(nu) // 2; q = len(nu) // 4
    return dict(h1=float(nu[:h].sum()), h2=float(nu[h:].sum()),
                wf=[round(float(nu[i * q:(i + 1) * q].sum())) for i in range(4)])


# پارامترهای پیش‌فرضِ خروج (کالیبرهٔ طلا؛ مطابقِ نشست‌های calendar)
SL, TP, MH = 150, 300, 96


def main():
    print("=" * 96)
    print("S214b — مومنتومِ Late-Entry (فصلِ ۱۱) به‌عنوان فیلترِ تأیید روی لایه‌های زمان-محورِ LONG طلا")
    print("=" * 96, flush=True)

    targets = ['S142_midmonth', 'S140_monday', 'S139_overnight', 'S141_turnmonth', 'S144_preeom']
    tfs = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1']
    # گریدِ کوچکِ فیلتر
    filt_grid = [
        dict(ef=20, es=50, n_run=4, br=0.5, clx=1.5, look=12),
        dict(ef=20, es=50, n_run=4, br=0.5, clx=2.5, look=24),
        dict(ef=10, es=30, n_run=4, br=0.5, clx=2.5, look=12),
        dict(ef=10, es=30, n_run=3, br=0.5, clx=2.5, look=8),
    ]

    rows = []
    for tf in tfs:
        asset = tf.split('_')[0]
        df = S.lastn(S.load(tf), y=4)
        for kind in targets:
            base_sig = calendar_signals(df, kind)
            rb, trb = eval_layer(df, asset, base_sig)
            if rb is None or rb['n'] < 30:
                continue
            base_wr = rb['wr']; base_net = rb['net']; base_n = rb['n']
            for fg in filt_grid:
                mask = late_entry_state_mask(df, fg['ef'], fg['es'], fg['n_run'],
                                             fg['br'], fg['clx'], fg['look'])
                fsig = base_sig & mask
                rf, trf = eval_layer(df, asset, fsig)
                if rf is None or rf['n'] < 30:
                    continue
                d_wr = rf['wr'] - base_wr
                d_net = rf['net'] - base_net
                # WF/halves برای واریانتِ فیلترشده
                hv = wf_halves(df, asset, fsig)
                wf_ok = hv is not None and all(w > 0 for w in hv['wf']) and hv['h1'] > 0 and hv['h2'] > 0
                improved = (rf['wr'] >= WR_FLOOR and rf['wr'] > base_wr + 0.5 and rf['net'] > 0)
                rows.append(dict(
                    tf=tf, kind=kind, filt=fg,
                    base_wr=round(base_wr, 2), base_net=round(base_net, 1), base_n=base_n,
                    f_wr=round(rf['wr'], 2), f_net=round(rf['net'], 1), f_n=rf['n'],
                    d_wr=round(d_wr, 2), d_net=round(d_net, 1),
                    wf=hv['wf'] if hv else None, wf_ok=bool(wf_ok), improved=bool(improved)))

    rows.sort(key=lambda r: (-int(r['improved']), -r['d_wr']))
    print(f"\nمجموع ترکیب‌های آزموده‌شده: {len(rows)}\n")
    print("### بهترین‌ها (بر مبنای بهبودِ WR با net مثبت):")
    for r in rows[:25]:
        tag = "✅IMPROVED" if r['improved'] else "  "
        wfok = "WFok" if r['wf_ok'] else "wf✗"
        print(f"  {tag} {r['tf']} {r['kind']:16s} "
              f"base(WR{r['base_wr']},net{r['base_net']:+.0f},n{r['base_n']}) "
              f"→ filt(WR{r['f_wr']},net{r['f_net']:+.0f},n{r['f_n']}) "
              f"ΔWR{r['d_wr']:+.1f} Δnet{r['d_net']:+.0f} {wfok} "
              f"[ef{r['filt']['ef']} run{r['filt']['n_run']} clx{r['filt']['clx']} look{r['filt']['look']}]")

    n_improved = sum(1 for r in rows if r['improved'])
    print(f"\nترکیب‌های بهبوددهنده (WR↑ با net>0): {n_improved}")
    with open(os.path.join(RESULTS, '_s214b_filter.json'), 'w') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("saved: results/_s214b_filter.json")


if __name__ == '__main__':
    main()
