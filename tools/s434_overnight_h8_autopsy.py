"""
s434_overnight_h8_autopsy.py — کالبدشکافیِ دروازهٔ H8 برای لایهٔ S139 «رانشِ شبانه»
================================================================================
هدف (S434، مأموریت ۴ — احیای سوخته‌ها):
  لایهٔ S139 در فهرستِ اولویت تنها دروازهٔ `H8` را می‌افتد. اما `H8` یک عطفِ سه‌جزئی است:

      h8 = (maxdd_pct <= 8.0) و (mcl <= mcl_allowed) و (recovery >= 3.0)

  پس «H8 افتاد» هیچ راهنمایی برای بهبود نمی‌دهد. این ابزار **کدام جزء** را
  می‌سنجد، در **هر تایم‌فریمِ طلا مستقلاً** (قانونِ اولِ پروژه: MTF).

چرا این گام قبل از هر بهبودی لازم است:
  در S307 (تلاشِ احیای قبلی) چهار خانوادهٔ بهبود کورکورانه جارو شد و همه شکست
  خورد. علتش در S434/E-15 روشن شد: آن جاروب هندسه را از TP=3.33×SL به TP=SL
  برد و نقطهٔ سربه‌سر را از ۲۳.۶٪ به ۵۰.۸٪ **بالا** برد. یعنی جاروبِ کور،
  بودجهٔ معامله را خرج کرد. این ابزار عمداً **هیچ بهبودی اعمال نمی‌کند** —
  فقط پایه (baseline) را با هندسهٔ اصلی می‌سنجد تا بدانیم دقیقاً چه چیزی
  باید درست شود.

روشِ ضدِ خودفریبی:
  • هندسهٔ اصلیِ S139 دست‌نخورده: SL=150 · TP=500 (نسبت 1:3.33).
  • `max_hold` برای هر تایم‌فریم به **زمانِ ثابتِ ۲۴ ساعت** تبدیل می‌شود، نه
    عددِ ثابتِ کندل. اگر ۹۶ کندل را روی H1 هم به کار می‌بردم، پنجرهٔ هولد
    ۴ روز می‌شد — یعنی لایهٔ دیگری را می‌آزمودم و نامش را S139 می‌گذاشتم.
    (این همان اشتباهِ رایجِ ۶ است: پارامترِ یکسان برای همهٔ تایم‌فریم‌ها.)
  • ساعتِ سیگنال از UTC خوانده می‌شود، همان‌طور که اسکریپتِ اصلی می‌خواند.
  • هیچ فیلتری اعمال نمی‌شود. این پایه است، نه نامزد.

خروجی: results/_s434_h8/autopsy_<TF>.json  (هر تایم‌فریم مستقل ذخیره می‌شود تا
        ریست شدنِ سندباکس کارِ انجام‌شده را نبَرَد — قانونِ سومِ پروژه)
"""
import os, sys, json, argparse

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs2 as R

OUT_DIR = os.path.join(ROOT, 'results', '_s434_h8')

# هندسهٔ اصلیِ S139 — عمداً دست‌نخورده (تعهدِ پیش‌ثبت‌شدهٔ S434)
SL_PIP = 150.0
TP_PIP = 500.0
HOLD_HOURS = 24.0          # پنجرهٔ هولدِ اصلی = ۹۶ کندلِ M15 = ۲۴ ساعت
SIGNAL_HOURS = (22, 23)    # ساعاتِ UTC طبقِ سندِ اصلیِ S139

# دقیقهٔ هر تایم‌فریم ⇒ برای تبدیلِ ۲۴ ساعت به تعدادِ کندل
TF_MINUTES = {'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
              'H1': 60, 'H4': 240, 'D1': 1440, 'W1': 10080}


def bars_for_hours(tf, hours):
    """تبدیلِ پنجرهٔ زمانی به تعدادِ کندل — نه عددِ ثابت برای همهٔ TFها."""
    m = TF_MINUTES[tf]
    return max(1, int(round(hours * 60.0 / m)))


def build_signals(df, hours):
    """سیگنالِ LONG روی کندلی که ساعتِ UTC آن در `hours` است.

    عیناً همان منطقِ strategies/s139_gold_overnight_drift.py — بازسازی نمی‌کنم
    تا خطای «آزمودنِ لایهٔ دیگر به نامِ S139» رخ ندهد.
    """
    hour = pd.to_datetime(df['time'], unit='s').dt.hour.values
    sig = np.zeros(len(df), bool)
    for h in hours:
        sig |= (hour == h)
    return sig


def h8_parts(trades, asset, initial_capital=10000.0):
    """سه جزءِ H8 را جدا محاسبه می‌کند، با همان توابعِ موتور (نه بازنویسی).

    چرا با توابعِ موتور: اگر maxDD را خودم دوباره پیاده کنم، ممکن است عددی
    بگیرم که موتور نمی‌گیرد و بعد «بهبودی» بسازم که دروازهٔ واقعی را
    راضی نمی‌کند. پس مرجع، خودِ موتور است.
    """
    tr = trades.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    outcomes = tr['outcome'].tolist()
    wins = sum(1 for o in outcomes if o == 'win')
    wr = wins / n * 100.0 if n else 0.0

    mcl = R.max_consec_losses(outcomes)
    mcl_allow = R.mcl_bound(n, wr)
    return {'n': n, 'wr': wr, 'mcl': int(mcl), 'mcl_allowed': int(mcl_allow)}


