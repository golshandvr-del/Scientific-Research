# -*- coding: utf-8 -*-
"""S391 — **فیلترِ کاهشِ افتِ سرمایه** برای نامزدِ `cci20_xup_135 @ XAUUSD_H1`.

نامزد پس از بهبودِ هندسه (S390) **۱۰ از ۱۱** دروازه را پاس می‌کند و تنها
`H8` را رد می‌کند — و تفکیکِ سه‌جزئیِ `H8` نشان داد که **فقط** جزءِ افتِ
سرمایه رد است (۱۱.۶۷٪ در برابرِ ۸.۰٪)، در حالی که رشتهٔ باخت (۲۰ در
برابرِ کرانِ ۲۳) و ضریبِ بازیافت سالم‌اند.

⚠️ قیدِ تنگِ توان (محاسبه‌شده در پیش‌ثبتِ S391، **پیش از** اجرا)
--------------------------------------------------------------
`z` فعلی ۴.۲۴ است و کرانِ شانس ۴.۰۷ ⇒ حاشیهٔ فقط ۰.۱۷. جدولِ
آلفایِ‌لازم/نگه‌داشت نشان داد:

    اگر فیلتر آلفا را بالا نبرد، حداکثر می‌تواند ۱۲.۲٪ معامله دور بریزد.

پس فیلترِ قابلِ‌قبول باید **همزمان** افت را ≥۳۱.۴٪ کم کند **و** آلفا را
به‌قدرِ جبرانِ افتِ `n` بالا ببرد. این بسیار سخت‌تر از «فیلتری که WR را
بالا ببرد» است.

⚠️ نکتهٔ ظریفِ صحت — **خطِ مبنا هم فیلتر می‌خورد**
------------------------------------------------
اگر خریدارِ کورِ **بی‌فیلتر** با لایهٔ **فیلترشده** مقایسه شود، تمامِ اثرِ
فیلتر به‌غلط «مهارت» ثبت می‌شود. مثال: فیلترِ «ساعتِ لندن» ممکن است
WR را ۳ واحد بالا ببرد فقط چون **همه** در آن ساعت بیشتر می‌برند.
پس `uncond_baseline` روی همان زیرمجموعهٔ کندل‌ها ساخته می‌شود.
این هم‌خانوادهٔ باگِ هندسهٔ S386 است و اینجا **ساختاراً** پیشگیری شد.

سایرِ قیدها
----------
* هندسه **قفل** روی `sl_k=1.5, rr=2.2` (بهترین سلولِ S390) — هیچ
  بهینه‌سازیِ همزمانِ هندسه+فیلتر (ضربِ بارِ چندگانگی).
* مقادیرِ **غیررند** عمدی (اشتباهِ رایجِ ۷): ۱۷، ۲۱، ۹۶، ۰.۱۷، ۰.۲۷،
  ۰.۳۸، ۱۴، ۲۳، ۳۱.
* مدلِ صفر برای **هر** سلول از نو (درسِ S385/S387: `perm_max` تابعِ n است؛
  فیلتر n را کم می‌کند ⇒ سقفِ شانس **بالا** می‌رود).
* بارِ چندگانگیِ صادقانه: ۲۳٬۸۸۷ = ۲۳٬۸۷۵ + ۱۲.
* ذخیرهٔ **مرحله‌به‌مرحله** (قانونِ اندک‌اندک — ۷ ریستِ سندباکس).
* سلولِ `none` (بی‌فیلتر) به‌عنوانِ **شاهدِ درونی** اجرا می‌شود و باید
  عیناً با `results/_s390/k1.5_rr2.2.json` بخواند.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R  # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s391')
os.makedirs(OUT, exist_ok=True)

CARD = 'XAUUSD_H1'
RULE = 'cci20_xup_135'
ASSET = 'XAUUSD'
COST_PIP = 3.3
SEED = 20260805
K_PERM = 2000
STRIDES = (1, 3, 7)

# هندسهٔ قفل‌شده — بهترین سلولِ S390
SL_K = 1.5
RR = 2.2

N_TRIALS = 23887          # ۲۳٬۸۷۵ + ۱۲ فیلتر
Z_LUCK = 4.07
DD_TARGET = 8.0           # آستانهٔ MAXDD_MAX_PCT
RETENTION_FLOOR = 0.88    # مرزِ مطلقِ قیدِ توان (اگر آلفا ثابت بماند)


# ─────────────────── اندیکاتورهای فیلتر — دوره‌های غیررند ───────────────────
def _atr(df, p):
    h, l, c = (df['high'].astype(float), df['low'].astype(float),
               df['close'].astype(float))
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def _er(df, p):
    """کاراییِ روندِ کافمن: |تغییرِ خالص| / مجموعِ تغییرهای مطلق."""
    c = df['close'].astype(float)
    net = (c - c.shift(p)).abs()
    vol = c.diff().abs().rolling(p).sum()
    return net / vol.replace(0.0, np.nan)


def _adx(df, p):
    h, l, c = (df['high'].astype(float), df['low'].astype(float),
               df['close'].astype(float))
    up, dn = h.diff(), -l.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1.0 / p, adjust=False).mean()
    pdi = 100.0 * pd.Series(plus, index=df.index).ewm(
        alpha=1.0 / p, adjust=False).mean() / atr_.replace(0.0, np.nan)
    mdi = 100.0 * pd.Series(minus, index=df.index).ewm(
        alpha=1.0 / p, adjust=False).mean() / atr_.replace(0.0, np.nan)
    dx = 100.0 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / p, adjust=False).mean()


def build_filters(df):
    """۱۲ فیلترِ تک‌شرطی + شاهدِ بی‌فیلتر. خروجی: list[(name, bool-array)]."""
    n = len(df)
    ones = np.ones(n, dtype=bool)
    vr = (_atr(df, 14) / _atr(df, 96).replace(0.0, np.nan)).to_numpy()
    er = _er(df, 21).to_numpy()
    ad = _adx(df, 17).to_numpy()
    hr = df['dt'].dt.hour.to_numpy()

    def ok(a):
        return np.nan_to_num(a, nan=-1e18)

    out = [('none', ones)]
    # H-A رژیمِ نوسان
    for t in (0.85, 0.95, 1.15):
        out.append((f'volratio_14_96_lt_{t}', ok(-vr) > -t))
    # H-B کاراییِ روند
    for t in (0.17, 0.27, 0.38):
        out.append((f'er21_gt_{t}', ok(er) > t))
    # H-B' قدرتِ روند
    for t in (14, 23, 31):
        out.append((f'adx17_gt_{t}', ok(ad) > t))
    # H-C ساعتِ ورود
    out.append(('hour_london_ny', (hr >= 7) & (hr <= 20)))
    out.append(('hour_no_asia', (hr >= 6)))
    out.append(('hour_no_lastbar', (hr >= 7) & (hr <= 17)))
    return out


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_cell(L, NM, df, sig_base, fname, fmask, atr_med, ps, span, n_base):
    sig = np.asarray(sig_base).astype(bool) & np.asarray(fmask).astype(bool)
    n_sig = int(sig.sum())
    sl_abs = atr_med * SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * RR

    tr = L.simulate_trades(df, pd.Series(sig, index=df.index),
                           sl_abs, RR, True, ps)
    n = len(tr)
    base = dict(card=CARD, rule=RULE, filt=fname, sl_k=SL_K, rr=RR,
                span_years=round(span, 2), n_signals=n_sig, n_trades=n,
                retention=round(n / n_base, 4) if n_base else None,
                sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                cost_share_pct=round(100.0 * COST_PIP / sl_pip, 2))
    if n < 300:
        base['verdict'] = 'TOO_FEW_TRADES'
        return base

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())

    # ── مدلِ صفر — روی **همان زیرمجموعهٔ فیلترشده** (نکتهٔ صحتِ §۶) ──────
    _bk = L.RR
    try:
        L.RR = RR
        # خریدارِ کور: ورود در هر کندلِ **مجاز به فیلتر** ⇒ df محدود‌شده
        sub = df.loc[np.asarray(fmask).astype(bool)].reset_index(drop=True)
        unc = max(NM.uncond_baseline(L, sub, sl_abs, ps, s)[0] or -1e9
                  for s in STRIDES)
        perm = NM.perm_baseline(L, sub, sl_abs, ps, n_sig,
                                k=K_PERM, seed=SEED)
    finally:
        L.RR = _bk

    null = {'long': dict(uncond_wr=unc, perm_mean=perm['mean'],
                         perm_sd=perm['sd'], perm_max=perm['max'],
                         perm_k=perm['k']),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}

    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=df['time'].to_numpy(),
                         close=df['close'].to_numpy(float),
                         null=null, n_trials=N_TRIALS,
                         split_bar=int(0.70 * len(df)))
    g = res.get('gates') or {}
    base.update(
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        per_year=round(n / span, 1), avg_held_bars=round(held, 1),
        uncond_wr=round(unc, 2), alpha=round(wr - unc, 2),
        perm_mean=round(perm['mean'], 2), perm_sd=round(perm['sd'], 2),
        perm_max=round(perm['max'], 2),
        gap_to_perm_max=round(wr - perm['max'], 2),
        pf=res.get('profit_factor'), rqs2=res.get('rqs2_score'),
        verdict=res.get('verdict'), gates=g,
        n_gates_fail=sum(1 for v in g.values() if v is False),
        failed_gates=sorted(k for k, v in g.items() if v is False))
    # متریک‌ها در سطحِ ریشه یا زیرِ metrics — هر دو خوانده می‌شود
    m = res.get('metrics') or res
    for k in ('profit_factor', 'net_profit', 'skill_z', 'max_dd_pct',
              'expectancy_pip', 'max_consec_losses'):
        base[k] = m.get(k) if isinstance(m, dict) else None
    return base


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    bank = dict(RB.build_rules())

    print(f'S391 dd-filter | {RULE} @ {CARD} | LOCKED sl_k={SL_K} rr={RR}')
    print(f'n_trials={N_TRIALS} z_luck={Z_LUCK} K={K_PERM} '
          f'dd_target<={DD_TARGET} retention_floor={RETENTION_FLOOR}')
    print()

    df = L.load(CARD)
    ps = L.pip_size(ASSET)
    atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    sig_base = np.asarray(bank[RULE](df)).astype(bool)

    filters = build_filters(df)
    print(f'bars={len(df)} span={span:.2f}y raw_signals={int(sig_base.sum())} '
          f'filters={len(filters)}')
    print()
    print('%-22s %6s %6s %6s %6s %7s %6s %7s %6s %6s %6s %6s %s' % (
        'filter', 'n', 'keep', '/yr', 'wr', 'lift', 'unc', 'alpha',
        'pmax', 'pf', 'dd', 'z', 'fails'))
    print('-' * 128)

    n_base = None
    for fname, fmask in filters:
        fn = os.path.join(OUT, f'{fname}.json')
        if os.path.exists(fn):
            r = json.load(open(fn))
        else:
            r = run_cell(L, NM, df, sig_base, fname, fmask,
                         atr_med, ps, span, n_base or 1285)
            json.dump(r, open(fn, 'w'), indent=1)
        if fname == 'none':
            n_base = r['n_trades']
        if r.get('verdict') == 'TOO_FEW_TRADES':
            print('%-22s %6d TOO_FEW' % (fname, r['n_trades']))
            continue
        print('%-22s %6d %6.3f %6.1f %6.2f %+7.2f %6.2f %+7.2f %6.2f '
              '%6.3f %6.2f %6.2f %s' % (
                  fname, r['n_trades'], r['retention'] or 0, r['per_year'],
                  r['wr'], r['lift'], r['uncond_wr'], r['alpha'],
                  r['perm_max'], r.get('profit_factor') or 0,
                  r.get('max_dd_pct') or 0, r.get('skill_z') or 0,
                  ','.join(r['failed_gates']) or 'ACCEPT'))
    print()
    print('done.')


if __name__ == '__main__':
    main()
