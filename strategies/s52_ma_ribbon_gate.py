"""
استراتژی ۵۲ — گیتِ «ریبونِ چند-MA» در تایم‌فریمِ بالا (پاسخ به User Note دوم)
================================================================================
هدفِ دوگانه:
  (الف) پیاده‌سازیِ مستقیمِ ایدهٔ کاربر: «چند MA در تایم‌فریمِ بالا → کشفِ روند/
        حمایت/مقاومت از همگرایی-واگراییِ خطوط → استفاده در تایم‌فریمِ پایین».
  (ب)  حمله به مشکلِ L27 (کشفِ S51): سودآوریِ سبد به رژیمِ صعودیِ نیمهٔ دوم وابسته
        بود و نیمهٔ اول زیانده. فرضیه: گیتِ ریبون فقط اجازهٔ معامله در «روندِ سالمِ
        تأییدشده در HTF» را می‌دهد، پس شاید نیمهٔ اول را از زیان خارج و
        سودآوری را در هر دو نیمه پایدار کند.

روش (Recipe-S25):
  ۱. probaهای پایه (S25 long/short) از cacheِ S49 خوانده می‌شوند — بدونِ آموزشِ مجدد.
  ۲. گیتِ ریبون به‌صورتِ فیلترِ ورود اعمال می‌شود (long فقط اگر ریبونِ H1&H4 قوی-صعودی).
  ۳. آزمونِ ۲×۲: (پایه) در برابر (پایه + گیتِ ریبون)، و مهم‌تر: **تفکیکِ دو-نیمه**.
  ۴. همان موتورِ چند-پله‌ای S51 برای خروج.
معیارِ پذیرشِ سختگیرانه (L27): PF>1.3 و exp>0 در **هر دو نیمهٔ زمانی**، نه فقط کل.
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

print("ساخت featureهای ریبونِ H1/H4 ...", flush=True)
rib = build_ribbon_features(df, tfs=('H1', 'H4'))
# گیتِ ریبون: هر دو تایم‌فریم روندِ قویِ هم‌جهت داشته باشند
rib_up = ((rib['h1_rib_order'].fillna(0) >= 0.6) &
          (rib['h4_rib_order'].fillna(0) >= 0.6)).values
rib_dn = ((rib['h1_rib_order'].fillna(0) <= -0.6) &
          (rib['h4_rib_order'].fillna(0) <= -0.6)).values
# گیتِ نرم‌تر (فقط H4)
rib_up_soft = (rib['h4_rib_order'].fillna(0) >= 0.6).values
rib_dn_soft = (rib['h4_rib_order'].fillna(0) <= -0.6).values

assert os.path.exists(CACHE), "cache نیست؛ ابتدا s49 را اجرا کنید."
z = np.load(CACHE); ens_long = z['ens_long']; ens_short = z['ens_short']

base_L = cand_long & ~np.isnan(ens_long) & (ens_long >= THRESH_L) & align_long
base_S = cand_short & ~np.isnan(ens_short) & (ens_short >= THRESH_S) & align_short
print(f"سیگنالِ پایه: L={int(base_L.sum())}  S={int(base_S.sum())}", flush=True)


def run_ms(entries, direction, spread=SPREAD):
    return run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
        tp_mults=TP_MULTS, tp_fracs=TP_FRACS, trail_mult=TRAIL, be_offset=BE,
        spread=spread, max_hold=HZ * 4, allow_overlap=False)[1]


def merge_dedup(frames):
    fs = [t for t in frames if t is not None and len(t) > 0]
    if not fs: return None
    allt = pd.concat(fs, ignore_index=True).sort_values('entry_bar')
    return allt.drop_duplicates(subset='entry_bar', keep='first').reset_index(drop=True)


def stats(tr):
    if tr is None or len(tr) == 0: return None
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else float('inf')
    wr = (tr['pnl'] > 0).mean() * 100; exp = tr['pnl'].mean()
    d = daily_pnl_stats(tr)
    return dict(n=len(tr), wr=wr, pf=pf, exp=exp, pnl=tr['pnl'].sum(),
                dpf=d['daily_profit_factor'], apd=d.get('actions_per_calendar_day', 0),
                tpd=d['trades_per_calendar_day'])


def show(tr, label):
    s = stats(tr)
    if s is None: print(f"  {label}: no trades"); return None
    ok = (s['wr'] > 60 and s['pf'] > 1.3 and s['exp'] > 0)
    print(f"  {label}: n={s['n']} WR={s['wr']:.2f}% PF={s['pf']:.3f} dPF={s['dpf']:.2f} "
          f"exp={s['exp']:+.3f}$ اکشن/روز={s['apd']:.2f} {'✅' if ok else ''}")
    return s


def split_halves(tr):
    """تفکیکِ معاملات به دو نیمهٔ زمانی بر اساسِ entry_bar (نقطهٔ میانیِ داده)."""
    if tr is None or len(tr) == 0: return None, None
    mid = n // 2
    return tr[tr['entry_bar'] < mid], tr[tr['entry_bar'] >= mid]


# ============ آزمونِ ۱: اثرِ گیتِ ریبون روی کلِ دوره ============
print("\n================ آزمونِ ۱: پایه vs گیتِ ریبون (کلِ دوره) ================", flush=True)
scenarios = {
    'پایه (بدونِ ریبون)':        (base_L, base_S),
    'گیتِ ریبونِ H1&H4 (سخت)':   (base_L & rib_up, base_S & rib_dn),
    'گیتِ ریبونِ H4 (نرم)':      (base_L & rib_up_soft, base_S & rib_dn_soft),
}
results = {}
for name, (eL, eS) in scenarios.items():
    trL = run_ms(eL, 'long'); trS = run_ms(eS, 'short')
    tr = merge_dedup([trL, trS])
    results[name] = tr
    show(tr, name)


# ============ آزمونِ ۲: پایداریِ دو-نیمه (حملهٔ اصلی به L27) ============
print("\n================ آزمونِ ۲: پایداریِ دو-نیمه (رفعِ L27) ================", flush=True)
for name, tr in results.items():
    h1, h2 = split_halves(tr)
    print(f"\n▶ {name}:")
    s1 = show(h1, "   نیمهٔ اول ")
    s2 = show(h2, "   نیمهٔ دوم ")
    if s1 and s2:
        stable = (s1['pf'] > 1.3 and s1['exp'] > 0 and s2['pf'] > 1.3 and s2['exp'] > 0
                  and s1['wr'] > 60 and s2['wr'] > 60)
        print(f"   → پایدار در هر دو نیمه؟ {'✅ بله' if stable else '❌ خیر'}")

print("\nتمام.", flush=True)
