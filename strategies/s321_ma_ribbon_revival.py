# -*- coding: utf-8 -*-
"""
S321 — احیای S52 (MA Ribbon / GMMA-Alligator) با RQS+ ≥ 80
================================================================================
لایهٔ سوختهٔ هدف: `results/MA_Ribbon_HTF_Gate_RegimeBound_74.md` (RQS قدیم = 74).
سندِ مرجعِ معیار: docs/RQS_ROBUST_QUALITY_SCORE.md  ·  موتور: engine/rqs.py

--------------------------------------------------------------------------------
تز (نبوغ + تفکر خطی/غیرخطی + استناد علمی)
--------------------------------------------------------------------------------
S52 اصلی از «ریبونِ چند-MA» فقط به‌عنوانِ *گیت* روی probaهای ML (S49) استفاده کرد و
شکست خورد چون (L28): «گیتِ کیفیِ روند زیان را حذف می‌کند اما سودِ ناموجود را در
رژیمِ رنج نمی‌سازد» ⇒ نیمهٔ اولِ داده (رنجِ ۲۰۲۰–۲۰۲۳) PF≈1.0 ⇒ G4 (walk-forward)
می‌میرد.

راهِ نو (به‌جای گیت روی ML → یک لایهٔ price-action مستقلِ pip-native):
  ریبونِ فیبوناچیِ ۷خطی (EMA 8/13/21/34/55/89/144) — همان GMMA / منطقِ Alligator —
  را به یک ستاپِ کلاسیکِ «pullback-to-ribbon در روندِ تأییدشده» تبدیل می‌کنیم:

  LONG وقتی:
    (1) ribbon کاملاً مرتب و صعودی  : rib_order ≥ ord_thr           (fan صعودی)
    (2) ریبون «باز» است (روند واقعی): rib_width_z ≥ wz_gate         ← رفعِ L28
        (در رژیمِ رنج width_z<0 است ⇒ خودبه‌خود کنار می‌رود)
    (3) قیمت به بدنهٔ ریبون pullback کرده: pos_in_rib ≤ pull_max      (نه در سقف)
        ولی هنوز بالای کفِ ریبون: pos_in_rib ≥ pull_min              (حمایت نشکسته)
    (4) کندلِ تأییدِ صعودی: close > open  (بازگشت از پولبک)
  SHORT قرینه (برای EURUSD/رژیم نزولی آزموده می‌شود؛ طلا long-bias دارد).

  همه‌چیز شناور: ord_thr, wz_gate, pull_min/max, sl_mult/tp_mult(×ATR), max_hold,
  و be_trigger — grid-search؛ اعدادِ TP/SL از ATR مشتق می‌شوند نه اعدادِ رند.

اجرا:  python3 strategies/s321_ma_ribbon_revival.py XAUUSD M5 [max_seconds] [side]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import itertools

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs

TF_FILE = {
    'M5':  'data/{a}_M5.csv',  'M15': 'data/{a}_M15.csv',
    'M30': 'data/{a}_M30.csv', 'H1':  'data/{a}_H1.csv', 'H4': 'data/{a}_H4.csv',
}

RIBBON_PERIODS = [8, 13, 21, 34, 55, 89, 144]

# فضای جستجوی «شناور» (اعداد غیر-رند عمداً حاضرند)
GRID = dict(
    ord_thr=[0.55, 0.71, 0.85],          # چقدر ریبون باید مرتب باشد (fan)
    wz_gate=[-0.30, 0.00, 0.35],         # رژیم: ریبونِ «باز» (رفعِ L28)
    pull_min=[0.05, 0.20],               # کفِ pullback (حمایت نشکسته)
    pull_max=[0.45, 0.60, 0.78],         # سقفِ pullback (نه در قله)
    sl_mult=[1.1, 1.6, 2.2],             # SL = sl_mult × ATR (pip)
    tp_mult=[1.7, 2.4, 3.3],             # TP = tp_mult × ATR (pip)
    max_hold=[24, 60],
)


def build_features(df):
    """featureهای ریبونِ درون-تایم‌فریمی (in-TF، بدون MTF گیت بیرونی)."""
    c = df['close']
    atr_ = ind.atr(df, 14)
    emas = [ind.ema(c, p) for p in RIBBON_PERIODS]
    E = np.column_stack([e.values for e in emas])
    top = np.nanmax(E, axis=1)
    bot = np.nanmin(E, axis=1)
    price = c.values

    # ترتیبِ صحیح (fan): کسری از جفت‌های مجاورِ صعودی → [-1,+1]
    asc = np.zeros(len(df)); pairs = 0
    for k in range(len(RIBBON_PERIODS) - 1):
        asc += (E[:, k] > E[:, k + 1]).astype(float)
        pairs += 1
    rib_order = 2 * (asc / pairs) - 1

    # واگرایی/همگرایی و z-scoreِ آن (قدرت/رژیمِ روند)
    spread = (top - bot) / np.where(price != 0, price, np.nan)
    sp = pd.Series(spread)
    rib_width_z = ((sp - sp.rolling(200).mean()) /
                   (sp.rolling(200).std() + 1e-12)).values

    # موقعیتِ قیمت در بدنهٔ ریبون [0..1] (0=کف، 1=سقف)
    band = (top - bot)
    pos_in_rib = np.where(band > 1e-9, (price - bot) / band, 0.5)

    feats = dict(
        close=price, open=df['open'].values,
        atr_pip=(atr_.values / se_pip),
        rib_order=rib_order, rib_width_z=np.nan_to_num(rib_width_z, nan=-9.0),
        pos_in_rib=pos_in_rib, top=top, bot=bot,
    )
    return feats


def make_signals(feats, cfg, side):
    close = feats['close']; opn = feats['open']
    order = feats['rib_order']; wz = feats['rib_width_z']
    pos = feats['pos_in_rib']; atr_pip = feats['atr_pip']

    bull_candle = close > opn
    bear_candle = close < opn
    open_regime = wz >= cfg['wz_gate']
    pull_ok = (pos >= cfg['pull_min']) & (pos <= cfg['pull_max'])

    long_ok = ((order >= cfg['ord_thr']) & open_regime & pull_ok & bull_candle)
    # SHORT قرینه: ریبونِ نزولیِ باز + پولبکِ صعودی به بدنه + کندلِ نزولی
    short_ok = ((order <= -cfg['ord_thr']) & open_regime &
                (pos >= (1 - cfg['pull_max'])) & (pos <= (1 - cfg['pull_min'])) &
                bear_candle)

    if side == 'long':
        short_ok = np.zeros_like(short_ok, dtype=bool)
    elif side == 'short':
        long_ok = np.zeros_like(long_ok, dtype=bool)

    long_sig = np.nan_to_num(long_ok, nan=0).astype(bool)
    short_sig = np.nan_to_num(short_ok, nan=0).astype(bool)

    sl_pip = np.clip(np.nan_to_num(cfg['sl_mult'] * atr_pip, nan=0.0), 5.0, None)
    tp_pip = np.clip(np.nan_to_num(cfg['tp_mult'] * atr_pip, nan=0.0), 5.0, None)
    return long_sig, short_sig, sl_pip, tp_pip


def lite_stats(trades):
    n = len(trades)
    if n == 0:
        return 0, 0, 0, 0
    pnl = trades['pnl_pip'].values
    wins = (pnl > 0).sum()
    wr = wins / n * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 999
    return n, wr, pf, pnl.sum()


def main():
    global se_pip
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    max_sec = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
    side = sys.argv[4] if len(sys.argv) > 4 else ('long' if asset == 'XAUUSD' else 'both')

    se_pip = se.ASSETS[asset]['pip']
    path = TF_FILE[tf].format(a=asset)
    df = se.load_data(path)
    print(f"[{asset} {tf}] rows={len(df)}  {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]}  side={side}")

    feats = build_features(df)
    keys = list(GRID.keys())
    total = 1
    for k in keys:
        total *= len(GRID[k])
    print(f"grid size = {total}")

    t0 = time.time()
    shortlist = []
    tested = 0
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > max_sec * 0.6:
            print(f"[time] coarse screen stopped at {tested}")
            break
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] <= cfg['sl_mult']:
            continue  # فقط RR>1 معنی‌دار
        ls, ss, sl, tp = make_signals(feats, cfg, side)
        trades = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                    max_hold=cfg['max_hold'], allow_overlap=False)
        tested += 1
        n, wr, pf, net = lite_stats(trades)
        if n >= rqs.N_FLOOR and wr >= 58 and pf >= 1.25:
            sig = ls | ss
            med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
            shortlist.append((pf, wr, n, cfg, trades, med_tp))

    shortlist.sort(key=lambda x: x[0], reverse=True)
    print(f"tested={tested}  shortlist={len(shortlist)}  (elapsed {time.time()-t0:.0f}s)")

    results = []
    for pf, wr, n, cfg, trades, med_tp in shortlist:
        if time.time() - t0 > max_sec:
            print("[time] full-RQS stopped"); break
        r = rqs.compute_rqs(trades, asset,
                            sl_pip=float(np.median(trades['sl_pip'])), tp_pip=med_tp)
        results.append((r['rqs_score'], r['passed'], cfg, r['metrics'], r['gates']))

    results.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print("=" * 110)
    for score, passed, cfg, m, gates in results[:20]:
        gl = ''.join('1' if gates[g] else '0' for g in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f"RQS={score:5.1f} {'PASS' if passed else 'FAIL'} G[{gl}] "
              f"n={m['n_trades']:4d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} wf={m['wf_nets']} | "
              f"ord{cfg['ord_thr']} wz{cfg['wz_gate']} pull[{cfg['pull_min']},{cfg['pull_max']}] "
              f"sl{cfg['sl_mult']}tp{cfg['tp_mult']} mh{cfg['max_hold']}")
    if not results:
        print("NO CANDIDATE PASSED LITE SCREEN (WR>=58 & PF>=1.25)")


if __name__ == '__main__':
    se_pip = 0.10
    main()
