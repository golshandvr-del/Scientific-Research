# -*- coding: utf-8 -*-
"""
S650 — «تشدیدِ چرخه-روند» (Ehlers Cycle-Turn Resumption) — فازِ اکتشاف
========================================================================
ایدهٔ لایه (نو، نه احیا):
  LONG  : trendflex(p_t) > 0  (رژیمِ صعودیِ کم‌تأخیر — مجوزِ جهت)
          و reflex(p_r) گذرِ صعودی از صفر  (کفِ چرخه درونِ روند — تایمینگ)
  SHORT : آینه‌ایِ کامل (تقارن — قانونِ هندسهٔ سخاوتمند)

  «خریدِ پولبک درونِ روند» با فیلترهای DSPِ مهندسی‌شدهٔ Ehlers — دسته‌ای که
  هرگز در هیچ لایهٔ ACCEPT استفاده نشده (فضای سفیدِ پروژه).

هندسهٔ منجمد (پیش از دیدنِ هر نتیجه، این‌جا ثبت):
  SL = 1.618 × ATR(34)   (Wilder RMA)
  RR = 1.618  ⇒  TP = 1.618 × SL  (TP > SL — قانونِ حفظِ بودجه، سپرِ H2/H9)
  max_hold = 34 کندل (فیبوناچی — ضدِ اشتباهِ #۷ «عددهای گرد»)

پروتکلِ چندگانگی: مسیرِ C (ممیزی §6.2)
  • این اسکریپت **فقط نیمهٔ اولِ** دادهٔ هر تایم‌فریم را می‌بیند.
  • فضای جست‌وجو: جفت‌های (p_trend, p_reflex) از فیبوناچی {13,21,34,55,89}
    با p_trend ≥ p_reflex و حذفِ 89/13 — همین‌جا پیش‌ثبت، نه بیشتر.
  • هندسه جست‌وجو **نمی‌شود** — منجمد است.
  • پیکربندیِ منتخب سپس در یک commitِ جداگانه پیش‌ثبت می‌شود و نیمهٔ دوم
    **یک بار و فقط یک بار** در اسکریپتِ داوریِ نهایی لمس خواهد شد.

دادهٔ اجباری: data/mt5_full (۱۵.۶ سال) — اگر src چیزِ دیگری بود، توقفِ فوری
(درسِ E-16: دو فایلِ همنام، دو بازهٔ کاملاً متفاوت؛ در mt5_full اصلاً H4/M2
وجود ندارد و fallback خاموش به دادهٔ کوتاه یعنی فاجعه).

چک‌پوینتِ اندک‌اندک: پس از هر TF یک JSON در results/_scan_S650/ نوشته و
commit+push می‌شود — منتظرِ اتمامِ همهٔ TFها نمی‌مانیم (بی‌ثباتیِ سندباکس).

اجرا:  python3 strategies/s650_ehlers_explore.py [TF ...]
       بدونِ آرگومان: همهٔ ۱۹ TF به ترتیبِ M1 اول.
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from numba import njit                                     # noqa: E402
from engine import scalp_engine as se                      # noqa: E402
from strategies.s346_fast import (barrier_outcomes,        # noqa: E402
                                  select_non_overlap)
from tools import s434_fast_data as fd                     # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S650')

# ---------------- پیش‌ثبتِ فضای جست‌وجو (مسیرِ C — قانونِ ۱ و ۲) ----------------
FIB = (13, 21, 34, 55, 89)
COMBOS = tuple((pt, pr) for pt in FIB for pr in FIB
               if pt >= pr and not (pt == 89 and pr == 13))
# ⇒ ۱۴ جفت (۵ قطری + ۹ غیرقطری بدونِ 89/13). در گزارش صریحاً شمارش می‌شود.

GEO_ATR_P = 34          # منجمد
GEO_SL_K = 1.618        # منجمد
GEO_RR = 1.618          # منجمد — TP > SL همیشه
GEO_HOLD = 34           # منجمد
BASELINE_MAX_EVENTS = 400_000   # سقفِ رویدادِ مبنا (حافظه/سرعت) — با stride

TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')

ASSET = 'XAUUSD'        # قانونِ صریحِ کاربر: هیچ وقتی برای EURUSD صرف نمی‌شود


# ================= پورتِ numbaی اندیکاتورها (برابری اثبات‌شده) =================
# مرجع: engine/indicator_bank.py — _ssf_arr و _flex. پورتِ خط‌به‌خط؛ تستِ
# برابری در main() پیش از هر اکتشاف اجرا می‌شود (اعتماد بی‌اثبات ممنوع).

@njit(cache=True)
def _ssf_nb(xv, period):
    n = xv.shape[0]
    out = np.empty(n)
    a = np.exp(-1.414 * np.pi / period)
    b = 2.0 * a * np.cos(1.414 * np.pi / period)
    c2 = b
    c3 = -a * a
    c1 = 1.0 - c2 - c3
    for i in range(n):
        if i < 2:
            out[i] = xv[i]
        else:
            out[i] = (c1 * (xv[i] + xv[i - 1]) / 2.0
                      + c2 * out[i - 1] + c3 * out[i - 2])
    return out


@njit(cache=True)
def _flex_nb(xv, period, trend):
    n = xv.shape[0]
    ssf = _ssf_nb(xv, period / 2.0)
    out = np.zeros(n)
    ms = 0.0
    for i in range(period, n):
        if trend:
            s = 0.0
            for k in range(1, period + 1):
                s += ssf[i] - ssf[i - k]
            s /= period
        else:
            slope = (ssf[i - period] - ssf[i]) / period
            s = 0.0
            for k in range(1, period + 1):
                s += ssf[i] + k * slope - ssf[i - k]
            s /= period
        ms = 0.04 * s * s + 0.96 * ms
        out[i] = s / np.sqrt(ms) if ms > 0.0 else 0.0
    return out


@njit(cache=True)
def _atr_rma_nb(h, l, c, period):
    n = h.shape[0]
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        a = h[i] - l[i]
        b = abs(h[i] - c[i - 1])
        d = abs(l[i] - c[i - 1])
        tr[i] = max(a, max(b, d))
    s = 0.0
    for i in range(period):
        s += tr[i]
    prev = s / period
    out[period - 1] = prev
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def parity_check():
    """برابریِ پورتِ numba با بانکِ رسمی — روی دادهٔ واقعیِ H1 (برشِ ۲۰k)."""
    from engine import indicator_bank as ib
    d = fd.load_fast(ASSET, 'H1')
    assert 'mt5_full' in d['src'], f"E-16! src={d['src']}"
    df = fd.as_dataframe(d).iloc[:20000].reset_index(drop=True)
    xv = df['close'].values.astype(np.float64)
    for p in (13, 34, 89):
        ref_t = ib.trendflex(df, period=p).values
        ref_r = ib.reflex(df, period=p).values
        my_t = _flex_nb(xv, p, True)
        my_r = _flex_nb(xv, p, False)
        et = float(np.nanmax(np.abs(ref_t - my_t)))
        er = float(np.nanmax(np.abs(ref_r - my_r)))
        assert et < 1e-9 and er < 1e-9, f"parity FAIL p={p}: {et}, {er}"
    print("[parity] trendflex/reflex numba == indicator_bank ✅ (max|Δ|<1e-9)",
          flush=True)


# ============================ اکتشاف روی یک TF ============================
def signals(close, pt, pr):
    tfv = _flex_nb(close, pt, True)
    rx = _flex_nb(close, pr, False)
    up = (rx[1:] > 0.0) & (rx[:-1] <= 0.0)
    dn = (rx[1:] < 0.0) & (rx[:-1] >= 0.0)
    ls = np.zeros(len(close), dtype=bool)
    ss = np.zeros(len(close), dtype=bool)
    ls[1:] = up & (tfv[1:] > 0.0)
    ss[1:] = dn & (tfv[1:] < 0.0)
    return ls, ss


def eval_events(df, sig_idx, is_long, atr, cfg):
    """رویدادها → سد دوطرفه → صفِ بی‌همپوشانی → آمار."""
    if len(sig_idx) == 0:
        return None
    sl_dist = GEO_SL_K * atr[sig_idx]
    tp_dist = GEO_RR * sl_dist
    fo = barrier_outcomes(df, sig_idx, is_long, sl_dist, tp_dist, GEO_HOLD,
                          float(cfg['pip']), float(cfg['spread_pip']),
                          float(cfg.get('slip_pip', 0.0)))
    if len(fo['entry_bar']) == 0:
        return None
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
    pnl = fo['pnl_pip'][keep]
    if len(pnl) == 0:
        return None
    win = pnl > 0
    return dict(n=int(len(pnl)), wr=float(win.mean() * 100.0),
                exp=float(pnl.mean()))


def explore_tf(tf):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    # 🔒 سپرِ E-16 — فقط دادهٔ کاملِ ۱۵.۶ ساله
    assert 'mt5_full' in src, f"E-16 TRAP! src={src} — دادهٔ کوتاه، توقف."
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    # 🔒 مسیرِ C — فقط نیمهٔ اول. نیمهٔ دوم این‌جا هرگز خوانده نمی‌شود.
    df = df_full.iloc[:half].reset_index(drop=True)
    close = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    atr = _atr_rma_nb(h, l, close, GEO_ATR_P)
    cfg = se.ASSETS[ASSET]

    warmup = max(4 * max(FIB), 4 * GEO_ATR_P, 300)
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[(valid >= warmup) & (valid + 1 + GEO_HOLD < half)]

    print(f"\n{'='*88}\n=== S650 explore :: {ASSET} {tf} — bars(full)={n_full:,} "
          f"half={half:,} valid={len(valid):,}\n    src={src}", flush=True)

    out = dict(layer='S650', tf=tf, asset=ASSET, src=src, n_bars_full=n_full,
               half_idx=half, first_half_only=True, path='C',
               geometry=dict(atr_p=GEO_ATR_P, sl_k=GEO_SL_K, rr=GEO_RR,
                             hold=GEO_HOLD),
               n_combos=len(COMBOS), combos=[])

    if len(valid) < 500:
        out['status'] = 'TOO_SHORT'
        return out

    # ---- مبنای غیرشرطی (تقریبِ اکتشافی؛ مبنای رسمیِ K≥500 در داوری) ----
    stride = max(1, len(valid) // BASELINE_MAX_EVENTS)
    vb = valid[::stride]
    base = {}
    for side, flag in (('long', True), ('short', False)):
        st = eval_events(df, vb, np.full(len(vb), flag), atr, cfg)
        if st is None:
            out['status'] = 'NO_BASELINE'
            return out
        base[side] = st
        print(f"    baseline {side:<5} n={st['n']:,} wr={st['wr']:.2f}% "
              f"(stride={stride})", flush=True)
    out['baseline'] = {k: {kk: v[kk] for kk in ('n', 'wr', 'exp')}
                       for k, v in base.items()}

    # ------------------------- ۱۴ جفتِ پیش‌ثبت‌شده -------------------------
    for pt, pr in COMBOS:
        ls, ss = signals(close, pt, pr)
        ok = np.isfinite(atr) & (atr > 0)
        ls &= ok
        ss &= ok
        ls[:warmup] = False
        ss[:warmup] = False
        li = np.where(ls)[0]
        si = np.where(ss)[0]
        rec = dict(p_trend=int(pt), p_reflex=int(pr))
        zs = []
        for side, idx, flag in (('long', li, True), ('short', si, False)):
            st = eval_events(df, idx, np.full(len(idx), flag), atr, cfg)
            if st is None or st['n'] < 30:
                rec[side] = dict(n=0 if st is None else st['n'])
                zs.append(-9.0)
                continue
            p0 = base[side]['wr'] / 100.0
            lift = st['wr'] - base[side]['wr']
            z = (lift / 100.0) * np.sqrt(st['n'] / (p0 * (1 - p0)))
            rec[side] = dict(n=st['n'], wr=round(st['wr'], 3),
                             exp=round(st['exp'], 3), lift=round(lift, 3),
                             z_est=round(float(z), 3))
            zs.append(float(z))
        rec['z_min'] = round(min(zs), 3)   # تقارن: هر دو سمت باید مهارت داشته باشند
        rec['z_sum'] = round(sum(max(z, 0.0) for z in zs), 3)
        out['combos'].append(rec)
        ln = rec.get('long', {})
        sn = rec.get('short', {})
        print(f"    pt={pt:>2} pr={pr:>2} | "
              f"L n={ln.get('n', 0):>7} z={ln.get('z_est', '—')} | "
              f"S n={sn.get('n', 0):>7} z={sn.get('z_est', '—')} | "
              f"z_min={rec['z_min']}", flush=True)

    ranked = sorted(out['combos'], key=lambda r: r['z_min'], reverse=True)
    out['best_by_zmin'] = ranked[0] if ranked else None
    out['status'] = 'OK'
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def _save_and_push(tf, out):
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, f'explore_{tf}.json')
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"    ✔ saved {fp}", flush=True)
    # چک‌پوینتِ گیت — قانونِ اندک‌اندک؛ خطای شبکه اکتشاف را متوقف نمی‌کند
    try:
        subprocess.run(['git', 'add', 'results/_scan_S650'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f'S650 explore checkpoint: {tf} (first-half only, path C)'],
            cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=ROOT,
                           capture_output=True, timeout=120)
            print(f"    ✔ git checkpoint pushed ({tf})", flush=True)
    except Exception as e:                                  # noqa: BLE001
        print(f"    ⚠ git checkpoint failed ({tf}): {e}", flush=True)


def main():
    tfs = sys.argv[1:] if len(sys.argv) > 1 else list(TFS)
    print(f"S650 explore — path C — TFs: {tfs}", flush=True)
    parity_check()
    for tf in tfs:
        try:
            out = explore_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S650', tf=tf, status='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_and_push(tf, out)
    print("\nS650 explore — DONE (all requested TFs)", flush=True)


if __name__ == '__main__':
    main()
