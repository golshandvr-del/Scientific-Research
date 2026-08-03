# -*- coding: utf-8 -*-
"""
S374 — «دروازهٔ شکستِ Kennedy» (Kennedy Break Gate)

پیش‌ثبت: results/S374_PREREG_kennedy_break_gate.md  (commit شده پیش از این فایل)

═══════════════════════════════════════════════════════════════════════════
ایده در یک خط
═══════════════════════════════════════════════════════════════════════════
Jeffrey Kennedy (*Trading the Line*, ص ۱۳–۱۵) تعریفِ رایجِ شکستِ خطِ روند را
**رد** می‌کند:

      رایج (فعلیِ پروژه):  close < line   /   close > line
      Kennedy:             high  < line   /   low   > line

چون برای هر کندل `close ≤ high` و `close ≥ low`:

      high < line  ⟹  close < line
      low  > line  ⟹  close > line

⇒ سیگنال‌های Kennedy **زیرمجموعهٔ محضِ** سیگنال‌های فعلی‌اند. شرط اکیداً
سخت‌تر است ⇒ نمونه **الزاماً** کوچک می‌شود (اندازه‌گیری‌شده: میانهٔ ۴۰٪ نگه‌داشت).

═══════════════════════════════════════════════════════════════════════════
این یک «آزمونِ فیلترِ خالص» است، نه لایهٔ جدید
═══════════════════════════════════════════════════════════════════════════
هارنسِ S373 عیناً وارد می‌شود. تنها تفاوت، عبارتِ بولیِ ماشه است:

    MODE="close"    →  below = c < lower  ,  above = c > upper      (پایه)
    MODE="kennedy"  →  below = h < lower  ,  above = l > upper      (Kennedy)

دست‌نخورده: FAM_K/FAM_M/FAM_S · بریکتِ هر عضو · افقِ نگهداری (از میانهٔ مدتِ
کانالِ همان کارت) · warmup · GATE_BY_ASSET · مدلِ صفر · N_PERM=400 · قیدهای
ریزساختاری (`feas`).

⇒ تفاضلِ اندازه‌گیری‌شده اثرِ **تعریفِ شکست** را جدا می‌کند و هیچ چیزِ دیگری را.

═══════════════════════════════════════════════════════════════════════════
بندهای قفل — از پیش‌ثبت، در کد به‌صورت ثابت
═══════════════════════════════════════════════════════════════════════════
۱) قفلِ تعریف: تنها دو مقدارِ MODE مجازند. هیچ تعریفِ میانی (نوارِ تحمل،
   چند-کندلی، ترکیبی) پیاده نشده و نباید افزوده شود — آن یک جست‌وجوست.
۲) قفلِ خانواده: هیچ پارامتری بازتنظیم نمی‌شود.
۳) قفلِ تک‌فیلتر: هیچ فیلترِ دیگری افزوده نمی‌شود.
۴) قفلِ گزارشِ کامل: هر ۵ تایم‌فریمِ مشترک، شاملِ شکست‌ها.
۵) قفلِ اقتصاد: e_pip هر ابزار باید هزینهٔ رفت‌وبرگشتِ خودش را بپوشاند،
   بی‌اعتنا به معناداری.

آمارهٔ پذیرش = `trade_pooled` (قانونِ سوگیریِ خوش‌بینیِ میانگینِ خانواده).
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from engine.rqs2 import expected_max_z                                   # noqa: E402
from strategies.s366_stairs_channel_breakout import (                    # noqa: E402
    channel_context, _first_per_seg, _perm_meanR,
    FAM_K, FAM_M, FAM_S, MIN_TRADES, HORIZON_MULT, MAX_HOLD_CAP)

OUT = "results/_scan_S374"
N_PERM = 400

# ⛔ قفلِ منطقِ ابزارمحور — عیناً از S373، تغییرپذیر نیست.
GATE_BY_ASSET = {"XAUUSD": False, "EURUSD": True}

# ⛔ شمارشِ آزمون و سد — در پیش‌ثبت §۶ تثبیت شد، پیش از اجرا.
N_TRIALS = 112
Z_LUCK = expected_max_z(N_TRIALS)          # = 2.570

SHARED_TFS = ("M5", "M15", "M30", "H1", "H4")
PAIR = ("XAUUSD", "EURUSD")

# ⛔ قفلِ تعریف (بندِ ۱): تنها این دو حالت.
MODES = ("close", "kennedy")


# ═════════════════ سیگنالِ یک عضو — تنها نقطهٔ تفاوت ═════════════════
def member_signals_mode(df, ctx, m, s, asset, gate, mode):
    """
    کلونِ `s366.member_signals` با **یک** تفاوت: منبعِ قیمتِ ماشه.

    mode="close"    : below = close < lower ، above = close > upper
    mode="kennedy"  : below = high  < lower ، above = low   > upper

    هر چیزِ دیگری (بریکت، feas، first-per-seg، dur) بیت‌به‌بیت یکسان است.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")

    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])

    live = ctx["ok"]
    bear = ctx["is_bear"]
    shr = ctx["shrink"] if gate else np.zeros(n, dtype=bool)

    if mode == "close":
        c = df["close"].values.astype(float)
        src_dn = c                      # شکستِ نزولی با close سنجیده می‌شود
        src_up = c                      # شکستِ صعودی با close سنجیده می‌شود
    else:                               # kennedy
        src_dn = df["high"].values.astype(float)   # high باید زیرِ خط باشد
        src_up = df["low"].values.astype(float)    # low  باید بالای خط باشد

    below = live & np.nan_to_num(src_dn < ctx["lower"], nan=False)
    above = live & np.nan_to_num(src_up > ctx["upper"], nan=False)

    # کانالِ خرسی: هم‌جهت=شکست به پایین(SHORT) ، برگشتی=شکست به بالا(LONG)
    # کانالِ گاوی: هم‌جهت=شکست به بالا(LONG)  ، برگشتی=شکست به پایین(SHORT)
    short_raw = (bear & ~shr & below) | (~bear & shr & below)
    long_raw = (~bear & ~shr & above) | (bear & shr & above)

    trig = short_raw | long_raw
    first = _first_per_seg(trig, ctx["seg"])
    long_sig = first & long_raw
    short_sig = first & short_raw

    ch = np.nan_to_num(ctx["chan_h"], nan=0.0)
    sl_pip = np.zeros(n)
    tp_pip = np.zeros(n)
    sel = long_sig | short_sig
    sl_pip[sel] = (s * ch[sel]) / pip
    tp_pip[sel] = (m * ch[sel]) / pip

    # قیدهای ریزساختاری — عیناً از S366، دست‌نخورده.
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    feas = (tp_pip >= 2.0 * cost) & (sl_pip >= cost)
    long_sig &= feas
    short_sig &= feas

    dur = np.where(sel, np.arange(n) - ctx["t0"], 0)
    return long_sig, short_sig, sl_pip, tp_pip, dur


