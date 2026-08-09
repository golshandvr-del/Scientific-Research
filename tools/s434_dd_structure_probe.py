"""
s434_dd_structure_probe.py — کاوشِ **ساختارِ** افتِ سرمایه در لایهٔ S139
================================================================================
هدف: افتِ سرمایه (maxDD) تنها جزءِ شکسته‌شدهٔ H8 است (S434 گام ۵). اما پیش از
     ساختنِ هر فیلتری باید بدانم افت **از کجا** می‌آید. سه فرضیهٔ رقیب:

  فرضیهٔ A — «رژیمِ نزولیِ کلان»: لایه فقط LONG است، پس در بازارِ نزولیِ ممتد
             هر شب ضرر می‌کند و افت انباشته می‌شود. ⇒ درمان: فیلترِ رژیم.
  فرضیهٔ B — «خوشهٔ تقویمی»: افت در یک بازهٔ تاریخیِ خاص متمرکز است (مثلاً یک
             بحرانِ خاص). ⇒ درمان: احتمالاً هیچ؛ این نشانهٔ شکنندگی است.
  فرضیهٔ C — «نویزِ پراکنده»: افت از زیان‌های کوچکِ پخش‌شده می‌آید، بدون تمرکز.
             ⇒ درمان: فیلترِ کیفیتِ سیگنال (نه رژیم).

روشِ تفکیک — چرا این‌ها را می‌سنجم و نه چیزِ دیگر:
  1) منحنیِ equity را می‌سازم و **بازهٔ دقیقِ بیشترین افت** را استخراج می‌کنم
     (تاریخِ قله تا تاریخِ دره). اگر آن بازه کوتاه و یگانه باشد ⇒ فرضیهٔ B.
  2) هر معامله را با **جهتِ رژیمِ کلان** برچسب می‌زنم و انتظارِ ریاضی را در دو
     رژیم جدا می‌سنجم. اگر تفاوت بزرگ باشد ⇒ فرضیهٔ A.
  3) سهمِ افت را می‌شمارم: چند درصدِ کلِ زیان از بدترین ۵٪ معاملات است.
     اگر پخش باشد ⇒ فرضیهٔ C.

نکتهٔ روش‌شناختی (ضدِ اشتباهِ رایجِ ۷ — شبکهٔ محدودِ اعداد):
  برای «رژیم» **یک** تعریف به کار نمی‌برم. سه تعریفِ مستقل را همزمان می‌سنجم:
    • MA بلند (close نسبت به SMA) — تعریفِ کلاسیک
    • شیبِ بازدهِ تجمعیِ k-روزه — تعریفِ بی‌اندیکاتور
    • ATR-نرمال‌شدهٔ فاصله از قله — تعریفِ نوسان-محور
  و طولِ پنجره را از یک شبکهٔ **غیرِرند** انتخاب می‌کنم (۹۳، ۱۳۷، ۱۸۹، ۲۴۱ …)
  تا در دامِ ۵۰/۱۰۰/۲۰۰ نیفتم. هدفِ این گام «یافتنِ بهترین عدد» نیست، بلکه
  دیدنِ این است که **آیا اثر به تعریف حساس است یا نه** — اثری که فقط با یک
  تعریفِ خاص ظاهر شود، مشکوک است.

این ابزار **هیچ حکمی صادر نمی‌کند** و هیچ فیلتری را نمی‌پذیرد؛ فقط تشخیص است.
"""
import os, sys, json, argparse

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se

OUT_DIR = os.path.join(ROOT, 'results', '_s434_h8')

SL_PIP, TP_PIP = 150.0, 500.0
HOLD_HOURS = 24.0
SIGNAL_HOURS = (22, 23)
TF_MINUTES = {'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60}

# شبکهٔ عمداً غیرِرند برای طولِ پنجرهٔ رژیم (اشتباهِ رایجِ ۷)
REGIME_WINDOWS_BARS_PER_DAY = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24}
REGIME_DAYS = (7, 13, 23, 41, 67)      # روز — نه ۱۰/۲۰/۵۰/۱۰۰


