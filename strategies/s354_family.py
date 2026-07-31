# -*- coding: utf-8 -*-
"""
S354-FAMILY — آزمونِ **سطحِ خانواده** برای «Trend Resumption Day» (فصلِ ۲۵ Brooks)
====================================================================================

چرا این آزمون؟
--------------
اسکنِ گریدِ S354 (results/_scan_S354/*.json) نشان داد الگوی resumption یک لبهٔ
**واقعی و غیرتصادفی** است (lift اغلب +۱۰ تا +۱۵pp، بسیار بالای کفِ ۴pp) که در هر دو
ارز و اکثرِ TFها تکرار می‌شود — اما همه REJECT شدند چون:
  · H3: z<3.0 (z بهترین کارت، XAU-H1، فقط ۲.۶۱ بود)
  · H5: p_adj = p × n_trials؛ با n_trials≈۴۰۰ (تعدادِ واریانتِ گرید) عملاً کشته شد.

راهِ **غلط**: پایین‌آوردنِ آستانه یا کم‌شمردنِ n_trials → داده‌کاوی روی خودِ معیار
(اشتباهِ رایجِ #۸ «دور زدنِ معیار»). این کار را نمی‌کنم.

راهِ **درست** (طبقِ RQS2_SPEC §۲.۵ و پیروزیِ S346):
> جریمهٔ چندگانگی بهای **انتخابِ بهترینِ N** است. اگر هیچ عضوی انتخاب نشود،
> بهایی هم نیست ⇒ N=1.

پروتکل:
  · یک **خانوادهٔ پیش‌ثبت‌شده** از پارامترهای resumption تعریف می‌کنیم (هیچ گزینشی).
  · آماره = **میانگینِ WR روی همهٔ اعضا** (نه بهترین عضو).
  · توزیعِ صفر = جای‌گشتِ زمانی که برای هر عضو **همان تعدادِ ورود** و **همان نسبتِ
    long/short** را در زمان‌های تصادفی می‌گذارد (رانش برای دو سمت هدیهٔ متفاوت دارد).
  · چندگانگی N=1 ⇒ کرانِ E[max_1]=0.52σ.

خانوادهٔ پیش‌ثبت‌شده (منشأ: امضای برندهٔ XAU-H1 در اسکنِ گرید):
  side = both (جهت از init_dir طبیعیِ روز؛ گزینش نمی‌شود)
  r2_gate = r2_fib_55 ≥ 0.45  (فیلترِ رژیمِ برنده، ثابت)
  محورها: n_open_frac × late_from × spike_k × tight_atr × RR  (اعدادِ غیررند)
  SL/TP از ATRِ per-TF (پادزهرِ اشتباهِ #۶/#۷).

اجرا:  python3 strategies/s354_family.py XAUUSD H1 300
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se           # noqa: E402
from engine import indicator_bank as ib          # noqa: E402
from engine.rqs2 import expected_max_z            # noqa: E402
from strategies import s354_brooks_trend_resumption as base  # noqa: E402

OUT = 'results/_scan_S354'

# ------------------------------------------------------------------------------
# خانوادهٔ پیش‌ثبت‌شده — پیش از اجرای آزمون تثبیت شده (امضای برندهٔ XAU-H1).
# side=both ⇒ جهت از روندِ صبحِ روز می‌آید؛ هیچ سمتی گزینش نمی‌شود.
# r2_fib_55≥0.45 فیلترِ رژیمِ ثابتِ خانواده است (نه یک درجهٔ آزادیِ گزینشی).
# ------------------------------------------------------------------------------
FAM_R2 = ("r2_fib_55", "ge", 0.45)
FAM_N_OPEN = (0.13, 0.21)          # کسرِ ساعتِ اول
FAM_LATE = (0.55, 0.68)            # شروعِ پنجرهٔ پایانی
FAM_SPIKE = (0.8, 1.3)             # اسپایکِ صبح ≥ spike×ATR
FAM_TIGHT = (8.0, 12.0)            # رنجِ midday ≤ tight×ATR
FAM_RR = (1.0, 1.6)                # TP/SL (SL از ATRِ per-TF)
FAM_SL_K = 1.3                     # SL = 1.3×ATR_pip (ثابت)


def members():
    """۳۲ عضوِ خانواده. هیچ رتبه‌بندی، هیچ گزینشی."""
    out = []
    for nof in FAM_N_OPEN:
        for lf in FAM_LATE:
            for sk in FAM_SPIKE:
                for ta in FAM_TIGHT:
                    for rr in FAM_RR:
                        out.append(dict(n_open_frac=nof, late_from=lf,
                                        spike_k=sk, tight_atr=ta, rr=rr))
    return out


def _wr_of(df, ls, ss, sl, tp, asset, mh):
    """WRِ یک عضو با صفِ بی‌همپوشانیِ موتورِ رسمی."""
    tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh,
                            allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None, 0
    wins = int((tr["pnl_pip"] > 0).sum())
    n = len(tr)
    return 100.0 * wins / n, n


def run(asset='XAUUSD', tf='H1', n_perm=300, seed=11, save=True):
    path = f"data/{asset}_{tf}.csv"
    df = se.load_data(path)
    n = len(df)
    rng = np.random.default_rng(seed)

    atr_pip = base._atr_pip(df, asset, base.TF_ATR_P.get(tf, 34))
    mh = base.TF_MAX_HOLD.get(tf, 40)
    sl = round(FAM_SL_K * atr_pip, 1)
    gate = base.regime_gate(df, FAM_R2)

    mem = members()
    print(f"=== S354 FAMILY-LEVEL TEST :: {asset}-{tf} (bars={n}) ===", flush=True)
    print(f"    pre-registered family: resumption / side=both / r2>=0.45 "
          f"sl_k={FAM_SL_K} (SL={sl}pip)", flush=True)
    print(f"    members = {len(mem)}  (NO member is selected)", flush=True)
    print(f"    permutations = {n_perm}", flush=True)

    # ---------------- گامِ ۱: آمارهٔ مشاهده‌شده روی همهٔ اعضا ----------------
    per_member, prepared = [], []
    for gi, g in enumerate(mem):
        long_raw, short_raw = base.build_signals(df, asset, tf, g['n_open_frac'],
                                                  g['late_from'], g['spike_k'],
                                                  g['tight_atr'])
        ls = long_raw & gate
        ss = short_raw & gate
        sig = np.where(ls | ss)[0]
        if len(sig) < 15:
            continue
        tp = round(g['rr'] * sl, 1)
        wr, nt = _wr_of(df, ls, ss, sl, tp, asset, mh)
        if wr is None or nt < 15:
            continue
        is_long = ls[sig]
        per_member.append(dict(geom=g, n=nt, wr=round(wr, 3),
                               n_long=int(is_long.sum()),
                               n_short=int((~is_long).sum())))
        # آماده‌سازیِ جای‌گشت: بارهای مجاز (warmup..n-hold)
        valid = np.arange(260, n - mh - 2)
        prepared.append(dict(geom=g, k=len(sig), labels=is_long.copy(),
                             valid=valid, tp=tp))
        if (gi + 1) % 8 == 0:
            print(f"    ... member {gi+1}/{len(mem)}", flush=True)

    if not per_member:
        print("!!! no viable member", flush=True)
        return None

    wr_obs = float(np.mean([m['wr'] for m in per_member]))
    n_tot = int(sum(m['n'] for m in per_member))
    wr_min = min(m['wr'] for m in per_member)
    wr_max = max(m['wr'] for m in per_member)
    print(f"\n  OBSERVED  family mean WR = {wr_obs:.3f}%   Σn = {n_tot:,}",
          flush=True)
    print(f"            member WR range = [{wr_min:.2f}, {wr_max:.2f}] "
          f"over {len(per_member)} members", flush=True)

    # ---------------- گامِ ۲: توزیعِ صفر با جای‌گشتِ زمانی ----------------
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    pip = se.ASSETS[asset]["pip"]
    cfg = se.ASSETS[asset]
    cost = cfg["spread_pip"] + 2 * cfg.get("slip_pip", 0.0)
    sl_d = sl * pip

    def perm_member_wr(pr):
        v = pr['valid']
        if len(v) <= pr['k']:
            return None
        pick = np.sort(rng.choice(v, size=pr['k'], replace=False))
        lab = rng.permutation(pr['labels'])   # نسبتِ long/short حفظ می‌شود
        tp_d = pr['tp'] * pip
        wins = 0
        used = 0
        last_exit = -1
        for si, is_long in zip(pick, lab):
            if si <= last_exit:
                continue                      # صفِ بی‌همپوشانیِ ساده
            eb = si + 1
            if eb >= n:
                continue
            ent = o[eb]
            hit = None
            kend = min(eb + mh, n)
            for k in range(eb, kend):
                if is_long:
                    if l[k] <= ent - sl_d:
                        hit = False; last_exit = k; break
                    if h[k] >= ent + tp_d:
                        hit = True; last_exit = k; break
                else:
                    if h[k] >= ent + sl_d:
                        hit = False; last_exit = k; break
                    if l[k] <= ent - tp_d:
                        hit = True; last_exit = k; break
            if hit is None:
                last = c[kend - 1]; last_exit = kend - 1
                pnl = (last - ent) if is_long else (ent - last)
                hit = (pnl / pip - cost) > 0
            used += 1
            if hit:
                wins += 1
        if used == 0:
            return None
        return 100.0 * wins / used

    wr_perm = []
    for b in range(n_perm):
        wrs = []
        for pr in prepared:
            w = perm_member_wr(pr)
            if w is not None:
                wrs.append(w)
        if wrs:
            wr_perm.append(float(np.mean(wrs)))
        if (b + 1) % 25 == 0:
            arr = np.array(wr_perm)
            print(f"    perm {b+1}/{n_perm}  null mean WR = {arr.mean():.3f} "
                  f"sd={arr.std(ddof=1):.3f} max={arr.max():.3f}", flush=True)

    wp = np.array(wr_perm)
    ge_wr = int((wp >= wr_obs).sum())
    p_wr = (1.0 + ge_wr) / (len(wp) + 1.0)
    z_wr = (wr_obs - wp.mean()) / wp.std(ddof=1) if wp.std(ddof=1) > 0 else 0.0
    bound = expected_max_z(1)
    verdict = ('FAMILY EDGE CONFIRMED'
               if (z_wr > bound and p_wr < 0.05) else 'NOT CONFIRMED')

    print(f"\n  {'='*72}", flush=True)
    print(f"  NULL (time-permuted, {len(wp)} draws):", flush=True)
    print(f"     WR mean={wp.mean():.3f} sd={wp.std(ddof=1):.3f} "
          f"range=[{wp.min():.3f}, {wp.max():.3f}]", flush=True)
    print(f"  OBSERVED WR={wr_obs:.3f}", flush=True)
    print(f"  LIFT     WR={wr_obs - wp.mean():+.3f}pp  ({z_wr:.2f}sigma)", flush=True)
    print(f"  p_emp    WR={p_wr:.5f}  (#draws>=obs: {ge_wr})", flush=True)
    print(f"  N=1 (pre-registered, no member selected) ⇒ luck bound = "
          f"{bound:.3f}sigma", flush=True)
    print(f"  ⇒ {verdict}", flush=True)
    print(f"  {'='*72}", flush=True)

    rec = dict(asset=asset, tf=tf,
               family=dict(r2=FAM_R2, sl_k=FAM_SL_K, sl_pip=sl,
                           n_open=list(FAM_N_OPEN), late=list(FAM_LATE),
                           spike=list(FAM_SPIKE), tight=list(FAM_TIGHT),
                           rr=list(FAM_RR)),
               n_members=len(per_member), n_trades_total=n_tot,
               wr_obs=round(wr_obs, 4), wr_member_min=wr_min,
               wr_member_max=wr_max, n_perm=len(wp),
               null_wr_mean=round(float(wp.mean()), 4),
               null_wr_sd=round(float(wp.std(ddof=1)), 4),
               null_wr_max=round(float(wp.max()), 4),
               lift_wr=round(wr_obs - float(wp.mean()), 4),
               z_wr=round(float(z_wr), 4), p_emp_wr=round(p_wr, 6),
               luck_bound_n1=round(float(bound), 4), verdict=verdict,
               members=per_member)
    if save:
        os.makedirs(OUT, exist_ok=True)
        with open(f"{OUT}/{asset}_{tf}_family.json", 'w') as fh:
            json.dump(rec, fh, default=float)
        print(f"  saved -> {OUT}/{asset}_{tf}_family.json", flush=True)
    return rec


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'H1'
    nb = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    run(asset, tf, n_perm=nb)
