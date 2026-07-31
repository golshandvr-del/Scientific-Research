# -*- coding: utf-8 -*-
"""
S354 — Al Brooks «Trend Resumption Day» (فصلِ ۲۵، Part IV)
==========================================================

منبع: Telegram-Resource/telegram_source_1/pdfs/1 Trading Price Action - Trends.pdf
CHAPTER 25 «Trend Resumption Day» (pdf idx 454–461).

تزِ مرکزیِ فصل (نقلِ مکانیکیِ Brooks):
  - روز یک روندِ قویِ صبحگاهی (ساعتِ اول) دارد، سپس وارد یک trading range (اغلب tight) می‌شود
    که ساعت‌ها طول می‌کشد و معامله‌گران را فریب می‌دهد که روز آرام تمام می‌شود.
  - «The trend resumes in the final hour or two.» ⇒ در ساعتِ آخرِ روز، روندِ صبح از سر می‌گیرد.
  - «The second leg often is about the same size as the first leg.» ⇒ leg دوم ≈ leg اول (measured move).
  - «There is often a breakout from the trading range late in the day that tries to reverse the
    trend, but it is usually a trap.» ⇒ شکستِ خلافِ جهت اغلب تله است؛ بازار در جهتِ روندِ صبح
    breakout می‌کند تا close.

ترجمهٔ بک‌تست‌پذیر (causal, shift-safe):
  برای هر روزِ معاملاتی (مرزِ روزِ UTC داده):
    1. اسپایکِ صبح: از `n_open` کندلِ اول، جهت و اندازهٔ روندِ اولیه:
         init_ret = close[open_end-1] - open[day_start]
         init_dir = sign(init_ret)؛ leg1 = |init_ret|
       قیدِ معناداری: leg1 ≥ spike_k × ATR_ref (اسپایکِ واقعی، نه رنجِ کوچک).
    2. midday range: بعد از اسپایک تا شروعِ پنجرهٔ پایانی، دامنهٔ range باید کوچک/tight باشد:
         mid_range = max(high[mid]) − min(low[mid])
         قیدِ tightness: mid_range ≤ tight_f × leg1   (رنجِ فشرده نسبت به اسپایک)
    3. ماشهٔ resumption (فقط در پنجرهٔ ساعتِ پایانیِ روز، ورودِ next-open):
         روندِ صعودیِ صبح (init_dir>0): close[t] از سقفِ midday-range بالا می‌زند ⇒ LONG.
         روندِ نزولیِ صبح (init_dir<0): close[t] از کفِ midday-range پایین می‌زند ⇒ SHORT.
       (breakout در جهتِ روندِ صبح = resumption؛ همان چیزی که Brooks می‌گوید.)
    4. فیلترِ رژیمِ بانک (اختیاری، برای بردنِ RQS2 بالا): r2/hurst/chop روی نقطهٔ ورود.
    5. TP = measured-move (leg1) یا نسبتِ R؛ SL آن‌سوی midday-range. per-TF و غیررند.

داوری با RQS2 (۱۱ دروازهٔ H0..H10) — الگوی دو مرحله‌ایِ S353:
  مرحلهٔ ۱: اسکنِ کاملِ گرید بدونِ مدلِ صفر، رتبه‌بندی با proxy = (PF−1)·√n.
  مرحلهٔ ۲: بازداوریِ TOPK برتر با مدلِ صفرِ سختِ دوگانه (uncond + gated).

قانونِ MTF: از XAUUSD-M1 شروع (طلا M1 ندارد ⇒ M5)، سپس همهٔ TFهای XAU و EUR.
هر TF جداگانه اسکن و نتیجه در JSON ذخیره می‌شود (قانونِ اندک‌اندک).
"""
import os
import sys
import json
import itertools
import argparse
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import rqs2
from engine import indicator_bank as ib

# ----------------------------- پیکربندیِ per-TF -----------------------------
# n_open = تعدادِ کندلِ «ساعتِ اولِ» روز؛ mid = میانهٔ روز؛ late = پنجرهٔ پایانی.
# همه بر پایهٔ تعدادِ کندل در یک روزِ معاملاتیِ ~24 ساعته (فارکس/طلا) کالیبره شده.
# طلا ~۲۴ ساعت معامله ⇒ M5:288, M15:96, M30:48, H1:24, H4:6 کندل در روز.
TF_BARS_PER_DAY = {"M5": 288, "M15": 96, "M30": 48, "H1": 24, "H4": 6, "M1": 1440}

