# -*- coding: utf-8 -*-
"""
s195_s140pp_robustness.py — بررسیِ استحکامِ S140⁺⁺ (حذفِ ساعتِ ۲۱ از پنجرهٔ ورود)
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥۴۰٪ فقط کفِ پذیرش.

S194 نشان داد روی M5، محدودکردنِ ساعتِ ورودِ S140 از [18,19,20,21] به [18,19,20]
(حذفِ ساعتِ ۲۱) net را +1,295$ و WR را ۴۲.۵→۴۴.۵٪ بالا می‌برد و WF4/4 و دو نیمه مثبت‌اند.
ساعتِ ۲۱ به‌تنهایی زیان‌ده بود.

⚠️ خطرِ overfit: fine-tuningِ ساعت روی همان داده می‌تواند شانسی باشد. برای اطمینان:
  آزمونِ استحکامِ مستقل ⇒ آیا همین الگو (ساعتِ ۲۱ ضعیف‌تر از ۱۸-۲۰) روی **M15** هم
  دیده می‌شود؟ اگر روی هر دو تایم‌فریمِ مستقل یک‌جور باشد، الگوی واقعیِ ساختاری است،
  نه نویزِ یک تایم‌فریم.

اگر M15 هم تأیید کند ⇒ S140⁺⁺ پذیرفته و اثرِ افزایشیِ محافظه‌کارانه محاسبه می‌شود.
اگر M15 رد کند ⇒ S140⁺⁺ رد (محافظه‌کارانه)؛ S140-M5 خام (Δ+993) می‌ماند.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0
for tf in ('M15', 'M5'):
    se.ASSETS[f'XAUUSD_{tf}'] = dict(file=f'data/XAUUSD_{tf}.csv', pip=0.10, contract=100.0,
                                     pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    dt = df['dt']; df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek
    return df.reset_index(drop=True)


def net_of(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values if len(pt) else np.array([])
    w = int((nu > 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()) if n else 0.0; gl = float(-nu[nu <= 0].sum()) if n else 0.0
    return dict(net=float(st['net_profit']), n=n, wr=(w/n*100.0 if n else 0.0),
                pf=(gp/gl if gl > 0 else float('inf')))


def sim(df, mask, sl, tp, mh, asset):
    tr = se.simulate_trades(df, mask.astype(bool), np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    tr['entry_time'] = pd.to_datetime(df['time'].values[tr['entry_bar'].values], unit='s')
    return tr


def wf(tr, asset, k=4):
    if tr is None or len(tr) < k * 5:
        return False, []
    tr = tr.sort_values('entry_time').reset_index(drop=True)
    nets = [round(net_of(tr.iloc[ii], asset)['net'], 0) for ii in np.array_split(np.arange(len(tr)), k)]
    return all(n > 0 for n in nets), nets


def halves(tr, asset):
    if tr is None or len(tr) < 10:
        return False
    tr = tr.sort_values('entry_time').reset_index(drop=True); m = len(tr) // 2
    return net_of(tr.iloc[:m], asset)['net'] > 0 and net_of(tr.iloc[m:], asset)['net'] > 0


def main():
    print("=" * 100)
    print("S195 — بررسیِ استحکامِ S140⁺⁺ (حذفِ ساعتِ ۲۱)")
    print("=" * 100, flush=True)

    out = {}
    # ---------- آزمونِ استحکامِ مستقل روی M15 ----------
    print("\n[آزمونِ استحکامِ مستقل] آیا الگوی «ساعتِ ۲۱ ضعیف‌تر از ۱۸-۲۰» روی M15 هم هست؟")
    df15 = load('XAUUSD_M15')
    for label, hours in [('h18-21 (کامل)', [18, 19, 20, 21]), ('h18-20 (بدونِ۲۱)', [18, 19, 20]),
                         ('h21 تنها', [21])]:
        m = (df15['dow'].values == 0) & np.isin(df15['hour'].values, hours)
        tr = sim(df15, m, 100, 300, 96, 'XAUUSD_M15')  # تنظیماتِ رکوردِ M15
        s = net_of(tr, 'XAUUSD_M15')
        print(f"   M15 {label:18s}: net={s['net']:>+10,.0f}  WR={s['wr']:.1f}%  n={s['n']}")
        out[f'm15_{label}'] = s
    m15_full = out['m15_h18-21 (کامل)']['net']; m15_no21 = out['m15_h18-20 (بدونِ۲۱)']['net']
    m15_confirms = (m15_no21 >= m15_full) or (out['m15_h21 تنها']['net'] < 0)
    print(f"   ⇒ M15 {'تأیید می‌کند' if m15_confirms else 'تأیید نمی‌کند'} که ساعتِ ۲۱ ضعیف‌تر است.")

    # ---------- محاسبهٔ اثرِ افزایشیِ نهاییِ S140⁺⁺ روی بازهٔ مشترک (منصفانه با رکورد) ----------
    print("\n[اثرِ افزایشی] مقایسهٔ S140⁺⁺-M5 (h18-20) با نسخهٔ فیلتردارِ رکوردِ M15 روی بازهٔ مشترک")
    df5 = load('XAUUSD_M5')
    start = max(df15['dt'].iloc[0], df5['dt'].iloc[0]); end = min(df15['dt'].iloc[-1], df5['dt'].iloc[-1])
    df15c = df15[(df15['dt'] >= start) & (df15['dt'] <= end)].reset_index(drop=True)
    df5c = df5[(df5['dt'] >= start) & (df5['dt'] <= end)].reset_index(drop=True)

    # نسخهٔ فیلتردارِ رکوردِ M15 (score≥3) — همان مبنای S193 برای مقایسهٔ منصفانه
    # (اینجا ساده: کل پنجرهٔ 18-21 چون در S193 همین مبنا بود؛ Δ نسبت به همان)
    from engine import indicators as ind
    def confirms15(df):
        c = df['close']; e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
        a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values; r14 = ind.rsi(c, 14).values
        _, _, hist = ind.macd(c); hist = hist.values; price = c.values
        d = load('DXY_M15'); d['e'] = ind.ema(d['close'], 200); bear = (d['close'] < d['e']).astype(float)
        a = df[['time']].copy(); a['idx'] = np.arange(len(a))
        mm = pd.merge_asof(a.sort_values('time'), d[['time']].assign(b=bear.values).sort_values('time'),
                           on='time', direction='backward').sort_values('idx')
        dxy = np.nan_to_num(mm['b'].values, nan=0) > 0.5
        allf = [np.nan_to_num(price > e200, nan=False), np.nan_to_num(e50 > e200, nan=False),
                np.nan_to_num((a100 > 0) & (a14 > a100), nan=False), np.nan_to_num(hist > 0, nan=False),
                np.nan_to_num((r14 >= 35) & (r14 <= 70), nan=False), dxy]
        sc = np.zeros(len(df), int)
        for f in allf: sc += f.astype(int)
        return sc
    sc15c = confirms15(df15c)
    m15_rec = (df15c['dow'].values == 0) & np.isin(df15c['hour'].values, [18, 19, 20, 21]) & (sc15c >= 3)
    s_m15_rec = net_of(sim(df15c, m15_rec, 100, 300, 96, 'XAUUSD_M15'), 'XAUUSD_M15')

    # S140⁺⁺-M5: h18-20
    m5_pp = (df5c['dow'].values == 0) & np.isin(df5c['hour'].values, [18, 19, 20])
    tr5pp = sim(df5c, m5_pp, 100, 200, 288, 'XAUUSD_M5')
    s_m5_pp = net_of(tr5pp, 'XAUUSD_M5')
    wfok, nets = wf(tr5pp, 'XAUUSD_M5', 4); hok = halves(tr5pp, 'XAUUSD_M5')

    print(f"   M15 رکورد (score≥3, h18-21):  net={s_m15_rec['net']:>+10,.0f}  WR={s_m15_rec['wr']:.1f}%  n={s_m15_rec['n']}")
    print(f"   S140⁺⁺-M5 (h18-20):          net={s_m5_pp['net']:>+10,.0f}  WR={s_m5_pp['wr']:.1f}%  n={s_m5_pp['n']}")
    print(f"   WF4/4={wfok} {nets}   دو نیمه={hok}")
    delta_pp = s_m5_pp['net'] - s_m15_rec['net']

    # مقایسه با S140-M5 خام (h18-21) که قبلاً Δ+993 داشت
    delta_vs_raw_m5 = s_m5_pp['net'] - 8653.61  # مبنای S193 M5 خام روی بازهٔ مشترک

    accept = (s_m5_pp['wr'] >= 40) and wfok and hok and m15_confirms and delta_pp > 0
    print("\n" + "=" * 100)
    if accept:
        print(f"✅ S140⁺⁺ پذیرفته: WR≥۴۰ + WF4/4 + دو نیمه + تأییدِ مستقلِ M15 + Δ>0")
        print(f"   Δ نسبت به نسخهٔ فیلتردارِ رکوردِ M15 = {delta_pp:+,.0f}$")
        print(f"   (نسبت به S140-M5 خام که قبلاً پذیرفته بود: {delta_vs_raw_m5:+,.0f}$ اضافه‌تر)")
        verdict = 'accept'
    else:
        reasons = []
        if s_m5_pp['wr'] < 40: reasons.append('WR<40')
        if not wfok: reasons.append('WF fail')
        if not hok: reasons.append('halves fail')
        if not m15_confirms: reasons.append('M15 does not confirm')
        if delta_pp <= 0: reasons.append('Δ<=0')
        print(f"❌ S140⁺⁺ رد (محافظه‌کارانه): {', '.join(reasons)}")
        print(f"   ⇒ S140-M5 خام (h18-21, Δ+993) می‌ماند.")
        verdict = 'reject'

    out.update(dict(m15_confirms=bool(m15_confirms), s_m15_record=s_m15_rec, s140pp_m5=s_m5_pp,
                    wf=nets, wf_ok=wfok, halves_ok=hok, delta_vs_m15_record=round(delta_pp, 1),
                    delta_vs_raw_m5=round(delta_vs_raw_m5, 1), verdict=verdict))
    with open(os.path.join(RESULTS, '_s195_s140pp_robustness.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("\n✅ ذخیره شد: results/_s195_s140pp_robustness.json")
    print("=" * 100)


if __name__ == '__main__':
    main()
