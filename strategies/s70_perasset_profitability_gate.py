"""
S70 — گیتِ سودآوریِ walk-forward برای هر دارایی (روی خروجیِ S69)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی در هر سند و هر کد): هدفِ پروژه **فقط و فقط
«سودِ خالصِ بیشتر»** است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است؛ تعدادِ معامله
و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.** تعریفِ فعلیِ
«سودِ خالص» = مجموعِ سودِ خالصِ چهار دارایی (XAUUSD+DXY+EURUSD+AUDUSD) به‌طورِ هم‌زمان.

--------------------------------------------------------------------------------
انگیزه (ادامهٔ یافتهٔ S69):
  S69 نشان داد منطقِ برندهٔ طلا روی EURUSD/AUDUSD **زیان‌ده** است (پرتفوی +۱۲٬۸۴۴$،
  کمتر از S67 تک‌طلا +۳۷٬۱۵۶$). راه‌حلِ طبقِ قانونِ #۱: **زیان نکنیم.** یک «گیتِ
  سودآوریِ walk-forward» می‌گذاریم که برای هر دارایی، فقط وقتی اجازهٔ معامله می‌دهد
  که استراتژی روی همان دارایی در **گذشتهٔ اخیرِ خودش** سودده بوده باشد.

روشِ گیت (کاملاً forward-safe — فقط از گذشته):
  معاملاتِ هر دارایی به ترتیبِ زمانِ خروج مرتب می‌شوند. برای هر معاملهٔ i:
    • به pnlِ سرمایه‌محورِ K معاملهٔ *قبلیِ همان دارایی* (پنجرهٔ لغزان) نگاه می‌کنیم.
    • اگر مجموعِ آن پنجره ≤ آستانه بود → این معامله **رد** می‌شود (اجازهٔ ورود نداریم).
    • K معاملهٔ اولِ هر دارایی (که هنوز تاریخچه نداریم) طبقِ سیاستِ warmup تصمیم می‌شود:
        - 'gold_only' : در warmup فقط طلا مجاز است (چون a-priori می‌دانیم لبهٔ طلاست).
        - 'allow'     : در warmup همه مجازند (بدونِ پیش‌داوری، محافظه‌کارتر برای اعتبار).
  چون تصمیمِ هر معامله فقط به معاملاتِ قبل‌ترِ خودش وابسته است، هیچ نشتِ آینده ندارد.

  ⚠️ نکتهٔ اعتبار: خودِ «گیت» یک لایهٔ تصمیمِ اضافه است؛ برای اینکه صادقانه باشد،
  آستانه و K را ثابت و ساده نگه می‌داریم (بدونِ بهینه‌سازیِ روی کلِ داده). سپس آزمونِ
  دو-نیمه را روی نتیجهٔ گیت‌شده هم گزارش می‌کنیم.

ورودی: results/_s69_trades_<asset>.csv (ستون‌های trades + sl_dist + kelly_w)
خروجی: چاپِ سودِ خالصِ پرتفویِ گیت‌شده + ذخیرهٔ results/_s70_summary.json
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from capital_engine import run_capital_backtest

RES_DIR = os.path.join(os.path.dirname(__file__), '..', 'results')

ASSETS = {
    'XAUUSD': dict(contract=100.0,     tradable=True),
    'EURUSD': dict(contract=100_000.0, tradable=True),
    'AUDUSD': dict(contract=100_000.0, tradable=True),
    'DXY':    dict(contract=1_000.0,   tradable=True),
}
INITIAL_CAPITAL = 10_000.0
RISK_PCT = 1.0
COMMISSION = 7.0

# --- پارامترهای گیت (ساده و ثابت — بدونِ بهینه‌سازیِ روی کلِ داده) ---
GATE_K = 40              # پنجرهٔ لغزانِ تعدادِ معاملهٔ اخیرِ همان دارایی
GATE_THR = 0.0           # آستانهٔ سودِ خالصِ پنجره (≤0 ⇒ خاموش)
WARMUP_POLICY = 'gold_only'   # 'gold_only' | 'allow'


def per_trade_pnl(tr, sl, w, contract):
    """pnlِ سرمایه‌محورِ تک‌تکِ معاملات (ریسکِ ثابتِ ۱٪) — برای ساختِ سیگنالِ گیت."""
    # ریسکِ ثابت: هر معامله روی سرمایهٔ اولیه حساب می‌شود (نه مرکب) تا سیگنالِ گیت پایدار بماند.
    stats, eq = run_capital_backtest(tr, sl, weights=w,
                                     initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                     commission_per_lot=COMMISSION, compounding=False,
                                     contract_size=contract)
    # eq تجمعی است؛ pnlِ هر معامله = تفاضلِ متوالیِ equity
    eq = np.asarray(eq, dtype=np.float64)
    pnl = np.diff(eq)   # طول n (چون eq طولِ n+1 دارد و با initial شروع می‌شود)
    return pnl, stats


def apply_gate(name, contract):
    """گیتِ سودآوریِ walk-forward را روی معاملاتِ یک دارایی اعمال و ماسکِ مجاز را برمی‌گرداند."""
    p = os.path.join(RES_DIR, f'_s69_trades_{name}.csv')
    if not os.path.exists(p):
        return None
    tr = pd.read_csv(p)
    if len(tr) == 0:
        return dict(name=name, tr=tr, mask=np.array([], dtype=bool))
    tr = tr.sort_values('exit_bar').reset_index(drop=True)
    sl = tr['sl_dist'].values
    w = tr['kelly_w'].values
    pnl, _ = per_trade_pnl(tr, sl, w, contract)
    n = len(tr)
    mask = np.zeros(n, dtype=bool)
    for i in range(n):
        if i < GATE_K:
            # warmup: هنوز تاریخچهٔ کافی نداریم
            if WARMUP_POLICY == 'gold_only':
                mask[i] = (name == 'XAUUSD')
            else:
                mask[i] = True
        else:
            recent = pnl[i - GATE_K:i].sum()   # فقط گذشته — forward-safe
            mask[i] = recent > GATE_THR
    return dict(name=name, tr=tr, sl=sl, w=w, mask=mask, pnl_all=pnl)


def eval_gated(name, contract, g):
    """سودِ خالصِ دارایی پس از اعمالِ گیت را با موتورِ سرمایه محاسبه می‌کند."""
    tr, sl, w, mask = g['tr'], g['sl'], g['w'], g['mask']
    if mask.sum() == 0:
        return dict(name=name, n=0, net=0.0, ret=0.0, dd=0.0, pf=0.0, wr=0.0,
                    h1_net=0.0, h2_net=0.0, n_raw=len(tr))
    trg = tr[mask].reset_index(drop=True)
    slg = sl[mask]; wg = w[mask]
    stats, _ = run_capital_backtest(trg, slg, weights=wg,
                                    initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                    commission_per_lot=COMMISSION, compounding=False,
                                    contract_size=contract)
    # دو-نیمه
    mid = trg['exit_bar'].median()
    m1 = trg['exit_bar'].values <= mid
    def half_net(mk):
        if mk.sum() == 0:
            return 0.0
        s, _ = run_capital_backtest(trg[mk].reset_index(drop=True), slg[mk], weights=wg[mk],
                                    initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                    commission_per_lot=COMMISSION, compounding=False,
                                    contract_size=contract)
        return s['net_profit']
    return dict(name=name, n=stats['n_trades'], net=stats['net_profit'],
                ret=stats['return_pct'], dd=stats['max_dd_pct'], pf=stats['profit_factor'],
                wr=stats['win_rate'], h1_net=half_net(m1), h2_net=half_net(~m1),
                n_raw=len(tr))


def main():
    print("=== S70: گیتِ سودآوریِ walk-forward برای هر دارایی ===", flush=True)
    print(f"قانونِ #۱: فقط سودِ خالص. گیت: K={GATE_K}, آستانه={GATE_THR}, warmup={WARMUP_POLICY}", flush=True)
    print(f"{'دارایی':10s} {'خام n':>6s} {'گیت n':>6s} {'خام net$':>11s} {'گیت net$':>11s} "
          f"{'PF':>6s} {'WR%':>6s} {'H1$':>9s} {'H2$':>9s}", flush=True)

    results = {}
    total_raw = 0.0; total_gated = 0.0
    for name, cfg in ASSETS.items():
        g = apply_gate(name, cfg['contract'])
        if g is None or 'mask' not in g:
            # DXY خام صفر معامله دارد
            results[name] = dict(name=name, n=0, net=0.0, n_raw=0, raw_net=0.0,
                                 pf=0.0, wr=0.0, h1_net=0.0, h2_net=0.0)
            print(f"{name:10s} {0:6d} {0:6d} {0:+11.0f} {0:+11.0f} {'—':>6s} {'—':>6s}", flush=True)
            continue
        # سودِ خام (بدونِ گیت) برای مقایسه
        tr = g['tr']; sl = g['sl']; w = g['w']
        raw_stats, _ = run_capital_backtest(tr, sl, weights=w,
                                            initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                            commission_per_lot=COMMISSION, compounding=False,
                                            contract_size=cfg['contract'])
        e = eval_gated(name, cfg['contract'], g)
        e['raw_net'] = raw_stats['net_profit']; e['raw_n'] = raw_stats['n_trades']
        results[name] = e
        total_raw += raw_stats['net_profit']; total_gated += e['net']
        print(f"{name:10s} {raw_stats['n_trades']:6d} {e['n']:6d} {raw_stats['net_profit']:+11.0f} "
              f"{e['net']:+11.0f} {e['pf']:6.2f} {e['wr']:6.1f} {e['h1_net']:+9.0f} {e['h2_net']:+9.0f}", flush=True)

    print("-" * 90, flush=True)
    print(f"{'جمعِ کل':10s} {'':6s} {'':6s} {total_raw:+11.0f} {total_gated:+11.0f}", flush=True)
    print(f"\n★ سودِ خالصِ پرتفویِ خام (بدونِ گیت)      = {total_raw:+.0f}$", flush=True)
    print(f"★ سودِ خالصِ پرتفویِ گیت‌شده (S70)          = {total_gated:+.0f}$", flush=True)
    print(f"  مقایسه: رکوردِ فعلی S67 (فقط XAUUSD)      = +37,156$", flush=True)

    out = {name: {k: v for k, v in results[name].items()} for name in ASSETS}
    out['_portfolio'] = dict(total_raw=total_raw, total_gated=total_gated,
                             gate_K=GATE_K, gate_thr=GATE_THR, warmup=WARMUP_POLICY)
    with open(os.path.join(RES_DIR, '_s70_summary.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\nخلاصه در results/_s70_summary.json ذخیره شد. تمام.", flush=True)


if __name__ == '__main__':
    main()
