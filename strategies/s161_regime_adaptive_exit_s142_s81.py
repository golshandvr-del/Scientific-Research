# -*- coding: utf-8 -*-
"""
s161_regime_adaptive_exit_s142_s81.py
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
انگیزه: S160 نشان داد فیلتر/TP-ثابت برای رساندنِ WR≥40 در S142/S81 سود را نابود
می‌کند (Δ −11.6k و −18.3k). فرضیهٔ آخر: به‌جای TPِ ثابت، **TPِ تطبیقیِ رژیم-آگاه**:
  • وقتی «تأییدها قوی» است (score بالا از فیلترهای متعامد) ⇒ TPِ بلند نگه‌دار (بگذار
    بردِ بزرگ بدود — منبعِ سودِ لایه‌های R:R-بالا).
  • وقتی «تأییدها ضعیف» است ⇒ TPِ کوتاه (سودِ سریع بگیر ⇒ WR بالا می‌رود).
این per-signal است: tp_pip یک آرایه می‌شود (موتور از tp آرایه‌ای پشتیبانی می‌کند).

هدف: آیا ترکیبِ «TPِ دوگانهٔ رژیم-آگاه» می‌تواند WR≥40 بدهد بدونِ افتِ چشمگیرِ سود؟
اگر باز هم نشد ⇒ نتیجهٔ علمیِ قطعی: WR-پایینِ این دو لایه ساختاری است.

مشخصاتِ واقعیِ حساب و پنجرهٔ ۴ ساله دقیقاً مثلِ S157–S160.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK, YEARS = 10000.0, 1.0, 4
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s'); return df.reset_index(drop=True)


def last_n_years(df, years=YEARS):
    end = df['dt'].iloc[-1]; start = end - pd.DateOffset(years=years)
    return df[df['dt'] >= start].reset_index(drop=True), start, end


def add_calendar(df):
    dt = df['dt']; df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day; return df


def stats_capital(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values if len(pt) else np.array([])
    wins = int((nu > 0).sum()); losses = int((nu <= 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()) if n else 0.0; gl = float(-nu[nu <= 0].sum()) if n else 0.0
    return dict(net=float(st['net_profit']), n=n, wins=wins, losses=losses,
                wr=(wins / n * 100.0 if n else 0.0), pf=(gp / gl if gl > 0 else float('inf')))


def run_layer_arr(df, ls, shs, sl, tp_arr, mh, asset):
    """tp_arr آرایهٔ هم‌طولِ df (TPِ per-signal)."""
    tr = se.simulate_trades(df, ls, shs, sl, tp_arr, asset, max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0: return None
    tr = tr.copy(); tr['sl_pip'] = float(sl); return tr


def align_dxy(df_asset):
    dxy = load('DXY_M15'); dxy['ema200'] = ind.ema(dxy['close'], 200)
    bear = (dxy['close'] < dxy['ema200']).astype(float)
    a = df_asset[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'),
                      dxy[['time']].assign(bear=bear.values).sort_values('time'),
                      on='time', direction='backward').sort_values('idx')
    return (np.nan_to_num(m['bear'].values, nan=0.0) > 0.5)


def confirm_score(df, keys):
    c = df['close']; e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
    a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values
    r14 = ind.rsi(c, 14).values; _, _, hist = ind.macd(c); hist = hist.values; price = c.values
    allf = {
        'price>EMA200': np.nan_to_num(price > e200, nan=False).astype(bool),
        'EMA50>EMA200': np.nan_to_num(e50 > e200, nan=False).astype(bool),
        'ATR14>ATR100': np.nan_to_num((a100 > 0) & (a14 > a100), nan=False).astype(bool),
        'MACD>0': np.nan_to_num(hist > 0, nan=False).astype(bool),
        'RSI∈[35,70]': np.nan_to_num((r14 >= 35) & (r14 <= 70), nan=False).astype(bool),
        'DXY<EMA200': align_dxy(df),
    }
    score = np.zeros(len(df), dtype=int)
    for k in keys: score += allf[k].astype(int)
    return score


def eval_adaptive(name, df, base_long, base_short, sl, tp_long, tp_short, mh, asset,
                  keys, score_thr, baseline_tp):
    is_short = base_short.any()
    b = stats_capital(se.simulate_trades(df, base_long, base_short, sl, baseline_tp, asset,
                                         max_hold=mh, allow_overlap=False,
                                         be_trigger_pip=(8 if is_short else None),
                                         trail_pip=(8 if is_short else None)) .pipe(
                          lambda t: t.assign(sl_pip=float(sl)) if t is not None and len(t) else t), asset)
    print("\n" + "=" * 100)
    print(f"لایه: {name}  BASELINE  n={b['n']} WR={b['wr']:.1f}%  net={b['net']:+,.0f}  PF={b['pf']:.2f}")
    print(f"  TPِ تطبیقی: score≥{score_thr} ⇒ TP{tp_long} (بگذار بدود) ، وگرنه TP{tp_short} (سودِ سریع)")
    score = confirm_score(df, keys)
    strong = score >= score_thr
    tp_arr = np.where(strong, float(tp_long), float(tp_short))
    ls = base_long; shs = base_short
    s = stats_capital(run_layer_arr(df, ls, shs, sl, tp_arr, mh, asset), asset)
    d = s['net'] - b['net']
    ok = '✅' if (s['wr'] >= 40 and s['net'] >= b['net'] - 1e-6) else (
        f'△ سود {d:+,.0f}' if s['wr'] >= 40 else 'WR<40')
    print(f"  نتیجه: n={s['n']} WR={s['wr']:.1f}%  net={s['net']:+,.0f} (Δ{d:+,.0f})  PF={s['pf']:.2f}  {ok}")
    return {'baseline': b, 'adaptive': s, 'params': dict(tp_long=tp_long, tp_short=tp_short,
            score_thr=score_thr, keys=keys)}


def main():
    print("=" * 100); print("S161 — TPِ تطبیقیِ رژیم-آگاه روی S142/S81"); print("=" * 100, flush=True)
    report = {}
    dfx = add_calendar(load('XAUUSD_M15')); dfx4, _, _ = last_n_years(dfx); dfx4 = add_calendar(dfx4.copy())
    KEYS_G = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']
    zeros = np.zeros(len(dfx4), bool)
    base_s142 = np.isin(dfx4['dom'].values, [10, 13, 20]) & np.isin(dfx4['hour'].values, list(range(1, 13)))

    best142 = None
    for thr in [2, 3, 4]:
        for tps in [150, 200, 250]:
            for tpl in [500, 600, 800]:
                r = eval_adaptive('S142 Mid-Month', dfx4, base_s142, zeros, 100, tpl, tps, 96, 'XAUUSD',
                                  KEYS_G, thr, baseline_tp=500)
                s = r['adaptive']; b = r['baseline']
                if s['wr'] >= 40 and (best142 is None or s['net'] > best142['adaptive']['net']):
                    best142 = r
    report['S142_best'] = best142

    dfm30 = add_calendar(load('XAUUSD_M30')); dfm30_4, _, _ = last_n_years(dfm30); dfm30_4 = dfm30_4.reset_index(drop=True)
    c30 = dfm30_4['close']; e20 = ind.ema(c30, 20).values; e100b = ind.ema(c30, 100).values; r14 = ind.rsi(c30, 14).values
    base_s81 = np.nan_to_num((e20 > e100b) & (r14 < 35), nan=False).astype(bool)
    KEYS_81 = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'DXY<EMA200']
    zeros81 = np.zeros(len(dfm30_4), bool)

    best81 = None
    for thr in [1, 2, 3]:
        for tps in [150, 200, 300]:
            for tpl in [800, 1000, 1200]:
                r = eval_adaptive('S81 Swing-Pullback', dfm30_4, base_s81, zeros81, 120, tpl, tps, 144,
                                  'XAUUSD_M30', KEYS_81, thr, baseline_tp=1200)
                s = r['adaptive']
                if s['wr'] >= 40 and (best81 is None or s['net'] > best81['adaptive']['net']):
                    best81 = r
    report['S81_best'] = best81

    print("\n" + "#" * 100)
    for tag, r in [('S142', best142), ('S81', best81)]:
        if r:
            b = r['baseline']; s = r['adaptive']; p = r['params']
            print(f"🥇 {tag}: TPl{p['tp_long']}/TPs{p['tp_short']}/score≥{p['score_thr']}  "
                  f"WR {b['wr']:.1f}%→{s['wr']:.1f}%  net {b['net']:+,.0f}→{s['net']:+,.0f} (Δ{s['net']-b['net']:+,.0f})")
        else:
            print(f"⚠️ {tag}: هیچ ترکیبِ تطبیقی WR≥40 نداد.")

    with open(os.path.join(RESULTS, '_s161_regime_adaptive_exit.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s161_regime_adaptive_exit.json")
    return report


if __name__ == '__main__':
    main()
