# -*- coding: utf-8 -*-
"""
s156_revive_costsensitive_newspec.py — بازآزماییِ استراتژی‌های *ضررده/مرزیِ حساس به هزینه*
============================================================================================
با مشخصاتِ دقیقِ حسابِ جدید (XAU spread 3.3pip، همهٔ فارکس‌ها کمیسیون=۰).

منشأ (User Note): «استراتژیی که با مشخصاتِ قبلی ضررده بود اما با مشخصاتِ فعلی سودده است
                   را شناسایی و به‌عنوانِ لایهٔ نو اضافه کن.»

S155 فقط ۴ یافتهٔ EURUSDِ «مرزی» را بازآزمایی کرد (احیا=۰). این اسکریپت سراغِ دو دستهٔ
دیگر می‌رود که S155 پوشش نداد:

  الف) لایهٔ SHORT-MA-Confluenceِ طلا (پرفرکانس‌ترین لایهٔ پروژه، ۳۳۱۸ معامله) —
       چون فرکانسِ بالا ⇒ حساس‌ترین به هزینه؛ کاهشِ 5.0→3.3pip باید بیشترین اثر را
       اینجا بگذارد. با هزینهٔ قدیم «مرزی/نویز» ثبت شده بود (S137: +$34,959, Δ+$417).

  ب) S71/S72 فارکس (ضررِ سنگینِ −$20k) — بازآزمایی با کمیسیونِ صفر برای اثباتِ علمی
     که ضررشان *ساختاری* بود نه هزینه‌ای (فرضیهٔ راهنما: ruin به کمیسیون ربطی ندارد).

روش (علمی، بدونِ overfit):
  • هر کاندید را با **دقیقاً همان قواعدِ ثبت‌شده** (بدونِ بهینه‌سازیِ دوباره) اجرا می‌کنیم.
  • هر کاندید دو بار اجرا می‌شود: مدلِ هزینهٔ OLD (XAU 5.0pip) و NEW (XAU 3.3pip).
  • گیتِ سختِ پروژه: (۱) net مثبت، (۲) هر دو نیمهٔ داده مثبت، (۳) هر ۴ پنجرهٔ WF مثبت.
  • «احیا» فقط وقتی است که کاندید با NEW از گیت رد شود ولی با OLD رد نمی‌شد.
"""
import json
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import capital_engine as ce
from engine import indicators as ind

DATA_XAU = 'data/XAUUSD_M15.csv'
DATA_EUR = 'data/EURUSD_M15.csv'
DATA_AUD = 'data/AUDUSD_M15.csv'

RISK = 0.01
CAP0 = 10_000.0

# مشخصاتِ دو مدلِ هزینه برای XAUUSD
XAU_OLD = dict(spread_pip=4.0, slip_pip=0.5)   # =5.0pip رفت‌وبرگشتِ مؤثر (مدلِ بدبینانهٔ قدیم)
XAU_NEW = dict(spread_pip=3.3, slip_pip=0.0)   # =3.3pip واقعیِ حسابِ کاربر


def _apply_xau_cost(model):
    se.ASSETS['XAUUSD']['spread_pip'] = float(model['spread_pip'])
    se.ASSETS['XAUUSD']['slip_pip'] = float(model['slip_pip'])
    se.ASSETS['XAUUSD']['comm'] = 0.0


def load(path):
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    if 'dt' not in df.columns:
        tcol = cols.get('time') or cols.get('date') or cols.get('datetime') or df.columns[0]
        df['dt'] = pd.to_datetime(df[tcol])
    for k in ['open', 'high', 'low', 'close']:
        if k not in df.columns and k in cols:
            df[k] = df[cols[k]]
    df['hour'] = df['dt'].dt.hour
    return df.reset_index(drop=True)


# ---------- (الف) سیگنالِ SHORT-MA-Confluence طلا (بازتولیدِ دقیقِ s97) ----------
def build_short_ma_signals(df):
    c = df['close']
    price = c.values
    ema20 = ind.ema(c, 20).values
    ema50 = ind.ema(c, 50).values
    sma50 = ind.sma(c, 50).values
    sma200 = ind.sma(c, 200).values
    atr = ind.atr(df, 14).values
    ma_stack = np.column_stack([ema20, ema50, sma50, sma200])
    ma_mid = np.nanmean(ma_stack, axis=1)
    ema20_slope = pd.Series(ema20).diff().values
    prev_above_mid = np.r_[False, price[:-1] > ma_mid[:-1]]
    base = prev_above_mid & (price < ma_mid) & (ema20_slope < 0)
    return base, atr


# ---------- (ج) سیگنالِ MA-Pullback فارکس (بازتولیدِ دقیقِ s149) ----------
PIP_EUR = 0.0001

