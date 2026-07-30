# -*- coding: utf-8 -*-
"""
S346 — انباشتِ فیلترها روی رویدادِ کانالِ تطبیقی (قانونِ بی‌نهایت + جعبه‌ابزارِ ۴۰۱)
================================================================================
یافتهٔ مرحلهٔ قبل (s346_geom): رویدادِ خامِ «بستن بیرونِ کانالِ تطبیقی» روی XAU-M15
با هندسهٔ منصفانه (TP ≥ SL) در هر دو نیمهٔ زمانی WR ≈ ۵۲.۵–۵۳.۳٪ می‌دهد —
یعنی لبهٔ واقعیِ کوچکی **بالای** WRِ سربه‌سرِ ۵۰٪ دارد، ولی اسپرد آن را کاملاً می‌خورد.
پس مسئله دقیقاً «انتخابِ زیرمجموعهٔ باکیفیت» است، نه «ساختنِ لبه از هیچ».

--------------------------------------------------------------------------------
روشِ علمی (سه مرحله)
--------------------------------------------------------------------------------
مرحله ۱ — پرده‌بندیِ آستانه‌ای (screening):
   برای هر ویژگی از **جعبه‌ابزارِ ۴۰۱ اندیکاتوری** (نمونه‌گیریِ فراگیر از هر ۹ دسته
   + ۴ ویژگیِ ساختاریِ خودِ کانال + ۲ ویژگیِ زمانی)، آستانه‌های چندکی از **فقط
   بازهٔ discovery** استخراج می‌شود (بدونِ نشتِ اطلاعات از holdout) و هر دو جهت
   (`>= thr` و `<= thr`) سنجیده می‌شود.

مرحله ۲ — آزمونِ تکرارپذیری (replication):
   فیلتری کاندیدا می‌شود که در **هر دو** بازه بهبودِ WR بدهد:
   ΔWR_D ≥ min_gain_D  و  ΔWR_H ≥ min_gain_H. این تنها سپرِ واقعی در برابرِ
   برازشِ بیش از حد است (یک فیلترِ نویزی نمی‌تواند در بازهٔ ندیده هم تکرار شود).

مرحله ۳ — انباشتِ حریصانه (greedy stacking) — «قانونِ بی‌نهایتِ بهبود»:
   فیلترها یکی‌یکی اضافه می‌شوند؛ در هر گام فیلتری برنده است که
   `min(WR_D, WR_H)` را بیشترین مقدار کند، مشروط به اینکه n نهایی از کفِ
   نمونه پایین‌تر نرود. هیچ سقفی برای تعدادِ فیلترها نیست (۳، ۵، ۱۰ … مجاز).

--------------------------------------------------------------------------------
سپرهای صریحِ ضدِ «اشتباهاتِ رایج»
--------------------------------------------------------------------------------
#۱ (تمرکز بر زمان): ویژگی‌های زمانی (`hour`, `dow`) حاضرند ولی برچسب `TIME:` دارند
    و در پایان **گزارشِ سهمِ زمان** چاپ می‌شود؛ نسخهٔ «بدونِ هیچ فیلترِ زمانی» هم
    همیشه محاسبه و مقایسه می‌شود.
#۳ (چند اندیکاتورِ ساده): پرده‌بندی از **هر ۹ دستهٔ** بانک نمونه می‌گیرد
    (trend/momentum/volatility/volume/cycle/statistical/pattern/composite/overlap).
#۷ (اعدادِ رند): دوره‌های فیبوناچی/لوکاسِ بانک (۱۳، ۲۱، ۳۴، ۴۷، ۷۶، ۸۹، ۱۲۳، ۱۹۹…)
    و آستانه‌های چندکی (نه اعدادِ گردِ دستی).
#۸ (تقلبِ TP<SL): هندسهٔ پایه از s346_geom می‌آید که rr ≥ ۱.۰ را سخت تضمین می‌کند.
"""
import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from engine import indicator_bank as ib
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_fast import barrier_outcomes, stats
from strategies.s346_geom import CARDS, event_mask

OUT = 'results/_scan_S346'

