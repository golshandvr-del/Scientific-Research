# -*- coding: utf-8 -*-
"""
تستِ واحدِ RQS2 — اعتبارسنجیِ خودِ معیار با موردهای مصنوعیِ **معلوم‌الجواب**
================================================================================
یک معیارِ اعتبارسنجی‌نشده بی‌ارزش است. پیش از آنکه RQS2 به لایه‌ای حکم بدهد،
باید ثابت شود که خودش روی موردهایی که جوابشان *از پیش* معلوم است درست عمل
می‌کند — به‌ویژه روی همان دو حفره‌ای که RQS+ داشت:

  T1  لایهٔ «فقط رانش»    : WR بالا ولی مبنای بی‌سیگنال هم همان‌قدر ⇒ باید H3 رد شود
  T2  لایهٔ «مهارتِ واقعی» : WR مشابهِ T1 ولی مبنا پایین          ⇒ باید H3 پاس شود
  T3  نبودِ `tp_pip`      : ⇒ باید H2 = UNKNOWN و حکم INCOMPLETE (نه ACCEPT)
  T4  تقلبِ TP<SL         : WR جعلیِ ۷۸٪ با TP=0.3×SL           ⇒ باید H2 رد شود
  T5  نبودِ مدلِ صفر       : ⇒ باید H3/H4/H5 = UNKNOWN و حکم INCOMPLETE
  T6  سمتِ بی‌مهارت       : لانگ ماهر + شورتِ سوارِ رانش         ⇒ باید H4 رد شود
  T7  خوشه‌ای‌شدنِ تقویمی  : همهٔ معاملات در یک بازه              ⇒ باید H6 رد شود
  T8  معاملاتِ هم‌پوشان    : ⇒ باید H0 رد شود (p-value نامعتبر)

── موردهای نسخهٔ ۲.۱ — اعتبارسنجیِ رفعِ **سه خطای بُعدی** ──────────────────────
کاربر افشا کرد که نسخهٔ ۲.۰ یک اسکالپِ **سوددهِ** `RR=3` را رد می‌کرد. سه دروازه
عددِ WR را بدونِ RR می‌سنجیدند و در نتیجه فرضِ نااعلامِ `RR≈1` را حمل می‌کردند:
`H1` (کفِ مطلقِ ۶۰٪) · `H8` (کاپِ مطلقِ MCL=8) · `H7` (کفِ یتیمِ ۵۷٪).
این موردها ثابت می‌کنند رفع **کار می‌کند**، نه اینکه ادعا می‌شود:

  T13 اسکالپِ `SL=7 TP=21 WR=45٪` : ⇒ H1/H2/H7/H8 **همه پاس** (هر سه قبلاً رد
      می‌شدند) ولی H9 رد ⇒ REJECT. **علتِ رد اقتصادی است، نه بُعدی.**
  T14 ⭐ همان اسکالپ با `WR=50٪`   : ⇒ **ACCEPT کامل.** اثباتِ اینکه RQS2 یک لایهٔ
      WR-پایینِ RR-بالا را می‌پذیرد — یعنی «سوگیریِ ضدِ اسکالپ» رفع شد.
  T15 همان اسکالپ با ترتیبِ تصادفی : MCL=12 ⇒ کاپِ قدیمِ ۸ می‌شکست، ولی کرانِ
      Erdős–Rényi (۱۷) آن را **روتین** می‌شمارد و شکست به علتِ **واقعی** یعنی
      افتِ سرمایه نسبت داده می‌شود.
  T16 بلیتِ بخت‌آزمایی            : یک برندهٔ استثنایی ۶۴٪ سودِ ناخالص ⇒ H1 رد
      (سپرِ نوِ `top_win_share` — معکوسِ اشتباهِ رایجِ #۸)
  T17 دمِ برندهٔ نمونه‌گیری‌نشده    : فقط ۶ برنده ⇒ H1 رد (سپرِ نوِ `WIN_FLOOR`)

اجرا:  python -m engine.rqs2_selftest
"""
import numpy as np
import pandas as pd

