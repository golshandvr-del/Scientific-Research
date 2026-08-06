# -*- coding: utf-8 -*-
"""
ممیزیِ **لایهٔ اولِ آرشیو** — `S69` پرتفویِ چهار-داراییِ سرمایه‌محور
================================================================================
لایه: `results/S69_MultiAsset_Portfolio_NetProfit_12844.md`
کد  : `strategies/s69_multiasset_capital_portfolio.py`
منطق: دو مغزِ LightGBM (Bull-long / Bear-short) با walk-forward روی ۵۷ ویژگی،
      رژیمِ `EMA50/200 × ER(32)` کافمن، و `TP/SL-Plan` رژیم-آگاه.

بازتولید **تأییدشده**: اجرای مجددِ کدِ اصلی عیناً اعدادِ آرشیو را داد
(`XAUUSD: n=1526, net=+26641$, WR=52.9%` در برابرِ `_s69_XAUUSD.json`:
`n=1526, net=26641.49`). پس معامله‌هایی که داوری می‌شوند **همان** معامله‌های
تاریخیِ لایه‌اند، نه بازسازیِ تقریبی.

════════════════════════════════════════════════════════════════════════════
سه تصمیمِ صحت که این ممیزی را از یک داوریِ سطحی جدا می‌کند
════════════════════════════════════════════════════════════════════════════

① **هندسهٔ لایه متغیر است، و مدلِ صفر باید همان تغییرپذیری را ببیند.**
   `SL` از ۲۴.۶ تا ۱۱۷۱.۷ pip می‌رود (میانه ۱۰۳.۸) چون از `plan` رژیم-آگاه
   می‌آید. اگر نول را با یک `SL` ثابتِ میانه بسازم، خریدارِ کور براکتی می‌گیرد
   که لایه هرگز نداشته ⇒ مقایسه ناهم‌تراز. پس نول با **توزیعِ واقعیِ** `SL`
   لایه ساخته می‌شود (نمونه‌گیریِ بوت‌استرپ از همان توزیع).

② **`n_trials` صادقانه.** S69 وارثِ زنجیرهٔ `S63→S67` است و روی چهار دارایی
   اجرا شد. سندِ لایه شمارشِ صریحی نمی‌دهد، پس فالبکِ محافظه‌کارانه به کار
   می‌رود که به نفعِ `REJECT` خطا می‌کند، نه `ACCEPT` (اشتباهِ رایجِ ۸).

③ **هر دارایی یک کارتِ مستقل است** (قانونِ MTF). سندِ S69 «سودِ پرتفوی» را
   جمعِ چهار دارایی تعریف کرده بود، اما RQS2 **لایه را می‌سنجد نه سبد را**:
   اگر منطق روی EURUSD کلِ سرمایه را بسوزاند، جمع‌کردنش با سودِ طلا آن شکست را
   **پنهان** می‌کند. اسپک صریح است که هر کارت جداگانه باید معیار را پاس کند.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rqs2 as R                        # noqa: E402
from engine import scalp_engine as se               # noqa: E402
from tools.audit_rqs2_rejudge import load_card, bar_time_of, PERM_K, SEED  # noqa: E402
from tools.audit_runner import save_verdict, summarize  # noqa: E402

LAYER_FILE = 'S69_MultiAsset_Portfolio_NetProfit_12844.md'
TF = 'M15'                       # کارتِ سازندهٔ لایه (همهٔ دارایی‌ها M15)
MAX_HOLD = 48                    # `HZ=48` در کدِ اصلی
PIP = {'XAUUSD': 0.1, 'EURUSD': 0.0001, 'AUDUSD': 0.0001}

# فضایِ جست‌وجویِ محافظه‌کارانه: زنجیرهٔ S63→S69، ۴ دارایی، شبکهٔ TP/SL-Plan.
# سند عددِ صریح نمی‌دهد ⇒ برآوردِ **بالا** انتخاب می‌شود (به نفعِ REJECT).
N_TRIALS = 4000

CARDS = ['XAUUSD', 'EURUSD', 'AUDUSD']   # DXY در `data/` نیست ⇒ داوری‌ناپذیر


# ═══════════════════════════════════════════════════════════════════════════
#  مدلِ صفر با **توزیعِ واقعیِ هندسهٔ لایه**
# ═══════════════════════════════════════════════════════════════════════════
def null_variable_geom(df, asset, sl_pool, rr_pool, side, n_sig,
                       k=PERM_K, seed=SEED, max_hold=MAX_HOLD, stride=7):
    """
    دو خطِ مبنا، هر دو با **همان توزیعِ هندسه‌ای** که لایه واقعاً استفاده کرد.

    چرا این کار لازم است (و چرا میانه‌گرفتن غلط است):
    `H3` می‌پرسد «آیا مهارتِ *انتخابِ زمان* وجود دارد؟» و پاسخ را از تفاوتِ
    `WR` لایه با `WR` همان براکت روی زمان‌های تصادفی می‌گیرد. اما `WR` یک
    براکت **شدیداً** تابعِ نسبتِ `TP/SL` است. لایهٔ S69 در رژیمِ روندی براکتِ
    پهن و در رژیمِ چاپ براکتِ تنگ می‌گذارد؛ اگر نول را با یک براکتِ ثابتِ
    میانه بسازم، مبنایی می‌سازم که **هیچ‌وقت وجود نداشته** و لیفتِ حاصل
    مخلوطی از «مهارتِ زمان» و «تفاوتِ هندسه» می‌شود — یعنی همان ناهم‌ترازیِ
    مبنا که §۰ اسپک آن را قاتلِ RQS+ می‌نامد.

    راه‌حل: در هر جای‌گشت، به هر ورودِ تصادفی یک جفتِ `(sl, rr)` که
    **بوت‌استرپ از توزیعِ واقعیِ لایه** است تخصیص می‌یابد. پس خریدارِ کور
    دقیقاً همان تنوعِ براکت را دارد، فقط **زمان‌هایش تصادفی است**. آن‌وقت
    تفاوتِ باقی‌مانده فقط و فقط مهارتِ زمان‌بندی است.
    """
    n = len(df)
    rng = np.random.default_rng(seed)
    lo, hi = 260, n - MAX_HOLD - 2
    if hi <= lo:
        return None

    def wr_of(pos):
        sl_arr = np.full(n, np.nan)
        tp_arr = np.full(n, np.nan)
        sl_draw = rng.choice(sl_pool, size=len(pos), replace=True)
        rr_draw = rng.choice(rr_pool, size=len(pos), replace=True)
        sl_arr[pos] = sl_draw
        tp_arr[pos] = sl_draw * rr_draw
        m = np.zeros(n, bool)
        m[pos] = True
        # NaN بیرونِ سیگنال‌ها بی‌اثر است چون شبیه‌ساز فقط روی سیگنال می‌خواند
        sl_arr = np.nan_to_num(sl_arr, nan=float(np.median(sl_pool)))
        tp_arr = np.nan_to_num(tp_arr, nan=float(np.median(sl_pool)))
        ls = m if side == 'long' else np.zeros(n, bool)
        ss = m if side == 'short' else np.zeros(n, bool)
        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset,
                                max_hold=max_hold, allow_overlap=False)
        if tr is None or len(tr) < 10:
            return None
        return 100.0 * float((tr['outcome'] == 'win').mean())

    # ① مبنایِ بی‌قید — هر کندلِ n-امین (stride) با هندسهٔ بوت‌استرپ‌شده
    uncond = wr_of(np.arange(lo, hi, stride))

    # ② جای‌گشتِ زمانی — همان تعدادِ سیگنال، موقعیت‌های تصادفی
    n_sig = int(max(1, min(n_sig, (hi - lo) - 1)))
    wrs = []
    for _ in range(k):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        w = wr_of(np.sort(pos))
        if w is not None:
            wrs.append(w)
    if len(wrs) < 50:
        return None
    a = np.asarray(wrs, float)
    return dict(uncond_wr=uncond, perm_mean=float(a.mean()),
                perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()),
                perm_k=int(len(a)))


def judge_asset(asset: str) -> dict:
    """یک دارایی از S69 را به‌طورِ کاملاً مستقل داوری می‌کند (قانونِ MTF)."""
    csv = os.path.join(ROOT, 'results', f'_s69_trades_{asset}.csv')
    if not os.path.exists(csv):
        return {'card': f'{asset}-{TF}', 'verdict': 'INCOMPLETE',
                'rqs2_score': 0.0, 'reason': 'trades not reproduced'}
    df = load_card(asset, TF)
    if df is None:
        return {'card': f'{asset}-{TF}', 'verdict': 'INCOMPLETE',
                'rqs2_score': 0.0, 'reason': 'card data missing'}

    t = pd.read_csv(csv)
    ps = PIP[asset]

    # ترجمهٔ خروجیِ لایه به قرارداد rqs2: pip، و TP از خودِ معامله‌ها
    tr = pd.DataFrame({
        'entry_bar': t['entry_bar'].astype(int),
        'exit_bar': t['exit_bar'].astype(int),
        'outcome': t['outcome'],
        'pnl_pip': t['pnl'].astype(float) / ps,
        'sl_pip': t['sl_dist'].astype(float) / ps,
        'direction': t['direction'],
    })
    # TP واقعیِ هر معامله: برنده‌ها فاصلهٔ TP را *دقیقاً* پیموده‌اند.
    # برای بازنده‌ها TP مشاهده نشد، پس از نسبتِ rr همان رژیم برآورد می‌شود:
    # میانهٔ rr برنده‌ها ⇒ محافظه‌کارانه‌ترین برآوردِ در دسترس.
    win = tr['outcome'] == 'win'
    rr_obs = (tr.loc[win, 'pnl_pip'] / tr.loc[win, 'sl_pip']).replace(
        [np.inf, -np.inf], np.nan).dropna()
    rr_med = float(rr_obs.median()) if len(rr_obs) else 1.0
    tr['tp_pip'] = tr['sl_pip'] * rr_med

    sl_pool = tr['sl_pip'].to_numpy(float)
    sl_pool = sl_pool[np.isfinite(sl_pool) & (sl_pool > 0)]
    rr_pool = rr_obs.to_numpy(float) if len(rr_obs) else np.array([rr_med])
    rr_pool = rr_pool[np.isfinite(rr_pool) & (rr_pool > 0)]

    n_by_side = {s: int((tr['direction'] == s).sum()) for s in ('long', 'short')}
    print(f'  {asset}: n={len(tr)}  long={n_by_side["long"]} short={n_by_side["short"]}  '
          f'SLmed={np.median(sl_pool):.1f}pip  rr_med={rr_med:.2f}', flush=True)

    nul = {}
    for side in ('long', 'short'):
        if n_by_side[side] <= 0:
            nul[side] = {}
            continue
        print(f'    building null [{side}] K={PERM_K} ...', flush=True)
        nb = null_variable_geom(df, asset, sl_pool, rr_pool, side,
                                n_by_side[side])
        nul[side] = nb or {}
        if nb:
            print(f'      uncond={nb["uncond_wr"]}  perm_mean={nb["perm_mean"]:.2f} '
                  f'sd={nb["perm_sd"]:.2f} max={nb["perm_max"]:.2f}', flush=True)

    bt = bar_time_of(df)
    split_bar = int(len(df) * 0.70)
    r = R.compute_rqs2(tr, asset, sl_pip=float(np.median(sl_pool)),
                       tp_pip=float(np.median(sl_pool) * rr_med),
                       bar_time=bt, null=nul, n_trials=N_TRIALS,
                       split_bar=split_bar,
                       close=df['close'].to_numpy(float))
    r['card'] = f'{asset}-{TF}'
    r['rr_med_estimated'] = rr_med
    r['null_built'] = any(bool(v) for v in nul.values())
    return r


def main():
    per_card = []
    for asset in CARDS:
        print(f'\n══ judging {asset}-{TF} ══', flush=True)
        r = judge_asset(asset)
        per_card.append(r)
        print('  ' + summarize(r), flush=True)
        # ثبتِ فوریِ تجمعی پس از هر کارت — قانونِ «اندک اندک»
        p = save_verdict(LAYER_FILE, per_card,
                         {'engine_note': 'S69 reproduced bit-exact vs archive',
                          'max_hold': MAX_HOLD, 'n_trials': N_TRIALS,
                          'null_geometry': 'bootstrap from layer real SL/rr pools'})
        print(f'  saved -> {p}', flush=True)


if __name__ == '__main__':
    main()
