# -*- coding: utf-8 -*-
"""
S346 — پروبِ لبهٔ شرطی: کدام ابزارِ بانکِ ۴۰۱‌تایی رویدادِ «خروج از کانالِ تطبیقی» را
از حالتِ تقریباً تصادفی به یک لبهٔ واقعی تبدیل می‌کند؟
================================================================================
یافتهٔ اسکنِ اول (مستند در گزارش): رویدادِ پایه (بستنِ کندل بیرونِ کانالِ ATR تطبیقی)
روی XAUUSD-M5 با n≈۱۰٬۰۰۰–۱۷٬۰۰۰ معامله **تقریباً تصادفی** است
(WR≈۴۳.۵٪ در برابر breakeven≈۴۴٪ ⇒ PF≈۰.۷). یعنی خودِ ماشه «لبه» ندارد ولی
**فراوانیِ بسیار بالا** دارد. این دقیقاً موقعیتی است که «قانونِ بی‌نهایت بهبود»
برای آن ساخته شده: با فیلترهای رژیمی، زیرمجموعهٔ دارای لبه را جدا می‌کنیم و
N بالا را (تا حدِ ممکن) نگه می‌داریم.

روشِ علمی (ضدِ overfit):
  • فاز ۱: مقایسهٔ گونه‌های پایه (fade/breakout × reentry × side) — بدونِ فیلتر.
  • فاز ۲: **screeningِ تک‌ویژگی**. برای ~۷۰ ابزار از همهٔ دسته‌های بانک، مقدارِ
    ویژگی در کندلِ سیگنال گرفته می‌شود و معاملات به ۵ چندکِ مساوی تقسیم می‌شوند.
    برای هر چندک WR و expectancy (pip) گزارش می‌شود.
    ⚠️ کشفِ فیلتر فقط روی **نیمهٔ اولِ زمانی (discovery)** و اعتبارسنجی روی
    **نیمهٔ دومِ دست‌نخورده (holdout)** انجام می‌شود. ویژگی‌ای که در holdout
    تکرار نشود، به مرحلهٔ بعد راه نمی‌یابد.

اجرا:
    python strategies/s346_edge_probe.py base XAUUSD-M15
    python strategies/s346_edge_probe.py screen XAUUSD-M15
"""
import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                        # noqa: E402
from engine import indicator_bank as ib                      # noqa: E402
from strategies.s346_adaptive_channel import build_signals    # noqa: E402
from strategies.s346_scan import CARDS                        # noqa: E402

OUT_DIR = 'results/_scan_S346'
os.makedirs(OUT_DIR, exist_ok=True)

# پایهٔ مرجع برای screening (هندسهٔ میانه — نه بهینه‌شده، تا سوگیریِ انتخاب نداشته باشیم)
BASE = dict(mode='fade', p=21, mult=1.618, er_thr=0.236, sl_k=2.058, rr=1.0)

