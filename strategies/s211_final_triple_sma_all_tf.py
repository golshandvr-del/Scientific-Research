# -*- coding: utf-8 -*-
"""
S211 (نهایی و قطعی) — لایهٔ Triple-SMA(13/100/200) stack-pullback + Vortex + Kaufman-ER
========================================================================================
هدف: پاسخِ کاملِ علمی به دو نکتهٔ کاربر در ادامهٔ گفتگو:

  نکته ۱ (رکورد پایه): رکوردِ رسمیِ قطعی = +$252,471 (تأییدشده از README خط ۲۱/۱۲۸).
  نکته ۲ (چرا فقط M15؟): این اسکریپت لایهٔ *نهایی* را روی **همهٔ تایم‌فریم‌ها**ی
     هر دو ارز (XAUUSD: M5,M15,M30,H1,H4  و  EURUSD: M1,M5,M15,M30) اجرا می‌کند و
     نتیجهٔ هر TF را مجزا گزارش و در JSON ذخیره می‌کند (قانونِ مولتی‌تایم‌فریم #۱).

این اسکریپت خودبسنده است و از موتورِ مشترکِ پروژه (engine/scalp_engine.py) استفاده
می‌کند تا اعداد دقیقاً با بقیهٔ پرتفوی هم‌گام باشند (همان مدلِ هزینه: اسپرد 3.3pip طلا،
کمیسیون صفر، ریسکِ ۱٪، لاتِ واقعی).

منطقِ لایه (دقیقاً همان چیزی که در سشن قبل برنده شد):
  ورودِ LONG وقتی:
    (1) چیدمانِ صعودی: SMA_fast(13) > SMA_mid(100) > SMA_slow(240?→200)  [رژیمِ روند صعودی]
        → مقادیرِ برنده: fast=13, mid=100, slow=200
    (2) pullback: قیمت به SMA_fast نزدیک/زیر آن آمده و دوباره بالای آن بسته → بازگشت به روند
    (3) فیلترِ تأییدِ روند (اندیکاتورهای کمیاب):
          Vortex: VI+ > VI-      (جهتِ روندِ صعودی تأیید)
          Kaufman-ER > 0.20      (کیفیت/کاراییِ روند بالا — نه رنجِ نویزی)
  SHORT: به‌طورِ متقارن آزموده شد (طبقِ L53 طلا بایاسِ صعودی دارد ⇒ انتظارِ ضرر).

خروجی: results/_s211_final_all_tf.json  (commit می‌شود تا از بین نرود).
"""
import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.scalp_engine import load_data, simulate_trades, run_capital, ASSETS  # noqa


# ----------------------------------------------------------------------------
# اندیکاتورهای مورد نیاز (خودبسنده تا به تغییرِ engine وابسته نباشیم)
# ----------------------------------------------------------------------------
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def vortex(df: pd.DataFrame, period: int = 14):
    """Vortex Indicator (VI+ , VI-) — تشخیصِ جهتِ روند."""
    h, l, c = df['high'], df['low'], df['close']
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    vmp = (h - l.shift()).abs()
    vmm = (l - h.shift()).abs()
    str_ = tr.rolling(period).sum()
    vip = vmp.rolling(period).sum() / str_
    vim = vmm.rolling(period).sum() / str_
    return vip, vim


def kaufman_er(s: pd.Series, period: int = 10) -> pd.Series:
    """Kaufman Efficiency Ratio — کیفیتِ روند: |تغییرِ خالص| / مجموعِ |تغییرات|."""
    change = (s - s.shift(period)).abs()
    vol = s.diff().abs().rolling(period).sum()
    return change / vol.replace(0, np.nan)


# ----------------------------------------------------------------------------
# منطقِ لایه
# ----------------------------------------------------------------------------
FAST, MID, SLOW = 13, 100, 200
VORTEX_P = 14
ER_P = 10
ER_MIN = 0.20

# TP/SL مخصوصِ هر TF (ATR در TFهای بزرگ‌تر بزرگ‌تر است) — قانونِ بهبود: هر TF تنظیمِ خود
TF_CFG = {
    'M1':  dict(sl=60,  tp=120, mh=60),
    'M5':  dict(sl=100, tp=200, mh=48),
    'M15': dict(sl=150, tp=300, mh=32),
    'M30': dict(sl=200, tp=400, mh=24),
    'H1':  dict(sl=250, tp=500, mh=16),
    'H4':  dict(sl=400, tp=800, mh=12),
}


def build_signals(df, direction):
    """تولیدِ آرایهٔ بولینِ سیگنال برای LONG یا SHORT.

    ⚠️ تعریفِ pullback دقیقاً همان تعریفِ *بازتولیدپذیرِ* S211e است:
       LONG: low کندلِ قبلی به/زیرِ SMA_fast رسیده (لمسِ سایه) و close فعلی بالای SMA_fast.
       (تعریفِ سخت‌گیرانهٔ close<=fast اشتباهاً سیگنال‌ها را ~۳ برابر کم می‌کرد.)
    """
    c = df['close']
    l = df['low']
    h = df['high']
    f = sma(c, FAST)
    m = sma(c, MID)
    s = sma(c, SLOW)
    vip, vim = vortex(df, VORTEX_P)
    er = kaufman_er(c, ER_P)

    prev_f = f.shift(1)
    prev_l = l.shift(1)
    prev_h = h.shift(1)

    if direction == 'long':
        stack = (f > m) & (m > s)                     # چیدمانِ صعودی
        pullback = (prev_l <= prev_f) & (c > f)       # لمسِ سایه از پایین + بستنِ بالای fast
        trend_ok = (vip > vim) & (er > ER_MIN)        # فیلترِ کمیاب: Vortex + ER
        sig = stack & pullback & trend_ok
    else:
        stack = (f < m) & (m < s)
        pullback = (prev_h >= prev_f) & (c < f)       # قرینهٔ SHORT
        trend_ok = (vim > vip) & (er > ER_MIN)
        sig = stack & pullback & trend_ok

    return sig.fillna(False).values


