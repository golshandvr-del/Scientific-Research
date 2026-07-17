# ============================================================================
# استراتژی ۹۰ — «ادغامِ واقعیِ S88 با پرتفویِ برنده (dedup) و سنجشِ سودِ خالصِ کل»
# ----------------------------------------------------------------------------
# قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر». سود خالص = XAUUSD + EURUSD. WR گزارشی.
#
# پرسشِ تعیین‌کننده: آیا افزودنِ لایهٔ نوِ S88 (MACD-in-up-regime) به پرتفویِ برنده
# (رکورد +۵۸٬۲۹۵$ = S67+S79+S81 طلا + S73 یورو) سودِ خالصِ کل را بالا می‌برد؟
#
# چون S88 و S67 هر دو LONG روی طلا M15 و همبستگیِ روزانه ~۰.۴ دارند، جمعِ خام
# = double-count. آزمونِ منصفانه: **ادغامِ سیگنال‌ها روی یک سرمایهٔ مشترکِ M15 با
# dedup** (اگر هر دو در یک بازه پوزیشن دارند، ورودِ جدید تا بسته‌شدنِ قبلی رد می‌شود
# — همان allow_overlap=False روی اتحادِ سیگنال‌ها). سپس مقایسه با S67 تنها.
#
# اگر ادغام > S67-تنها ⇒ S88 افزایشی است و به رکورد اضافه می‌شود.
# اگر ادغام ≤ S67-تنها ⇒ S88 صرفاً منطقِ درستِ سایت است (نه اهرمِ سودِ کل).
# ============================================================================
import sys, os, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, rsi, atr, macd
from engine import scalp_engine as SE

RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
CAP, RISK = 10_000.0, 1.0


def s88_signals(df):
    c = df['close']
    ema50 = ema(c, 50); ema200 = ema(c, 200)
    _, _, hist = macd(c); slope = ema50.diff(5)
    up = (ema50 > ema200) & (slope > 0)
    macd_up = (hist > 0) & (hist.shift(1) <= 0)
    return (macd_up & up).fillna(False).values


def s67_entry_mask(df):
    """ماسکِ ورودِ S67 روی همان ایندکسِ df (long)، برای اتحاد با S88."""
    from engine.backtest import run_backtest
    from engine.tpsl_plan import build_plan
    HZ = 48; SPREAD = 0.20; ER_TREND_THR = 0.30; P_HI = 0.66; P_MIN = 0.58
    z = np.load(os.path.join(RES, '_s61_cache.npz'), allow_pickle=True)
    pL = z['pL']; up_reg = z['up_reg']; er = z['er']; atrv = z['atrv']
    n = len(df)
    trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)
    baseL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
    ef = np.where(trendy, 'trend', 'chop'); pw = np.where(pL >= P_HI, 'hi', 'lo')
    lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
    lab[~baseL] = ''
    planL = build_plan('long', lab, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)
    eval_mask = np.zeros(n, bool); eval_mask[24000:] = True
    return (planL.entries & eval_mask), planL, HZ, SPREAD


def run_scalp(df, sig, sl, tp, hold):
    tr = SE.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, 'XAUUSD',
                            max_hold=hold, allow_overlap=False)
    st, _ = SE.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK)
    return st


def main():
    df = SE.load_data('data/XAUUSD_M15.csv')
    print('=' * 88)
    # S88 تنها (موتورِ scalp، SL150/TP450)
    s88_sig = s88_signals(df)
    st88 = run_scalp(df, s88_sig, 150.0, 450.0, 48)
    print('S88 تنها (scalp, SL150/TP450) : net=%+.1f$  n=%d  PF=%.2f'
          % (st88['net_profit'], st88['n_trades'], st88['profit_factor']))

    # S67 تنها روی همان موتورِ scalp با SL/TP ثابتِ نمایندهٔ آن (برای مقایسهٔ هم‌موتور
    # منصفانه، از میانگینِ SL/TP سویینگِ طلا استفاده می‌کنیم: SL120/TP360)
    s67_mask, _, HZ, _ = s67_entry_mask(df)
    st67 = run_scalp(df, s67_mask, 120.0, 360.0, HZ)
    print('S67-entries (scalp, SL120/TP360): net=%+.1f$  n=%d  PF=%.2f'
          % (st67['net_profit'], st67['n_trades'], st67['profit_factor']))

    # اتحادِ سیگنال‌ها (dedup طبیعی با allow_overlap=False) — SL/TP مشترکِ سویینگ
    union = s88_sig | s67_mask
    st_u = run_scalp(df, union, 150.0, 450.0, 48)
    print('-' * 88)
    print('UNION(S88 ∪ S67) dedup, SL150/TP450: net=%+.1f$  n=%d  PF=%.2f'
          % (st_u['net_profit'], st_u['n_trades'], st_u['profit_factor']))
    print('-' * 88)
    # مقایسهٔ افزایشی
    add_vs_67 = st_u['net_profit'] - st67['net_profit']
    print('Δ نسبت به S67-entries تنها (هم‌موتور): %+.1f$' % add_vs_67)
    if add_vs_67 > 0:
        print('=> ادغام افزایشی است: S88 چیزی می‌گیرد که S67 نمی‌گیرد.')
    else:
        print('=> ادغام افزایشی نیست: S88 عمدتاً زیرمجموعه/هم‌بستهٔ S67 است.')
    print('=' * 88)
    out = dict(s88=st88['net_profit'], s67_entries=st67['net_profit'],
               union=st_u['net_profit'], delta_vs_s67=float(add_vs_67))
    with open(os.path.join(RES, '_s90_merge.json'), 'w') as f:
        json.dump(out, f, indent=2)
    print('ذخیره شد: results/_s90_merge.json')


if __name__ == '__main__':
    main()
