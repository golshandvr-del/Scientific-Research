# -*- coding: utf-8 -*-
"""
S366 — Stairs (فصلِ ۲۶ Brooks): **شکستِ کانال با هدفِ measured-move**

پیش‌ثبت: `results/S366_PREREG_stairs_channel_breakout.md` (پیش از اجرا commit شد)

════════════════════════════════════════════════════════════════════════════
تفاوتِ بنیادی با S364/S365
════════════════════════════════════════════════════════════════════════════
    S364/S365:  ورود **داخلِ** کانال، خلافِ پله (fade)  →  هر دو مردند
    S366:       ورود روی **شکستِ خودِ کانال**، با هدف = **ارتفاعِ کانال**

منبعِ متنیِ مستقیم (ص ۴۳۲):
    «one stair might suddenly accelerate and **break out of the trend channel**…
     the breakout will probably continue for at least two more legs or at least
     the approximate **height of the channel** in an imprecise measured move
     (**the distance beyond the channel should be about the same as the distance
     within the channel**).»

و قاعدهٔ جهت (متن + مقایسهٔ شکلِ ۲۶.۲ با ۲۶.۳):
    «If each breakout gets a little smaller than the prior one, then this is a
     **shrinking stairs** pattern and a sign of **waning momentum**… It often
     leads to a **two-legged reversal and a trend line break**.»

    ⇒ پله‌های سالم      → شکست **هم‌جهت** با شیبِ کانال      (شکلِ ۲۶.۲، EURUSD Daily)
    ⇒ پله‌های کوچک‌شونده → شکست **خلافِ** شیب (کانال = پرچم)  (شکلِ ۲۶.۳)

════════════════════════════════════════════════════════════════════════════
چرا این‌بار بریکت مشکلِ کشندهٔ دو لایهٔ قبل را ندارد
════════════════════════════════════════════════════════════════════════════
طبقِ `docs/FINDING_R_SPACE_BASELINE_LAW.md`:   E[R] = e − b   ,   b = c / SL

    S364:  SL = s·ext      (ext = «چقدر از پله رد شد» — عمداً کوچک)  → b = 0.25…0.49
    S365:  SL = s·pull     (ارتفاعِ یک نوسان)                         → b = 0.03…0.38
    S366:  SL = s·chan_h   (**ارتفاعِ کلِ کانال** — بزرگ‌ترین مقیاسِ الگو)

و TP = m·chan_h هم **انتخابِ من نیست**؛ همان measured-moveِ خودِ فصل است. یعنی
برای نخستین‌بار در این پژوهش، هر دو پای بریکت را **متن** تجویز کرده و اتفاقاً
دقیقاً در مقیاسی که قانونِ خطِ مبنا می‌طلبد.

════════════════════════════════════════════════════════════════════════════
قاعدهٔ تصمیم (سه‌شرطی — از پیش‌ثبت)
════════════════════════════════════════════════════════════════════════════
    (۱) z ≥ 3.09σ در برابرِ نالِ هم‌بریکت           ← مهارت
    (۲) میانگینِ R خانواده > 0                      ← قابلِ تبدیل به پول
    (۳) میانگینِ R در **هر دو نیمه جداگانه** > 0    ← تکرارِ داخلی
"""

import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s364_stairs_family import pivot_flags, MIN_TRADES        # noqa: E402

OUT = "results/_scan_S366"

# ───────────────── خانوادهٔ ازپیش‌ثبت‌شده (۱۲ عضو · قفل) ─────────────────
FAM_K = (2, 3, 5)               # بازوی pivot — فیبوناچی/غیررند
FAM_M = (0.618, 1.000)          # TP = m · chan_h   (۱.۰ = measured-moveِ متن)
FAM_S = (0.500, 0.786)          # SL = s · chan_h   (۰.۷۸۶ = √۰.۶۱۸ — غیررند)

N_PERM = 400
Z_BAR = 3.09

# ⚠️ **یک** ثابتِ ساختاری، سوئپ نمی‌شود و عضوِ خانواده نیست:
# «افقِ زمانیِ الگو» = ۲ × مدتِ خودِ کانال. هم عمرِ زمینه را محدود می‌کند
# (تا خطوطِ برون‌یابی‌شده تا ابد امتداد نیابند) و هم مبنای max_hold است.
# منطقش متنِ فصل است: measured-move تقریباً به‌اندازهٔ خودِ کانال طول می‌کشد.
HORIZON_MULT = 2.0
MAX_HOLD_CAP = 400

