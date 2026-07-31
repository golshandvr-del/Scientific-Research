# -*- coding: utf-8 -*-
"""
S352 — «pullbackِ دوجهته با گیتِ ساختارِ لگ-متناسب» (Bidirectional Structure Pullback)
================================================================================
انگیزه (از یافتهٔ S351): فیلترِ جهتیِ ساختار، لایهٔ لانگِ S333 را در `state=−1`
(بازگشت از کفِ ساختارِ نزولی) بهبود داد و روی M5 دروازهٔ مهارت H3 را از رد به پاس
برد. اما حکم به **INCOMPLETE** رسید، چون فیلتر همهٔ معاملات را هم‌سو کرد و H10
(مقاومتِ دوجهته) دیگر معاملهٔ خلافِ‌رانش نداشت تا داوری کند.

**فرضیهٔ متقارن:** اگر لانگِ pullback در ساختارِ نزولی خوب است، آنگاه یک **شورتِ
pullbackِ کاملاً آینه‌ای** باید در ساختارِ صعودی (`state=+1`) خوب باشد. ترکیبِ این دو
= معاملاتِ **دوجهته** ⇒ معاملاتِ counter-drift بازمی‌گردند ⇒ H10 قابلِ ارزیابی می‌شود.

--------------------------------------------------------------------------------
⛔ سپرهای انصاف
--------------------------------------------------------------------------------
  ۱) شورت یک **بازتابِ ریاضیِ دقیقِ** لانگِ S333 است — هیچ پارامترِ جدیدی:
        up_trend  = ef>es           →  down_trend = ef<es
        r < rth                     →  r > (100−rth)
        c > prev_high (تأیید)       →  c < prev_low
     همان `ef, es, rp, rth, confirm` که S333 روی هر TF دارد بازاستفاده می‌شود.
  ۲) گیتِ ساختار صفر-پارامتر: long فقط در state=−1، short فقط در state=+1.
  ۳) هندسه = همان `BEST_CFG` خودِ S333 (sl/tp/max_hold per-TF). دست‌نخورده.
  ۴) `state` علّی (فقط پیوتِ بسته‌شده). LPSB = عضوِ مرکزیِ L=8,f=0.33.

اجرا: PYTHONPATH=. python strategies/s352_bidir_structure.py [CARD ...] --n-perm 300
"""
import os
import sys
import json
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies import s333_s79_pullback_revival as s333           # noqa: E402
from strategies.s351_lpsb import lpsb_signals                      # noqa: E402
from strategies.s351_verdict import CENTRAL, build_null_side       # noqa: E402

OUT = 'results/_scan_S351'
WARMUP = 300
N_MULT = 8                    # هم‌سان با S351 (۲ علامت × ۴ کارت)
SPLIT_FRAC = 0.60
SEED = 12345
CARDS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1']


def ema(x, span):
    return s333.ema(x, span)


def rsi(x, p):
    return s333.rsi(x, p)


def short_core(df, ema_fast, ema_slow, rsi_p, rsi_th, confirm='rsi_turn'):
    """بازتابِ دقیقِ core_signal_confirmed برای سمتِ شورت. صفر پارامترِ جدید."""
    c = df['close'].values
    l = df['low'].values
    ef = ema(c, ema_fast); es = ema(c, ema_slow); r = rsi(c, rsi_p)
    down_trend = ef < es
    r_prev = np.concatenate([[r[0]], r[:-1]])
    c_prevlow = np.concatenate([[l[0]], l[:-1]])
    hi_th = 100.0 - rsi_th                       # آینهٔ آستانهٔ RSI

    if confirm == 'none':
        sig = down_trend & (r > hi_th)
    elif confirm == 'rsi_turn':
        # سقفِ RSI شکل گرفت: کندلِ قبل در اشباعِ خرید بود، حالا RSI برمی‌گردد پایین.
        sig = down_trend & (r_prev > hi_th) & (r < r_prev) & (r > hi_th - 10)
    elif confirm == 'price_turn':
        popped = (r > hi_th) | (r_prev > hi_th)
        sig = down_trend & popped & (c < c_prevlow)
    else:
        raise ValueError(confirm)
    return np.nan_to_num(sig).astype(bool)


def _win_col(tr):
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)
    return tr