# جعبه‌ابزار: نمایندهٔ همهٔ دسته‌های بانک (رفعِ اشتباهِ رایج #۳)
FEATURES = [
    # --- statistical / fractal ---
    ('hurst_34', lambda d: ib.hurst(d, p=34)),
    ('hurst_64', lambda d: ib.hurst(d, p=64)),
    ('r2_21', lambda d: ib.r2(d, p=21)),
    ('r2_55', lambda d: ib.r2(d, p=55)),
    ('entropy_21', lambda d: ib.entropy(d, p=21)),
    ('skew_34', lambda d: ib.skew(d, p=34)),
    ('kurt_34', lambda d: ib.kurt(d, p=34)),
    ('zscore_21', lambda d: ib._zscore_v(d, 21)),
    ('zscore_55', lambda d: ib._zscore_v(d, 55)),
    ('fdi_34', lambda d: ib.fdi(d, p=34)),
    ('frama_dist', lambda d: (d['close'] - ib.frama(d, p=21)) / ib.atr_s(d, 21)),
    # --- volatility / cost regime ---
    ('natr_21', lambda d: ib.natr(d, p=21)),
    ('chop_21', lambda d: ib.chop(d, p=21)),
    ('chop_55', lambda d: ib.chop(d, p=55)),
    ('ulcer_21', lambda d: ib.ulcer(d, p=21)),
    ('atr_pct_21', lambda d: ib.atr_pct(d, p=21)),
    ('mass_idx', lambda d: ib.mass(d)),
    ('rvi_vol_21', lambda d: ib.rvi_vol(d, p=21)),
    # --- trend / structure ---
    ('ema_dist_atr', lambda d: ib.ema_dist_atr(d, emaP=55, atrP=21)),
    ('adx_like_vortex', lambda d: ib.vortex(d, period=21)),
    ('aroon_21', lambda d: ib.aroon(d, period=21)),
    ('supertrend_side', lambda d: np.sign(d['close'] - ib.supertrend(d, period=13, mult=2.618))),
    ('psar_side', lambda d: np.sign(d['close'] - ib.psar(d))),
    ('trend_gate', lambda d: ib.trend_gate(d, chopP=21, emaP=55)),
    ('dsma_dist', lambda d: (d['close'] - ib.dsma(d, period=21)) / ib.atr_s(d, 21)),
    ('kama_dist', lambda d: (d['close'] - ib.kama(d, p=21)) / ib.atr_s(d, 21)),
    ('vidya_dist', lambda d: (d['close'] - ib.vidya(d, p=21)) / ib.atr_s(d, 21)),
    ('t3_dist', lambda d: (d['close'] - ib.t3(d, p=13)) / ib.atr_s(d, 21)),
    ('donch_pos', lambda d: (d['close'] - ib.donchian_mid(d, period=34)) / ib.atr_s(d, 21)),
    ('gann_hilo', lambda d: ib.gann_hilo(d, period=13)),
    # --- momentum ---
    ('rsi_14', lambda d: ib.compute('rsi_fib_13', d) if 'rsi_fib_13' in ib.REGISTRY else ib.laguerre_rsi(d)),
    ('cmo_21', lambda d: ib.cmo(d, p=21)),
    ('tsi', lambda d: ib.tsi(d)),
    ('fisher_13', lambda d: ib.fisher(d, p=13)),
    ('ifish_rsi', lambda d: ib.ifish_rsi(d, p=13)),
    ('crsi', lambda d: ib.crsi(d)),
    ('roc_13', lambda d: ib.roc(d, p=13)),
    ('mom_21', lambda d: ib.mom(d, p=21)),
    ('ao', lambda d: ib.ao(d)),
    ('ac', lambda d: ib.ac(d)),
    ('trix_21', lambda d: ib.trix(d, p=21)),
    ('dpo_21', lambda d: ib.dpo(d, p=21)),
    ('bop_14', lambda d: ib.bop(d)),
    ('cfo_21', lambda d: ib.cfo(d, p=21)),
    ('pgo_21', lambda d: ib.pgo(d, p=21)),
    ('rvgi', lambda d: ib.rvgi(d)),
    ('kdj_j', lambda d: ib.kdj_j(d)),
    ('wr_cn_21', lambda d: ib.wr_cn(d, p=21)),
    ('psy_13', lambda d: ib.psy(d, p=13)),
    ('bias_13', lambda d: ib.bias(d, p=13)),
    ('adtm', lambda d: ib.adtm(d)),
    ('qqe', lambda d: ib.qqe(d)),
    ('stc', lambda d: ib.stc(d)),
    ('tdi', lambda d: ib.tdi(d)),
    ('elder_impulse', lambda d: ib.elder_impulse(d)),
    ('waddah', lambda d: ib.waddah(d)),
    # --- cycle / DSP (اِهلرز) ---
    ('reflex_21', lambda d: ib.reflex(d, period=21)),
    ('trendflex_21', lambda d: ib.trendflex(d, period=21)),
    ('cg_13', lambda d: ib.cg(d, period=13)),
    ('laguerre', lambda d: ib.laguerre(d)),
    ('roof_ss', lambda d: ib.roof(d)),
    ('ehp_48', lambda d: ib.ehp(d, period=48)),
    ('ssf_13', lambda d: ib.ssf(d, period=13)),
    # --- volume (tick proxy) ---
    ('obv_slope', lambda d: ib.obv(d).diff(13)),
    ('efi_13', lambda d: ib.efi(d, p=13)),
    ('mfi_14', lambda d: ib.mfi(d, p=14)),
    ('adosc', lambda d: ib.adosc(d)),
    ('emv_14', lambda d: ib.emv(d, p=14)),
    ('vol_rel', lambda d: d['volume'] / d['volume'].rolling(55).mean()),
    # --- ER خودِ منبع + مشتقاتش ---
    ('er_21', lambda d: ib._er_v(d, 21)),
    ('er_55', lambda d: ib._er_v(d, 55)),
    ('rsi_of_er', lambda d: ib.rsi_of_er(d, erP=13, rsiP=13)),
    # --- زمان (برای اثباتِ نکردنِ اشتباهِ #۱ فقط به‌عنوان یکی از ۷۰ گزینه) ---
    ('hour_utc', lambda d: d['dt'].dt.hour),
    ('dow', lambda d: d['dt'].dt.dayofweek),
]


