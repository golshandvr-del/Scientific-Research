# -*- coding: utf-8 -*-
"""
s194_s140_m5_double_filter.py — امتحانِ فیلترِ مضاعف روی S140-M5 (ساختنِ S140⁺⁺ واقعی)
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥۴۰٪ فقط کفِ پذیرش.

انگیزه (سؤالِ کاربر): «یه S140⁺⁺ هم داشتیم!» — در واقع S140⁺⁺ وجود نداشت (آنچه بود
S143⁺⁺ بود). اما ایدهٔ ساختنِ S140⁺⁺ روی نسخهٔ برندهٔ M5 (SL100/TP200، mh288) با یک
فیلترِ مضاعف، کاملاً معتبر و تست‌نشده است ⇒ راهِ اولِ پروژه: «بهبود».

نسخهٔ مبنا (پذیرفته‌شده در S193):  S140-M5 = دوشنبه، Long، SL100/TP200, mh288
  net=+8,654  WR=42.9%  n=310  (روی بازهٔ ۲۰۲۳-۰۹ تا ۲۰۲۶-۰۷)

فیلترهای مضاعفِ آزمایشی (همه بدون look-ahead، فقط دادهٔ گذشته):
  F1) score≥k از ۶ تأییدِ S163 (k=۲,۳,۴)
  F2) روند: close > EMA200  (فقط روزهای هم‌سو با روندِ صعودی)
  F3) ساعتِ ورود: turn-of-hour drift — فقط دوشنبه‌هایی که در ساعتِ قویِ h1 UTC وارد شوند
       (در S190 دیده شد h1 قوی‌ترین ساعتِ M5 است). چون S140 در ابتدای دوشنبه وارد می‌شود،
       این را به‌صورت «ساعتِ ورود ∈ {۰,۱,۲}» می‌آزماییم.
  F4) نوسانِ کنترل‌شده: ATR14 در محدودهٔ نرمال (نه اسپایکِ خبری) → a14 ≤ ۲×a100

معیارِ پذیرش (سخت): فیلتر باید هم‌زمان
   (الف) WR را ≥۴۰٪ نگه دارد،
   (ب) net را نسبت به مبنای S140-M5 (+8,654) بالا ببرد **یا** WR را معنادار بالا ببرد
       بدون افتِ قابل‌توجهِ net،
   (ج) walk-forward ۴/۴ مثبت بماند،
   (د) هر دو نیمهٔ تاریخ مثبت.
اگر هیچ فیلتری این‌ها را با هم پاس نکند ⇒ S140⁺⁺ رد؛ نسخهٔ S140-M5 خام می‌ماند (صداقتِ علمی).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0
se.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                             pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    dt = df['dt']
    df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek; df['dom'] = dt.dt.day
    return df.reset_index(drop=True)


def dxy_bear(dfa):
    d = load('DXY_M15'); d['e'] = ind.ema(d['close'], 200); bear = (d['close'] < d['e']).astype(float)
    a = dfa[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'), d[['time']].assign(b=bear.values).sort_values('time'),
                      on='time', direction='backward').sort_values('idx')
    return np.nan_to_num(m['b'].values, nan=0) > 0.5


def confirms(df):
    """همان ۶ تأییدِ امتیازیِ S163 (بدون look-ahead)."""
    c = df['close']; e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
    a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values; r14 = ind.rsi(c, 14).values
    _, _, hist = ind.macd(c); hist = hist.values; price = c.values
    allf = [np.nan_to_num(price > e200, nan=False), np.nan_to_num(e50 > e200, nan=False),
            np.nan_to_num((a100 > 0) & (a14 > a100), nan=False), np.nan_to_num(hist > 0, nan=False),
            np.nan_to_num((r14 >= 35) & (r14 <= 70), nan=False), dxy_bear(df)]
    sc = np.zeros(len(df), int)
    for f in allf: sc += f.astype(int)
    return sc


def net_of(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values if len(pt) else np.array([])
    w = int((nu > 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()) if n else 0.0; gl = float(-nu[nu <= 0].sum()) if n else 0.0
    return dict(net=float(st['net_profit']), n=n, wr=(w/n*100.0 if n else 0.0),
                pf=(gp/gl if gl > 0 else float('inf')))


def wf_ok(tr, asset, k=4):
    """walk-forward: تقسیم به k پنجرهٔ زمانی؛ همه باید net>0 باشند."""
    if tr is None or len(tr) < k * 5:
        return False, []
    tr = tr.sort_values('entry_time').reset_index(drop=True)
    idx = np.array_split(np.arange(len(tr)), k)
    nets = []
    for ii in idx:
        sub = tr.iloc[ii]
        nets.append(round(net_of(sub, asset)['net'], 0))
    return all(n > 0 for n in nets), nets


def two_halves_ok(tr, asset):
    if tr is None or len(tr) < 10:
        return False
    tr = tr.sort_values('entry_time').reset_index(drop=True)
    mid = len(tr) // 2
    a = net_of(tr.iloc[:mid], asset)['net']; b = net_of(tr.iloc[mid:], asset)['net']
    return a > 0 and b > 0


def build_trades(df, mask, sl, tp, mh, asset):
    ls = mask.astype(bool)
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    tr['entry_time'] = pd.to_datetime(df['time'].values[tr['entry_bar'].values], unit='s')
    tr['entry_hour'] = tr['entry_time'].dt.hour
    return tr


def main():
    print("=" * 100)
    print("S194 — امتحانِ فیلترِ مضاعف روی S140-M5 (ساختنِ S140⁺⁺ واقعی)")
    print("قانونِ #۱: هدف=سودِ خالص؛ WR≥۴۰٪ کف. پذیرش فقط با گیتِ سختِ کامل.")
    print("=" * 100, flush=True)

    asset = 'XAUUSD_M5'
    df = load('XAUUSD_M5')
    SL, TP, MH = 100.0, 200.0, 288

    # ⚠️ اصلاحِ حیاتی: سیگنالِ پایهٔ S140 در S193 = دوشنبه (dow==0) **و ساعتِ ۱۸-۲۱ UTC**.
    # فیلترِ ساعت [18,19,20,21] بخشِ ذاتیِ لایه است، نه فیلترِ مضاعف. بدونِ آن لایه سودده نیست.
    ENTRY_HOURS = [18, 19, 20, 21]
    base_mask = (df['dow'].values == 0) & np.isin(df['hour'].values, ENTRY_HOURS)

    # نسخهٔ مبنا (بدون فیلترِ مضاعف)
    base_tr = build_trades(df, base_mask, SL, TP, MH, asset)
    base = net_of(base_tr, asset)
    print(f"\n[مبنا] S140-M5 خام (دوشنبه, SL100/TP200, mh288):")
    print(f"   net=+{base['net']:,.0f}  WR={base['wr']:.1f}%  n={base['n']}  PF={base['pf']:.2f}")

    # اندیکاتورهای فیلتر (بدون look-ahead)
    sc = confirms(df)
    e200 = ind.ema(df['close'], 200).values
    a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values
    price = df['close'].values

    filters = {
        'F1_score>=2': base_mask & (sc >= 2),
        'F1_score>=3': base_mask & (sc >= 3),
        'F1_score>=4': base_mask & (sc >= 4),
        'F2_trend_up': base_mask & np.nan_to_num(price > e200, nan=False),
        'F4_calm_vol': base_mask & np.nan_to_num(a14 <= 2.0 * a100, nan=False),
        'F1F2_sc>=3_trend': base_mask & (sc >= 3) & np.nan_to_num(price > e200, nan=False),
    }

    print(f"\n[فیلترهای مضاعفِ آزمایشی] — معیار: WR≥۴۰ و (net↑ یا WR↑ بدونِ افتِ زیادِ net) و WF4/4 و دو نیمه مثبت\n")
    print(f"{'فیلتر':22s}{'net':>12}{'Δنسبتِمبنا':>13}{'WR':>8}{'n':>6}{'PF':>7}  {'WF4/4':>7}  {'2نیمه':>6}  تصمیم")
    print("-" * 100)

    results = {}
    best = None
    for name, m in filters.items():
        # فیلترِ F3 (ساعتِ ورود) بعد از ساخت trade اعمال می‌شود؛ اینجا فقط ماسک‌های بار-محور
        tr = build_trades(df, m, SL, TP, MH, asset)
        if tr is None or len(tr) < 20:
            print(f"{name:22s}{'—':>12}{'':>13}{'':>8}{'':>6}{'':>7}  {'—':>7}  {'—':>6}  n<20 رد")
            results[name] = dict(action='reject', reason='n<20')
            continue
        st = net_of(tr, asset)
        wfok, nets = wf_ok(tr, asset, 4)
        hok = two_halves_ok(tr, asset)
        d_net = st['net'] - base['net']
        # معیار پذیرش
        improved = (st['wr'] >= 40.0) and wfok and hok and (
            (st['net'] > base['net'] + 200) or (st['wr'] > base['wr'] + 1.5 and st['net'] > base['net'] - 400))
        dec = "✅ کاندید" if improved else "❌ رد"
        print(f"{name:22s}{st['net']:>+12,.0f}{d_net:>+13,.0f}{st['wr']:>7.1f}%{st['n']:>6}{st['pf']:>7.2f}"
              f"  {str(wfok):>7}  {str(hok):>6}  {dec}")
        results[name] = dict(action=('candidate' if improved else 'reject'),
                             net=round(st['net'], 1), delta_vs_base=round(d_net, 1),
                             wr=round(st['wr'], 2), n=st['n'], pf=round(st['pf'], 3),
                             wf=nets, wf_ok=wfok, halves_ok=hok)
        if improved and (best is None or st['net'] > best[1]['net']):
            best = (name, st, d_net)

    # F3: کدام زیرمجموعهٔ ساعاتِ [18-21] بهتر است؟ (trade-level)
    print(f"\n[F3 — زیرمجموعهٔ ساعاتِ ورود درونِ 18-21 UTC] روی مبنا:")
    for hset, label in [((18, 19), 'h18-19'), ((20, 21), 'h20-21'), ((19, 20), 'h19-20'), ((18, 19, 20), 'h18-20')]:
        sub = base_tr[base_tr['entry_hour'].isin(hset)]
        if len(sub) < 20:
            print(f"   {label:6s}: n<20 رد"); continue
        st = net_of(sub, asset); wfok, nets = wf_ok(sub, asset, 4); hok = two_halves_ok(sub, asset)
        d_net = st['net'] - base['net']
        improved = (st['wr'] >= 40.0) and wfok and hok and (
            (st['net'] > base['net'] + 200) or (st['wr'] > base['wr'] + 1.5 and st['net'] > base['net'] - 400))
        dec = "✅ کاندید" if improved else "❌ رد"
        print(f"   {label:6s}: net={st['net']:>+10,.0f} (Δ{d_net:>+8,.0f})  WR={st['wr']:.1f}%  n={st['n']}  "
              f"WF={wfok} 2H={hok}  {dec}")
        results[f'F3_{label}'] = dict(action=('candidate' if improved else 'reject'),
                                      net=round(st['net'], 1), delta_vs_base=round(d_net, 1),
                                      wr=round(st['wr'], 2), n=st['n'], wf=nets, wf_ok=wfok, halves_ok=hok)
        if improved and (best is None or st['net'] > best[1]['net']):
            best = (f'F3_{label}', st, d_net)

    print("\n" + "=" * 100)
    if best is None:
        print("نتیجه: هیچ فیلترِ مضاعفی گیتِ سختِ کامل را پاس نکرد ⇒ S140⁺⁺ رد.")
        print("       نسخهٔ S140-M5 خام (بدون فیلترِ مضاعف) بهترین می‌ماند. (صداقتِ علمی)")
        verdict = dict(s140pp='rejected', best=None, base=base)
    else:
        nm, st, dn = best
        print(f"نتیجه: بهترین فیلترِ مضاعف = {nm}")
        print(f"       net=+{st['net']:,.0f}  WR={st['wr']:.1f}%  (Δ نسبت به مبنای S140-M5 = {dn:+,.0f})")
        if dn > 200:
            print(f"       ⇒ S140⁺⁺ کاندیدِ پذیرش (بهبودِ واقعی +{dn:,.0f}$).")
        else:
            print(f"       ⇒ بهبودِ net ناچیز؛ فقط اگر WR معنادار بالا رفت ارزش دارد.")
        verdict = dict(s140pp=('accept' if dn > 200 else 'marginal'),
                       best=dict(filter=nm, net=round(st['net'], 1), wr=round(st['wr'], 2), delta=round(dn, 1)),
                       base=base)

    out = dict(note='S194 double-filter test on S140-M5 (attempt to build S140++)',
               base_s140_m5=base, filters=results, verdict=verdict)
    with open(os.path.join(RESULTS, '_s194_s140_m5_double_filter.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n✅ ذخیره شد: results/_s194_s140_m5_double_filter.json")
    print("=" * 100)


if __name__ == '__main__':
    main()
