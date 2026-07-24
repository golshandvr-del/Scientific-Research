"""
s218_friday_continuation_layer.py — لایهٔ نو: Friday-Morning + فیلترِ Continuation
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪. رکورد قبلی = +$262,519.

پاسخِ مستقیم به User Note:
  کاربر جمعه صبح یک روندِ صعودیِ قویِ خالص روی M5/M15 دید، اما سایت کور بود. علت‌یابی:
    (الف) S214 (لایهٔ فعالِ pre-EOM) شرطِ «۴ کندلِ صعودیِ *غیر-climactic*» دارد ⇒ در رالیِ
          قوی/پرشتاب که کندل‌ها climactic می‌شوند، فیلترِ ضد-climax سیگنال را رد می‌کند.
    (ب) لایهٔ Friday-H4 (S210) هرگز به روتر زنده متصل نشده بود.

فرضیهٔ این گام (راهِ سوم — لایهٔ جدید + پاسخِ User Note):
  یک لایهٔ صریحِ «Friday-Morning Continuation»: در ساعاتِ صبحِ جمعه، هنگامی که روندِ
  کوتاه‌مدت صعودی است و مومنتومِ تداوم (رشتهٔ کندلِ صعودی) وجود دارد — *بدونِ* شرطِ
  سختگیرانهٔ ضد-climax — BUY بده. این دقیقاً setup‌ای است که کاربر دید.

  همچنین به‌عنوان کنترل، واریانتِ «Friday-Morning خام» (فقط ساعت×روز، بدونِ فیلتر) و
  «+continuation» را مقایسه می‌کنیم تا اثبات شود منبعِ سود چیست (ablation).

قانونِ مولتی‌تایم‌فریم: روی XAUUSD M5/M15/M30/H1 (و EURUSD) مستقل تست می‌شود؛
هر TF با TP/SL مخصوصِ خودش (اشتباهِ رایج: یکسان برای همه).
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
CAP, RISK = 10000.0, 1.0

# ساعاتِ صبحِ جمعه (UTC) بر پایهٔ TF — کندل‌های ۰۰..۱۲ UTC (پایانِ NY + آسیا + آغازِ لندن)
FRI_MORNING = {
    'M5':  list(range(0, 12)),
    'M15': list(range(0, 12)),
    'M30': list(range(0, 12)),
    'H1':  list(range(0, 12)),
}
TPSL = {
    'M5':  [(120, 80, 24), (200, 120, 24)],
    'M15': [(250, 150, 16), (400, 200, 20)],
    'M30': [(400, 200, 12), (600, 300, 16)],
    'H1':  [(600, 300, 8), (800, 400, 10)],
}
PAIRS_TF = [('XAUUSD', 'M5'), ('XAUUSD', 'M15'), ('XAUUSD', 'M30'), ('XAUUSD', 'H1'),
            ('EURUSD', 'M15'), ('EURUSD', 'M30')]


def load(pair, tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', f'{pair}_{tf}.csv'))
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour; df['dow'] = df['dt'].dt.dayofweek
    return df.reset_index(drop=True)


def ema(x, n):
    a = 2.0/(n+1.0); out = np.empty(len(x)); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a*x[i]+(1-a)*out[i-1]
    return out


def run(df, sig, sl, tp, mh, asset):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, sl, tp, asset, max_hold=mh)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st


def gate(df, sig, sl, tp, mh, asset):
    st = run(df, sig, sl, tp, mh, asset)
    if st is None or st['n_trades'] < 30:
        return None
    n = len(df); half = n//2
    s1 = run(df.iloc[:half].reset_index(drop=True), sig[:half], sl, tp, mh, asset)
    s2 = run(df.iloc[half:].reset_index(drop=True), sig[half:], sl, tp, mh, asset)
    wf = []
    for k in range(4):
        a = k*(n//4); b = n if k == 3 else (k+1)*(n//4)
        sk = run(df.iloc[a:b].reset_index(drop=True), sig[a:b], sl, tp, mh, asset)
        wf.append(sk['net_profit'] if sk else 0.0)
    both = (s1 and s1['net_profit'] > 0) and (s2 and s2['net_profit'] > 0)
    ok = st['net_profit'] > 0 and both and min(wf) > 0 and st['win_rate'] >= 40
    return dict(net=st['net_profit'], wr=st['win_rate'], n=st['n_trades'], pf=st['profit_factor'],
                h1=(s1['net_profit'] if s1 else 0), h2=(s2['net_profit'] if s2 else 0),
                wf=wf, wf_min=min(wf), both=both, ok=ok)


def build_signals(df, tf):
    c = df['close'].values; o = df['open'].values
    ef = ema(c, 20); es = ema(c, 100)
    up_bar = (c > o).astype(int)
    runc = np.zeros(len(c), int)
    for i in range(1, len(c)):
        runc[i] = runc[i-1]+1 if up_bar[i] else 0
    fri_morning = (df['dow'].values == 4) & np.isin(df['hour'].values, FRI_MORNING[tf])
    trend_up = ef > es
    momentum = runc >= 3
    raw = fri_morning                                  # A) خامِ جمعه صبح
    cont = fri_morning & trend_up & momentum            # B) جمعه صبح + تداومِ روند
    return raw, cont


def main():
    print("=" * 92)
    print("s218 — Friday-Morning Continuation (پاسخِ User Note + راهِ سومِ لایهٔ جدید)")
    print("=" * 92, flush=True)
    winners = []
    for pair, tf in PAIRS_TF:
        try:
            df = load(pair, tf)
        except FileNotFoundError:
            continue
        # فقط پنجرهٔ رکورد (۲۰۲۰+) برای هم‌ترازی با معیارِ رسمیِ رکورد
        m5start = load(pair, 'M5')['dt'].iloc[0] if os.path.exists(os.path.join(ROOT,'data',f'{pair}_M5.csv')) else df['dt'].iloc[0]
        dfR = df[df['dt'] >= m5start].reset_index(drop=True)
        raw, cont = build_signals(dfR, tf)
        for label, sig in [('RAW-FriMorning', raw), ('CONT-FriMorning', cont)]:
            if sig.sum() < 30:
                continue
            for (tp, sl, mh) in TPSL[tf]:
                g = gate(dfR, sig, sl, tp, mh, pair)
                if g is None:
                    continue
                mark = "✅" if g['ok'] else "  "
                if g['ok'] or g['net'] > 800:
                    print(f"{mark} {pair}-{tf} {label} TP{tp}/SL{sl}/mh{mh}: "
                          f"net=${g['net']:+,.0f} WR={g['wr']:.1f}% n={g['n']} PF={g['pf']:.2f} "
                          f"h1=${g['h1']:+,.0f} h2=${g['h2']:+,.0f} WFmin=${g['wf_min']:+,.0f}", flush=True)
                if g['ok']:
                    winners.append(dict(pair=pair, tf=tf, label=label, tp=tp, sl=sl, mh=mh, **g))
    print("\n" + "=" * 92)
    print(f"کاندیدِ گیت-پاس: {len(winners)}")
    winners.sort(key=lambda w: -w['net'])
    for w in winners:
        print(f"  {w['pair']}-{w['tf']} {w['label']} TP{w['tp']}/SL{w['sl']}: "
              f"net=${w['net']:+,.0f} WR={w['wr']:.1f}% n={w['n']} h1=${w['h1']:+,.0f} h2=${w['h2']:+,.0f}")
    with open(os.path.join(RESULTS, '_s218_friday_continuation.json'), 'w') as f:
        json.dump(winners, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s218_friday_continuation.json")


if __name__ == '__main__':
    main()
