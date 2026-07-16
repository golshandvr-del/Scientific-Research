"""
استراتژی ۳۵ (طرح P02 + P41): «پرتفوی جریان‌های چند-تایم‌فریمی» (MTF Portfolio of Streams).

--------------------------------------------------------------------------------
انگیزه — تفاوت بنیادی با S33/S34:
S33/S34 نشان دادند MTF-as-feature (چسباندن اطلاعات HTF به مدل M15) سقف را نمی‌شکند،
چون همان اطلاعات M15 در رزولوشن دیگر است. اما تیم هرگز MTF-as-INDEPENDENT-STREAM را
تست نکرد: هر تایم‌فریم یک *ژنراتور سیگنال مستقل* با مدل ML خودش، تنظیم‌شده در نقطهٔ
کاری PF (که تک‌جریان WR>60/PF>1.3 می‌دهد ولی فرکانس کم).

فرضیهٔ ریاضی (هستهٔ P02):
  «تضاد WR↔فرکانس یک قانون درون-جریان است، نه بین-جریان.»
  اگر K جریان مستقل هر یک WR≥60 و ~1 معامله/روز داشته باشند، پرتفویِ dedup شدهٔ
  آن‌ها WR وزنی همان >60 را نگه می‌دارد ولی فرکانس‌ها جمع می‌شوند → شاید ≥5/روز.

  چرا MTF جریان‌های *ناهمبسته در زمان* می‌سازد؟ چون سیگنال هر TF فقط روی کندل‌های
  بسته‌شدهٔ همان TF ارزیابی می‌شود (H4 هر ۴ ساعت، H1 هر ۱ ساعت، M30 هر ۳۰ دقیقه،
  M15 هر ۱۵ دقیقه) → زمان‌بندی ورودها طبیعتاً پراکنده است.

طراحی هر جریان:
  - مدل LightGBM روی feature های *همان* تایم‌فریم (اندیکاتورهای اصیل آن TF).
  - برچسب: TP1.4×ATR قبل از SL1.7×ATR در افق آن TF (همان نقطهٔ PF برندهٔ P01).
  - Purged Walk-Forward روی سری همان TF (embargo متناسب).
  - سیگنال (کندل بستهٔ TF + proba≥thr) به زمانِ بسته‌شدن نگاشت و روی M15 با موتور
    مشترک اجرا می‌شود (ورود open کندل M15 بعدی، SL/TP بر حسب ATR همان M15).

ترکیب پرتفوی:
  - همهٔ سیگنال‌های همهٔ جریان‌ها روی محور زمان M15 ادغام؛ dedup: اگر معامله‌ای باز
    است، سیگنال جدید رد می‌شود (allow_overlap=False روی کل پرتفوی).
  - WR/PF/exp/tpd پرتفوی گزارش می‌شود.

اعتبار: open-next + spread 0.2$ + WF. float32/gc برای RAM محدود (~1GB).
"""
import sys, gc; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
import indicators as ind
from mtf import load_tf, TF_SECONDS
import warnings; warnings.filterwarnings('ignore')

SPREAD = 0.20
SEEDS = [42, 7]
N_FOLDS = 5
MIN_TRAIN_FRAC = 0.40
# نقطهٔ کاری PF برندهٔ P01 (تک‌جریان WR>60, PF>1.3):
TP_MULT, SL_MULT = 1.4, 1.7
BE = SL_MULT / (TP_MULT + SL_MULT) * 100  # break-even WR ≈ 54.8%

# ---------------------------------------------------------------------------
# ۱) داده پایه M15 (محور زمان اجرا و بک‌تست)
# ---------------------------------------------------------------------------
print("بارگذاری M15 (محور اجرا) ...", flush=True)
m15 = pd.read_csv('data/XAUUSD_M15.csv').sort_values('time').reset_index(drop=True)
m15['dt'] = pd.to_datetime(m15['time'], unit='s')
m15['open_time'] = m15['time'].astype(np.int64)
m15_o = m15['open'].values.astype(np.float64)
m15_h = m15['high'].values.astype(np.float64)
m15_l = m15['low'].values.astype(np.float64)
m15_c = m15['close'].values.astype(np.float64)
n15 = len(m15)
atr15 = ind.atr(m15, 14).values.astype(np.float64)
ema50_15 = ind.ema(m15['close'], 50).values
ema200_15 = ind.ema(m15['close'], 200).values
span_days = (m15['dt'].iloc[-1] - m15['dt'].iloc[0]).days
# بازهٔ زمانی معتبر M15 (برای محدود کردن جریان‌های HTF به همین بازه)
t_start_15 = m15['open_time'].iloc[0]
t_end_15 = m15['open_time'].iloc[-1]


