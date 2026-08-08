# -*- coding: utf-8 -*-
"""
S431 — احیای `S351`ِ POWER-LIMITED از راهِ **تجمیعِ چند-کارتی**
================================================================================
پیش‌ثبت: `results/S431_PREREG_S351_MULTICARD_POOLING.md` (با دو الحاقیه).

فرضیه
--------------------------------------------------------------------------------
عضوِ مرکزیِ LPSB (`L=8, f=0.33`) با هندسهٔ منجمدِ `S351`
(`SL=1.618·ATR21`, `RR=1.618`, `hold=12`) روی چهار کارتِ طلا
(`M5/M15/M30/H1`) **هیچ دروازه‌ای را نمی‌شکند** و هر چهار `POWER-LIMITED`اند:
تنها بیماری‌شان `n≈۵۰` است، با `lift`های هم‌جهت و هم‌مرتبه (+۱۲.۵ تا +۱۸.۸).

چون هندسه بر حسبِ **ATRِ خودِ کارت** است (نه pipِ ثابت)، قانون
تایم‌فریم-اگنوستیک است. پس تجمیعِ تقویمیِ چهار کارت باید `n` را به ~۲۳۱
برساند و `z` را از ~۲.۱ به بالای `۳.۰۹` ببرد — **بدونِ افزودنِ حتی یک
پارامترِ نو**، یعنی بدونِ هزینهٔ چندگانگیِ نو.

⛔ چرا این «نرم‌کردنِ معیار» نیست
--------------------------------------------------------------------------------
۱) هیچ پارامتری جست‌وجو نمی‌شود؛ همه از `S351` **منجمد** ارث می‌رسند.
۲) همپوشانیِ زمانی با صفِ FIFOِ تقویمیِ `engine/rqs2_pool.py` **حذف** می‌شود،
   پس `n`ِ گزارش‌شده `n_eff`ِ واقعی است، نه تورمِ ۴برابریِ چهار کارت.
۳) مدلِ صفر **اندازه‌گیری‌شده** است (جای‌گشت روی همان کارت‌ها)، نه فرضی.
۴) حکم با `compute_rqs2`ِ استاندارد (v2.6) صادر می‌شود، نه با proxy.

درسِ ثبت‌شده از تلاشِ شکست‌خوردهٔ قبلی (`s351_pool_rescue.py`)
--------------------------------------------------------------------------------
آن گام نسخهٔ **خام** را تجمیع کرد (D1 با `lift=+۱۳.۹` و `n=۷۴` در کنارِ H1 با
`lift=+۲.۳` و `n=۱۹۳۷`) ⇒ **رقیق‌سازیِ وزنی** ⇒ `z=۱.۵۷` ⇒ REJECT.
اینجا اعضا هم‌مرتبه‌اند (بیشترین سهم ۳۲٪ ⇒ قیدِ `C5` پاس).

قانونِ «اندک اندک»: هر کارت به‌محضِ محاسبه در JSONِ خودش checkpoint می‌شود؛
منتظرِ اتمامِ همه نمی‌مانیم، چون سندباکس ناپایدار است.
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from engine.rqs2_pool import pool_cards                             # noqa: E402
from strategies import s333_s79_pullback_revival as s333            # noqa: E402
from strategies.s351_lpsb import lpsb_signals                       # noqa: E402
from strategies.s351_verdict import build_null_side, CENTRAL        # noqa: E402

OUT = 'results/_scan_S431'

# ---------------------- اعضای استخر (قفل‌شده در پیش‌ثبت) ----------------------
# قیدِ `C2`: این فهرست **پیش از** دیدنِ هر عددِ نو قفل شده و پس از اجرا
# کوتاه نمی‌شود. نام‌گذاری با زیرخط چون `s333.BEST_CFG` همین کلید را دارد.
POOL_MEMBERS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1']

WARMUP = 300                            # همان WARMUPِ `s351_filter_rqs2.py`
SEED = 20260805                         # بذرِ پیش‌ثبت‌شده
K_PERM = 2000                           # `K` پیش‌ثبت‌شده
SPLIT_FRAC = 0.60                       # همان تقسیمِ ارثی

# قیدِ `C5`ِ پیش‌ثبت‌شده: هیچ عضوی بیش از این سهم از نمونهٔ تجمیعی نباشد.
C5_MAX_MEMBER_SHARE = 0.50

# ---- چندگانگیِ صادقانه (قیدِ `C4`) --------------------------------------------
# `S431` هیچ پارامترِ نویی جست‌وجو نمی‌کند: نه هندسه (ارثیِ `S333.BEST_CFG`)،
# نه فیلتر (`state == -1`، صفر-پارامتر). هزینهٔ ارثی = ۲ علامتِ حالت × ۴ کارت
# = ۸ (همان `N_MULT`ِ `s351_filter_rqs2.py`). برای بدبینیِ بیشتر، خودِ
# تصمیمِ «تجمیع» را هم یک درجهٔ آزادی می‌شماریم ⇒ ۸ × ۲ = ۱۶.
N_TRIALS_INHERITED = 16


def _win_col(tr):
    """`evaluate` ممکن است ستونِ `win` نداشته باشد؛ از `pnl_pip` بساز."""
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)
    return tr


def card_population(card, n_perm=K_PERM, verbose=True):
    """
    جمعیتِ یک عضوِ استخر = **`S333` + دروازهٔ صفر-پارامترِ `state == -1`**.

    ⚠️ این تابع در الحاقیهٔ ۳ بازنویسی شد. نسخهٔ اولِ من LPSBِ **خام** را
    اجرا می‌کرد (`n≈۴۴۶۱`, `lift≈۰`) که جمعیتِ اشتباهی بود؛ جمعیتِ درست
    همان است که `s351_filter_rqs2.py:77` می‌سازد:
        `filt = s333.build_layer(df, cfg) & (state == -1)`
    هندسه = `S333.BEST_CFG[card]` (ارثی، جست‌وجو نشده).

    برمی‌گرداند dict شاملِ `tr`، `dt` (محورِ تقویمی)، `lift` نسبت به مبنای
    **اندازه‌گیری‌شده**، و متریک‌های کارت.
    """
    cfg = s333.BEST_CFG[card]
    asset = 'XAUUSD'
    path = se.ASSETS[card]['file']
    if not os.path.exists(path):
        return None

    df = se.load_data(path)
    n = len(df)
    close = df['close'].to_numpy(float)
    dt = df['dt'].values if 'dt' in df.columns else np.arange(n)

    base = s333.build_layer(df, cfg)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    filt = base & (state == -1)                      # فیلترِ صفر-پارامتر

    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']
    tr, _ = s333.evaluate(df, filt, card, sl, tp, mh)
    if tr is None or len(tr) < 3:
        return None
    tr = _win_col(tr)

    # ---- مبنای **اندازه‌گیری‌شده** روی همان کارت (نه عددِ فرضی) ----
    valid = np.where(np.isfinite(close))[0]
    valid = valid[valid >= WARMUP]
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    rng = np.random.default_rng(SEED)
    sl_price = sl * se.ASSETS[asset]['pip']
    null = build_null_side(df, asset, valid, np.full(n, sl_price),
                           nL, nS, n_perm, rng, verbose=verbose)

    # lift وزنی به سمت، نسبت به مبنای بی‌قید
    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
    refs, wts = [], []
    for side, cnt in (('long', nL), ('short', nS)):
        u = null[side].get('uncond_wr')
        if u is not None and cnt > 0:
            refs.append(u * cnt)
            wts.append(cnt)
    ref = (sum(refs) / sum(wts)) if wts else None
    lift = (wr - ref) if ref is not None else None

    return dict(card=card, asset=asset, tr=tr, dt=dt, lift=lift,
                n=int(len(tr)), wr=wr, ref_wr=ref, null=null,
                n_long=nL, n_short=nS, n_base=int(base.sum()),
                sl_pip=float(sl), tp_pip=float(tp), max_hold=int(mh),
                exp_pip=float(np.mean(tr['pnl_pip'])),
                bars=int(n))


def blend_pool_null(members_used, pool_df):
    """
    مدلِ صفرِ استخر: ترکیبِ **وزنیِ** نول‌های اندازه‌گیری‌شدهٔ اعضا، با وزنِ
    سهمِ هر کارت از معاملاتِ **باقی‌ماندهٔ پس از FIFO** (نه سهمِ اولیه‌اش).

    چرا وزن با سهمِ پس-از-FIFO؟ چون صفِ FIFO بخشی از معاملات را حذف می‌کند و
    اگر با سهمِ اولیه وزن بدهیم، مبنای کارتی که بیشتر حذف شده بیش‌ازحد
    اثر می‌گذارد ⇒ مبنایِ اشتباه ⇒ liftِ اشتباه. این جزئیاتِ ریز، تفاوتِ
    یک اندازه‌گیریِ درست و یک عددِ خوش‌ظاهر است.
    """
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u, den_u = 0.0, 0.0
        num_m, num_s, den_p, kmin = 0.0, 0.0, 0.0, None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
            if w <= 0:
                continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * w
                den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w
                # واریانسِ ترکیب: وزن‌ها را روی واریانس اعمال می‌کنیم، نه sd
                num_s += (d['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = d.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None,
            perm_k=kmin)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--perm', type=int, default=K_PERM)
    ap.add_argument('--cards', type=str, default='')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    want = [c.strip() for c in a.cards.split(',') if c.strip()] or POOL_MEMBERS

    print(f'== S431 — تجمیعِ چند-کارتیِ LPSB · اعضا: {want} ==', flush=True)
    print(f'   جمعیت: S333 + دروازهٔ `state == -1` · عضوِ LPSB={CENTRAL} · '
          f'هندسه: ارثیِ S333.BEST_CFG (per-card) · K={a.perm}', flush=True)

    members = []
    for card in want:
        cache = os.path.join(OUT, f'{card.replace("-", "_")}_member.json')
        print(f'\n-- کارتِ {card} --', flush=True)
        m = card_population(card, n_perm=a.perm)
        if m is None:
            print('   ناکافی (سیگنال/معاملهٔ کم) — رد', flush=True)
            continue
        print(f"   n={m['n']} (L={m['n_long']}/S={m['n_short']}) "
              f"WR={m['wr']:.2f} ref={m['ref_wr']} lift={m['lift']} "
              f"exp={m['exp_pip']:+.2f} pip", flush=True)
        # checkpointِ «اندک اندک» — بی‌درنگ روی دیسک
        with open(cache, 'w', encoding='utf-8') as fh:
            json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
                      fh, ensure_ascii=False, indent=1, default=str)
        members.append(m)

    if len(members) < 2:
        print('\n[توقف] کمتر از دو عضوِ معتبر — تجمیع بی‌معناست.', flush=True)
        return

    # ------------------------- قیدِ C1: همگنی -------------------------
    lifts = [m['lift'] for m in members if m['lift'] is not None]
    same_sign = all(x > 0 for x in lifts) or all(x < 0 for x in lifts)
    print(f'\n[C1 همگنی] liftها={["%.2f" % x for x in lifts]} '
          f'هم‌علامت={same_sign}', flush=True)
    if not same_sign:
        print('[C1 نقض] اعضا هم‌جهت نیستند ⇒ تجمیع متوقف (REJECT).',
              flush=True)
        return

    # --------------------- تجمیعِ تقویمی + حذفِ همپوشانی ---------------------
    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                           lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] pool_cards هیچ عضوِ معتبری نیافت.', flush=True)
        return

    pool = res['pool']
    print(f"\n[تجمیع] n_before={res['n_before']} → n_after={res['n_after']} "
          f"(حذفِ همپوشانیِ FIFO: "
          f"{100*(1-res['n_after']/max(res['n_before'],1)):.1f}%)", flush=True)
    print(f"   used={[u['card'] for u in res['used']]}", flush=True)
    for d in res['dropped']:
        print(f"   dropped {d['card']}: {d['reason']}", flush=True)
    print(f"   selection trace={json.dumps(res['selection']['trace'], ensure_ascii=False)}",
          flush=True)

    # ------------------------- قیدِ C5: سقفِ سهم -------------------------
    share = pool['src_card'].value_counts(normalize=True)
    print(f'\n[C5 سهمِ اعضا] {share.round(3).to_dict()}', flush=True)
    if float(share.max()) > C5_MAX_MEMBER_SHARE:
        print(f'[C5 نقض] عضوِ {share.idxmax()} سهمِ {share.max():.1%} دارد '
              f'> {C5_MAX_MEMBER_SHARE:.0%} ⇒ خطرِ رقیق‌سازی ⇒ توقف (REJECT).',
              flush=True)
        with open(os.path.join(OUT, 'pool_c5_violation.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(dict(share=share.to_dict(), limit=C5_MAX_MEMBER_SHARE),
                      fh, ensure_ascii=False, indent=1)
        return

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f'\n[نولِ استخر] {json.dumps(null, ensure_ascii=False, default=str)}',
          flush=True)

    # ------------------------- داوریِ RQS2 v2.6 -------------------------
    asset = used_members[0]['asset']
    # ⚠️ هندسهٔ استخر: اعضا SLِ **pipِ متفاوت** دارند (M5=۱۲۰ … H1=۴۵۰)، پس
    # نمی‌توان یک عددِ ثابت داد. مدیانِ **وزنی به سهمِ پس-از-FIFO** گرفته
    # می‌شود تا `H9`/`H2` با هندسهٔ واقعیِ استخر داوری شوند، نه با هندسهٔ یک
    # کارتِ دلبخواه. `RR`ِ استخر هم از همان نسبتِ ارثی مشتق می‌شود.
    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = sum(by_card[c]['sl_pip'] * w for c, w in shares.items()
                 if c in by_card)
    tp_med = sum(by_card[c]['tp_pip'] * w for c, w in shares.items()
                 if c in by_card)
    sl_med = float(sl_med) if sl_med > 0 else None
    tp_med = float(tp_med) if tp_med > 0 else None

    # ---------------- محورِ تقویمیِ مشترک (اصلاحِ باگِ BUG-AXIS) ----------------
    # ⚠️ نسخهٔ اولِ من `bar_time = pool['t_entry']` می‌داد. باگ: موتور
    # (`rqs2.py:729`) محور را با **`exit_bar`** ایندکس می‌کند
    # (`bt[clip(exit_bar, 0, len(bt)-1)]`). طولِ آن آرایه ۱۰۹ بود و
    # `exit_bar`ها ~۱۲۰٬۰۰۰ ⇒ همه به ۱۰۸ کلیپ شدند ⇒ هر ۱۰۹ معامله در **یک**
    # سطلِ تقویمی افتادند (`cal_occupied=1`) ⇒ `H0`/`H6` به‌غلط شکستند.
    # این یک نقصِ لایه نبود، نقصِ کدِ من بود.
    #
    # اصلاحِ درست: استخر جمعیتی **ترکیبی** است و `entry_bar`ِ هر عضو در
    # ایندکس‌گذاریِ کارتِ خودش معنا دارد (کندلِ ۵۰۰۰ در M5 ≠ در H1). پس یک
    # محورِ **مشترک** می‌سازیم و اندیس‌ها را روی آن **بازنویسی** می‌کنیم تا
    # هر سه مصرف‌کنندهٔ موتور هم‌راستا شوند:
    #   • `H6`/تقسیمِ تقویمی  ← `bar_time[exit_bar]`
    #   • همزمانی (`rqs2.py:662`) ← `[entry_bar, exit_bar]`
    #   • `H10` خلاف‌جریان (`rqs2.py:413`) ← `close[entry_bar]`
    # ---- محورِ مشترک: شبکهٔ **مصنوعیِ** ۵دقیقه‌ای روی افقِ کاملِ استخر ----
    # ⚠️ دو تلاشِ قبلیِ من هر دو باگ داشتند و هر دو با عدد کشف شدند:
    #   • `BUG-QUANT` (محورِ H1): همپوشانیِ واقعیِ تقویمی **صفر** بود، ولی ۴
    #     معامله فاصله‌شان از خروجِ قبلی زیرِ ۶۰ دقیقه بود (کمینه ۵ دقیقه) ⇒
    #     در یک سطلِ ساعتی برخورد کردند ⇒ `concurrency=2` ⇒ `H0` غلط شکست.
    #   • `BUG-SPAN` (محورِ فایلِ M5): فایلِ `XAUUSD_M5.csv` فقط از
    #     **۲۰۲۳-۰۹-۱۸** شروع می‌شود، ولی اعضای M30/H1 از **۲۰۱۱-۰۱-۰۳**.
    #     پس هر معاملهٔ پیش از ۲۰۲۳ به ایندکسِ صفر **کلیپ** شد و روی هم انبار
    #     گشت ⇒ `concurrency=34` (بدتر از قبل!). یعنی افقِ محور باید **ابرمجموعهٔ**
    #     افقِ استخر باشد؛ هیچ فایلِ واحدی این شرط را ندارد.
    # اصلاح: محور را از هیچ فایلی نمی‌گیریم — یک شبکهٔ یکنواختِ ۵دقیقه‌ای از
    # min(t_entry) تا max(t_exit) می‌سازیم. رزولوشن = ریزترین فاصلهٔ واقعیِ
    # استخر (۵ دقیقه) و پوشش = کلِ ~۱۵ سال. پس نه گردکردن رخ می‌دهد نه کلیپ.
    STEP_NS = 5 * 60 * 1_000_000_000            # ۵ دقیقه بر حسبِ نانوثانیه
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS, dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f'\n[محورِ مشترک] شبکهٔ ۵دقیقه‌ای · {axis_dt[0]} → {axis_dt[-1]} '
          f'· {len(axis_t):,} سطل', flush=True)

    # `close`ِ هم‌راستا با محور (برای `H10`): از درشت‌ترین کارتی که کلِ افق را
    # دارد (H1، از ۲۰۱۱) با نگهداشتِ آخرین مقدار روی شبکه نمونه‌برداری می‌شود.
    # `searchsorted(..., 'right')-1` ⇒ هیچ قیمتِ **آینده** به گذشته نمی‌نشیند.
    ref_df = se.load_data(se.ASSETS['XAUUSD_H1']['file'])
    ref_t = ref_df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    ref_c = ref_df['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.searchsorted(axis_t, pool['t_entry'].values, 'left')
    pool['exit_bar'] = np.searchsorted(axis_t, pool['t_exit'].values, 'left')
    pool['entry_bar'] = np.clip(pool['entry_bar'], 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(pool['exit_bar'], 0, len(axis_t) - 1)
    # معاملهٔ درون-ساعتی (M5) ممکن است ورود و خروجش به یک سطل بیفتد؛ برای
    # اینکه محاسبهٔ همزمانی بازهٔ تهی نبیند، حداقل یک سطل عرض می‌دهیم.
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    bar_time = axis_dt

    # ---------- تقسیمِ اکتشاف/خارج‌نمونه (اصلاحِ `BUG-OOS`) ----------
    # اجرای قبلی `H3`/`H7` را «نامعلوم» داد چون `split_bar` پاس نشده بود
    # (`oos = {}`). این هم نقصِ کدِ من بود، نه نقصِ لایه — و خطرناک‌تر از
    # شکستِ صریح است، چون دروازه در **سکوت** خاموش می‌شود.
    #
    # قاعده **ارثی** است، ساختهٔ من نیست: `s351_filter_rqs2.py:46` ⇒
    # `SPLIT_FRAC = 0.60` و هر چهار کارت همین ۶۰٪ را داشتند
    # (M5:۱۲۰۰۰۰/۲۰۰۰۰۰، M15:۹۰۰۰۰/۱۵۰۰۰۰، M30:۱۰۸۸۲۹/۱۸۱۳۸۳، H1:۵۴۵۷۰/۹۰۹۵۰).
    #
    # ⚠️ چرا `holdout_mask` و نه `split_bar`: استخر جمعیتی ترکیبی است و
    # `split_bar` را موتور روی `entry_bar` اعمال می‌کند — که من بازنویسی‌اش
    # کردم. ماسکِ صریح روی **زمانِ تقویمیِ مطلق** ساخته می‌شود (نقطهٔ ۶۰٪ِ
    # محورِ مشترک)، پس مرزِ اکتشاف/خارج‌نمونه برای هر سه تایم‌فریم **یک
    # لحظهٔ تقویمیِ واحد** است، نه سه مرزِ متفاوت. موتور طولِ ماسک را هم
    # اعتبارسنجی می‌کند، پس ناهم‌ترازیِ خاموش ممکن نیست.
    # ⚠️ اصلاحِ `BUG-SPLITDIR`: نسخهٔ اولِ من مرز را نقطهٔ ۶۰٪ِ **تقویم** گرفت
    # (`axis_t[0.6 * len]`) و نتیجه **معکوس** شد: مرز=۲۰۲۰ ⇒ اکتشاف=۱۸،
    # خارج‌نمونه=۹۱. علت: معاملات در سال‌های اخیر متمرکزند، چون M5 فقط از
    # ۲۰۲۳ و M15 از ۲۰۲۰ داده دارند و فقط M30 تا ۲۰۱۱ عقب می‌رود. پس ۶۰٪ِ
    # *زمان* ≠ ۶۰٪ِ *نمونه*.
    # قاعدهٔ ارثی «۶۰٪ اولِ **کندل‌ها**» بود که در هر کارت تقریباً ۶۰٪ِ
    # معاملات را می‌داد. معادلِ درستِ آن در جمعیتِ ترکیبی، صدکِ ۶۰٪ِ **زمانِ
    # ورودِ معاملات** است: هم جهت را درست می‌کند (اکتشافِ قدیمی‌تر،
    # خارج‌نمونهٔ جدیدتر ⇒ آزمونِ **آینده‌نگر**) و هم نسبتِ ۶۰/۴۰ را حفظ می‌کند.
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'\n[تقسیمِ ارثی {SPLIT_FRAC:.0%}] مرز={np.datetime64(split_ns, "ns")} '
          f'· اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}',
          flush=True)

    r = rqs2.compute_rqs2(pool, asset, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null,
                          close=axis_close,
                          holdout_mask=holdout,
                          n_trials=N_TRIALS_INHERITED,
                          allow_overlap=False)

    print('\n' + rqs2.format_rqs2('S431-POOL', r), flush=True)

    out = dict(members=[dict(card=m['card'], n=m['n'], lift=m['lift'],
                             wr=m['wr'], exp_pip=m['exp_pip'])
                        for m in members],
               used=[u['card'] for u in res['used']],
               dropped=res['dropped'],
               selection=res['selection'],
               n_before=res['n_before'], n_after=res['n_after'],
               member_share=share.to_dict(),
               sl_pip_med=sl_med, tp_pip_med=tp_med,
               n_trials=N_TRIALS_INHERITED,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'))
    with open(os.path.join(OUT, 'pool_verdict.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f"\n[saved] {OUT}/pool_verdict.json", flush=True)


if __name__ == '__main__':
    main()
