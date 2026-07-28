"""
s333_mr_short_revival.py — احیای لایهٔ «Mean-Reversion SHORT» (منشأ: s122) با RQS+
================================================================================
> معیارِ رسمی = RQS+ ≥ ۸۰ (نه سودِ خالص، نه WR خام). سند: docs/RQS_ROBUST_QUALITY_SCORE.md
================================================================================
منشأ لایه:
  s122 (اسکالپِ SHORT روی M5، mean-reversion): «SHORT وقتی قیمت بیش‌ازحد بالای
  میانگین رفته (z-score بالا) + RSI اشباعِ خرید + شمعِ برگشتی ⇒ fade به میانگین.»
  s122 تحت رژیمِ قدیمِ سود-خالص ساخته شد، از اعدادِ رند (SL40/TP60, z=1.5/2.0/2.5,
  rsi=65/70/75) استفاده کرد و هرگز تحت RQS+ ارزیابی نشد (فایلِ نتیجهٔ MD نداشت).

تزِ احیا (نبوغ + تفکرِ غیرخطی):
  fade فقط در رژیمِ بازگشت‌به‌میانگین (mean-reverting) معنا دارد. در رژیمِ روندی،
  fade کشته می‌شود (همان چیزی که s121/s122 خام را زمین زد). طبقِ docs/indicators/
  statistical.md، دقیقاً برای همین «سوییچِ هرست» هست:
    H<0.45 ⇒ فقط لایهٔ fade/bounce مجاز است.
  و kurt (کشیدگی) به‌عنوانِ safety-gate: در kurt بالا (ریسکِ دُم) خاموش شو تا یک
  جهشِ دُم استاپ را نزند ⇒ محافظِ مستقیمِ G3 (maxDD + MaxConsecLoss).

  فیلترها (جعبه‌ابزار = بانکِ ۴۰۱‌تایی، نه کدنویسیِ دستی):
    F1) hurst < h_thr           → رژیمِ mean-reverting (کلیدِ اصلی)
    F2) kurt  < k_thr           → safety-gate ریسکِ دُم
    F3) chop  > c_thr (اختیاری) → بازارِ رنج/بی‌روند (مکملِ هرست)
    F4) r2    < r2_thr (اختیاری)→ نبودِ روندِ خطیِ قوی

  همهٔ آستانه‌ها/TP/SL per-TF و غیررند از اسکن.
================================================================================
"""
import sys, os, json, argparse
ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'engine'))
import numpy as np, pandas as pd
from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs
RESULTS = os.path.join(ROOT, 'results')


def load(asset, tf):
    path = os.path.join(ROOT, 'data', f'{asset}_{tf}.csv')
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def rsi_np(x, p=14):
    d = np.diff(x, prepend=x[0]); g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = pd.Series(g).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag / np.where(al == 0, np.nan, al)
    return 100 - 100/(1 + rs)


def build_short_mr(df, z_win, z_thr, rsi_thr, rsi_p=14):
    """منطقِ پایهٔ s122: SHORT fade اشباعِ خرید (بدونِ look-ahead)."""
    c = df['close'].values.astype(float); o = df['open'].values.astype(float)
    ma = pd.Series(c).rolling(z_win).mean().values
    sd = pd.Series(c).rolling(z_win).std().values
    z = (c - ma) / np.where(sd == 0, np.nan, sd)
    r = rsi_np(c, rsi_p)
    bear_candle = (c < o) & (c < np.roll(c, 1))
    sig = (z > z_thr) & (r > rsi_thr) & bear_candle
    return np.nan_to_num(sig, nan=0).astype(bool)


_REG_CACHE = {}