def base_trades(df, asset, mode, p, mult, er_thr, sl_k, rr, max_hold,
                require_reentry=False, side=None, extra_gate=None):
    pip = se.ASSETS[asset]['pip']
    spread = se.ASSETS[asset]['spread_pip']
    ls, ss, slp, tpp, ch = build_signals(
        df, mode=mode, p=p, mult=mult, er_thr=er_thr, sl_k=sl_k, tp_k=sl_k * rr,
        pip=pip, min_sl_pip=2.0 * spread, require_reentry=require_reentry,
        extra_gate=extra_gate)
    if side == 'long':
        ss = np.zeros(len(df), dtype=bool)
    elif side == 'short':
        ls = np.zeros(len(df), dtype=bool)
    tr = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp, asset=asset,
                            max_hold=max_hold, allow_overlap=False)
    return tr, ch, (ls, ss, slp, tpp)


def phase_base(card):
    asset, path, mh_grid = CARDS[card]
    df = se.load_data(path)
    mh = mh_grid[1]
    print(f"=== {card} base variants (p={BASE['p']} mult={BASE['mult']} "
          f"er={BASE['er_thr']} sl_k={BASE['sl_k']} rr={BASE['rr']} mh={mh})", flush=True)
    rows = []
    for mode in ('fade', 'breakout'):
        for reentry in (False, True):
            for side in (None, 'long', 'short'):
                tr, _, _ = base_trades(df, asset, mode, BASE['p'], BASE['mult'],
                                       BASE['er_thr'], BASE['sl_k'], BASE['rr'], mh,
                                       require_reentry=reentry, side=side)
                if tr is None or len(tr) < 30:
                    continue
                wr = (tr['outcome'] == 'win').mean() * 100
                exp = tr['pnl_pip'].mean()
                cap, _ = se.run_capital(tr, asset)
                rows.append(dict(mode=mode, reentry=reentry, side=side or 'both',
                                 n=len(tr), wr=round(wr, 2), exp_pip=round(exp, 3),
                                 pf=round(cap['profit_factor'], 3),
                                 net=round(cap['net_profit'], 1)))
                print(f"  {mode:8s} reentry={str(reentry):5s} side={side or 'both':5s} "
                      f"| n={len(tr):6d} WR={wr:5.2f}% exp={exp:7.3f}pip "
                      f"PF={cap['profit_factor']:5.3f} net={cap['net_profit']:10.1f}", flush=True)
    with open(f'{OUT_DIR}/{card}_base.json', 'w') as f:
        json.dump(rows, f, indent=1, default=float)
    return rows