def bidir_trades(df, cfg, state, card):
    """معاملاتِ دوجهته: long(state=−1) + short(state=+1)، با هندسهٔ S333."""
    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']
    asset = 'XAUUSD'

    long_sig = s333.build_layer(df, cfg) & (state == -1)
    short_sig = short_core(df, cfg['ef'], cfg['es'], cfg['rp'], cfg['rth'],
                           confirm=cfg.get('confirm', 'rsi_turn')) & (state == 1)
    # گیتِ رژیمِ hurst مشترک (همان که build_layer دارد) روی شورت هم اعمال شود
    import numpy as _np
    hu = s333.ib.compute('hurst', df).values
    short_sig = short_sig & (_np.nan_to_num(hu, nan=-1.0) > cfg['hurst'])
    if cfg.get('er') is not None:
        er = s333.ib.compute('er_lucas_29', df).values
        short_sig = short_sig & (_np.nan_to_num(er, nan=-1.0) > cfg['er'])
    if cfg.get('r2') is not None:
        r2v = s333.ib.compute('r2_fib_89', df).values
        short_sig = short_sig & (_np.nan_to_num(r2v, nan=-1.0) > cfg['r2'])

    n = len(df)
    # شبیه‌سازی: دو صف مستقل، سپس ادغام و مرتب‌سازی بر خروج
    tr_l = se.simulate_trades(df, long_sig, np.zeros(n, bool), sl, tp, asset,
                              max_hold=mh)
    tr_s = se.simulate_trades(df, np.zeros(n, bool), short_sig, sl, tp, asset,
                              max_hold=mh)
    frames = [t for t in (tr_l, tr_s) if t is not None and len(t) > 0]
    if not frames:
        return None, long_sig, short_sig
    tr = pd.concat(frames, ignore_index=True).sort_values('exit_bar')
    tr = tr.reset_index(drop=True)
    return _win_col(tr), long_sig, short_sig


def judge(card, n_perm=300, verbose=True):
    cfg = s333.BEST_CFG[card]
    asset = 'XAUUSD'
    path = se.ASSETS[card]['file']
    if not os.path.exists(path):
        return dict(card=card, verdict='NO_DATA')

    df = se.load_data(path)
    n = len(df)
    close = df['close'].to_numpy(float)
    bar_time = df['dt'].values if 'dt' in df.columns else None
    split = int(n * SPLIT_FRAC)

    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    tr, long_sig, short_sig = bidir_trades(df, cfg, state, card)
    if tr is None or len(tr) < 3:
        return dict(card=card, verdict='TOO_FEW')

    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    sl, tp = cfg['sl'], cfg['tp']

    valid = np.where(np.isfinite(close))[0]
    valid = valid[valid >= WARMUP]
    sl_price = sl * se.ASSETS[asset]['pip']
    rng = np.random.default_rng(SEED)
    null = build_null_side(df, asset, valid, np.full(n, sl_price),
                           nL, nS, n_perm, rng, verbose=False)

    r = rqs2.compute_rqs2(tr, asset, n_trials=N_MULT,
                          sl_pip=float(sl), tp_pip=float(tp),
                          bar_time=bar_time, null=null,
                          split_bar=split, close=close)

    if verbose:
        print(f"\n{'='*90}\n=== S352 BIDIR :: {card} (bars={n:,}) ===", flush=True)
        print(f"    n_long={nL} n_short={nS} total={len(tr)} "
              f"| geom sl={sl} tp={tp} mh={cfg['mh']}", flush=True)
        print(rqs2.format_rqs2(f'{card} BIDIR', r), flush=True)

    out = dict(card=card, asset=asset, bars=n, cfg=dict(cfg),
               n_mult=N_MULT, split_bar=split, lpsb_member=dict(CENTRAL),
               n_long=nL, n_short=nS, n_total=len(tr),
               verdict=r['verdict'],
               rqs2={k: r[k] for k in
                     ('verdict', 'rqs2_score', 'gates', 'metrics', 'notes')
                     if k in r})
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f'{card}_bidir.json')
    with open(p, 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    if verbose:
        print(f"    [checkpoint] {p}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cards', nargs='*', default=CARDS)
    ap.add_argument('--n-perm', type=int, default=300)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    for card in (a.cards if a.cards else CARDS):
        judge(card, n_perm=a.n_perm, verbose=not a.quiet)


if __name__ == '__main__':
    main()
