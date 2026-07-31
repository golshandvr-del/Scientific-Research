# -*- coding: utf-8 -*-
"""
S353 — HalfTrend flip + **دروازهٔ رژیمِ روند** (r2 · hurst · entropy)
================================================================================
منبعِ الهام: `Telegram-Resource/telegram_source_1/+++AgimatPro 2020 (2)/`
(HalfTrend + Heiken Ashi). لایهٔ خامِ آن = S166.

مسئله‌ای که این لایه حل می‌کند
--------------------------------------------------------------------------------
اسکنِ MTFِ S166 یک **نردبانِ فراکتالیِ یکنواخت** کشف کرد: PF با بالا رفتنِ تایم‌فریم
یکنواخت صعود می‌کند (طلا: 0.63 در M5 → 1.02 در D1 → 1.28 در W1؛ یورو: 0.25 → 1.09).
علتِ ریاضی روشن است: flipِ HalfTrend در TFِ پایین **زیادی** شلیک می‌کند (۲۳۰۰۰ معامله
روی M5) و اسپرد را روی هر معامله می‌پردازد؛ در TFِ بالا روندها تمیزتر و شلیک‌ها کمترند.

اما تشخیصِ ۱۱-گیت نشان داد `XAUUSD-D1` (sl_k=2) یک لبهٔ **POWER-LIMITED** است:
همهٔ گیت‌های اقتصادی پاس (PF=1.32، net=+$4584، H4 هر دو سمت سالم)، lift=+2.43 مثبت،
ولی z=0.91 ⇒ H3 رد. یعنی «لبه هست، اثباتش نمونه/کیفیت کم دارد».

راهبردِ بهبود (قانونِ دومِ پروژه)
--------------------------------------------------------------------------------
برای پاس‌کردنِ H3 باید `lift ≥ 4.0pp` و `z ≥ 3.0` شود. چون `z ≈ lift/perm_sd` و
`perm_sd ∝ 1/√n`، فیلتر کردن **باید lift را سریع‌تر از افتِ √n بالا ببرد**؛ یعنی
کمیتِ هدف `lift·√n` است، نه فقط lift.

فیلترها از بانکِ ۴۰۱ اندیکاتور و مطابقِ `docs/indicators/statistical.md` انتخاب شدند —
همان دو ابزاری که سندِ بانک صریحاً «کلیدِ احیای S332» می‌نامد:
  • `r2`      قدرتِ خطی‌بودنِ روند (چند درصدِ حرکت را یک خطِ راست توضیح می‌دهد)
  • `hurst`   حافظهٔ بلندمدت: H>0.5 پایدار/روندی، H<0.5 بازگشتی
  • `entropy` آنتروپیِ شانونِ بازده: آنتروپیِ پایین = ساختارِ قابلِ استخراج
منطق: HalfTrend یک لایهٔ **روند-دنبال‌کن** است؛ پس فقط در رژیمِ «روندیِ ساختارمند»
اجازهٔ ورود دارد. این پادزهرِ مستقیمِ over-tradingِ کشف‌شده است.

قانونِ «شاید همه چیز شناور است»
--------------------------------------------------------------------------------
آستانه‌ها **عدد ثابت نیستند**؛ *درصدکِ متحرک* روی پنجرهٔ `PCT_WIN` هستند. یعنی
«r2 در بالاترین ۳۵٪ِ ۲۳۳ کندلِ اخیرِ خودش» — پس دروازه با رژیمِ هر تایم‌فریم و هر
دورهٔ بازار **خودکالیبره** می‌شود و به عددِ رندِ جهانی وابسته نیست.

ضدِ اشتباهاتِ رایج
--------------------------------------------------------------------------------
#۱: فیلتر زمان‌محور نیست، آماری/فراکتالی است.
#۳: از بانک استفاده شد (r2/hurst/entropy)، نه MA سادهٔ تکراری.
#۵: هر ۷ تایم‌فریم × ۲ دارایی آزموده می‌شود (قانونِ MTF).
#۶: SL/TP کسری از **ATRِ همان تایم‌فریم** است، نه پیپِ ثابتِ مشترک.
#۷: دوره‌ها غیررندند: r2∈{29,43,61}، hurst∈{55,89}، entropy∈{34}، درصدک‌ها ۳۵/۵۰/۶۵.
#۸: TP≥SL (rr≥1) نگه داشته می‌شود؛ هیچ تلاشی برای تورمِ WR با TP<SL نمی‌شود.

مدلِ صفرِ **دوگانه** (سختگیرانه‌ترین انتخاب)
--------------------------------------------------------------------------------
تلهٔ W1 در S166 نشان داد اگر مدلِ صفر ضعیف باشد فریب می‌خوریم: روی W1 طلا PF=1.63
بود ولی lift **منفی** — چون طلا در نمونه صعودی بود و هر ورودِ لانگِ تصادفی برنده
می‌شد. برای اینکه دروازهٔ رژیم همان تله را دوباره نسازد (دروازه ممکن است صرفاً
«دوره‌های صعودی» را انتخاب کند)، دو مدلِ صفر ساخته می‌شود:
  null_uncond : ورودِ تصادفی در هر بارِ مجاز
  null_gated  : ورودِ تصادفی **فقط در بارهایی که دروازه باز است**
و **قوی‌ترِ آن دو** (WRِ مرجعِ بالاتر) به RQS2 داده می‌شود. پس H3 می‌پرسد:
«آیا سیگنالِ HalfTrend چیزی بیش از خودِ دروازه اضافه می‌کند؟» — این دقیقاً همان
سختگیریِ لازم است و هیچ آستانه‌ای هم شل نمی‌شود.

خروجی: `results/_scan_S353/<asset>_<tf>.json` (یکی به‌ازای هر کارت، چک‌پوینت‌شده).
"""
import os
import sys
import json
import itertools
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs2
from engine import indicator_bank as ib
from strategies.s166_halftrend_heikenashi import signals