from engine import rqs2 as R


def make_trades(n_win, n_loss, sl_pip, tp_pip, *, side='long', start_bar=0,
                step=10, hold=5, interleave=True):
    """ساختِ DataFrameِ معاملاتِ مصنوعیِ سازگار با قراردادِ `simulate_trades`.

    `pnl_pip` دقیقاً مثلِ موتور محاسبه می‌شود: برد = TP، باخت = −SL
    (هزینه از پیش در سطوح لحاظ شده فرض می‌شود تا تستِ دروازه‌ها خالص بماند).
    """
    rows, b = [], start_bar
    seq = ((['win'] * n_win + ['loss'] * n_loss) if not interleave else
           _interleave(n_win, n_loss))
    for o in seq:
        rows.append(dict(signal_bar=b, entry_bar=b, exit_bar=b + hold,
                         direction=side, entry_price=1.0, exit_price=1.0,
                         outcome=o,
                         pnl_pip=(tp_pip if o == 'win' else -sl_pip),
                         sl_pip=sl_pip, bars_held=hold))
        b += step
    return pd.DataFrame(rows)


def _interleave(a, b):
    """پخشِ یکنواختِ برد/باخت تا رشتهٔ باختِ متوالی مصنوعی نسازیم (H8) و هر
    بازهٔ تقویمی سودده شود (H6)."""
    out, ra, rb = [], a, b
    while ra > 0 or rb > 0:
        if ra * (b + 1) >= rb * (a + 1):
            if ra > 0:
                out.append('win'); ra -= 1
            else:
                out.append('loss'); rb -= 1
        else:
            if rb > 0:
                out.append('loss'); rb -= 1
            else:
                out.append('win'); ra -= 1
    return out


#  فاصلهٔ کندلِ محورِ زمانِ مصنوعی = **فاصلهٔ کارتِ D1**.
#  ⭐ چرا دقیقاً D1؟ چون افقِ رژیمِ v2.3 برابرِ ۲۰۰ **روزِ معاملاتی** (=۲۸۰ روزِ
#  تقویمی) است، و روی فاصلهٔ D1 همین افق دقیقاً ۲۰۰ **کندل** می‌شود — یعنی عیناً
#  ثابتِ کندل‌محورِ قدیم. پس این انتخاب دو کار را با هم انجام می‌دهد:
#    (۱) موردهای حقیقتِ‌زمینیِ H10 با همان نیّتِ اصلی و همان جوابِ معلوم می‌مانند
#        (`mk_close(cycle=800)` باز هم رژیم را متناوب می‌کند)،
#    (۲) و **خودِ خاصیتِ ناوردایی روی D1 را اثبات می‌کند**: تصحیحِ زمان‌محور روی
#        کارتِ D1 هیچ‌چیز را عوض نمی‌کند و فقط کارت‌های بدمقیاس را اصلاح می‌کند.
BAR_SECONDS_D1 = (R.REGIME_LOOKBACK_SECONDS / 200.0)   # ۱۲۰٬۹۶۰s ≈ ۱.۴ روز


def horizon(trades, factor=1.0, bar_seconds=BAR_SECONDS_D1, t0=1_500_000_000.0):
    """محورِ زمانِ مصنوعی برای کارت. `factor=1` ⇒ افقِ داده ≈ گسترهٔ معاملات
    (پوششِ کامل). `factor=5` ⇒ افقِ داده پنج برابرِ گسترهٔ معاملات، یعنی معاملات
    در ~۲۰٪ نخستِ تقویم **خوشه** شده‌اند و `H6` باید آن را بگیرد.

    ⚠️ از v2.3 خروجی **زمانِ حقیقی (unix)** است نه شمارهٔ کندل، چون افقِ رژیمِ
    `H10` دیگر زمان‌محور است. `bar_seconds` پیش‌فرض = فاصلهٔ D1 (بالا را ببینید).
    """
    hi = int(trades['exit_bar'].max()) + 2
    n = int(hi * factor)
    return t0 + np.arange(n, dtype='float64') * float(bar_seconds)