def phase_screen(card, mode='fade', reentry=False, side=None, nq=5):
    asset, path, mh_grid = CARDS[card]
    df = se.load_data(path)
    mh = mh_grid[1]
    tr, _, _ = base_trades(df, asset, mode, BASE['p'], BASE['mult'], BASE['er_thr'],
                           BASE['sl_k'], BASE['rr'], mh, require_reentry=reentry, side=side)
    print(f"=== {card} screening on base n={len(tr)} mode={mode} reentry={reentry} "
          f"side={side or 'both'}", flush=True)
    sig = tr['signal_bar'].values
    pnl = tr['pnl_pip'].values
    win = (tr['outcome'] == 'win').values
    half = len(tr) // 2
    out = []
    for name, fn in FEATURES:
        try:
            s = fn(df)
            v = np.asarray(pd.Series(s).values, dtype=np.float64)[sig]
        except Exception as e:                                    # noqa: BLE001
            print(f"  !! {name}: {e}", flush=True)
            continue
        ok = np.isfinite(v)
        if ok.sum() < 200:
            continue
        # چندک‌ها روی نیمهٔ discovery تعیین می‌شوند تا از نشتِ اطلاعاتِ holdout جلوگیری شود
        d_idx = np.arange(len(tr)) < half
        dv = v[d_idx & ok]
        if len(dv) < 100:
            continue
        qs = np.quantile(dv, np.linspace(0, 1, nq + 1))
        qs[0], qs[-1] = -np.inf, np.inf
        buckets = []
        for k in range(nq):
            m = ok & (v >= qs[k]) & (v < qs[k + 1])
            md = m & d_idx
            mh_ = m & (~d_idx)
            if md.sum() < 30 or mh_.sum() < 30:
                buckets.append(None)
                continue
            buckets.append(dict(
                k=k, lo=float(qs[k]), hi=float(qs[k + 1]),
                n_d=int(md.sum()), wr_d=round(float(win[md].mean() * 100), 2),
                exp_d=round(float(pnl[md].mean()), 3),
                n_h=int(mh_.sum()), wr_h=round(float(win[mh_].mean() * 100), 2),
                exp_h=round(float(pnl[mh_].mean()), 3)))
        good = [b for b in buckets if b]
        if not good:
            continue
        best_d = max(good, key=lambda b: b['exp_d'])
        # تکرارپذیری: همان سطلِ برنده در holdout هم مثبت باشد
        rep = best_d['exp_h'] > 0
        out.append(dict(feature=name, best_bucket=best_d, replicated=rep, buckets=good))
        flag = 'REPL' if rep else '    '
        print(f"  {name:16s} best q{best_d['k']} [{best_d['lo']:.4g},{best_d['hi']:.4g}) "
              f"D: n={best_d['n_d']:5d} WR={best_d['wr_d']:5.2f} exp={best_d['exp_d']:7.3f} | "
              f"H: n={best_d['n_h']:5d} WR={best_d['wr_h']:5.2f} exp={best_d['exp_h']:7.3f} {flag}",
              flush=True)
    out.sort(key=lambda r: (r['replicated'], min(r['best_bucket']['exp_d'],
                                                 r['best_bucket']['exp_h'])), reverse=True)
    with open(f'{OUT_DIR}/{card}_screen_{mode}_{side or "both"}.json', 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print("\n--- TOP replicated features ---", flush=True)
    for r in out[:15]:
        b = r['best_bucket']
        print(f"  {r['feature']:16s} q{b['k']} exp_D={b['exp_d']:7.3f} exp_H={b['exp_h']:7.3f} "
              f"WR_D={b['wr_d']:5.2f} WR_H={b['wr_h']:5.2f} n_tot={b['n_d'] + b['n_h']}",
              flush=True)
    return out


if __name__ == '__main__':
    cmd = sys.argv[1]
    card = sys.argv[2]
    if cmd == 'base':
        phase_base(card)
    elif cmd == 'screen':
        mode = sys.argv[3] if len(sys.argv) > 3 else 'fade'
        side = sys.argv[4] if len(sys.argv) > 4 else None
        side = None if side in (None, 'both') else side
        phase_screen(card, mode=mode, side=side)
