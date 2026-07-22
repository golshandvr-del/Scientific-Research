# -*- coding: utf-8 -*-
"""
s158_scored_confirmation_weak_layers.py
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم،
> نه آمارِ زیبا.** تنها تابعِ هدف: **سودِ خالصِ تجمعیِ پس از اسپرد/اسلیپیج/کمیسیون.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
انگیزه (User Note این نشست، بخشِ ۲):
  «چرا از استراتژی‌های کنارگذاشته به‌عنوانِ *تأیید* استفاده نکردیم تا WR بالاتر برود؟»

S157 نشان داد فیلترِ تک‌بعدیِ AND-سخت برای S142/S81/S143 «بیش‌ازحد» معامله حذف می‌کند
و سود می‌افتد. این اسکریپت رویکردِ **تأییدِ امتیازی (scored confirmation)** را می‌آزماید:
  به‌جای AND-سختِ یک فیلتر، به هر معامله یک «امتیازِ تأیید» می‌دهیم (تعدادِ فیلترهای
  ناهمبستهٔ برقرار) و فقط معاملاتی را نگه می‌داریم که score >= k. این ملایم‌تر است و
  اجازه می‌دهد نقطهٔ بهینهٔ (WR≥40٪ + بیشینهٔ سودِ خالص) پیدا شود.

هم‌چنین برای لایهٔ R:R-خیلی-بالای S81 (TP1200/SL120)، جاروبِ کوچکِ TP را هم می‌آزماییم
(کاهشِ TP، WRِ ساختاری را بالا می‌برد؛ باید سودِ خالص حفظ شود).

مشخصاتِ واقعیِ حساب و پنجرهٔ ۴ ساله دقیقاً مثلِ S157/ممیزی.
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

se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)
se.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def last_n_years(df, years=YEARS):
    end = df['dt'].iloc[-1]; start = end - pd.DateOffset(years=years)
    return df[df['dt'] >= start].reset_index(drop=True), start, end


def add_calendar(df):
    dt = df['dt']
    df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day; df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df


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


def run_layer(df, ls, shs, sl, tp, mh, asset='XAUUSD', be=None, trail=None):
    tr = se.simulate_trades(df, ls, shs, sl, tp, asset, max_hold=mh,
                            allow_overlap=False, be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    return tr


# ----------------------------- فیلترهای پایه -----------------------------
def build_confirms(df, asset_kind='gold'):
    """دیکشنریِ فیلترهای ناهمبسته برای امتیازدهی (همه بدون look-ahead)."""
    c = df['close']
    e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
    a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values
    r14 = ind.rsi(c, 14).values
    _, _, hist = ind.macd(c)
    hist = hist.values
    price = c.values
    conf = {}
    conf['price>EMA200'] = np.nan_to_num(price > e200, nan=False).astype(bool)
    conf['EMA50>EMA200'] = np.nan_to_num(e50 > e200, nan=False).astype(bool)
    conf['ATR14>ATR100'] = np.nan_to_num((a100 > 0) & (a14 > a100), nan=False).astype(bool)
    conf['MACD>0'] = np.nan_to_num(hist > 0, nan=False).astype(bool)
    conf['RSI∈[35,70]'] = np.nan_to_num((r14 >= 35) & (r14 <= 70), nan=False).astype(bool)
    # DXY رژیم (asof)
    conf['DXY<EMA200'] = align_dxy(df)
    return conf


def align_dxy(df_asset):
    dxy = load('DXY_M15')
    dxy['ema200'] = ind.ema(dxy['close'], 200)
    bear = (dxy['close'] < dxy['ema200']).astype(float)
    a = df_asset[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'),
                      dxy[['time']].assign(bear=bear.values).sort_values('time'),
                      on='time', direction='backward').sort_values('idx')
    return (np.nan_to_num(m['bear'].values, nan=0.0) > 0.5)


def scored_mask(conf, keys, k):
    """ماسک: حداقل k فیلتر از میانِ keys برقرار باشد."""
    score = np.zeros(len(next(iter(conf.values()))), dtype=int)
    for key in keys:
        score += conf[key].astype(int)
    return score >= k


def eval_scored(name, df, base_long, base_short, sl, tp, mh, asset, conf, keys):
    print("\n" + "=" * 100)
    print(f"لایه: {name}  (SL{sl}/TP{tp}/mh{mh}، {asset}) — تأییدِ امتیازیِ {len(keys)} فیلتر")
    print("-" * 100)
    is_short = base_short.any()
    be = 8 if is_short else None; trail = 8 if is_short else None
    tr0 = run_layer(df, base_long, base_short, sl, tp, mh, asset, be=be, trail=trail)
    b = stats_capital(tr0, asset)
    print(f"{'BASELINE':30s} n={b['n']:>5} WR={b['wr']:>5.1f}%  net={b['net']:>+11,.0f}  PF={b['pf']:.2f}")
    out = {'baseline': b, 'k_variants': {}, 'best': None}
    best = None
    for k in range(1, len(keys) + 1):
        m = scored_mask(conf, keys, k)
        if is_short:
            ls = np.zeros(len(df), bool); shs = base_short & m
        else:
            ls = base_long & m; shs = np.zeros(len(df), bool)
        tr = run_layer(df, ls, shs, sl, tp, mh, asset, be=be, trail=trail)
        s = stats_capital(tr, asset)
        out['k_variants'][f'k>={k}'] = s
        flag = ''
        if s['wr'] >= 40.0 and s['net'] >= b['net'] - 1e-6:
            flag = '  ✅'
            if best is None or s['net'] > best[1]['net']:
                best = (f'score≥{k} از {len(keys)} تأیید', s)
        elif s['wr'] >= 40.0:
            flag = f'  △ سود {s["net"]-b["net"]:+,.0f}'
        print(f"{('score≥'+str(k)):30s} n={s['n']:>5} WR={s['wr']:>5.1f}%  net={s['net']:>+11,.0f}  PF={s['pf']:.2f}{flag}")
    if best:
        out['best'] = {'filter': best[0], **best[1]}
        d = best[1]['net'] - b['net']
        print(f"🥇 بهترین: «{best[0]}»  WR {b['wr']:.1f}%→{best[1]['wr']:.1f}%  net {b['net']:+,.0f}→{best[1]['net']:+,.0f} (Δ{d:+,.0f})")
    else:
        print("⚠️ هیچ آستانهٔ امتیازی هم‌زمان WR≥40 و حفظِ سود را رعایت نکرد.")
    return out


def main():
    print("=" * 100)
    print("S158 — تأییدِ امتیازیِ چند-فیلتری روی لایه‌های ضعیف (WR<40٪)")
    print("=" * 100, flush=True)
    report = {}

    dfx = add_calendar(load('XAUUSD_M15'))
    dfx4, s4, e4 = last_n_years(dfx); dfx4 = add_calendar(dfx4.copy())
    n = len(dfx4); zeros = np.zeros(n, bool)
    conf_g = build_confirms(dfx4, 'gold')
    KEYS_G = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']

    base_s140 = (dfx4['dow'].values == 0) & np.isin(dfx4['hour'].values, [18, 19, 20, 21])
    report['S140'] = eval_scored('S140 Monday', dfx4, base_s140, zeros, 100, 300, 96, 'XAUUSD', conf_g, KEYS_G)

    base_s142 = np.isin(dfx4['dom'].values, [10, 13, 20]) & np.isin(dfx4['hour'].values, list(range(1, 13)))
    report['S142'] = eval_scored('S142 Mid-Month', dfx4, base_s142, zeros, 100, 500, 96, 'XAUUSD', conf_g, KEYS_G)

    # S81 M30
    dfm30 = add_calendar(load('XAUUSD_M30'))
    dfm30_4, _, _ = last_n_years(dfm30); dfm30_4 = dfm30_4.reset_index(drop=True)
    c30 = dfm30_4['close']
    e20 = ind.ema(c30, 20).values; e100b = ind.ema(c30, 100).values; r14 = ind.rsi(c30, 14).values
    base_s81 = np.nan_to_num((e20 > e100b) & (r14 < 35), nan=False).astype(bool)
    conf_81 = build_confirms(dfm30_4, 'gold')
    KEYS_81 = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'DXY<EMA200']  # MACD/RSI با base همبسته‌اند
    report['S81'] = eval_scored('S81 Swing-Pullback', dfm30_4, base_s81,
                                np.zeros(len(dfm30_4), bool), 120, 1200, 144, 'XAUUSD_M30', conf_81, KEYS_81)

    # S81 با کاهشِ TP (جاروبِ کوچک برای بالا بردنِ WRِ ساختاری)
    print("\n" + "#" * 100)
    print("# S81 — جاروبِ TP (R:R پایین‌تر ⇒ WR بالاتر؛ باید سودِ خالص حفظ شود)")
    print("#" * 100)
    s81_tp = {}
    b81 = report['S81']['baseline']
    for tp in [300, 400, 500, 600, 800, 1000]:
        tr = run_layer(dfm30_4, base_s81, np.zeros(len(dfm30_4), bool), 120, tp, 144, 'XAUUSD_M30')
        s = stats_capital(tr, 'XAUUSD_M30')
        s81_tp[f'TP{tp}'] = s
        flag = '  ✅' if (s['wr'] >= 40.0 and s['net'] >= b81['net'] - 1e-6) else (
            f'  △ سود {s["net"]-b81["net"]:+,.0f}' if s['wr'] >= 40.0 else '')
        print(f"{('TP'+str(tp)):30s} n={s['n']:>5} WR={s['wr']:>5.1f}%  net={s['net']:>+11,.0f}  PF={s['pf']:.2f}{flag}")
    report['S81_tp_sweep'] = s81_tp

    # S143 EURUSD
    dfe = add_calendar(load('EURUSD_M15'))
    dfe4, _, _ = last_n_years(dfe); dfe4 = add_calendar(dfe4.copy())
    ne = len(dfe4); ze = np.zeros(ne, bool)
    conf_e = build_confirms(dfe4, 'eur')
    KEYS_E = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']
    base_s143 = np.isin(dfe4['dom'].values, [3, 9, 20]) & np.isin(dfe4['hour'].values,
                                                                  [1, 2, 3, 4, 5, 11, 12, 13, 14, 15])
    report['S143'] = eval_scored('S143 EURUSD Mid-Month', dfe4, base_s143, ze, 20, 120, 96, 'EURUSD', conf_e, KEYS_E)

    with open(os.path.join(RESULTS, '_s158_scored_confirmation.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s158_scored_confirmation.json")
    return report


if __name__ == '__main__':
    main()
