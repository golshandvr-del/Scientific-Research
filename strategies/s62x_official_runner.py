#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S62x — رانر رسمی احکام بلوک S620–S629 (اقلیدس)
PREREG-2: results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md (commit 31bc0c61)

usage: python3 strategies/s62x_official_runner.py s624
هر لایه: سیگنال منجمد روی کل داده | null هندسه‌پوش و گیت‌شرطی (stride-hardest + perm K=500)
| یک فراخوان compute_rqs2 با split_bar=n_full//2 و n_trials صادقانه | حکم موتور = کلمهٔ نهایی | MD خودکار.
"""
import sys, os, json, gc, time
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs2 as R

PIP = 0.10
PERM_K = 500
PERM_CAP = 2000          # سقف تعداد ورود در هر قرعهٔ null (RAM) — محافظه‌کارانه (sd بزرگ‌تر)
STRIDES = (3, 7, 13)

CFG = {
 's620': dict(name='LaguerreExit',          tf='M1', side='both',  k=2.0,  rr=1.0, mh=240, nt=3672, seed=620620),
 's621': dict(name='LaguerreMtfShort',      tf='H3', side='short', k=1.5,  rr=1.5, mh=64,  nt=193,  seed=621621),
 's622': dict(name='RoundNumberRejection',  tf='M1', side='both',  k=1.5,  rr=1.0, mh=240, nt=192,  seed=622622),
 's623': dict(name='RoundRejectionCoarse',  tf='M1', side='long',  k=16.0, rr=1.5, mh=960, nt=48,   seed=623623),
 's624': dict(name='EmaPullbackLong',       tf='H2', side='long',  k=2.0,  rr=1.0, mh=64,  nt=49,   seed=624624),
 's625': dict(name='WickDominanceLong',     tf='M5', side='long',  k=2.0,  rr=1.0, mh=240, nt=24,   seed=625625),
 's626': dict(name='RoundNativeDriftLong',  tf='H1', side='long',  k=1.5,  rr=1.5, mh=96,  nt=49,   seed=626626),
 's627': dict(name='DriftResumptionCross',  tf='H2', side='long',  k=2.0,  rr=1.0, mh=64,  nt=13,   seed=627627),
 's628': dict(name='RollingSupportHold',    tf='H2', side='long',  k=1.5,  rr=1.5, mh=64,  nt=25,   seed=628628),
 's629': dict(name='FreshHighContinuation', tf='H6', side='long',  k=2.0,  rr=1.5, mh=56,  nt=13,   seed=629629),
}

layer = sys.argv[1]
cfg = CFG[layer]
TF, SIDE, K, RR, MH, NT, SEED = (cfg[x] for x in ('tf', 'side', 'k', 'rr', 'mh', 'nt', 'seed'))
t0 = time.time()

d = fd.load_fast('XAUUSD', TF)
for _k in ('hour', 'minute', 'dow'):
    d.pop(_k, None)                      # RAM: ستون‌های مشتق لازم نیستند
df = fd.as_dataframe(d)
n = len(df); half = n // 2
op = df['open'].values; hi = df['high'].values; lo = df['low'].values; cl = df['close'].values  # ارجاع، بی‌کپی


def atr_lowmem(p=100):
    """بیت‌به‌بیت برابر `ib.atr_s(df,p)` (تأیید: max|diff|=0 روی H1) ولی بدونِ pd.concat
    سه‌ستونیِ M1 که ۳۷۰MB می‌گرفت و سندباکس ۱GB را می‌کشت (دو بار Killed)."""
    tr_ = hi - lo
    pc = np.empty(n); pc[0] = np.nan; pc[1:] = cl[:-1]
    np.maximum(tr_, np.abs(hi - pc), out=tr_); np.maximum(tr_, np.abs(lo - pc), out=tr_)
    tr_[0] = hi[0] - lo[0]
    del pc
    return pd.Series(tr_).ewm(alpha=1.0 / p, adjust=False).mean().values


atr_price = atr_lowmem(100)               # واحد قیمت (دلار) — ADDENDUM-1
atr_pip = atr_price / PIP                 # pip = ×10
gc.collect()
valid = np.isfinite(atr_pip) & (atr_pip > 0)
valid[:101] = False
print(f'[{layer}] {cfg["name"]} TF={TF} src={d["src"]} n_full={n} split_bar={half} mh={MH} k={K} rr={RR}', flush=True)


def drift90():
    g = np.zeros(n, bool)
    g[90:] = cl[89:n - 1] > cl[:n - 90]
    return g


def _lag_rsi_lowmem(xv, g):
    """بیت‌به‌بیت برابر `ib.laguerre_rsi` (همان ترتیب عمل‌ها، بی fastmath؛ تأیید روی H1:
    max|diff|=0) ولی تک‌گذر و بی‌آرایه‌های میانیِ L0..L3/cu/cd که روی M1 ~۴۰۰MB می‌شد."""
    try:
        from numba import njit
    except ImportError:            # fallback: مسیر رسمی بانک اندیکاتور
        return None
    @njit(cache=False)
    def _k(xv, g):
        n = len(xv); out = np.empty(n)
        L0 = L1 = L2 = L3 = 0.0
        for i in range(n):
            pL0, pL1, pL2 = L0, L1, L2
            L0 = (1 - g) * xv[i] + g * L0
            L1 = -g * L0 + pL0 + g * L1
            L2 = -g * L1 + pL1 + g * L2
            L3 = -g * L2 + pL2 + g * L3
            cu = 0.0; cd = 0.0
            for a, b in ((L0, L1), (L1, L2), (L2, L3)):
                if a >= b: cu += a - b
                else: cd += b - a
            tot = cu + cd
            out[i] = 100 * cu / tot if tot != 0 else 50.0
        return out
    return _k(xv, g)


def lag_edge(gamma, th):
    lag = _lag_rsi_lowmem(cl, gamma)
    if lag is None:
        lag = ib.laguerre_rsi(df, gamma).values
    long_raw = np.zeros(n, bool); short_raw = np.zeros(n, bool)
    long_raw[1:] = (lag[:-1] < th) & (lag[1:] >= th)
    short_raw[1:] = (lag[:-1] > 100.0 - th) & (lag[1:] <= 100.0 - th)
    del lag; gc.collect()
    return long_raw, short_raw


def round_reject(G, q):
    tau = q * atr_price
    r_lo = np.round(lo / G) * G; r_hi = np.round(hi / G) * G
    lr = (np.abs(lo - r_lo) <= tau) & (cl > r_lo + tau)
    sr = (np.abs(hi - r_hi) <= tau) & (cl < r_hi - tau)
    return lr, sr


long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)
gate = valid.copy()

if layer == 's620':
    lr, sr = lag_edge(0.4, 10.0)
    long_sig = lr & valid; short_sig = sr & valid
elif layer == 's621':
    # conf: LagRSI(0.5) روی D1، مقدار آخرین کندل D1 که قبل از زمان کندل H3 بسته شده
    cd = fd.load_fast('XAUUSD', 'D1'); cdf = fd.as_dataframe(cd)
    clag = ib.laguerre_rsi(cdf, 0.5).values
    closes = cdf['time'].values.astype(np.int64) + 24 * 3600
    idx = np.searchsorted(closes, df['time'].values.astype(np.int64), side='right') - 1
    conf = np.full(n, np.nan); ok = idx >= 0; conf[ok] = clag[idx[ok]]
    gate = valid & np.isfinite(conf) & (conf >= 70.0)
    _, sr = lag_edge(0.4, 20.0)
    short_sig = sr & gate
elif layer == 's622':
    lr, sr = round_reject(10.0, 0.2)
    long_sig = lr & valid; short_sig = sr & valid
elif layer == 's623':
    lr, _ = round_reject(10.0, 0.2)
    long_sig = lr & valid
elif layer == 's624':
    ema = df['close'].ewm(span=89, adjust=False).mean().values
    above_prev = np.zeros(n, bool); above_prev[1:] = lo[:-1] > ema[:-1]
    long_sig = above_prev & (lo <= ema) & (cl > ema) & valid
elif layer == 's625':
    body = np.abs(cl - op); rng_ = hi - lo; wick_lo = np.minimum(op, cl) - lo; mid = (hi + lo) / 2.0
    gate = valid & (rng_ > 0)
    long_sig = (wick_lo >= 2.0 * body) & (wick_lo >= 0.6 * rng_) & (cl > mid) & gate
elif layer == 's626':
    dr = drift90(); gate = valid & dr
    tau = 0.1 * atr_price; Rn = np.round(lo / 50.0) * 50.0
    long_sig = gate & (np.abs(lo - Rn) <= tau) & (cl > Rn + tau)
elif layer == 's627':
    fast = np.full(n, np.nan); fast[91:] = cl[90:n - 1] - cl[:n - 91]
    slow = np.full(n, np.nan); slow[361:] = cl[360:n - 1] - cl[:n - 361]
    prev_fast = np.full(n, np.nan); prev_fast[1:] = fast[:-1]
    v2 = valid & np.isfinite(slow) & np.isfinite(fast)
    gate = v2 & (slow > 0) & (fast > 0)
    long_sig = gate & (prev_fast <= 0)
elif layer == 's628':
    dr = drift90()
    lmin = pd.Series(lo).rolling(55).min().shift(1).values
    v2 = valid & np.isfinite(lmin); v2[:57] = False
    gate = v2 & dr
    tau = 0.2 * atr_price
    long_sig = gate & (lo >= lmin) & (lo <= lmin + tau) & (cl > lmin + tau)
elif layer == 's629':
    dr = drift90()
    hmax = pd.Series(hi).rolling(55).max().shift(1).values
    v2 = valid & np.isfinite(hmax); v2[:92] = False
    gate = v2 & dr
    above = cl > hmax; prev_above = np.zeros(n, bool); prev_above[1:] = above[:-1]
    long_sig = gate & above & ~prev_above

# ورود در کندل بعد ⇒ مانند اسکن، کندل‌های انتهایی بی‌اعتبار
tail = max(0, n - MH - 2)
long_sig[tail:] = False; short_sig[tail:] = False; gate[tail:] = False

sl_arr = K * atr_pip; tp_arr = RR * sl_arr
n_sig = int(long_sig.sum() + short_sig.sum())
print(f'[{layer}] signals long={int(long_sig.sum())} short={int(short_sig.sum())} gate_bars={int(gate.sum())}', flush=True)

MAIN_CHUNK = 250_000


def simulate_exact_chunked(ls, ss):
    """معادلِ دقیقِ `se.simulate_trades(...)` روی کل داده، ولی قطعه‌ای برای RAM.
    بیت‌به‌بیت: busy_until بین قطعه‌ها حمل می‌شود (سیگنال‌های درون بازهٔ اشغالِ آخرین
    معاملهٔ قطعهٔ قبل حذف)، هر قطعه MH+2 کندلِ سرریز برای خروج دارد، و اندیس‌ها به
    مختصات کامل برگردانده می‌شوند. برای n≤1.5M همان تماسِ مستقیم موتور."""
    if n <= 1_500_000:
        return se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD', max_hold=MH, allow_overlap=False)
    parts = []; busy_until = -1
    for a in range(0, n, MAIN_CHUNK):
        core = min(MAIN_CHUNK, n - a); b = min(n, a + core + MH + 2)
        l2 = ls[a:b].copy(); s2 = ss[a:b].copy(); l2[core:] = False; s2[core:] = False
        # حذف سیگنال‌هایی که کندل ورودشان (si+1) هنوز در اشغالِ معاملهٔ قطعهٔ قبل است
        cut = busy_until - a          # آخرین اندیسِ محلیِ اشغال‌شده (entry_bar ≤ cut ⇒ رد)
        if cut >= 0:
            l2[:min(cut, core)] = False; s2[:min(cut, core)] = False
        if l2.any() or s2.any():
            t = se.simulate_trades(df.iloc[a:b].reset_index(drop=True), l2, s2, sl_arr[a:b], tp_arr[a:b],
                                   'XAUUSD', max_hold=MH, allow_overlap=False)
            if len(t):
                for col in ('signal_bar', 'entry_bar', 'exit_bar'):
                    t[col] = t[col] + a
                busy_until = int(t['exit_bar'].iloc[-1])
                parts.append(t)
        del l2, s2; gc.collect()
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


tr = simulate_exact_chunked(long_sig, short_sig)
ntr = len(tr); wr = 100 * float((tr['outcome'] == 'win').mean()) if ntr else 0.0
exp_pip = float(tr['pnl_pip'].mean()) if ntr else 0.0
print(f'[{layer}] trades n={ntr} WR={wr:.2f}% exp={exp_pip:+.3f} pip ({time.time()-t0:.0f}s)', flush=True)


def wr_side(t, side):
    t2 = t[t['direction'] == side]
    return (100 * float((t2['outcome'] == 'win').mean()) if len(t2) else None), int(len(t2))


sides = [s for s in ('long', 'short') if (long_sig if s == 'long' else short_sig).any()]
n_side = {s: int((long_sig if s == 'long' else short_sig).sum()) for s in sides}

# ---- null ①: سخت‌ترین stride درون گیت، هر سمت ----
# RAM (S622 سندباکس را دو بار فریز کرد): stride=3 روی M1 ≈ ۱.۶M سیگنال ⇒ موتور لیستِ
# دیکشنریِ صدها هزار معامله می‌سازد (>600MB). برای n>1.5M، شبیه‌سازی قطعه‌ای (CHUNK بار
# + MH+2 بار سرریز برای خروج). انحراف: busy_until در ابتدای هر قطعه صفر می‌شود ⇒ حداکثر
# یک هم‌پوشانی اضافه در هر مرز قطعه (≈ n/CHUNK معامله از صدها هزار) — بی‌اثر روی WR.
STRIDE_CHUNK = 400_000


def stride_wr(ls, ss):
    """WR هر سمت (درصد) برای سیگنال‌های stride؛ قطعه‌ای اگر داده بزرگ باشد."""
    if n <= 1_500_000:
        t = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD', max_hold=MH, allow_overlap=False)
        out = {s: wr_side(t, s)[0] for s in sides}
        del t; return out
    cnt = {s: [0, 0] for s in sides}   # [wins, total]
    for a in range(0, n, STRIDE_CHUNK):
        core = min(STRIDE_CHUNK, n - a); b = min(n, a + core + MH + 2)
        l2 = ls[a:b].copy(); s2 = ss[a:b].copy(); l2[core:] = False; s2[core:] = False
        if not (l2.any() or s2.any()): continue
        t = se.simulate_trades(df.iloc[a:b].reset_index(drop=True), l2, s2, sl_arr[a:b], tp_arr[a:b],
                               'XAUUSD', max_hold=MH, allow_overlap=False)
        for s in sides:
            t2 = t[t['direction'] == s]
            cnt[s][0] += int((t2['outcome'] == 'win').sum()); cnt[s][1] += int(len(t2))
        del t, l2, s2; gc.collect()
    return {s: (100.0 * c[0] / c[1] if c[1] else None) for s, c in cnt.items()}


uncond = {s: [] for s in sides}
for st in STRIDES:
    b = np.zeros(n, bool); b[::st] = True; b &= gate
    for s in sides:
        # هر سمت جدا: موتور در تلاقی long|short، long را مقدم می‌گیرد؛ اگر هر دو سمت
        # همان b باشند، سمت short هیچ معامله‌ای نمی‌گیرد (نقص نسخهٔ قبلی برای side=both).
        ls = b if s == 'long' else np.zeros(n, bool)
        ss = b if s == 'short' else np.zeros(n, bool)
        w = stride_wr(ls, ss)
        if w[s] is not None: uncond[s].append(w[s])
        print(f'[{layer}] stride {st} {s}={w[s]} ({time.time()-t0:.0f}s)', flush=True)
        del ls, ss; gc.collect()
    del b
print(f'[{layer}] stride-uncond per side: ' + ' '.join(f'{s}=max{max(v):.2f}' for s, v in uncond.items()), flush=True)

# ---- null ②: جای‌گشت درون گیت K=500 با همان تعداد سیگنال (سقف PERM_CAP) ----
def _rss_mb():
    try: return int(open('/proc/self/statm').read().split()[1]) * 4 // 1024
    except Exception: return -1
print(f'[{layer}] RSS before perm: {_rss_mb()} MB', flush=True)
rs = np.random.RandomState(SEED)
pool = np.where(gate)[0]
perm = {s: [] for s in sides}
for kk in range(PERM_K):
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    for s in sides:
        m = min(n_side[s], PERM_CAP, len(pool))
        # بی‌جای‌گذاری، ولی بدونِ permutation کاملِ pool (روی M1: ۵M×int64 ×۲ در هر قرعه ⇒ OOM S620)
        pick = np.unique(rs.randint(0, len(pool), size=int(m * 1.02) + 16))
        rs.shuffle(pick); pick = pool[pick[:m]]
        (ls if s == 'long' else ss)[pick] = True
    t = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD', max_hold=MH, allow_overlap=False)
    for s in sides:
        w, _ = wr_side(t, s)
        if w is not None: perm[s].append(w)
    del t, ls, ss
    if kk % 100 == 99:
        gc.collect(); print(f'[{layer}] perm {kk+1}/{PERM_K} ({time.time()-t0:.0f}s) RSS={_rss_mb()}MB', flush=True)

null = {}
for s in sides:
    a = np.array(perm[s])
    null[s] = dict(uncond_wr=float(max(uncond[s])), perm_mean=float(a.mean()),
                   perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()), perm_k=int(len(a)))
    print(f'[{layer}] null[{s}]: uncond={null[s]["uncond_wr"]:.2f} perm_mean={a.mean():.2f} sd={a.std(ddof=1):.2f} max={a.max():.2f} k={len(a)}', flush=True)

OUTD = os.path.join(ROOT, 'results', f'_official_{layer.upper()}')
os.makedirs(OUTD, exist_ok=True)
json.dump(dict(null=null, perm_cap=PERM_CAP, n_side=n_side, seed=SEED), open(os.path.join(OUTD, 'null_model.json'), 'w'), indent=1)

# موتور SL/TP اسکالر می‌خواهد؛ SL متغیر (k×ATR) ⇒ نمایندهٔ صادق = میانهٔ SL معاملات واقعی
# (همان fallback داخلی موتور، خط 907) و TP = RR×همان ⇒ نسبت RR بیت‌به‌بیت درست ⇒ H2 صحیح.
sl_rep = float(np.median(tr['sl_pip'].values)) if ntr else float(np.nanmedian(sl_arr))
tp_rep = RR * sl_rep
print(f'[{layer}] representative SL={sl_rep:.1f} TP={tp_rep:.1f} pip (median of realised)', flush=True)
res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_rep, tp_pip=tp_rep, bar_time=df['time'], close=df['close'],
                     null=null, n_trials=NT, split_bar=half)
json.dump(res, open(os.path.join(OUTD, f'{TF}_rqs2.json'), 'w'), indent=1, default=str)
tr.to_csv(os.path.join(OUTD, f'{TF}_trades.csv'), index=False)

g = res.get('gates', {}); m = res.get('metrics', {})
gs = ' '.join(f"H{i}:{'✓' if g.get(f'H{i}') else ('?' if g.get(f'H{i}') is None else '✗')}" for i in range(11))
verdict = res.get('verdict'); score = res.get('rqs2_score')
line = (f"{layer.upper()}_{cfg['name']}_{TF} | {verdict} RQS2={score} | n={ntr} WR={wr:.2f}% exp={exp_pip:+.2f}pip "
        f"PF={m.get('profit_factor')} lift={m.get('skill_lift_pp')}pp z={m.get('skill_z')} p_emp={m.get('p_emp')} "
        f"oos={m.get('oos')} | {gs}")
print('\n' + line, flush=True)
notes = '\n'.join(f'- {x}' for x in res.get('notes', []))

num = layer[1:]
vtag = str(verdict).split()[0].replace('(', '')
md_name = f"S{num}_{cfg['name']}_Xauusd_{TF}_rqs2_{score}_{vtag}.md"
md = f"""# S{num} — {cfg['name']} · XAUUSD-{TF} · حکم رسمی موتور: {verdict} (RQS2={score})

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61 + ADDENDUM-1 9ba370d7، قبل از اجرا) · n_trials={NT} · seed={SEED}
**پیش‌ثبت اصلی جست‌وجو:** `results/S{num}_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
{line}
```

## قاعدهٔ منجمد
سمت: {SIDE} · SL={K}×ATR100 (میانهٔ محقق‌شده {sl_rep:.1f} pip) · TP={RR}×SL · max_hold={MH} · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل ({n} کندل) · split_bar={half} (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{json.dumps(null, indent=1)}
سقف ورود هر قرعهٔ null={PERM_CAP} (محافظه‌کارانه) · K={PERM_K}

## دروازه‌ها
{gs}

## یادداشت‌های موتور
{notes}

## آرتیفکت‌ها
`results/_official_{layer.upper()}/{{{TF}_rqs2.json, {TF}_trades.csv, null_model.json}}`

— اقلیدس، بلوک S620–S629 📐
"""
open(os.path.join(ROOT, 'results', md_name), 'w').write(md)
print(f'MD -> results/{md_name}', flush=True)