ALL_CARDS = [("XAUUSD", tf) for tf in ("M5", "M15", "M30", "H1", "H4", "D1", "W1")] + \
            [("EURUSD", tf) for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1")]


# ═══════════════════ زمینهٔ کانال (با ایندکسِ پیوت‌ها) ═══════════════════
def channel_context(df, k):
    """
    برخلافِ `stairs_context` در S364 که فقط **قیمتِ** پیوت‌ها را نگه می‌داشت،
    اینجا **ایندکسِ** پیوت‌ها هم لازم است، چون باید دو خطِ کانال را بسازیم.

    خروجی (آرایه‌های هم‌طولِ df):
        ok        : زمینهٔ کانال زنده است
        is_bear   : کانالِ نزولی است (وگرنه صعودی)
        lower[t]  : مقدارِ خطِ پایینِ کانال در بارِ t (برون‌یابی‌شده)
        upper[t]  : مقدارِ خطِ بالای کانال در بارِ t (موازیِ خطِ پایین)
        chan_h    : ضخامتِ عمودیِ کانال
        shrink    : پلهٔ آخر کوچک‌تر از پلهٔ قبلی بود؟
        seg       : شناسهٔ زمینه (برای «فقط اولین شکست»)
        t0        : ایندکسِ نخستین پیوتِ کانال (برای مدت/افق)
    """
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    n = len(df)
    ph, pl = pivot_flags(h, l, k)

    # رویدادها: هر پیوت در بارِ i، اما **تأییدشده** در i+k ⇒ بدونِ نشتِ آینده
    ev = [(i + k, i, "H", h[i]) for i in np.flatnonzero(ph)]
    ev += [(i + k, i, "L", l[i]) for i in np.flatnonzero(pl)]
    ev.sort(key=lambda e: (e[0], e[1]))

    ok = np.zeros(n, dtype=bool)
    is_bear = np.zeros(n, dtype=bool)
    lower = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    chan_h = np.full(n, np.nan)
    shrink = np.zeros(n, dtype=bool)
    seg = np.full(n, -1, dtype=np.int64)
    t0a = np.full(n, -1, dtype=np.int64)

    piv = []            # zigzagِ متناوب: [(typ, idx, px)]
    ptr, n_ev = 0, len(ev)
    cur = None          # dict یا None
    seg_id = -1

    for t in range(n):
        changed = False
        while ptr < n_ev and ev[ptr][0] <= t:
            _, idx, typ, px = ev[ptr]
            ptr += 1
            if piv and piv[-1][0] == typ:
                # پیوتِ هم‌نوعِ شدیدتر ⇒ جایگزینی (zigzag)
                if (typ == "H" and px > piv[-1][2]) or (typ == "L" and px < piv[-1][2]):
                    piv[-1] = (typ, idx, px)
                    changed = True
            else:
                piv.append((typ, idx, px))
                changed = True
                if len(piv) > 8:
                    del piv[0]

        if changed:
            new = _build_channel(piv)
            # مقایسهٔ ساختاری: زمینهٔ نو فقط وقتی «نو» است که هندسه‌اش عوض شود
            if new != cur:
                cur = new
                if new is not None:
                    seg_id += 1

        if cur is None:
            continue
        # افقِ زندگیِ زمینه: خطوط تا ابد برون‌یابی نمی‌شوند
        if t > cur["t_last"] + HORIZON_MULT * max(1, cur["t_last"] - cur["t0"]):
            continue

        lo = cur["a"] + cur["b"] * (t - cur["t_ref"])
        ok[t] = True
        is_bear[t] = cur["bear"]
        lower[t] = lo
        upper[t] = lo + cur["h"]
        chan_h[t] = cur["h"]
        shrink[t] = cur["shrink"]
        seg[t] = seg_id
        t0a[t] = cur["t0"]

    return dict(ok=ok, is_bear=is_bear, lower=lower, upper=upper,
                chan_h=chan_h, shrink=shrink, seg=seg, t0=t0a)


def _build_channel(piv):
    """از ۵ پیوتِ آخر یک کانالِ stairs بساز (یا None).

    خرسی: [L1,H1,L2,H2,L3]  با L1>L2>L3 ، H1>H2 ، **H2>L1** (قیدِ همپوشانی)
    گاوی: [H1,L1,H2,L2,H3]  با H1<H2<H3 ، L1<L2 ، **L2<H1**

    قیدِ همپوشانی مستقیماً از متن است: در کانالِ خرسی، رالیِ پس از شکستِ کفِ نو
    باید **از نقطهٔ شکست عبور کند**؛ نقطهٔ شکست همان کفی است که شکسته شد (L1)،
    نه کفی که رالی از آن شروع شده (L2). این همان تصحیحی است که در فایلِ فصل ثبت شد.
    """
    if len(piv) < 5:
        return None
    tps = [p[0] for p in piv[-5:]]
    ix = [p[1] for p in piv[-5:]]
    px = [p[2] for p in piv[-5:]]

    if tps == ["L", "H", "L", "H", "L"]:
        L1, H1, L2, H2, L3 = px
        iL1, iH1, iL2, iH2, iL3 = ix
        if not (L1 > L2 > L3 and H1 > H2 and H2 > L1):
            return None
        if iL3 <= iL2:
            return None
        b = (L3 - L2) / float(iL3 - iL2)        # شیبِ خطِ پایین (منفی)
        hgt = H2 - (L3 + b * (iH2 - iL3))       # ضخامتِ عمودی در بارِ H2
        if not (hgt > 0):
            return None
        return dict(bear=True, a=L3, b=b, t_ref=iL3, h=hgt,
                    shrink=(L2 - L3) < (L1 - L2), t0=iL1, t_last=iL3)

    if tps == ["H", "L", "H", "L", "H"]:
        H1, L1, H2, L2, H3 = px
        iH1, iL1, iH2, iL2, iH3 = ix
        if not (H1 < H2 < H3 and L1 < L2 and L2 < H1):
            return None
        if iH3 <= iH2:
            return None
        bu = (H3 - H2) / float(iH3 - iH2)       # شیبِ خطِ بالا (مثبت)
        hgt = (H3 + bu * (iL2 - iH3)) - L2      # ضخامتِ عمودی در بارِ L2
        if not (hgt > 0):
            return None
        # `a/t_ref` همیشه خطِ **پایین** را توصیف می‌کند تا پایین‌دست یکنواخت بماند
        return dict(bear=False, a=H3 - hgt, b=bu, t_ref=iH3, h=hgt,
                    shrink=(H3 - H2) < (H2 - H1), t0=iH1, t_last=iH3)

    return None


# ═════════════════════════ سیگنالِ یک عضو ═════════════════════════
def member_signals(df, ctx, m, s, asset, gate=True):
    """
    gate=True  → قاعدهٔ Brooks: سالم⇒هم‌جهت ، کوچک‌شونده⇒برگشتی
    gate=False → ablation: همیشه شکستِ هم‌جهت (فقط تشخیصی، در پذیرش دخالت ندارد)
    """
    c = df["close"].values.astype(float)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])

    live = ctx["ok"]
    bear = ctx["is_bear"]
    shr = ctx["shrink"] if gate else np.zeros(n, dtype=bool)

    below = live & np.nan_to_num(c < ctx["lower"], nan=False)
    above = live & np.nan_to_num(c > ctx["upper"], nan=False)

    #  کانالِ خرسی: هم‌جهت = شکست به پایین (SHORT) ؛ برگشتی = شکست به بالا (LONG)
    #  کانالِ گاوی: هم‌جهت = شکست به بالا (LONG) ؛ برگشتی = شکست به پایین (SHORT)
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

    # قیدهای ریزساختاری (واقعیتِ بازار، نه پارامترِ قابلِ تنظیم):
    # هدفِ باریک‌تر از دو برابرِ رفت‌وبرگشتِ اسپرد اصلاً «معامله» نیست.
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    feas = (tp_pip >= 2.0 * cost) & (sl_pip >= cost)
    long_sig &= feas
    short_sig &= feas

    dur = np.where(sel, np.arange(n) - ctx["t0"], 0)
    return long_sig, short_sig, sl_pip, tp_pip, dur


