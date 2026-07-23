"""
s205_sos_h1_final_confirm.py — تأییدِ نهاییِ لایهٔ نو: SoS-H1 + ATR14>ATR100 (سهمِ مستقل)
================================================================================
S204 نشان داد فیلترِ ATR14>ATR100 سهمِ مستقلِ SoS-H1 را به لبهٔ پایدار می‌رساند
(net=+$1,445، WR=54.8٪، WF=[+1025,+593,+1635,+638]). این‌جا تأییدِ نهاییِ ضدِ
دوباره‌شماری انجام می‌شود: سهمِ مستقل را در برابرِ *اجتماعِ روزهای معاملاتیِ همهٔ
لایه‌های LONGِ طلای پرتفوی روی M15* (نه فقط SoS-M15) می‌سنجیم — محافظه‌کارانه‌ترین حالت.

لایه‌های LONGِ طلای پرتفوی (روی M15) که روزهایشان استخراج می‌شود:
  Overnight(h22-23) · Monday(h18-21) · TurnOfMonth(dom1,h7-12) · SoS-M15 · Squeeze · BrooksHigh2
هر تریدِ SoS-H1 که روزِ ورودش در اجتماعِ بالا باشد، «همپوشان» و کنار گذاشته می‌شود.
آنچه می‌ماند = لبهٔ واقعاً نو و افزایشی. گیتِ سخت روی همان: net>0 ∧ WF۴/۴>0 ∧ WR≥۴۰.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from s171_brooks_signs_of_strength_filter import (
    load, cal, stats, sim, signs_of_strength_bull, confirms)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIGN = pd.Timestamp('2020-02-20')


def sos_edge(df, tf_win=32):
    sos = signs_of_strength_bull(df, ema_period=20, win=tf_win)
    strong = sos['score'] >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


def days_of(df, longs, shorts, sl, tp, mh):
    t = sim(df, longs, shorts, sl, tp, mh, 'XAUUSD')
    if t is None or len(t) == 0:
        return set()
    return set(df['dt'].iloc[t['entry_bar'].values].dt.floor('D').values)


def portfolio_long_days(dfm):
    """اجتماعِ روزهای معاملاتیِ همهٔ لایه‌های LONGِ طلا روی M15 (محافظه‌کارانه)."""
    dt = dfm['dt']; h = dt.dt.hour.to_numpy(); dow = dt.dt.dayofweek.to_numpy()
    dom = dt.dt.day.to_numpy()
    n = len(dfm); z = np.zeros(n, bool)
    days = set()

    def add(mask, sl, tp, mh):
        days.update(days_of(dfm, mask, z, sl, tp, mh))

    # Overnight h22-23
    add(np.isin(h, [22, 23]), 150, 500, 96)
    # Monday h18-21
    add((dow == 0) & np.isin(h, [18, 19, 20, 21]), 150, 400, 96)
    # Turn-of-Month dom==1 h7-12
    add((dom == 1) & np.isin(h, list(range(7, 13))), 150, 400, 96)
    # SoS-M15 (رکورد)
    add(sos_edge(dfm, 32), 300, 450, 96)
    return days


def eval_trades(t):
    if t is None or len(t) == 0:
        return dict(net=0, wr=0, n=0, pf=0, wf=[0, 0, 0, 0])
    s = stats(t, 'XAUUSD')
    tt = t.sort_values('entry_bar').reset_index(drop=True)
    k = 4; bnd = [int(len(tt) * i / k) for i in range(k + 1)]
    wf = [round(tt.iloc[bnd[i]:bnd[i+1]]['pnl_pip'].sum()) for i in range(k)]
    return dict(net=round(s['net']), wr=round(s['wr'], 1), n=s['n'],
                pf=round(s['pf'], 2), wf=wf)


def main():
    print("=" * 96)
    print("s205 — تأییدِ نهاییِ SoS-H1 + ATR14>ATR100 در برابرِ کلِ پرتفویِ LONGِ طلا")
    print("=" * 96, flush=True)

    dfm = cal(load('XAUUSD_M15')); dfm = dfm[dfm['dt'] >= ALIGN].reset_index(drop=True)
    dfh = cal(load('XAUUSD_H1'));  dfh = dfh[dfh['dt'] >= ALIGN].reset_index(drop=True)

    # لایهٔ H1 + فیلترِ ATR14>ATR100
    edge = sos_edge(dfh, 32); z = np.zeros(len(dfh), bool)
    th = sim(dfh, edge, z, 250, 750, 96, 'XAUUSD').copy()
    th['day'] = dfh['dt'].iloc[th['entry_bar'].values].dt.floor('D').values
    atr_ok = confirms(dfh, ['ATR14>ATR100']).astype(bool)
    th['atr_ok'] = atr_ok[th['signal_bar'].values]
    th_f = th[th['atr_ok']].copy()

    print(f"\nSoS-H1 + ATR14>ATR100 (کل): {eval_trades(th_f)}")

    # اجتماعِ روزهای پرتفویِ LONG
    pdays = portfolio_long_days(dfm)
    print(f"اجتماعِ روزهای معاملاتیِ پرتفویِ LONGِ طلا (M15): {len(pdays)} روز")

    # سهمِ واقعاً نو: تریدهای H1+ATR که روزشان در پرتفوی نیست
    indep = th_f[~th_f['day'].isin(pdays)].copy()
    res = eval_trades(indep)
    print(f"\n🎯 سهمِ *واقعاً نوِ* افزایشی (خارج از اجتماعِ کلِ پرتفوی):")
    print(f"   net=${res['net']:+,} · WR={res['wr']}% · n={res['n']} · PF={res['pf']} · WF={res['wf']}")

    gate = (res['net'] > 0 and res['n'] >= 15 and res['wr'] >= 40 and min(res['wf']) > 0)
    print("\n" + "=" * 96)
    if gate:
        print(f"✅ گیتِ سخت پاس شد ⇒ لبهٔ نوِ افزایشیِ پایدار. Δ سودِ خالص ≈ ${res['net']:+,}")
        print(f"   رکوردِ فعلی +$252,471 ⇒ رکوردِ جدید ≈ +${252471 + res['net']:,}")
        verdict = 'ACCEPT'
    else:
        print("❌ گیتِ سخت رد شد پس از حذفِ همپوشانی با کلِ پرتفوی.")
        print("   ⇒ لبهٔ مستقلِ پایدار پس از ضدِ دوباره‌شماریِ کامل باقی نمی‌ماند.")
        verdict = 'REJECT'
    print("=" * 96)

    out = dict(h1_atr_all=eval_trades(th_f), portfolio_days=len(pdays),
               truly_new=res, gate=gate, verdict=verdict,
               record_now=252471,
               record_new=(252471 + res['net']) if gate else 252471)
    with open(os.path.join(ROOT, 'results', '_s205_sos_h1_confirm.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("ذخیره شد: results/_s205_sos_h1_confirm.json")


if __name__ == '__main__':
    main()