# ═════════════════ یک پا = یک ابزار روی یک تایم‌فریم ═════════════════
def run_leg(asset, tf, mode, mh_override=None):
    """
    ⚠️ نکتهٔ طراحیِ مهم: افقِ نگهداری (`mh`) از **حالتِ پایه** گرفته می‌شود و
       به حالتِ Kennedy تحمیل می‌شود (`mh_override`). دلیل: اگر هر حالت افقِ
       خودش را از هندسهٔ سیگنال‌های خودش استخراج کند، دو متغیر همزمان عوض
       می‌شوند و اثرِ فیلتر از اثرِ افق جدا نمی‌شود. این یک قیدِ سخت‌گیرانه
       است، نه یک تسهیل.
    """
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        return None
    df = se.load_data(path)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    warm = min(260, max(30, n // 8))
    half = n // 2
    gate = GATE_BY_ASSET[asset]

    ctxs = {k: channel_context(df, k) for k in FAM_K}

    if mh_override is not None:
        mh = int(mh_override)
    else:
        durs = []
        for k in FAM_K:
            ls, ss, _, _, dur = member_signals_mode(df, ctxs[k], FAM_M[0],
                                                    FAM_S[0], asset, gate, mode)
            sel = ls | ss
            if sel.any():
                durs.extend(dur[sel].tolist())
        if not durs:
            return None
        mh = int(min(MAX_HOLD_CAP,
                     max(5, round(HORIZON_MULT * float(np.median(durs))))))

    members, obsR, sls, rrs, isLs = [], [], [], [], []
    allR, allEB, burdens, tp_lt_sl = [], [], [], []
    n_raw_sig = 0
    for k in FAM_K:
        ctx = ctxs[k]
        for m_ in FAM_M:
            for s_ in FAM_S:
                ls, ss, slv, tpv, _ = member_signals_mode(df, ctx, m_, s_,
                                                          asset, gate, mode)
                ls[:warm] = False
                ss[:warm] = False
                ls[n - mh - 2:] = False
                ss[n - mh - 2:] = False
                n_raw_sig += int(ls.sum() + ss.sum())
                tr = se.simulate_trades(df, ls, ss, slv, tpv, asset,
                                        max_hold=mh, allow_overlap=False)
                if tr is None or len(tr) == 0:
                    continue
                sl = tr["sl_pip"].values.astype(float)
                okm = sl > 0
                if okm.sum() < MIN_TRADES:
                    continue
                R = tr["pnl_pip"].values[okm] / sl[okm]
                eb = tr["entry_bar"].values.astype(int)[okm]
                isL = (tr["direction"].values[okm] == "long")
                tp_lt_sl.append(1.0 if (float(m_) < float(s_)) else 0.0)
                members.append(dict(asset=asset, k=k, m=m_, s=s_,
                                    n=int(okm.sum()),
                                    meanR=round(float(R.mean()), 4),
                                    burden=round(float(np.mean(cost / sl[okm])), 4)))
                obsR.append(float(R.mean()))
                sls.append(sl[okm])
                rrs.append(float(m_) / float(s_))
                isLs.append(isL)
                burdens.append(float(np.mean(cost / sl[okm])))
                allR.append(R)
                allEB.append(eb < half)

    if not members:
        return None

    return dict(asset=asset, tf=tf, gate=gate, bars=n, max_hold=mh,
                warm=warm, pip=pip, cost=cost, mode=mode,
                n_raw_sig=n_raw_sig,
                o=df["open"].values.astype(float),
                h=df["high"].values.astype(float),
                l=df["low"].values.astype(float),
                members=members, obsR=obsR, sls=sls, rrs=rrs, isLs=isLs,
                burdens=burdens, allR=allR, allFirstHalf=allEB,
                tp_lt_sl=tp_lt_sl)


# ═════════════════ یک کارتِ ادغام‌شده در یک حالت ═════════════════
def run_mode(tf, mode, n_perm, seed, mh_map=None):
    legs = []
    for a in PAIR:
        lg = run_leg(a, tf, mode,
                     mh_override=(mh_map or {}).get(a))
        if lg is None:
            return None
        legs.append(lg)

    obs_all = [x for lg in legs for x in lg["obsR"]]
    fam = float(np.mean(obs_all))

    R_pool = np.concatenate([r for lg in legs for r in lg["allR"]])
    F_pool = np.concatenate([f for lg in legs for f in lg["allFirstHalf"]])
    trade_pooled = float(R_pool.mean())
    h1 = float(R_pool[F_pool].mean()) if F_pool.any() else float("nan")
    h2 = float(R_pool[~F_pool].mean()) if (~F_pool).any() else float("nan")

    tot = int(sum(m["n"] for lg in legs for m in lg["members"]))
    share_tp_lt_sl = float(np.mean([x for lg in legs for x in lg["tp_lt_sl"]]))

    econ = {}
    for lg in legs:
        bur = float(np.mean(lg["burdens"]))
        famA = float(np.mean(lg["obsR"]))
        # اقتصاد در فضای معامله (نه خانواده) — سازگار با آمارهٔ پذیرش.
        R_a = np.concatenate(lg["allR"])
        tradeA = float(R_a.mean())
        sl_eff = lg["cost"] / bur if bur > 0 else float("nan")
        econ[lg["asset"]] = dict(
            n=int(sum(m["n"] for m in lg["members"])),
            n_raw_sig=lg["n_raw_sig"],
            fam_meanR=round(famA, 4),
            trade_meanR=round(tradeA, 4),
            burden=round(bur, 4),
            sl_eff=round(sl_eff, 2), cost=lg["cost"],
            # e_pip بر پایهٔ آمارهٔ پذیرش (trade-space) — قفلِ ۵ پیش‌ثبت.
            e_pip=round(tradeA * sl_eff + lg["cost"], 3),
            surplus=round(tradeA * sl_eff, 3),
            e_pip_fam=round(famA * sl_eff + lg["cost"], 3),
            gate=lg["gate"], max_hold=lg["max_hold"])

    # ── مدلِ صفر: عیناً از S373 ──
    rng = np.random.default_rng(seed)
    perms = []
    for _ in range(n_perm):
        vals = []
        for lg in legs:
            lo, hi = lg["warm"], lg["bars"] - lg["max_hold"] - 2
            for sl_arr, isL, rr in zip(lg["sls"], lg["isLs"], lg["rrs"]):
                mlen = len(sl_arr)
                picks = rng.integers(lo, hi, size=mlen)
                v = _perm_meanR(lg["o"], lg["h"], lg["l"], picks, isL,
                                sl_arr[rng.permutation(mlen)], lg["pip"],
                                lg["max_hold"], lg["cost"], rr)
                if v is not None:
                    vals.append(v)
        if vals:
            perms.append(float(np.mean(vals)))
    perms = np.array(perms, dtype=float)
    null_mean = float(perms.mean()) if len(perms) else float("nan")
    sd = float(perms.std(ddof=1)) if len(perms) > 1 else float("nan")

    # آمارهٔ پذیرش = trade_pooled (قانونِ سوگیریِ خوش‌بینی)
    lift = trade_pooled - null_mean
    z = lift / sd if (sd and sd > 0) else float("nan")
    p_perm = float((perms >= trade_pooled).sum() + 1) / (len(perms) + 1)
    n_needed = int(round((Z_LUCK * sd / lift) ** 2 * tot)) if lift > 0 else -1

    return dict(tf=tf, mode=mode, pair=list(PAIR),
                gate_map=GATE_BY_ASSET,
                n_trials=N_TRIALS, z_luck=round(float(Z_LUCK), 3),
                n_members=len(obs_all), n_trades=tot,
                fam_pooled=round(fam, 4),
                trade_pooled=round(trade_pooled, 4),
                weighting_effect=round(fam - trade_pooled, 4),
                null_meanR=round(null_mean, 4), sd=round(sd, 4),
                lift=round(lift, 4), z=round(z, 3),
                p_perm=round(p_perm, 4),
                half1=round(h1, 4), half2=round(h2, 4),
                share_tp_lt_sl=round(share_tp_lt_sl, 3),
                n_needed=n_needed, econ=econ, n_perm=len(perms),
                mh_map={lg["asset"]: lg["max_hold"] for lg in legs},
                members=[m for lg in legs for m in lg["members"]])


# ═════════════════ یک کارت = پایه + Kennedy، مقایسهٔ جفتی ═════════════════
def run_card(tf, n_perm=N_PERM, seed=374, save=True):
    print(f"\n{'='*72}")
    print(f"=== S374 KENNEDY BREAK GATE :: {tf} ===")
    print(f"{'='*72}", flush=True)

    # ① پایه (close) — افقِ نگهداری از هندسهٔ خودش استخراج می‌شود.
    base = run_mode(tf, "close", n_perm, seed)
    if base is None:
        res = dict(tf=tf, verdict="INCOMPLETE_PAIR")
        if save:
            _save(res, tf)
        print("   >>> INCOMPLETE_PAIR")
        return res

    # ② Kennedy — همان افقِ نگهداریِ پایه تحمیل می‌شود (جداسازیِ متغیر).
    ken = run_mode(tf, "kennedy", n_perm, seed, mh_map=base["mh_map"])
    if ken is None:
        res = dict(tf=tf, verdict="KENNEDY_NO_SAMPLE", base=base)
        if save:
            _save(res, tf)
        print("   >>> KENNEDY_NO_SAMPLE (دروازه نمونهٔ کافی نگذاشت)")
        return res

    for tag, r in (("BASE   (close)", base), ("KENNEDY(high/low)", ken)):
        print(f"\n  ── {tag} ──")
        print(f"     members={r['n_members']}  Σn={r['n_trades']:,}"
              f"   trade_pooled={r['trade_pooled']:+.4f}"
              f"  (fam={r['fam_pooled']:+.4f})")
        print(f"     null={r['null_meanR']:+.4f}  sd={r['sd']:.4f}"
              f"  lift={r['lift']:+.4f}  z={r['z']:+.3f}"
              f"  p_perm={r['p_perm']:.4f}")
        print(f"     halves=({r['half1']:+.4f}, {r['half2']:+.4f})"
              f"   n_needed={r['n_needed']:,}")
        for a, e in r["econ"].items():
            print(f"       {a}: n={e['n']:>6,}  SL_eff={e['sl_eff']:>6.1f}p"
                  f"  e_pip={e['e_pip']:>+7.2f} vs c={e['cost']:.1f}"
                  f"  ⇒ surplus={e['surplus']:>+7.2f}", flush=True)

    # ── مقایسهٔ جفتی: سنجهٔ اصلیِ این آزمون ──
    print(f"\n  ── Δ (KENNEDY − BASE) ── سنجهٔ اصلیِ پیش‌ثبت‌شده ──")
    retain = 100.0 * ken["n_trades"] / base["n_trades"] if base["n_trades"] else 0.0
    print(f"     retention: {ken['n_trades']:,}/{base['n_trades']:,}"
          f" = {retain:.1f}%")
    print(f"     Δ trade_pooled = {ken['trade_pooled']-base['trade_pooled']:+.4f}")
    print(f"     Δ z            = {ken['z']-base['z']:+.3f}")
    d_epip = {}
    n_worse = 0
    for a in PAIR:
        if a in base["econ"] and a in ken["econ"]:
            d = ken["econ"][a]["e_pip"] - base["econ"][a]["e_pip"]
            d_epip[a] = round(d, 3)
            if d < 0:
                n_worse += 1
            print(f"     Δ e_pip[{a}] = {d:+7.3f}"
                  f"   ({base['econ'][a]['e_pip']:+.2f} → "
                  f"{ken['econ'][a]['e_pip']:+.2f})")

    # ── حکم: چهار شرطِ پیش‌ثبت‌شده روی حالتِ Kennedy ──
    conds = {}
    conds["luck"] = bool(ken["z"] >= Z_LUCK)
    conds["sample"] = bool(ken["n_needed"] > 0 and ken["n_trades"] >= ken["n_needed"])
    conds["econ"] = all(e["surplus"] > 0 for e in ken["econ"].values())
    conds["replication"] = bool(ken["half1"] > 0 and ken["half2"] > 0)
    passed = all(conds.values())

    print(f"\n  ── VERDICT (Kennedy mode, ceiling z_luck={Z_LUCK:.3f}) ──")
    for k, v in conds.items():
        print(f"     {k:12} : {'PASS' if v else 'FAIL'}")

    if passed:
        verdict = "ACCEPT"
    elif not conds["econ"]:
        verdict = "DEAD_BELOW_COST"
    elif not conds["luck"]:
        verdict = "DEAD_LUCK_BOUND"
    elif not conds["sample"]:
        verdict = "DEAD_INSUFFICIENT_SAMPLE"
    else:
        verdict = "DEAD_NO_REPLICATION"
    print(f"     >>> {verdict}", flush=True)

    res = dict(tf=tf, verdict=verdict, conds=conds,
               retention_pct=round(retain, 1),
               d_trade_pooled=round(ken["trade_pooled"] - base["trade_pooled"], 4),
               d_z=round(ken["z"] - base["z"], 3),
               d_e_pip=d_epip, n_epip_worse=n_worse,
               base=base, kennedy=ken)
    if save:
        _save(res, tf)
    return res


def _save(res, tf):
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{tf}.json", "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(f"   [saved] {OUT}/{tf}.json", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="")
    ap.add_argument("--perm", type=int, default=N_PERM)
    ap.add_argument("--seed", type=int, default=374)
    a = ap.parse_args()
    tfs = [a.tf] if a.tf else list(SHARED_TFS)
    # ترتیب: از گران‌ترین اطلاعات (H4، بهترین کارتِ پروژه) شروع نمی‌کنیم؛
    # طبقِ قانونِ MTF از سبک‌ترین شروع می‌شود ولی همه گزارش می‌شوند.
    for tf in tfs:
        try:
            run_card(tf, n_perm=a.perm, seed=a.seed)
        except Exception as ex:                                   # noqa: BLE001
            print(f"   !! {tf} FAILED: {type(ex).__name__}: {ex}", flush=True)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