def build_signals(df, hours):
    hour = pd.to_datetime(df['time'], unit='s').dt.hour.values
    sig = np.zeros(len(df), bool)
    for h in hours:
        sig |= (hour == h)
    return sig


def equity_and_dd(pnl):
    """منحنیِ equity بر حسبِ pip و بازهٔ بیشترین افت (اندیسِ قله و دره)."""
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(eq)
    dd = eq - peak
    i_trough = int(np.argmin(dd))
    i_peak = int(np.argmax(eq[:i_trough + 1])) if i_trough > 0 else 0
    return eq, dd, i_peak, i_trough


def regime_labels(df, tf):
    """سه تعریفِ مستقلِ رژیم ⇒ دیکشنری از آرایه‌های بولین (True = رژیمِ صعودی).

    هیچ‌کدام از آینده استفاده نمی‌کند: همه با shift(1) عقب‌کشیده می‌شوند تا
    برچسبِ کندلِ i تنها از اطلاعاتِ تا i-1 ساخته شود.
    """
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    bpd = REGIME_WINDOWS_BARS_PER_DAY[tf]
    out = {}

    for d in REGIME_DAYS:
        w = max(2, d * bpd)
        s = pd.Series(close)

        # تعریفِ ۱ — MA بلند
        ma = s.rolling(w, min_periods=w).mean().shift(1).values
        out[f'ma_{d}d'] = np.where(np.isnan(ma), False, close > ma)

        # تعریفِ ۲ — شیبِ بازدهِ تجمعی (بی‌اندیکاتور)
        prev = s.shift(w).values
        with np.errstate(invalid='ignore'):
            ret = (close - prev) / np.where(prev == 0, np.nan, prev)
        ret_lag = pd.Series(ret).shift(1).values
        out[f'mom_{d}d'] = np.where(np.isnan(ret_lag), False, ret_lag > 0)

        # تعریفِ ۳ — فاصله از قلهٔ w-کندلی نرمال‌شده با ATR
        roll_max = s.rolling(w, min_periods=w).max().shift(1).values
        tr = pd.Series(high - low).rolling(14, min_periods=14).mean().shift(1).values
        with np.errstate(invalid='ignore'):
            depth = (roll_max - close) / np.where((tr == 0) | np.isnan(tr), np.nan, tr)
        # «نزدیکِ قله» = رژیمِ سالم (عمقِ کمتر از ۳ برابرِ ATR)
        out[f'peak_{d}d'] = np.where(np.isnan(depth), False, depth < 3.0)
    return out


