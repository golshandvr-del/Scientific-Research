# -*- coding: utf-8 -*-
"""
session_dow_wr_matrix.py — تحلیلِ WR هر لایهٔ XAUUSD M15 به تفکیکِ «روزِ هفته × سشنِ معاملاتیِ UTC»
================================================================================
پاسخ به User Note (نشستِ جاری):
  «WR هر لایه را نه در کل بازهٔ تاریخی، بلکه در هر پنجرهٔ زمانی و هر روز از هفته
   جداگانه بدست بیاور. برای هر لایه یک جدول: سطرها = روزهای هفته، ستون‌ها = سشن‌های
   فارکس بر حسب UTC (لندن / تداخل لندن-آسیا / نیویورک / تداخل لندن-نیویورک / ...).
   تداخل‌ها ستون جداگانه. در هر خانه WR آن لایه در آن بازهٔ زمانی نوشته می‌شود.»

روش:
  • هر لایه دقیقاً با سیگنالِ نهاییِ تثبیت‌شده‌اش بازتولید می‌شود (منبع: audit_all_layers).
  • هر معامله بر مبنای «زمانِ ورودِ واقعی» (entry_bar → ساعت UTC + روزِ هفته) به یک خانه
    نسبت داده می‌شود.
  • WR هر خانه بر مبنایِ تعریفِ رسمیِ پروژه = نسبتِ معاملاتی که net_usd>0 (پس از هزینهٔ
    واقعیِ ۳.۳pip). مشخصاتِ حساب = single source of truth (scalp_engine.ASSETS).
  • خروجی: جدولِ Markdown برای هر لایه + شمارشِ n در هر خانه (WR بدونِ n بی‌معناست).

تعریفِ سشن‌های فارکس (UTC) — استانداردِ صنعت:
  Sydney         : 21–06  (شبانه)
  Tokyo/Asian    : 00–08
  London         : 07–15
  New York       : 12–20
  تداخل‌ها (ستونِ مستقل):
    Tokyo∩London  : 07–08   (صبحِ اروپا)
    London∩NY     : 12–15   (مهم‌ترین نقدینگیِ روز)
  * هر کندل بر اساسِ ساعتِ UTCِ ورودش دقیقاً به یک ستونِ «سشنِ اصلی» و در صورتِ لزوم
    به یک ستونِ «تداخل» نسبت داده می‌شود. برای شفافیت، خانه‌های تداخل جدا گزارش می‌شوند
    و مجموعِ n در ستون‌های اصلی = کلِ معاملات (تداخل‌ها زیرمجموعه‌اند و علامت‌گذاری شده‌اند).
"""
import os, sys
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind

# ---- مشخصاتِ واقعیِ کاربر (single source of truth) ----
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

CAP, RISK = 10000.0, 1.0

# ============================ سشن‌های UTC ============================
# هر ساعتِ UTC به مجموعه‌ای از برچسب‌ها نگاشت می‌شود.
DOW_NAMES = ['Mon دوشنبه', 'Tue سه‌شنبه', 'Wed چهارشنبه', 'Thu پنجشنبه',
             'Fri جمعه', 'Sat شنبه', 'Sun یکشنبه']

# ستون‌ها به ترتیبِ نمایش (اصلی + تداخل‌ها)
SESSION_COLS = [
    ('Sydney(21-06)',      lambda h: h >= 21 or h <= 5),
    ('Tokyo(00-08)',       lambda h: 0 <= h <= 7),
    ('London(07-15)',      lambda h: 7 <= h <= 14),
    ('NewYork(12-20)',     lambda h: 12 <= h <= 19),
    ('OVL Tokyo∩Lon(07-08)', lambda h: 7 <= h <= 8),
    ('OVL Lon∩NY(12-15)',  lambda h: 12 <= h <= 14),
]


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def add_calendar(df):
    dt = df['dt']
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    days['tom_rel'] = days.apply(
        lambda r: int(r['from_end']) if r['from_end'] >= -2 else int(r['rank_in_month']), axis=1)
    df['tom_rel'] = df['date'].map(dict(zip(days['date'], days['tom_rel']))).astype(int)
    return df


def per_trade_net(tr, asset='XAUUSD'):
    """اجرای لایهٔ سرمایه و برگرداندنِ per-trade با net_usd و entry_bar."""
    if tr is None or len(tr) == 0:
        return pd.DataFrame(columns=['entry_bar', 'net_usd'])
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP,
                                        risk_pct=RISK, compounding=True)
    # pt به ترتیبِ همان tr است؛ entry_bar را از tr می‌گیریم
    if 'entry_bar' not in pt.columns:
        pt = pt.reset_index(drop=True)
        pt['entry_bar'] = tr['entry_bar'].values[:len(pt)]
    return pt[['entry_bar', 'net_usd']].copy()


