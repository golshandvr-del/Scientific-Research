"""
S135 — «فیلترِ کاهشِ ضرر» برای لایهٔ Squeeze→Breakout (کشفِ S132)
================================================================================
> 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت):
>   معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،
>   نه تعدادِ معامله. تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

هدفِ این اسکریپت (پاسخِ User Note این نشست):
  «با حفظ یا افزایشِ سودِ خالص، ضررها و سیگنال‌های غلط را کاهش بده. با کاهشِ ضررها،
   سودِ خالص هم زیاد می‌شود.»

روش (علمی، ضدِ overfit):
  ۱) لایهٔ برندهٔ S132 (sqz_pct=0.25, breakout_lookback=6, TP300/SL90) را اجرا و برای
     *هر معامله* مجموعه‌ای از featureهای «لحظهٔ ورود» را ثبت می‌کنیم (بدون نگاه به آینده):
       - adx14        : قدرتِ روند در لحظهٔ ورود
       - rsi21        : اشباعِ خرید/فروش
       - dist_ema200  : فاصلهٔ درصدیِ قیمت از EMA200 (چقدر «کش‌آمده»)
       - bw_pct       : صدکِ پهنای باند (شدتِ فشردگی)
       - brk_strength : قدرتِ شکست = (close - priorHigh)/ATR
       - atr_pct      : ATR/price (رژیمِ نوسان)
       - dow          : روزِ هفته (۰=دوشنبه)
       - hour         : ساعتِ UTC (سشن)
  ۲) توزیعِ هر feature را برای بردها vs ضررها مقایسه می‌کنیم تا «امضای ضرر» را بیابیم.
  ۳) چند فیلترِ ساده و قابل‌تفسیر (تک‌شرطی) را جدا می‌سنجیم؛ فقط فیلتری را نگه می‌داریم
     که سودِ خالص را *بالا ببرد* (یا حفظ کند ولی ضرر و DD را کم کند) و در *هر دو نیمهٔ
     داده* و *walk-forward* پایدار باشد (گیتِ ضدِ overfit).
  ۴) خروجی: بهترین فیلتر + Δ سودِ خالص + آمارِ کاهشِ ضرر. ذخیره در JSON.

هیچ داده‌ای از آینده استفاده نمی‌شود: همهٔ featureها با اندیس ≤ i (کندلِ سیگنال) اند و
ورود در open کندلِ i+1 اجرا می‌شود (منطبق با paper_broker).
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strategies.s91_scalp_signal_exit import paper_broker, ema, rsi, atr, stats
from strategies.s94_scalp_hidden_target import make_hidden_exit
from strategies.s132_squeeze_breakout_m15 import (
    build_entries_squeeze, bollinger_bandwidth, rolling_min_percentile,
)

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(ROOT, 'results')
PIP = 0.1
MAX_HOLD_M15 = 96

# پارامترِ برندهٔ s133 (ثابت — بدونِ جاروبِ دوباره تا از overfit پرهیز شود)
SQZ_PCT = 0.25
BRK_LB = 6
TP_PIP = 300.0
SL_PIP = 90.0


def adx(df, period=14):
    """ADX کلاسیک (Welles Wilder). بردارِ هم‌طولِ df."""
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)
    tr = np.zeros(n); plus_dm = np.zeros(n); minus_dm = np.zeros(n)
    for i in range(1, n):
        up = h[i] - h[i - 1]
        dn = l[i - 1] - l[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    # Wilder smoothing
    atr_s = np.zeros(n); pdm_s = np.zeros(n); mdm_s = np.zeros(n)
    adx_out = np.full(n, np.nan)
    if n <= period:
        return adx_out
    atr_s[period] = tr[1:period + 1].sum()
    pdm_s[period] = plus_dm[1:period + 1].sum()
    mdm_s[period] = minus_dm[1:period + 1].sum()
    dx = np.full(n, np.nan)
    for i in range(period + 1, n):
        atr_s[i] = atr_s[i - 1] - atr_s[i - 1] / period + tr[i]
        pdm_s[i] = pdm_s[i - 1] - pdm_s[i - 1] / period + plus_dm[i]
        mdm_s[i] = mdm_s[i - 1] - mdm_s[i - 1] / period + minus_dm[i]
        if atr_s[i] > 0:
            pdi = 100.0 * pdm_s[i] / atr_s[i]
            mdi = 100.0 * mdm_s[i] / atr_s[i]
            denom = pdi + mdi
            dx[i] = 100.0 * abs(pdi - mdi) / denom if denom > 0 else 0.0
    # ADX = smoothed DX
    first = period * 2
    if n > first:
        adx_out[first] = np.nanmean(dx[period + 1:first + 1])
        for i in range(first + 1, n):
            if not np.isnan(dx[i]) and not np.isnan(adx_out[i - 1]):
                adx_out[i] = (adx_out[i - 1] * (period - 1) + dx[i]) / period
    return adx_out


def build_entries_with_features(df):
    """
    همان ماشهٔ برندهٔ S132 + ثبتِ featureهای لحظهٔ ورود (اندیسِ سیگنال i).
    برمی‌گرداند: (entries [(i,'long')...], feat_by_i {i: {...}})
    """
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    n = len(df)

    bw, mid, upper = bollinger_bandwidth(c, 20, 2.0)
    bw_pct = rolling_min_percentile(bw, 100)
    ef50 = ema(c, 50)
    es200 = ema(c, 200)
    rsi21 = rsi(c, 21)
    atr14 = atr(df, 14)
    adx14 = adx(df, 14)
    t = pd.to_datetime(df['time'].values, unit='s', utc=True)
    dow = t.dayofweek.values
    hour = t.hour.values

    entries = []
    feat = {}
    for i in range(200, n - 1):
        # ماشهٔ S132: فشردگی (bw_pct پایین) + شکستِ صعودی + گیتِ روند
        if np.isnan(bw_pct[i]) or bw_pct[i] > SQZ_PCT:
            continue
        b_lo = max(0, i - BRK_LB)
        prior_high = np.nanmax(h[b_lo:i]) if i > b_lo else np.nan
        if not (np.isfinite(prior_high) and c[i] > prior_high):
            continue
        if not (np.isfinite(ef50[i]) and np.isfinite(es200[i]) and ef50[i] > es200[i]):
            continue
        entries.append((i, 'long'))
        atrv = atr14[i] if (np.isfinite(atr14[i]) and atr14[i] > 0) else np.nan
        feat[i] = dict(
            adx14=float(adx14[i]) if np.isfinite(adx14[i]) else np.nan,
            rsi21=float(rsi21[i]) if np.isfinite(rsi21[i]) else np.nan,
            dist_ema200=float((c[i] - es200[i]) / es200[i] * 100.0) if es200[i] else np.nan,
            bw_pct=float(bw_pct[i]),
            brk_strength=float((c[i] - prior_high) / atrv) if np.isfinite(atrv) else np.nan,
            atr_pct=float(atrv / c[i] * 100.0) if (np.isfinite(atrv) and c[i]) else np.nan,
            dow=int(dow[i]),
            hour=int(hour[i]),
        )
    return entries, feat


def run_trades(df, entries):
    exit_fn = make_hidden_exit(TP_PIP, SL_PIP, use_trend_break=False)
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=400.0,
                      max_hold=MAX_HOLD_M15)
    return tr


def attach_features(tr, feat):
    """feature‌های لحظهٔ ورود را به هر معامله می‌چسباند (بر اساسِ entry_bar-1=سیگنال)."""
    cols = ['adx14', 'rsi21', 'dist_ema200', 'bw_pct', 'brk_strength', 'atr_pct', 'dow', 'hour']
    for cln in cols:
        tr[cln] = np.nan
    for idx in tr.index:
        sig_i = int(tr.at[idx, 'entry_bar']) - 1  # سیگنال یک کندل قبل از ورود
        f = feat.get(sig_i)
        if f is None:
            # ممکن است entry_bar به‌خاطرِ busy_until جابه‌جا شده باشد؛ نزدیک‌ترین را نگیر
            continue
        for cln in cols:
            tr.at[idx, cln] = f[cln]
    return tr, cols


def net_of(tr):
    return float(tr['net_usd'].sum()) if len(tr) else 0.0


def half_wf_gates(df, entries_all, mask_fn):
    """گیتِ ضدِ overfit: سودِ خالص در هر دو نیمه + هر ۴ پنجرهٔ walk-forward
    وقتی فیلتر اعمال شود. mask_fn(feat_i)->bool تصمیم می‌گیرد معامله نگه‌داشته شود."""
    n = len(df)
    halves = []
    for (a, b) in [(0, n // 2), (n // 2, n)]:
        seg = df.iloc[a:b].reset_index(drop=True)
        e, f = build_entries_with_features(seg)
        e2 = [(i, s) for (i, s) in e if mask_fn(f.get(i, {}))]
        tr = run_trades(seg, e2)
        halves.append(net_of(tr))
    wf = []
    step = n // 4
    for k in range(4):
        a = k * step
        b = n if k == 3 else (k + 1) * step
        seg = df.iloc[a:b].reset_index(drop=True)
        e, f = build_entries_with_features(seg)
        e2 = [(i, s) for (i, s) in e if mask_fn(f.get(i, {}))]
        tr = run_trades(seg, e2)
        wf.append(net_of(tr))
    return halves, wf


def main():
    print("=" * 92)
    print("S135 — فیلترِ کاهشِ ضرر برای لایهٔ Squeeze→Breakout (پاسخِ User Note)")
    print("قانونِ #۱: سودِ خالص = XAUUSD + EURUSD (نه WR). هدف: کاهشِ ضرر ⇒ افزایشِ سودِ خالص.")
    print("=" * 92, flush=True)

    df = pd.read_csv(DATA)
    print(f"داده: {len(df):,} کندلِ M15 XAUUSD", flush=True)

    # ── مبنا: لایهٔ Squeeze بدونِ فیلتر ──
    entries, feat = build_entries_with_features(df)
    tr0 = run_trades(df, entries)
    tr0, cols = attach_features(tr0, feat)
    base_net = net_of(tr0)
    wins0 = tr0[tr0['pnl_pip'] > 0]
    loss0 = tr0[tr0['pnl_pip'] <= 0]
    gross_loss0 = float(abs(loss0['net_usd'].sum()))
    print(f"\n── مبنا (بدونِ فیلتر) ──")
    print(f"  n={len(tr0)}  net=${base_net:+,.2f}  wins={len(wins0)}  losses={len(loss0)}  "
          f"WR={len(wins0)/max(1,len(tr0))*100:.1f}%  ضررِ ناخالص=${gross_loss0:,.0f}", flush=True)

    # ── امضای ضرر: میانگینِ هر feature برای بردها vs ضررها ──
    print(f"\n── امضای ضرر (میانگینِ feature: برد | ضرر) ──")
    signature = {}
    for cln in cols:
        wv = wins0[cln].dropna(); lv = loss0[cln].dropna()
        if len(wv) and len(lv):
            signature[cln] = dict(win=float(wv.mean()), loss=float(lv.mean()))
            print(f"  {cln:14s}: برد={wv.mean():+8.3f}  |  ضرر={lv.mean():+8.3f}  "
                  f"Δ={wv.mean()-lv.mean():+.3f}", flush=True)

    # ── کاندیدهای فیلترِ ساده و قابل‌تفسیر (تک‌شرطی) ──
    # هر فیلتر: تابعی که feature لحظهٔ ورود را می‌گیرد و True=نگه‌دار می‌دهد.
    candidates = {
        'بدونِ فیلتر (مبنا)':        lambda f: True,
        'ADX>=20 (روندِ کافی)':      lambda f: f.get('adx14', 0) >= 20,
        'ADX>=25 (روندِ قوی)':       lambda f: f.get('adx14', 0) >= 25,
        'RSI<=70 (نه اشباعِ خرید)':  lambda f: f.get('rsi21', 100) <= 70,
        'RSI<=75':                    lambda f: f.get('rsi21', 100) <= 75,
        'dist_ema200<=3% (نه کش‌آمده)': lambda f: f.get('dist_ema200', 99) <= 3.0,
        'dist_ema200<=5%':            lambda f: f.get('dist_ema200', 99) <= 5.0,
        'brk_strength>=0.15 (شکستِ قاطع)': lambda f: f.get('brk_strength', 0) >= 0.15,
        'brk_strength>=0.30':         lambda f: f.get('brk_strength', 0) >= 0.30,
        'atr_pct>=0.20 (نوسانِ کافی)': lambda f: f.get('atr_pct', 0) >= 0.20,
        'not-Friday (بدونِ جمعه)':    lambda f: f.get('dow', 0) != 4,
        'session 7-20 UTC (Lon+NY)':  lambda f: 7 <= f.get('hour', 0) <= 20,
    }

    print(f"\n── ارزیابیِ فیلترها (فقط فیلتری که سودِ خالص را بالا ببرد نگه می‌داریم) ──")
    print(f"  {'فیلتر':38s} {'n':>5} {'net':>12} {'Δnet':>11} {'ضرر':>10} {'Δضرر':>10}")
    print("  " + "-" * 92)
    results = {}
    for name, fn in candidates.items():
        e2 = [(i, s) for (i, s) in entries if fn(feat.get(i, {}))]
        tr = run_trades(df, e2)
        tr, _ = attach_features(tr, feat)
        net = net_of(tr)
        loss = tr[tr['pnl_pip'] <= 0]
        gl = float(abs(loss['net_usd'].sum()))
        results[name] = dict(n=int(len(tr)), net=net, dnet=net - base_net,
                             gross_loss=gl, dloss=gl - gross_loss0,
                             wr=float(len(tr[tr['pnl_pip'] > 0]) / max(1, len(tr)) * 100))
        print(f"  {name:38s} {len(tr):>5} {net:>+12,.0f} {net-base_net:>+11,.0f} "
              f"{gl:>+10,.0f} {gl-gross_loss0:>+10,.0f}", flush=True)

    # ── انتخابِ بهترین فیلتر: بیشترین سودِ خالص (قانونِ #۱) ──
    best_name = max((k for k in results if k != 'بدونِ فیلتر (مبنا)'),
                    key=lambda k: results[k]['net'])
    best = results[best_name]
    print(f"\n── بهترین فیلترِ تک‌شرطی: «{best_name}» ──")
    print(f"  net=${best['net']:+,.0f}  (Δ نسبت به مبنا = {best['dnet']:+,.0f}$)  "
          f"ضررِ ناخالص=${best['gross_loss']:,.0f} (Δ={best['dloss']:+,.0f}$)  "
          f"WR={best['wr']:.1f}%", flush=True)

    # ── گیتِ ضدِ overfit روی بهترین فیلتر ──
    best_fn = candidates[best_name]
    halves, wf = half_wf_gates(df, entries, best_fn)
    h_ok = all(x > 0 for x in halves)
    wf_ok = all(x > 0 for x in wf)
    print(f"\n── گیتِ ضدِ overfit (بهترین فیلتر) ──")
    print(f"  نیمه‌ها: {[round(x) for x in halves]}  → {'✅ هر دو مثبت' if h_ok else '❌ منفی دارد'}")
    print(f"  WF(۴ پنجره): {[round(x) for x in wf]}  → {'✅ هر ۴ مثبت' if wf_ok else '❌ منفی دارد'}",
          flush=True)

    verdict = (best['net'] > base_net) and h_ok and wf_ok
    print(f"\n{'='*92}")
    print(f"داوری: {'✅ فیلتر سودِ خالص را بالا برد و پایدار است' if verdict else '❌ فیلترِ پایداری که سود را بالا ببرد یافت نشد'}")
    if verdict:
        print(f"  سودِ خالصِ لایهٔ Squeeze: ${base_net:+,.0f} → ${best['net']:+,.0f} "
              f"(+${best['dnet']:,.0f})  با کاهشِ ضرر ${-best['dloss']:,.0f}$")
    print(f"{'='*92}")

    os.makedirs(RESULTS, exist_ok=True)
    out = dict(
        base_net=base_net, base_gross_loss=gross_loss0, base_n=int(len(tr0)),
        signature=signature, filters=results,
        best_filter=best_name, best=best,
        halves=halves, wf=wf, half_ok=h_ok, wf_ok=wf_ok, verdict=bool(verdict),
    )
    with open(os.path.join(RESULTS, '_s135_squeeze_loss_filter.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("خلاصه در results/_s135_squeeze_loss_filter.json ذخیره شد.")
    print("قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (نه WR).")


if __name__ == '__main__':
    main()
