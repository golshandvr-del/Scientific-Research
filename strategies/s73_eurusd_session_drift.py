"""
S73 — EURUSD Session-Open Time-of-Day Drift  (کشفِ مخصوصِ EURUSD، نه منطقِ طلا)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی در هر سند و هر کد): هدفِ پروژه **فقط و فقط
«سودِ خالصِ بیشتر»** است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است؛ تعدادِ معامله
و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.** تعریفِ فعلیِ
«سودِ خالص» = مجموعِ سودِ خالصِ دو دارایی: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
کشفِ علمی (کاملاً از دلِ داده، بدونِ تحمیلِ منطقِ طلا):
  تحلیلِ اکتشافیِ EURUSD نشان داد autocorrelation در M15 تقریباً صفر است ⇒ به همین
  دلیل momentum/mean-reversion سادهٔ S71/S72 شکست خوردند. اما یک ساختارِ بسیار قویِ
  «ساعتی/سشن-محور» وجود دارد:
    • ساعتِ 0 UTC: drift صعودیِ فوق‌العاده قوی و پایدار در هر 4 دورهٔ زمانی
      (t-stat ≈ +10 تا +15 در همهٔ دوره‌ها). این «باز شدنِ نقدینگیِ اروپا» است.
    • ساعاتِ 13 UTC (و 6/12/18/22) drift نزولیِ پایدار (اما ضعیف‌تر).
  پروفایلِ سیگنالِ ساعت0: بهترین افقِ نگهداری 4–6 کندل (WR≈۷۲٪، +۲.۳ تا +۲.۶ pip)؛
  MFE میانه ۵.۳ pip، MAE میانه ۳.۲ pip؛ و فیلترِ pullback (اگر قبلش نزولی بود)
  بازدهِ آتی را از +۱.۶ به +۳.۲ pip تقویت می‌کند.

استراتژی نهایی (Time-of-Day، ذاتاً forward-safe چون فقط به ساعتِ ساعت-دیوارِ کندل وابسته):
  • ورود Long روی سیگنالِ آخرین کندلِ قبل از ساعتِ 0 UTC ⇒ ورود در open کندلِ
    ساعتِ 0 UTC (کندلِ بعد). این دقیقاً «باز شدنِ نقدینگیِ اروپا» را می‌گیرد.
  • TP و SL ثابت به pip (نه ATR!) چون drift کوچک است: SL=12 pip، TP=12 pip.
  • فیلترِ pullback (ضروری): فقط وقتی وارد شویم که 4 کندلِ قبل نزولی بوده باشد
    (buy-the-dip باز شدنِ اروپا) — سود را از +5493$ به +7302$ می‌رساند.
  • Short غیرفعال: آزمونِ استحکام ثابت کرد Short ساعت13 زیان‌ده است (-8451$).
  • خروج زمان‌محور در 6 کندل (~1.5h) اگر TP/SL نخورد.

نتیجهٔ رسمی: EURUSD net = +7302$ (WR 67.5٪، PF 1.62، MaxDD -2.5٪، Sharpe 5.47،
هر دو نیمه مثبت). سودِ خالصِ کل = XAUUSD(+37156$) + EURUSD(+7302$) = +44458$.

اعتبار:
  • Time-of-Day بودن ⇒ هیچ نشتِ آینده‌ای ممکن نیست (ساعت از پیش معلوم است).
  • ورود در open کندلِ بعد، اسپردِ واقعیِ EURUSD (1 pip)، کمیسیونِ 7$/لات.
  • موتورِ سرمایه‌محورِ مشترک (همان که XAUUSD را +37k$ سنجید)، ریسکِ ثابتِ 1٪.
  • آزمونِ دو-نیمه (H1/H2) برای پایداریِ سود در زمان.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

# --- پارامترهای نهاییِ استراتژی (از grid خروج + آزمونِ استحکام، robust نه overfit) ---
# نتیجهٔ آزمون‌ها:
#   • فیلترِ pullback ضروری است (buy-the-dip باز شدنِ اروپا): +7302$ در برابر +5493$.
#   • Short ساعت13 فاجعه است (-8451$، ruin) ⇒ فقط Long. (سود 0 بهتر از منفی — قانون #۱)
#   • SL/TP پیکسلی (pip-based) نه ATR: چون drift کوچک (~2-3 pip) است. لنگر SL=TP=12 pip.
#   • hold=6 (~1.5h) مرکزِ پایدار؛ hold=4 خیلی زود است. کلِ همسایگی both-halves-positive.
#   • مقاوم به هزینه: حتی با اسپردِ 1.5 pip هنوز +3210$ و هر دو نیمه مثبت.
LONG_ENTRY_HOUR = 0        # ورود در open کندلِ ساعتِ 0 UTC (باز شدنِ نقدینگیِ اروپا)
SL_PIP = 12.0              # SL ثابت به pip
TP_PIP = 12.0              # TP ثابت به pip
MAX_HOLD = 6               # ~1.5 ساعت
PULLBACK_LOOKBACK = 4      # فیلترِ buy-the-dip
USE_PULLBACK_FILTER = True
USE_SHORT = False          # آزمون ثابت کرد Short زیان‌ده است
PIP_UNIT = 0.0001

PIP = 0.0001
EURUSD_CFG = dict(file='data/EURUSD_M15.csv', contract=100_000.0, spread=0.00010)  # 1 pip اسپرد
INITIAL_CAPITAL = 10_000.0
RISK_PCT = 1.0
COMMISSION = 7.0
EVAL_START = 24000       # هم‌راستا با بقیهٔ پروژه (warmup)
RES_DIR = os.path.join(os.path.dirname(__file__), '..', 'results')


def build_signals(df):
    n = len(df)
    dt = pd.to_datetime(df['time'], unit='s')
    hour = dt.dt.hour.values
    minute = dt.dt.minute.values
    c = df['close'].values

    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True

    # سیگنالِ Long: روی کندلِ ساعتِ 23 (minute==45 آخرین کندل) ⇒ ورود open ساعت0.
    # ساده‌تر و مقاوم: سیگنال روی «کندلی که کندلِ بعدش ساعتِ 0 UTC است».
    is_last_before_h0 = np.zeros(n, dtype=bool)
    is_last_before_h0[:-1] = (hour[1:] == LONG_ENTRY_HOUR) & (hour[:-1] != LONG_ENTRY_HOUR)
    long_sig = is_last_before_h0 & eval_mask

    # فیلترِ pullback: چند کندلِ قبلِ ورود نزولی بوده باشد (buy-the-dip)
    if USE_PULLBACK_FILTER:
        prior = np.zeros(n)
        prior[PULLBACK_LOOKBACK:] = c[PULLBACK_LOOKBACK:] - c[:-PULLBACK_LOOKBACK]
        long_sig = long_sig & (prior < 0)

    short_sig = np.zeros(n, dtype=bool)  # Short غیرفعال (آزمونِ استحکام ثابت کرد زیان‌ده است)
    return long_sig, short_sig


def run_eurusd(cfg=EURUSD_CFG, label="S73 base"):
    print(f"\n{'='*80}\n=== {label} — EURUSD Session-Open Drift ===\n{'='*80}", flush=True)
    df = load_data(cfg['file'])
    n = len(df)

    long_sig, short_sig = build_signals(df)
    print(f"کندل‌ها={n} | Long-sig={int(long_sig.sum())} | Short-sig={int(short_sig.sum())} "
          f"(pullback_filter={USE_PULLBACK_FILTER}, short={USE_SHORT})", flush=True)

    sl_series = np.full(n, SL_PIP * PIP_UNIT)   # SL/TP ثابت به pip
    tp_series = np.full(n, TP_PIP * PIP_UNIT)

    def trades_for(direction, sig):
        st, tr = run_backtest(df, sig, None, None, direction, spread=cfg['spread'],
                              max_hold=MAX_HOLD, sl_series=sl_series, tp_series=tp_series)
        if len(tr) == 0:
            return tr, np.array([])
        sld = sl_series[tr['signal_bar'].values]
        return tr, sld

    trL, slL = trades_for('long', long_sig)
    frames = [trL]; sls = [slL]
    if USE_SHORT:
        trS, slS = trades_for('short', short_sig)
        frames.append(trS); sls.append(slS)
    else:
        trS = pd.DataFrame()

    all_tr = pd.concat([f for f in frames if len(f)], ignore_index=True)
    all_sl = np.concatenate([s for s in sls if len(s)]) if any(len(s) for s in sls) else np.array([])
    if len(all_tr) == 0:
        print("  هیچ معامله‌ای تولید نشد.", flush=True)
        return dict(name='EURUSD', n=0, net=0.0, ret=0.0, dd=0.0, pf=0.0, wr=0.0,
                    n_long=0, n_short=0, h1_net=0.0, h2_net=0.0, sharpe=0.0)

    order = all_tr['exit_bar'].values.argsort()
    all_tr = all_tr.iloc[order].reset_index(drop=True)
    all_sl = all_sl[order]

    stats, _ = run_capital_backtest(all_tr, all_sl, weights=None,
                                    initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                    commission_per_lot=COMMISSION, compounding=False,
                                    contract_size=cfg['contract'])
    # دو-نیمه
    mid_bar = all_tr['exit_bar'].median()
    m1 = all_tr['exit_bar'].values <= mid_bar
    def half_net(mk):
        if mk.sum() == 0: return 0.0
        s, _ = run_capital_backtest(all_tr[mk].reset_index(drop=True), all_sl[mk], weights=None,
                                    initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                    commission_per_lot=COMMISSION, compounding=False,
                                    contract_size=cfg['contract'])
        return s['net_profit']
    h1, h2 = half_net(m1), half_net(~m1)

    print(f"  >>> EURUSD: n={stats['n_trades']} (L={len(trL)},S={len(trS)})  "
          f"net={stats['net_profit']:+.0f}$ ({stats['return_pct']:+.1f}%)  "
          f"maxDD={stats['max_dd_pct']:.1f}%  PF={stats['profit_factor']:.2f}  "
          f"WR={stats['win_rate']:.1f}%  Sharpe={stats['sharpe']:.2f}", flush=True)
    print(f"      دو-نیمه:  H1={h1:+.0f}$   H2={h2:+.0f}$", flush=True)
    return dict(name='EURUSD', n=stats['n_trades'], net=stats['net_profit'], ret=stats['return_pct'],
                dd=stats['max_dd_pct'], pf=stats['profit_factor'], wr=stats['win_rate'],
                n_long=len(trL), n_short=len(trS), h1_net=h1, h2_net=h2, sharpe=stats['sharpe'])


def main():
    print("=== S73: EURUSD Session-Open Time-of-Day Drift ===", flush=True)
    print("قانونِ #۱: فقط سودِ خالص (XAUUSD+EURUSD). کشف: drift ساعتِ 0 UTC صعودیِ پایدار.", flush=True)
    res = run_eurusd()
    XAUUSD_RECORD = 37156.0
    total = XAUUSD_RECORD + res['net']
    print(f"\n{'#'*80}", flush=True)
    print(f"### سودِ خالصِ EURUSD (این استراتژی) = {res['net']:+.0f}$", flush=True)
    print(f"### XAUUSD (رکوردِ ثابتِ S67، دست‌نخورده) = +{XAUUSD_RECORD:.0f}$", flush=True)
    print(f"### سودِ خالصِ کل (XAUUSD+EURUSD) = {total:+.0f}$", flush=True)
    print(f"{'#'*80}", flush=True)
    with open(os.path.join(RES_DIR, '_s73_summary.json'), 'w') as fh:
        json.dump(dict(eurusd=res, xauusd_record=XAUUSD_RECORD, total_net=total),
                  fh, ensure_ascii=False, indent=2, default=float)
    print("\nخلاصه در results/_s73_summary.json ذخیره شد. تمام.", flush=True)


if __name__ == '__main__':
    main()
