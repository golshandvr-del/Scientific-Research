# -*- coding: utf-8 -*-
"""
rqs_metric.py — RQS (Robust Quality Score / امتیازِ کیفیتِ مقاوم)

پاسخِ مستقیم به نگرانیِ کاربر (این نشست):
  «سود خالص و WR به‌تنهایی گول‌زننده‌اند؛ یک استراتژیِ رندوم هم می‌تواند WR بالا بگیرد
   (BUG-044/045). معیاری می‌خواهم که کاراییِ واقعیِ استراتژی، سیگنال‌های درست، و
   اینکه معاملاتِ درست ضررِ معاملاتِ اشتباه را جبران کنند را بسنجد — تا سرمایهٔ
   دموِ کاربر دوباره صفر نشود.»

RQS از پنج دروازهٔ سخت (hard gate) ساخته شده. یک لایه فقط وقتی «واقعی/قابلِ‌اتصال
به سایت» است که هر ۵ دروازه را پاس کند. اگر حتی یک دروازه رد شود، لایه با هر WR/net
مردود است (چون یک نقطه‌ضعف برای صفر کردنِ حساب کافی است).

دروازه‌ها:
  G1  Edge-over-Random : net_edge>0  و  WR_excess ≥ WR_EXCESS_MIN
  G2  Profit-Factor    : pf ≥ PF_MIN
  G3  Tail-Risk        : maxDD ≤ MAXDD_PCT×سرمایه  و  worst_loss ≤ WORST_R×avg_win
  G4  Stability        : هر ۴ پنجرهٔ walk-forward مثبت (+ هر دو نیمه مثبت)
  G5  Expectancy       : امیدِ ریاضیِ هر معامله > EXPECTANCY_MIN دلار

خروجی: dict شاملِ pass/fail هر دروازه، دلایل، و نمرهٔ ۰..۱۰۰ (با veto).
"""
from __future__ import annotations
import numpy as np

# ---------------------------------------------------------------------------
# آستانه‌ها (قابلِ تنظیم؛ محافظه‌کارانه انتخاب شده‌اند تا از فاجعهٔ صفرشدنِ حساب جلو بگیرند)
# ---------------------------------------------------------------------------
WR_EXCESS_MIN   = 3.0     # درصد؛ WR واقعی باید دستِ‌کم ۳٪ از WRِ سیگنالِ رندومِ هم‌ساختار بالاتر باشد
PF_MIN          = 1.30    # profit factor؛ زیرِ این، لبه شکننده است (یک اسلیپیج منفی‌اش می‌کند)
MAXDD_PCT       = 8.0     # درصدِ سرمایه؛ بیشترین افتِ متوالیِ سرمایه نباید از این بیشتر شود
WORST_R         = 8.0     # بزرگترین باختِ یک معامله نباید از این ضریب × میانگینِ برد بیشتر شود
EXPECTANCY_MIN  = 0.0     # دلار؛ امیدِ ریاضیِ هر معامله باید مثبت باشد (بعد از هزینهٔ واقعی)