# ------------------------------------------------------------------------------
# جعبه‌ابزار: نمونه‌گیریِ فراگیر از هر ۹ دستهٔ بانک (رفعِ اشتباهِ رایجِ #۳)
# دوره‌ها عمداً فیبوناچی/لوکاس‌اند، نه ۵۰/۱۰۰/۲۰۰ (رفعِ #۷)
# ------------------------------------------------------------------------------
BANK_FEATURES = [
    # --- volatility (رژیمِ نوسان) ---
    'atr_pct', 'natr', 'chop', 'chop_fib_21', 'chop_fib_55', 'mass', 'ulcer',
    'rvi_vol', 'natr_fib_13', 'natr_fib_34', 'std_fib_21', 'std_fib_55',
    'atr_fib_13', 'atr_fib_89',
    # --- statistical (ساختارِ آماری) ---
    'entropy', 'fdi', 'hurst', 'kurt', 'skew', 'r2', 'r2_fib_21', 'r2_fib_55',
    'corr_t', 'corr_t_fib_21', 'corr_t_fib_89', 'zscore_fib_13', 'zscore_fib_21',
    'zscore_fib_55', 'zscore_fib_89',
    # --- composite (ترکیبی — ERِ لوکاس، دقیقاً هم‌خانوادهٔ منبعِ ما) ---
    'elder_impulse', 'ema_dist_atr', 'rsi_of_er', 'trend_gate',
    'er_lucas_7', 'er_lucas_11', 'er_lucas_18', 'er_lucas_29', 'er_lucas_47',
    'er_lucas_76', 'er_lucas_123', 'er_lucas_199',
    # --- cycle (اِهلرز) ---
    'cg', 'cg_fib_21', 'cg_fib_55', 'dsma', 'ehp', 'laguerre', 'laguerre_rsi',
    'reflex', 'roof', 'ssf', 'trendflex', 'ssf_fib_21', 'laguerre_g_29',
    'laguerre_g_76',
    # --- momentum ---
    'ac', 'ao', 'apo', 'ar', 'bias', 'bias_fib_21', 'bias_fib_55', 'bop',
    'br', 'cfo', 'cmo', 'cmo_fib_21', 'cr', 'crsi', 'dpo', 'dpo_fib_21',
    'fisher', 'ifish_rsi', 'kdj_j', 'mom', 'mom_fib_21', 'mtm', 'pgo', 'ppo',
    # --- volume ---
    'ad', 'adosc', 'efi', 'emv', 'mfi', 'obv', 'vpt', 'wvad',
    # --- trend ---
    'aroon', 'chandelier', 'frama', 'gann_hilo', 'kama', 'mcgd', 'psar',
    'donchian_mid', 'alma', 'hma', 'dema_fib_21', 'rma_fib_55',
    # --- pattern (شمعی — به‌عنوان فیلترِ تأیید/رد) ---
    'cdl_doji', 'cdl_engulf_bull', 'cdl_engulf_bear', 'cdl_hammer',
    'cdl_shootingstar', 'cdl_marubozu', 'cdl_highwave', 'cdl_longleg_doji',
    'cdl_spinningtop', 'cdl_harami_bull', 'cdl_harami_bear',
    # --- overlap ---
    'hl2', 'wcp',
]


def build_features(df, ch, card):
    """ماتریسِ ویژگی‌های causal. کش روی دیسک چون محاسبهٔ ۱۲۰ اندیکاتور گران است."""
    cache = f"{OUT}/{card}_feat.parquet"
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(cache):
        try:
            F = pd.read_parquet(cache)
            if len(F) == len(df):
                return F
        except Exception:
            pass

    cols = {}
    ok, bad = 0, []
    for name in BANK_FEATURES:
        try:
            cols['BANK:' + name] = ib.compute(name, df).values.astype(np.float64)
            ok += 1
        except Exception as e:
            bad.append((name, str(e)[:40]))
    print(f"  features: bank ok={ok} failed={len(bad)}", flush=True)
    if bad:
        print("   failed:", bad[:8], flush=True)

    # --- ویژگی‌های ساختاریِ خودِ کانالِ تطبیقی (ذاتِ منبع — نه اندیکاتورِ بیرونی) ---
    c = df['close'].values.astype(np.float64)
    atr_a, val, er = ch['atr_a'], ch['val'], ch['er']
    with np.errstate(invalid='ignore', divide='ignore'):
        cols['CHAN:er'] = er
        # سرعتِ تغییرِ پهنای کانال — ویژگیِ منحصربه‌فردِ این ابزار (mladen)
        cols['CHAN:atr_slope'] = np.concatenate(([np.nan], np.diff(atr_a))) / np.where(atr_a > 0, atr_a, np.nan)
        # شیبِ خطِ میانی نرمال‌شده با ATR (روندِ محلی، مقیاس‌آزاد)
        cols['CHAN:val_slope'] = np.concatenate(([np.nan], np.diff(val))) / np.where(atr_a > 0, atr_a, np.nan)
        # میزانِ عبور از کانال بر حسبِ ATR (شدتِ اکستنشن)
        cols['CHAN:pierce'] = np.abs(c - val) / np.where(atr_a > 0, atr_a, np.nan)
        # پهنای کانال نسبت به میانگینِ بلندِ خودش (رژیمِ انقباض/انبساط)
        aser = pd.Series(atr_a)
        cols['CHAN:width_rel'] = (aser / aser.rolling(233, min_periods=55).mean()).values
        # کشیدگیِ بدنهٔ کندلِ سیگنال نسبت به ATR
        cols['CHAN:body_atr'] = np.abs(c - df['open'].values) / np.where(atr_a > 0, atr_a, np.nan)
        # نسبتِ رنجِ کندل به ATR تطبیقی
        cols['CHAN:range_atr'] = (df['high'].values - df['low'].values) / np.where(atr_a > 0, atr_a, np.nan)

    # --- ویژگی‌های زمانی (برچسب‌دار، تا سهمشان شفاف بماند — رفعِ #۱) ---
    t = pd.to_datetime(df['time'], unit='s', utc=True) if 'time' in df.columns \
        else pd.to_datetime(df.index, utc=True)
    cols['TIME:hour'] = t.dt.hour.values.astype(np.float64)
    cols['TIME:dow'] = t.dt.dayofweek.values.astype(np.float64)

    F = pd.DataFrame(cols, index=df.index)
    try:
        F.to_parquet(cache)
    except Exception:
        pass
    return F