# ---------------------------------------------------------------------------
# ۲) ساخت feature و برچسب برای یک تایم‌فریم دلخواه (روی سری خودش)
# ---------------------------------------------------------------------------
def tf_features(df):
    """feature های اصیل روی سری خودِ تایم‌فریم (سبک، ~30 ستون)."""
    c, h, l, o, v = df['close'], df['high'], df['low'], df['open'], df['volume']
    f = pd.DataFrame(index=df.index)
    for p in [1, 2, 3, 5, 8, 13]:
        f[f'ret_{p}'] = c.pct_change(p)
    for p in [7, 14, 21]:
        f[f'rsi_{p}'] = ind.rsi(c, p)
    macd_line, sig, hist = ind.macd(c)
    f['macd'] = macd_line; f['macd_hist'] = hist
    a = ind.atr(df, 14)
    f['atr_pct'] = a / c
    f['atr_ratio'] = a / a.rolling(50).mean()
    f['range_pct'] = (h - l) / c
    f['body_pct'] = (c - o).abs() / c
    adx_, pdi, mdi = ind.adx(df, 14)
    f['adx'] = adx_; f['di_diff'] = pdi - mdi
    lo_b, mid_b, up_b = ind.bollinger(c, 20, 2.0)
    width = (up_b - lo_b).replace(0, np.nan)
    f['bb_pos'] = (c - lo_b) / width; f['bb_width'] = width / c
    k, d = ind.stoch(df, 14, 3)
    f['stoch_k'] = k; f['stoch_d'] = d
    for p in [20, 50, 100]:
        e = ind.ema(c, p); f[f'dist_ema{p}'] = (c - e) / e
    f['slope_20'] = ind.rolling_slope(c, 20) / c
    f['zscore_20'] = ind.zscore(c, 20)
    f['zscore_50'] = ind.zscore(c, 50)
    f['vol_ratio'] = v / v.rolling(20).mean()
    rng = (h - l).replace(0, np.nan)
    f['upper_wick'] = (h - np.maximum(o, c)) / rng
    f['lower_wick'] = (np.minimum(o, c) - l) / rng
    f['close_pos'] = (c - l) / rng
    ema200 = ind.ema(c, 200)
    f['above_ema200'] = (c > ema200).astype(float)
    f['dist_ema200'] = (c - ema200) / ema200
    # زمانی
    hour = df['dt'].dt.hour; dow = df['dt'].dt.dayofweek
    f['hour'] = hour; f['dow'] = dow
    return f


def tf_label(df, tp_mult, sl_mult, horizon):
    """برچسب TP-before-SL روی سری همان TF (ورود در close، افق=horizon کندل TF)."""
    from features import _target_loop
    a = ind.atr(df, 14).values.astype(np.float64)
    return _target_loop(df['high'].values.astype(np.float64),
                        df['low'].values.astype(np.float64),
                        df['close'].values.astype(np.float64),
                        a, horizon, tp_mult, sl_mult, True)


# ---------------------------------------------------------------------------
# ۳) تولید سیگنال یک جریان TF و نگاشت به محور M15
# ---------------------------------------------------------------------------
def stream_signals_on_m15(tf_name, thr, horizon):
    """
    مدل ML روی سری TF آموزش می‌بیند (WF)، سیگنال‌ها (proba≥thr روی کندل uptrend) به
    زمان بسته‌شدن نگاشت و به نزدیک‌ترین کندل M15 که بعد از آن باز می‌شود منتقل می‌شود.
    خروجی: آرایهٔ بولین هم‌طول M15 (entries برای این جریان).
    """
    df = load_tf(tf_name)  # دارای open_time/close_time
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    # محدود به بازهٔ کمی وسیع‌تر از M15 برای warmup
    c = df['close'].values
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    atrv = ind.atr(df, 14).values
    cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atrv)

    X = tf_features(df).astype(np.float32)
    cols = list(X.columns)
    Xmat = X.values
    y = tf_label(df, TP_MULT, SL_MULT, horizon)

    ok = ~np.isnan(Xmat).any(axis=1) & ~np.isnan(y) & cand
    idx = np.where(ok)[0]
    if len(idx) < 500:
        return np.zeros(n15, dtype=bool), dict(n_tf=0)
    Xi = Xmat[idx].astype(np.float32); Yi = y[idx].astype(np.int8)
    N = len(Xi); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    emb = max(5, horizon)

    proba = np.full(len(df), np.nan)
    for seed in SEEDS:
        pr = np.full(len(df), np.nan)
        for k in range(N_FOLDS):
            tr_end = mt + k * fold
            te_start = tr_end + emb
            te_end = tr_end + fold if k < N_FOLDS - 1 else N
            if te_start >= te_end:
                continue
            m = lgb.LGBMClassifier(n_estimators=250, learning_rate=0.04, num_leaves=31,
                max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=60,
                reg_lambda=2.0, random_state=seed, verbose=-1, n_jobs=2)
            m.fit(Xi[:tr_end], Yi[:tr_end])
            pr[idx[te_start:te_end]] = m.predict_proba(Xi[te_start:te_end])[:, 1]
            del m; gc.collect()
        m2 = ~np.isnan(pr)
        proba[m2] = np.where(np.isnan(proba[m2]), pr[m2], (proba[m2] + pr[m2]) / 2)
        del pr; gc.collect()

    # سیگنال روی سری TF
    sig_tf = cand & ~np.isnan(proba) & (proba >= thr)
    sig_close_times = df['close_time'].values[sig_tf]  # زمان بسته‌شدن سیگنال‌ها

    # نگاشت به M15: برای هر close_time، اولین کندل M15 که open_time >= close_time
    m15_open = m15['open_time'].values
    entries = np.zeros(n15, dtype=bool)
    pos = np.searchsorted(m15_open, sig_close_times, side='left')
    pos = pos[pos < n15]
    entries[pos] = True
    del df, X, Xmat, y, proba; gc.collect()
    return entries, dict(n_tf=int(sig_tf.sum()))


