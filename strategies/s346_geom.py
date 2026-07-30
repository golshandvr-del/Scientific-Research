# -*- coding: utf-8 -*-
"""
S346 — اکتشافِ «سطحِ هندسی» رویدادِ کانالِ تطبیقی، با قیدِ سختِ ضدِ تقلب
================================================================================
هدفِ این ماژول: پیدا کردنِ ناحیه‌ای از فضای (هندسهٔ کانال × SL/TP × افقِ نگهداری)
که در آن رویداد **به‌طورِ طبیعی** WR بالا بدهد، *بدونِ* دست‌کاریِ نسبتِ TP/SL.

--------------------------------------------------------------------------------
⛔ قیدِ سختِ ضدِ تقلب (پاسخِ صریح به اشتباهِ رایجِ #۸)
--------------------------------------------------------------------------------
اشتباهِ #۸: «بالا بردنِ WR با TP کوچک‌تر از SL». در این ماژول
        rr = tp_k / sl_k  و  **rr ≥ 1.0 اجباری است**.
یعنی TP هرگز کوچک‌تر از SL نیست ⇒ WRِ سربه‌سر = sl/(sl+tp) ≤ ۵۰٪ ⇒ هر WRِ ۶۰٪+
یک لبهٔ **واقعی** است، نه محصولِ هندسه. (گیتِ G1 خودِ RQS+ هم همین را می‌سنجد؛
ما یک لایه محافظتِ اضافه در *فضای جست‌وجو* می‌گذاریم تا حتی وسوسه‌اش هم نباشد.)

--------------------------------------------------------------------------------
دو خانوادهٔ هدف‌گذاریِ TP (هر دو آزموده می‌شوند)
--------------------------------------------------------------------------------
A) `atr` — کلاسیک: SL = sl_k·atr_a ، TP = rr·SL          (شناور با نوسان)
B) `mid` — **ساختاری**: TP = فاصلهٔ واقعی تا خطِ میانیِ کانال (val) در کندلِ سیگنال،
          SL = sl_k·atr_a. این هدفِ *طبیعیِ* منطقِ fade است (بازگشت به میانه)،
          نه یک عددِ دلخواه. برای پذیرش، همین‌جا هم rr_eff = TP/SL ≥ ۱ الزامی است.

--------------------------------------------------------------------------------
ضدِ برازشِ بیش از حد
--------------------------------------------------------------------------------
هر ترکیب روی **دو بازهٔ زمانیِ مجزا** سنجیده می‌شود:
   D (discovery) = ۶۰٪ نخستِ داده     ،     H (holdout) = ۴۰٪ پایانی
شرطِ «تکرارپذیری» (REPL): WR و expectancy در **هر دو** بازه هم‌جهت و مثبت باشند.
ترکیبی که فقط در D خوب است، نویز است و کنار گذاشته می‌شود.

اعدادِ پارامترها عمداً **غیر-رند** (فیبوناچی/اعدادِ اول) انتخاب شده‌اند تا اشتباهِ
رایجِ #۷ («۵۰/۱۰۰/۲۰۰») رخ ندهد: p ∈ {13,21,34,55,89} و mult ∈ {1.272,…,2.618}.
"""
import sys
import os
import json
import itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_fast import barrier_outcomes, stats

OUT = 'results/_scan_S346'

CARDS = {
    'XAUUSD-M1':  ('XAUUSD', 'data/XAUUSD_M1.csv'),
    'XAUUSD-M5':  ('XAUUSD', 'data/XAUUSD_M5.csv'),
    'XAUUSD-M15': ('XAUUSD', 'data/XAUUSD_M15.csv'),
    'XAUUSD-M30': ('XAUUSD', 'data/XAUUSD_M30.csv'),
    'XAUUSD-H1':  ('XAUUSD', 'data/XAUUSD_H1.csv'),
    'XAUUSD-H4':  ('XAUUSD', 'data/XAUUSD_H4.csv'),
    'EURUSD-M1':  ('EURUSD', 'data/EURUSD_M1.csv'),
    'EURUSD-M5':  ('EURUSD', 'data/EURUSD_M5.csv'),
    'EURUSD-M15': ('EURUSD', 'data/EURUSD_M15.csv'),
    'EURUSD-M30': ('EURUSD', 'data/EURUSD_M30.csv'),
    'EURUSD-H1':  ('EURUSD', 'data/EURUSD_H1.csv'),
}

P_GRID    = [13, 21, 34, 55, 89]
MULT_GRID = [1.272, 1.618, 2.058, 2.618]
ER_GRID   = [0.146, 0.191, 0.236, 0.309, 0.382]
SLK_GRID  = [0.618, 1.0, 1.272, 1.618, 2.058]
RR_GRID   = [1.0, 1.272, 1.618, 2.058]      # ⛔ هیچ مقداری < 1.0 مجاز نیست
HOLD_GRID = [13, 21, 34, 55, 89]


def channel_cache(df, p_list):
    """val/atr_a/er فقط به p وابسته‌اند (mult ارزان است) ⇒ یک‌بار محاسبه."""
    cache = {}
    for p in p_list:
        cache[p] = adaptive_channel(df, p=p, mult=1.0)   # mult بی‌اثر بر val/atr_a
    return cache