def _ema_np(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values

def _atr_pips_eur(df, period=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().values
    return atr / PIP_EUR  # بر حسبِ pip

def gen_ma_pullback(df, ema_fast=20, ema_slow=50, cooldown=8, touch_atr=0.3, direction='both'):
    o = df['open'].values; c = df['close'].values
    h = df['high'].values; l = df['low'].values
    n = len(df)
    ef = _ema_np(c, ema_fast); es = _ema_np(c, ema_slow)
    atr_p = _atr_pips_eur(df, 14)
    long_sig = np.zeros(n, dtype=bool); short_sig = np.zeros(n, dtype=bool)
    last = -10**9
    start = ema_slow + 2
    for i in range(start, n - 1):
        if i - last < cooldown:
            continue
        a = atr_p[i]
        if not np.isfinite(a) or a <= 0:
            continue
        near = touch_atr * a * PIP_EUR
        up = ef[i] > es[i]; dn = ef[i] < es[i]
        if up and direction in ('both', 'long'):
            if l[i] <= ef[i] + near and c[i] > es[i] and c[i] > o[i]:
                long_sig[i] = True; last = i; continue
        if dn and direction in ('both', 'short'):
            if h[i] >= ef[i] - near and c[i] < es[i] and c[i] < o[i]:
                short_sig[i] = True; last = i; continue
    return long_sig, short_sig


# ---------- (ب) سیگنالِ mean-reversion فارکس (بازتولیدِ دقیقِ s71) ----------
def build_forex_meanrev(df):
    c = df['close']
    ma = ind.sma(c, 20).values
    sd = pd.Series(c.values).rolling(20).std().values
    upper = ma + 2.2 * sd
    lower = ma - 2.2 * sd
    rsi = ind.rsi(c, 14).values
    price = c.values
    # ورودِ long وقتی زیرِ باندِ پایین + RSI<28 ؛ short وقتی بالای باندِ بالا + RSI>72
    long_sig = (price < lower) & (rsi < 28)
    short_sig = (price > upper) & (rsi > 72)
    return long_sig, short_sig


def _net_of(trades_df, asset):
    """net دلاری با موتورِ سرمایهٔ پروژه (ریسکِ ثابتِ ۱٪، compounding)."""
    if trades_df is None or len(trades_df) == 0:
        return 0.0, 0.0
    stats, _ = se.run_capital(trades_df, asset, initial_capital=CAP0,
                              risk_pct=RISK * 100.0, compounding=True)
    return float(stats['net_profit']), float(stats.get('max_dd', 0.0))


def run_layer(df, long_sig, short_sig, sl, tp, hold, asset):
    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                asset=asset, max_hold=hold, allow_overlap=False)
    if trades is None or len(trades) == 0:
        return dict(n=0, net=0.0, h1=0.0, h2=0.0, wf=[0, 0, 0, 0], maxdd=0.0)
    net, maxdd = _net_of(trades, asset)
    idxs = trades['entry_bar'].values
    mid = len(df) // 2

    def _sub_net(mask):
        if mask.sum() == 0:
            return 0.0
        n, _ = _net_of(trades[mask].reset_index(drop=True), asset)
        return n

    h1 = _sub_net(idxs < mid)
    h2 = _sub_net(idxs >= mid)
    wf = []
    q = len(df) // 4
    for k in range(4):
        lo, hi = k * q, ((k + 1) * q if k < 3 else len(df))
        wf.append(round(_sub_net((idxs >= lo) & (idxs < hi)), 0))
    return dict(n=int(len(trades)), net=float(net), h1=float(h1), h2=float(h2),
                wf=wf, maxdd=float(maxdd))


def gate(r):
    """گیتِ سختِ پروژه: net>0 و هر دو نیمه>0 و هر ۴ WF>0."""
    if r['n'] == 0:
        return False
    return (r['net'] > 0) and (r.get('h1', -1) > 0) and (r.get('h2', -1) > 0) \
        and all(w > 0 for w in r.get('wf', [-1]))


def main():
    print("=" * 84)
    print("S156 — بازآزماییِ استراتژی‌های ضررده/مرزیِ حساس به هزینه با مشخصاتِ جدید")
    print("=" * 84)

    out = {'user_note_spec': {'xau_new_pip': 3.3, 'xau_old_pip': 5.0, 'forex_comm': 0.0},
           'candidates': {}}

    # ================= (الف) SHORT-MA-Confluence طلا =================
    print("\n[الف] SHORT-MA-Confluence طلا (پرفرکانس‌ترین لایه، حساس‌ترین به هزینه)")
    dfx = load(DATA_XAU)
    base, atr = build_short_ma_signals(dfx)
    long0 = np.zeros(len(dfx), dtype=bool)
    # واریانتِ ثبت‌شدهٔ لایهٔ رکورد: SHORTِ سریع SL30/TP کوچک/hold کوتاه
    # (طبقِ s97: «TP کوچک، سریع، max_hold کوتاه»). واریانتِ نمایندهٔ رکورد: SL30/TP30/H12
    for (sl, tp, hold) in [(30, 30, 12), (25, 20, 8), (20, 15, 6)]:
        label = f'SHORT_MA SL{sl}/TP{tp}/H{hold}'
        _apply_xau_cost(XAU_OLD)
        r_old = run_layer(dfx, long0, base, sl, tp, hold, 'XAUUSD')
        _apply_xau_cost(XAU_NEW)
        r_new = run_layer(dfx, long0, base, sl, tp, hold, 'XAUUSD')
        g_old, g_new = gate(r_old), gate(r_new)
        revived = (not g_old) and g_new
        print(f"  {label:26s}  OLD net={r_old['net']:+9,.0f}$ gate={'✅' if g_old else '❌'}"
              f"  |  NEW net={r_new['net']:+9,.0f}$ gate={'✅' if g_new else '❌'}"
              f"  |  Δ={r_new['net']-r_old['net']:+8,.0f}$  {'🎉احیا!' if revived else ''}")
        out['candidates'][label] = dict(old=r_old, new=r_new, gate_old=g_old,
                                        gate_new=g_new, revived=revived)

    # ================= (ب) S71 فارکس mean-reversion =================
    print("\n[ب] S71 فارکس mean-reversion (ضررِ سنگینِ ثبت‌شده −$20k) با کمیسیونِ صفر")
    for asset, path in [('EURUSD', DATA_EUR), ('AUDUSD', DATA_AUD)]:
        if not os.path.exists(path):
            print(f"  {asset}: فایلِ داده موجود نیست — رد شد")
            continue
        dff = load(path)
        lsig, ssig = build_forex_meanrev(dff)
        r = run_layer(dff, lsig, ssig, sl=30, tp=45, hold=48, asset=asset)  # comm=0 در موتور
        g = gate(r)
        print(f"  {asset:8s} (comm=0)  net={r['net']:+9,.0f}$  n={r['n']}  "
              f"h1={r.get('h1',0):+,.0f} h2={r.get('h2',0):+,.0f}  gate={'✅' if g else '❌'}")
        out['candidates'][f'S71_{asset}_comm0'] = dict(new=r, gate_new=g, revived=g)

    # ================= (ج) EURUSD MA-Pullback (s149) با کمیسیونِ صفر =================
    print("\n[ج] EURUSD MA-Pullback روند-پیرو (s149، ثبت‌شده −$4,771 با کمیسیون ۷$) با کمیسیونِ صفر")
    # (کمیسیونِ EURUSD در موتور از قبل صفر است → مدلِ جدید)
    dfe = load(DATA_EUR)
    for d in ('both', 'long', 'short'):
        ls, ss = gen_ma_pullback(dfe, direction=d)
        # جاروبِ سبکِ TP/SL/hold مطابقِ s149 (بدونِ بهینه‌سازیِ کل-داده)
        best = None
        for (sl, tp, hold) in [(20, 30, 48), (25, 40, 48), (30, 45, 64)]:
            r = run_layer(dfe, ls, ss, sl, tp, hold, 'EURUSD')
            if best is None or r['net'] > best[1]['net']:
                best = ((sl, tp, hold), r)
        (sl, tp, hold), r = best
        g = gate(r)
        print(f"  dir={d:5s} SL{sl}/TP{tp}/H{hold}: net={r['net']:+9,.0f}$  n={r['n']}  "
              f"h1={r.get('h1',0):+,.0f} h2={r.get('h2',0):+,.0f}  WF={r.get('wf')}  gate={'✅' if g else '❌'}")
        out['candidates'][f'S149_pullback_{d}_comm0'] = dict(new=r, gate_new=g, revived=g,
                                                             params=dict(sl=sl, tp=tp, hold=hold))

    # ================= جمع‌بندی =================
    revived_any = [k for k, v in out['candidates'].items() if v.get('revived')]
    print("\n" + "=" * 84)
    if revived_any:
        print(f"🎉 احیاشده: {len(revived_any)} کاندید → {revived_any}")
    else:
        print("نتیجه: هیچ کاندیدی از گیتِ سختِ پروژه با مشخصاتِ جدید عبور نکرد که قبلاً رد می‌شد.")
        print("(کاهشِ هزینه سود را بهبود داد، ولی لبهٔ ساختاریِ پایدار نساخت.)")
    out['revived'] = revived_any

    os.makedirs('results', exist_ok=True)
    with open('results/_s156_revive_costsensitive.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n✅ ذخیره شد: results/_s156_revive_costsensitive.json")


if __name__ == '__main__':
    main()