OUTDIR = os.path.join(ROOT, "results", "_scan_S353")
os.makedirs(OUTDIR, exist_ok=True)

CAPITAL = 10_000.0

# پایه‌های دارایی — دقیقاً مطابقِ موتورِ رسمی se.ASSETS.
ASSET_BASE = {
    "XAUUSD": dict(pip=0.10, contract=100.0, pip_value=10.0,
                   spread_pip=3.3, comm=0.0, slip_pip=0.0),
    "EURUSD": dict(pip=0.0001, contract=100_000.0, pip_value=10.0,
                   spread_pip=1.0, comm=0.0, slip_pip=0.3),
}
TFS = ["M5", "M15", "M30", "H1", "H4", "D1", "W1"]

# ---------------------------- شبکهٔ پارامتری (غیررند) ----------------------------
SL_K = [1.5, 2.0]          # ضریبِ ATR برای SL (بهترین‌های S166)
RR = [1.0, 1.5]            # TP/SL — هرگز <۱ (ضدِ اشتباهِ #۸)
AMPL = [2, 3]
ATR_P = 100
MAX_HOLD = 24

R2_P = [29, 43, 61]        # دوره‌های غیررندِ r2
HURST_P = [55, 89]         # دوره‌های غیررندِ hurst
ENT_P = 34                 # دورهٔ آنتروپی
PCT_WIN = 233              # پنجرهٔ درصدکِ متحرک (خودکالیبره)
R2_Q = [0.35, 0.50, 0.65]  # کفِ درصدکِ r2 (بالاتر = روندی‌تر)
HURST_MIN = [0.50, 0.55]   # کفِ مطلقِ hurst (مرزِ نظریِ پایداری)
ENT_Q = [1.00, 0.65]       # سقفِ درصدکِ آنتروپی (1.00 = بی‌فیلتر)

N_PERM = 200
SEED = 7


def _load(asset, tf):
    return se.load_data(os.path.join(ROOT, "data", f"{asset}_{tf}.csv"))


def _register(asset, tf):
    se.ASSETS[asset] = dict(file=f"data/{asset}_{tf}.csv", **ASSET_BASE[asset])


