"""
s812_mtf_scan.py — غربال MTF لایه‌ی S812 (دریفت تقویمی آخرهفته) روی کارت‌های طلا
==============================================================================
قانون MTF (پیش‌ثبت §6): پس از حکم M1 (REJECT 15.9)، همه‌ی کارت‌های دیگر با
همان پنجره/جهت/هندسه‌ی بازوی برنده (WKND · LONG · none · SL=TP=1.618×ADR21)
غربال می‌شوند. max_hold بر حسب دقیقه ثابت (420 دقیقه) → تبدیل به کندلِ TF
(کف 1). رخداد: اولین کندل جمعه با hour ≥ 21 (زمان سرور). برای TFهای درشت
(≥H3) رخداد جمعه‌ی ساعت ≥21 ممکن است وجود نداشته باشد → NA صادقانه.

هر کارت: بازوی LONG روی **کل** تاریخ (هولد‌اوت M1 سوخته؛ کارت‌های دیگر
غربال‌اند نه آزمون تأییدی — `n_trials` = تعداد کارت‌های غربال‌شده) با null
جهت‌جای‌گشتی K=500 روی همان ورودی‌ها؛ checkpoint گیت بعد از هر کارت.
"""
import os, sys, json, subprocess
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import scalp_engine as se        # noqa: E402
from engine import rqs2                      # noqa: E402
from tools import s434_fast_data as fd       # noqa: E402
from strategies import s812_weekend_drift as L  # noqa: E402

OUTDIR = os.path.join(ROOT, 'results', '_s812')
OUT = os.path.join(OUTDIR, 'mtf_scan.json')
K = 500
SEED = 815
MH_MIN = 420  # دقیقه — بازوی برنده WKND
TF_MIN = {'M1': 1, 'M3': 3, 'M4': 4, 'M5': 5, 'M6': 6, 'M10': 10, 'M12': 12,
          'M15': 15, 'M20': 20, 'M30': 30, 'H1': 60, 'H2': 120, 'H3': 180,
          'H4': 240, 'H6': 360, 'H8': 480, 'H12': 720, 'D1': 1440}
ORDER = ['M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
         'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1']


def git_ckpt(tf, msg):
    try:
        subprocess.run(['git', 'add', OUT], cwd=ROOT, check=True,
                       capture_output=True)
        subprocess.run(['git', 'commit', '-q', '-m',
                        f'S812 MTF checkpoint {tf}: {msg}'], cwd=ROOT,
                       capture_output=True)
    except Exception as e:  # noqa: BLE001
        print('ckpt skipped:', e)