def run_tf(asset, tf, verbose=True):
    path = os.path.join(ROOT, 'data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return {'asset': asset, 'tf': tf, 'skipped': 'no data file'}

    df = se.load_data(path)
    mh = bars_for_hours(tf, HOLD_HOURS)
    sig = build_signals(df, SIGNAL_HOURS)
    n_sig = int(sig.sum())

    if verbose:
        print(f'[{asset}-{tf}] bars={len(df)}  signals={n_sig}  max_hold={mh} bars '
              f'(= {HOLD_HOURS}h)', flush=True)

    if n_sig == 0:
        return {'asset': asset, 'tf': tf, 'bars': len(df), 'n_signals': 0,
                'skipped': 'no signal bars at hours 22/23 UTC'}

    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, SL_PIP, TP_PIP, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return {'asset': asset, 'tf': tf, 'bars': len(df),
                'n_signals': n_sig, 'skipped': 'no trades'}

    parts = h8_parts(tr, asset)

    # داوریِ کاملِ v2.6 — بدونِ null/n_trials هنوز، چون این گام تشخیصی است و
    # ادعای ACCEPT نمی‌کند. هدف: دیدنِ دروازه‌ها و سنجه‌های دنباله.
    res = R.compute_rqs2(tr, asset, sl_pip=SL_PIP, tp_pip=TP_PIP,
                         bar_time=df['time'].values, close=df['close'].values)
    m = res.get('metrics', {})
    g = res.get('gates', {})

    be = R.breakeven_wr_cost(SL_PIP, TP_PIP, se.ASSETS[asset]['spread_pip']
                             + se.ASSETS[asset]['slip_pip'])

    out = {
        'asset': asset, 'tf': tf, 'bars': int(len(df)),
        'n_signals': n_sig,
        'geometry': {'sl_pip': SL_PIP, 'tp_pip': TP_PIP,
                     'max_hold_bars': mh, 'hold_hours': HOLD_HOURS,
                     'signal_hours_utc': list(SIGNAL_HOURS)},
        'h8_parts': parts,
        'breakeven_wr': round(be, 3) if be is not None else None,
        # ⚠️ BUG-METRICKEYS (S434) — نامِ این کلیدها را در نسخهٔ اول *حدس* زده بودم
        #   (`wr_pct`, `maxdd_pct`, `mcl`, `recovery`, `net_pip`) و همه `None`
        #   برگشتند. خطرِ واقعی: خروجی «کار کرد» و هیچ استثنایی نداد — یعنی
        #   کالبدشکافیِ H8 با هر سه جزءِ نامعلوم گزارش می‌شد و من می‌توانستم
        #   نتیجه بگیرم «maxDD مشکل نیست». نام‌ها از خودِ موتور استخراج شدند.
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'expectancy_at_2x_cost',
            'rr', 'top_win_share', 'max_concurrency')},
        'gates': {k: g.get(k) for k in sorted(g)},
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'notes': res.get('notes', []),
    }
    # حاشیهٔ لبه = WR واقعی − سربه‌سر (سنجهٔ درست، نه WR خام)
    wr_real = m.get('win_rate')
    if wr_real is not None and be is not None:
        out['edge_margin_pp'] = round(float(wr_real) - be, 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default='M5,M15,M30,H1,H4,D1,W1')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    for tf in [t.strip() for t in args.tfs.split(',') if t.strip()]:
        try:
            out = run_tf(args.asset, tf)
        except Exception as e:
            out = {'asset': args.asset, 'tf': tf, 'error': f'{type(e).__name__}: {e}'}
        fp = os.path.join(OUT_DIR, f'autopsy_{args.asset}_{tf}.json')
        with open(fp, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        # چاپِ خلاصه بلافاصله — تا اگر سندباکس مرد، لاگ باقی بماند
        if 'error' in out:
            print(f'  !! {tf}: {out["error"]}', flush=True)
        elif 'skipped' in out:
            print(f'  -- {tf}: skipped ({out["skipped"]})', flush=True)
        else:
            m = out['metrics']
            fails = [k for k, v in out['gates'].items() if v is False]
            print(f'  == {tf}: n={m["n_trades"]} wr={m["win_rate"]}% '
                  f'exp={m["expectancy_pip"]} pf={m["profit_factor"]} '
                  f'dd={m["max_dd_pct"]}% '
                  f'mcl={m["max_consec_losses"]}/{m["mcl_allowed"]} '
                  f'rec={m["recovery_factor"]} '
                  f'edge_margin={out.get("edge_margin_pp")}pp '
                  f'verdict={out["verdict"]} failed={fails}', flush=True)
    print('[done]', flush=True)


if __name__ == '__main__':
    main()
