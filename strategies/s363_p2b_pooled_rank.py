# -*- coding: utf-8 -*-
"""
S363 · پروتکل **P2B — رتبه‌بندیِ مجددِ ترکیبیِ Stouffer**

پیاده‌سازیِ `results/S363_ADDENDUM_P2B_POOLED_STATISTIC_PREREG.md`
(کامیت‌شده **پیش از** نوشتنِ این فایل).

این اسکریپت **هیچ بک‌تستی اجرا نمی‌کند.** همان ۲٬۸۴۷ کاندیدای ذخیره‌شده در
`P2_PARTIAL.jsonl` را با آماره‌ای دیگر رتبه‌بندی می‌کند. تنها چیزی که عوض
می‌شود «آماره» است، نه داده، نه هندسه، نه آستانه‌ها. این تضمین می‌کند که هر
تفاوتی در نتیجه، منشأش آماره است و نه یک تغییرِ پنهانِ دیگر.

ترتیبِ اجرا **اجباری** است و در کد هم همان ترتیب پیاده شده:

    گامِ ۱ →  محاسبهٔ توانِ پیشینی  →  اگر < 0.20 ⇒ خودلغوی، خروج
    گامِ ۲ →  رتبه‌بندی

اگر گامِ ۲ پیش از گامِ ۱ می‌آمد، دیدنِ رتبه‌بندی می‌توانست انتخابِ سد را
آلوده کند. §۳ الحاقیه صریحاً این ترتیب را الزام کرده است.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = "results/_scan_S363"
PARTIAL = os.path.join(OUT, "P2_PARTIAL.jsonl")
DISCOVERY = os.path.join(OUT, "P2_DISCOVERY.json")
LOCK = os.path.join(OUT, "P2_LOCK.json")

# ═══════════ پارامترهای منجمدِ §۳ الحاقیهٔ P2B (تغییرناپذیر) ═══════════
Z_POOL_BAR = 2.58          # معادلِ p یک‌سویه = 0.005
MIN_Z_SIDE = 0.0           # قیدِ جهان‌شمولیِ کیفی: هر ۷ کارت باید مثبت باشند
POWER_ABORT = 0.20         # قاعدهٔ خودالزام §۳


def load_candidates():
    """۲٬۸۴۷ کاندیدا از حافظهٔ نهانِ شاردیِ P2 — بدونِ هیچ بازمحاسبه‌ای."""
    cands = []
    with open(PARTIAL) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cands.extend(rec.get('cands', []))
    return cands


def card_weights(cards):
    """`w_c = √n_c` با `n_c` = کلِ سیگنال‌های **بخشِ کشفِ** آن کارت.

    چرا `n_keep + n_drop` و نه `n_keep`؟
    ------------------------------------
    چون `n_keep + n_drop` برای هر کارت **ثابت** است (کلِ سیگنال‌های کشف) و به
    کاندیدا وابسته نیست. اگر وزن را از `n_keep` می‌گرفتم، وزن‌ها با کاندیدا
    عوض می‌شدند و یک کاندیدا می‌توانست با نگه‌داشتِ بیشترِ سیگنال‌های یک کارتِ
    خوش‌شانس، **وزنِ خودش را بسازد** — یعنی درجهٔ آزادیِ پنهانی که آماره را
    قابلِ‌بازی می‌کرد. با تعریفِ فعلی، وزن‌ها خاصیتِ *کارت*اند نه *کاندیدا*.
    """
    return {c: float(np.sqrt(n)) for c, n in cards.items()}


def z_pool_of(cand, w):
    """ترکیبِ Stouffer وزنی. علامت حفظ می‌شود ⇒ کارتِ منفی، سهمِ منفی می‌دهد."""
    num = 0.0
    den = 0.0
    for card, v in cand['per_card'].items():
        wc = w[card]
        num += wc * v['z']
        den += wc * wc
    return num / np.sqrt(den)


def prior_power(ref, w, verbose=True):
    """گامِ ۱ — توانِ پیشینیِ آمارهٔ جدید، پیش از هر رتبه‌بندی‌ای.

    تحتِ فرضیهٔ مقابل «اثرهای مشاهده‌شدهٔ P2 واقعی‌اند»:

        z_c  ~  N(δ_c, 1)                      δ_c = z مشاهده‌شدهٔ همان کارت
        Z_pool ~ N(Σ w_c δ_c / √(Σ w_c²), 1)

        توان = P(Z_pool ≥ 2.58) × P(همهٔ z_c > 0)
             = [1 − Φ(2.58 − μ_pool)] × Π_c Φ(δ_c)

    **کاندیدای مرجع عمداً برندهٔ P2 است** (`argmax z_min`)، نه برندهٔ P2B.
    اگر توان را روی برندهٔ P2B حساب می‌کردم، عددی پس‌رویدادی می‌شد و مقایسه با
    `0.0039`ِ P2 بی‌معنا. با مرجعِ یکسان، دو عدد مستقیماً قابلِ‌مقایسه‌اند.
    """
    deltas = {c: v['z'] for c, v in ref['per_card'].items()}
    num = sum(w[c] * d for c, d in deltas.items())
    den = np.sqrt(sum(w[c] ** 2 for c in deltas))
    mu_pool = num / den

    p_pool = float(1.0 - stats.norm.cdf(Z_POOL_BAR - mu_pool))
    p_sign = float(np.prod([stats.norm.cdf(d) for d in deltas.values()]))
    power = p_pool * p_sign

    if verbose:
        print(f"\n{'='*92}")
        print("گامِ ۱ — محاسبهٔ توانِ پیشینی (پیش از هر رتبه‌بندی‌ای)")
        print(f"{'='*92}")
        print(f"  کاندیدای مرجع = برندهٔ P2: {ref['indicator']} "
              f"{ref['direction']} q={ref['quantile']}")
        print(f"  {'card':13s}{'delta_z':>10}{'w_c':>9}")
        for c in sorted(deltas):
            print(f"  {c:13s}{deltas[c]:10.3f}{w[c]:9.2f}")
        print(f"\n  mu_pool = Σw·δ/√Σw² = {mu_pool:.4f}")
        print(f"  P(Z_pool ≥ {Z_POOL_BAR})      = {p_pool:.4f}")
        print(f"  P(همهٔ z_c > 0)        = {p_sign:.4f}")
        print(f"  ── توانِ P2B          = {power:.4f}")
        print(f"     توانِ P2 (مرجع)     = 0.0039")
        print(f"     نسبتِ بهبود         = {power/0.0039:.1f}×")
        print(f"  قاعدهٔ خودالزام: لغو اگر توان < {POWER_ABORT}  ⇒  "
              f"{'ABORT' if power < POWER_ABORT else 'ادامه مجاز'}")
    return dict(reference=f"{ref['indicator']}|{ref['direction']}|{ref['quantile']}",
                deltas={c: round(d, 4) for c, d in deltas.items()},
                mu_pool=round(float(mu_pool), 4),
                p_pool_term=round(p_pool, 6), p_sign_term=round(p_sign, 6),
                power=round(power, 6), power_p2_reference=0.0039,
                abort_threshold=POWER_ABORT, aborted=bool(power < POWER_ABORT))


def main():
    if not os.path.exists(PARTIAL):
        sys.exit(f"missing {PARTIAL} — P2 discovery must run first.")

    meta = json.load(open(DISCOVERY))['card_meta']
    cands = load_candidates()

    # n_c = کلِ سیگنال‌های بخشِ کشف (ثابت برای هر کارت)
    any_c = cands[0]['per_card']
    n_disc = {c: v['n_keep'] + v['n_drop'] for c, v in any_c.items()}
    w = card_weights(n_disc)

    print(f"{'='*92}")
    print("S363 · P2B — رتبه‌بندیِ مجددِ Stouffer روی همان ۲٬۸۴۷ کاندیدا")
    print(f"  پیش‌ثبت: results/S363_ADDENDUM_P2B_POOLED_STATISTIC_PREREG.md")
    print(f"  هیچ بک‌تستِ جدیدی اجرا نمی‌شود · هیچ داده‌ای بازمحاسبه نمی‌شود")
    print(f"{'='*92}")
    print(f"  کاندیداها = {len(cands)}")
    print(f"  {'card':13s}{'n_discovery':>13}{'w_c=√n':>10}")
    for c in sorted(n_disc):
        print(f"  {c:13s}{n_disc[c]:13d}{w[c]:10.2f}")

    # ─────────────────── گامِ ۱: توانِ پیشینی (اجباری، اول) ───────────────────
    ref = max(cands, key=lambda d: d['z_min'])       # = برندهٔ P2، قطعی
    pw = prior_power(ref, w)

    if pw['aborted']:
        payload = dict(protocol='P2B', decision='SELF_ABORTED_UNDERPOWERED',
                       power=pw)
        with open(os.path.join(OUT, 'P2B_RANKING.json'), 'w') as f:
            json.dump(payload, f, indent=1, ensure_ascii=False)
        print("\n⛔ P2B خودلغو شد (توان < 0.20). هیچ رتبه‌بندی‌ای انجام نشد.")
        return

    # ─────────────────────────── گامِ ۲: رتبه‌بندی ───────────────────────────
    print(f"\n{'='*92}")
    print("گامِ ۲ — رتبه‌بندی با Z_pool، مشروط به قیدِ جهان‌شمولیِ min z_c > 0")
    print(f"{'='*92}")

    scored = []
    for c in cands:
        zs = [v['z'] for v in c['per_card'].values()]
        scored.append(dict(
            indicator=c['indicator'], direction=c['direction'],
            quantile=c['quantile'], z_pool=round(float(z_pool_of(c, w)), 4),
            z_min=round(float(min(zs)), 4), z_mean=round(float(np.mean(zs)), 4),
            all_positive=bool(min(zs) > MIN_Z_SIDE), per_card=c['per_card']))

    eligible = [s for s in scored if s['all_positive']]
    scored.sort(key=lambda d: -d['z_pool'])
    eligible.sort(key=lambda d: -d['z_pool'])

    print(f"  کاندیداهای واجدِ قیدِ جهان‌شمولی (همهٔ ۷ کارت مثبت): "
          f"{len(eligible)} / {len(scored)}")
    zp_all = np.array([s['z_pool'] for s in scored])
    print(f"  توزیعِ Z_pool روی همه: p50={np.percentile(zp_all,50):+.3f} "
          f"p90={np.percentile(zp_all,90):+.3f} "
          f"p99={np.percentile(zp_all,99):+.3f} max={zp_all.max():+.3f}")

    print(f"\n  === ۱۵ کاندیدای برترِ واجدِ شرط (رتبه‌بندی با Z_pool) ===")
    print(f"  {'#':>3} {'indicator':22s}{'dir':11s}{'q':>5}"
          f"{'Z_pool':>9}{'z_min':>8}{'z_mean':>8}")
    for i, s in enumerate(eligible[:15], 1):
        print(f"  {i:3d} {s['indicator']:22s}{s['direction']:11s}"
              f"{s['quantile']:5.2f}{s['z_pool']:9.3f}{s['z_min']:8.3f}"
              f"{s['z_mean']:8.3f}")

    if not eligible:
        decision, winner = 'P2B_FAIL_NO_ELIGIBLE', None
    else:
        winner = eligible[0]
        decision = ('P2B_PASS_LOCK' if winner['z_pool'] >= Z_POOL_BAR
                    else 'P2B_FAIL_BAR')

    print(f"\n{'='*92}")
    if winner:
        print(f"  بهترین Z_pool واجدِ شرط = {winner['z_pool']:.3f}  "
              f"(سد = {Z_POOL_BAR})")
    print(f"  حکم: {decision}")
    print(f"{'='*92}")

    payload = dict(
        protocol='P2B',
        prereg='results/S363_ADDENDUM_P2B_POOLED_STATISTIC_PREREG.md',
        statistic='stouffer_sqrt_n_weighted', z_pool_bar=Z_POOL_BAR,
        universality_constraint='min_z_card > 0',
        n_candidates=len(scored), n_eligible=len(eligible),
        card_n_discovery=n_disc, card_weights={k: round(v, 4) for k, v in w.items()},
        power=pw, decision=decision, winner=winner, top30=eligible[:30])
    with open(os.path.join(OUT, 'P2B_RANKING.json'), 'w') as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    print(f"→ saved {OUT}/P2B_RANKING.json")

    if decision == 'P2B_PASS_LOCK':
        lock = dict(
            protocol='P2', locked_by='P2B',
            prereg='results/S363_ADDENDUM_P2B_POOLED_STATISTIC_PREREG.md',
            indicator=winner['indicator'], direction=winner['direction'],
            quantile=winner['quantile'], z_pool=winner['z_pool'],
            thresholds={c: v['thr'] for c, v in winner['per_card'].items()},
            discovery_detail=winner['per_card'])
        with open(LOCK, 'w') as f:
            json.dump(lock, f, indent=1, ensure_ascii=False)
        print(f"→ 🔒 locked  {LOCK}")


if __name__ == '__main__':
    main()
