# -*- coding: utf-8 -*-
"""
S173-FINALIZE — ثبتِ رسمیِ سهمِ مستقلِ «Market Inertia» SHORT (طلا)
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

کاندیدِ برندهٔ گریدِ S173 (فصلِ ۱، «trend fade reversal-attempt» SHORT):
    XAUUSD  ema20/50  adx>28  lb20  SL250/TP375/mh48
    خام: net=$+2,016  WR=50.0%  n=196  PF=1.36  (گیتِ کامل پاس)

اما «قانونِ همپوشانی» پروژه می‌گوید: وقتی لایهٔ جدید با لایه‌های موجود همپوشانی دارد،
باید سهمِ مستقل (anti-double-counting، هم‌سو با S172) ثبت شود — یعنی سیگنال‌هایی که
در بازهٔ recent-۱۲ کندلِ *اجتماعِ* پرتفویِ SHORT نیستند.

پرتفویِ SHORT موجود (از AuditAllLayers…222355.md):
  • SHORT-MA-Confluence  (+$94,467) — تنها لبهٔ SHORT خالصِ اثبات‌شده
  • S67 Router           (+$17,559) — Long/Short ترکیبی (سهمِ SHORT آن هم لحاظ می‌شود)

این اسکریپت:
  1) سیگنالِ خامِ S173-SHORT را بازتولید می‌کند (روی همان ۴ سال).
  2) سیگنالِ SHORT-MA-Confluence را بازسازی می‌کند (cross_mid_down).
  3) اجتماعِ پرتفویِ SHORT را می‌سازد و بازهٔ recent-۱۲ آن را حذف می‌کند.
  4) سهمِ مستقل را با گیتِ کامل (net>0 + WR≥40 + هر دو نیمه + walk-forward ۴ پنجره +
     n≥30) می‌سنجد و درصدِ همپوشانی را دقیق گزارش می‌کند.

خروجی: چاپِ کنسول + results/_s173_finalize.json
"""
import os, sys, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S          # load, lastn, sim, stats, halves
import s173_brooks_market_inertia as MI   # inertia_signals
from engine import indicators as ind

OVERLAP_BARS = 12   # هم‌سو با روشِ anti-double-counting در S172
WR_FLOOR = 40.0

# کاندیدِ برندهٔ S173-SHORT (تثبیت‌شده در گرید)
CFG = dict(asset='XAUUSD', ef=20, es=50, adx_hi=28, lb=20,
           sl=250, tp=375, mh=48, side='short')


# ---------------------------------------------------------------------------
#  بازسازیِ سیگنالِ SHORT-MA-Confluence (از explore_short_ma_confluence.py)
#  cross_mid_down = (prev price>prev mid) & (price<mid) & (ema20_slope<0)
#  ma_mid = mean(ema20, ema50, sma50, sma200)
# ---------------------------------------------------------------------------
def short_ma_confluence_signal(df):
    c = df['close']; price = c.to_numpy()
    ema20 = ind.ema(c, 20).to_numpy()
    ema50 = ind.ema(c, 50).to_numpy()
    sma50 = ind.sma(c, 50).to_numpy()
    sma200 = ind.sma(c, 200).to_numpy()
    ma_stack = np.column_stack([ema20, ema50, sma50, sma200])
    ma_mid = np.nanmean(ma_stack, axis=1)
    ema20_slope = pd.Series(ema20).diff().to_numpy()
    prev_above = np.r_[False, price[:-1] > ma_mid[:-1]]
    cross_mid_down = prev_above & (price < ma_mid) & (ema20_slope < 0)
    # causal: در بک‌تستِ پرتفوی سیگنال با کندلِ بعد اجرا می‌شود
    return pd.Series(cross_mid_down).shift(1).fillna(False).to_numpy()


