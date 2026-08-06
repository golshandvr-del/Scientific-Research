# -*- coding: utf-8 -*-
"""
موتورِ اجراییِ ماموریتِ ممیزی — **داوریِ لایه‌های آرشیو، یکی‌یکی، با ثبتِ فوری**
================================================================================
این فایل «مغزِ عملیاتی» ماموریت است. سه مسئولیت دارد و بیش از آن نه:

  ① یک لایهٔ آرشیو را از **معامله‌های واقعیِ بازتولیدشده‌اش** برمی‌دارد.
  ② با موتورِ رسمیِ `engine/rqs2.py` روی **هر کارت جداگانه** داوری می‌کند
     (قانونِ MTF)، و حکم/نمرهٔ سرتیتر را می‌سازد.
  ③ نتیجه را **بلافاصله** روی دیسک می‌نشاند (`_audit_rename/verdicts/`) تا
     ریستِ سندباکس هیچ چیزی را نبرد — قانونِ «اندک اندک».

════════════════════════════════════════════════════════════════════════════
منبعِ معامله‌ها: چرا CSV و نه فراخوانیِ مستقیمِ لایه
════════════════════════════════════════════════════════════════════════════
لایه‌های آرشیو معماری‌های ناهمگونی دارند: بعضی ML سنگین با walk-forward
(`S69`)، بعضی قاعده‌ای خالص (`S382`)، بعضی چند-دارایی. یک امضای واحد برای
فراخوانیِ همه وجود ندارد. اما **همه** در نهایت یک چیز تولید می‌کنند:
جدولِ معامله‌ها.

پس قرارداد این است: هر لایه معامله‌هایش را به‌صورتِ CSV با ستون‌های
`entry_bar, exit_bar, outcome, pnl_pip, sl_pip, tp_pip, direction` می‌دهد، و
این موتور از همان‌جا داوری می‌کند. مزیتِ حیاتی: **معامله‌ها یک‌بار تولید
می‌شوند و بارها داوری می‌شوند**، در حالی که بازتولیدِ یک لایهٔ ML ده‌ها دقیقه
می‌برد و سندباکسِ ناپایدار ممکن است وسطش برود.

⚠️ یک قیدِ صحتِ غیرقابلِ‌مذاکره: CSVِ معامله‌ای که مکانیکِ ورودش با مدلِ صفر
هم‌تراز نباشد، `H3` را بی‌معنا می‌کند (سندِ
`_audit_rename/CALIBRATION_FINDING.md`). پس هر CSV باید ستونِ `mech` داشته
باشد که می‌گوید معامله‌ها با چه مکانیکی ساخته شده‌اند، و نولِ متناظر با همان
مکانیک ساخته شود. اگر `mech` نبود، مکانیکِ رسمیِ `scalp_engine` فرض می‌شود و
این فرض در خروجی **صریح ثبت** می‌شود، پنهان نمی‌ماند.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rqs2 as R                       # noqa: E402
from tools.audit_rqs2_rejudge import (             # noqa: E402
    load_card, bar_time_of, canonical_null, resolve_max_hold,
    pick_headline, new_filename, PERM_K, SEED, N_TRIALS_FALLBACK)

VERDICT_DIR = os.path.join(ROOT, 'results', '_audit_rename', 'verdicts')


# ═══════════════════════════════════════════════════════════════════════════
#  داوریِ یک کارت از جدولِ معاملهٔ آماده
# ═══════════════════════════════════════════════════════════════════════════
def judge_trades(tr: pd.DataFrame, pair: str, tf: str, *,
                 n_trials: int, max_hold=None, k: int = PERM_K,
                 seed: int = SEED, holdout_frac: float = 0.30,
                 n_sig_by_side: dict | None = None) -> dict:
    """
    یک جدولِ معاملهٔ **واقعیِ بازتولیدشده** را با معیارِ رسمی داوری می‌کند.

    ورودیِ `tr` باید ستون‌های `outcome, pnl_pip, sl_pip, tp_pip, direction,
    entry_bar, exit_bar` را داشته باشد.

    چهار ورودیِ اجباریِ اسپک، و رفتارِ صریح در نبودِ هرکدام:
      · `tp_pip`  نباشد ⇒ `H2 = UNKNOWN` ⇒ حکم `INCOMPLETE` (نه ACCEPT).
      · `null`    نباشد ⇒ `H3/H4/H5 = UNKNOWN` ⇒ `INCOMPLETE`.
      · `n_trials` نباشد ⇒ فالبکِ **بزرگِ** محافظه‌کارانه (به نفعِ REJECT).
      · `holdout` نباشد ⇒ `H7 = UNKNOWN`.
    این سیاست عیناً §اسپک است: «نبودِ آزمونِ کنترل، شاهدِ وجودِ مهارت نیست.»
    """
    card = f'{pair}-{tf}'
    if tr is None or len(tr) == 0:
        return {'card': card, 'verdict': 'REJECT', 'rqs2_score': 0.0,
                'n_trades': 0, 'reason': 'zero trades'}

    df = load_card(pair, tf)
    if df is None or len(df) < 500:
        return {'card': card, 'verdict': 'INCOMPLETE', 'rqs2_score': 0.0,
                'reason': 'card data missing'}

    asset = pair
    bt = bar_time_of(df)
    mh = resolve_max_hold(max_hold, len(df))

    sl_med = float(np.nanmedian(tr['sl_pip'])) if 'sl_pip' in tr else None
    tp_med = float(np.nanmedian(tr['tp_pip'])) if 'tp_pip' in tr else None

    # ── مدلِ صفر: به تفکیکِ سمت، با **همان** هندسه و **همان** افقِ لایه ──
    n_by_side = {s: int((tr['direction'] == s).sum()) for s in ('long', 'short')} \
        if 'direction' in tr else {'long': len(tr), 'short': 0}
    sides = tuple(s for s in ('long', 'short') if n_by_side[s] > 0)
    if n_sig_by_side is None:
        # اگر تعدادِ سیگنالِ خام معلوم نباشد، تعدادِ معامله بهترین برآوردِ
        # موجود است. این برآورد **محافظه‌کارانه** است: سیگنالِ خام همیشه
        # ≥ معامله است (قیدِ عدمِ هم‌پوشانی حذف می‌کند)، و نولِ کم‌سیگنال
        # `perm_sd` بزرگ‌تری می‌دهد ⇒ `z` کوچک‌تر ⇒ سخت‌گیرانه‌تر.
        n_sig_by_side = dict(n_by_side)

    nul = None
    if sl_med and tp_med:
        try:
            nul = canonical_null(df, asset, sl_med, tp_med, mh, sides,
                                 n_sig_by_side, k=k, seed=seed)
        except Exception as e:                       # noqa: BLE001
            nul = None
            print(f'    [warn] null failed on {card}: {e}', flush=True)

    split_bar = int(len(df) * (1.0 - holdout_frac))
    r = R.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med, bar_time=bt,
                       null=nul, n_trials=int(n_trials), split_bar=split_bar,
                       close=df['close'].to_numpy(float))
    r['card'] = card
    r['null_built'] = nul is not None
    return r


# ═══════════════════════════════════════════════════════════════════════════
#  ثبتِ فوری — قانونِ «اندک اندک»
# ═══════════════════════════════════════════════════════════════════════════
def save_verdict(layer_file: str, per_card: list, meta: dict) -> str:
    """
    حکمِ یک لایه را **بی‌درنگ** روی دیسک می‌نشاند.

    چرا بی‌درنگ و نه در پایانِ حلقه: سندباکس ناپایدار است و یک‌بار وسطِ همین
    ماموریت ریست شد. هر لایه‌ای که داوری‌اش تمام شده و ثبت نشده باشد، در ریست
    از دست می‌رود و کلِ محاسبهٔ گرانش دوباره باید انجام شود.
    """
    os.makedirs(VERDICT_DIR, exist_ok=True)
    verdict, score = pick_headline(per_card)
    tfs = [c['card'].replace('-', '_').replace('_', '-', 1) for c in per_card
           if c.get('verdict') not in (None,)]
    tfs = [c['card'] for c in per_card]
    rec = {
        'layer_file': layer_file,
        'headline_verdict': verdict,
        'headline_score': round(float(score), 1),
        'proposed_name': new_filename(layer_file, tfs, verdict, score),
        'cards': per_card,
        'meta': meta,
        'judged_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'engine': 'engine/rqs2.py (official)',
        'perm_k': PERM_K, 'seed': SEED,
    }
    stem = layer_file[:-3] if layer_file.endswith('.md') else layer_file
    p = os.path.join(VERDICT_DIR, f'{stem}.json')
    json.dump(rec, open(p, 'w'), ensure_ascii=False, indent=1, default=float)
    return p


def summarize(r: dict) -> str:
    """یک‌خطیِ خوانا از حکمِ یک کارت — برای لاگِ زنده."""
    m = r.get('metrics') or {}
    g = r.get('gates') or {}
    fails = [k for k, v in g.items() if v is False]
    unk = [k for k, v in g.items() if v is None]
    return (f"{r.get('card','?'):<14} {r.get('verdict','?'):<14} "
            f"score={r.get('rqs2_score',0):>5.1f} "
            f"n={m.get('n_trades','?'):>5} wr={m.get('win_rate','?')} "
            f"net={m.get('net_profit','?')} "
            f"fail={','.join(fails) or '-'} unk={','.join(unk) or '-'}")