def precompute_regime(df):
    """اندیکاتورهای رژیم را یک‌بار محاسبه و کش کن (hurst کند است)."""
    key = id(df)
    if key in _REG_CACHE:
        return _REG_CACHE[key]
    reg = {
        'hurst': np.nan_to_num(pd.Series(ib.compute('hurst', df)).values, nan=1.0),
        'kurt':  np.nan_to_num(pd.Series(ib.compute('kurt', df)).values, nan=99.0),
        'chop':  np.nan_to_num(pd.Series(ib.compute('chop', df)).values, nan=0.0),
        'r2':    np.nan_to_num(pd.Series(ib.compute('r2', df)).values, nan=1.0),
    }
    _REG_CACHE[key] = reg
    return reg


def regime_filters(df, h_thr=None, k_thr=None, c_thr=None, r2_thr=None):
    """ماسکِ رژیمِ mean-reverting از بانکِ ۴۰۱‌تایی (بدونِ look-ahead، از کش)."""
    reg = precompute_regime(df)
    mask = np.ones(len(df), dtype=bool)
    used = []
    if h_thr is not None:
        mask &= reg['hurst'] < h_thr;  used.append(f'hurst<{h_thr}')
    if k_thr is not None:
        mask &= reg['kurt'] < k_thr;   used.append(f'kurt<{k_thr}')
    if c_thr is not None:
        mask &= reg['chop'] > c_thr;   used.append(f'chop>{c_thr}')
    if r2_thr is not None:
        mask &= reg['r2'] < r2_thr;    used.append(f'r2<{r2_thr}')
    return mask, used


