# -*- coding: utf-8 -*-
"""
s580_adjudicate.py — داورِ `S580`: بازآزماییِ لایهٔ منجمدِ `S334` (MR-SHORT)
روی دادهٔ کاملِ ۱۵.۶ ساله. پیش‌ثبت: `results/S580_PREREG_MRSHORT_XAUUSD_VIRGIN_HOLDOUT.md`

بازوها (نه بیشتر):
  A  فقط بخشِ بکر  time < 1695076500  (2011-01-03 → 2023-09-18) — تأییدِ hold-out
  B  کلِ ۱۵.۶ سال — داوریِ رسمیِ کارتِ XAUUSD-M5

گاردهای ارثی (هر یک با نامِ باگِ مولدش):
  ① BUG-PERMK      — perm_k = pa.size نه اندازهٔ نمونه.
  ② BUG-NULLUNCOND — نالِ هر بازو با دادهٔ **همان بازو** و هندسهٔ همان بازو.
  ③ BUG-SCOREKEY   — نگاشتِ خروجی عیناً از s437_adjudicate.py؛ کلیدِ درست rqs2_score.
  ④ BUG-ZBARNEST   — z_luck_bound از res['metrics'] خوانده می‌شود نه سطحِ بالا.
  ⑤ BUG-PIPGUESS   — pip از موتور خوانده می‌شود (ASSETS)، حدس زده نمی‌شود.
  ⑥ قیدِ ۲          — n<30 ⇒ MEASUREMENT-LIMITED، نه حکم.
  ⑦ BUG-GEOMDRIFT  — کانفیگ از آرتیفکتِ رسمی results/_s334_XAUUSD_M5.json **خوانده**
                     می‌شود؛ هیچ عددی اینجا بازنویسی نمی‌شود.
  ⑧ BUG-DATASETDRIFT — منبعِ داده (src/rows/span) با هر نتیجه چاپ و ذخیره می‌شود.
  ⑨ نکتهٔ نو (شکارشده هنگامِ خواندنِ رابط): این لایه SHORT است ⇒ ماسک‌های نال به
     آرگومانِ short_sig موتور می‌روند و دیکشنریِ نال در کلیدِ 'short' پر می‌شود.
     کپیِ کورکورانهٔ نسخهٔ long از S437 = باگِ جدید.

منطقِ سیگنال import می‌شود (strategies/s334_mr_short_revival) — بازنویسی ممنوع.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time as _time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'strategies'), os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                       # noqa: E402
from engine import indicator_bank as ib                     # noqa: E402
from engine.rqs2 import compute_rqs2                        # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402
import strategies.s334_mr_short_revival as s334             # noqa: E402

OUT = 'results/_s580_arms'
CACHE = 'results/_s580_regime_cache'
N_TRIALS = 500        # پیش‌ثبت §۵ — سخاوتمندانه؛ ≤۵۶۶ سدِ یکسان می‌دهد
N_PERM = 500          # درسِ S435: زیرِ ۵۰۰ حکمِ H3 نوسانی است
SEED = 20260812
CUTOFF_EPOCH = 1695076500   # آغازِ دادهٔ قدیمِ S334 — مرزِ دیده/بکر (پیش‌ثبت §۳)

FROZEN = os.path.join(ROOT, 'results', '_s334_XAUUSD_M5.json')


def frozen_cfg() -> dict:
    """گاردِ ⑦ — کانفیگ فقط از آرتیفکتِ رسمی."""
    with open(FROZEN, encoding='utf-8') as f:
        j = json.load(f)
    c = j['cfg']
    assert j['asset'] == 'XAUUSD' and j['tf'] == 'M5', 'آرتیفکتِ اشتباه!'
    return dict(z_win=int(c['z_win']), z_thr=float(c['z_thr']),
                rsi_thr=float(c['rsi_thr']), h=float(c['h']), k=float(c['k']),
                sl=float(c['sl']), tp=float(c['tp']), mh=int(c['mh']))


def load_full(tf: str = 'M5'):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s')
    prov = {'src': d['src'], 'rows': int(len(df)),
            'span': f"{df['dt'].iloc[0]} → {df['dt'].iloc[-1]}"}
    print(f"  [داده] {prov['rows']:,} کندل · {prov['span']}\n  src={prov['src']}")
    # گاردِ BUG-DATASETDRIFT بر مبنای «بازهٔ زمانی» (معیارِ درست) نه تعدادِ سطر:
    # دادهٔ کوتاهِ data/ فقط ~۲.۸ سال است؛ دادهٔ کامل باید >۱۲ سال باشد.
    span_years = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    assert span_years > 12.0, \
        f'BUG-DATASETDRIFT: بازه فقط {span_years:.1f} سال — این دادهٔ کامل نیست!'
    # معیارِ حاکم همان بازهٔ زمانی است. mt5_full نسخهٔ H4 ندارد ولی
    # data/XAUUSD_H4.csv خودش کاملِ ۲۰۱۱-۲۰۲۶ است ⇒ فقط هشدار، نه توقف.
    if 'mt5_full' not in str(d['src']):
        print(f'  ⚠️ src خارج از mt5_full اما بازه {span_years:.1f} سال است '
              f'(کامل) — پذیرفته شد.')
    return df, prov


def regime_arrays(df: pd.DataFrame, tf: str = 'M5') -> dict:
    """hurst/kurt روی کلِ داده — با کشِ دیسکی (قانونِ ذره‌ذره: hurst کُند است)."""
    os.makedirs(os.path.join(ROOT, CACHE), exist_ok=True)
    key = f"XAUUSD_{tf}_n{len(df)}"
    path = os.path.join(ROOT, CACHE, f'{key}.npz')
    if os.path.exists(path):
        z = np.load(path)
        print(f'  [رژیم] از کش: {path}')
        return {'hurst': z['hurst'], 'kurt': z['kurt']}
    t0 = _time.time()
    print('  [رژیم] محاسبهٔ hurst(64) و kurt(20) روی کلِ داده — صبور باش...')
    hurst = np.nan_to_num(pd.Series(ib.compute('hurst', df)).values, nan=1.0)
    print(f'    hurst تمام شد ({_time.time()-t0:.0f}s)')
    kurt = np.nan_to_num(pd.Series(ib.compute('kurt', df)).values, nan=99.0)
    print(f'    kurt تمام شد ({_time.time()-t0:.0f}s)')
    np.savez_compressed(path, hurst=hurst, kurt=kurt)
    return {'hurst': hurst, 'kurt': kurt}


def build_mask(df: pd.DataFrame, reg: dict, cfg: dict) -> np.ndarray:
    """سیگنالِ منجمد: build_short_mr (importشده) & گیتِ رژیم."""
    base = s334.build_short_mr(df, z_win=cfg['z_win'], z_thr=cfg['z_thr'],
                               rsi_thr=cfg['rsi_thr'])
    gate = (reg['hurst'] < cfg['h']) & (reg['kurt'] < cfg['k'])
    return base & gate


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def null_for_short(df, mask, sl, tp, mh, asset='XAUUSD',
                   n_perm=N_PERM, seed=SEED):
    """مدلِ صفرِ اختصاصیِ بازو — گاردِ ② + نکتهٔ ⑨ (سمتِ SHORT).

    ساختار عیناً از tools/s437_adjudicate.py::null_for، با دو تغییرِ آگاهانه:
    ماسک‌ها به short_sig می‌روند و خروجی در کلیدِ 'short' می‌نشیند.
    """
    n = len(df)
    z = np.zeros(n, bool)
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)

    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool)
    um[pick] = True
    tu = se.simulate_trades(df, z, um, sl, tp, asset, max_hold=mh,
                            allow_overlap=True)
    wr_unc = _wr(tu)

    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, z, pm, sl, tp, asset, max_hold=mh,
                               allow_overlap=False)
        w = _wr(t)
        if w is not None:
            perm.append(w)
    pa = np.array(perm, float) if perm else np.array([])
    return {'short': dict(uncond_wr=wr_unc,
                          perm_mean=float(pa.mean()) if pa.size else None,
                          perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                          perm_max=float(pa.max()) if pa.size else None,
                          perm_k=int(pa.size)),     # گاردِ ① BUG-PERMK
            'long': {}}


def adjudicate(df, mask, label, cfg, card, prov, oos_frac=0.30):
    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, z, mask, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 30:                  # گاردِ ⑥
        return {'arm': label, 'card': card, 'provenance': prov,
                'error': f'n<30 (n={0 if tr is None else len(tr)})',
                'invalid': True, 'n_signals': int(mask.sum())}

    null = null_for_short(df, mask, sl, tp, mh)
    split_bar = int(len(df) * (1.0 - oos_frac))
    res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)
    g = res.get('gates') or {}
    m = res.get('metrics') or {}
    return {                                         # گاردِ ③
        'arm': label,
        'card': card,
        'provenance': prov,
        'frozen_cfg': cfg,
        'geometry': {'sl_pip': sl, 'tp_pip': tp, 'max_hold': mh,
                     'rr': round(tp / sl, 3)},
        'n_signals': int(mask.sum()),
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': sorted(k for k, v in g.items() if v is False),
        'unknown_gates': sorted(k for k, v in g.items() if v is None),
        'null': null['short'],
        'n_trials': N_TRIALS,
        'z_luck_bound': m.get('z_luck_bound'),       # گاردِ ④ — از metrics
        'z_margin': m.get('z_margin'),
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share',
            'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm',
            'p_emp', 'p_adj_bonferroni', 'perm_k', 'perm_max')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }


def median_atr_pip(df) -> float:
    atr = pd.Series(ib.atr_s(df, 14))
    pip = se.ASSETS['XAUUSD']['pip']            # گاردِ ⑤ — از موتور
    return float(atr.median()) / pip


def run_c_arm(tf: str, cfg: dict, ratio_sl: float, ratio_tp: float):
    """بازوی C — پیش‌ثبت §۴: هندسه = مضرب‌های M5 × medianATR14(TF)ِ همان TF.
    منطق و آستانه‌های رژیم ثابت. هیچ جاروبی. یک آزمون به‌ازای هر TF."""
    import gc
    print(f'\n  ── C[{tf}] ──')
    df, prov = load_full(tf)
    med = median_atr_pip(df)
    sl = round(ratio_sl * med, 1)
    tp = round(ratio_tp * med, 1)
    ccfg = dict(cfg, sl=sl, tp=tp)
    print(f'  medianATR14={med:.1f} pip ⇒ SL={sl}/TP={tp} (نسبت‌های منجمدِ M5)')
    # رژیمِ M1 پنج میلیون float64 است (۲×40MB) — بلافاصله به بولینِ ۵MB
    # فروکاسته و آزاد می‌شود؛ سپس ستون‌های زائد (dt/volume) حذف می‌شوند تا
    # پیکِ ساختِ سیگنال در سندباکسِ ~1GB جا شود. تغییرِ زیرساختی، نه روشی —
    # gate دقیقاً همان (hurst<h)&(kurt<k) منجمد است.
    reg = regime_arrays(df, tf)
    gate = (reg['hurst'] < ccfg['h']) & (reg['kurt'] < ccfg['k'])
    del reg
    keep = [c for c in ('time', 'open', 'high', 'low', 'close') if c in df.columns]
    df = df[keep]
    gc.collect()
    base = s334.build_short_mr(df, z_win=ccfg['z_win'], z_thr=ccfg['z_thr'],
                               rsi_thr=ccfg['rsi_thr'])
    gc.collect()
    mask = base & gate
    del base, gate
    print(f'  سیگنال={int(mask.sum())}')
    out = adjudicate(df, mask, f'C-{tf}', ccfg, f'XAUUSD-{tf}',
                     dict(prov, geometry_rule=f'SL={ratio_sl:.4f}·medATR '
                          f'TP={ratio_tp:.4f}·medATR، medATR={med:.1f}pip'))
    path = os.path.join(ROOT, OUT, f'arm_C_{tf}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    if out.get('invalid'):
        print(f'  ⛔ C[{tf}] نامعتبر: {out["error"]} (سیگنال={out.get("n_signals")})')
    else:
        m = out['metrics']
        print(f'  C[{tf}] n={m["n_trades"]} WR={m["win_rate"]} '
              f'lift={m["skill_lift_pp"]} z={m["skill_z"]} '
              f'PF={m["profit_factor"]} net=${m["net_profit"]} '
              f'RQS2={out.get("rqs2_score")} {out.get("verdict")} '
              f'شکسته={out.get("failed_gates")}')
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='A,B',
                    help='A=بکر، B=کامل، C:TF (مثل C:M15) = بازوی MTF')
    a = ap.parse_args()

    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    cfg = frozen_cfg()
    print(f'[S580 داوری] کانفیگِ منجمد از {os.path.basename(FROZEN)}: {cfg}')
    print(f'  n_trials={N_TRIALS} · {N_PERM} جای‌گشت/بازو · seed={SEED}')

    arm_list = [x.strip().upper() for x in a.arms.split(',') if x.strip()]
    c_tfs = [x.split(':', 1)[1] for x in arm_list if x.startswith('C:')]
    arm_list = [x for x in arm_list if not x.startswith('C:')]

    if c_tfs:
        # نسبت‌های منجمدِ هندسه از خودِ M5 (پیش‌ثبت §۴) — یک‌بار محاسبه
        df5, _ = load_full('M5')
        med5 = median_atr_pip(df5)
        ratio_sl, ratio_tp = cfg['sl'] / med5, cfg['tp'] / med5
        print(f'  [C] medianATR14(M5)={med5:.1f} pip ⇒ '
              f'ratio_sl={ratio_sl:.4f} ratio_tp={ratio_tp:.4f}')
        del df5
        for tf in c_tfs:
            run_c_arm(tf, cfg, ratio_sl, ratio_tp)
        if not arm_list:
            print('[done]')
            return 0

    df, prov = load_full('M5')
    reg = regime_arrays(df, 'M5')
    mask_full = build_mask(df, reg, cfg)
    cut = int(np.searchsorted(df['time'].to_numpy(), CUTOFF_EPOCH))
    print(f'  مرزِ بکر/دیده: اندیسِ {cut:,} از {len(df):,} '
          f'({df["dt"].iloc[cut]})')
    print(f'  سیگنالِ کل={int(mask_full.sum())} · '
          f'بکر={int(mask_full[:cut].sum())} · '
          f'دیده={int(mask_full[cut:].sum())}')

    for arm in arm_list:
        t0 = _time.time()
        if arm == 'A':
            dfa = df.iloc[:cut].reset_index(drop=True)
            ma = mask_full[:cut].copy()
            pa = dict(prov, slice=f'virgin rows 0..{cut} '
                      f'({dfa["dt"].iloc[0]} → {dfa["dt"].iloc[-1]})')
            card = 'XAUUSD-M5-VIRGIN(2011-2023)'
        elif arm == 'B':
            dfa, ma, pa, card = df, mask_full, dict(prov, slice='full'), 'XAUUSD-M5'
        else:
            print(f'  ⛔ بازوی ناشناخته: {arm}')
            continue
        print(f'  [{arm}] {card} · سیگنال={int(ma.sum())} — داوری...')
        out = adjudicate(dfa, ma, arm, cfg, card, pa)
        path = os.path.join(ROOT, OUT, f'arm_{arm}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=float)
        if out.get('invalid'):
            print(f'  ⛔ [{arm}] نامعتبر: {out["error"]} '
                  f'(سیگنال={out.get("n_signals")}) [{_time.time()-t0:.0f}s]')
            continue
        m = out['metrics']
        print(f'  [{arm}] n={m["n_trades"]} WR={m["win_rate"]} '
              f'lift={m["skill_lift_pp"]} z={m["skill_z"]} '
              f'bar={out.get("z_luck_bound")} PF={m["profit_factor"]} '
              f'net=${m["net_profit"]} RQS2={out.get("rqs2_score")} '
              f'{out.get("verdict")} [{_time.time()-t0:.0f}s]')
        print(f'        شکسته={out.get("failed_gates")} '
              f'نامعلوم={out.get("unknown_gates")}')

    print('[done]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