def mk_close(n_bars, cycle=800, amp=0.25):
    """سریِ قیمتِ مصنوعی با رژیم‌های **متناوبِ** صعودی/نزولی.

    با `REGIME_LOOKBACK=200` و `cycle=800`، علامتِ بازدهِ ۲۰۰ کندلِ گذشته به‌طورِ
    دوره‌ای عوض می‌شود ⇒ حدوداً نیمی از معاملات «هم‌سو» و نیمی «خلاف‌جریان»
    می‌افتند، که برای آزمونِ معنادارِ H10 لازم است.
    """
    t = np.arange(int(n_bars), dtype='float64')
    return 100.0 * np.exp(amp * np.sin(2 * np.pi * t / float(cycle)))


def assign_outcomes(trades, close, wr_counter, wr_aligned, sl_pip, tp_pip):
    """بازنویسیِ نتیجهٔ معاملات تا WR در **دو زیرمجموعهٔ رژیمی** دقیقاً کنترل شود.

    این تنها راهِ ساختِ موردِ معلوم‌الجواب برای H10 است: باید بتوانیم لایه‌ای
    بسازیم که کلِ WR آن قابلِ قبول باشد ولی همهٔ سودش از معاملاتِ هم‌سو بیاید.
    """
    cdm = R.counter_drift_mask(trades, close)
    assert cdm is not None, "close series too short for the regime lookback"
    out = trades.copy().reset_index(drop=True)
    outcomes = [None] * len(out)
    for mask, wr in ((cdm, wr_counter), (~cdm, wr_aligned)):
        idx = np.where(mask)[0]
        k = int(round(len(idx) * float(wr) / 100.0))
        for i, o in zip(idx, _interleave(k, len(idx) - k)):
            outcomes[i] = o
    out['outcome'] = outcomes
    out['pnl_pip'] = [tp_pip if o == 'win' else -sl_pip for o in outcomes]
    return out


def make_scalp(n, wr_pct, sl_lvl, tp_lvl, cost_pip, *, shuffle_seed=None,
               step=10, hold=5):
    """اسکالپِ مصنوعی با هندسهٔ `RR>1` و `pnl_pip`ِ **خالصِ پس از هزینه**.

    تفاوتِ مهم با `make_trades`: این‌جا **سطح** و **نتیجهٔ اقتصادی** از هم جدا
    می‌شوند، چون تمامِ بحثِ نسخهٔ ۲.۱ همین است —
      • سطوح  (`sl_lvl`/`tp_lvl`) ⇒ هندسه، ورودیِ `breakeven_wr_cost`
      • خالص  (`tp−c` و `−(sl+c)`) ⇒ اقتصاد، ورودیِ `expectancy`
    `make_trades` هزینه را «از پیش لحاظ‌شده» فرض می‌کند که برای `SL=TP=100`
    بی‌اثر است (۳.۳ در برابرِ ۱۰۰) ولی برای اسکالپ **تعیین‌کننده** است
    (۳.۳ در برابرِ ۲۱ ⇒ ۱۵.۷٪ از هدف).

    `shuffle_seed=None` ⇒ پخشِ یکنواخت (رشتهٔ باختِ مصنوعی نمی‌سازد).
    `shuffle_seed=k`    ⇒ ترتیبِ **تصادفیِ واقع‌گرایانه** ⇒ رشتهٔ باختِ طبیعی.
    """
    nw = int(round(n * float(wr_pct) / 100.0))
    nl = n - nw
    if shuffle_seed is None:
        seq = _interleave(nw, nl)
    else:
        seq = ['win'] * nw + ['loss'] * nl
        np.random.default_rng(int(shuffle_seed)).shuffle(seq)
    win_net = float(tp_lvl) - float(cost_pip)
    loss_net = float(sl_lvl) + float(cost_pip)
    rows, b = [], 0
    for o in seq:
        rows.append(dict(signal_bar=b, entry_bar=b, exit_bar=b + hold,
                         direction='long', entry_price=1.0, exit_price=1.0,
                         outcome=o,
                         pnl_pip=(win_net if o == 'win' else -loss_net),
                         sl_pip=float(sl_lvl), bars_held=hold))
        b += step
    return pd.DataFrame(rows)