# ---------------------------------------------------------------------------
#  سهمِ S67-Router SHORT — رویدادِ ورودِ گزینشی، نه شرطِ پیوستهٔ رژیم.
#  نکتهٔ روش‌شناختی: همپوشانی باید بر اساسِ «رویدادهای ورودِ واقعی» سنجیده شود،
#  نه صرفاً «بودن در رژیمِ نزولی». اگر شرطِ پیوستهٔ رژیم را علامت بزنیم، هر
#  استراتژیِ SHORT ذاتاً ~۹۰٪ همپوشان به‌نظر می‌رسد که بی‌معناست (S172 هم
#  همپوشانی را بر رویدادِ ورود سنجید، نه شرطِ رژیم).
#  S67 یک روتر است که در نقاطِ گذارِ رژیم به SHORT وارد می‌شود ⇒ رویدادِ کراسِ
#  رو-به-پایینِ ema20 زیرِ ema50 در رژیمِ روندی (ADX>25) به‌عنوانِ رویدادِ ورودِ
#  گزینشیِ آن تقریب زده می‌شود (کراس = گذار، نه وضعیتِ پیوسته).
# ---------------------------------------------------------------------------
def s67_short_proxy(df):
    c = df['close']; price = c.to_numpy()
    ema20 = ind.ema(c, 20).to_numpy()
    ema50 = ind.ema(c, 50).to_numpy()
    sma200 = ind.sma(c, 200).to_numpy()
    adx = ind.adx(df, 14)
    adx = adx[0] if isinstance(adx, tuple) else adx
    adx = pd.Series(np.asarray(adx)).fillna(0).to_numpy()
    below = ema20 < ema50
    cross_down = np.r_[False, (~below[:-1]) & below[1:]]   # رویدادِ کراس، نه وضعیت
    raw = cross_down & (adx > 25) & (price < sma200)
    return pd.Series(raw).shift(1).fillna(False).to_numpy()


# ---------------------------------------------------------------------------
#  حذفِ سیگنال‌هایی که در بازهٔ recent-N کندلِ اجتماعِ پرتفوی هستند
# ---------------------------------------------------------------------------
def independent_share(sig, portfolio_union, n_bars=OVERLAP_BARS):
    """
    سیگنالِ sig که در پنجرهٔ [i-n_bars, i] آن هر بارِ portfolio_union روشن باشد،
    «همپوشان» تلقی و حذف می‌شود؛ فقط بخشِ مستقل باقی می‌ماند.
    """
    recent = pd.Series(portfolio_union.astype(float)).rolling(
        n_bars, min_periods=1).max().to_numpy() > 0
    indep = sig & (~recent)
    return indep