def event_mask(df, ch, mode, mult, er_thr, warmup):
    c = df['close'].values.astype(np.float64)
    up = ch['val'] + mult * ch['atr_a']
    dn = ch['val'] - mult * ch['atr_a']
    er = ch['er']
    out_up = c >= up
    out_dn = c <= dn
    if mode == 'fade':
        reg = er < er_thr
        ls, ss = out_dn & reg, out_up & reg
    else:
        reg = er > er_thr
        ls, ss = out_up & reg, out_dn & reg
    valid = np.isfinite(er) & np.isfinite(ch['atr_a']) & (ch['atr_a'] > 0)
    valid[:warmup] = False
    return (ls & valid), (ss & valid)


def eval_combo(df, ch, asset, mode, mult, er_thr, side, sl_k, rr, hold,
               tp_mode, split_idx, pip, spread, slip, warmup):
    ls, ss = event_mask(df, ch, mode, mult, er_thr, warmup)
    if side == 'long':
        sig = np.where(ls)[0]
        is_long = np.ones(len(sig), dtype=bool)
    elif side == 'short':
        sig = np.where(ss)[0]
        is_long = np.zeros(len(sig), dtype=bool)
    else:
        sig = np.where(ls | ss)[0]
        is_long = ls[sig]
    if len(sig) < 60:
        return None

    atr_s = ch['atr_a'][sig]
    sl_d = sl_k * atr_s
    if tp_mode == 'atr':
        tp_d = rr * sl_d
    else:  # 'mid' — هدفِ ساختاری: فاصلهٔ واقعی تا خطِ میانی
        c = df['close'].values[sig]
        tp_d = np.abs(ch['val'][sig] - c)
        # ⛔ قیدِ ضدِ تقلب روی نسخهٔ ساختاری هم اعمال می‌شود
        tp_d = np.maximum(tp_d, sl_d * 1.0)

    ok = (sl_d > 0) & np.isfinite(sl_d) & np.isfinite(tp_d) & (tp_d >= sl_d)
    sig, is_long, sl_d, tp_d = sig[ok], is_long[ok], sl_d[ok], tp_d[ok]
    if len(sig) < 60:
        return None

    fo = barrier_outcomes(df, sig, is_long, sl_d, tp_d, hold,
                          pip, spread, slip)
    sb = fo['sig_idx']
    pnl, win = fo['pnl_pip'], fo['win']
    dmask = sb < split_idx
    hmask = ~dmask
    if dmask.sum() < 30 or hmask.sum() < 30:
        return None
    sd = stats(pnl[dmask], win[dmask], spread)
    sh = stats(pnl[hmask], win[hmask], spread)
    sa = stats(pnl, win, spread)
    rr_eff = float(np.median(tp_d / sl_d))
    return dict(mode=mode, mult=mult, er_thr=er_thr, side=side, sl_k=sl_k,
                rr=rr, hold=hold, tp_mode=tp_mode, rr_eff=round(rr_eff, 3),
                D=sd, H=sh, ALL=sa)


def scan_card(card, p_list=None, top_k=40):
    asset, path = CARDS[card]
    cfg = se.ASSETS[asset]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    df = se.load_data(path)
    split_idx = int(len(df) * 0.60)
    p_list = p_list or P_GRID
    print(f"=== {card} bars={len(df)} split@{split_idx} ===", flush=True)
    cache = channel_cache(df, p_list)

    rows = []
    for p in p_list:
        ch = cache[p]
        warmup = max(5 * p, 250)
        for mode, mult, er_thr, side, sl_k, rr, hold, tp_mode in itertools.product(
                ['fade', 'breakout'], MULT_GRID, ER_GRID, ['long', 'short'],
                SLK_GRID, RR_GRID, HOLD_GRID, ['atr', 'mid']):
            if tp_mode == 'mid' and rr != 1.0:
                continue          # در حالتِ ساختاری، rr از خودِ ساختار می‌آید
            r = eval_combo(df, ch, asset, mode, mult, er_thr, side, sl_k, rr,
                           hold, tp_mode, split_idx, pip, spread, slip, warmup)
            if r is None:
                continue
            r['p'] = p
            rows.append(r)
        print(f"  p={p} done, rows={len(rows)}", flush=True)
        os.makedirs(OUT, exist_ok=True)
        with open(f"{OUT}/{card}_geom.json", 'w') as f:
            json.dump(rows, f)

    # --- گزارش: تکرارپذیرها (WR≥58 در هر دو بازه + exp>0 در هر دو) ---
    repl = [r for r in rows
            if r['D']['wr'] >= 58.0 and r['H']['wr'] >= 58.0
            and r['D']['exp'] > 0 and r['H']['exp'] > 0]
    repl.sort(key=lambda r: -(min(r['D']['wr'], r['H']['wr'])))
    print(f"\n>>> {card}: rows={len(rows)}  replicating(WR>=58 both)={len(repl)}",
          flush=True)
    for r in repl[:top_k]:
        print(f"  {r['mode']:8s} {r['side']:5s} tp={r['tp_mode']:3s} p={r['p']:2d} "
              f"m={r['mult']:.3f} er={r['er_thr']:.3f} sl={r['sl_k']:.3f} "
              f"rr={r['rr_eff']:.2f} h={r['hold']:2d} | "
              f"D n={r['D']['n']:5d} WR={r['D']['wr']:5.2f} PF={r['D']['pf']:.2f} "
              f"| H n={r['H']['n']:5d} WR={r['H']['wr']:5.2f} PF={r['H']['pf']:.2f}",
              flush=True)
    with open(f"{OUT}/{card}_geom_repl.json", 'w') as f:
        json.dump(repl[:200], f)
    return rows


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        args = ['XAUUSD-M15']
    for card in args:
        scan_card(card)
