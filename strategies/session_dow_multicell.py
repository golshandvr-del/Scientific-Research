# -*- coding: utf-8 -*-
"""
session_dow_multicell.py — گامِ بعدِ تحلیلِ روز×سشن: انتخابِ «زیرمجموعهٔ چند-سلولی»
================================================================================
یافتهٔ گامِ قبل (session_dow_wr_matrix): هیچ لایه‌ای با یک تک‌سلولِ روز×سشن به WR≥۶۰٪
(با n≥۳۰) نمی‌رسد؛ نزدیک‌ترین‌ها ۵۵–۵۹٪ بودند.

این اسکریپت گامِ منطقیِ بعد را برمی‌دارد (راهِ اول پروژه: «بهبود»):
  برای هر لایه، سلول‌های (روز×سشنِ اصلی، بدونِ دوباره‌شماریِ تداخل) را بر اساسِ WR نزولی
  مرتب می‌کند و به‌صورتِ حریصانه (greedy) از بالاترین WR شروع به جمع‌کردنِ سلول‌ها می‌کند
  تا جایی که WR ترکیبی همچنان ≥۶۰٪ بماند و n کل ≥ N_FLOOR شود. سپس:
    • net دلاریِ همان زیرمجموعه (فقط معاملاتِ آن سلول‌ها) را گزارش می‌کند،
    • «سهمِ باقیمانده» (سلول‌های حذف‌شده) را هم نشان می‌دهد،
    • تصمیم: آیا این «فیلترِ روز×سشن» لایه را به کفِ جدیدِ ۶۰٪ می‌رساند و net مثبت می‌ماند؟

⚠️ توجهِ ضدِ overfit: انتخابِ حریصانهٔ سلول‌ها روی کلِ داده ذاتاً in-sample است. این گام
   فقط «کاندیدِ بهبود» تولید می‌کند؛ اعتبارِ نهایی موکول به آزمونِ walk-forward در گامِ
   بعد است (اگر کاندیدی امیدوارکننده پیدا شود).

منبعِ سیگنال‌ها: عیناً session_dow_wr_matrix.layer_signals + run_squeeze_pertrade.
"""
import os, sys
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from session_dow_wr_matrix import (
    load, add_calendar, assign_from_end, layer_signals,
    run_layer_engine, run_squeeze_pertrade, per_trade_net,
    SESSION_COLS, DOW_NAMES, se)

# فقط سشن‌های «اصلی» برای پارتیشنِ بدونِ دوباره‌شماری (تداخل‌ها زیرمجموعه‌اند)
MAIN_SESSIONS = [
    ('Sydney(21-06)',  lambda h: h >= 21 or h <= 5),
    ('Tokyo(00-08)',   lambda h: 0 <= h <= 7),
    ('London(07-15)',  lambda h: 7 <= h <= 14),
    ('NewYork(12-20)', lambda h: 12 <= h <= 19),
]
# نگاشتِ منحصربه‌فرد: هر ساعت به «اولین سشنِ اصلیِ منطبق» (پارتیشنِ قطعی برای net)
def hour_to_partition(h):
    # اولویت: London > NewYork > Tokyo > Sydney (برای ساعاتِ هم‌پوشان، بازارِ فعال‌تر)
    if 7 <= h <= 14: return 'London(07-15)'
    if 15 <= h <= 20: return 'NewYork(12-20)'   # ۱۵–۲۰ نیویورکِ خالص
    if 12 <= h <= 14: return 'London(07-15)'    # (پوشش داده شد بالا)
    if 0 <= h <= 6: return 'Tokyo(00-08)'
    return 'Sydney(21-06)'  # ۲۱–۲۳ و بقیه


N_FLOOR = 60          # کفِ n کلِ زیرمجموعه (برای اعتبارِ آماری)
CELL_N_MIN = 15       # کفِ n هر سلول برای واردشدن به انتخاب
WR_TARGET = 60.0


def build_cell_table(pt, df):
    """هر معامله را به سلولِ (dow, partition-session) نسبت می‌دهد و net/win را جمع می‌کند."""
    if pt is None or len(pt) == 0:
        return {}
    eb = np.clip(pt['entry_bar'].values.astype(int), 0, len(df) - 1)
    hours = df['hour'].values[eb]
    dows = df['dow'].values[eb]
    net = pt['net_usd'].values
    cells = {}
    for i in range(len(net)):
        key = (int(dows[i]), hour_to_partition(int(hours[i])))
        c = cells.setdefault(key, dict(n=0, wins=0, net=0.0))
        c['n'] += 1
        c['wins'] += 1 if net[i] > 0 else 0
        c['net'] += float(net[i])
    return cells


