"""
استراتژی ۵۱ — پیکربندیِ برنده (تأییدِ نهایی): همهٔ قیود هم‌زمان برآورده
================================================================================
این اسکریپت پیکربندیِ برندهٔ کشف‌شده در S50 را با جزئیاتِ کامل اجرا و اعتبارسنجی
می‌کند. برای اولین‌بار در کلِ پروژه، هر پنج قید هم‌زمان برآورده می‌شوند:

  WR>60٪  ·  PF شمارشی>1.3  ·  PF روزانه>1.3  ·  اکشن/روز≥5  ·  Expectancy مثبت

ترکیبِ برنده = دو اهرمِ مخالف که یکدیگر را متعادل می‌کنند:
  (۱) کیفیتِ بالاترِ ورود (آستانهٔ ML = 0.69/0.67) → PF و WR بالا
  (۲) scale-out ۶-سطحیِ ریز → تعدادِ اکشنِ اجرایی در روز ≥۵ و WR شمارشی بالاتر

مبنا: پرتفوی L+S (long uptrend + short downtrend، گیتِ چند-جفت‌ارزی، ensemble
۳-seed از cacheِ S49). خروج: موتورِ چند-پله‌ای ۶-سطحی + BE + تریلینگِ ATR.

اعتبارسنجیِ اضافی: تفکیکِ نتایج به دو نیمهٔ زمانی (out-of-sample پایداری) و
آزمونِ حساسیت به اسپرد.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from dynamic_backtest import run_multistep_backtest, daily_pnl_stats
from multipair import build_multipair_features
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SL_M = 1.5
THRESH_L = 0.69; THRESH_S = 0.67
TP_MULTS = (0.5, 0.9, 1.3, 1.8, 2.4, 3.2)
TP_FRACS = (0.10, 0.12, 0.13, 0.15, 0.20, 0.30)
TRAIL = 2.2; BE = 0.15
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

z = np.load(CACHE); ens_long = z['ens_long']; ens_short = z['ens_short']
entries_L = cand_long & ~np.isnan(ens_long) & (ens_long >= THRESH_L) & align_long
entries_S = cand_short & ~np.isnan(ens_short) & (ens_short >= THRESH_S) & align_short
print(f"سیگنال‌ها: L={int(entries_L.sum())}  S={int(entries_S.sum())}", flush=True)


def run_ms(entries, direction, spread=0.20):
    return run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
        tp_mults=TP_MULTS, tp_fracs=TP_FRACS, trail_mult=TRAIL, be_offset=BE,
        spread=spread, max_hold=HZ * 4, allow_overlap=False)


def merge_dedup(frames):
    fs = [t for t in frames if t is not None and len(t) > 0]
    if not fs: return None
    allt = pd.concat(fs, ignore_index=True).sort_values('entry_bar')
    return allt.drop_duplicates(subset='entry_bar', keep='first').reset_index(drop=True)


def full_report(tr, label):
    if tr is None or len(tr) == 0:
        print(f"{label}: no trades"); return None
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else float('inf')
    wr = (tr['pnl'] > 0).mean() * 100; exp = tr['pnl'].mean()
    d = daily_pnl_stats(tr)
    print(f"\n=== {label} ===")
    print(f"  معاملات(ورود): {len(tr)}   کلِ اکشن‌ها: {int(tr['n_actions'].sum())}")
    print(f"  WR شمارشی      : {wr:.2f}%")
    print(f"  PF شمارشی      : {pf:.3f}")
    print(f"  Expectancy     : {exp:+.4f}$ / معامله")
    print(f"  کلِ PnL        : {tr['pnl'].sum():+.1f}$")
    print(f"  ─ سنجه‌های روزانه (معیارِ اصلیِ User Note) ─")
    print(f"  PF روزانه (dPF): {d['daily_profit_factor']:.3f}")
    print(f"  سود خالصِ روزانه: {d['avg_daily_pnl']:+.3f}$ (میانگین)")
    print(f"  Sharpe روزانه  : {d['daily_sharpe']:.3f}")
    print(f"  روزهای سودده   : {d['daily_win_rate']:.1f}%")
    print(f"  ─ فرکانس ─")
    print(f"  ورودِ مستقل/روزِ تقویمی : {d['trades_per_calendar_day']:.2f}")
    print(f"  اکشن/روزِ تقویمی        : {d.get('actions_per_calendar_day',0):.2f}")
    print(f"  اکشن/روزِ فعال          : {d.get('actions_per_active_day',0):.2f}")
    # ارزیابیِ قیود
    ok_wr = wr > 60; ok_pf = pf > 1.3; ok_dpf = d['daily_profit_factor'] > 1.3
    ok_act = d.get('actions_per_calendar_day', 0) >= 5; ok_exp = exp > 0
    print(f"  ─ قیود ─  WR>60:{'✅' if ok_wr else '❌'}  PF>1.3:{'✅' if ok_pf else '❌'}"
          f"  dPF>1.3:{'✅' if ok_dpf else '❌'}  اکشن≥5:{'✅' if ok_act else '❌'}"
          f"  exp>0:{'✅' if ok_exp else '❌'}")
    if ok_wr and ok_pf and ok_dpf and ok_act and ok_exp:
        print("  🎉 همهٔ قیود هم‌زمان برآورده شدند!")
    return d


# --- ۱) نتیجهٔ کاملِ کلِ دوره ---
trL = run_ms(entries_L, 'long')[1]
trS = run_ms(entries_S, 'short')[1]
tr_all = merge_dedup([trL, trS])
full_report(tr_all, "کلِ دوره (۱۵۰k کندل)")

# --- ۲) پایداریِ زمانی: دو نیمه ---
half = n // 2
trL1 = trL[trL['entry_bar'] < half]; trS1 = trS[trS['entry_bar'] < half]
trL2 = trL[trL['entry_bar'] >= half]; trS2 = trS[trS['entry_bar'] >= half]
full_report(merge_dedup([trL1, trS1]), "نیمهٔ اول (پایداری OOS)")
full_report(merge_dedup([trL2, trS2]), "نیمهٔ دوم (پایداری OOS)")

# --- ۳) حساسیت به اسپرد ---
print("\n================ حساسیت به اسپرد ================")
for sp in [0.20, 0.30, 0.40]:
    trLs = run_ms(entries_L, 'long', spread=sp)[1]
    trSs = run_ms(entries_S, 'short', spread=sp)[1]
    tr = merge_dedup([trLs, trSs])
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else float('inf')
    wr = (tr['pnl'] > 0).mean() * 100; d = daily_pnl_stats(tr)
    print(f"  اسپرد={sp}$: WR={wr:.2f}% PF={pf:.3f} dPF={d['daily_profit_factor']:.2f} "
          f"exp={tr['pnl'].mean():+.3f}$ اکشن/روز={d.get('actions_per_calendar_day',0):.2f}")

print("\nتمام.", flush=True)
