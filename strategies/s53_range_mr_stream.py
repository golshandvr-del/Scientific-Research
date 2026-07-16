"""
استراتژی ۵۳ — جریانِ mean-reversion برای رژیمِ رنج (رفعِ L28، پایدارسازیِ دو-نیمه)
================================================================================
کشفِ L28 (S52): جریان‌های روند-پیرو (long uptrend + short downtrend) در نیمهٔ اولِ
داده (رژیمِ رنجِ ۲۰۲۰–۲۰۲۳) فقط بریک‌ایون‌اند، چون در آن رژیم روندی وجود نداشته که
شکار شود. راهِ حلِ منطقی: یک جریانِ سومِ **بازگشت-به-میانگین** که دقیقاً وقتی بازار
رنج/بی‌روند است فعال شود — یعنی مکملِ زمانیِ جریان‌های روندی.

تشخیصِ رژیمِ رنج (بدونِ look-ahead): وقتی ریبونِ HTF «درهم و فشرده» است:
  |h4_rib_order| کوچک (خطوط درهم = بی‌روند)  AND  ADX پایین.

سیگنالِ mean-reversion (کلاسیک، اثبات‌شده در ادبیات): بازگشت از باندهای بولینگر در
رنج. long وقتی قیمت به باندِ پایین می‌رسد و RSI اشباعِ فروش؛ short برعکس. هدف:
بازگشت به میانگین (نه روند) — TP کوچک، SL متقارن.

روش (Recipe-S25):
  مرحله ۱ — آزمونِ خامِ اثر: آیا سیگنالِ MR در رژیمِ رنج edge دارد (P(fav) و WR خام)؟
  مرحله ۲ — بک‌تستِ واقعی با ورودِ open بعدی + اسپرد + خروجِ چند-پله‌ای.
  مرحله ۳ — تفکیکِ دو-نیمه: آیا این جریان در نیمهٔ اول (رنج) سودآور است؟ (کلید)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from dynamic_backtest import run_multistep_backtest, daily_pnl_stats
from ma_ribbon import build_ribbon_features
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SL_M = 1.5; SPREAD = 0.20

df = load_data(); n = len(df); c = df['close'].values
h = df['high'].values; l = df['low'].values
atr = ind.atr(df, 14); atrv = atr.values
rsi = ind.rsi(df['close'], 14).values
lo_b, mid_b, up_b = ind.bollinger(df['close'], 20, 2.0)
lo_b, mid_b, up_b = lo_b.values, mid_b.values, up_b.values
adx_, pdi, mdi = ind.adx(df, 14); adxv = adx_.values

print("ساخت featureهای ریبونِ H4 ...", flush=True)
rib = build_ribbon_features(df, tfs=('H4',))
order = rib['h4_rib_order'].fillna(0).values
width_z = rib['h4_rib_width_z'].fillna(0).values

# --- تشخیصِ رژیمِ رنج (بی‌روند): ریبون درهم + ADX پایین ---
range_regime = (np.abs(order) <= 0.4) & (adxv < 22) & ~np.isnan(atrv)
trend_regime = (np.abs(order) >= 0.6)
print(f"سهمِ کندل‌های رژیمِ رنج: {100*range_regime.mean():.1f}%  | روندی: {100*trend_regime.mean():.1f}%")
mid = n // 2
print(f"  رنج در نیمهٔ اول: {100*range_regime[:mid].mean():.1f}%  | نیمهٔ دوم: {100*range_regime[mid:].mean():.1f}%")

# --- سیگنالِ mean-reversion در رژیمِ رنج ---
# long: قیمت زیرِ باندِ پایین + RSI اشباعِ فروش
mr_long = range_regime & (c < lo_b) & (rsi < 35)
# short: قیمت بالای باندِ بالا + RSI اشباعِ خرید
mr_short = range_regime & (c > up_b) & (rsi > 65)
print(f"سیگنالِ MR: long={int(mr_long.sum())}  short={int(mr_short.sum())}")


# --- مرحله ۱: آزمونِ خامِ اثر (P(fav) طیِ HZ کندل) ---
def raw_edge(sig, direction, hz=24):
    idx = np.where(sig)[0]; idx = idx[idx + hz < n]
    if len(idx) < 30: return None
    if direction == 'long':
        fav = (c[idx + hz] - c[idx]) > 0
    else:
        fav = (c[idx + hz] - c[idx]) < 0
    return len(idx), fav.mean() * 100


for nm, sig, d in [('MR-long', mr_long, 'long'), ('MR-short', mr_short, 'short')]:
    r = raw_edge(sig, d)
    if r: print(f"  خامِ {nm}: n={r[0]}  P(fav در {24} کندل)={r[1]:.1f}%")


# --- مرحله ۲+۳: بک‌تستِ واقعی با خروجِ چند-پله‌ایِ MR (TP کوچک‌تر، متقارن) ---
# برای MR: هدف بازگشت به میانگین است، پس TP نزدیک‌تر و بدونِ دُمِ بزرگ.
TP_MULTS = (0.5, 0.9, 1.3); TP_FRACS = (0.4, 0.35, 0.25); TRAIL = 1.5; BE = 0.10


def run_ms(entries, direction):
    return run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
        tp_mults=TP_MULTS, tp_fracs=TP_FRACS, trail_mult=TRAIL, be_offset=BE,
        spread=SPREAD, max_hold=HZ * 2, allow_overlap=False)[1]


def rep(tr, label):
    if tr is None or len(tr) == 0:
        print(f"  {label}: بدونِ معامله"); return None
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else 99
    wr = (tr['pnl'] > 0).mean() * 100; exp = tr['pnl'].mean()
    d = daily_pnl_stats(tr)
    print(f"  {label}: n={len(tr)} WR={wr:.1f}% PF={pf:.3f} exp={exp:+.3f}$ "
          f"pnl={tr['pnl'].sum():+.0f}$ اکشن/روز={d.get('actions_per_calendar_day',0):.2f}")
    return dict(n=len(tr), wr=wr, pf=pf, exp=exp)


print("\n================ جریانِ MR (mean-reversion در رنج) ================", flush=True)
trL = run_ms(mr_long, 'long'); trS = run_ms(mr_short, 'short')
allmr = pd.concat([t for t in [trL, trS] if t is not None and len(t) > 0],
                  ignore_index=True).sort_values('entry_bar').reset_index(drop=True)
rep(allmr, "MR کل      ")
rep(allmr[allmr['entry_bar'] < mid], "MR نیمهٔ اول")
rep(allmr[allmr['entry_bar'] >= mid], "MR نیمهٔ دوم")

print("\nتمام.", flush=True)
