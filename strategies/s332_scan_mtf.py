# -*- coding: utf-8 -*-
"""
S331 — اسکنِ مولتی‌تایم‌فریمِ squeeze روی XAUUSD و EURUSD برای عبور از RQS+
================================================================================
قانونِ مولتی‌تایم‌فریم: هر TF ممکن است بهبودِ متناسبِ خود را بخواهد. TFهای بالاتر
(M30/H1/H4) معمولاً معاملاتِ تمیزتر و maxDD/MCL کمتر دارند ⇒ شانسِ بیشترِ عبور از G3.
همچنین max_hold باید متناسبِ هر TF باشد (اشتباهِ رایجِ #۶: TP/SL یکسان برای همه TF).

خروجی: برای هر (sym, tf) بهترین پیکربندیِ گیت-پاس (بیشترین net) یا نزدیک‌ترین.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs
import strategies.s332_squeeze_rqs_revival as S


def make_filter_pool(df):
    c = df['close'].values.astype(np.float64)
    adx_, pdi, mdi = S.adx(df, 14)
    rsi_ = S.rsi(c, 14)
    atr_ = S.atr(df, 14)
    e50 = S.ema(c, 50); e100 = S.ema(c, 100)
    atr_med = pd.Series(atr_).rolling(200, min_periods=50).median().values
    raw = {
        'none':       np.ones(len(df), bool),
        'adx>20':     adx_ > 20,
        'adx>25':     adx_ > 25,
        'adx>30':     adx_ > 30,
        'pdi>mdi':    pdi > mdi,
        'rsi>50':     rsi_ > 50,
        'rsi45_75':   (rsi_ > 45) & (rsi_ < 75),
        'ema50>100':  e50 > e100,
        'atr<1.5med': atr_ < 1.5 * atr_med,
        'atr>0.8med': atr_ > 0.8 * atr_med,
    }
    pool = {}
    for k, v in raw.items():
        pool[k] = np.nan_to_num(np.asarray(v, float), nan=0.0).astype(bool)
    return pool


# max_hold و شبکهٔ TP/SL متناسبِ هر TF (بر حسبِ pip — طلا pip=0.1$)
TF_PARAMS = {
    'M5':  dict(max_hold=288, tp=[120,180,250,300,400], sl=[70,90,120,180,250]),
    'M15': dict(max_hold=96,  tp=[150,200,250,300,400], sl=[90,110,150,200,250]),
    'M30': dict(max_hold=48,  tp=[150,250,300,400,500], sl=[100,150,200,250,300]),
    'H1':  dict(max_hold=24,  tp=[200,300,400,500,700], sl=[120,180,250,350,450]),
    'H4':  dict(max_hold=18,  tp=[300,500,700,900,1200],sl=[200,300,450,600,800]),
}

FILT_COMBOS = [
    ('none',), ('adx>20',), ('adx>25',), ('adx>30',), ('pdi>mdi',),
    ('rsi>50',), ('rsi45_75',), ('ema50>100',), ('atr<1.5med',),
    ('adx>25','pdi>mdi'), ('adx>20','rsi>50'), ('adx>25','atr<1.5med'),
    ('pdi>mdi','rsi45_75'), ('adx>20','ema50>100'), ('adx>25','rsi>50'),
    ('adx>30','pdi>mdi'), ('adx>20','atr<1.5med'),
]


def scan_tf(sym, tf, sqz_pct=0.25, brk=6, be_grid=(None,40,60), trail_grid=(None,)):
    df = S.load_tf(sym, tf)
    if df is None:
        return None, None
    sig = S.build_squeeze_signal(df, sqz_pct=sqz_pct, breakout_lookback=brk)
    if sig.sum() < 30:
        return df, pd.DataFrame()
    pool = make_filter_pool(df)
    P = TF_PARAMS[tf]
    rows = []
    for combo in FILT_COMBOS:
        fmask = np.ones(len(df), bool)
        for name in combo:
            fmask = fmask & pool[name]
        if fmask.sum() < 30:
            continue
        for tp in P['tp']:
            for sl in P['sl']:
                for be in be_grid:
                    for trl in trail_grid:
                        r, tr = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp,
                                           max_hold=P['max_hold'],
                                           be_trigger_pip=be, trail_pip=trl, filt=fmask)
                        m = r['metrics']
                        if m.get('n_trades', 0) < 30:
                            continue
                        rows.append(dict(
                            sym=sym, tf=tf, combo='+'.join(combo), sqz=sqz_pct, brk=brk,
                            tp=tp, sl=sl, be=be, trl=trl, mh=P['max_hold'],
                            passed=bool(r['passed']), rqs=r['rqs_score'],
                            n=m['n_trades'], wr=m['win_rate'], net=m['net_profit'],
                            pf=m['profit_factor'], dd=m['max_dd_pct'], mcl=m['max_consec_losses'],
                            ngate=sum(r['gates'].values()),
                            gates=''.join('1' if r['gates'][g] else '0'
                                          for g in ['G0','G1','G2','G3','G4','G5'])))
    return df, pd.DataFrame(rows)


def report(res, sym, tf, top=8):
    if res is None or len(res) == 0:
        print(f"  {sym} {tf}: no valid configs")
        return
    passed = res[res['passed']].sort_values('net', ascending=False)
    if len(passed):
        print(f"  ✅ {sym} {tf}: {len(passed)} PASS. Best net=+${passed.iloc[0]['net']:,.0f}")
        cols = ['combo','tp','sl','be','trl','rqs','n','wr','net','pf','dd','mcl','gates']
        print(passed[cols].head(top).to_string(index=False))
    else:
        near = res.sort_values(['ngate','net'], ascending=[False, False])
        b = near.iloc[0]
        print(f"  ✗ {sym} {tf}: no pass. closest ngate={b['ngate']} net=+${b['net']:,.0f} gates={b['gates']}")
        cols = ['combo','tp','sl','be','trl','n','wr','net','pf','dd','mcl','gates']
        print(near[cols].head(top).to_string(index=False))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', default='XAUUSD')
    ap.add_argument('--tf', default='M15')
    ap.add_argument('--sqz', type=float, default=0.25)
    ap.add_argument('--brk', type=int, default=6)
    args = ap.parse_args()
    df, res = scan_tf(args.sym, args.tf, sqz_pct=args.sqz, brk=args.brk)
    print(f"\n=== {args.sym} {args.tf} sqz={args.sqz} brk={args.brk} | signals & scan ===")
    report(res, args.sym, args.tf)
    if res is not None and len(res):
        out = f"results/_s331_{args.sym}_{args.tf}_sqz{int(args.sqz*100)}_brk{args.brk}.csv"
        res.to_csv(out, index=False)
        print(f"saved: {out}")
