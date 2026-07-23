"""
s200_overnight_add_hour21.py — بهبودِ لایهٔ Overnight (S139): افزودنِ ساعتِ ۲۱ UTC
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪ کف.
> راهِ #۱ (بهبودِ وضعیتِ فعلی).

کشفِ زنجیره‌ایِ این نشست (از تحلیلِ H1):
  • فایلِ رکوردِ S139 (GoldOvernightDrift_NetProfit_171738.md) صراحتاً می‌گوید:
    «قوی‌ترین ورود ساعتِ ۲۱ UTC است (t=+7.78)» — اما نسخهٔ فعالِ رکورد فقط ساعاتِ
    [22, 23] را entry می‌گیرد و ساعتِ ۲۱ را فقط «approaching» می‌شمارد!
  • تستِ H1 نشان داد h21-23 بسیار پرسودتر از h22-23 است (روی هر دو TF).

پرسش: آیا افزودنِ ساعتِ ۲۱ UTC به entryهای لایهٔ Overnightِ M15 یک بهبودِ واقعی
(net بالاتر + گیتِ سخت پاس + WR≥40٪) است؟

روش (سیب‌به‌سیب با رکورد، روی M15 که رکورد بر آن بنا شده):
  • داده: XAUUSD_M15 کامل.
  • baseline = h22-23 با پارامترِ رکورد SL150/TP500/mh96.
  • کاندید  = h21-23 با همان پارامتر.
  • همچنین سهمِ *مستقلِ ساعتِ ۲۱* (بخشِ افزوده) به‌تنهایی سنجیده می‌شود.
  • گیتِ سخت: net>0 و هر دو نیمه مثبت و WF ۴/۴ مثبت و WR≥40٪.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

RESULTS = os.path.join(ROOT, 'results')
DATA_M15 = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
CAP, RISK = 10000.0, 1.0
SL, TP, MH = 150, 500, 96   # پارامترِ رکوردِ S139


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    return df.reset_index(drop=True)


def run(df, hours, sl=SL, tp=TP, mh=MH):
    long_sig = np.isin(df['hour'].values, list(hours))
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def gate(df, hours, sl=SL, tp=TP, mh=MH):
    n = len(df)
    st, _ = run(df, hours, sl, tp, mh)
    if st is None:
        return None
    net = st['net_profit']; wr = st['win_rate']; ntr = st['n_trades']
    half = n // 2
    s1, _ = run(df.iloc[:half].reset_index(drop=True), hours, sl, tp, mh)
    s2, _ = run(df.iloc[half:].reset_index(drop=True), hours, sl, tp, mh)
    h1 = s1['net_profit'] if s1 else 0.0; h2 = s2['net_profit'] if s2 else 0.0
    wf = []
    for k in range(4):
        a = k * (n // 4); b = n if k == 3 else (k + 1) * (n // 4)
        sK, _ = run(df.iloc[a:b].reset_index(drop=True), hours, sl, tp, mh)
        wf.append(sK['net_profit'] if sK else 0.0)
    wf_min = min(wf)
    both = h1 > 0 and h2 > 0
    ok = net > 0 and both and wf_min > 0 and wr >= 40.0
    return dict(net=float(net), wr=float(wr), n=int(ntr), h1=float(h1), h2=float(h2),
                wf=[float(x) for x in wf], wf_min=float(wf_min), both=bool(both), ok=bool(ok))


def main():
    print("=" * 92)
    print("s200 — بهبودِ Overnight (S139): افزودنِ ساعتِ ۲۱ UTC به entryها (M15)")
    print("=" * 92, flush=True)

    df = load(DATA_M15)
    print(f"داده: {len(df):,} کندلِ M15 ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})")
    print(f"پارامتر: SL{SL}/TP{TP}/mh{MH} (پارامترِ رکوردِ S139)\n")

    print("── baseline رکورد: ساعاتِ [22, 23] ──")
    gb = gate(df, [22, 23])
    print(f"   net=${gb['net']:+,.0f}  WR={gb['wr']:.1f}%  n={gb['n']}  "
          f"H1=${gb['h1']:+,.0f} H2=${gb['h2']:+,.0f}  WFmin=${gb['wf_min']:+,.0f}  "
          f"{'✅گیت' if gb['ok'] else '—'}")

    print("\n── کاندیدِ بهبود: ساعاتِ [21, 22, 23] ──")
    gc = gate(df, [21, 22, 23])
    print(f"   net=${gc['net']:+,.0f}  WR={gc['wr']:.1f}%  n={gc['n']}  "
          f"H1=${gc['h1']:+,.0f} H2=${gc['h2']:+,.0f}  WFmin=${gc['wf_min']:+,.0f}  "
          f"WF={['%+.0f'%x for x in gc['wf']]}  {'✅گیت' if gc['ok'] else '—'}")

    print("\n── سهمِ مستقلِ ساعتِ ۲۱ (بخشِ افزوده) به‌تنهایی ──")
    g21 = gate(df, [21])
    print(f"   net=${g21['net']:+,.0f}  WR={g21['wr']:.1f}%  n={g21['n']}  "
          f"H1=${g21['h1']:+,.0f} H2=${g21['h2']:+,.0f}  WFmin=${g21['wf_min']:+,.0f}  "
          f"WF={['%+.0f'%x for x in g21['wf']]}  {'✅گیت' if g21['ok'] else '—'}")

    delta = gc['net'] - gb['net']
    print(f"\n{'='*92}")
    print(f"Δ بهبود (h21-23 منهای h22-23) = ${delta:+,.0f}")
    verdict = gc['ok'] and delta > 0 and g21['ok']
    if verdict:
        print(f"✅✅ بهبودِ تأییدشده: افزودنِ ساعتِ ۲۱ سود را ${delta:+,.0f} افزایش می‌دهد،")
        print(f"    کلِ لایه (h21-23) گیتِ سخت را پاس می‌کند و بخشِ افزوده (h21) هم مستقلاً گیت-پاس است.")
    else:
        print(f"⚠️ بهبود تأیید نشد (یکی از گیت‌ها رد شد). جزئیات بالا.")

    out = dict(param=dict(sl=SL, tp=TP, mh=MH),
               baseline_h2223=gb, candidate_h2123=gc, added_h21=g21,
               delta=float(delta), verdict=bool(verdict))
    with open(os.path.join(RESULTS, '_s200_overnight_add21.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s200_overnight_add21.json")


if __name__ == '__main__':
    main()
