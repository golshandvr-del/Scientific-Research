"""
S131 — «تحلیلِ سهمِ هر لایه در هفته‌های منفی + راهکارِ درستِ کاهشِ هفته‌های منفی»
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR).**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD. WR فقط عددِ گزارشی است.

------------------------------------------------------------------------------
انگیزه (ادامهٔ User Note):
  در s130 دیدیم «بریکرِ هفتگی» درصدِ هفته‌های منفی را کم نکرد (چون بیشترِ هفته‌های
  منفی کم‌عمق‌اند و بریکر معاملاتِ جبران‌کننده را هم قربانی می‌کند). پس باید علتِ
  واقعی را بیابیم: **کدام لایه بیشترین سهم را در هفته‌های منفی دارد؟** و بعد یک
  راهکارِ درست (حذف/کاهش‌وزنِ لایهٔ مقصر) بسازیم که هم هفته‌های منفی را کم کند و
  هم — طبقِ قانونِ #۱ — سودِ خالص را حفظ یا زیاد کند.

روش: همان ۵ لایهٔ رکوردِ فعلی را با per-trade timestamp بازتولید می‌کنیم (بازاستفاده
از s130)، هر لایه را جدا به سطلِ هفتگی می‌بریم، و برای «هفته‌هایی که پرتفویِ کل منفی
بوده» می‌سنجیم هر لایه چقدر سود/زیان داشته (سهمِ علّی). سپس چند «پرتفویِ کاندید»
(حذفِ یک لایه یا کاهش‌وزنِ آن) را می‌سازیم و سودِ خالص + درصدِ هفته‌های منفی را مقایسه
می‌کنیم.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# بازاستفاده از لایه‌های s130 (منبعِ واحدِ حقیقت)
from strategies import s130_portfolio_periodic_equity as S130
from engine.periodic_pnl import build_pnl_events, periodic_summary, worst_streak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')
YEARS_BACK = S130.YEARS_BACK


def weekly_series(events):
    ev = events.copy().set_index('dt')
    g = ev['pnl'].resample('W-MON').sum()
    cnt = ev['pnl'].resample('W-MON').count()
    return g[cnt > 0]


def main():
    print("=" * 92, flush=True)
    print("  S131 — تحلیلِ سهمِ لایه‌ها در هفته‌های منفی + راهکارِ درستِ کاهشِ آن‌ها", flush=True)
    print("  قانونِ #۱: فقط سودِ خالص (XAUUSD + EURUSD). WR گزارشی است.", flush=True)
    print("=" * 92, flush=True)

    layers = []
    for fn in (S130.layer_s67, S130.layer_scalpv2, S130.layer_s81,
               S130.layer_short, S130.layer_s73):
        L = fn()
        layers.append(L)
        s = L['stats']
        print(f"  ✓ {L['name']}: net={s['net_profit']:+,.0f}$  n={s['n_trades']}", flush=True)

    max_dt = max(L['pt']['dt'].max() for L in layers if len(L['pt']))
    cutoff = max_dt - pd.DateOffset(years=YEARS_BACK)

    # سریِ هفتگیِ هر لایه (فقط ۴ سالِ اخیر)، روی ایندکسِ مشترک
    layer_ev = {}
    for L in layers:
        pt = L['pt']
        pt = pt[pt['dt'] >= cutoff].reset_index(drop=True)
        layer_ev[L['name']] = build_pnl_events(pt, 'net_usd', 'dt')

    port = pd.concat(layer_ev.values(), ignore_index=True).sort_values('dt').reset_index(drop=True)
    port_w = weekly_series(port)
    all_weeks = port_w.index

    lay_w = {nm: weekly_series(ev).reindex(all_weeks).fillna(0.0)
             for nm, ev in layer_ev.items()}

    # ---- سهمِ هر لایه در «هفته‌های منفیِ پرتفوی» ----
    neg_mask = port_w < 0
    neg_weeks = port_w[neg_mask]
    print("\n" + "#" * 92, flush=True)
    print(f"#  سهمِ هر لایه در {int(neg_mask.sum())} هفتهٔ منفیِ پرتفوی (از {len(port_w)} هفته)", flush=True)
    print("#" * 92, flush=True)
    print(f"\n  {'لایه':<32}{'جمعِ سهم در هفته‌های منفی':>26}{'میانگین':>12}", flush=True)
    print("  " + "-" * 68, flush=True)
    contrib = {}
    for nm, w in lay_w.items():
        s = float(w[neg_mask].sum())
        contrib[nm] = s
        print(f"  {nm:<32}{s:>26,.0f}{w[neg_mask].mean():>12,.1f}", flush=True)
    worst_layer = min(contrib, key=contrib.get)
    print(f"\n  ⇒ مقصرِ اصلیِ هفته‌های منفی: «{worst_layer}» "
          f"(جمعِ سهمِ منفی = {contrib[worst_layer]:+,.0f}$)", flush=True)

    # ---- ساختِ پرتفوی‌های کاندید (حذفِ یک لایه) و مقایسه ----
    print("\n" + "#" * 92, flush=True)
    print("#  راهکار: حذف/کاهش‌وزنِ لایه‌ها — مقایسهٔ سودِ خالص و %هفتهٔ منفی", flush=True)
    print("#" * 92, flush=True)
    base_net = float(port_w.sum()); base_neg = int((port_w < 0).sum()); tot = len(port_w)
    print(f"\n  {'کاندید':<40}{'سودِ خالص':>14}{'هفتهٔ منفی':>14}{'%منفی':>9}{'بدترین دنباله':>16}", flush=True)
    print("  " + "-" * 90, flush=True)

    def report(name, w):
        neg = int((w < 0).sum()); net = float(w.sum())
        streak, wsum = worst_streak(w)
        print(f"  {name:<40}{net:>14,.0f}{neg:>10}/{tot:<3}{100*neg/tot:>8.1f}%"
              f"{streak:>6}wk/{wsum:>7,.0f}$", flush=True)
        return dict(name=name, net=net, neg=neg, tot=tot, streak=streak, wsum=wsum, w=w)

    cands = []
    cands.append(report('پایه (همهٔ ۵ لایه)', port_w))
    cands[-1]['tag'] = 'Baseline (all 5 layers)'
    names = list(lay_w.keys())
    tags = {'S67': 'drop S67', 'ScalpV2': 'drop ScalpV2 (M5)', 'S81': 'drop S81',
            'SHORT': 'drop SHORT', 'S73': 'drop S73'}
    for drop in names:
        w = sum((lay_w[n] for n in names if n != drop), start=pd.Series(0.0, index=all_weeks))
        c = report(f'حذفِ: {drop}', w)
        c['tag'] = next((v for k, v in tags.items() if k in drop), 'drop layer')
    # کاهش‌وزنِ ScalpV2 (نوسانی‌ترین) به نصف
    sc = [n for n in names if 'ScalpV2' in n]
    if sc:
        scn = sc[0]
        w = sum((lay_w[n]*(0.5 if n == scn else 1.0) for n in names),
                start=pd.Series(0.0, index=all_weeks))
        c = report('کاهش‌وزنِ ScalpV2 به ۵۰٪', w)
        c['tag'] = 'ScalpV2 weight 50%'

    # انتخابِ بهترین طبقِ قانونِ #۱: بیشترین سودِ خالص، سپس کمترین %منفی
    # (اگر دو کاندید سودِ نزدیک داشتند، آنکه هفتهٔ منفیِ کمتری دارد برنده است)
    best_net = max(cands, key=lambda c: c['net'])
    # کاندیدهایی که سودشان دستِ‌کم به‌اندازهٔ پایه است ولی هفتهٔ منفیِ کمتری دارند:
    improved = [c for c in cands if c['net'] >= base_net and c['neg'] < base_neg]
    print(f"\n  بیشترین سودِ خالص: «{best_net['name']}» = +${best_net['net']:,.0f} "
          f"(هفتهٔ منفی {best_net['neg']}/{tot} = {100*best_net['neg']/tot:.1f}%)", flush=True)
    if improved:
        b = max(improved, key=lambda c: c['net'])
        print(f"  ✅ راهکارِ برنده (سود ≥ پایه و هفتهٔ منفیِ کمتر): «{b['name']}» "
              f"→ +${b['net']:,.0f}، هفتهٔ منفی {100*b['neg']/tot:.1f}% "
              f"(پایه {100*base_neg/tot:.1f}%)", flush=True)
        chosen = b
    else:
        print("  ⚠️ هیچ کاندیدی هم‌زمان سودِ ≥پایه و هفتهٔ منفیِ کمتر نداد ⇒ "
              "طبقِ قانونِ #۱ سودِ خالص مقدم است، پایه حفظ می‌شود.", flush=True)
        chosen = best_net

    # ذخیرهٔ خروجی
    out = {
        'cutoff': str(cutoff.date()),
        'contrib_negweeks': contrib,
        'worst_layer': worst_layer,
        'base': {'net': base_net, 'neg': base_neg, 'tot': tot},
        'candidates': [{k: v for k, v in c.items() if k != 'w'} for c in cands],
        'chosen': chosen['name'],
    }
    with open(os.path.join(RES, '_s131_attribution.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\n  خلاصه در results/_s131_attribution.json ذخیره شد.", flush=True)

    # نمودارِ مقایسهٔ پایه vs بهترین کاندید (Equity ماهانهٔ تجمعی)
    plot(port, chosen, layer_ev, all_weeks, base_neg, tot)
    print("\nتمام.", flush=True)


def plot(port, chosen, layer_ev, all_weeks, base_neg, tot):
    base = 100_000.0
    port_w = weekly_series(port)
    cw = chosen['w']
    ctag = chosen.get('tag', chosen['name'])
    fig, axes = plt.subplots(2, 1, figsize=(14, 9))

    # --- بالا: هر دو منحنیِ Equity (خط‌چینِ باریک برای پایه تا هر دو دیده شوند) ---
    ax = axes[0]
    ax.plot(np.arange(len(port_w)), (base + port_w.cumsum()).values,
            color='#1e3a8a', lw=3.2, alpha=0.9, label=f'Baseline all-5 (neg {base_neg}/{tot})')
    ax.plot(np.arange(len(cw)), (base + cw.cumsum()).values,
            color='#f59e0b', lw=1.6, ls='--', label=f"{ctag} (neg {chosen['neg']}/{tot})")
    ax.axhline(base, color='gray', ls=':', lw=0.8)
    ax.set_title('Equity Curve — Baseline vs Chosen Fix (recent 4y, weekly cum.)', fontsize=13)
    ax.set_ylabel('Cumulative Net Profit ($)')
    ax.legend(loc='upper left'); ax.grid(alpha=0.3)

    # --- پایین: تفاوتِ تجمعی (chosen منهای پایه) تا اثرِ واقعیِ راهکار دیده شود ---
    ax = axes[1]
    diff = (cw.cumsum() - port_w.cumsum()).values
    ax.fill_between(np.arange(len(diff)), 0, diff,
                    where=(diff >= 0), color='#16a34a', alpha=0.6, label='fix better')
    ax.fill_between(np.arange(len(diff)), 0, diff,
                    where=(diff < 0), color='#dc2626', alpha=0.6, label='fix worse')
    ax.axhline(0, color='black', lw=0.8)
    ax.set_title(f'Cumulative Difference (Chosen − Baseline) — final = '
                 f'{diff[-1]:+,.0f}$  |  net {chosen["net"]:+,.0f}$ vs {float(port_w.sum()):+,.0f}$',
                 fontsize=13)
    ax.set_ylabel('Δ Cumulative ($)'); ax.set_xlabel('week index')
    ax.legend(loc='upper left'); ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(RES, '_s131_fix_compare.png')
    plt.savefig(path, dpi=110, bbox_inches='tight'); plt.close()
    print(f"  نمودار ذخیره شد: {path}", flush=True)


if __name__ == '__main__':
    main()