def make_trades_pnl(win_pnls, loss_pnls, sl_pip, *, step=10, hold=5):
    """معاملات با `pnl_pip`ِ **دلخواه و نامتقارن** — برای آزمونِ سپرهای نوِ H1.

    تنها راهِ ساختِ «بلیتِ بخت‌آزمایی» است: برندگانی با اندازه‌های متفاوت که
    یکی‌شان بخشِ بزرگی از سودِ ناخالص را تنها می‌سازد.
    """
    seq = ([('win', v) for v in win_pnls] + [('loss', v) for v in loss_pnls])
    order = _interleave(len(win_pnls), len(loss_pnls))
    wq = list(win_pnls)
    lq = list(loss_pnls)
    rows, b = [], 0
    for o in order:
        v = wq.pop(0) if o == 'win' else lq.pop(0)
        rows.append(dict(signal_bar=b, entry_bar=b, exit_bar=b + hold,
                         direction='long', entry_price=1.0, exit_price=1.0,
                         outcome=o,
                         pnl_pip=(abs(v) if o == 'win' else -abs(v)),
                         sl_pip=float(sl_pip), bars_held=hold))
        b += step
    assert not wq and not lq and len(rows) == len(seq)
    return pd.DataFrame(rows)


def mk_null(long_wr, short_wr=None, sd=1.5, k=20, gap=4.0):
    """مدلِ صفرِ مصنوعی. `gap` = فاصلهٔ perm_max از perm_mean."""
    d = {}
    for s, v in (('long', long_wr), ('short', short_wr)):
        if v is None:
            v = 45.0
        d[s] = dict(uncond_wr=v, perm_mean=v, perm_sd=sd, perm_max=v + gap,
                    perm_k=k)
    return d


def _run(name, trades, *, expect_gate=None, expect_state=None, **kw):
    r = R.compute_rqs2(trades, 'XAUUSD', **kw)
    ok = True
    detail = []
    if expect_gate:
        for g, want in expect_gate.items():
            got = r['gates'][g]
            if got is not want:
                ok = False
                detail.append(f"{g} want={want} got={got}")
    if expect_state and r['verdict'] != expect_state:
        ok = False
        detail.append(f"verdict want={expect_state} got={r['verdict']}")
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print("        " + R.format_rqs2(name[:22], r))
    if detail:
        print("        >>> " + " | ".join(detail))
    return ok, r