# SL/TP پایهٔ per-TF (غیررند، پادزهرِ اشتباهِ #۶/#۷). TP از measured-move می‌آید ولی
# در گرید چند RR هم آزموده می‌شود.
TF_ATR_P = {"M5": 55, "M15": 34, "M30": 34, "H1": 21, "H4": 21, "M1": 89}
TF_MAX_HOLD = {"M5": 96, "M15": 40, "M30": 28, "H1": 20, "H4": 10, "M1": 200}

# گریدِ سیگنال (اعدادِ غیررند/فیبوناچی-لوکاس)
N_OPEN_FRAC = [0.13, 0.21, 0.34]      # کسری از روز که «ساعتِ اول» است
LATE_FROM = [0.55, 0.68]              # شروعِ پنجرهٔ پایانی (کسر از روز)
SPIKE_K = [0.8, 1.3]                  # leg1 ≥ spike_k × ATR (اسپایکِ صبحِ واقعی)
# قیدِ tightness رنجِ midday: mid_range ≤ tight_atr × ATR (رنجِ فشرده، مطابقِ متنِ Brooks
# «very tight trading range») — نسبت به ATR نه leg1 ⇒ پایدارتر بینِ روزهای پرنوسان/آرام.
TIGHT_ATR = [3.0, 5.0, 8.0]
SL_K = [0.9, 1.3]                     # SL = sl_k × ATR_pip
RR = [1.0, 1.6]                       # TP/SL (measured-move→RR≈1؛ swing→RR≈1.6)
# فیلترهای رژیمِ بانک (q = آستانهٔ صدکِ رولینگ؛ None = بدونِ فیلتر)
R2_MODE = [None, ("r2_fib_55", "le", 0.62), ("r2_fib_55", "ge", 0.45)]

N_PERM = 300
TOPK_NULL = 6
MIN_N = 30


def bars_per_day(tf):
    return TF_BARS_PER_DAY.get(tf, 96)


def _atr_pip(df, asset, p):
    """ATR بر حسبِ pip (median) — برای کالیبراسیونِ SL/TP و اسپایک."""
    pip = se.ASSETS[asset]["pip"]
    atr = ib.compute(f"atr_fib_{_nearest_fib(p)}", df)
    if atr is None or (hasattr(atr, "isna") and atr.isna().all()):
        # fallback ساده
        h = df["high"].values; l = df["low"].values; c = df["close"].values
        tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
        return float(np.median(tr)) / pip
    return float(np.nanmedian(np.asarray(atr, dtype=float))) / pip