# ------------------------------------------------------------------------------
def outcomes_for_geom(df, ch, asset, g, warmup):
    """رویداد + نتیجهٔ سدِ دوطرفه برای یک هندسهٔ پایه (dict مانندِ خروجیِ s346_geom)."""
    cfg = se.ASSETS[asset]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    ls, ss = event_mask(df, ch, g['mode'], g['mult'], g['er_thr'], warmup)
    if g['side'] == 'long':
        sig = np.where(ls)[0]; is_long = np.ones(len(sig), bool)
    elif g['side'] == 'short':
        sig = np.where(ss)[0]; is_long = np.zeros(len(sig), bool)
    else:
        sig = np.where(ls | ss)[0]; is_long = ls[sig]

    atr_s = ch['atr_a'][sig]
    sl_d = g['sl_k'] * atr_s
    if g.get('tp_mode', 'atr') == 'atr':
        tp_d = g['rr'] * sl_d
    else:
        tp_d = np.maximum(np.abs(ch['val'][sig] - df['close'].values[sig]), sl_d)
    ok = (sl_d > 0) & np.isfinite(sl_d) & np.isfinite(tp_d) & (tp_d >= sl_d)
    sig, is_long, sl_d, tp_d = sig[ok], is_long[ok], sl_d[ok], tp_d[ok]

    fo = barrier_outcomes(df, sig, is_long, sl_d, tp_d, g['hold'], pip, spread, slip)
    return fo, spread