def _first_per_seg(trig, seg):
    """فقط نخستین شکست در هر زمینه — تا یک الگو چند سیگنالِ همبسته نپاشد."""
    n = len(trig)
    out = np.zeros(n, dtype=bool)
    seen = set()
    for t in np.flatnonzero(trig):
        sid = seg[t]
        if sid < 0 or sid in seen:
            continue
        seen.add(sid)
        out[t] = True
    return out


# ═════════════════════════ اجرای یک کارت ═════════════════════════
def run_card(asset, tf, n_perm=N_PERM, seed=366, save=True, gate=True):
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        print(f"   !! missing {path}")
        return None
    df = se.load_data(path)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    warm = min(260, max(30, n // 8))
    half = n // 2
    tag = "A(gated)" if gate else "B(ablation)"
    print(f"\n=== S366 {tag} :: {asset}-{tf} (bars={n:,}) ===", flush=True)

    ctxs = {k: channel_context(df, k) for k in FAM_K}

    # ── گامِ ۱: افقِ نگه‌داری از هندسهٔ خودِ الگو (نه از نتیجهٔ معاملات) ──
    durs = []
    for k in FAM_K:
        ls, ss, slv, tpv, dur = member_signals(df, ctxs[k], FAM_M[0], FAM_S[0],
                                               asset, gate)
        sel = (ls | ss)
        if sel.any():
            durs.extend(dur[sel].tolist())
    if not durs:
        res = dict(asset=asset, tf=tf, bars=n, verdict="NO_CONTEXT")
        if save:
            _save(res, asset, tf, gate)
        print("   NO_CONTEXT")
        return res
    mh = int(min(MAX_HOLD_CAP, max(5, round(HORIZON_MULT * float(np.median(durs))))))
    print(f"    median channel duration={np.median(durs):.0f} bars ⇒ max_hold={mh}",
          flush=True)

    # ── گامِ ۲: هر ۱۲ عضو ──
    members, obsR, sls, rrs, isLs, halves = [], [], [], [], [], []
    n_alive = 0
    burdens = []
    for k in FAM_K:
        ctx = ctxs[k]
        for m_ in FAM_M:
            for s_ in FAM_S:
                ls, ss, slv, tpv, _ = member_signals(df, ctx, m_, s_, asset, gate)
                ls[:warm] = False
                ss[:warm] = False
                ls[n - mh - 2:] = False
                ss[n - mh - 2:] = False
                tr = se.simulate_trades(df, ls, ss, slv, tpv, asset,
                                        max_hold=mh, allow_overlap=False)
                if tr is None or len(tr) == 0:
                    continue
                sl = tr["sl_pip"].values.astype(float)
                okm = sl > 0
                if okm.sum() < MIN_TRADES:
                    continue
                n_alive += 1
                R = tr["pnl_pip"].values[okm] / sl[okm]
                eb = tr["entry_bar"].values.astype(int)[okm]
                isL = (tr["direction"].values[okm] == "long")
                members.append(dict(k=k, m=m_, s=s_, n=int(okm.sum()),
                                    meanR=round(float(R.mean()), 4),
                                    med_sl=round(float(np.median(sl[okm])), 2),
                                    burden=round(float(np.mean(cost / sl[okm])), 4),
                                    wr=round(100.0 * float((R > 0).mean()), 2)))
                obsR.append(float(R.mean()))
                sls.append(sl[okm])
                rrs.append(float(m_) / float(s_))
                isLs.append(isL)
                burdens.append(float(np.mean(cost / sl[okm])))
                f1 = eb < half
                halves.append((float(R[f1].mean()) if f1.sum() >= 5 else np.nan,
                               float(R[~f1].mean()) if (~f1).sum() >= 5 else np.nan))

    if not members:
        res = dict(asset=asset, tf=tf, bars=n, n_members_alive=0,
                   verdict="NO_VIABLE_MEMBER")
        if save:
            _save(res, asset, tf, gate)
        print("   NO_VIABLE_MEMBER")
        return res

    fam = float(np.mean(obsR))
    h1 = float(np.nanmean([a for a, _ in halves]))
    h2 = float(np.nanmean([b for _, b in halves]))
    tot = int(sum(m_["n"] for m_ in members))
    print(f"  OBSERVED family mean R = {fam:+.4f}   alive={n_alive}/12  Σn={tot:,}")
    print(f"           member range   = [{min(obsR):+.4f}, {max(obsR):+.4f}]")
    print(f"           halves         = ({h1:+.4f}, {h2:+.4f})")
    print(f"           mean burden b  = {np.mean(burdens):.4f}"
          f"   (theory: null ≈ {-np.mean(burdens):+.4f})", flush=True)

    # ── گامِ ۳: نالِ هم‌بریکت (بارها تصادفی، مجموعهٔ بریکت و RRِ عضو دست‌نخورده) ──
    rng = np.random.default_rng(seed)
    o_ = df["open"].values.astype(float)
    h_ = df["high"].values.astype(float)
    l_ = df["low"].values.astype(float)
    lo, hi = warm, n - mh - 2
    perms = []
    for _ in range(n_perm):
        vals = []
        for sl_arr, isL, rr in zip(sls, isLs, rrs):
            mlen = len(sl_arr)
            picks = rng.integers(lo, hi, size=mlen)
            v = _perm_meanR(o_, h_, l_, picks, isL,
                            sl_arr[rng.permutation(mlen)], pip, mh, cost, rr)
            if v is not None:
                vals.append(v)
        if vals:
            perms.append(float(np.mean(vals)))
    perms = np.asarray(perms, dtype=float)
    nullm = float(perms.mean())
    sd = float(perms.std(ddof=1)) or 1e-9
    z = (fam - nullm) / sd
    p = float((perms >= fam).mean())

    skill = z >= Z_BAR
    positive = fam > 0
    repl = (h1 > 0) and (h2 > 0)
    if skill and positive and repl:
        verdict = "FAMILY_CONFIRMED"
    elif skill and positive:
        verdict = "DEAD_NO_REPLICATION"
    elif skill:
        verdict = "DEAD_NEGATIVE_ABSOLUTE"
    else:
        verdict = "DEAD_NO_SKILL"

    print(f"  NULL   family mean R = {nullm:+.4f}   sd = {sd:.4f}  (perms={len(perms)})")
    print(f"  LIFT_R = {fam - nullm:+.4f} R/trade   z = {z:+.2f}σ   p = {p:.4f}")
    print(f"  >>> {verdict}   (skill={skill}, positive={positive}, repl={repl})",
          flush=True)

    res = dict(asset=asset, tf=tf, bars=n, gate=gate, max_hold=mh,
               n_members_alive=n_alive, n_members_total=12, n_total_trades=tot,
               fam_meanR=round(fam, 4), null_meanR=round(nullm, 4),
               sd=round(sd, 4), lift=round(fam - nullm, 4), z=round(z, 3),
               p_perm=round(p, 4), burden_mean=round(float(np.mean(burdens)), 4),
               half1_meanR=round(h1, 4), half2_meanR=round(h2, 4),
               member_min=round(min(obsR), 4), member_max=round(max(obsR), 4),
               n_members_positive=int(sum(1 for x in obsR if x > 0)),
               n_perm=len(perms), members=members, verdict=verdict)
    if save:
        _save(res, asset, tf, gate)
    return res


def _perm_meanR(o, h, l, picks, isL, sl_v, pip, mh, cost, rr):
    """R میانگینِ یک جای‌گشت — همان بریکت‌ها و همان نسبتِ RRِ عضو، بارهای تصادفی."""
    m = len(picks)
    if m == 0:
        return None
    if len(isL) != m:
        isL = np.resize(isL, m)
    out = np.zeros(m)
    sl_pr = sl_v * pip
    for i in range(m):
        st = picks[i] + 1
        en = min(st + mh, len(o))
        if st >= en:
            continue
        e = o[st]
        d = sl_pr[i]
        if d <= 0:
            continue
        t = d * rr
        hh, ll = h[st:en], l[st:en]
        if isL[i]:
            up = (hh >= e + t)
            dn = (ll <= e - d)
        else:
            up = (ll <= e - t)
            dn = (hh >= e + d)
        i_up = int(np.argmax(up)) if up.any() else 10**9
        i_dn = int(np.argmax(dn)) if dn.any() else 10**9
        if i_up < i_dn:
            out[i] = rr - cost / (d / pip)
        elif i_dn < 10**9:
            out[i] = -1.0 - cost / (d / pip)
        else:
            px = o[en - 1] if en - 1 < len(o) else e
            raw = (px - e) if isL[i] else (e - px)
            out[i] = raw / d - cost / (d / pip)
    return float(out.mean())


def _save(res, asset, tf, gate):
    os.makedirs(OUT, exist_ok=True)
    suf = "" if gate else "_ABL"
    p = f"{OUT}/{asset}_{tf}{suf}.json"
    with open(p, "w") as f:
        json.dump(res, f, indent=1)
    print(f"    saved -> {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="XAUUSD")
    ap.add_argument("--tf", default="H1")
    ap.add_argument("--perm", type=int, default=N_PERM)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ablation", action="store_true")
    a = ap.parse_args()
    gate = not a.ablation
    if a.all:
        for asset, tf in ALL_CARDS:
            try:
                run_card(asset, tf, n_perm=a.perm, gate=gate)
            except Exception as e:                                  # noqa: BLE001
                print(f"   !! {asset}-{tf} failed: {e}", flush=True)
    else:
        run_card(a.asset, a.tf, n_perm=a.perm, gate=gate)


if __name__ == "__main__":
    main()