def _atr_pip(df, asset, p=ATR_P):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(p).mean().values
    return float(np.nanmedian(atr) / ASSET_BASE[asset]["pip"])


def _pct_rank(s, win=PCT_WIN):
    """درصدکِ متحرکِ علّی: نسبتِ مقادیرِ پنجره که ≤ مقدارِ جاری‌اند."""
    return s.rolling(win).apply(
        lambda w: float((w <= w[-1]).mean()), raw=True)


def build_regime(df, r2_p, hurst_p):
    """سری‌های رژیم + درصدک‌های متحرکِ آن‌ها (همه علّی)."""
    r2s = ib.r2(df, p=r2_p)
    hs = ib.hurst(df, p=hurst_p)
    ent = ib.entropy(df, p=ENT_P)
    return dict(r2=r2s, r2_pct=_pct_rank(r2s), hurst=hs,
                ent=ent, ent_pct=_pct_rank(ent))


def gate_mask(reg, r2_q, hurst_min, ent_q):
    """ماسکِ دروازهٔ رژیم؛ آستانه‌ها درصدکیِ خودکالیبره‌اند."""
    m = (reg["r2_pct"] >= r2_q).fillna(False).values
    m &= (reg["hurst"] >= hurst_min).fillna(False).values
    if ent_q < 1.0:
        m &= (reg["ent_pct"] <= ent_q).fillna(False).values
    return m


def _perm_wr(df, asset, sl, tp, n_side, is_long, allowed_bars, rng,
             n_perm=N_PERM):
    """WRِ جای‌گشتی: n_side ورودِ تصادفی از میانِ allowed_bars."""
    n = len(df)
    if n_side < 1 or allowed_bars.size <= n_side:
        return None
    wrs = []
    zero = np.zeros(n, dtype=bool)
    for _ in range(n_perm):
        bars = rng.choice(allowed_bars, size=n_side, replace=False)
        sig = np.zeros(n, dtype=bool)
        sig[bars] = True
        tr = se.simulate_trades(df, sig if is_long else zero,
                                zero if is_long else sig, sl, tp, asset,
                                max_hold=MAX_HOLD, allow_overlap=False)
        if tr is not None and len(tr) >= 1 and "outcome" in tr.columns:
            wrs.append(100.0 * float((tr["outcome"] == "win").mean()))
    if not wrs:
        return None
    a = np.asarray(wrs, dtype="float64")
    return dict(uncond_wr=float(a.mean()), perm_mean=float(a.mean()),
                perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()),
                perm_k=int(len(a)))


def build_null_strict(df, asset, sl, tp, n_long, n_short, gate, rng):
    """
    مدلِ صفرِ دوگانه: ورودِ تصادفی (الف) در همه‌جا (ب) فقط در بارهای دروازه‌باز.
    **قوی‌ترِ** آن دو (WRِ مرجعِ بالاتر) برگردانده می‌شود ⇒ سختگیرانه‌ترین H3.
    """
    n = len(df)
    lo, hi = 260, n - MAX_HOLD - 1
    if hi <= lo:
        return None, {}
    all_bars = np.arange(lo, hi)
    g = np.zeros(n, dtype=bool)
    g[:min(n, len(gate))] = gate[:min(n, len(gate))]
    gated_bars = all_bars[g[all_bars]]

    null, diag = {}, {}
    for side, is_long, n_side in (("long", True, n_long),
                                  ("short", False, n_short)):
        cands = []
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
            diag[side] = dict(chosen=tag,
                              wrs={k: round(v["uncond_wr"], 2)
                                   for k, v in cands})
        else:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)
    return null, diag


