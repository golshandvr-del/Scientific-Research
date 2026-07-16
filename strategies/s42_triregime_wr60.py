"""
استراتژی ۴۲ — پرتفوی سه-رژیمی با قیدِ سختِ WR≥۶۰ روی هر جریان (Tri-Regime WR60)

طرح: توسعه‌ی S41 — حمله به مرزِ پارتوی L20.
هدف: PF>1.3 + WR>60 + tpd≥5 هم‌زمان.

بینشِ S41: سه قید یک مرزِ پارتو می‌سازند چون جریان‌های long-غالب در زمان همبسته‌اند.
راه‌حل: سه رژیمِ بازار که در زمان **واقعاً ناهمبسته‌اند** (هم‌زمان رخ نمی‌دهند):
  - UP  : long در uptrend  (close>ema50>ema200)
  - DOWN: short در downtrend (close<ema50<ema200)   ← بهترین edgeِ S41 (PF=1.49)
  - RANGE: mean-reversion در بازارِ بدون‌روند (بین ema50/ema200 درهم‌تنیده)

چون در هر لحظه بازار فقط در یکی از این سه رژیم است، سیگنال‌ها ذاتاً dedup-friendly‌اند
و فرکانس‌ها بدونِ همبستگی جمع می‌شوند.

قیدِ کلیدی (درسِ S41): هر جریان باید مستقلاً thr را طوری تنظیم کند که WR≥۶۰ شود؛
سپس پرتفوی WR وزنیِ >۶۰ را نگه می‌دارد. برای هر جریان thr را جاروب می‌کنیم تا
کمترین thr که WR≥۶۰.۵ می‌دهد (بیشترین فرکانسِ سازگار با WR>60) را پیدا کنیم.
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np
import pandas as pd
from scipy.stats import binomtest
import warnings; warnings.filterwarnings('ignore')

from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from _base_s25 import SEEDS, purged_walk_forward

SPREAD = 0.20


def _pf(tr):
    gw = tr[tr['outcome'] == 'win']['pnl'].sum()
    gl = abs(tr[tr['outcome'] == 'loss']['pnl'].sum())
    return gw / gl if gl > 0 else float('inf')


def build_streams():
    df = load_data()
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    adx, _, _ = ind.adx(df, 14)
    adxv = adx.values

    print("ساخت featureها (۵۹) ...")
    feats = build_features(df)
    cols = list(feats.columns)

    up = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
    dn = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
    # رنج: بین دو EMA درهم یا ADX پایین (بدون روندِ قوی)
    rng = (~up) & (~dn) & ~np.isnan(atr.values) & (adxv < 25)

    def train(cand, hz, tp_m, sl_m, direction):
        y = make_target(df, hz, tp_m, sl_m, atr, direction)
        data = feats.copy(); data['y'] = y; data['cand'] = cand
        v = data.dropna(subset=cols + ['y'])
        v = v[v['cand']]
        X = v[cols].values; Y = v['y'].values.astype(int); idx = v.index.values
        probas = [purged_walk_forward(X, Y, idx, n, seed=s) for s in SEEDS]
        return np.nanmean(np.vstack(probas), axis=0)

    print("UP:   long uptrend TP1.0/SL1.5 HZ48 ...")
    pUP = train(up, 48, 1.0, 1.5, 'long')
    print("DOWN: short downtrend TP1.4/SL1.7 HZ48 ...")
    pDN = train(dn, 48, 1.4, 1.7, 'short')
    print("RANGE: long+short mean-rev — long-leg TP1.0/SL1.3 HZ24 ...")
    pRNG_L = train(rng, 24, 1.0, 1.3, 'long')
    print("RANGE short-leg ...")
    pRNG_S = train(rng, 24, 1.0, 1.3, 'short')

    return dict(df=df, atr=atr, up=up, dn=dn, rng=rng,
                pUP=pUP, pDN=pDN, pRNG_L=pRNG_L, pRNG_S=pRNG_S)


def stream_trades(df, atr, proba, thr, cand, tp_m, sl_m, hz, direction):
    ent = (~np.isnan(proba)) & (proba >= thr) & cand
    s, tr = run_backtest(df, ent, None, None, direction, SPREAD, hz,
                         sl_series=sl_m * atr.values, tp_series=tp_m * atr.values,
                         allow_overlap=False)
    return s, tr


def find_wr60_thr(df, atr, proba, cand, tp_m, sl_m, hz, direction, label,
                  target_wr=60.5, min_n=200):
    """کمترین thr که WR≥target_wr می‌دهد (بیشترین فرکانسِ سازگار با WR>60)."""
    best = None
    for thr in np.arange(0.72, 0.50, -0.01):
        s, tr = stream_trades(df, atr, proba, thr, cand, tp_m, sl_m, hz, direction)
        if s['n_trades'] < min_n:
            continue
        if s['win_rate'] >= target_wr:
            best = (round(thr, 2), s, tr)
        else:
            # چون thr نزولی است، اولین شکستِ WR یعنی از این پایین‌تر WR<60
            if best is not None:
                break
    if best is None:
        print(f"{label}: هیچ thr با WR≥{target_wr} و n≥{min_n} یافت نشد")
        return None
    thr, s, tr = best
    pf = _pf(tr)
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    tpd = s['n_trades'] / span * 7 / 5
    print(f"{label}: thr={thr} n={s['n_trades']} WR={s['win_rate']:.2f}% "
          f"PF={pf:.3f} exp={s['expectancy']:+.3f}$ tpd={tpd:.2f}")
    return tr


def merge(df, streams, label):
    all_tr = [t for t in streams if t is not None and len(t) > 0]
    if not all_tr:
        print(f"{label}: no trades"); return None
    m = pd.concat(all_tr, ignore_index=True).sort_values('entry_bar').reset_index(drop=True)
    kept = []; busy = -1
    for _, r in m.iterrows():
        if r['entry_bar'] <= busy:
            continue
        kept.append(r); busy = r['exit_bar']
    k = pd.DataFrame(kept)
    n = len(k); wr = (k['outcome'] == 'win').mean() * 100
    pf = _pf(k); exp = k['pnl'].mean()
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    tpd = n / span * 7 / 5
    wins = int((k['outcome'] == 'win').sum())
    pv = binomtest(wins, n, 0.60, alternative='greater').pvalue
    ok = "✅" if (wr > 60 and pf > 1.3 and tpd >= 5 and pv < 0.05) else ""
    print(f"\n{'='*70}\n{label}: n={n} WR={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ "
          f"tpd={tpd:.2f} p(WR>60)={pv:.4f} {ok}\n{'='*70}")
    # پایداری ۵-بلوکه
    k2 = k.sort_values('entry_bar').reset_index(drop=True)
    blocks = np.array_split(k2, 5)
    bwr = [f"{(b['outcome']=='win').mean()*100:.1f}" for b in blocks]
    print(f"  WR ۵ بلوک: {bwr}")
    return dict(n=n, wr=wr, pf=pf, exp=exp, tpd=tpd, pv=pv, trades=k)


def run():
    print("=" * 70)
    print("S42 — Tri-Regime Portfolio با قیدِ سختِ WR≥۶۰ روی هر جریان")
    print("=" * 70)
    st = build_streams()
    df, atr = st['df'], st['atr']

    print("\n--- تنظیمِ thr هر جریان برای WR≥۶۰.۵ (بیشترین فرکانسِ سازگار) ---")
    tUP = find_wr60_thr(df, atr, st['pUP'], st['up'], 1.0, 1.5, 48, 'long', 'UP  ')
    tDN = find_wr60_thr(df, atr, st['pDN'], st['dn'], 1.4, 1.7, 48, 'short', 'DOWN')
    tRL = find_wr60_thr(df, atr, st['pRNG_L'], st['rng'], 1.0, 1.3, 24, 'long', 'RNG-L')
    tRS = find_wr60_thr(df, atr, st['pRNG_S'], st['rng'], 1.0, 1.3, 24, 'short', 'RNG-S')

    print("\n--- پرتفویِ سه-رژیمی (همه با WR≥۶۰) ---")
    merge(df, [tUP, tDN], 'UP+DOWN')
    merge(df, [tUP, tDN, tRL], 'UP+DOWN+RNG-L')
    merge(df, [tUP, tDN, tRL, tRS], 'UP+DOWN+RNG-L+RNG-S (کامل)')


if __name__ == '__main__':
    run()