def build_matrix(pt, df):
    """جدولِ (dow × session): n و WR. WR = share of net_usd>0."""
    if pt is None or len(pt) == 0:
        return None
    eb = pt['entry_bar'].values.astype(int)
    eb = np.clip(eb, 0, len(df) - 1)
    hours = df['hour'].values[eb]
    dows = df['dow'].values[eb]
    net = pt['net_usd'].values
    win = net > 0

    # فقط روزهایی که واقعاً معامله دارند
    present_dows = sorted(set(dows.tolist()))
    rows = []
    for d in present_dows:
        dm = dows == d
        row = {'dow': d, 'dow_name': DOW_NAMES[d]}
        for col_name, fn in SESSION_COLS:
            in_col = np.array([fn(int(h)) for h in hours]) & dm
            n = int(in_col.sum())
            w = int(win[in_col].sum())
            row[col_name] = (n, w, (w / n * 100.0 if n else None))
        # مجموعِ روز (بدونِ تداخل‌ها؛ بر مبنای همهٔ معاملاتِ آن روز)
        n_all = int(dm.sum()); w_all = int(win[dm].sum())
        row['ALL'] = (n_all, w_all, (w_all / n_all * 100.0 if n_all else None))
        rows.append(row)
    return rows


def matrix_to_md(rows, layer_name, total_n, total_wr, total_net):
    if rows is None:
        return f"### {layer_name}\n\n_صفر معامله در بازهٔ داده._\n\n"
    cols = [c for c, _ in SESSION_COLS]
    md = f"### {layer_name}\n\n"
    md += f"- **کل معاملات:** {total_n} | **WR کل:** {total_wr:.1f}% | **net کل:** {total_net:+,.0f}$\n\n"
    md += "قالبِ هر خانه: `WR% (wins/n)` — خانهٔ خالی = صفر معامله در آن ترکیب.\n\n"
    header = "| روز \\ سشن (UTC) | " + " | ".join(cols) + " | **کلِ روز** |"
    sep = "|" + "---|" * (len(cols) + 2)
    md += header + "\n" + sep + "\n"
    for r in rows:
        cells = []
        for c in cols:
            n, w, wr = r[c]
            cells.append(f"{wr:.0f}% ({w}/{n})" if n else "—")
        na, wa, wra = r['ALL']
        all_cell = f"**{wra:.0f}% ({wa}/{na})**" if na else "—"
        md += f"| {r['dow_name']} | " + " | ".join(cells) + f" | {all_cell} |\n"
    md += "\n"
    return md


# ============================================================================
# تعریفِ لایه‌ها (سیگنالِ نهاییِ تثبیت‌شده — عیناً از audit_all_layers)
# هر تابع (long_sig, short_sig, sl, tp, mh, extra) را برمی‌گرداند.
# ============================================================================
def layer_signals(df):
    """برمی‌گرداند: dict[layer_name] = (long_sig, short_sig, sl, tp, mh, be, trail)"""
    n = len(df)
    zeros = np.zeros(n, bool)
    c = df['close']
    hour = df['hour'].values
    dow = df['dow'].values
    dom = df['dom'].values
    from_end = df['from_end'].values
    tom_rel = df['tom_rel'].values
    out = {}

    # S139 Overnight: hour∈{22,23}  SL150/TP500/mh96
    ls = np.isin(hour, [22, 23])
    out['S139 Overnight (Long)'] = (ls, zeros, 150, 500, 96, None, None)

    # S140⁺⁺ Monday: dow=0 & hour∈{18,19,20}  SL100/TP300/mh96  (نسخهٔ رکورد: بدونِ ۲۱)
    ls = (dow == 0) & np.isin(hour, [18, 19, 20])
    out['S140++ Monday (Long)'] = (ls, zeros, 100, 300, 96, None, None)

    # S141 Turn-of-Month: tom_rel=1 & hour∈{7..12}  SL100/TP700/mh96
    ls = (tom_rel == 1) & np.isin(hour, [7, 8, 9, 10, 11, 12])
    out['S141 Turn-of-Month (Long)'] = (ls, zeros, 100, 700, 96, None, None)

    # S142⁺ Mid-Month: dom∈{10,13,20} & hour∈{1..12}  SL100/TP500/mh96
    ls = np.isin(dom, [10, 13, 20]) & np.isin(hour, list(range(1, 13)))
    out['S142+ Mid-Month (Long)'] = (ls, zeros, 100, 500, 96, None, None)

    # S144 End-of-Month Pre-End: from_end∈{-6,-7,-8} & hour∈{19..23}  SL150/TP300/mh96
    ls = np.isin(from_end, [-6, -7, -8]) & np.isin(hour, [19, 20, 21, 22, 23])
    out['S144 End-of-Month Pre-End (Long)'] = (ls, zeros, 150, 300, 96, None, None)

    # SHORT-MA-Confluence: price crosses mid[EMA50,EMA100,SMA200] down; SL40/TP200/mh12 BE8 trail8
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    price = c.values
    prev_above = np.r_[False, price[:-1] > mid[:-1]]
    sh = prev_above & (price < mid)
    out['SHORT-MA-Confluence (Short)'] = (zeros, sh, 40, 200, 12, 8, 8)

    # S168 Brooks High-2: long, ema20/50, SL300/TP450, mh32 (منبع: نتیجهٔ نهایی)
    from s168_brooks_high2_low2 import count_high2_low2
    long_evt, _ = count_high2_low2(df, 20, 50)
    ls = pd.Series(long_evt).shift(1).fillna(False).to_numpy()
    out['S168 Brooks High-2 (Long)'] = (ls, zeros, 300, 450, 32, None, None)

    # S171 Brooks Signs-of-Strength: long, w32/thr2, SL300/TP450, mh96 (منبع: نتیجهٔ نهایی)
    from s171_brooks_signs_of_strength_filter import signs_of_strength_bull
    sos = signs_of_strength_bull(df, ema_period=20, win=32)
    strong = sos['score'].to_numpy() >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    ls = pd.Series(edge).shift(1).fillna(False).to_numpy()
    out['S171 Signs-of-Strength (Long)'] = (ls, zeros, 300, 450, 96, None, None)

    return out


