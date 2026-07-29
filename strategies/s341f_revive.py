# -*- coding: utf-8 -*-
"""
S341f — احیای لایه‌های ردشدهٔ S341 (XAU H1/H4، EUR M15) با فیلترهای هم‌گرایی از «جعبه‌ابزار».

قانونِ جعبه‌ابزار (docs/indicators): وقتی لایه‌ای در ساخت به مانع خورد، به بانکِ ۴۰۱ اندیکاتور رجوع
کن. لایه‌های ردشدهٔ S341 همگی روی «کفِ WR<۶۰٪» (گیتِ G0) افتادند، نه روی p-value یا drawdown.
پس باید نرخِ اصابتِ *واقعی* را بالا برد — نه با کوچک‌کردنِ TP (اشتباهِ #۸ ممنوع) بلکه با فیلترِ
هم‌گرایی که فقط fadeهای «کششِ بالا از میانگین + خستگیِ مومنتوم» را نگه می‌دارد.

Brooks Ch.17: «middle of the day acts like a magnet» ⇒ fade فقط وقتی قیمت از میانگین دور (کشیده)
شده و اسیلاتور خسته است، احتمالِ برگشت به میانه بیشتر است. نگاشتِ مکانیکی:
  • ema_dist_atr  = (close − SMA)/EMA(ATR)  →  کششِ نرمالایزشده با ATR (بین TFها پایدار).
      LONG-fade: ema_dist_atr <= −stretch   (قیمت زیرِ میانگین، کشیده)
      SHORT-fade: ema_dist_atr >= +stretch
  • ifish_rsi (Inverse Fisher of RSI, docs momentum §۱۳): آستانهٔ تمیزتر از RSI خام، whipsaw کمتر.
      LONG-fade: ifish_rsi <= −exh   (اشباعِ فروش)
      SHORT-fade: ifish_rsi >= +exh

هر دو فیلتر «قانونِ همه‌چیز شناور است» را رعایت می‌کنند: آستانه‌ها غیررند و per-TF گرید می‌شوند.
"""
import sys
import numpy as np
import itertools

from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs
from strategies.s341_brooks_swing_levels import _fractal_levels, load_tf

# گریدِ SL/TP/mh — همان مقیاسِ s341c، غیررند و per-TF (اشتباهِ #۶/#۷ رعایت)
GRID = {
    ('XAUUSD', 'H1'): dict(sl=[520, 780], tp=[780, 1150, 1550], mh=[16, 28]),
    ('XAUUSD', 'H4'): dict(sl=[900, 1350], tp=[1350, 2000, 2700], mh=[14, 22]),
    ('EURUSD', 'M15'): dict(sl=[22, 33], tp=[33, 50, 66], mh=[20, 40]),
    ('EURUSD', 'M30'): dict(sl=[30, 45], tp=[45, 68, 90], mh=[18, 32]),
    # اجازهٔ سرریز روی لایه‌های تأییدشده هم بدهیم تا RQS+ را بالاتر ببریم:
    ('XAUUSD', 'M5'): dict(sl=[180, 260], tp=[260, 390, 520], mh=[24, 48]),
    ('XAUUSD', 'M15'): dict(sl=[280, 420], tp=[420, 620, 830], mh=[20, 40]),
    ('XAUUSD', 'M30'): dict(sl=[380, 560], tp=[560, 840, 1120], mh=[18, 32]),
}

W_GRID = [4, 5, 8]
BUF = [0.05, 0.15]
# رژیم را کمی می‌گشاییم چون فیلترِ هم‌گرایی خودش سخت‌گیر است (⇒ n بیشتر، پایدارتر)
REGIME_GRID = [
    dict(chop_min=52, r2_max=0.40, er_max=0.30),
    dict(chop_min=58, r2_max=0.30, er_max=0.22),
    dict(chop_min=61.8, r2_max=0.22, er_max=0.16),
]
SECOND = [False, True]
# آستانه‌های هم‌گرایی (غیررند، جهت‌دار). None = فیلتر خاموش (برای مقایسه).
STRETCH = [None, 0.7, 1.15, 1.6]     # |ema_dist_atr| حداقل
EXH = [None, 0.25, 0.5]              # |ifish_rsi| حداقل