# ---------------------------------------------------------------------------
# ۴) بک‌تست پرتفوی روی M15 (SL/TP بر حسب ATR همان M15، dedup سراسری)
# ---------------------------------------------------------------------------
from backtest import run_backtest

def eval_entries(entries, label=''):
    # فقط جایی که uptrend M15 برقرار است (سازگاری با کاندید جریان‌ها + ATR معتبر)
    valid15 = (m15_c > ema50_15) & (ema50_15 > ema200_15) & ~np.isnan(atr15)
    ent = entries & valid15
    s, tr = run_backtest(m15, ent, None, None, 'long', SPREAD, 48,
                         sl_series=SL_MULT * atr15, tp_series=TP_MULT * atr15,
                         allow_overlap=False)
    nt = s['n_trades']
    if nt < 30:
        print(f"  {label}: n<30 ({nt})", flush=True)
        return None
    wr = s['win_rate']
    gw = tr[tr['outcome'] == 'win']['pnl'].sum()
    gl = -tr[tr['outcome'] == 'loss']['pnl'].sum()
    pf = gw / gl if gl > 1e-9 else np.inf
    tpd = nt / span_days * 7 / 5
    wins = int(round(wr / 100 * nt))
    pv = binomtest(wins, nt, BE / 100, alternative='greater').pvalue
    print(f"  {label:28s}: n={nt:4d} WR={wr:.2f}% PF={pf:.3f} exp={s['expectancy']:+.3f}$ "
          f"pnl={s['total_pnl']:+.0f}$ tpd={tpd:.2f} p(WR>{BE:.0f})={pv:.4f}", flush=True)
    return dict(n=nt, wr=wr, pf=pf, exp=s['expectancy'], pnl=s['total_pnl'], tpd=tpd, pv=pv, entries=ent)


# ---------------------------------------------------------------------------
# اجرا
# ---------------------------------------------------------------------------
# افق هر TF طوری که مدت زمانی مشابه ~۱۲ ساعت باشد (نقطهٔ کاری متعادل)
# M15: 48 کندل=12h | M30: 24 | H1: 12 | H4: 4  (اما حداقل چند کندل برای TP/SL)
STREAM_CFG = [
    ('M15', 0.65, 48),
    ('M30', 0.65, 24),
    ('H1',  0.63, 12),
    ('H4',  0.60, 6),
]

print(f"\nنقطهٔ کاری: TP{TP_MULT}/SL{SL_MULT} (BE≈{BE:.1f}%), افق متغیر per-TF", flush=True)
print("="*80, flush=True)
print("جریان‌های منفرد (هر TF مستقل، سیگنال نگاشت‌شده به M15):", flush=True)
print("="*80, flush=True)

stream_entries = {}
for tf, thr, hz in STREAM_CFG:
    print(f"\n[جریان {tf}] آموزش WF + تولید سیگنال ...", flush=True)
    ent, meta = stream_signals_on_m15(tf, thr, hz)
    r = eval_entries(ent, f'{tf} (thr={thr},hz={hz})')
    if r is not None:
        stream_entries[tf] = ent
    gc.collect()

# ---------------------------------------------------------------------------
# پرتفوی: ادغام همهٔ جریان‌ها (OR) با dedup سراسری در بک‌تست
# ---------------------------------------------------------------------------
print("\n" + "="*80, flush=True)
print("پرتفوی ترکیبی (ادغام جریان‌ها + dedup سراسری):", flush=True)
print("="*80, flush=True)
if stream_entries:
    combos = [
        ('M15+M30', ['M15', 'M30']),
        ('M15+H1', ['M15', 'H1']),
        ('M15+M30+H1', ['M15', 'M30', 'H1']),
        ('M15+M30+H1+H4', ['M15', 'M30', 'H1', 'H4']),
    ]
    for name, tfs in combos:
        merged = np.zeros(n15, dtype=bool)
        avail = [t for t in tfs if t in stream_entries]
        if not avail:
            continue
        for t in avail:
            merged |= stream_entries[t]
        eval_entries(merged, f'PORTFOLIO {name}')

print("\nتمام.", flush=True)