def run_layer_engine(df, name, spec):
    ls, sh, sl, tp, mh, be, trail = spec
    tr = se.simulate_trades(df, ls, sh, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False,
                            be_trigger_pip=be, trail_pip=trail)
    pt = per_trade_net(tr, 'XAUUSD')
    return pt


def run_squeeze_pertrade(df):
    """S138 Squeeze نهایی: brk≥0.30 + rsi14≤75، paper_broker hidden(300,90).
    خروجی: per-trade با entry_bar و net_usd (حجمِ ثابت 0.01)."""
    from s132_squeeze_breakout_m15 import build_entries_squeeze, MAX_HOLD_M15
    from s94_scalp_hidden_target import make_hidden_exit
    import s91_scalp_signal_exit as s91
    s91.SPREAD_PIP = 3.3; s91.SLIP_PIP = 0.0; s91.COMM_PER_LOT = 0.0
    s91.COST_PIP = s91.SPREAD_PIP + 2.0 * s91.SLIP_PIP
    from s91_scalp_signal_exit import paper_broker, atr as s91atr

    TRIG = dict(sqz_pct=0.25, breakout_lookback=6)
    entries = build_entries_squeeze(df, **TRIG)
    cvals = df['close'].values.astype(np.float64); hvals = df['high'].values.astype(np.float64)
    a14 = s91atr(df, 14); brk = TRIG['breakout_lookback']

    def brkstr(i):
        ph = hvals[i - brk:i].max() if i >= brk else np.nan
        a = a14[i] if (np.isfinite(a14[i]) and a14[i] > 0) else np.nan
        return float((cvals[i] - ph) / a) if (np.isfinite(ph) and np.isfinite(a)) else 0.0

    ent = [(i, s) for (i, s) in entries if brkstr(i) >= 0.30]
    r14 = ind.rsi(df['close'], 14).values
    ent = [(i, s) for (i, s) in ent if np.isfinite(r14[i]) and r14[i] <= 75.0]
    exit_fn = make_hidden_exit(300.0, 90.0, use_trend_break=False)
    tr = paper_broker(df, ent, exit_fn, catastrophic_sl_pip=400.0, max_hold=MAX_HOLD_M15)
    if tr is None or len(tr) == 0:
        return pd.DataFrame(columns=['entry_bar', 'net_usd'])
    # paper_broker: ستونِ ورود ممکن است entry_bar یا entry_idx باشد
    col = 'entry_bar' if 'entry_bar' in tr.columns else ('entry_idx' if 'entry_idx' in tr.columns else None)
    if col is None:
        return pd.DataFrame(columns=['entry_bar', 'net_usd'])
    out = pd.DataFrame({'entry_bar': tr[col].values.astype(int),
                        'net_usd': tr['net_usd'].values})
    return out


