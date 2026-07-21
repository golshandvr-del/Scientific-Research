"""
explore_dxy_shock_gold_reaction.py — اکتشافِ علمی: «شوکِ DXY → واکنشِ تأخیریِ طلا»
================================================================================
> قانونِ شمارهٔ ۱: تنها معیار = سودِ خالص (XAUUSD + EURUSD). این فایل فقط اکتشاف است
> (کشفِ ساختار پیش از ساختِ استراتژی) — نه استراتژی.

ایدهٔ نبوغ+جنون (متعامد با همهٔ لایه‌های رکورد):
  همهٔ لایه‌های رکورد یا ساختارِ خودِ طلا (S67/S81/Squeeze) یا زمانِ تقویمی
  (S139..S144) را می‌بینند. هیچ‌کدام به **رویدادِ برون‌زای دلار** وابسته نیستند.
  فرضیه: DXY و طلا همبستگیِ معکوس دارند اما این واکنش **آنی نیست** — یک تأخیر
  (lag) دارد. وقتی DXY یک **شوکِ شارپ** (حرکتِ بزرگ در یک/چند کندل) می‌کند، طلا
  در کندل‌های بعدی با احتمالِ بالا در جهتِ معکوس واکنش نشان می‌دهد.

  اگر این lead-lag واقعی باشد ⇒ یک جریانِ سودِ **ذاتاً متعامد** با همهٔ لایه‌های
  فعلی می‌سازد (منبعِ سیگنال از دلار می‌آید، نه از طلا و نه از تقویم).

روش (بدونِ نشتِ آینده):
  ۱) DXY_M15 و XAUUSD_M15 را با merge_asof(backward) روی زمانِ کندل هم‌تراز کن.
     (برای هر کندلِ طلا فقط از DXYِ بسته‌شده تا آن لحظه استفاده می‌شود.)
  ۲) «شوکِ DXY» = بازدهِ k-کندلیِ DXY که قدرِمطلقش از یک آستانه (بر حسبِ z-score
     یا صدک) بزرگ‌تر باشد.
  ۳) واکنشِ طلا در افق‌های h∈{1,2,4,8,16} کندلِ *بعدی* اندازه گرفته می‌شود.
  ۴) t-stat و میانگینِ بازدهِ طلا (به pip) شرطی بر جهتِ شوکِ DXY گزارش می‌شود.
     انتظار: شوکِ DXY صعودی ⇒ طلا نزولی (mean منفی)، و برعکس.
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

XAU = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
DXY = os.path.join(ROOT, 'data', 'DXY_M15.csv')
PIP = 0.10  # طلا


def load_aligned():
    x = pd.read_csv(XAU); d = pd.read_csv(DXY)
    x['dt'] = pd.to_datetime(x['time'], unit='s')
    d['dt'] = pd.to_datetime(d['time'], unit='s')
    x = x.sort_values('dt').reset_index(drop=True)
    d = d.sort_values('dt').reset_index(drop=True)
    # DXY features (فقط از کندل‌های بسته‌شده)
    d['dxy_ret1'] = d['close'].pct_change(1)
    d['dxy_ret2'] = d['close'].pct_change(2)
    d['dxy_ret4'] = d['close'].pct_change(4)
    dsub = d[['dt', 'close', 'dxy_ret1', 'dxy_ret2', 'dxy_ret4']].rename(columns={'close': 'dxy_close'})
    # merge_asof backward: برای هر کندلِ طلا، آخرین DXYِ بسته‌شده تا آن لحظه
    m = pd.merge_asof(x, dsub, on='dt', direction='backward')
    return m


def explore():
    m = load_aligned()
    c = m['close'].values
    n = len(m)
    print("=" * 74)
    print("اکتشاف: شوکِ DXY → واکنشِ تأخیریِ طلا  (n=%d کندلِ هم‌تراز)" % n)
    print("=" * 74)

    for shock_col, klabel in [('dxy_ret1', '۱-کندل'), ('dxy_ret2', '۲-کندل'), ('dxy_ret4', '۴-کندل')]:
        sh = m[shock_col].values
        valid = ~np.isnan(sh)
        std = np.nanstd(sh)
        # آستانهٔ شوک = ۲ انحرافِ معیار (رویدادِ نادر و بزرگ)
        thr = 2.0 * std
        up_shock = valid & (sh > thr)     # دلار جهش کرد ⇒ انتظارِ طلا نزولی
        dn_shock = valid & (sh < -thr)    # دلار سقوط کرد ⇒ انتظارِ طلا صعودی
        print(f"\n### شوکِ DXY ({klabel}، آستانه=2σ={thr*100:.3f}%)  "
              f"| up_shock={up_shock.sum()}  dn_shock={dn_shock.sum()} ###")
        print(f"{'افقِ طلا':>10s} | {'پس از up-shock (pip)':>22s} | {'پس از dn-shock (pip)':>22s}")
        for h in [1, 2, 4, 8, 16]:
            fut = np.full(n, np.nan)
            fut[:n-h] = (c[h:] - c[:n-h]) / PIP    # بازدهِ آتیِ طلا به pip (forward)
            def stat(mask):
                v = fut[mask & ~np.isnan(fut)]
                if len(v) < 20: return (0.0, 0.0, 0)
                t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)) + 1e-12)
                return (v.mean(), t, len(v))
            mu_up, t_up, nu = stat(up_shock)
            mu_dn, t_dn, nd = stat(dn_shock)
            print(f"{'h='+str(h):>10s} | mean={mu_up:+7.2f} t={t_up:+5.2f} N={nu:<5d} | "
                  f"mean={mu_dn:+7.2f} t={t_dn:+5.2f} N={nd:<5d}")

    print("\nتفسیر: اگر up-shock ⇒ mean طلا منفی (t منفیِ معنادار) و dn-shock ⇒ mean مثبت،")
    print("       آنگاه رابطهٔ معکوسِ تأخیری تأیید می‌شود و لبهٔ mean-reversionِ بین‌دارایی وجود دارد.")
    print("       اگر برعکس (هم‌جهت) ⇒ لبهٔ momentum/pass-through است. هر دو قابلِ بهره‌برداری‌اند.")


if __name__ == '__main__':
    explore()