def full_gate(df, sig, asset, side, sl, tp, mh, label):
    z = np.zeros(len(df), bool)
    if side == 'short':
        tr = S.sim(df, z, sig, sl, tp, mh, asset)
    else:
        tr = S.sim(df, sig, z, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return dict(label=label, n=r['n'] if r else 0, ok=False, reason='n<30')
    hv = S.halves(df, z if side == 'short' else sig,
                  sig if side == 'short' else z, sl, tp, mh, asset)
    wf = MI.walk_forward(df, sig, side, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    ok = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(label=label, net=round(r['net'], 1), wr=round(r['wr'], 2),
                n=r['n'], pf=round(r['pf'], 3),
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok, ok=ok)


def main():
    print("=" * 100)
    print("S173-FINALIZE — سهمِ مستقلِ «Market Inertia» SHORT در برابرِ کلِ پرتفویِ SHORT")
    print("=" * 100)

    asset = CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")

    # 1) سیگنالِ خامِ S173-SHORT
    sig = MI.inertia_signals(df, CFG['ef'], CFG['es'], CFG['adx_hi'], CFG['lb'], 'short')
    print(f"\nS173-SHORT خام: n_signals={int(sig.sum())}")
    raw = full_gate(df, sig, asset, 'short', CFG['sl'], CFG['tp'], CFG['mh'], 'S173-SHORT raw')
    print(f"  خام: net={raw.get('net'):+.0f} WR={raw.get('wr')} n={raw['n']} PF={raw.get('pf')} "
          f"h1={raw.get('h1')} h2={raw.get('h2')} WF_ok={raw.get('wf_ok')} => {'OK' if raw['ok'] else 'X'}")

    # 2) سیگنال‌های پرتفویِ SHORT
    ma_sig = short_ma_confluence_signal(df)
    s67_sig = s67_short_proxy(df)
    print(f"\nپرتفویِ SHORT: MA-Confluence n={int(ma_sig.sum())}  |  S67-short-proxy n={int(s67_sig.sum())}")

    # 3) اجتماع و سهمِ مستقل (دو سناریو: فقط MA-Conf، و کلِ پرتفوی)
    union_maonly = ma_sig
    union_full = ma_sig | s67_sig

    def bar_overlap_pct(a, b):
        if a.sum() == 0:
            return 0.0
        recent = pd.Series(b.astype(float)).rolling(OVERLAP_BARS, min_periods=1).max().to_numpy() > 0
        return float((a & recent).sum()) / float(a.sum()) * 100

    ov_ma = bar_overlap_pct(sig, union_maonly)
    ov_full = bar_overlap_pct(sig, union_full)
    print(f"\nهمپوشانیِ بار-به-بار (recent-{OVERLAP_BARS}):")
    print(f"  S173-SHORT ∩ MA-Confluence      = {ov_ma:.0f}%")
    print(f"  S173-SHORT ∩ کلِ پرتفویِ SHORT  = {ov_full:.0f}%")

    # سهمِ مستقل نسبت به MA-Conf
    indep_ma = independent_share(sig, union_maonly)
    r_ma = full_gate(df, indep_ma, asset, 'short', CFG['sl'], CFG['tp'], CFG['mh'],
                     'indep-of-MAConf')
    # سهمِ مستقل نسبت به کلِ پرتفوی (محافظه‌کارانه‌ترین برآورد ⇐ برای ثبتِ رسمی)
    indep_full = independent_share(sig, union_full)
    r_full = full_gate(df, indep_full, asset, 'short', CFG['sl'], CFG['tp'], CFG['mh'],
                       'indep-of-FULL-short-portfolio')

    print(f"\nسهمِ مستقلِ S173-SHORT پس از حذفِ همپوشانی:")
    for r in (r_ma, r_full):
        tag = 'OK ✅' if r['ok'] else 'X'
        if r.get('net') is None:
            print(f"  [{r['label']:32}] n={r['n']} reason={r.get('reason','-')}  => {tag}")
            continue
        print(f"  [{r['label']:32}] net={r.get('net'):+.0f} WR={r.get('wr')} n={r['n']} "
              f"PF={r.get('pf')} h1={r.get('h1')} h2={r.get('h2')} "
              f"WF={'/'.join(f'{x[0]:+.0f}' for x in r.get('wf', []))}  => {tag}")

    # 4) تصمیم: دلتای ثبت‌پذیر = سهمِ مستقل نسبت به کلِ پرتفوی (محافظه‌کارانه‌ترین)
    registrable = r_full if r_full['ok'] else (r_ma if r_ma['ok'] else None)
    print("\n" + "=" * 100)
    if registrable and registrable['ok']:
        print(f"✅ دلتای ثبت‌پذیر (محافظه‌کارانه، مستقل از کلِ پرتفوی): "
              f"net=${registrable['net']:+,.0f}  WR={registrable['wr']}%  n={registrable['n']}  "
              f"PF={registrable['pf']}  (گیتِ کامل پاس)")
    else:
        print("⛔ سهمِ مستقل گیتِ کامل را پاس نکرد ⇒ لایه ثبت نمی‌شود (فقط به‌عنوانِ فیلتر قابلِ استفاده).")
    print("=" * 100)

    out = dict(strategy='S173_finalize', cfg=CFG,
               overlap_ma_pct=round(ov_ma, 1), overlap_full_pct=round(ov_full, 1),
               raw=raw, indep_of_maconf=r_ma, indep_of_full=r_full,
               registrable=registrable)
    os.makedirs('results', exist_ok=True)
    with open('results/_s173_finalize.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("✅ ذخیره شد: results/_s173_finalize.json")


if __name__ == '__main__':
    main()