def main(layer_filter=None):
    df = assign_from_end(add_calendar(load('XAUUSD_M15')))
    print(f"XAUUSD M15: {df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()}  ({len(df):,} کندل)", flush=True)

    specs = layer_signals(df)
    md_all = []
    md_all.append("# جدولِ WR به تفکیکِ روزِ هفته × سشنِ معاملاتیِ UTC — XAUUSD M15\n\n")
    md_all.append(f"> دارایی: **XAUUSD M15** | بازه: {df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()} "
                  f"| هزینه: ۳.۳pip اسپرد، comm=0 (مشخصاتِ واقعیِ حساب)\n\n")
    md_all.append("> WR هر خانه = نسبتِ معاملاتی که `net_usd>0` (پس از هزینه). "
                  "کفِ هدفِ پروژه (User Note جدید): **WR≥۶۰٪**.\n\n")
    md_all.append("**سشن‌های UTC:** Sydney 21–06 | Tokyo 00–08 | London 07–15 | NewYork 12–20 | "
                  "تداخلِ Tokyo∩London 07–08 | تداخلِ London∩NY 12–15.\n\n---\n\n")

    results = {}
    for name, spec in specs.items():
        if layer_filter and name not in layer_filter:
            continue
        print(f"\n{'='*70}\nلایه: {name}", flush=True)
        pt = run_layer_engine(df, name, spec)
        n = len(pt)
        if n == 0:
            print("  صفر معامله.", flush=True)
            md_all.append(matrix_to_md(None, name, 0, 0, 0))
            results[name] = None
            continue
        net = pt['net_usd'].values
        total_net = float(net.sum())
        total_wr = float((net > 0).sum() / n * 100.0)
        rows = build_matrix(pt, df)
        print(f"  کل: n={n}  WR={total_wr:.1f}%  net={total_net:+,.0f}$", flush=True)
        # چاپِ خلاصهٔ خانه‌های واجدِ WR≥60 با n≥15
        hits = []
        for r in rows:
            for cn, _ in SESSION_COLS:
                nn, ww, wr = r[cn]
                if nn >= 15 and wr is not None and wr >= 60.0:
                    hits.append(f"{r['dow_name'].split()[0]}×{cn}: WR{wr:.0f}% (n={nn})")
        if hits:
            print("  🎯 خانه‌های WR≥60 (n≥15):", flush=True)
            for hh in hits:
                print("     " + hh, flush=True)
        else:
            print("  — هیچ خانه‌ای WR≥60 با n≥15 ندارد.", flush=True)
        md_all.append(matrix_to_md(rows, name, n, total_wr, total_net))
        results[name] = dict(n=n, wr=total_wr, net=total_net, rows=rows, hits=hits)

    # --- Squeeze (paper_broker جداگانه) ---
    sq_name = 'S132/S136/S138 Squeeze→Breakout (Long)'
    if not layer_filter or sq_name in layer_filter:
        print(f"\n{'='*70}\nلایه: {sq_name}", flush=True)
        try:
            pt = run_squeeze_pertrade(df)
            n = len(pt)
            if n == 0:
                print("  صفر معامله.", flush=True)
                md_all.append(matrix_to_md(None, sq_name, 0, 0, 0))
            else:
                net = pt['net_usd'].values
                total_net = float(net.sum())
                total_wr = float((net > 0).sum() / n * 100.0)
                rows = build_matrix(pt, df)
                print(f"  کل: n={n}  WR={total_wr:.1f}%  net={total_net:+,.0f}$", flush=True)
                hits = []
                for r in rows:
                    for cn, _ in SESSION_COLS:
                        nn, ww, wr = r[cn]
                        if nn >= 15 and wr is not None and wr >= 60.0:
                            hits.append(f"{r['dow_name'].split()[0]}×{cn}: WR{wr:.0f}% (n={nn})")
                if hits:
                    print("  🎯 خانه‌های WR≥60 (n≥15):", flush=True)
                    for hh in hits:
                        print("     " + hh, flush=True)
                else:
                    print("  — هیچ خانه‌ای WR≥60 با n≥15 ندارد.", flush=True)
                md_all.append(matrix_to_md(rows, sq_name, n, total_wr, total_net))
                results[sq_name] = dict(n=n, wr=total_wr, net=total_net, rows=rows, hits=hits)
        except Exception as ex:
            print(f"  ⚠️ خطا در Squeeze: {ex}", flush=True)
            md_all.append(f"### {sq_name}\n\n_خطا در اجرا: {ex}_\n\n")

    return md_all, results


if __name__ == '__main__':
    md_all, results = main()
    out_path = os.path.join(ROOT, 'results',
                            'SESSION_DOW_WR_MATRIX_XAU_M15.md')
    with open(out_path, 'w') as f:
        f.write("".join(md_all))
    print(f"\n✅ ذخیره شد: {out_path}")