def hard_gate(df, trades, asset):
    """گیتِ سختِ ضدِ overfit: net>0، دو نیمه>0، ۴ پنجرهٔ walk-forward>0، WR≥40."""
    if trades is None or len(trades) == 0:
        return dict(n=0, net=0, wr=0.0, h1=0, h2=0, wf=[0, 0, 0, 0], pass_gate=False)

    def _net(t):
        if t is None or len(t) == 0:
            return 0.0
        st, _ = run_capital(t, asset)
        return st['net_profit']

    net = _net(trades)
    wr = 100.0 * (trades['outcome'] == 'win').mean()
    n = len(trades)
    half = len(df) // 2
    t1 = trades[trades['signal_bar'] < half]
    t2 = trades[trades['signal_bar'] >= half]
    net_h1, net_h2 = _net(t1), _net(t2)

    wf = []
    bounds = np.linspace(0, len(df), 5).astype(int)
    for k in range(4):
        tw = trades[(trades['signal_bar'] >= bounds[k]) & (trades['signal_bar'] < bounds[k + 1])]
        wf.append(round(_net(tw)))

    pass_gate = (net > 0 and net_h1 > 0 and net_h2 > 0 and all(w > 0 for w in wf) and wr >= 40.0)
    return dict(n=n, net=round(net), wr=round(wr, 1),
                h1=round(net_h1), h2=round(net_h2), wf=wf, pass_gate=bool(pass_gate))


def run_asset(asset, tfs):
    rows = []
    for tf in tfs:
        path = f'data/{asset}_{tf}.csv'
        if not os.path.exists(path):
            print(f"  {tf:>4}  (فایل موجود نیست: {path})")
            continue
        df = load_data(path)
        cfg = TF_CFG[tf]
        # موتور asset را برای pip/هزینه لازم دارد؛ اما دادهٔ TF را دستی می‌دهیم.
        # ASSETS[asset]['file'] فقط پیش‌فرض است؛ ما df را مستقیم پاس می‌دهیم.
        for direction in ('long', 'short'):
            sig = build_signals(df, direction)
            long_sig = sig if direction == 'long' else np.zeros(len(df), bool)
            short_sig = sig if direction == 'short' else np.zeros(len(df), bool)
            trades = simulate_trades(df, long_sig, short_sig,
                                     sl_pip=cfg['sl'], tp_pip=cfg['tp'],
                                     asset=asset, max_hold=cfg['mh'], allow_overlap=False)
            if trades is not None and len(trades):
                trades = trades.copy()
                # signal_bar = entry_bar-1 (سیگنال روی کندلِ قبل از ورود بود)
                if 'signal_bar' not in trades.columns:
                    trades['signal_bar'] = trades['entry_bar'] - 1
            g = hard_gate(df, trades, asset)
            g.update(asset=asset, tf=tf, dir=direction)
            rows.append(g)
            flag = '✅ PASS' if g['pass_gate'] else '✗'
            print(f"  {tf:>4} {direction:>6}  n={g['n']:>5}  net=${g['net']:>8}  "
                  f"wr={g['wr']:>5}%  h1={g['h1']:>7} h2={g['h2']:>7}  wf={g['wf']}  {flag}")
    return rows


def main():
    print("=" * 100)
    print("S211 نهایی — Triple-SMA(13/100/200)+Vortex+Kaufman-ER — همهٔ تایم‌فریم‌ها (پاسخ به نکتهٔ کاربر)")
    print(f"  مقادیر: SMA {FAST}/{MID}/{SLOW} | Vortex({VORTEX_P}) | ER({ER_P})>{ER_MIN}")
    print("=" * 100)

    all_rows = []
    print("\n### XAUUSD ###")
    all_rows += run_asset('XAUUSD', ['M5', 'M15', 'M30', 'H1', 'H4'])
    print("\n### EURUSD ###")
    all_rows += run_asset('EURUSD', ['M1', 'M5', 'M15', 'M30'])

    passed = [r for r in all_rows if r['pass_gate']]
    print("\n" + "=" * 100)
    print("### لایه‌هایی که گیتِ سخت را پاس کردند: ###")
    if passed:
        for r in passed:
            print(f"  ✅ {r['asset']} {r['tf']} {r['dir'].upper()}  net=${r['net']}  WR={r['wr']}%  wf={r['wf']}")
    else:
        print("  (هیچ)")
    total_raw = sum(r['net'] for r in passed)
    print(f"\n  جمعِ خامِ net لایه‌های پاس‌شده = ${total_raw:+,}")
    print("  (توجه: پیش از افزودن به رکورد باید همپوشانیِ معامله-محور بررسی شود — گام بعد S211g)")

    out = dict(params=dict(fast=FAST, mid=MID, slow=SLOW, vortex=VORTEX_P, er_p=ER_P, er_min=ER_MIN),
               rows=all_rows, passed=passed, total_raw_net=total_raw,
               record_base=252471)
    os.makedirs('results', exist_ok=True)
    with open('results/_s211_final_all_tf.json', 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\nsaved: results/_s211_final_all_tf.json")


if __name__ == '__main__':
    main()
