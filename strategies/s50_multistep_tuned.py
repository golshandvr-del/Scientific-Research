"""
استراتژی ۵۰ — ریزتنظیمِ خروجِ چند-پله‌ای برای بازگرداندنِ PF شمارشی به بالای ۱.۳
================================================================================
ادامهٔ S49. در S49 پیکربندیِ «۳سطح متعادل» به WR=64.5٪ + اکشن/روز=5.15 + dPF=1.57
رسید، اما PF شمارشی 1.265 بود (کمی زیرِ ۱.۳). فرضیه: scale-out زیاد در سطوحِ اول،
دُمِ سودِ بزرگ را می‌بُرد. راهِ حل: کسرِ بستنِ زودهنگام را کم و تریلینگ را بازتر
کنیم تا نیمهٔ باقی‌ماندهٔ بزرگ‌تری روندهای بزرگ را شکار کند — بدونِ افتِ WR زیرِ ۶۰
یا اکشن زیرِ ۵.

probaها از cacheِ S49 خوانده می‌شوند (بدونِ آموزشِ مجدد). فقط جاروبِ پارامترِ خروج.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from features import build_features
from dynamic_backtest import run_multistep_backtest, daily_pnl_stats
from multipair import build_multipair_features
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SL_M = 1.5; SPREAD = 0.20
import os as _os
THRESH_L = float(_os.environ.get('THL', '0.68'))
THRESH_S = float(_os.environ.get('THS', '0.66'))
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s49_proba_cache.npz')

print("بارگذاری داده + feature ...", flush=True)
df = load_data()
n = len(df); c = df['close'].values
atr = ind.atr(df, 14)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
cand_long = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
cand_short = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
mp = build_multipair_features(df)
align_long = mp['mp_align_long'].fillna(0).values.astype(bool)
align_short = mp['mp_align_short'].fillna(0).values.astype(bool)
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days

assert os.path.exists(CACHE), "cache نیست؛ ابتدا s49 را اجرا کنید."
z = np.load(CACHE); ens_long = z['ens_long']; ens_short = z['ens_short']
entries_L = cand_long & ~np.isnan(ens_long) & (ens_long >= THRESH_L) & align_long
entries_S = cand_short & ~np.isnan(ens_short) & (ens_short >= THRESH_S) & align_short
print(f"سیگنال‌ها: L={int(entries_L.sum())}  S={int(entries_S.sum())}", flush=True)


def run_ms(entries, direction, tp_mults, tp_fracs, trail):
    return run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
        tp_mults=tp_mults, tp_fracs=tp_fracs, trail_mult=trail, be_offset=0.15,
        spread=SPREAD, max_hold=HZ * 4, allow_overlap=False)


def merge_dedup(frames):
    fs = [t for t in frames if t is not None and len(t) > 0]
    if not fs: return None
    allt = pd.concat(fs, ignore_index=True).sort_values('entry_bar')
    return allt.drop_duplicates(subset='entry_bar', keep='first').reset_index(drop=True)


def metrics(tr):
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else float('inf')
    wr = (tr['pnl'] > 0).mean() * 100; exp = tr['pnl'].mean()
    d = daily_pnl_stats(tr)
    return wr, pf, exp, d


# جاروبِ هدفمند: کسرِ کمترِ سطحِ اول + تریلینگِ بازتر
# هر تاپل: (نام، tp_mults، tp_fracs، trail)
CONFIGS = [
    # ترکیبِ دو اهرمِ مخالف: کیفیتِ بالاترِ ورود (thr) + سطوحِ ریزترِ scale-out.
    ("K ۵سطح ریز trail2.2", (0.6, 1.0, 1.5, 2.1, 3.0), (0.12, 0.13, 0.15, 0.20, 0.40), 2.2),
    ("L ۶سطح ریز trail2.2", (0.5, 0.9, 1.3, 1.8, 2.4, 3.2), (0.10, 0.12, 0.13, 0.15, 0.20, 0.30), 2.2),
    ("M ۵سطح دُم‌بزرگ    ", (0.6, 1.0, 1.5, 2.2, 3.2), (0.12, 0.12, 0.14, 0.17, 0.45), 2.5),
]

print("\n نام                | WR%  |  PF   |  dPF  | exp$   | ورود/روز | اکشن/روز | وضعیت", flush=True)
print("-" * 92, flush=True)
best = None
for name, tpm, tpf, tr_m in CONFIGS:
    trL = run_ms(entries_L, 'long', tpm, tpf, tr_m)[1]
    trS = run_ms(entries_S, 'short', tpm, tpf, tr_m)[1]
    tr = merge_dedup([trL, trS])
    if tr is None or len(tr) == 0:
        print(f" {name}: no trades"); continue
    wr, pf, exp, d = metrics(tr)
    apd = d.get('actions_per_calendar_day', 0)
    tpd = d['trades_per_calendar_day']
    ok = "✅ همه" if (wr > 60 and pf > 1.3 and apd >= 5) else \
         ("~نزدیک" if (wr > 60 and apd >= 5 and pf > 1.25) else "")
    print(f" {name}| {wr:5.2f}| {pf:.3f} | {d['daily_profit_factor']:.2f}  | "
          f"{exp:+.3f} |  {tpd:.2f}   |  {apd:.2f}   | {ok}", flush=True)
    score = (wr > 60) * 1000 + (apd >= 5) * 1000 + pf * 100
    if best is None or score > best[0]:
        best = (score, name, wr, pf, d['daily_profit_factor'], apd, exp)

if best:
    print(f"\nبهترین: {best[1].strip()} → WR={best[2]:.2f}% PF={best[3]:.3f} "
          f"dPF={best[4]:.2f} اکشن/روز={best[5]:.2f} exp={best[6]:+.3f}$", flush=True)
print("\nتمام.", flush=True)