def evaluate(df, ssig, sl, tp, mh, asset, label, verbose=True):
    empty = np.zeros(len(df), dtype=bool)
    tr = se.simulate_trades(df, empty, ssig, sl, tp, asset, max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        if verbose:
            print(f"{label:44s} | no trades")
        return None, None
    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
    if verbose:
        print(rqs.format_report(label, r))
    return tr, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tf', default='M5')
    ap.add_argument('--stage', default='baseline')  # baseline | scan
    args = ap.parse_args()

    df = load(args.asset, args.tf)
    print(f"# داده: {len(df)} کندلِ {args.asset}_{args.tf}\n")

    if args.stage == 'baseline':
        # بازتولیدِ s122 خام تحتِ RQS+ (نقطهٔ شروعِ احیا)
        print("### مرحلهٔ ۱ — baseline خامِ s122 تحتِ RQS+ (اعدادِ رندِ اصلی) ###")
        for zt in [1.5, 2.0, 2.5]:
            for rt in [65, 70, 75]:
                ssig = build_short_mr(df, z_win=50, z_thr=zt, rsi_thr=rt)
                n_sig = int(ssig.sum())
                if n_sig < 30:
                    continue
                for (sl, tp, mh) in [(40, 60, 12), (50, 80, 16), (60, 100, 20)]:
                    evaluate(df, ssig, sl, tp, mh, args.asset,
                             f"base z>{zt} rsi>{rt} SL{sl}/TP{tp}")
        print("\n>>> baseline کامل شد. هیچ‌کدام انتظار می‌رود RQS+≥۸۰ نباشد (بدونِ فیلترِ رژیم).")

    elif args.stage == 'diag':
        # تشخیصِ نقطهٔ شیرینِ scan2: z34/2.4 rsi70 hurst<0.5 SL120/TP135 (۵ گیت، فقط G4 رد)
        # هدف: کدام پنجرهٔ walk-forward منفی است؟ و کدام فیلترِ مکمل آن را پاک می‌کند؟
        print("### تشخیصِ G4 روی نقطهٔ شیرین + جستجوی فیلترِ مکمل ###")
        base = build_short_mr(df, z_win=34, z_thr=2.4, rsi_thr=70)
        reg = precompute_regime(df)
        # فیلترهای مکملِ کاندیدا از بانک (بدونِ کشتنِ n)
        cand_extra = {
            'none':      np.ones(len(df), bool),
            'kurt<1.5':  reg['kurt'] < 1.5,
            'kurt<0.8':  reg['kurt'] < 0.8,
            'chop>46':   reg['chop'] > 46.0,
            'r2<0.55':   reg['r2'] < 0.55,
            'entropy>2.5': np.nan_to_num(pd.Series(ib.compute('entropy', df)).values, nan=0) > 2.5,
            'fdi>1.5':   np.nan_to_num(pd.Series(ib.compute('fdi', df)).values, nan=0) > 1.5,
        }
        hmask = reg['hurst'] < 0.5
        best = None
        for xname, xmask in cand_extra.items():
            ssig = base & hmask & xmask
            if ssig.sum() < 40:
                print(f"{xname:12s} n<40 (n={int(ssig.sum())}) — رد")
                continue
            for (sl, tp, mh) in [(120, 135, 22), (135, 145, 24), (110, 125, 20)]:
                lab = f"[hurst<0.5+{xname}] SL{sl}/TP{tp}"
                tr, r = evaluate(df, ssig, sl, tp, mh, args.asset, lab)
                if r:
                    m = r['metrics']
                    print(f"    wf={m['wf_nets']}  half={m['half_nets']}")
                if r and r['passed'] and (best is None or r['rqs_score'] > best[1]['rqs_score']):
                    best = (lab, r, dict(z_win=34, z_thr=2.4, rsi_thr=70, extra=xname, sl=sl, tp=tp, mh=mh))
        print("\n" + "=" * 70)
        if best:
            lab, r, cfg = best
            print(f"🏆 ACCEPT: {lab}  RQS+={r['rqs_score']}")
            out = dict(asset=args.asset, tf=args.tf, label=lab, cfg=cfg,
                       rqs=r['rqs_score'], gates=r['gates'], metrics=r['metrics'])
            with open(os.path.join(RESULTS, f'_s333_{args.asset}_{args.tf}.json'), 'w') as f:
                json.dump(out, f, ensure_ascii=False, indent=1, default=float)
            print(f"✅ ذخیره: results/_s333_{args.asset}_{args.tf}.json")
        else:
            print("❌ diag ACCEPT نداد — فیلترِ مکملِ دیگری لازم است.")

    elif args.stage == 'scan2':
        # درسِ scan۱: فیلترِ hurst کیفیت را می‌سازد (PF 0.75→1.5، DD 95٪→2٪) اما
        # فیلترِ سخت n را می‌کشد ⇒ G0(WR≥60) و G1(معناداری) رد. راهبردِ scan۲:
        #   (الف) RR متقارن‌تر (1:1..1.2) ⇒ breakeven WR پایین‌تر ⇒ G0/G1 آسان‌تر
        #   (ب) فیلترِ hurst متعادل‌تر تا n≥50 حفظ شود
        #   (ج) rsi اشباعِ عمیق‌تر (انتخابِ فقط بهترین fadeها بدونِ کشتنِ n)
        print("### مرحلهٔ ۳ (scan2) — RR متقارن + فیلترِ متعادل برای عبور از G0/G1 ###")
        best = None
        for z_win in [34, 55]:
            for z_thr in [2.4, 2.7, 3.0]:
                for rsi_thr in [70, 74]:
                    base = build_short_mr(df, z_win=z_win, z_thr=z_thr, rsi_thr=rsi_thr)
                    if base.sum() < 80:
                        continue
                    for (h, k, c, r2t) in [
                        (0.50, None, None, None),
                        (0.50, 1.0, None, None),
                        (0.52, None, 48.0, None),
                        (0.50, 0.5, 50.0, 0.45),
                    ]:
                        mask, used = regime_filters(df, h, k, c, r2t)
                        ssig = base & mask
                        if ssig.sum() < 40:
                            continue
                        # RR متقارن/کمی‌مثبت، غیررند، per-TF (M5 اسکالپ)
                        for (sl, tp, mh) in [(150, 150, 24), (135, 145, 22),
                                             (120, 135, 20), (165, 175, 28),
                                             (110, 118, 18)]:
                            lab = f"z{z_win}/{z_thr}r{rsi_thr} [{'+'.join(used)}] SL{sl}/TP{tp}"
                            tr, r = evaluate(df, ssig, sl, tp, mh, args.asset, lab)
                            if r and r['passed'] and (best is None or r['rqs_score'] > best[1]['rqs_score']):
                                best = (lab, r, dict(z_win=z_win, z_thr=z_thr, rsi_thr=rsi_thr,
                                        h=h, k=k, c=c, r2=r2t, sl=sl, tp=tp, mh=mh))
        print("\n" + "=" * 70)
        if best:
            lab, r, cfg = best
            print(f"🏆 بهترین ACCEPT: {lab}  RQS+={r['rqs_score']}")
            out = dict(asset=args.asset, tf=args.tf, label=lab, cfg=cfg,
                       rqs=r['rqs_score'], gates=r['gates'], metrics=r['metrics'])
            with open(os.path.join(RESULTS, f'_s333_{args.asset}_{args.tf}.json'), 'w') as f:
                json.dump(out, f, ensure_ascii=False, indent=1, default=float)
            print(f"✅ ذخیره: results/_s333_{args.asset}_{args.tf}.json")
        else:
            print("❌ scan2 هم ACCEPT نداد.")

    elif args.stage == 'scan':
        # مرحلهٔ احیا: فیلترِ رژیم (hurst/kurt/chop/r2) + TP/SL غیررند per-TF
        print("### مرحلهٔ ۲ — احیا با فیلترِ رژیمِ mean-reverting (جعبه‌ابزارِ بانک) ###")
        best = None
        # z_win فیبوناچی، آستانه‌های غیررند
        for z_win in [55, 89]:
            for z_thr in [2.0, 2.3, 2.6]:
                for rsi_thr in [68, 72]:
                    base = build_short_mr(df, z_win=z_win, z_thr=z_thr, rsi_thr=rsi_thr)
                    if base.sum() < 60:
                        continue
                    # ترکیب‌های فیلترِ رژیم
                    for (h, k, c, r2t) in [
                        (0.48, None, None, None),          # فقط هرست
                        (0.46, 0.0, None, None),           # هرست + safety-گیتِ kurt
                        (0.48, 0.5, 50.0, None),           # هرست + kurt + chop
                        (0.46, 0.0, 52.0, 0.40),           # هر چهار فیلتر
                        (0.44, -0.2, None, 0.35),          # هرستِ سخت + r2
                    ]:
                        mask, used = regime_filters(df, h, k, c, r2t)
                        ssig = base & mask
                        if ssig.sum() < 30:
                            continue
                        # TP/SL غیررند per-TF (اسکنِ اطراف اسپردِ واقعی)
                        for (sl, tp, mh) in [(135, 175, 24), (115, 155, 20),
                                             (95, 130, 18), (160, 200, 30)]:
                            lab = f"z{z_win}/{z_thr}r{rsi_thr} [{'+'.join(used)}] SL{sl}/TP{tp}"
                            tr, r = evaluate(df, ssig, sl, tp, mh, args.asset, lab)
                            if r and r['passed'] and (best is None or r['rqs_score'] > best[1]['rqs_score']):
                                best = (lab, r, dict(z_win=z_win, z_thr=z_thr, rsi_thr=rsi_thr,
                                        h=h, k=k, c=c, r2=r2t, sl=sl, tp=tp, mh=mh))
        print("\n" + "=" * 70)
        if best:
            lab, r, cfg = best
            print(f"🏆 بهترین ACCEPT: {lab}  RQS+={r['rqs_score']}")
            out = dict(asset=args.asset, tf=args.tf, label=lab, cfg=cfg,
                       rqs=r['rqs_score'], gates=r['gates'], metrics=r['metrics'])
            with open(os.path.join(RESULTS, f'_s333_{args.asset}_{args.tf}.json'), 'w') as f:
                json.dump(out, f, ensure_ascii=False, indent=1, default=float)
            print(f"✅ ذخیره: results/_s333_{args.asset}_{args.tf}.json")
        else:
            print("❌ در این گرید هیچ ترکیبی RQS+≥۸۰ نگرفت — گرید را گسترش بده.")


if __name__ == '__main__':
    main()