def compute_rqs(res: dict, random_wr: float, random_net: float,
                capital: float = 10000.0) -> dict:
    """
    res         : خروجیِ eval_signal (شاملِ net, wr, pf, n, net_usd, exit_bars, wins)
    random_wr   : WRِ سیگنالِ رندومِ هم‌ساختار (همان n، همان TP/SL) — از آزمونِ کنترل
    random_net  : netِ همان سیگنالِ رندوم
    capital     : سرمایهٔ پایه برای سنجشِ drawdown نسبی
    """
    nu = np.asarray(res['net_usd'], dtype=float)
    n = len(nu)
    wins = nu[nu > 0]
    losses = nu[nu < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    worst_loss = float(nu.min()) if n else 0.0

    # --- G1: Edge over Random ---
    wr_excess = res['wr'] - random_wr
    net_edge = res['net'] - random_net
    g1 = (net_edge > 0) and (wr_excess >= WR_EXCESS_MIN)
    g1_detail = f"WR_excess={wr_excess:+.1f}% (min {WR_EXCESS_MIN}), net_edge={net_edge:+.0f}"

    # --- G2: Profit Factor ---
    pf = res.get('pf', 0.0)
    g2 = pf >= PF_MIN
    g2_detail = f"PF={pf:.2f} (min {PF_MIN})"

    # --- G3: Tail Risk ---
    eq = np.cumsum(nu)
    peak = np.maximum.accumulate(eq)
    maxdd = float((eq - peak).min()) if n else 0.0
    maxdd_pct = abs(maxdd) / capital * 100.0
    worst_r = (abs(worst_loss) / avg_win) if avg_win > 0 else 999.0
    g3 = (maxdd_pct <= MAXDD_PCT) and (worst_r <= WORST_R)
    g3_detail = f"maxDD={maxdd_pct:.1f}% (max {MAXDD_PCT}%), worst_loss={worst_r:.1f}x avg_win (max {WORST_R}x)"

    # --- G4: Stability (walk-forward + halves) ---
    exit_bars = np.asarray(res['exit_bars'])
    order = np.argsort(exit_bars)
    o = nu[order]
    half = n // 2
    h1, h2 = o[:half].sum(), o[half:].sum()
    q = n // 4
    wf = [o[i*q:(i+1)*q].sum() if i < 3 else o[3*q:].sum() for i in range(4)]
    g4 = (h1 > 0) and (h2 > 0) and all(w > 0 for w in wf)
    g4_detail = f"halves=({h1:+.0f},{h2:+.0f}) wf={[round(w) for w in wf]}"

    # --- G5: Expectancy per trade ---
    expectancy = float(nu.mean()) if n else 0.0
    g5 = expectancy > EXPECTANCY_MIN
    g5_detail = f"expectancy=${expectancy:+.2f}/trade (min ${EXPECTANCY_MIN})"

    gates = {
        'G1_edge_over_random': (g1, g1_detail),
        'G2_profit_factor':    (g2, g2_detail),
        'G3_tail_risk':        (g3, g3_detail),
        'G4_stability':        (g4, g4_detail),
        'G5_expectancy':       (g5, g5_detail),
    }
    passed_all = all(v[0] for v in gates.values())
    n_pass = sum(1 for v in gates.values() if v[0])

    # --- نمره‌دهی با veto ---
    # هر دروازه ۲۰ امتیاز؛ اما اگر همه پاس نشوند، سقفِ نمره ۴۰ (یعنی «مردود، به سایت راه نده»).
    raw_score = n_pass * 20.0
    if not passed_all:
        score = min(raw_score, 40.0)
    else:
        # بونوسِ کیفیت وقتی همه پاس شده‌اند: بر اساسِ PF و WR_excess
        quality_bonus = min(20.0, (pf - PF_MIN) * 10.0 + max(0.0, wr_excess - WR_EXCESS_MIN))
        score = min(100.0, 80.0 + quality_bonus)

    verdict = 'واقعی/قابلِ‌اتصال ✅' if passed_all else 'مردود (نقطه‌ضعفِ خطرناک) ❌'

    return dict(
        rqs=round(score, 1), verdict=verdict, passed_all=passed_all, n_pass=n_pass,
        gates=gates,
        stats=dict(wr=res['wr'], pf=pf, net=res['net'], n=n,
                   wr_excess=round(wr_excess, 1), net_edge=round(net_edge, 0),
                   avg_win=round(avg_win, 1), avg_loss=round(avg_loss, 1),
                   worst_loss=round(worst_loss, 0), maxdd_pct=round(maxdd_pct, 1),
                   expectancy=round(expectancy, 2)),
    )


def format_rqs(name: str, r: dict) -> str:
    """گزارشِ خوانا برای یک لایه."""
    lines = [f"── {name} ── RQS={r['rqs']}/100  {r['verdict']}  ({r['n_pass']}/5 gate)"]
    for gk, (ok, det) in r['gates'].items():
        mark = '✅' if ok else '❌'
        lines.append(f"    {mark} {gk}: {det}")
    return '\n'.join(lines)


if __name__ == '__main__':
    print("rqs_metric.py — ماژولِ معیارِ کیفیتِ مقاوم. از compute_rqs در اسکریپت‌ها استفاده کنید.")
