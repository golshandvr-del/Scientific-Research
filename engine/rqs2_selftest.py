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


def horizon(trades, factor=1.0):
    """محورِ زمانِ مصنوعی برای کارت. `factor=1` ⇒ افقِ داده ≈ گسترهٔ معاملات
    (پوششِ کامل). `factor=5` ⇒ افقِ داده پنج برابرِ گسترهٔ معاملات، یعنی معاملات
    در ~۲۰٪ نخستِ تقویم **خوشه** شده‌اند و `H6` باید آن را بگیرد."""
    hi = int(trades['exit_bar'].max()) + 2
    return np.arange(int(hi * factor), dtype='float64')


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

    print("=" * 96)
    print("SELF-TEST RESULT: " + ("ALL PASS ✅" if allok else "FAILURES PRESENT ❌"))
    print("=" * 96)
    return 0 if allok else 1


if __name__ == '__main__':
    raise SystemExit(main())