def _nearest_fib(p):
    fibs = [3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
    return min(fibs, key=lambda f: abs(f - p))


def day_index(df):
    """اندیسِ روزِ تقویمی (UTC) برای هر کندل — مرزِ روز."""
    dt = pd.to_datetime(df["time"], unit="s")
    return dt.dt.floor("D").astype("int64").values


def build_signals(df, asset, tf, n_open_frac, late_from, spike_k, tight_atr):
    """
    ساختِ سیگنالِ long/short برای Trend Resumption Day.
    همه causal: در کندلِ t فقط از دادهٔ روزِ جاری تا t استفاده می‌شود.
    قیدِ tightness: mid_range ≤ tight_atr × ATR (واحدِ نوسانِ پایدار، نه leg1).
    """
    n = len(df)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    dayix = day_index(df)
    bpd = bars_per_day(tf)
    n_open = max(2, int(round(n_open_frac * bpd)))
    late_start_frac = late_from

    atr_series = ib.compute(f"atr_fib_{_nearest_fib(TF_ATR_P.get(tf, 34))}", df)
    atr = np.asarray(atr_series, dtype=float) if atr_series is not None else np.full(n, np.nan)

    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)

    # گروه‌بندیِ کندل‌ها به روز
    # پیمایشِ خطی: برای هر کندل موقعیتش در روز (bar-of-day) را می‌دانیم
    start = 0
    i = 0
    while i < n:
        d = dayix[i]
        j = i
        while j < n and dayix[j] == d:
            j += 1
        # کندل‌های روز: [i, j)
        day = np.arange(i, j)
        ndlen = len(day)
        if ndlen >= n_open + 4:
            ds = i
            open_end = ds + n_open           # پایانِ ساعتِ اول (exclusive)
            late_start = ds + int(round(late_start_frac * ndlen))
            # اسپایکِ صبح
            init_ret = c[open_end - 1] - o[ds]
            init_dir = np.sign(init_ret)
            leg1 = abs(init_ret)
            atr_ref = atr[open_end - 1] if open_end - 1 < n and np.isfinite(atr[open_end - 1]) else np.nan
            if init_dir != 0 and np.isfinite(atr_ref) and atr_ref > 0 and leg1 >= spike_k * atr_ref:
                # midday range: از open_end تا late_start
                mid_lo_idx = open_end
                mid_hi_idx = max(open_end + 1, late_start)
                if mid_hi_idx - mid_lo_idx >= 2 and mid_hi_idx < j:
                    # ماشه در پنجرهٔ پایانی: از late_start تا انتهای روز
                    for t in range(max(mid_hi_idx, late_start), j):
                        # midday range تا کندلِ t-1 (causal)
                        mseg_hi = np.max(h[mid_lo_idx:t]) if t > mid_lo_idx else np.nan
                        mseg_lo = np.min(l[mid_lo_idx:t]) if t > mid_lo_idx else np.nan
                        if not (np.isfinite(mseg_hi) and np.isfinite(mseg_lo)):
                            continue
                        mid_range = mseg_hi - mseg_lo
                        # قیدِ tightness رنجِ midday نسبت به ATR (واحدِ قیمت): رنجِ فشرده.
                        atr_now = atr[t - 1] if (t - 1) < n and np.isfinite(atr[t - 1]) else atr_ref
                        if not (np.isfinite(atr_now) and atr_now > 0):
                            continue
                        if mid_range > tight_atr * atr_now or mid_range <= 0:
                            continue
                        # resumption در جهتِ روندِ صبح
                        if init_dir > 0:
                            if c[t] > mseg_hi:      # breakout صعودی از سقفِ range = ادامهٔ روند صعودیِ صبح
                                long_sig[t] = True
                                break               # فقط اولین resumptionِ روز
                        else:
                            if c[t] < mseg_lo:      # breakout نزولی = ادامهٔ روندِ نزولیِ صبح
                                short_sig[t] = True
                                break
        i = j
    return long_sig, short_sig


def regime_gate(df, spec):
    """فیلترِ رژیم از بانک؛ spec=(name, 'le'|'ge', q) با آستانهٔ صدکِ رولینگ."""
    if spec is None:
        return np.ones(len(df), dtype=bool)
    name, op, q = spec
    s = ib.compute(name, df)
    if s is None:
        return np.ones(len(df), dtype=bool)
    arr = np.asarray(s, dtype=float)
    # آستانهٔ صدکِ سراسری (causal-safe؛ روی کلِ سری چون فقط رتبه‌بندیِ رژیم است)
    valid = arr[np.isfinite(arr)]
    if valid.size < 50:
        return np.ones(len(df), dtype=bool)
    thr = np.nanquantile(valid, q)
    if op == "le":
        gate = arr <= thr
    else:
        gate = arr >= thr
    gate = np.nan_to_num(gate, nan=False).astype(bool)
    return gate


