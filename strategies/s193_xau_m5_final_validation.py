# -*- coding: utf-8 -*-
"""
s193_xau_m5_final_validation.py — تأییدِ نهاییِ محافظه‌کارانهٔ لایه‌های M5 طلا
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥۴۰٪ فقط کفِ پذیرش.

انگیزه: S191/S192 نشان دادند دو کاندید روی M5 ارزش دارند:
  (الف) S140 Monday: M5 (SL100/TP200) بهتر از نسخهٔ *خامِ* M15 است. اما نسخهٔ M15 در
        رکورد **فیلتردار** است (S140⁺ = score≥3/6). پس مقایسهٔ منصفانه باید در برابرِ
        نسخهٔ فیلتردارِ رکورد باشد، نه نسخهٔ خام (وگرنه Δ به‌غلط بزرگ می‌شود).
  (ب) S139 Overnight: بخشِ مستقلِ M5 (روزهایی که M15 معامله نکرد) سودده و WR55٪ بود
        اما فقط ۶۹ معامله دارد ⇒ باید گیتِ walk-forwardِ جداگانه پاس کند تا مطمئن
        شویم شانسی نیست.

این اسکریپت هر دو نکته را با سخت‌گیریِ کامل حل می‌کند و اثرِ افزایشیِ **نهاییِ
محافظه‌کارانه** را می‌دهد. اگر کاندیدی گیت را پاس نکند، رد می‌شود (صداقتِ علمی).
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
for tf in ('M15', 'M5'):
    se.ASSETS[f'XAUUSD_{tf}'] = dict(file=f'data/XAUUSD_{tf}.csv', pip=0.10, contract=100.0,
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
    """همان ۶ تأییدِ امتیازیِ S163."""
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


def sim(df, ls, sl, tp, mh, asset):
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    tr['entry_time'] = pd.to_datetime(df['time'].values[tr['entry_bar'].values], unit='s')
    return tr


def main():
    print("=" * 100)
    print("S193 — تأییدِ نهاییِ محافظه‌کارانهٔ لایه‌های M5 طلا")
    print("=" * 100, flush=True)

    df15 = load('XAUUSD_M15'); df5 = load('XAUUSD_M5')
    start = max(df15['dt'].iloc[0], df5['dt'].iloc[0]); end = min(df15['dt'].iloc[-1], df5['dt'].iloc[-1])
    df15c = df15[(df15['dt'] >= start) & (df15['dt'] <= end)].reset_index(drop=True)
    df5c = df5[(df5['dt'] >= start) & (df5['dt'] <= end)].reset_index(drop=True)
    print(f"بازهٔ مشترک: {start.date()} → {end.date()}\n")

    final = {}

    # ---------- (الف) S140 Monday: M5 خام در برابرِ نسخهٔ فیلتردارِ رکورد M15 ----------
    print("=" * 100)
    print("▶ S140 Monday — مقایسهٔ منصفانه: M5 خام در برابرِ نسخهٔ فیلتردارِ رکورد (M15 score≥3)")
    print("=" * 100)
    b140_15 = (df15c['dow'].values == 0) & np.isin(df15c['hour'].values, [18, 19, 20, 21])
    sc15 = confirms(df15c)
    tr15_filt = sim(df15c, b140_15 & (sc15 >= 3), 100, 300, 96, 'XAUUSD_M15')
    s15_filt = net_of(tr15_filt, 'XAUUSD_M15')
    b140_5 = (df5c['dow'].values == 0) & np.isin(df5c['hour'].values, [18, 19, 20, 21])
    tr5 = sim(df5c, b140_5, 100, 200, 288, 'XAUUSD_M5')
    s5 = net_of(tr5, 'XAUUSD_M5')
    print(f"  M15 نسخهٔ رکورد (score≥3, SL100/TP300): net={s15_filt['net']:+,.0f} WR={s15_filt['wr']:.1f}% n={s15_filt['n']}")
    print(f"  M5 خام (SL100/TP200 mh288):            net={s5['net']:+,.0f} WR={s5['wr']:.1f}% n={s5['n']}")
    delta140 = s5['net'] - s15_filt['net']
    # گیتِ walk-forward برای M5 (اطمینان از پایداری)
    n = len(df5c); wf = []
    for k in range(4):
        a = n*k//4; b = n*(k+1)//4
        sub = df5c.iloc[a:b].reset_index(drop=True)
        ls = (sub['dow'].values == 0) & np.isin(sub['hour'].values, [18, 19, 20, 21])
        wf.append(net_of(sim(sub, ls, 100, 200, 288, 'XAUUSD_M5'), 'XAUUSD_M5'))
    all_wf = all(w['net'] > 0 for w in wf)
    print(f"  M5 walk-forward: " + " ".join(f"[{w['net']:+,.0f}]" for w in wf) + f" → ۴/۴: {all_wf}")
    if delta140 > 0 and s5['wr'] >= 40 and all_wf:
        print(f"  ✅ حتی در برابرِ نسخهٔ فیلتردارِ رکورد، M5 بهتر است ⇒ ارتقا. Δ={delta140:+,.0f}$")
        final['S140'] = dict(action='upgrade_to_M5', delta=delta140, m5=s5, m15_record=s15_filt)
    else:
        print(f"  ❌ در برابرِ نسخهٔ فیلتردارِ رکورد، M5 مزیتِ قطعی ندارد ⇒ رد (محافظه‌کارانه).")
        final['S140'] = dict(action='reject', delta=0.0, m5=s5, m15_record=s15_filt)

    # ---------- (ب) S139 Overnight: بخشِ مستقلِ M5 با گیتِ walk-forwardِ جداگانه ----------
    print("\n" + "=" * 100)
    print("▶ S139 Overnight — بخشِ مستقلِ M5 (روزهایی که M15 معامله نکرد) با گیتِ WF جداگانه")
    print("=" * 100)
    # معاملاتِ M15 (تنظیماتِ رکورد SL150/TP500) برای تعیینِ روزهای همپوشان
    b139_15 = np.isin(df15c['hour'].values, [22, 23])
    tr15_139 = sim(df15c, b139_15, 150, 500, 96, 'XAUUSD_M15')
    days15 = set(pd.to_datetime(tr15_139['entry_time']).dt.normalize())
    # معاملاتِ M5 (SL100/TP200 mh288)
    b139_5 = np.isin(df5c['hour'].values, [22, 23])
    tr5_139 = sim(df5c, b139_5, 100, 200, 288, 'XAUUSD_M5')
    d5 = pd.to_datetime(tr5_139['entry_time']).dt.normalize()
    indep_mask = ~d5.isin(days15).values
    tr5_indep = tr5_139[indep_mask].reset_index(drop=True)
    s_indep = net_of(tr5_indep, 'XAUUSD_M5')
    print(f"  بخشِ مستقلِ M5: net={s_indep['net']:+,.0f} WR={s_indep['wr']:.1f}% n={s_indep['n']}")
    # گیتِ walk-forward روی بخشِ مستقل (تقسیمِ زمانی به ۴ پنجره بر اساسِ entry_time)
    if s_indep['n'] >= 40:
        tr5_indep = tr5_indep.sort_values('entry_time').reset_index(drop=True)
        m = len(tr5_indep); wf2 = []
        for k in range(4):
            a = m*k//4; b = m*(k+1)//4
            sub = tr5_indep.iloc[a:b].reset_index(drop=True)
            wf2.append(net_of(sub, 'XAUUSD_M5'))
        # نیمه‌ها
        h1 = net_of(tr5_indep.iloc[:m//2].reset_index(drop=True), 'XAUUSD_M5')
        h2 = net_of(tr5_indep.iloc[m//2:].reset_index(drop=True), 'XAUUSD_M5')
        all_wf2 = all(w['net'] > 0 for w in wf2)
        both2 = h1['net'] > 0 and h2['net'] > 0
        print(f"  دو نیمه: [{h1['net']:+,.0f}] [{h2['net']:+,.0f}] → {both2}")
        print(f"  WF: " + " ".join(f"[{w['net']:+,.0f}]" for w in wf2) + f" → ۴/۴: {all_wf2}")
        if s_indep['net'] > 0 and s_indep['wr'] >= 40 and all_wf2 and both2:
            print(f"  ✅ بخشِ مستقلِ M5 گیتِ سختِ کامل را پاس کرد ⇒ افزودن. Δ={s_indep['net']:+,.0f}$")
            final['S139'] = dict(action='add_independent', delta=s_indep['net'], indep=s_indep)
        else:
            print(f"  ❌ بخشِ مستقل گیتِ سخت (دو نیمه/۴WF) را پاس نکرد ⇒ رد (محافظه‌کارانه، احتمالِ شانس).")
            final['S139'] = dict(action='reject', delta=0.0, indep=s_indep)
    else:
        print(f"  ❌ n<40 ⇒ نمونهٔ ناکافی برای گیتِ WF ⇒ رد.")
        final['S139'] = dict(action='reject', delta=0.0, indep=s_indep)

    # ---------- جمع‌بندی ----------
    total = sum(v['delta'] for v in final.values())
    print("\n" + "=" * 100)
    print("جمع‌بندیِ نهاییِ محافظه‌کارانه")
    print("=" * 100)
    for k, v in final.items():
        print(f"  {k}: {v['action']:20s} Δ={v['delta']:+,.0f}$")
    print(f"\n  مجموعِ اثرِ افزایشیِ نهایی روی رکورد = {total:+,.0f}$")

    out = dict(note='S193 final conservative validation of XAU M5 layers',
               window=[str(start.date()), str(end.date())], final=final, total_incremental=total)
    with open(os.path.join(RESULTS, '_s193_xau_m5_final.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s193_xau_m5_final.json")
    return out


if __name__ == '__main__':
    main()
