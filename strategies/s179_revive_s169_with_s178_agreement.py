# -*- coding: utf-8 -*-
"""
S179 — احیای استراتژیِ سوختهٔ S169 (Spike-and-Channel LONG طلا) با «فیلترِ توافقِ S178»
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪ برای هر لایه.

پاسخِ عملی به پرسشِ روش‌شناختیِ کاربر + راهِ دومِ پروژه (زنده‌کردنِ استراتژیِ سوخته):

  S169 (Spike-and-Channel LONG طلا) رد شد چون «سهمِ مستقلِ» آن WR≈33.9٪ و walk-forward
  ناپایدار داشت (سوخت). S178 (Two-Bar Reversal LONG طلا) یک لایهٔ *پذیرفته* است که در
  آزمونِ agreement-filter نشان داد حضورِ اخیرش WR را +۴~۷pp بالا می‌برد.

  فرضیه: «فیلترِ توافقِ S178» می‌تواند معاملاتِ کم‌کیفیتِ S169 را حذف کند و سهمِ مستقلِ
  آن را از WR<40 به WR≥40 با walk-forward پایدار برساند ⇒ لایهٔ سوخته به رکورد بازگردد.

روش (همه causal, shift-safe):
  1) سیگنالِ خامِ S169 LONG طلا (کاندیدِ برنده: ema10/30, spk3×1.5, cw20).
  2) سهمِ مستقل: حذفِ recent-۱۲ کندلِ اجتماعِ زمان-محورِ طلا (که S169 با آن‌ها همپوشان بود).
  3) فیلترِ توافقِ S178: نگه‌داشتنِ فقط سیگنال‌هایی که در w کندلِ اخیر یک two-bar-reversalِ
     S178 رخ داده (تأییدِ برگشتِ دو-کندلی).
  4) گیتِ کاملِ ۴-گانه: net>0, WR≥40, هر دو نیمه, walk-forward 4/4, n≥30.

خروجی: چاپِ کنسول + results/_s179_revive_s169.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S            # load, lastn, sim, stats, halves
import s174_brooks_sell_climax_reversal as SC   # walk_forward
import s174_finalize as F                    # time_drift_long, independent_share, bar_overlap_pct
import s178_brooks_two_bar_reversal as T
import s169_brooks_spike_channel as SP

WR_FLOOR = 40.0
OVERLAP_BARS = 12

# کاندیدِ برندهٔ S169 (از فایلِ REJECTED)
S169 = dict(asset='XAUUSD', side='long', ema_fast=10, ema_slow=30,
            spike_len=3, spike_atr_mult=1.5, channel_window=20, sl=200, tp=300, mh=32)
# فیلترِ S178 (برندهٔ مستقل)
S178CFG = dict(side='long', ema_fast=10, ema_slow=30, body_frac=0.6, size_tol=1.0, lb=40)


def s169_long_signal(df):
    le, sh = SP.detect_spike_channel_events(df, S169['ema_fast'], S169['ema_slow'],
                                            S169['spike_len'], S169['spike_atr_mult'],
                                            S169['channel_window'])
    return pd.Series(le).shift(1).fillna(False).to_numpy()   # causal


def gate(df, sig, asset, sl, tp, mh, label):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return dict(label=label, n=(r['n'] if r else 0), ok=False, reason='n<30')
    hv = S.halves(df, sig, z, sl, tp, mh, asset)
    wf = SC.walk_forward(df, sig, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    ok = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(label=label, net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None, h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok, ok=ok)


def main():
    print("=" * 100)
    print("S179 — احیای S169 (Spike-Channel LONG طلا) با «فیلترِ توافقِ S178»")
    print("گیت: net>0, WR≥40, هر دو نیمه, walk-forward 4/4, n≥30. هدف=سودِ خالص.")
    print("=" * 100)

    asset = S169['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}\n")

    s169 = s169_long_signal(df)
    s178 = T.two_bar_reversal_signals(df, S178CFG['side'], S178CFG['body_frac'],
                                      S178CFG['size_tol'], S178CFG['lb'],
                                      S178CFG['ema_fast'], S178CFG['ema_slow'])
    td = F.time_drift_long(df)
    print(f"سیگنال‌ها: S169={int(s169.sum())}  S178={int(s178.sum())}  time-drift={int(td.sum())}\n")

    # (1) خامِ S169
    raw = gate(df, s169, asset, S169['sl'], S169['tp'], S169['mh'], 'S169 raw')
    print(f"S169 خام        : net={raw.get('net'):+.0f} WR={raw.get('wr')}% n={raw['n']} "
          f"PF={raw.get('pf')} WF_ok={raw.get('wf_ok')}")

    # (2) سهمِ مستقل (خارج از پنجره‌های زمان-محور) — این همان چیزی است که سوخت
    indep = F.independent_share(s169, td)
    ri = gate(df, indep, asset, S169['sl'], S169['tp'], S169['mh'], 'S169 indep')
    print(f"S169 مستقل (سوخته): net={ri.get('net'):+.0f} WR={ri.get('wr')}% n={ri.get('n')} "
          f"PF={ri.get('pf')} WF_ok={ri.get('wf_ok')} => {'OK' if ri.get('ok') else 'سوخته/رد'}")

    # (3) فیلترِ توافقِ S178 روی سهمِ مستقلِ S169
    print("\nفیلترِ توافقِ S178 (نگه‌داشتنِ سیگنال‌هایی که S178 اخیراً تأیید کرده):")
    best = None; scan = []
    for w in (6, 12, 24, 48, 96):
        recent = pd.Series(s178.astype(float)).rolling(w, min_periods=1).max().to_numpy() > 0
        filt = indep & recent
        nf = int(filt.sum())
        g = gate(df, filt, asset, S169['sl'], S169['tp'], S169['mh'], f'indep∧S178(w={w})')
        d_wr = round(g['wr'] - ri['wr'], 2) if (g.get('wr') is not None and ri.get('wr') is not None) else None
        tag = '✅ گیت‌پاس' if g.get('ok') else ('WR<40' if g.get('wr') and g['wr'] < 40 else ('n<30' if nf < 30 else 'WF/نیمه رد'))
        print(f"  w={w:2d}: net={_f(g.get('net'))} WR={_f(g.get('wr'),'%')} n={nf} "
              f"PF={g.get('pf')} ΔWR={d_wr} WF_ok={g.get('wf_ok')} {tag}")
        scan.append(dict(w=w, res=g, d_wr=d_wr))
        if g.get('ok') and (best is None or g['net'] > best['res']['net']):
            best = dict(w=w, res=g)

    # (4) فیلترِ توافق روی خامِ کاملِ S169 (نه فقط مستقل) — برای مقایسه
    print("\nفیلترِ توافق روی *کلِ* S169 (نه فقط مستقل):")
    for w in (24, 48):
        recent = pd.Series(s178.astype(float)).rolling(w, min_periods=1).max().to_numpy() > 0
        filt = s169 & recent
        g = gate(df, filt, asset, S169['sl'], S169['tp'], S169['mh'], f'S169∧S178(w={w})')
        print(f"  w={w:2d}: net={_f(g.get('net'))} WR={_f(g.get('wr'),'%')} n={g.get('n')} "
              f"WF_ok={g.get('wf_ok')} => {'OK ✅' if g.get('ok') else 'رد'}")

    print("\n" + "=" * 100)
    if best:
        g = best['res']
        print(f"✅ احیا موفق! (w={best['w']}) سهمِ مستقلِ S169 پس از فیلترِ توافقِ S178:")
        print(f"   net={g['net']:+.0f} WR={g['wr']}% n={g['n']} PF={g['pf']} WF={'/'.join(f'{x[0]:+.0f}' for x in g['wf'])}")
        print(f"   ⇒ لایهٔ سوخته با فیلترِ توافق به رکورد بازمی‌گردد (+${g['net']:,.0f}).")
    else:
        print("⛔ فیلترِ توافقِ S178 نتوانست S169 را به گیت-پاسِ کامل برساند.")
        print("   (WR ممکن است بالا رفته باشد اما walk-forward/n هنوز پاس نمی‌شود.)")
    print("=" * 100)

    out = dict(strategy='S179_revive_s169', s169=S169, s178=S178CFG,
               raw=raw, indep=ri, scan=scan, best_w=(best['w'] if best else None))
    with open('results/_s179_revive_s169.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s179_revive_s169.json")


def _f(x, suf=''):
    return f"{x:+.0f}{suf}" if isinstance(x, (int, float)) else f"{x}{suf}"


if __name__ == '__main__':
    main()