def build_signal(h, l, c, atr, reg_mask, last_sh, last_sl, side, buf_frac,
                 require_second, stretch, exh, edist, ifr, second_lookback=40):
    n = len(h)
    sig = np.zeros(n, dtype=bool)
    recent = []
    for i in range(6, n):
        if not reg_mask[i]:
            continue
        a = atr[i]
        if not (a > 0) or not np.isfinite(a):
            continue
        buf = buf_frac * a
        if side == 'short':
            lvl = last_sh[i]
            if not np.isfinite(lvl):
                continue
            trig = (h[i] > lvl + buf) and (c[i] < lvl)
        else:
            lvl = last_sl[i]
            if not np.isfinite(lvl):
                continue
            trig = (l[i] < lvl - buf) and (c[i] > lvl)
        if not trig:
            continue

        # --- فیلترِ هم‌گراییِ جعبه‌ابزار (جهت‌دار) ---
        if stretch is not None:
            ed = edist[i]
            if not np.isfinite(ed):
                continue
            if side == 'long' and not (ed <= -stretch):
                continue
            if side == 'short' and not (ed >= stretch):
                continue
        if exh is not None:
            fv = ifr[i]
            if not np.isfinite(fv):
                continue
            if side == 'long' and not (fv <= -exh):
                continue
            if side == 'short' and not (fv >= exh):
                continue

        if require_second:
            recent = [k for k in recent if i - k <= second_lookback]
            recent.append(i)
            if len(recent) < 2:
                continue
        sig[i] = True
    return sig


def scan_one(asset, tf, verbose=True):
    key = (asset, tf)
    if key not in GRID:
        return None
    grid = GRID[key]
    df = load_tf(asset, tf)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    atr = ib.atr_s(df, p=14).to_numpy()
    ch = ib.chop(df, p=14).to_numpy()
    r2 = ib.r2(df, p=20).to_numpy()
    er = ib.compute('er_lucas_11', df).to_numpy()
    finite = np.isfinite(ch) & np.isfinite(r2) & np.isfinite(er)
    # فیلترهای هم‌گرایی — یک‌بار محاسبه
    edist = ib.compute('ema_dist_atr', df).to_numpy()
    ifr = ib.compute('ifish_rsi', df).to_numpy()

    best = None
    best_noflt = None  # بهترین بدونِ فیلتر، برای اثباتِ سهمِ فیلتر
    for side in ['long', 'short']:
        for w in W_GRID:
            last_sh, last_sl = _fractal_levels(h, l, w)
            for buf in BUF:
                for reg in REGIME_GRID:
                    rm = finite & (ch >= reg['chop_min']) & (r2 <= reg['r2_max']) & (np.abs(er) <= reg['er_max'])
                    for sec in SECOND:
                        for st in STRETCH:
                            for ex in EXH:
                                sig = build_signal(h, l, c, atr, rm, last_sh, last_sl,
                                                   side, buf, sec, st, ex, edist, ifr)
                                if sig.sum() < 30:
                                    continue
                                long_sig = sig if side == 'long' else np.zeros(len(df), bool)
                                short_sig = sig if side == 'short' else np.zeros(len(df), bool)
                                for sl, tp, mh in itertools.product(grid['sl'], grid['tp'], grid['mh']):
                                    if tp <= sl:
                                        continue
                                    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                                            asset=asset, max_hold=mh, allow_overlap=False)
                                    if tr is None or len(tr) < 30:
                                        continue
                                    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
                                    score = r['rqs_score']
                                    cfg = dict(side=side, w=w, buf=buf, sec=sec, stretch=st, exh=ex,
                                               sl=sl, tp=tp, mh=mh, **reg)
                                    if best is None or score > best[0]:
                                        best = (score, r, cfg)
                                        if verbose and r['passed']:
                                            print('  ACC-CAND', rqs.format_report(f'{asset}_{tf}_{side}', r), cfg, flush=True)
                                    if (st is None and ex is None) and (best_noflt is None or score > best_noflt[0]):
                                        best_noflt = (score, r, cfg)
    return best, best_noflt


if __name__ == '__main__':
    if len(sys.argv) > 2:
        order = [(sys.argv[1], sys.argv[2])]
    else:
        order = [('XAUUSD', 'H1'), ('XAUUSD', 'H4'), ('EURUSD', 'M15'), ('EURUSD', 'M30')]
    for asset, tf in order:
        res = scan_one(asset, tf, verbose=True)
        if res is None:
            print(f"{asset}-{tf} | no grid", flush=True); continue
        best, best_noflt = res
        score, r, cfg = best
        tag = 'ACCEPT ✅' if r['passed'] else 'reject'
        print(f"\n{asset}-{tf:4s} | WITH-FILTER best RQS {score:5.1f} | {tag}", flush=True)
        print('   ', rqs.format_report(f'{asset}_{tf}', r), flush=True)
        print('    cfg=', cfg, flush=True)
        if best_noflt is not None:
            s0, r0, c0 = best_noflt
            print(f"    [baseline no-filter best RQS {s0:5.1f} WR={r0['metrics'].get('win_rate',0):.1f}%]", flush=True)
        print('=' * 90, flush=True)