def scan_tf(tf, rng):
    d = fd.load_fast('XAUUSD', tf)
    assert 'mt5_full' in d['src']
    df = fd.as_dataframe(d)
    t = df['time'].values.astype(np.int64)
    agg = L.build_daily(t, df['high'].values, df['low'].values)
    adr_map, vref_map, qv_map = L.causal_maps(agg)
    ev = L.find_events(t)
    day = t // 86400
    n = len(df)
    ls, ss, slp, kept = L.arm_signals(ev, n, day, adr_map, vref_map, qv_map,
                                      'WKND', 'LONG', 'none')
    adr_bar = np.array([adr_map.get(dd, np.nan) for dd in day])
    slp_all = np.where(np.isfinite(adr_bar) & (adr_bar > 0),
                       np.maximum(L.SL_FLOOR, L.GEOM_K * adr_bar / 0.1), np.nan)
    mh = max(1, MH_MIN // TF_MIN[tf])
    out = dict(tf=tf, src=d['src'], n_events=int(kept), mh=mh)
    if kept < 30:
        out['note'] = 'NA — too few Friday>=21h bars on this TF'
        return out
    tr = L.run_arm(df, ls, ss, slp, mh)
    if tr is None or len(tr) == 0:
        out['note'] = 'no trades'; return out
    wr = float((tr['outcome'].values == 'win').mean() * 100)
    out.update(n=int(len(tr)), wr=round(wr, 3),
               pnl_pip=round(float(tr['pnl_pip'].sum()), 1))
    # null (الگوی S560/S437 — درس تلخ داوری M1 همین لایه): ورودهای **غیرشرطیِ تصادفی**
    # با همان تعداد، همان هندسه‌ی ADR-محور و همان max_hold؛ K جای‌گشت، هر دو سمت.
    # (جای‌گشتِ جهت روی *همان ورودی‌ها* در بازوی یک‌جهته همان‌گویانه است: perm_long == لایه.)
    n_sig = int(ls.sum())
    valid = np.where(np.isfinite(slp_all))[0]
    valid = valid[(valid > 200) & (valid < n - mh - 2)]
    perms_l, perms_s = [], []
    for k in range(K):
        pick = np.sort(rng.choice(valid, size=n_sig, replace=False))
        dirs = rng.integers(0, 2, n_sig)
        pl = np.zeros(n, bool); ps = np.zeros(n, bool)
        pl[pick[dirs == 1]] = True; ps[pick[dirs == 0]] = True
        ptr = L.run_arm(df, pl, ps, slp_all, mh)
        if ptr is None or len(ptr) == 0:
            continue
        isl = ptr['direction'].values == 'long'
        oc = ptr['outcome'].values == 'win'
        if isl.sum():
            perms_l.append(float(oc[isl].mean() * 100))
        if (~isl).sum():
            perms_s.append(float(oc[~isl].mean() * 100))
    # uncond: یک نمونه‌ی بزرگ یک‌جهته (n_sig×10) برای هر سمت
    big = np.sort(rng.choice(valid, size=min(len(valid), n_sig * 10), replace=False))
    bl = np.zeros(n, bool); bl[big] = True
    trL = L.run_arm(df, bl, np.zeros(n, bool), slp_all, mh)
    trS = L.run_arm(df, np.zeros(n, bool), bl, slp_all, mh)
    unc_l = float((trL['outcome'].values == 'win').mean() * 100)
    unc_s = float((trS['outcome'].values == 'win').mean() * 100)
    pm, psd, pmx = float(np.mean(perms_l)), float(np.std(perms_l)), float(np.max(perms_l))
    null = {'long': dict(uncond_wr=round(unc_l, 4), perm_mean=round(pm, 4),
                         perm_sd=round(psd, 4), perm_max=round(pmx, 4), perm_k=len(perms_l)),
            'short': dict(uncond_wr=round(unc_s, 4), perm_mean=round(float(np.mean(perms_s)), 4),
                          perm_sd=round(float(np.std(perms_s)), 4),
                          perm_max=round(float(np.max(perms_s)), 4), perm_k=len(perms_s))}
    ref = max(unc_l, pm)
    lift = wr - ref
    z = lift / psd if psd > 0 else 0.0
    out.update(uncond_long=round(unc_l, 3), perm_mean=round(pm, 3), perm_sd=round(psd, 3),
               perm_max=round(pmx, 3), lift_pp=round(lift, 3), z=round(z, 2))
    med_sl = float(np.nanmedian(slp[np.isfinite(slp)]))
    r = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=med_sl, tp_pip=med_sl,
                          bar_time=t, null=null, n_trials=len(ORDER),
                          split_bar=n // 2, close=df['close'].values)
    out.update(verdict=r['verdict'], rqs2=r['rqs2_score'],
               gates={k: r[k] for k in r if k.startswith('H') and k[1:].isdigit()},
               pf=r['metrics'].get('profit_factor'),
               exp_pip=r['metrics'].get('expectancy_pip'))
    return out


def main():
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    rng = np.random.default_rng(SEED)
    for tf in ORDER:
        if tf in res:
            continue
        print(f'--- {tf} ---', flush=True)
        try:
            r = scan_tf(tf, rng)
        except Exception as e:  # noqa: BLE001
            r = dict(tf=tf, note=f'error: {e}')
        res[tf] = r
        print(' ', {k: v for k, v in r.items() if k != 'gates'}, flush=True)
        json.dump(res, open(OUT, 'w'), indent=1, default=str)
        git_ckpt(tf, f"{r.get('verdict', r.get('note', '?'))} rqs2={r.get('rqs2', 'NA')} z={r.get('z', 'NA')}")
    print('MTF scan done.')


if __name__ == '__main__':
    main()
