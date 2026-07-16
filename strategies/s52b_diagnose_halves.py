"""
S52b — تشخیصِ منبعِ بی‌ثباتیِ نیمهٔ اول: جریانِ long مقصر است یا short؟
================================================================================
S52 نشان داد گیتِ ریبون نیمهٔ اول را از زیان به بریک‌ایون آورد اما هنوز <۱.۳ است.
این اسکریپت جریانِ long و short را جداگانه در هر نیمه گزارش می‌کند تا بفهمیم کدام
جریان در نیمهٔ اول (رژیمِ رنج/نوسانیِ ۲۰۲۰–۲۰۲۳) ضعیف است — کلیدِ پایدارسازی.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from dynamic_backtest import run_multistep_backtest, daily_pnl_stats
from multipair import build_multipair_features
from ma_ribbon import build_ribbon_features
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SL_M = 1.5; SPREAD = 0.20
THRESH_L = 0.69; THRESH_S = 0.67
TP_MULTS = (0.5, 0.9, 1.3, 1.8, 2.4, 3.2)
TP_FRACS = (0.10, 0.12, 0.13, 0.15, 0.20, 0.30)
TRAIL = 2.2; BE = 0.15
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s49_proba_cache.npz')

df = load_data(); n = len(df); c = df['close'].values
atr = ind.atr(df, 14)
ema50 = ind.ema(df['close'], 50).values; ema200 = ind.ema(df['close'], 200).values
cand_long = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
cand_short = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
mp = build_multipair_features(df)
align_long = mp['mp_align_long'].fillna(0).values.astype(bool)
align_short = mp['mp_align_short'].fillna(0).values.astype(bool)
rib = build_ribbon_features(df, tfs=('H1', 'H4'))
rib_up = (rib['h4_rib_order'].fillna(0) >= 0.6).values
rib_dn = (rib['h4_rib_order'].fillna(0) <= -0.6).values
z = np.load(CACHE); ens_long = z['ens_long']; ens_short = z['ens_short']

L = cand_long & ~np.isnan(ens_long) & (ens_long >= THRESH_L) & align_long & rib_up
S = cand_short & ~np.isnan(ens_short) & (ens_short >= THRESH_S) & align_short & rib_dn


def run_ms(entries, direction):
    return run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
        tp_mults=TP_MULTS, tp_fracs=TP_FRACS, trail_mult=TRAIL, be_offset=BE,
        spread=SPREAD, max_hold=HZ * 4, allow_overlap=False)[1]


def rep(tr, label):
    if tr is None or len(tr) == 0:
        print(f"  {label}: بدونِ معامله"); return
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else 99
    wr = (tr['pnl'] > 0).mean() * 100; exp = tr['pnl'].mean()
    print(f"  {label}: n={len(tr)} WR={wr:.1f}% PF={pf:.3f} exp={exp:+.3f}$ pnl={tr['pnl'].sum():+.0f}$")


mid = n // 2
trL = run_ms(L, 'long'); trS = run_ms(S, 'short')
print("=== جریانِ LONG (با گیتِ ریبونِ H4) ===")
rep(trL, "کل      ")
rep(trL[trL['entry_bar'] < mid], "نیمهٔ اول")
rep(trL[trL['entry_bar'] >= mid], "نیمهٔ دوم")
print("\n=== جریانِ SHORT (با گیتِ ریبونِ H4) ===")
rep(trS, "کل      ")
rep(trS[trS['entry_bar'] < mid], "نیمهٔ اول")
rep(trS[trS['entry_bar'] >= mid], "نیمهٔ دوم")

# آیا اصلاً در نیمهٔ اول سیگنالِ short وجود دارد؟
print(f"\nسیگنالِ short نیمهٔ اول: {int(S[:mid].sum())}  | نیمهٔ دوم: {int(S[mid:].sum())}")
print(f"سیگنالِ long  نیمهٔ اول: {int(L[:mid].sum())}  | نیمهٔ دوم: {int(L[mid:].sum())}")
print("\nتمام.")
