"""
استراتژی ۴۱ — پرتفوی جریان‌های مستقل برای حمله به قید فرکانس (Frequency Portfolio)

طرح: گروه A / P02 — اولویت جدید ۱ پس از P01.
هدف: PF>1.3 + WR>60 + ≥۵ معامله/روز هم‌زمان.

منطق ریاضی (بخش ۱ نقشه راه):
  «تضاد WR↔فرکانس یک قانون درون-استراتژی است، نه بین-استراتژی. اگر K جریان مستقل
  هرکدام WR≥۶۰ و ~۱–۲ معامله/روز داشته باشند، پرتفوی‌شان WR وزنی همان >۶۰ را نگه
  می‌دارد ولی فرکانس‌ها جمع می‌شوند.»

درسِ S36 (Bull+Bear رسید به tpd=4.24 اما WR=58.9): مشکل این بود که فرکانس را با
شل‌کردنِ thr به دست آورد (WR را کشت). این‌جا برعکس: هر جریان با thr سخت‌گیرانه
نگه داشته می‌شود (WR بالا)، و فرکانس از **جمعِ جریان‌های ناهمبسته در زمان** می‌آید.

جریان‌های کاندید (هرکدام باید مستقلاً WR≥۶۰ باشد):
  A) long در uptrend، نقطه‌ی P01: TP1.4/SL1.7
  B) long در uptrend، نقطه‌ی S25 پرکیفیت: TP1.0/SL1.5
  C) short در downtrend (رژیم زمانیِ ناهمبسته با long) — مدل جداگانه
  D) long با horizonِ کوتاه‌تر (HZ=24) — تایم‌افقِ متفاوت ⇒ سیگنالِ زمانیِ متفاوت

روش: هر جریان جداگانه walk-forward (L4)، سپس ادغام با dedup (اگر دو جریان در
پنجره‌ی زمانیِ یک معامله سیگنال دهند، یکی حساب می‌شود). گزارش WR/PF/exp/tpd پرتفوی.
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np
import pandas as pd
from scipy.stats import binomtest
import warnings; warnings.filterwarnings('ignore')

from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from _base_s25 import (SEEDS, purged_walk_forward)

SPREAD = 0.20


def _pf(tr):
    gw = tr[tr['outcome'] == 'win']['pnl'].sum()
    gl = abs(tr[tr['outcome'] == 'loss']['pnl'].sum())
    return gw / gl if gl > 0 else float('inf')


def build_stream_signals():
    """برای هر جریان، سیگنال‌های ورود (signal_bar) + جهت + TP/SL را می‌سازد."""
    df = load_data()
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values

    print("ساخت featureها (۵۹) ...")
    feats = build_features(df)
    cols = list(feats.columns)

    up = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
    dn = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)

    def train_stream(cand, hz, tp_m, sl_m, direction):
        y = make_target(df, hz, tp_m, sl_m, atr, direction)
        data = feats.copy(); data['y'] = y; data['cand'] = cand
        v = data.dropna(subset=cols + ['y'])
        v = v[v['cand']]
        X = v[cols].values; Y = v['y'].values.astype(int); idx = v.index.values
        probas = [purged_walk_forward(X, Y, idx, n, seed=s) for s in SEEDS]
        proba = np.nanmean(np.vstack(probas), axis=0)
        return proba

    print("جریان A: long uptrend TP1.4/SL1.7 HZ48 ...")
    pA = train_stream(up, 48, 1.4, 1.7, 'long')
    print("جریان B: long uptrend TP1.0/SL1.5 HZ48 ...")
    pB = train_stream(up, 48, 1.0, 1.5, 'long')
    print("جریان C: short downtrend TP1.4/SL1.7 HZ48 ...")
    pC = train_stream(dn, 48, 1.4, 1.7, 'short')
    print("جریان D: long uptrend TP1.0/SL1.5 HZ24 (تایم‌افق کوتاه) ...")
    pD = train_stream(up, 24, 1.0, 1.5, 'long')

    return dict(df=df, atr=atr, up=up, dn=dn,
                pA=pA, pB=pB, pC=pC, pD=pD)


def eval_stream(df, atr, proba, thr, cand, tp_m, sl_m, hz, direction, label):
    ent = (~np.isnan(proba)) & (proba >= thr) & cand
    s, tr = run_backtest(df, ent, None, None, direction, SPREAD, hz,
                         sl_series=sl_m * atr.values, tp_series=tp_m * atr.values,
                         allow_overlap=False)
    if s['n_trades'] == 0:
        print(f"{label}: no trades"); return None
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    tpd = s['n_trades'] / span * 7 / 5
    pf = _pf(tr)
    be = sl_m / (tp_m + sl_m) * 100
    wins = int(round(s['win_rate'] / 100 * s['n_trades']))
    pv = binomtest(wins, s['n_trades'], be / 100, alternative='greater').pvalue
    print(f"{label}: n={s['n_trades']} WR={s['win_rate']:.2f}% PF={pf:.3f} "
          f"exp={s['expectancy']:+.3f}$ tpd={tpd:.2f} p(WR>{be:.0f})={pv:.4f}")
    return tr


def merge_portfolio(df, streams, label='PORTFOLIO'):
    """
    ادغام معاملات چند جریان با dedup زمانی:
    معاملات را بر حسب entry_bar مرتب می‌کنیم؛ اگر ورودِ جدید پیش از بسته‌شدنِ
    معامله‌ی فعلیِ پرتفوی باشد، رد می‌شود (یک پوزیشن هم‌زمان، مثل حساب واقعی).
    """
    all_tr = []
    for tr in streams:
        if tr is not None and len(tr) > 0:
            all_tr.append(tr)
    if not all_tr:
        print(f"{label}: no trades"); return None
    m = pd.concat(all_tr, ignore_index=True).sort_values('entry_bar').reset_index(drop=True)
    kept = []
    busy_until = -1
    for _, row in m.iterrows():
        if row['entry_bar'] <= busy_until:
            continue
        kept.append(row)
        busy_until = row['exit_bar']
    k = pd.DataFrame(kept)
    n = len(k)
    wr = (k['outcome'] == 'win').mean() * 100
    pf = _pf(k)
    exp = k['pnl'].mean()
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    tpd = n / span * 7 / 5
    wins = int((k['outcome'] == 'win').sum())
    pv = binomtest(wins, n, 0.60, alternative='greater').pvalue
    print(f"\n{'='*70}\n{label}: n={n} WR={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ "
          f"tpd={tpd:.2f} p(WR>60)={pv:.4f}\n{'='*70}")
    return dict(n=n, wr=wr, pf=pf, exp=exp, tpd=tpd, pv=pv, trades=k)


def run():
    print("=" * 70)
    print("S41 — Frequency Portfolio (P02): جمعِ جریان‌های مستقل")
    print("=" * 70)
    st = build_stream_signals()
    df, atr, up, dn = st['df'], st['atr'], st['up'], st['dn']

    print("\n--- ارزیابیِ مستقلِ هر جریان (نقطه‌ی سخت‌گیرانه) ---")
    trA = eval_stream(df, atr, st['pA'], 0.66, up, 1.4, 1.7, 48, 'long', 'A long P01 thr0.66')
    trB = eval_stream(df, atr, st['pB'], 0.70, up, 1.0, 1.5, 48, 'long', 'B long S25 thr0.70')
    trC = eval_stream(df, atr, st['pC'], 0.66, dn, 1.4, 1.7, 48, 'short', 'C short thr0.66')
    trD = eval_stream(df, atr, st['pD'], 0.68, up, 1.0, 1.5, 24, 'long', 'D long HZ24 thr0.68')

    print("\n--- پرتفویِ ترکیبی (فقط جریان‌هایی که مستقلاً WR≥۶۰ دارند) ---")
    # همه‌ی ترکیب‌ها را امتحان می‌کنیم
    merge_portfolio(df, [trA, trB], 'PF: A+B')
    merge_portfolio(df, [trA, trC], 'PF: A+C')
    merge_portfolio(df, [trA, trB, trC], 'PF: A+B+C')
    merge_portfolio(df, [trA, trB, trC, trD], 'PF: A+B+C+D')

    # نسخه‌ی فرکانس‌محور: thr کمی پایین‌تر برای هر جریان تا فرکانس بالا رود
    print("\n--- نسخه‌ی فرکانس‌محور (thr متعادل روی هر جریان) ---")
    trA2 = eval_stream(df, atr, st['pA'], 0.62, up, 1.4, 1.7, 48, 'long', 'A2 thr0.62')
    trB2 = eval_stream(df, atr, st['pB'], 0.64, up, 1.0, 1.5, 48, 'long', 'B2 thr0.64')
    trC2 = eval_stream(df, atr, st['pC'], 0.62, dn, 1.4, 1.7, 48, 'short', 'C2 thr0.62')
    trD2 = eval_stream(df, atr, st['pD'], 0.62, up, 1.0, 1.5, 24, 'long', 'D2 thr0.62')
    merge_portfolio(df, [trA2, trB2, trC2, trD2], 'PF2: A2+B2+C2+D2 (freq)')
    merge_portfolio(df, [trA2, trC2, trD2], 'PF2: A2+C2+D2 (freq, no overlap B)')


if __name__ == '__main__':
    run()