def run_card(asset, tf, with_null=True, verbose=True):
    df = _load(asset, tf)
    _register(asset, tf)
    atr_pip = _atr_pip(df, asset)
    n = len(df)
    rng = np.random.default_rng(SEED)

    rows, best = [], None
    for ampl, r2_p, hurst_p in itertools.product(AMPL, R2_P, HURST_P):
        long_raw, short_raw = signals(df, ampl, ATR_P, True)
        reg = build_regime(df, r2_p, hurst_p)
        for r2_q, h_min, e_q in itertools.product(R2_Q, HURST_MIN, ENT_Q):
            gate = gate_mask(reg, r2_q, h_min, e_q)
            for side in ("long", "short"):
                ls = (np.asarray(long_raw, dtype=bool) & gate) \
                    if side == "long" else np.zeros(n, dtype=bool)
                ss = (np.asarray(short_raw, dtype=bool) & gate) \
                    if side == "short" else np.zeros(n, dtype=bool)
                n_sig = int(ls.sum() + ss.sum())
                if n_sig < 30:
                    continue
                for sl_k, rr in itertools.product(SL_K, RR):
                    sl = round(sl_k * atr_pip, 1)
                    tp = round(rr * sl, 1)
                    tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                            max_hold=MAX_HOLD,
                                            allow_overlap=False)
                    if tr is None or len(tr) < 30:
                        continue
                    tr = tr.copy()
                    tr["sl_pip"] = float(sl)
                    nl = int((tr["direction"] == "long").sum())
                    ns = int((tr["direction"] == "short").sum())
                    null, ndiag = (build_null_strict(df, asset, sl, tp, nl, ns,
                                                     gate, rng)
                                   if with_null else (None, {}))
                    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                                            bar_time=df["dt"].values,
                                            null=null)
                    m = res.get("metrics", {})
                    lift = m.get("skill_lift_pp")
                    z = m.get("skill_z")
                    rec = dict(ampl=ampl, r2_p=r2_p, hurst_p=hurst_p,
                               r2_q=r2_q, hurst_min=h_min, ent_q=e_q,
                               side=side, sl_k=sl_k, rr=rr, sl=sl, tp=tp,
                               n=m.get("n_trades"), wr=m.get("win_rate"),
                               pf=m.get("profit_factor"),
                               net=m.get("net_profit"),
                               lift=lift, z=z, rqs2=res.get("score"),
                               verdict=res.get("verdict"),
                               power_limited=res.get("power_limited"),
                               gates=res.get("gates"),
                               gate_families=res.get("gate_families"),
                               null_diag=ndiag)
                    rows.append(rec)
                    # اولویت: ACCEPT > POWER-LIMITED > lift·√n بزرگ‌تر
                    key = (res.get("verdict") == "ACCEPT",
                           bool(res.get("power_limited")),
                           (lift or -99) * ((m.get("n_trades") or 0) ** 0.5))
                    if best is None or key > best[0]:
                        best = (key, rec)

    out = dict(asset=asset, tf=tf, atr_pip=round(atr_pip, 2),
               n_variants=len(rows),
               best=(best[1] if best else None), variants=rows)
    path = os.path.join(OUTDIR, f"{asset}_{tf}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    if verbose:
        b = out["best"]
        if b:
            print(f"[done] {asset}_{tf} | verdict={b['verdict']} "
                  f"PL={b['power_limited']} n={b['n']} WR={b['wr']} "
                  f"PF={b['pf']} lift={b['lift']} z={b['z']} "
                  f"side={b['side']} r2p={b['r2_p']}/q={b['r2_q']} "
                  f"H{b['hurst_p']}>{b['hurst_min']} entq={b['ent_q']} "
                  f"sl_k={b['sl_k']} rr={b['rr']}")
        else:
            print(f"[done] {asset}_{tf} | no variant reached 30 trades")
    return out


def main():
    args = sys.argv[1:]
    cards = []
    if args:
        for a in args:
            asset, tf = a.split("_")
            cards.append((asset, tf))
    else:
        for asset in ("XAUUSD", "EURUSD"):
            for tf in TFS:
                cards.append((asset, tf))
    for asset, tf in cards:
        print(f"[run] {asset}_{tf} ...", flush=True)
        try:
            run_card(asset, tf)
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] {asset}_{tf}: {exc}", flush=True)


if __name__ == "__main__":
    main()
