# -*- coding: utf-8 -*-
"""
s157_confirmation_filters_weak_layers.py
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم،
> نه آمارِ زیبا.** تنها تابعِ هدف: **سودِ خالصِ تجمعیِ پس از اسپرد/اسلیپیج/کمیسیون.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
انگیزه (User Note این نشست — عیناً):
  «(۱) لایه‌هایی که WR زیرِ ۴۰٪ دارند را جوری تغییر و بهبود بده که WR اشان بالای ۴۰٪
   شود. از هر راهی بلدی. (۲) ما خیلی از استراتژی‌ها را کنار گذاشتیم چون گفتیم همبستگی
   دارند و سیگنال‌هایی می‌دهند که لایه‌های فعلی هم می‌دهند. اما چرا از آن‌ها به‌عنوان
   تأیید یا فیلتری بر سیگنال‌های فعلی استفاده نکردیم؟! تا WR بالاتر برود!»

راه‌حلِ این نشست (پاسخِ مستقیم به هر دو نکته):
  استراتژی‌هایی که به‌تنهایی لبهٔ مستقل نداشتند (DXY رژیم، رژیمِ نوسانِ ATR، روندِ
  EMA200، مومنتومِ MACD، بندِ RSI) را **نه به‌عنوان سیگنالِ ورودِ مستقل، بلکه به‌عنوان
  فیلترِ تأییدِ متعامد** روی لایه‌های ضعیف (WR<40٪) اعمال می‌کنیم. فیلتر معامله‌های
  «کم‌کیفیت» را حذف می‌کند ⇒ WR بالا می‌رود. قید: **سودِ خالصِ کل نباید کم شود**
  (قانونِ #۱ همچنان حاکم است).

لایه‌های هدف (WR<40٪ طبقِ ممیزیِ ۴ ساله):
  • S140 Monday        WR 39.7%   +$7,655
  • S142 Mid-Month     WR 35.5%   +$21,012
  • S81  Swing-Pullback WR 28.2%  +$25,488
  • S91  Scalp M5       WR 27.0%  +$317
  • S143 EURUSD Mid-Mo WR 34.0%   +$3,934

روش: هر لایه دقیقاً مثلِ اسکریپتِ ممیزی بازتولید می‌شود (baseline)؛ سپس هر فیلتر
به‌صورتِ ماسکِ AND روی سیگنالِ ورود اعمال و A/B می‌شود. هزینه/موتور/حساب یکسان.

مشخصاتِ واقعیِ حساب: CONTRACT_SIZE=100، طلا ۳.۳pip، کمیسیون صفر، مارجین ۴۰$/لات،
سرمایهٔ ۱۰k$، ریسکِ ۱٪ کامپاند. پنجرهٔ ۴ سالِ اخیر (همان ممیزی).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK, YEARS = 10000.0, 1.0, 4

# ---- مشخصاتِ واقعیِ کاربر (single source of truth، عیناً مثلِ ممیزی) ----
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)
se.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


# ----------------------------- بارگذاری/تقویم -----------------------------
def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def last_n_years(df, years=YEARS):
    end = df['dt'].iloc[-1]
    start = end - pd.DateOffset(years=years)
    return df[df['dt'] >= start].reset_index(drop=True), start, end


def add_calendar(df):
    dt = df['dt']
    df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day; df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df


# ----------------------------- آمارگیری -----------------------------
def stats_capital(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP,
                                        risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values if len(pt) else np.array([])
    wins = int((nu > 0).sum()); losses = int((nu <= 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()) if n else 0.0
    gl = float(-nu[nu <= 0].sum()) if n else 0.0
    return dict(net=float(st['net_profit']), n=n, wins=wins, losses=losses,
                wr=(wins / n * 100.0 if n else 0.0),
                pf=(gp / gl if gl > 0 else float('inf')))


def run_layer(df, long_sig, short_sig, sl, tp, mh, asset='XAUUSD', be=None, trail=None):
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset, max_hold=mh,
                            allow_overlap=False, be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    return tr


# ============================================================================
# فیلترهای تأییدِ متعامد (همه بدون look-ahead: فقط از کندلِ بستهٔ فعلی/گذشته)
# هر فیلتر یک آرایهٔ بولیِ هم‌طولِ df برمی‌گرداند (True = اجازهٔ معامله).
# ============================================================================
def align_dxy_ema200(df_asset):
    """DXY<EMA200 روی تایم‌فریمِ M15، هم‌ترازِ زمانی با df_asset (asof، گذشته-محور)."""
    dxy = load('DXY_M15')
    dxy['ema200'] = ind.ema(dxy['close'], 200)
    dxy_bear = (dxy['close'] < dxy['ema200']).astype(float)  # 1=رژیمِ نزولیِ دلار
    # asof merge: برای هر کندلِ asset، آخرین مقدارِ DXY که زمانش <= زمانِ asset
    a = df_asset[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'),
                      dxy[['time']].assign(bear=dxy_bear.values).sort_values('time'),
                      on='time', direction='backward')
    m = m.sort_values('idx')
    out = np.nan_to_num(m['bear'].values, nan=0.0) > 0.5
    return out


def filt_price_above_ema200(df):
    c = df['close']
    e = ind.ema(c, 200).values
    return np.nan_to_num(df['close'].values > e, nan=False).astype(bool)


def filt_atr_high(df, fast=14, slow=100):
    a_f = ind.atr(df, fast).values; a_s = ind.atr(df, slow).values
    r = np.divide(a_f, a_s, out=np.full_like(a_f, np.nan), where=a_s > 0)
    return np.nan_to_num(r > 1.0, nan=False).astype(bool)


def filt_atr_low(df, fast=14, slow=100):
    return ~filt_atr_high(df, fast, slow) & _valid_atr(df, slow)


def _valid_atr(df, slow=100):
    a_s = ind.atr(df, slow).values
    return np.isfinite(a_s) & (a_s > 0)


def filt_macd_pos(df):
    macd_line, sig, hist = ind.macd(df['close'])
    return np.nan_to_num(hist.values > 0, nan=False).astype(bool)


def filt_rsi_band(df, lo=35, hi=70):
    r = ind.rsi(df['close'], 14).values
    return np.nan_to_num((r >= lo) & (r <= hi), nan=False).astype(bool)


def filt_ema_uptrend(df, fast=50, slow=200):
    c = df['close']
    ef = ind.ema(c, fast).values; es = ind.ema(c, slow).values
    return np.nan_to_num(ef > es, nan=False).astype(bool)


def main():
    print("=" * 100)
    print("S157 — فیلترهای تأییدِ متعامد روی لایه‌های ضعیف (WR<40٪) — هدف: WR↑ بدونِ افتِ سودِ خالص")
    print("قانونِ #۱: سودِ خالص (XAUUSD+EURUSD) اولویت مطلق دارد؛ WR فقط گزارشی است.")
    print("=" * 100, flush=True)

    report = {}  # نتایج برای JSON

    # ============ دادهٔ M15 طلا ============
    dfx = add_calendar(load('XAUUSD_M15'))
    dfx4, s4, e4 = last_n_years(dfx)
    dfx4 = add_calendar(dfx4.copy())
    print(f"\nXAUUSD M15: پنجرهٔ ۴ ساله {s4.date()} → {e4.date()}  ({len(dfx4):,} کندل)")
    n = len(dfx4); zeros = np.zeros(n, bool)

    # فیلترهای مشترکِ طلا (یک‌بار محاسبه)
    f_dxy = align_dxy_ema200(dfx4)
    f_e200 = filt_price_above_ema200(dfx4)
    f_atrH = filt_atr_high(dfx4)
    f_atrL = filt_atr_low(dfx4)
    f_macd = filt_macd_pos(dfx4)
    f_rsi = filt_rsi_band(dfx4, 35, 70)
    f_up = filt_ema_uptrend(dfx4)

    GOLD_FILTERS = {
        'DXY<EMA200 (رژیمِ نزولیِ دلار)': f_dxy,
        'قیمت>EMA200 (روندِ صعودیِ طلا)': f_e200,
        'ATR14>ATR100 (نوسانِ بالا)': f_atrH,
        'ATR14<ATR100 (نوسانِ پایین)': f_atrL,
        'MACD hist>0 (مومنتومِ مثبت)': f_macd,
        'RSI∈[35,70] (غیرِاشباع)': f_rsi,
        'EMA50>EMA200 (روندِ ساختاری)': f_up,
        'DXY<EMA200 & قیمت>EMA200': f_dxy & f_e200,
        'قیمت>EMA200 & MACD>0': f_e200 & f_macd,
    }

    # -------- S140 Monday: dow=0 & hour∈{18..21}  SL100/TP300/mh96 --------
    base_s140 = (dfx4['dow'].values == 0) & np.isin(dfx4['hour'].values, [18, 19, 20, 21])
    report['S140'] = eval_layer('S140 Monday', dfx4, base_s140, zeros, 100, 300, 96,
                                'XAUUSD', GOLD_FILTERS)

    # -------- S142 Mid-Month: dom∈{10,13,20} & hour∈{1..12}  SL100/TP500/mh96 --------
    base_s142 = np.isin(dfx4['dom'].values, [10, 13, 20]) & np.isin(dfx4['hour'].values, list(range(1, 13)))
    report['S142'] = eval_layer('S142 Mid-Month', dfx4, base_s142, zeros, 100, 500, 96,
                                'XAUUSD', GOLD_FILTERS)

    # ============ S81 M30 Swing-Pullback ============
    dfm30 = add_calendar(load('XAUUSD_M30'))
    dfm30_4, s30, e30 = last_n_years(dfm30)
    dfm30_4 = dfm30_4.reset_index(drop=True)
    c30 = dfm30_4['close']
    e20 = ind.ema(c30, 20).values; e100b = ind.ema(c30, 100).values; r14 = ind.rsi(c30, 14).values
    base_s81 = np.nan_to_num((e20 > e100b) & (r14 < 35), nan=False).astype(bool)
    S81_FILTERS = {
        'DXY<EMA200 (رژیمِ نزولیِ دلار)': align_dxy_ema200(dfm30_4),
        'قیمت>EMA200 (روندِ صعودیِ طلا)': filt_price_above_ema200(dfm30_4),
        'ATR14>ATR100 (نوسانِ بالا)': filt_atr_high(dfm30_4),
        'ATR14<ATR100 (نوسانِ پایین)': filt_atr_low(dfm30_4),
        'MACD hist>0 (مومنتومِ مثبت)': filt_macd_pos(dfm30_4),
        'EMA50>EMA200 (روندِ ساختاری)': filt_ema_uptrend(dfm30_4),
        'DXY<EMA200 & قیمت>EMA200': align_dxy_ema200(dfm30_4) & filt_price_above_ema200(dfm30_4),
    }
    report['S81'] = eval_layer('S81 Swing-Pullback', dfm30_4, base_s81,
                               np.zeros(len(dfm30_4), bool), 120, 1200, 144,
                               'XAUUSD_M30', S81_FILTERS)

    # ============ دادهٔ M15 یورو (S143) ============
    dfe = add_calendar(load('EURUSD_M15'))
    dfe4, se5, ee5 = last_n_years(dfe)
    dfe4 = add_calendar(dfe4.copy())
    ne = len(dfe4); ze = np.zeros(ne, bool)
    print(f"\nEURUSD M15: پنجرهٔ ۴ ساله {se5.date()} → {ee5.date()}  ({ne:,} کندل)")

    base_s143 = np.isin(dfe4['dom'].values, [3, 9, 20]) & np.isin(dfe4['hour'].values,
                                                                   [1, 2, 3, 4, 5, 11, 12, 13, 14, 15])
    EUR_FILTERS = {
        'DXY<EMA200 (رژیمِ نزولیِ دلار)': align_dxy_ema200(dfe4),
        'قیمت>EMA200 (روندِ صعودیِ یورو)': filt_price_above_ema200(dfe4),
        'ATR14>ATR100 (نوسانِ بالا)': filt_atr_high(dfe4),
        'ATR14<ATR100 (نوسانِ پایین)': filt_atr_low(dfe4),
        'MACD hist>0 (مومنتومِ مثبت)': filt_macd_pos(dfe4),
        'RSI∈[35,70] (غیرِاشباع)': filt_rsi_band(dfe4, 35, 70),
        'EMA50>EMA200 (روندِ ساختاری)': filt_ema_uptrend(dfe4),
    }
    report['S143'] = eval_layer('S143 EURUSD Mid-Month', dfe4, base_s143, ze, 20, 120, 96,
                                'EURUSD', EUR_FILTERS)

    # ---------------- ذخیره ----------------
    with open(os.path.join(RESULTS, '_s157_confirmation_filters.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s157_confirmation_filters.json")
    return report


def eval_layer(name, df, base_long, base_short, sl, tp, mh, asset, filters):
    """baseline + A/B همهٔ فیلترها؛ چاپِ جدول و انتخابِ بهترین فیلترِ رعایت‌کنندهٔ قانون #۱."""
    print("\n" + "=" * 100)
    print(f"لایه: {name}   (SL{sl}/TP{tp}/mh{mh}، {asset})")
    print("-" * 100)
    is_short = base_short.any()
    tr0 = run_layer(df, base_long, base_short, sl, tp, mh, asset,
                    be=(8 if is_short else None), trail=(8 if is_short else None))
    b = stats_capital(tr0, asset)
    print(f"{'BASELINE (بدونِ فیلتر)':44s} n={b['n']:>5} WR={b['wr']:>5.1f}%  net={b['net']:>+11,.0f}  PF={b['pf']:.2f}")
    print("-" * 100)

    results = {'baseline': b, 'variants': {}}
    best = None
    for fname, mask in filters.items():
        if is_short:
            ls = np.zeros(len(df), bool); shs = base_short & mask
        else:
            ls = base_long & mask; shs = np.zeros(len(df), bool)
        tr = run_layer(df, ls, shs, sl, tp, mh, asset,
                       be=(8 if is_short else None), trail=(8 if is_short else None))
        s = stats_capital(tr, asset)
        results['variants'][fname] = s
        flag = ''
        # قید: WR بالای ۴۰٪ AND سودِ خالص کمتر نشود (قانونِ #۱)
        wr_ok = s['wr'] >= 40.0
        net_ok = s['net'] >= b['net'] - 1e-6
        if wr_ok and net_ok:
            flag = '  ✅ (WR≥40 و سود حفظ/بیشتر)'
            # بهترین = بیشترین سودِ خالص در میانِ واجدین شرط
            if best is None or s['net'] > best[1]['net']:
                best = (fname, s)
        elif wr_ok:
            flag = f'  △ WR≥40 ولی سود {s["net"]-b["net"]:+,.0f}'
        print(f"{fname:44s} n={s['n']:>5} WR={s['wr']:>5.1f}%  net={s['net']:>+11,.0f}  PF={s['pf']:.2f}{flag}")

    results['best'] = None
    if best:
        results['best'] = {'filter': best[0], **best[1]}
        d = best[1]['net'] - b['net']
        print("-" * 100)
        print(f"🥇 بهترین: «{best[0]}»  WR {b['wr']:.1f}%→{best[1]['wr']:.1f}%  "
              f"net {b['net']:+,.0f}→{best[1]['net']:+,.0f} (Δ{d:+,.0f})")
    else:
        print("-" * 100)
        print("⚠️ هیچ فیلتری هم‌زمان WR≥40 و حفظِ سود را رعایت نکرد ⇒ baseline حفظ می‌شود.")
    return results


if __name__ == '__main__':
    main()