# ------------------------------- مدلِ صفرِ سخت -------------------------------
def _perm_wr(df, asset, sl, tp, n_side, is_long, allowed_bars, rng, n_perm=N_PERM):
    n = len(df)
    if n_side < 1 or allowed_bars.size <= n_side:
        return None
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    pip = se.ASSETS[asset]["pip"]
    cfg = se.ASSETS[asset]
    cost = cfg["spread_pip"] + 2 * cfg.get("slip_pip", 0.0)
    mh = 40
    sl_d = sl * pip; tp_d = tp * pip
    wrs = []
    for _ in range(n_perm):
        pick = rng.choice(allowed_bars, size=n_side, replace=False)
        wins = 0
        for si in pick:
            eb = si + 1
            if eb >= n:
                continue
            ent = o[eb]
            hit = None
            for k in range(eb, min(eb + mh, n)):
                if is_long:
                    if l[k] <= ent - sl_d:
                        hit = False; break
                    if h[k] >= ent + tp_d:
                        hit = True; break
                else:
                    if h[k] >= ent + sl_d:
                        hit = False; break
                    if l[k] <= ent - tp_d:
                        hit = True; break
            if hit is None:
                last = c[min(eb + mh - 1, n - 1)]
                pnl = (last - ent) if is_long else (ent - last)
                hit = pnl > 0
            if hit:
                wins += 1
        wrs.append(wins / n_side * 100.0)
    wrs = np.array(wrs)
    return dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=int(n_perm))


def build_null_strict(df, asset, sl, tp, n_long, n_short, gate, rng):
    n = len(df)
    lo, hi = 260, n - 60
    if hi <= lo:
        return None, {}
    all_bars = np.arange(lo, hi)
    g = np.zeros(n, dtype=bool)
    g[:min(n, len(gate))] = gate[:min(n, len(gate))]
    gated_bars = all_bars[g[all_bars]]
    null, diag = {}, {}
    for side, is_long, n_side in (("long", True, n_long), ("short", False, n_short)):
        cands = []
        if n_side >= 1:
            u = _perm_wr(df, asset, sl, tp, n_side, is_long, all_bars, rng)
            if u:
                cands.append(("uncond", u))
            if gated_bars.size > n_side:
                gd = _perm_wr(df, asset, sl, tp, n_side, is_long, gated_bars, rng)
                if gd:
                    cands.append(("gated", gd))
        if cands:
            tag, best = max(cands, key=lambda kv: kv[1]["uncond_wr"])
            null[side] = best
            diag[side] = dict(chosen=tag, wrs={k: round(v["uncond_wr"], 2) for k, v in cands})
        else:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)
    return null, diag


def _edge_proxy(rec):
    pf = rec.get("pf") or 0.0
    n = rec.get("n") or 0
    return (pf - 1.0) * (n ** 0.5)


