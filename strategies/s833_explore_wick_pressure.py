# -*- coding: utf-8 -*-
"""
S833 — کاوشِ ۱: عدم توازنِ فشارِ فتیله‌ها (Wick-Pressure Imbalance) — فقط ۶۰٪ اکتشاف
=======================================================================================
فرضیه‌ی علّی: فتیله‌ی بالایی = ردِ قیمت‌های بالا توسط عرضه؛ فتیله‌ی پایینی = ردِ
قیمت‌های پایین توسط تقاضا. انباشتِ یک‌طرفه‌ی فتیله‌ها در پنجره‌ی W کندل، فشارِ
نهفته‌ی حراج را لو می‌دهد. دو خوانشِ رقیب (هر دو متقارن، جهت درون‌زاد):
  A) ادامه (continuation): فتیله‌های بالاییِ غالب ⇒ short (عرضه می‌راند)
  B) وارونه (reversal): فتیله‌های بالاییِ غالب ⇒ long (جذبِ عرضه تمام شد)
اکتشاف هر دو علامت را می‌سنجد — بازار انتخاب می‌کند.

سه پادزهر از شکست‌های S830/S831/S832 از روز اول:
  ۱) تقارن کامل آینه‌ای + جهت درون‌زاد
  ۲) پایداری E1/E2 در همان جدول
  ۳) 🔑 سنجه = lift نسبت به نالِ جای‌گشتیِ هم‌هندسه (K=120 در اکتشاف)، نه سربه‌سرِ هزینه
     هندسه‌ی ساده: SL/TP ثابتِ ATRمحور، بدون trail/BE (مدیریت = آلودگی سنجه)

تعریف: wick_up = h - max(o,c) ، wick_dn = min(o,c) - l
  imb(t) = Σ_W (wick_up - wick_dn) / Σ_W (wick_up + wick_dn)   ∈ [-1, +1]
  رخداد: |imb| > θ و |imb| در کندل قبل ≤ θ (عبورِ تازه — بدون خوشه‌ی رخداد)
شبکه: TF ∈ {H1, H4} × W ∈ {13, 34} × θ ∈ {0.25, 0.40} × mode ∈ {cont, rev}
هندسه ثابت: SL=2×ATR34, TP=2×SL, hold=34, no-overlap.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

WARMUP = 200
K_NULL = 120
SEED = 833001
SLM, RR, HOLD = 2.0, 2.0, 34

def pf_of(p):
    w = p[p > 0].sum(); lo_ = -p[p < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf

for TF in ('H1', 'H4'):
    d = fd.load_fast('XAUUSD', TF)
    df_full = fd.as_dataframe(d)
    split = int(len(df_full) * 0.6)          # ۶۰٪ اکتشاف همین TF
    df = df_full.iloc[:split].reset_index(drop=True)
    o = df['open'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(df)
    HALF = n // 2
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr); atr[0] = tr[0]
    a = 1.0 / 34
    for i in range(1, n):
        atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']
    slp = np.clip(atr_pip * SLM, 8, 5000)
    tpp = slp * RR

    wu = h - np.maximum(o, c)
    wd = np.minimum(o, c) - l
    print(f'\n################ TF={TF}  explore bars={n:,}  src={d["src"]} ################', flush=True)

    for W in (13, 34):
        # مجموعِ غلتانِ علّی
        cu = np.cumsum(np.concatenate([[0.0], wu]))
        cd = np.cumsum(np.concatenate([[0.0], wd]))
        su = cu[W:] - cu[:-W]        # مجموعِ W کندلِ منتهی به t (شامل t)
        sd = cd[W:] - cd[:-W]
        imb = np.full(n, np.nan)
        tot = su + sd
        ok = tot > 0
        imb[W-1:][ok] = (su[ok] - sd[ok]) / tot[ok]
        prev_imb = np.concatenate([[np.nan], imb[:-1]])

        for theta in (0.25, 0.40):
            up_x = (imb > theta) & ~(prev_imb > theta)       # عبور تازه به بالا
            dn_x = (imb < -theta) & ~(prev_imb < -theta)
            up_x[:WARMUP] = False; dn_x[:WARMUP] = False
            n_ev = int(up_x.sum() + dn_x.sum())
            if n_ev < 80:
                print(f'  W={W} th={theta}: events={n_ev} — کم، رد', flush=True)
                continue
            for mode in ('cont', 'rev'):
                # cont: فتیله‌ی بالایی غالب ⇒ عرضه می‌راند ⇒ short (و برعکس)
                if mode == 'cont':
                    ls, ss = dn_x, up_x
                else:
                    ls, ss = up_x, dn_x
                tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                         asset='XAUUSD', max_hold=HOLD,
                                         allow_overlap=False)
                if len(tdf) < 60:
                    continue
                pnl = tdf['pnl_pip'].values
                eb = tdf['entry_bar'].values
                wr = float((pnl > 0).mean() * 100)
                pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
                # 🔑 نالِ هم‌هندسه روی همان کندل‌های سیگنال (درس S832)
                sig_bars = tdf['signal_bar'].values.astype(int)
                rng = np.random.default_rng(SEED + W * 100 + int(theta * 100))
                wrs = []
                for _ in range(K_NULL):
                    dirs = rng.integers(0, 2, size=len(sig_bars)).astype(bool)
                    lm = np.zeros(n, bool); lm[sig_bars[dirs]] = True
                    sm = np.zeros(n, bool); sm[sig_bars[~dirs]] = True
                    ptr = se.simulate_trades(df, lm, sm, sl_pip=slp, tp_pip=tpp,
                                             asset='XAUUSD', max_hold=HOLD,
                                             allow_overlap=False)
                    if len(ptr):
                        wrs.append(float((ptr['pnl_pip'].values > 0).mean() * 100))
                nm = float(np.mean(wrs)); nsd = float(np.std(wrs))
                lift = wr - nm
                z = lift / nsd if nsd > 0 else 0.0
                flag = ' <<<' if (lift >= 4 and z >= 2.5 and pf >= 1.2) else ''
                print(f'  W={W} th={theta} {mode}: n={len(tdf):5,} WR={wr:5.2f}% '
                      f'null={nm:5.2f}%±{nsd:.2f} INFOlift={lift:+6.2f}pp z={z:+4.1f} '
                      f'exp={float(pnl.mean()):+7.2f} PF={pf:.3f} [E1={pf1:.3f} E2={pf2:.3f}]{flag}',
                      flush=True)

print('\n[S833 explore-1 complete]', flush=True)
