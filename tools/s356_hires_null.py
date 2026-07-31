# -*- coding: utf-8 -*-
"""
`S356` — حلِ مرزِ `p` با نالِ رزولوشن‌بالا (`K = 200_000` × ۳ seed)
==================================================================

پیش‌ثبت: `results/S356_PREREG_ADDENDUM_HIRES_NULL.md` (commitِ جدا، پیش از اجرا).

این ابزار **هیچ پارامترِ استراتژی را جست‌وجو یا تغییر نمی‌دهد**. تنها کاری که
می‌کند، اندازه‌گیریِ دقیق‌ترِ همان `p` تجربی است که در `K=2000` روی مرزِ `0.001`
نوسان می‌کرد. سیگنال‌ها، `SL`، `TP`، `max_hold` و رژیم، همه از
`strategies/s356_v24_rejudge.py` وارد می‌شوند — **بدونِ بازتعریف**، تا امکانِ
انحرافِ سهویِ منطق صفر شود.

## دو نمونه‌گیر و دلیلِ وجودِ هر دو

| نمونه‌گیر | الگوریتم | هزینهٔ هر قرعه | نقش |
|-----------|----------|----------------|------|
| `SLOW` | جای‌گشتِ کاملِ numpy (`shuffle=True`) | `O(|valid|) ≈ 6×10⁴` | مرجعِ بایگانی |
| `FAST` | انتخابِ Floyd (`shuffle=False`) | `O(k) = 117` | رزولوشن‌بالا |

`FAST` هم‌ارزِ **توزیعی** است نه هم‌ارزِ **جریانِ** اعدادِ تصادفی. پس قاعدهٔ `D2`
پیش‌ثبت‌شده اجرا می‌شود: مقایسهٔ میانگین، انحرافِ معیار و آزمونِ KS دو‌نمونه‌ای
روی `K=5000` مشترک. اگر `D2` رد شود، خروجی پرچمِ `sampler_valid=False` می‌خورد و
**حق ندارد** در حکم دخالت کند.

## قاعدهٔ تصمیمِ `D1` (پیش‌ثبت‌شده)

    پاس ⇐  p_upper(95%, Clopper–Pearson) ≤ 0.001

که همیشه از `p̂ ≤ 0.001` سخت‌گیرانه‌تر است، چون `p_upper > p̂` به‌طورِ اکید.

اجرا:
    python3 tools/s356_hires_null.py --card XAUUSD-H1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from strategies import s354_brooks_trend_resumption as base        # noqa: E402
from strategies.s354_causal_check import build_signals_causal      # noqa: E402
from strategies.s356_v24_rejudge import (                          # noqa: E402
    FROZEN, outcome_table, wr_of,
)

OUT = "results/_scan_S356"

# ───────────────── ثابت‌هایِ قفل‌شده در پیوستِ پیش‌ثبت ─────────────────
K_HI = 200_000          # قرعه به‌ازای هر seed
K_D2 = 5_000            # قرعه برای آزمونِ هم‌ارزیِ نمونه‌گیر
SEEDS = (23, 101, 777)  # همان سه seedِ سندِ اصلی — بدون اضافه/کم
P_BAR = 0.001           # خطِ قرمزِ اسپک
CONF = 0.95             # سطحِ اطمینانِ یک‌طرفه
D2_MEAN_TOL = 0.15      # درصدواحد
D2_SD_TOL = 0.15        # درصدواحد
D2_KS_MIN = 0.01


# ═══════════════════════════ برآوردگرهای آماری ═══════════════════════════
def clopper_pearson_upper(ge: int, k: int, conf: float = CONF) -> float:
    """کرانِ بالای یک‌طرفهٔ دقیقِ Clopper–Pearson برای نسبتِ دوجمله‌ای.

    `p_upper = BetaInv(conf ; ge+1 , k−ge)`.  برای `ge=k` مقدارِ ۱ برمی‌گرداند.
    این کران **دقیق** است (بر پایهٔ رابطهٔ دوجمله‌ای↔بتا) و برخلافِ تقریبِ نرمال
    در دُمِ توزیع با شمارشِ نادر معتبر می‌ماند.
    """
    if ge >= k:
        return 1.0
    return float(stats.beta.ppf(conf, ge + 1, k - ge))


def clopper_pearson_lower(ge: int, k: int, conf: float = CONF) -> float:
    """کرانِ پایینِ یک‌طرفهٔ متقارن — فقط برای گزارش، نه برای تصمیم."""
    if ge <= 0:
        return 0.0
    return float(stats.beta.ppf(1.0 - conf, ge, k - ge + 1))


def mc_point(ge: int, k: int) -> float:
    """برآوردگرِ محافظه‌کارانهٔ مونت‌کارلو `(1+ge)/(1+K)` (Davison & Hinkley 1997)."""
    return (1.0 + ge) / (1.0 + k)


# ═══════════════════════════ نمونه‌گیرها ═══════════════════════════
def draws_slow(valid, k, res, xbar, k_perm, seed):
    """مرجعِ بایگانی: جای‌گشتِ کاملِ numpy برای هر قرعه (`shuffle=True`)."""
    rng = np.random.default_rng(seed)
    out = np.empty(k_perm, dtype=float)
    got = 0
    for _ in range(k_perm):
        pick = np.sort(rng.choice(valid, size=min(k, valid.size), replace=False))
        w = wr_of(pick, res, xbar)
        if w is not None:
            out[got] = w
            got += 1
    return out[:got]


def draws_fast(valid, k, res, xbar, k_perm, seed, progress=None):
    """رزولوشن‌بالا: انتخابِ Floyd (`shuffle=False`) — `O(k)` به‌جای `O(|valid|)`.

    توزیعِ زیرمجموعه یکنواخت و یکسان با `draws_slow` است؛ تنها دنبالهٔ اعدادِ
    تصادفی متفاوت است. اعتبارش با قاعدهٔ `D2` سنجیده می‌شود.
    """
    rng = np.random.default_rng(seed)
    m = min(k, valid.size)
    out = np.empty(k_perm, dtype=float)
    got = 0
    for i in range(k_perm):
        pick = np.sort(rng.choice(valid, size=m, replace=False, shuffle=False))
        w = wr_of(pick, res, xbar)
        if w is not None:
            out[got] = w
            got += 1
        if progress and (i + 1) % progress == 0:
            print(f"      … {i + 1:,}/{k_perm:,} قرعه", flush=True)
    return out[:got]


# ═══════════════════════════ بازسازیِ کارت ═══════════════════════════
def rebuild_card(card):
    """بازسازیِ عینِ `S356` — همان توابع، همان ثابت‌ها، بدونِ بازتعریف."""
    asset, tf = card.split("-")
    path = os.path.join("data", f"{asset}_{tf}.csv")
    if not os.path.exists(path):
        raise SystemExit(f"داده نیست: {path}")
    df = se.load_data(path)

    atr_pip = base._atr_pip(df, asset, base.TF_ATR_P.get(tf, 34))
    mh = base.TF_MAX_HOLD.get(tf, 20)
    sl = round(FROZEN["sl_k"] * atr_pip, 1)
    tp = round(FROZEN["rr"] * sl, 1)

    gate = base.regime_gate(df, FROZEN["regime"])
    sig = build_signals_causal(df, asset, tf, FROZEN["n_open_frac"],
                               FROZEN["late_hour"], FROZEN["spike_k"],
                               FROZEN["tight_atr"], sl, tp, mh) & gate

    res, xbar = outcome_table(df, asset, sl, tp, mh)
    n = len(df)
    valid = np.arange(260, n - mh - 2)
    valid = valid[res[valid] != 0]

    picks = np.flatnonzero(np.asarray(sig))
    wr_obs = wr_of(picks, res, xbar)
    k = int(np.asarray(sig).sum())
    uncond = wr_of(valid, res, xbar)
    return dict(df=df, asset=asset, tf=tf, sl=sl, tp=tp, mh=mh,
                res=res, xbar=xbar, valid=valid, k=k,
                wr_obs=wr_obs, uncond=uncond)


# ═════════════════════════════════ اجرا ═════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", default="XAUUSD-H1")
    ap.add_argument("--k", type=int, default=K_HI)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    C = rebuild_card(a.card)
    print(f"\n=== {a.card} :: SL={C['sl']}pip TP={C['tp']}pip mh={C['mh']} "
          f"n={C['k']} WR_obs={C['wr_obs']:.2f} WR_uncond={C['uncond']:.2f} "
          f"|valid|={C['valid'].size:,}", flush=True)

    rec = dict(card=a.card, sl_pip=C["sl"], tp_pip=C["tp"], max_hold=C["mh"],
               n_trades=C["k"], wr_obs=round(C["wr_obs"], 4),
               wr_uncond=round(C["uncond"], 4),
               lift=round(C["wr_obs"] - C["uncond"], 4),
               valid_pool=int(C["valid"].size),
               k_hi=a.k, seeds=list(SEEDS), p_bar=P_BAR, conf=CONF,
               prereg="results/S356_PREREG_ADDENDUM_HIRES_NULL.md")

    # ── قاعدهٔ D2: اعتبارسنجیِ نمونه‌گیرِ سریع ──
    print(f"\n  [D2] اعتبارسنجیِ نمونه‌گیر — SLOW vs FAST، K={K_D2:,}, seed=23",
          flush=True)
    t0 = time.time()
    d_slow = draws_slow(C["valid"], C["k"], C["res"], C["xbar"], K_D2, 23)
    t_slow = time.time() - t0
    t0 = time.time()
    d_fast = draws_fast(C["valid"], C["k"], C["res"], C["xbar"], K_D2, 23)
    t_fast = time.time() - t0

    ks = stats.ks_2samp(d_slow, d_fast)
    dmean = abs(float(d_fast.mean()) - float(d_slow.mean()))
    dsd = abs(float(d_fast.std(ddof=1)) - float(d_slow.std(ddof=1)))
    d2_ok = (dmean <= D2_MEAN_TOL and dsd <= D2_SD_TOL
             and float(ks.pvalue) >= D2_KS_MIN)
    rec["D2"] = dict(
        k=K_D2, seed=23,
        slow=dict(mean=round(float(d_slow.mean()), 4),
                  sd=round(float(d_slow.std(ddof=1)), 4),
                  max=round(float(d_slow.max()), 4), secs=round(t_slow, 1)),
        fast=dict(mean=round(float(d_fast.mean()), 4),
                  sd=round(float(d_fast.std(ddof=1)), 4),
                  max=round(float(d_fast.max()), 4), secs=round(t_fast, 1)),
        d_mean=round(dmean, 4), d_sd=round(dsd, 4),
        ks_stat=round(float(ks.statistic), 5), ks_p=round(float(ks.pvalue), 5),
        tol=dict(mean=D2_MEAN_TOL, sd=D2_SD_TOL, ks_p=D2_KS_MIN),
        sampler_valid=bool(d2_ok),
    )
    print(f"      SLOW  mean={d_slow.mean():.3f} sd={d_slow.std(ddof=1):.3f} "
          f"max={d_slow.max():.2f}  ({t_slow:.1f}s)", flush=True)
    print(f"      FAST  mean={d_fast.mean():.3f} sd={d_fast.std(ddof=1):.3f} "
          f"max={d_fast.max():.2f}  ({t_fast:.1f}s)  →  شتاب ×{t_slow / max(t_fast, 1e-9):.0f}",
          flush=True)
    print(f"      Δmean={dmean:.4f} (≤{D2_MEAN_TOL})  Δsd={dsd:.4f} "
          f"(≤{D2_SD_TOL})  KS p={ks.pvalue:.4f} (≥{D2_KS_MIN})",
          flush=True)
    print(f"      →  sampler_valid = {d2_ok}", flush=True)

    with open(os.path.join(OUT, f"{a.card}_hires_null.json"), "w") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)

    if not d2_ok:
        rec["decision"] = dict(rule="D1", verdict="SAMPLER_INVALID",
                               note="قاعدهٔ D2 رد شد؛ نالِ سریع حق دخالت در حکم ندارد.")
        with open(os.path.join(OUT, f"{a.card}_hires_null.json"), "w") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        print("\n  ⛔ D2 رد شد — توقف طبقِ پیش‌ثبت.", flush=True)
        return 0

    # ── نالِ رزولوشن‌بالا ──
    per_seed = {}
    for sd_ in SEEDS:
        print(f"\n  [HI] seed={sd_}  K={a.k:,}", flush=True)
        t0 = time.time()
        d = draws_fast(C["valid"], C["k"], C["res"], C["xbar"], a.k, sd_,
                       progress=max(a.k // 5, 1))
        el = time.time() - t0
        ge = int((d >= C["wr_obs"] - 1e-12).sum())
        kk = int(d.size)
        p_hat = mc_point(ge, kk)
        p_up = clopper_pearson_upper(ge, kk)
        p_lo = clopper_pearson_lower(ge, kk)
        z = (C["wr_obs"] - float(d.mean())) / float(d.std(ddof=1))
        ok = bool(p_up <= P_BAR)
        per_seed[str(sd_)] = dict(
            k=kk, ge=ge, p_hat=round(p_hat, 8),
            p_upper95=round(p_up, 8), p_lower95=round(p_lo, 8),
            perm_mean=round(float(d.mean()), 4),
            perm_sd=round(float(d.std(ddof=1)), 4),
            perm_max=round(float(d.max()), 4),
            perm_q999=round(float(np.quantile(d, 0.999)), 4),
            skill_z=round(float(z), 4), D1_pass=ok, secs=round(el, 1),
        )
        print(f"      ge={ge}/{kk:,}  p̂={p_hat:.6f}  "
              f"CI95=[{p_lo:.6f}, {p_up:.6f}]", flush=True)
        print(f"      perm: mean={d.mean():.3f} sd={d.std(ddof=1):.3f} "
              f"q99.9={np.quantile(d, 0.999):.2f} max={d.max():.2f}  z={z:.3f}",
              flush=True)
        print(f"      →  D1 (p_upper ≤ {P_BAR}) = {ok}   ({el:.0f}s)", flush=True)

        rec["per_seed"] = per_seed
        with open(os.path.join(OUT, f"{a.card}_hires_null.json"), "w") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)

    # ── تصمیمِ نهایی طبقِ پیش‌ثبت ──
    passes = [v["D1_pass"] for v in per_seed.values()]
    hats = [v["p_hat"] for v in per_seed.values()]
    spread = max(hats) - min(hats)
    if all(passes):
        verdict = "D1_PASS"
    elif not any(passes):
        verdict = "D1_FAIL"
    else:
        verdict = "D1_INCONSISTENT_ON_BOUNDARY"   # ⇒ محافظه‌کارانه = DEAD
    rec["decision"] = dict(
        rule="D1", verdict=verdict,
        all_seeds_pass=bool(all(passes)),
        p_hat_spread=round(spread, 8),
        P4_resolution_confirmed=bool(spread < 0.0002),
        note=("پاس در هر سه seed" if verdict == "D1_PASS" else
              "رد در هر سه seed" if verdict == "D1_FAIL" else
              "ناهمگونیِ مرزی ⇒ طبقِ پیش‌ثبت محافظه‌کارانه DEAD"),
    )
    with open(os.path.join(OUT, f"{a.card}_hires_null.json"), "w") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)

    print(f"\n  ══ تصمیمِ D1: {verdict}   (پراکندگیِ p̂ = {spread:.6f}, "
          f"P4={rec['decision']['P4_resolution_confirmed']})", flush=True)
    print(f"  [saved] {OUT}/{a.card}_hires_null.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