def main():
    print("=" * 96)
    print("RQS2 SELF-TEST — synthetic cases with known ground truth")
    print("=" * 96)
    allok = True

    SL, TP = 100.0, 100.0          # RR=1 ⇒ سربه‌سرِ بی‌هزینه ۵۰٪
    NT = 1000                      # n_trials فرضی برای H5 (جریمهٔ Bonferroni)

    # پایه: n=400 با WR=63٪. اندازهٔ نمونه عمداً بزرگ است تا لایهٔ «بامهارت»
    # بتواند از جریمهٔ ۱۰۰۰ آزمونِ H5 هم جان سالم ببرد — وگرنه H5 در همهٔ
    # سناریوها رد می‌شد و آزمونِ بقیهٔ دروازه‌ها بی‌معنا می‌گشت.
    t = make_trades(252, 148, SL, TP)                      # WR = 63.0٪
    BT = horizon(t)                                        # پوششِ کاملِ تقویم
    CL = mk_close(int(t['exit_bar'].max()) + 400)          # رژیم‌های متناوب

    # ---- T1: فقط رانش — WR=63٪ ولی مبنای بی‌سیگنال هم ۶۰٪ است ----
    ok, _ = _run("T1 drift-only (fail H3)", t,
                 expect_gate={'H3': False}, expect_state='REJECT',
                 tp_pip=TP, bar_time=BT, close=CL, null=mk_null(60.0),
                 n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T2: مهارتِ واقعی — همان WR ولی مبنا ۵۲٪ ⇒ باید کاملاً ACCEPT شود ----
    #   این سخت‌ترین آزمونِ معیار است: معیاری که همه‌چیز را رد کند بی‌فایده است.
    ok, _ = _run("T2 real skill (full ACCEPT)", t,
                 expect_gate={'H3': True}, expect_state='ACCEPT',
                 tp_pip=TP, bar_time=BT, close=CL, null=mk_null(52.0),
                 n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T3: نبودِ tp_pip ⇒ H2 نامعلوم، حکم INCOMPLETE (نه ACCEPT، نه REJECT) ----
    ok, _ = _run("T3 tp_pip missing (H2=?)", t,
                 expect_gate={'H2': None}, expect_state='INCOMPLETE',
                 bar_time=BT, close=CL, null=mk_null(52.0), n_trials=NT,
                 split_bar=1000)
    allok &= ok

    # ---- T4: تقلبِ TP<SL — WR جعلیِ ۷۸٪ با TP=0.3×SL ----
    t4 = make_trades(312, 88, SL, 30.0)                    # WR = 78.0٪
    ok, _ = _run("T4 TP<SL gaming (fail H2)", t4,
                 expect_gate={'H2': False},
                 tp_pip=30.0, sl_pip=SL, bar_time=horizon(t4),
                 close=mk_close(int(t4['exit_bar'].max()) + 400),
                 null=mk_null(52.0), n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T5: نبودِ مدلِ صفر ⇒ H3/H4/H5 نامعلوم ----
    ok, _ = _run("T5 no null model (H3/H4/H5=?)", t,
                 expect_gate={'H3': None, 'H4': None, 'H5': None},
                 expect_state='INCOMPLETE',
                 tp_pip=TP, bar_time=BT, close=CL, split_bar=1000)
    allok &= ok

    # ---- T6: سمتِ بی‌مهارت — لانگِ ماهر (۷۰٪ vs ۵۲) + شورتِ سوارِ رانش (۵۶٪ vs ۵۵) ----
    tl = make_trades(140, 60, SL, TP, side='long', start_bar=0, step=20)
    ts = make_trades(112, 88, SL, TP, side='short', start_bar=10, step=20)
    t6 = pd.concat([tl, ts], ignore_index=True).sort_values('exit_bar')
    ok, _ = _run("T6 one skilless side (fail H4)", t6,
                 expect_gate={'H4': False},
                 tp_pip=TP, bar_time=horizon(t6),
                 close=mk_close(int(t6['exit_bar'].max()) + 400),
                 null=mk_null(52.0, 55.0), n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T7: خوشه‌ای‌شدنِ تقویمی — معاملات فقط در ~۲۰٪ نخستِ افقِ داده ----
    ok, _ = _run("T7 calendar clustering (fail H6)", t,
                 expect_gate={'H6': False},
                 tp_pip=TP, bar_time=horizon(t, factor=5), close=CL,
                 null=mk_null(52.0), n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T8: معاملاتِ هم‌پوشان ⇒ استقلال نقض ⇒ H0 رد ----
    t8 = make_trades(252, 148, SL, TP, step=2, hold=9)     # hold > step
    ok, _ = _run("T8 overlapping trades (fail H0)", t8,
                 expect_gate={'H0': False},
                 tp_pip=TP, bar_time=horizon(t8),
                 close=mk_close(int(t8['exit_bar'].max()) + 400),
                 null=mk_null(52.0), n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T9: نبودِ محورِ زمان ⇒ H6 نامعلوم (ادعا نشده ≠ تأیید شده) ----
    ok, _ = _run("T9 no bar_time (H6=?)", t,
                 expect_gate={'H6': None}, expect_state='INCOMPLETE',
                 tp_pip=TP, close=CL, null=mk_null(52.0), n_trials=NT,
                 split_bar=1000)
    allok &= ok

    # ---- T10 ⭐ سوارِ رانش: کلِ WR قابلِ قبول ولی همهٔ سود از معاملاتِ هم‌سو ----
    #   این همان لایه‌ای است که *همهٔ* دروازه‌های دیگر — از جمله آزمونِ جای‌گشت —
    #   از آن عبور می‌کنند، چون جای‌گشت رانشِ نمونه را حفظ می‌کند.
    t10 = assign_outcomes(t, CL, wr_counter=40.0, wr_aligned=82.0, sl_pip=SL,
                          tp_pip=TP)
    ok, _ = _run("T10 drift-rider (fail H10)", t10,
                 expect_gate={'H3': True, 'H10': False},
                 tp_pip=TP, bar_time=BT, close=CL, null=mk_null(52.0),
                 n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T11: لبهٔ واقعی — در هر دو رژیم سودده ⇒ H10 پاس ----
    t11 = assign_outcomes(t, CL, wr_counter=62.0, wr_aligned=64.0, sl_pip=SL,
                          tp_pip=TP)
    ok, _ = _run("T11 regime-robust (pass H10)", t11,
                 expect_gate={'H10': True}, expect_state='ACCEPT',
                 tp_pip=TP, bar_time=BT, close=CL, null=mk_null(52.0),
                 n_trials=NT, split_bar=1000)
    allok &= ok

    # ---- T12: نبودِ سریِ قیمت ⇒ H10 نامعلوم ----
    ok, _ = _run("T12 no close (H10=?)", t,
                 expect_gate={'H10': None}, expect_state='INCOMPLETE',
                 tp_pip=TP, bar_time=BT, null=mk_null(52.0), n_trials=NT,
                 split_bar=1000)
    allok &= ok

    # ======================================================================
    #  موردهای نسخهٔ ۲.۱ — اعتبارسنجیِ رفعِ سه خطای بُعدی (RR-blindness)
    # ======================================================================
    print("-" * 96)
    print("v2.1 CASES — validating the RR-awareness fixes (H1 / H7 / H8)")
    print("-" * 96)

    SL_S, TP_S = 7.0, 21.0                 # RR = 3
    COST_S = R.se.ASSETS['XAUUSD']['spread_pip']       # ۳.۳pip
    BE_COST = (SL_S + COST_S) / (SL_S + TP_S) * 100.0        # ۳۶.۷۹٪
    BE_ROBUST = (SL_S + 2 * COST_S) / (SL_S + TP_S) * 100.0  # ۴۸.۵۷٪
    print(f"    scalp geometry SL={SL_S} TP={TP_S} (RR=3) cost={COST_S}pip")
    print(f"    cost breakeven      (SL+c)/(SL+TP)  = {BE_COST:.2f}%   ⇐ H2")
    print(f"    ROBUST breakeven    (SL+2c)/(SL+TP) = {BE_ROBUST:.2f}%   ⇐ H9 "
          f"(cost-stress) ⇒ the REAL bar for a scalp")

    # ---- T13: اسکالپِ کاربر با WR=45٪ — سه دروازهٔ اصلاح‌شده باید پاس شوند ----
    #   قبلِ نسخهٔ ۲.۱: H1 رد (۴۵<۶۰) · H7 رد (۴۵<۵۷) ⇒ «سوگیریِ ضدِ اسکالپ».
    #   بعدِ نسخهٔ ۲.۱: هر دو پاس؛ رد فقط از H9 می‌آید چون
    #   `exp=+۲.۳۰pip < cost=۳.۳pip` ⇒ اگر اسپرد دو برابر شود لایه زیان‌ده است.
    #   این ردِ **اقتصادی** است نه بُعدی — و برای اسکالپ مهم‌ترین ریسکِ واقعی.
    t13 = make_scalp(800, 45.0, SL_S, TP_S, COST_S)
    BT13 = horizon(t13)
    CL13 = mk_close(int(t13['exit_bar'].max()) + 400)
    ok, r13 = _run("T13 RR=3 scalp WR=45 (H1/H2/H7/H8 pass, H9 fails)", t13,
                   expect_gate={'H1': True, 'H2': True, 'H7': True,
                                'H8': True, 'H9': False},
                   expect_state='REJECT',
                   sl_pip=SL_S, tp_pip=TP_S, bar_time=BT13, close=CL13,
                   null=mk_null(36.0), n_trials=NT, split_bar=6000)
    allok &= ok
    m13 = r13['metrics']
    sub = (abs(m13['breakeven_wr_cost'] - BE_COST) < 0.01
           and m13['expectancy_at_2x_cost'] < 0)
    print(f"        >>> {'OK  ' if sub else 'BAD '} economic cause: "
          f"exp={m13['expectancy_pip']:+.2f}pip vs cost={COST_S}pip ⇒ "
          f"exp@2x={m13['expectancy_at_2x_cost']:+.2f} ; be_cost="
          f"{m13['breakeven_wr_cost']:.2f}% (H2 excess "
          f"{m13['wr_excess_cost']:+.2f}pp)")
    allok &= sub

    # ---- T14 ⭐ همان اسکالپ با WR=50٪ (بالای سربه‌سرِ مقاوم ۴۸.۵۷٪) ⇒ ACCEPT ----
    #   ⭐ **موردِ سرنوشت‌ساز.** اگر این پاس شود، ادعای «RQS2 اسکالپ را رد می‌کند»
    #   قطعاً باطل است: لایه‌ای با WR=۵۰٪ — یعنی ۱۰pp زیرِ کفِ ارثیِ ۶۰٪ —
    #   نمرهٔ کاملِ ACCEPT می‌گیرد، تنها به‌خاطرِ اینکه هندسه‌اش `RR=3` است.
    t14 = make_scalp(800, 50.0, SL_S, TP_S, COST_S)
    ok, r14 = _run("T14 ⭐ RR=3 scalp WR=50 (full ACCEPT)", t14,
                   expect_gate={'H1': True, 'H2': True, 'H7': True,
                                'H8': True, 'H9': True},
                   expect_state='ACCEPT',
                   sl_pip=SL_S, tp_pip=TP_S, bar_time=horizon(t14),
                   close=mk_close(int(t14['exit_bar'].max()) + 400),
                   null=mk_null(36.0), n_trials=NT, split_bar=6000)
    allok &= ok
    m14 = r14['metrics']
    sub = (m14['win_rate'] < R.WR_FLOOR_NO_RR
           and m14['win_rate'] > BE_ROBUST
           and m14['expectancy_at_2x_cost'] > 0)
    print(f"        >>> {'OK  ' if sub else 'BAD '} accepted at WR="
          f"{m14['win_rate']:.2f}% which is {R.WR_FLOOR_NO_RR - m14['win_rate']:.2f}pp "
          f"BELOW the legacy floor and {m14['win_rate'] - BE_ROBUST:+.2f}pp above "
          f"the robust breakeven ⇒ anti-scalp bias is gone")
    allok &= sub

    # ---- T15: ترتیبِ تصادفیِ واقع‌گرایانه ⇒ MCL=12 ----
    #   کاپِ قدیمِ `MCL≤8` این را «بیمارگونه» می‌شمرد. کرانِ Erdős–Rényi برای
    #   `WR=45٪, n=800` عددِ ۱۷ است ⇒ رشتهٔ ۱۲ **روتین** است و دروازه باید شکست
    #   را به علتِ **واقعی** نسبت دهد: افتِ سرمایه (۱۵.۴٪ > ۸٪ در ریسکِ ۱٪).
    t15 = make_scalp(800, 45.0, SL_S, TP_S, COST_S, shuffle_seed=7)
    ok, r15 = _run("T15 realistic ordering (MCL routine, DD is the real cause)",
                   t15,
                   expect_gate={'H8': False},
                   sl_pip=SL_S, tp_pip=TP_S, bar_time=horizon(t15),
                   close=mk_close(int(t15['exit_bar'].max()) + 400),
                   null=mk_null(36.0), n_trials=NT, split_bar=6000)
    allok &= ok
    m15 = r15['metrics']
    bound15 = R.mcl_bound(len(t15), m15['win_rate'])
    sub = (m15['max_consec_losses'] > R.MCL_ABS_CAP
           and m15['max_consec_losses'] <= bound15
           and m15['max_dd_pct'] > R.MAXDD_MAX_PCT)
    print(f"        >>> {'OK  ' if sub else 'BAD '} MCL="
          f"{m15['max_consec_losses']} exceeds the legacy cap "
          f"{R.MCL_ABS_CAP} but sits inside the Erdős–Rényi bound {bound15} "
          f"⇒ streak EXCUSED; H8 fails on maxDD={m15['max_dd_pct']:.2f}% "
          f"> {R.MAXDD_MAX_PCT}% ⇒ failure correctly re-attributed")
    allok &= sub

    # ---- T16: بلیتِ بخت‌آزمایی — معکوسِ اشتباهِ رایجِ #۸ ----
    #   حذفِ کفِ WR یک حفره باز می‌کند: `TP>>SL` تا امیدِ ریاضی روی چند برندهٔ
    #   نادر سوار شود. این‌جا ۱۲ برنده هست (پس `WIN_FLOOR` شلیک نمی‌کند) و
    #   `PF=1.50` هم قبول است ⇒ تنها سپری که می‌تواند بگیرد `top_win_share` است.
    t16 = make_trades_pnl([20.0] * 11 + [400.0], [10.3] * 40, SL_S)
    ok, r16 = _run("T16 lottery-ticket concentration (fail H1)", t16,
                   expect_gate={'H1': False},
                   sl_pip=SL_S, tp_pip=TP_S, bar_time=horizon(t16),
                   close=mk_close(int(t16['exit_bar'].max()) + 400),
                   null=mk_null(15.0), n_trials=NT, split_bar=300)
    allok &= ok
    m16 = r16['metrics']
    sub = (m16['profit_factor'] >= R.PF_MIN
           and m16['n_wins'] >= R.WIN_FLOOR
           and m16['top_win_share'] > R.TOP_WIN_SHARE_MAX)
    print(f"        >>> {'OK  ' if sub else 'BAD '} isolated: PF="
          f"{m16['profit_factor']:.3f}≥{R.PF_MIN} ✓ and n_wins="
          f"{m16['n_wins']}≥{R.WIN_FLOOR} ✓, so ONLY top_win_share="
          f"{m16['top_win_share']:.3f}>{R.TOP_WIN_SHARE_MAX} caused the failure")
    allok &= sub

    # ---- T17: دمِ برندهٔ نمونه‌گیری‌نشده ----
    #   `RR` نجومی با ۶ برنده: برندگان هم‌اندازه‌اند (پس `top_win_share` شلیک
    #   نمی‌کند) و `PF=2.33` قبول است ⇒ تنها `WIN_FLOOR` می‌تواند بگیرد.
    t17 = make_trades_pnl([400.0] * 6, [10.3] * 100, SL_S)
    ok, r17 = _run("T17 unsampled winning tail (fail H1)", t17,
                   expect_gate={'H1': False},
                   sl_pip=SL_S, tp_pip=800.0, bar_time=horizon(t17),
                   close=mk_close(int(t17['exit_bar'].max()) + 400),
                   null=mk_null(4.0), n_trials=NT, split_bar=600)
    allok &= ok
    m17 = r17['metrics']
    sub = (m17['profit_factor'] >= R.PF_MIN
           and m17['n_wins'] < R.WIN_FLOOR
           and (m17['top_win_share'] or 0) <= R.TOP_WIN_SHARE_MAX)
    print(f"        >>> {'OK  ' if sub else 'BAD '} isolated: PF="
          f"{m17['profit_factor']:.3f}≥{R.PF_MIN} ✓ and top_win_share="
          f"{m17['top_win_share']:.3f}≤{R.TOP_WIN_SHARE_MAX} ✓, so ONLY "
          f"n_wins={m17['n_wins']}<{R.WIN_FLOOR} caused the failure")
    allok &= sub

    print("=" * 96)
    print("SELF-TEST RESULT: " + ("ALL PASS ✅" if allok else "FAILURES PRESENT ❌"))
    print("=" * 96)
    return 0 if allok else 1


if __name__ == '__main__':
    raise SystemExit(main())
