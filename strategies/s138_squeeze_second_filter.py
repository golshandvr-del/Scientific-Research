"""
s138_squeeze_second_filter.py — فیلترِ دومِ کاهشِ سیگنالِ غلط روی لایهٔ Squeeze
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> WR فقط عددِ گزارشی است؛ تعدادِ معامله و Profit Factor هم هدف نیستند.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**
================================================================================

پاسخ به User Note این نشست:
  «هدف افزایشِ سود از سیگنالِ جدید نیست؛ هدف کاهشِ سیگنال‌های غلط برای کاهشِ ضرر و
   به‌دنبالِ آن افزایشِ سودِ خالص است.»

--------------------------------------------------------------------------------
یافتهٔ نشست (s137): لایهٔ SHORT هیچ امضای ضررِ تک‌بعدیِ قابل‌بهره‌برداری ندارد
(تفاوتِ feature بینِ برد/باخت < 0.02؛ ماشه از قبل کارآمد است). پس هدف را به
**لایهٔ Squeeze** منتقل می‌کنیم — تنها لایه‌ای که *اثبات‌شده* امضای ضرر دارد:
`brk_strength≥0.30` قبلاً +$4,424 داد (s136). سؤالِ این نشست:

   آیا یک **فیلترِ دومِ قابل‌تفسیر** روی entriesِ *باقی‌مانده* (پس از brk≥0.30)
   می‌تواند سیگنال‌های غلطِ بیشتری را حذف و سودِ خالص را باز هم بالا ببرد؟

روش (کاملاً هم‌ترازِ s136، ضدِ overfit):
  ۱) ماشه و خروجِ رکوردِ Squeeze عیناً بازتولید می‌شود (TRIG=sqz0.25/lb6, TP300/SL90).
  ۲) فیلترِ اولِ رکورد (`brk_strength≥0.30`) اعمال ⇒ مبنای این نشست = +$24,859.
  ۳) برای entriesِ *باقی‌مانده*، featureهای لحظهٔ ورود ثبت و امضای ضرر یافته می‌شود.
  ۴) فیلترهای دومِ تک‌شرطیِ قابل‌تفسیر جاروب می‌شوند؛ فقط آن‌که سودِ خالص را ↑ و ضرر
     را ↓ کند و در هر دو نیمه + هر ۴ پنجرهٔ walk-forward مثبت بماند پذیرفته می‌شود.
  ۵) خروجی: بهترین فیلترِ دوم + Δ + آمارِ کاهشِ ضرر. ذخیره در JSON.

موتورِ سرمایه دقیقاً مثلِ رکورد: se.run_capital, initial=10000, risk=1%, compounding=True.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind
from strategies.s91_scalp_signal_exit import paper_broker, ema, atr
from strategies.s94_scalp_hidden_target import make_hidden_exit
from strategies.s132_squeeze_breakout_m15 import build_entries_squeeze, DATA, MAX_HOLD_M15

RESULTS = os.path.join(ROOT, 'results')

TP, SL, TB = 300.0, 90.0, False
TRIG = dict(sqz_pct=0.25, breakout_lookback=6)
BRK1 = 0.30                       # فیلترِ اولِ رکورد (s136) — ثابت
RECORD_TOTAL = 126118.0
RECORD_SQUEEZE_BASE = 24859.0    # سهمِ فعلیِ Squeeze در رکورد (پس از brk≥0.30)
RECORD_REST = RECORD_TOTAL - RECORD_SQUEEZE_BASE


def brk_strength_for_entries(df, entries):
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    atr14 = atr(df, 14)
    brk = TRIG['breakout_lookback']
    out = {}
    for (i, _s) in entries:
        prior_high = h[i - brk:i].max() if i >= brk else np.nan
        a = atr14[i] if (np.isfinite(atr14[i]) and atr14[i] > 0) else np.nan
        out[i] = float((c[i] - prior_high) / a) if (np.isfinite(prior_high) and np.isfinite(a)) else 0.0
    return out


def second_features(df, entries):
    """featureهای لحظهٔ ورود برای فیلترِ دوم (همه با اندیس ≤ i، forward-safe)."""
    c = df['close']
    price = c.values
    atr14 = atr(df, 14)
    adx14, _, _ = ind.adx(df, 14); adx14 = adx14.values
    ema200 = ind.ema(c, 200).values
    rsi14 = ind.rsi(c, 14).values
    ema50 = ind.ema(c, 50).values
    out = {}
    for (i, _s) in entries:
        a = atr14[i] if (np.isfinite(atr14[i]) and atr14[i] > 0) else np.nan
        out[i] = dict(
            adx14=float(adx14[i]) if np.isfinite(adx14[i]) else np.nan,
            rsi14=float(rsi14[i]) if np.isfinite(rsi14[i]) else np.nan,
            dist_ema200=float((price[i] - ema200[i]) / ema200[i] * 100.0) if (np.isfinite(ema200[i]) and ema200[i] != 0) else np.nan,
            atr_pct=float(a / price[i] * 100.0) if (np.isfinite(a) and price[i] != 0) else np.nan,
            above_ema50=float(1.0 if (np.isfinite(ema50[i]) and price[i] > ema50[i]) else 0.0),
        )
    return out


def cap_net(df, entries):
    if len(entries) == 0:
        return None, None
    exit_fn = make_hidden_exit(TP, SL, use_trend_break=TB)
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=400.0, max_hold=MAX_HOLD_M15)
    if len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(SL)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=10000.0, risk_pct=1.0, compounding=True)
    return st, tr


def net_of(st):
    if not st: return 0.0
    for k in ('net_profit', 'net', 'total_net', 'net_usd'):
        if k in st: return float(st[k])
    return 0.0


def gross_loss_lot(tr):
    if tr is None or len(tr) == 0: return 0.0
    loss = tr[tr['pnl_pip'] <= 0]
    return float(abs(loss['net_usd'].sum()))


def entries_brk1(df):
    """entriesِ رکورد پس از فیلترِ اولِ brk≥0.30."""
    entries = build_entries_squeeze(df, **TRIG)
    bs = brk_strength_for_entries(df, entries)
    return [(i, s) for (i, s) in entries if bs.get(i, 0) >= BRK1]


def apply_second(df, ent, key, op, thr):
    feats = second_features(df, ent)
    keep = []
    for (i, s) in ent:
        v = feats[i][key]
        if np.isnan(v):
            continue
        ok = (v >= thr) if op == '>=' else (v <= thr) if op == '<=' else \
             (v > thr) if op == '>' else (v < thr)
        if ok:
            keep.append((i, s))
    return keep


def main():
    print("=" * 92)
    print("s138 — فیلترِ دومِ کاهشِ سیگنالِ غلط روی لایهٔ Squeeze (پس از brk≥0.30)")
    print("قانونِ #۱: سودِ خالص = XAUUSD + EURUSD (نه WR). هدف: کاهشِ ضرر ⇒ افزایشِ سود.")
    print("=" * 92, flush=True)

    df = pd.read_csv(DATA)
    n = len(df)
    ent0 = entries_brk1(df)
    st_b, tr_b = cap_net(df, ent0)
    base_net = net_of(st_b); base_gl = gross_loss_lot(tr_b)
    print(f"\nمبنا (فیلترِ اولِ رکورد brk≥0.30): n={len(ent0)}  net=${base_net:+,.0f}  "
          f"ضررِ ناخالص=${base_gl:,.0f}", flush=True)

    # امضای ضرر روی entriesِ باقی‌مانده
    feats = second_features(df, ent0)
    idx = tr_b['entry_bar'].values.astype(int) if 'entry_bar' in tr_b else None
    # نگاشتِ نتیجهٔ هر ورود از روی paper_broker: از pnl استفاده می‌کنیم
    win = tr_b['pnl_pip'].values > 0
    # entry index در paper_broker ممکن است signal_bar باشد؛ برای امضا از خودِ entries استفاده می‌کنیم
    ent_idx = [i for (i, _s) in ent0]
    keys = ['adx14', 'rsi14', 'dist_ema200', 'atr_pct', 'above_ema50']
    print(f"\nامضای ضرر (میانگینِ feature در بردها vs باخت‌ها):")
    print(f"  {'feature':>14} {'برد':>10} {'باخت':>10}")
    m = min(len(ent_idx), len(win))
    for k in keys:
        fv = np.array([feats[ent_idx[j]][k] for j in range(m)])
        w = win[:m]
        mw = np.nanmean(fv[w]); ml = np.nanmean(fv[~w])
        print(f"  {k:>14} {mw:>10.3f} {ml:>10.3f}")

    # جاروبِ فیلترِ دوم
    cands = [
        ('adx14', '>=', 15.0), ('adx14', '>=', 20.0), ('adx14', '>=', 25.0),
        ('rsi14', '>=', 45.0), ('rsi14', '>=', 50.0), ('rsi14', '<=', 75.0), ('rsi14', '<=', 70.0),
        ('dist_ema200', '>=', 0.0), ('dist_ema200', '<=', 5.0), ('dist_ema200', '<=', 3.0),
        ('atr_pct', '<=', 0.5), ('atr_pct', '<=', 0.4), ('atr_pct', '>=', 0.1),
        ('above_ema50', '>=', 1.0),
    ]

    half = n // 2
    df1 = df.iloc[:half].reset_index(drop=True)
    df2 = df.iloc[half:].reset_index(drop=True)
    ent0_1 = entries_brk1(df1); ent0_2 = entries_brk1(df2)

    print(f"\n{'='*92}\nجاروبِ فیلترِ دوم (گیت: net≥مبنا + ضرر<مبنا + هر دو نیمه مثبت):")
    print(f"  {'filter':>22} {'n':>5} {'net':>11} {'Δnet':>10} {'gLoss':>10} {'Δg':>9} {'h1':>9} {'h2':>9} حکم")
    rows = []
    for key, op, thr in cands:
        ent = apply_second(df, ent0, key, op, thr)
        st, tr = cap_net(df, ent)
        if st is None:
            continue
        net = net_of(st); gl = gross_loss_lot(tr)
        e1 = apply_second(df1, ent0_1, key, op, thr)
        e2 = apply_second(df2, ent0_2, key, op, thr)
        st1, _ = cap_net(df1, e1); st2, _ = cap_net(df2, e2)
        h1 = net_of(st1); h2 = net_of(st2)
        both = h1 > 0 and h2 > 0
        ok = both and net >= base_net and gl < base_gl and len(ent) < len(ent0)
        flag = "✅" if ok else "—"
        label = f"{key}{op}{thr}"
        print(f"  {label:>22} {len(ent):>5} ${net:>+10,.0f} ${net-base_net:>+9,.0f} "
              f"${gl:>9,.0f} ${gl-base_gl:>+8,.0f} ${h1:>+8,.0f} ${h2:>+8,.0f} {flag}", flush=True)
        rows.append(dict(filter=label, key=key, op=op, thr=thr, n=int(len(ent)),
                         net=float(net), dnet=float(net - base_net), gloss=float(gl),
                         dgl=float(gl - base_gl), h1=float(h1), h2=float(h2),
                         both_pos=bool(both), ok=bool(ok)))

    passed = [r for r in rows if r['ok']]
    out = dict(base_net=base_net, base_gross_loss=base_gl, base_n=len(ent0), sweep=rows)

    if not passed:
        print("\n⚠️ هیچ فیلترِ دومی هر سه گیت را پاس نکرد. رکورد بدون تغییر می‌ماند.")
        out['verdict'] = False
    else:
        passed.sort(key=lambda r: -r['net'])
        best = passed[0]
        key, op, thr = best['key'], best['op'], best['thr']
        print(f"\n{'='*92}\n🏆 برندهٔ فیلترِ دوم: {best['filter']}")
        print(f"  net=${best['net']:+,.0f}  Δ=${best['dnet']:+,.0f}  ضرر=${best['gloss']:,.0f} "
              f"(مبنا ${base_gl:,.0f}, Δ${best['dgl']:+,.0f})")

        # walk-forward
        print(f"\n  Walk-forward چهار پنجره:")
        wf = []; all_pos = True
        for k in range(4):
            a = k * (n // 4); b = n if k == 3 else (k + 1) * (n // 4)
            seg = df.iloc[a:b].reset_index(drop=True)
            e = apply_second(seg, entries_brk1(seg), key, op, thr)
            st, _ = cap_net(seg, e); net = net_of(st)
            wf.append(float(net))
            if net <= 0: all_pos = False
            print(f"    W{k+1}: ${net:>+9,.0f}")

        neigh = [r for r in rows if r['key'] == key]
        n_improve = sum(1 for r in neigh if r['dnet'] >= 0 and r['dgl'] < 0)
        print(f"\n  Robustness: از {len(neigh)} آستانهٔ همسایه، {n_improve} تا هم‌زمان سود↑ و ضرر↓ "
              f"({'✅' if n_improve >= 2 else '⚠️'})")

        new_sq = best['net']
        new_total = RECORD_REST + new_sq
        print(f"\n  رکوردِ جدیدِ کل = بقیه ${RECORD_REST:,.0f} + Squeeze ${new_sq:,.0f} = ${new_total:,.0f}")
        print(f"  Δ نسبت به ${RECORD_TOTAL:,.0f} = ${new_total-RECORD_TOTAL:+,.0f}")
        verdict = all_pos and new_total > RECORD_TOTAL
        print(f"\n  {'✅✅ رکوردِ جدید تأیید شد!' if verdict else '⚠️ گیتِ نهایی ناموفق'}")
        out.update(best_filter=best, wf=wf, wf_all_pos=bool(all_pos),
                   robust=int(n_improve), new_squeeze=float(new_sq),
                   new_total=float(new_total), verdict=bool(verdict))

    with open(os.path.join(RESULTS, '_s138_squeeze_second_filter.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s138_squeeze_second_filter.json")


if __name__ == '__main__':
    main()
