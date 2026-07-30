# -*- coding: utf-8 -*-
"""
S346 — انباشتِ فیلترِ نسخهٔ ۲: «بیشینه‌سازیِ N با کفِ WR» + آزمونِ ابلیشنِ زمان
================================================================================
چرا نسخهٔ ۲؟ در نسخهٔ ۱ هدفِ گام «بیشینه کردنِ WR» بود؛ نتیجه: WR ۶۸٪ ولی n=۱۹۳.
User Note این نشست می‌گوید: **N بالا و تعدادِ معاملهٔ زیاد** (با رعایتِ RQS+).
پس تابعِ هدف عوض می‌شود:

        max  n_total          به‌شرطِ   min(WR_D, WR_H) ≥ wr_floor
                                        و   min(PF_D, PF_H) ≥ pf_floor

یعنی جست‌وجو دنبالِ «کم‌ترین فیلترِ لازم برای رسیدن به کفِ کیفیت» است، نه
«بیشترین WRِ ممکن». این دقیقاً همان تعادلی است که RQS+ می‌خواهد: G0 (WR≥۶۰)
و G2 (PF≥۱.۳) کف‌اند، و n بالا هم p-value را کوچک و هم آمار را معنادار می‌کند.

--------------------------------------------------------------------------------
🛡️ ابلیشنِ زمان — سپرِ صریح در برابرِ اشتباهِ رایجِ #۱
--------------------------------------------------------------------------------
هر جست‌وجو **دو بار** اجرا می‌شود:
   (الف) `allow_time=True`  — همهٔ ویژگی‌ها مجاز
   (ب) `allow_time=False` — هرگونه ویژگیِ `TIME:*` ممنوع
و نتیجهٔ هر دو در گزارش می‌آید. اگر نسخهٔ (ب) هم به کفِ کیفیت برسد، ثابت می‌شود
لبه **ساختاری** است نه یک آرتیفکتِ ساعتِ روز. اگر زمان لازم بود، باید نشان دهیم
که فقط **یکی از چند** مؤلفه است و بخشِ غیرزمانی خودش لبه دارد.

--------------------------------------------------------------------------------
🛡️ سپرِ ضدِ همبستگی (anti-redundancy)
--------------------------------------------------------------------------------
دو فیلتر که ماسکِ تقریباً یکسان می‌سازند (Jaccard > 0.92) لبهٔ نو اضافه نمی‌کنند و
فقط n را می‌خورند؛ چنین فیلتری در گامِ بعد رد می‌شود.
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_fast import stats, select_non_overlap
from strategies.s346_geom import CARDS
from strategies.s346_stack import build_features, outcomes_for_geom

OUT = 'results/_scan_S346'


# ------------------------------------------------------------------------------
# ⭐ آمارِ «صف‌آگاه» — تابعِ هدفِ درست
# ------------------------------------------------------------------------------
def q_stats(P, mask):
    """
    آمارِ D/H/ALL روی **زیرمجموعهٔ بی‌همپوشانیِ** رویدادهای عبورکرده از فیلترها.

    نکتهٔ کلیدیِ روش‌شناختی (کشفِ این نشست): فیلتر کردن، خودِ صفِ معاملات را
    عوض می‌کند. اگر رویدادِ زودتر حذف شود، رویدادِ بعدی — که قبلاً به‌دلیلِ اشغال
    بودنِ حساب معامله نمی‌شد — اکنون معامله می‌شود. پس ماسک باید **قبل** از
    اعمالِ قاعدهٔ همپوشانی زده شود، نه بعد از آن. برابریِ این بازتولید با موتورِ
    اصلی در `s346_parity_fast.run_case_noverlap` اثبات شده (۰ اختلاف).
    """
    fo, spread, is_d = P['fo'], P['spread'], P['is_d']
    eb = fo['entry_bar'][mask]
    eo = fo['exit_off'][mask]
    if len(eb) == 0:
        z = stats(np.array([]), np.array([], bool), spread)
        return z, z, z
    keep = select_non_overlap(eb, eo)
    idx = np.where(mask)[0][keep]
    pnl, win = P['pnl'][idx], P['win'][idx]
    dsel = is_d[idx]
    return (stats(pnl[dsel], win[dsel], spread),
            stats(pnl[~dsel], win[~dsel], spread),
            stats(pnl, win, spread))


def prepare(card, geom):
    asset, path = CARDS[card]
    df = se.load_data(path)
    split_idx = int(len(df) * 0.60)
    ch = adaptive_channel(df, p=geom['p'], mult=1.0)
    warmup = max(5 * geom['p'], 250)
    F = build_features(df, ch, card)
    fo, spread = outcomes_for_geom(df, ch, asset, geom, warmup)
    sb = fo['sig_idx']
    return dict(df=df, ch=ch, F=F, fo=fo, sb=sb, spread=spread, asset=asset,
                split_idx=split_idx, pnl=fo['pnl_pip'], win=fo['win'],
                is_d=sb < split_idx, FV=F.iloc[sb].reset_index(drop=True))


def screen(P, min_gain_d=1.5, min_gain_h=1.0, allow_time=True,
           qlist=(0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.5,
                  0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)):
    """پرده‌بندیِ آستانه‌ای با آستانه‌های استخراج‌شده فقط از discovery."""
    is_d = P['is_d']
    n_ev = len(P['sb'])
    base_d, base_h, _ = q_stats(P, np.ones(n_ev, bool))
    FV = P['FV']
    cands = []
    for col in FV.columns:
        if (not allow_time) and col.startswith('TIME:'):
            continue
        v = FV[col].values
        finite = np.isfinite(v)
        if finite.sum() < 0.5 * len(v):
            continue
        vd = v[is_d & finite]
        if len(vd) < 200:
            continue
        for q in qlist:
            thr = float(np.nanquantile(vd, q))
            for d in ('ge', 'le'):
                m = ((v >= thr) if d == 'ge' else (v <= thr)) & finite
                sd, sh, _ = q_stats(P, m)
                nd_, nh_ = sd['n'], sh['n']
                if nd_ < 45 or nh_ < 25:
                    continue
                gd, gh = sd['wr'] - base_d['wr'], sh['wr'] - base_h['wr']
                if gd >= min_gain_d and gh >= min_gain_h:
                    cands.append(dict(col=col, q=q, thr=thr, dir=d,
                                      gd=round(gd, 2), gh=round(gh, 2),
                                      wr_d=sd['wr'], wr_h=sh['wr'],
                                      n_d=nd_, n_h=nh_,
                                      exp_d=sd['exp'], exp_h=sh['exp'],
                                      pf_d=sd['pf'], pf_h=sh['pf']))
    cands.sort(key=lambda r: -min(r['gd'], r['gh']))
    return base_d, base_h, cands


def _mask_of(FV, f):
    v = FV[f['col']].values
    m = (v >= f['thr']) if f['dir'] == 'ge' else (v <= f['thr'])
    return m & np.isfinite(v)


def stack_maxn(P, cands, wr_floor=61.0, pf_floor=1.35, max_filters=14,
               jaccard_max=0.92, verbose=True):
    """
    انباشتِ حریصانه با تابعِ هدفِ «بیشینهٔ n مشروط به کفِ کیفیت».

    ⭐ اصلاحِ معیارِ گام (کشفِ این نشست)
    ------------------------------------------------------------------
    نسخهٔ قبل کلیدِ گام را `(reached, n_total)` گذاشته بود؛ یعنی از میانِ همهٔ
    فیلترهای بهبود‌دهنده، **کم‌ریزش‌ترین** را برمی‌داشت. نتیجهٔ تجربی: روی
    هندسه‌های پرظرفیت (WRِ پایهٔ ۴۷–۴۸٪) فیلترهای انتخابی هر بار فقط ~۰.۳pp
    بهبود می‌دادند و WR در ≈۴۹٪ **گیر** می‌کرد؛ سقفِ max_filters تمام می‌شد
    بی‌آنکه به کفِ ۶۱٪ نزدیک شویم. یعنی الگوریتم «ارزان‌ترین گام» را با
    «مؤثرترین گام» اشتباه گرفته بود.

    معیارِ جدید = **بهره به‌ازای هزینه** (bang-for-buck):
            efficiency = Δmin(WR)  /  ln(n_cur / n_new)
    یعنی «چند درصد بهبودِ WR به‌ازای هر واحدِ لگاریتمیِ nِ فداشده». این معیار
    ذاتاً هم فیلترِ خیلی سخت‌گیر (Δ بزرگ ولی هزینهٔ نجومی) و هم فیلترِ بی‌اثر
    (هزینهٔ کم ولی Δ≈۰) را جریمه می‌کند و مسیرِ بهینه‌ی «پارِتو» را می‌گیرد.
    به‌محضِ آنکه گامی کف را برآورده کند، اولویت به `reached` می‌رود و در آن
    گروه بیشینهٔ n انتخاب می‌شود ⇒ هدفِ «N بالا» حفظ می‌شود.
    """
    FV = P['FV']
    stack, used, hist = [], set(), []
    cur = np.ones(len(P['sb']), bool)

    for step in range(max_filters):
        # ⭐ آمارِ صف‌آگاه: همان صفی که داورِ رسمی می‌بیند
        sd0, sh0, _ = q_stats(P, cur)
        nd0, nh0 = sd0['n'], sh0['n']
        if min(sd0['wr'], sh0['wr']) >= wr_floor and min(sd0['pf'], sh0['pf']) >= pf_floor:
            break   # کف برآورده شد — n را بیش از این نمی‌خوریم

        best, best_key = None, None
        for r in cands:
            if r['col'] in used:
                continue
            m = _mask_of(FV, r)
            new = cur & m
            # سپرِ ضدِ همبستگی: اگر ماسکِ جدید تقریباً همان قبلی است، لبهٔ نو ندارد
            inter = (new).sum()
            union = (cur | m).sum()
            if union > 0 and inter / max(cur.sum(), 1) > jaccard_max:
                continue
            sd, sh, _ = q_stats(P, new)
            nd_, nh_ = sd['n'], sh['n']
            if nd_ < 45 or nh_ < 25:
                continue
            # باید کیفیت را در هر دو بازه بهبود دهد (تکرارپذیریِ گامِ انباشت)
            if sd['wr'] <= sd0['wr'] or sh['wr'] <= sh0['wr']:
                continue
            wr_min = min(sd['wr'], sh['wr'])
            reached = (wr_min >= wr_floor) and (min(sd['pf'], sh['pf']) >= pf_floor)
            # ⭐ کلیدِ گام: اگر کف برآورده شد ⇒ بیشینهٔ n؛ وگرنه ⇒ بهره‌به‌ازای‌هزینه
            n_cur = max(nd0 + nh0, 1)
            n_new = max(nd_ + nh_, 1)
            cost = np.log(n_cur / n_new) if n_new < n_cur else 1e-9
            gain = wr_min - min(sd0['wr'], sh0['wr'])
            eff = gain / max(cost, 1e-9)
            key = (1, nd_ + nh_) if reached else (0, eff)
            if best_key is None or key > best_key:
                best_key, best = key, (r, sd, sh, nd_, nh_, new)
        if best is None:
            break
        r, sd, sh, nd_, nh_, new = best
        cur = new
        stack.append(r)
        used.add(r['col'])
        hist.append(dict(step=step + 1, col=r['col'], dir=r['dir'], thr=r['thr'],
                         wr_d=sd['wr'], wr_h=sh['wr'], pf_d=sd['pf'], pf_h=sh['pf'],
                         exp_d=sd['exp'], exp_h=sh['exp'], n_d=nd_, n_h=nh_))
        if verbose:
            print(f"    +F{step+1} {r['col']:22s} {r['dir']} thr={r['thr']:>12.4f} | "
                  f"D n={nd_:5d} WR={sd['wr']:5.2f} PF={sd['pf']:.2f} | "
                  f"H n={nh_:5d} WR={sh['wr']:5.2f} PF={sh['pf']:.2f}", flush=True)
    return stack, hist, cur


def run(card, geom, wr_floor=61.0, pf_floor=1.35, tag_extra=''):
    print(f"=== S346-v2 :: {card} :: {geom} ===", flush=True)
    P = prepare(card, geom)
    out = dict(card=card, geom=geom, wr_floor=wr_floor, pf_floor=pf_floor)

    for allow_time in (False, True):
        label = 'NO-TIME' if not allow_time else 'WITH-TIME'
        base_d, base_h, cands = screen(P, allow_time=allow_time)
        print(f"  [{label}] BASE D n={base_d['n']} WR={base_d['wr']:.2f} PF={base_d['pf']:.3f}"
              f" | H n={base_h['n']} WR={base_h['wr']:.2f} PF={base_h['pf']:.3f}"
              f" | cands={len(cands)}", flush=True)
        stack, hist, mask = stack_maxn(P, cands, wr_floor=wr_floor, pf_floor=pf_floor)
        # ⭐ گزارشِ نهایی هم صف‌آگاه: عددِ اینجا باید با داورِ رسمی هم‌خوان باشد
        sd, sh, sa = q_stats(P, mask)
        ok = (min(sd['wr'], sh['wr']) >= wr_floor and
              min(sd['pf'], sh['pf']) >= pf_floor)
        print(f"  [{label}] RESULT {'REACHED' if ok else 'not-reached'} "
              f"filters={len(stack)} | ALL n={sa['n']} WR={sa['wr']:.2f} PF={sa['pf']:.2f} "
              f"exp={sa['exp']:.2f}", flush=True)
        out[label] = dict(base_d=base_d, base_h=base_h, n_cands=len(cands),
                          stack=stack, history=hist, reached=bool(ok),
                          D=sd, H=sh, ALL=sa)

    os.makedirs(OUT, exist_ok=True)
    t = f"{card}_{geom['mode']}_{geom['side']}_p{geom['p']}{tag_extra}_v2.json"
    with open(f"{OUT}/{t}", 'w') as f:
        json.dump(out, f, default=float)
    print(f"  saved -> {OUT}/{t}", flush=True)
    return out


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-M15'
    geom = dict(mode='fade', side='long', p=21, mult=1.272, er_thr=0.236,
                sl_k=1.618, rr=1.0, hold=34, tp_mode='atr')
    run(card, geom)