def greedy_select(cells):
    """حریصانه: سلول‌ها را بر WR نزولی مرتب کن؛ از بالا جمع کن تا WR کل ≥۶۰ و n≥N_FLOOR."""
    items = [(k, v) for k, v in cells.items() if v['n'] >= CELL_N_MIN]
    items.sort(key=lambda kv: (kv[1]['wins'] / kv[1]['n']), reverse=True)
    sel = []
    tn = tw = 0
    tnet = 0.0
    for k, v in items:
        # امتحانِ افزودن این سلول
        nn = tn + v['n']; ww = tw + v['wins']
        wr = ww / nn * 100.0
        if wr >= WR_TARGET or tn == 0:  # سلولِ اول را همیشه بگیر (بالاترین WR)
            sel.append((k, v))
            tn, tw, tnet = nn, ww, tnet + v['net']
        else:
            # اگر افزودن WR را زیرِ ۶۰ می‌برد، رد کن (چون بقیه WRِ کمتری دارند، توقف)
            break
    twr = (tw / tn * 100.0) if tn else 0.0
    return sel, tn, tw, twr, tnet


def main():
    df = assign_from_end(add_calendar(load('XAUUSD_M15')))
    specs = layer_signals(df)

    md = ["# انتخابِ زیرمجموعهٔ چند-سلولی روز×سشن برای رساندنِ WR به ≥۶۰٪ — XAUUSD M15\n\n"]
    md.append(f"> بازه: {df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()} | "
              f"روش: greedy روی سلول‌های (روز × سشنِ اصلیِ پارتیشن‌شده) با WR نزولی.\n")
    md.append(f"> شرط: WR ترکیبی ≥{WR_TARGET:.0f}% و n کل ≥{N_FLOOR} و n هر سلول ≥{CELL_N_MIN}.\n\n")
    md.append("⚠️ **این گام in-sample است** (انتخابِ سلول روی کلِ داده). کاندیدِ امیدوارکننده "
              "باید در گامِ بعد walk-forward شود.\n\n")
    md.append("| لایه | #سلول‌های منتخب | ترکیب | WR ترکیبی | n | net زیرمجموعه | تصمیم |\n")
    md.append("|---|---|---|---|---|---|---|\n")

    # لایه‌های engine
    all_pt = {}
    for name, spec in specs.items():
        all_pt[name] = run_layer_engine(df, name, spec)
    all_pt['S132/S136/S138 Squeeze→Breakout (Long)'] = run_squeeze_pertrade(df)

    findings = {}
    for name, pt in all_pt.items():
        cells = build_cell_table(pt, df)
        if not cells:
            md.append(f"| {name} | 0 | — | — | — | — | صفر معامله |\n")
            continue
        sel, tn, tw, twr, tnet = greedy_select(cells)
        combo = "، ".join(f"{DOW_NAMES[d].split()[0]}×{s.split('(')[0]}" for (d, s), _ in sel)
        if twr >= WR_TARGET and tn >= N_FLOOR and tnet > 0:
            decision = "✅ کاندیدِ بهبود (به WF برود)"
        elif twr >= WR_TARGET and tnet > 0:
            decision = f"🟡 WR پاس ولی n={tn}<{N_FLOOR}"
        elif twr >= WR_TARGET:
            decision = "🟡 WR پاس ولی net≤0"
        else:
            decision = f"❌ حتی بهترین ترکیب WR={twr:.0f}%<۶۰"
        md.append(f"| {name} | {len(sel)} | {combo} | {twr:.1f}% | {tn} | {tnet:+,.0f}$ | {decision} |\n")
        findings[name] = dict(sel=sel, n=tn, wr=twr, net=tnet, decision=decision)
        print(f"{name}: WR={twr:.1f}% n={tn} net={tnet:+,.0f}  [{decision}]", flush=True)

    out = os.path.join(ROOT, 'results', 'SESSION_DOW_MULTICELL_XAU_M15.md')
    with open(out, 'w') as f:
        f.write("".join(md))
    print(f"\n✅ ذخیره شد: {out}")
    return findings


if __name__ == '__main__':
    main()