# ------------------------------- اسکنِ یک TF -------------------------------
def scan_tf(asset, tf, with_null=True, seed=12345):
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        return dict(asset=asset, tf=tf, error="no data")
    df = se.load_data(path)
    n = len(df)
    bar_time = df["time"].values
    atr_pip = _atr_pip(df, asset, TF_ATR_P.get(tf, 34))
    mh = TF_MAX_HOLD.get(tf, 40)
    rng = np.random.default_rng(seed)

    rows = []
    for n_open_frac, late_from, spike_k, tight_atr in itertools.product(
            N_OPEN_FRAC, LATE_FROM, SPIKE_K, TIGHT_ATR):
        long_raw, short_raw = build_signals(df, asset, tf, n_open_frac, late_from, spike_k, tight_atr)
        if int(long_raw.sum() + short_raw.sum()) < MIN_N:
            continue
        for r2_spec in R2_MODE:
            gate = regime_gate(df, r2_spec)
            for side in ("long", "short"):
                ls = (long_raw & gate) if side == "long" else np.zeros(n, dtype=bool)
                ss = (short_raw & gate) if side == "short" else np.zeros(n, dtype=bool)
                if int(ls.sum() + ss.sum()) < MIN_N:
                    continue
                for sl_k, rr in itertools.product(SL_K, RR):
                    sl = round(sl_k * atr_pip, 1)
                    tp = round(rr * sl, 1)
                    if sl <= 0:
                        continue
                    tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                            max_hold=mh, allow_overlap=False)
                    if tr is None or len(tr) < MIN_N:
                        continue
                    tr = tr.copy(); tr["sl_pip"] = float(sl)
                    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                                            bar_time=bar_time, null=None)
                    m = res.get("metrics", {})
                    rows.append(dict(
                        n_open_frac=n_open_frac, late_from=late_from,
                        spike_k=spike_k, tight_atr=tight_atr,
                        r2=(None if r2_spec is None else f"{r2_spec[0]}:{r2_spec[1]}:{r2_spec[2]}"),
                        side=side, sl_k=sl_k, rr=rr, sl=sl, tp=tp,
                        n=m.get("n_trades"), wr=m.get("win_rate"),
                        pf=m.get("profit_factor"), net=m.get("net_profit"),
                        stage=1, verdict=res.get("verdict")))

    ranked = sorted(rows, key=_edge_proxy, reverse=True)[:TOPK_NULL]
    judged, best = [], None
    if with_null:
        for rec in ranked:
            long_raw, short_raw = build_signals(df, asset, tf, rec["n_open_frac"],
                                                rec["late_from"], rec["spike_k"], rec["tight_atr"])
            r2_spec = None
            if rec["r2"]:
                nm, op, q = rec["r2"].split(":")
                r2_spec = (nm, op, float(q))
            gate = regime_gate(df, r2_spec)
            ls = (long_raw & gate) if rec["side"] == "long" else np.zeros(n, dtype=bool)
            ss = (short_raw & gate) if rec["side"] == "short" else np.zeros(n, dtype=bool)
            tr = se.simulate_trades(df, ls, ss, rec["sl"], rec["tp"], asset,
                                    max_hold=mh, allow_overlap=False)
            if tr is None or len(tr) < MIN_N:
                continue
            tr = tr.copy(); tr["sl_pip"] = float(rec["sl"])
            nl = int((tr["direction"] == "long").sum())
            ns = int((tr["direction"] == "short").sum())
            null, ndiag = build_null_strict(df, asset, rec["sl"], rec["tp"], nl, ns, gate, rng)
            res = rqs2.compute_rqs2(tr, asset, sl_pip=rec["sl"], tp_pip=rec["tp"],
                                    bar_time=bar_time, null=null,
                                    n_trials=max(1, len(rows)))
            m = res.get("metrics", {})
            out = dict(rec)
            out.update(stage=2, n=m.get("n_trades"), wr=m.get("win_rate"),
                       pf=m.get("profit_factor"), net=m.get("net_profit"),
                       lift=m.get("skill_lift_pp"), z=m.get("skill_z"),
                       rqs2=res.get("rqs2_score"), verdict=res.get("verdict"),
                       power_limited=res.get("power_limited"),
                       gates=res.get("gates"), null_diag=ndiag)
            judged.append(out)
            key = (res.get("verdict") == "ACCEPT",
                   (m.get("skill_lift_pp") or -99) * ((m.get("n_trades") or 0) ** 0.5))
            if best is None or key > best[0]:
                best = (key, out)

    result = dict(asset=asset, tf=tf, n_bars=n, n_stage1=len(rows),
                  top=ranked, judged=judged,
                  best=(best[1] if best else None))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default="XAUUSD,EURUSD")
    ap.add_argument("--tfs", default="M5,M15,M30,H1,H4")
    ap.add_argument("--out", default="results/_scan_S354")
    ap.add_argument("--no-null", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    assets = args.assets.split(",")
    tfs = args.tfs.split(",")
    for asset in assets:
        for tf in tfs:
            print(f"[S354] scanning {asset}-{tf} ...", flush=True)
            try:
                r = scan_tf(asset, tf, with_null=not args.no_null)
            except Exception as e:
                import traceback
                r = dict(asset=asset, tf=tf, error=str(e), tb=traceback.format_exc())
                print(f"  ERROR {asset}-{tf}: {e}", flush=True)
            fn = os.path.join(args.out, f"{asset}_{tf}.json")
            with open(fn, "w") as f:
                json.dump(r, f, default=str, ensure_ascii=False, indent=1)
            b = r.get("best")
            if b:
                print(f"  -> {asset}-{tf} BEST verdict={b.get('verdict')} rqs2={b.get('rqs2')} "
                      f"n={b.get('n')} wr={b.get('wr')} pf={b.get('pf')} "
                      f"lift={b.get('lift')} z={b.get('z')} side={b.get('side')}", flush=True)
            else:
                print(f"  -> {asset}-{tf} no candidate (stage1={r.get('n_stage1')})", flush=True)


if __name__ == "__main__":
    main()