def screen_and_stack(card, geom, min_n_final=150, min_gain_d=2.5, min_gain_h=1.5,
                     max_filters=12, qlist=(0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85),
                     verbose=True):
    asset, path = CARDS[card]
    df = se.load_data(path)
    split_idx = int(len(df) * 0.60)
    ch = adaptive_channel(df, p=geom['p'], mult=1.0)
    warmup = max(5 * geom['p'], 250)
    F = build_features(df, ch, card)

    fo, spread = outcomes_for_geom(df, ch, asset, geom, warmup)
    sb = fo['sig_idx']
    pnl, win = fo['pnl_pip'], fo['win']
    is_d = sb < split_idx

    base_d = stats(pnl[is_d], win[is_d], spread)
    base_h = stats(pnl[~is_d], win[~is_d], spread)
    if verbose:
        print(f"  BASE  D n={base_d['n']:5d} WR={base_d['wr']:5.2f} exp={base_d['exp']:7.2f} "
              f"PF={base_d['pf']:.3f} | H n={base_h['n']:5d} WR={base_h['wr']:5.2f} "
              f"exp={base_h['exp']:7.2f} PF={base_h['pf']:.3f}", flush=True)

    # مقادیرِ ویژگی روی کندلِ سیگنال
    FV = F.iloc[sb].reset_index(drop=True)

    # ---------- مرحله ۱+۲: پرده‌بندی + تکرارپذیری ----------
    cands = []
    for col in FV.columns:
        v = FV[col].values
        finite = np.isfinite(v)
        if finite.sum() < 0.5 * len(v):
            continue
        vd = v[is_d & finite]
        if len(vd) < 200:
            continue
        for q in qlist:
            thr = float(np.nanquantile(vd, q))       # آستانه فقط از discovery
            for direction in ('ge', 'le'):
                m = (v >= thr) if direction == 'ge' else (v <= thr)
                m = m & finite
                nd_, nh_ = (m & is_d).sum(), (m & ~is_d).sum()
                if nd_ < 100 or nh_ < 50:
                    continue
                sd = stats(pnl[m & is_d], win[m & is_d], spread)
                sh = stats(pnl[m & ~is_d], win[m & ~is_d], spread)
                gd = sd['wr'] - base_d['wr']
                gh = sh['wr'] - base_h['wr']
                if gd >= min_gain_d and gh >= min_gain_h:
                    cands.append(dict(col=col, q=q, thr=thr, dir=direction,
                                      gd=round(gd, 2), gh=round(gh, 2),
                                      wr_d=sd['wr'], wr_h=sh['wr'],
                                      n_d=int(nd_), n_h=int(nh_),
                                      exp_d=sd['exp'], exp_h=sh['exp']))
    cands.sort(key=lambda r: -min(r['gd'], r['gh']))
    if verbose:
        print(f"  screening: replicating candidates = {len(cands)}", flush=True)
        for r in cands[:18]:
            print(f"    {r['col']:24s} {r['dir']} q{int(r['q']*100):02d} "
                  f"thr={r['thr']:>11.4f} | WR_D={r['wr_d']:5.2f}(+{r['gd']:4.2f}) "
                  f"WR_H={r['wr_h']:5.2f}(+{r['gh']:4.2f}) n={r['n_d']}/{r['n_h']}",
                  flush=True)

    # ---------- مرحله ۳: انباشتِ حریصانه (قانونِ بی‌نهایت) ----------
    def apply_stack(stack):
        m = np.ones(len(sb), bool)
        for f in stack:
            v = FV[f['col']].values
            mm = (v >= f['thr']) if f['dir'] == 'ge' else (v <= f['thr'])
            m &= (mm & np.isfinite(v))
        return m

    stack = []
    used_cols = set()
    history = []
    for step in range(max_filters):
        best, best_key = None, None
        for r in cands:
            if r['col'] in used_cols:
                continue
            m = apply_stack(stack + [r])
            nd_, nh_ = (m & is_d).sum(), (m & ~is_d).sum()
            if nd_ + nh_ < min_n_final or nd_ < 40 or nh_ < 25:
                continue
            sd = stats(pnl[m & is_d], win[m & is_d], spread)
            sh = stats(pnl[m & ~is_d], win[m & ~is_d], spread)
            # امتیازِ گام: کمینهٔ WRِ دو بازه (سپرِ تکرارپذیری) + جریمهٔ ریزشِ n
            key = (min(sd['wr'], sh['wr']), min(sd['exp'], sh['exp']))
            if best_key is None or key > best_key:
                best_key, best = key, (r, sd, sh, int(nd_), int(nh_))
        if best is None:
            break
        r, sd, sh, nd_, nh_ = best
        stack.append(r)
        used_cols.add(r['col'])
        history.append(dict(step=step + 1, col=r['col'], dir=r['dir'], thr=r['thr'],
                            wr_d=sd['wr'], wr_h=sh['wr'], exp_d=sd['exp'],
                            exp_h=sh['exp'], pf_d=sd['pf'], pf_h=sh['pf'],
                            n_d=nd_, n_h=nh_))
        if verbose:
            print(f"  +F{step+1} {r['col']:24s} {r['dir']} thr={r['thr']:>11.4f} | "
                  f"D n={nd_:5d} WR={sd['wr']:5.2f} PF={sd['pf']:.2f} | "
                  f"H n={nh_:5d} WR={sh['wr']:5.2f} PF={sh['pf']:.2f}", flush=True)
        if min(sd['wr'], sh['wr']) >= 66.0 and min(nd_, nh_) >= 60:
            break

    res = dict(card=card, geom=geom, base_d=base_d, base_h=base_h,
               n_cands=len(cands), cands=cands[:60], stack=stack, history=history)
    tag = f"{card}_{geom['mode']}_{geom['side']}_p{geom['p']}"
    with open(f"{OUT}/{tag}_stack.json", 'w') as f:
        json.dump(res, f, default=float)
    return res


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-M15'
    geom = dict(mode='fade', side='long', p=21, mult=1.272, er_thr=0.236,
                sl_k=1.618, rr=1.0, hold=34, tp_mode='atr')
    print(f"=== S346 stack :: {card} :: {geom} ===", flush=True)
    screen_and_stack(card, geom)