def run_tf(asset, tf):
    path = os.path.join(ROOT, 'data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return {'asset': asset, 'tf': tf, 'skipped': 'no data'}
    df = se.load_data(path)
    mh = max(1, int(round(HOLD_HOURS * 60.0 / TF_MINUTES[tf])))
    sig = build_signals(df, SIGNAL_HOURS)
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, SL_PIP, TP_PIP, asset,
                            max_hold=mh, allow_overlap=False)
    tr = tr.sort_values('exit_bar').reset_index(drop=True)
    pnl = tr['pnl_pip'].values.astype(np.float64)
    n = len(tr)

    eq, dd, i_peak, i_trough = equity_and_dd(pnl)
    times = pd.to_datetime(df['time'].values, unit='s')
    t_entry = times[tr['entry_bar'].values.astype(int)]

    # --- فرضیهٔ B: تمرکزِ تقویمیِ افت ---
    seg = slice(i_peak, i_trough + 1)
    dd_trades = int(i_trough - i_peak + 1)
    dd_pip = float(eq[i_trough] - eq[i_peak])
    dd_start = str(t_entry[i_peak].date()) if n else None
    dd_end = str(t_entry[i_trough].date()) if n else None
    span_days = ((t_entry[i_trough] - t_entry[i_peak]).days) if n else None

    # --- فرضیهٔ C: تمرکزِ زیان در دنبالهٔ بدترین معاملات ---
    losses = np.sort(pnl[pnl < 0])          # صعودی: بدترین اول
    tot_loss = float(-losses.sum()) if len(losses) else 0.0
    k5 = max(1, int(round(0.05 * n)))
    worst5_share = (float(-losses[:k5].sum()) / tot_loss * 100.0) if tot_loss > 0 else None

    # --- فرضیهٔ A: تفکیکِ انتظارِ ریاضی بر حسبِ رژیم ---
    regs = regime_labels(df, tf)
    ent = tr['entry_bar'].values.astype(int)
    reg_stats = {}
    for name, arr in regs.items():
        lab = arr[ent]
        for side, mask in (('bull', lab), ('bear', ~lab)):
            sub = pnl[mask]
            if len(sub) == 0:
                reg_stats[f'{name}|{side}'] = None
                continue
            e2, d2, p2, t2 = equity_and_dd(sub)
            reg_stats[f'{name}|{side}'] = {
                'n': int(len(sub)),
                'exp_pip': round(float(sub.mean()), 3),
                'net_pip': round(float(sub.sum()), 1),
                'wr': round(float((sub > 0).mean() * 100.0), 2),
                'maxdd_pip': round(float(d2.min()), 1),
            }
    return {
        'asset': asset, 'tf': tf, 'n_trades': n,
        'total_net_pip': round(float(pnl.sum()), 1),
        'worst_dd': {'pip': round(dd_pip, 1), 'n_trades_in_dd': dd_trades,
                     'from': dd_start, 'to': dd_end, 'span_days': span_days,
                     'share_of_net_pct': (round(abs(dd_pip) / abs(float(pnl.sum())) * 100.0, 1)
                                          if pnl.sum() != 0 else None)},
        'loss_concentration': {'worst5pct_share_of_total_loss': (round(worst5_share, 1)
                                                                if worst5_share else None),
                               'n_losses': int(len(losses))},
        'regime_split': reg_stats,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default='M5,M15,M30,H1')
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    for tf in [t.strip() for t in args.tfs.split(',') if t.strip()]:
        try:
            out = run_tf(args.asset, tf)
        except Exception as e:
            out = {'asset': args.asset, 'tf': tf, 'error': f'{type(e).__name__}: {e}'}
        fp = os.path.join(OUT_DIR, f'ddprobe_{args.asset}_{tf}.json')
        json.dump(out, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if 'error' in out:
            print(f'!! {tf}: {out["error"]}', flush=True); continue
        w = out['worst_dd']
        print(f'== {tf}: n={out["n_trades"]} net={out["total_net_pip"]}pip | '
              f'worstDD={w["pip"]}pip over {w["n_trades_in_dd"]} trades '
              f'({w["from"]}→{w["to"]}, {w["span_days"]}d, {w["share_of_net_pct"]}% of net) | '
              f'worst5%%share={out["loss_concentration"]["worst5pct_share_of_total_loss"]}%',
              flush=True)
        # سه بهترین تفکیکِ رژیم بر حسبِ اختلافِ انتظار
        rows = []
        for k, v in out['regime_split'].items():
            if v is None: continue
            base, side = k.split('|')
            rows.append((base, side, v))
        by_base = {}
        for base, side, v in rows:
            by_base.setdefault(base, {})[side] = v
        deltas = []
        for base, d in by_base.items():
            if 'bull' in d and 'bear' in d:
                deltas.append((d['bull']['exp_pip'] - d['bear']['exp_pip'], base, d))
        deltas.sort(reverse=True)
        for delta, base, d in deltas[:4]:
            print(f'    {base:<10} bull: n={d["bull"]["n"]:>5} exp={d["bull"]["exp_pip"]:>8} '
                  f'dd={d["bull"]["maxdd_pip"]:>9} | bear: n={d["bear"]["n"]:>5} '
                  f'exp={d["bear"]["exp_pip"]:>8} dd={d["bear"]["maxdd_pip"]:>9} '
                  f'| Δexp={delta:.2f}', flush=True)
    print('[done]', flush=True)


if __name__ == '__main__':
    main()
