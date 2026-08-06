# -*- coding: utf-8 -*-
"""
راننده‌ی **دسته‌ایِ** ماموریتِ ممیزی — capture → judge → rename → commit
================================================================================

هر لایه یک واحدِ کارِ مستقل است و **بلافاصله** پس از داوری در گیت ثبت می‌شود
(قانونِ «اندک اندک» + HARD-RULE checkpoint). اگر سندباکس وسطِ کار ریست شود،
هر لایه‌ای که تمام شده در گیتهاب هست و از سرگیری از همان‌جا ادامه می‌دهد.

════════════════════════════════════════════════════════════════════════════
سیاستِ حکم برای لایه‌هایی که بازتولید نمی‌شوند
════════════════════════════════════════════════════════════════════════════
اگر اسکریپت وجود نداشته باشد، خطا بدهد، یا هیچ فراخوانیِ موتور ضبط نشود،
حکم `INCOMPLETE` است — **هرگز** ACCEPT. این خودِ سیاستِ اسپک است:
«نبودِ آزمونِ کنترل، شاهدِ وجودِ مهارت نیست.»

`INCOMPLETE` یعنی «این لایه با ابزارِ فعلی قابلِ اثبات نیست»، نه «این لایه بد
است». تفکیکِ این دو برای امانتِ علمی حیاتی است و در نامِ فایل هم دیده می‌شود.

════════════════════════════════════════════════════════════════════════════
`n_trials` — بارِ چندگانگی
════════════════════════════════════════════════════════════════════════════
از `scan.json` (که از خودِ متنِ سندها استخراج شده) گرفته می‌شود؛ **بیشترین**
عددِ ذکرشده انتخاب می‌شود چون کم‌شمردنِ سابقهٔ جست‌وجو دقیقاً «دور زدنِ معیار»
است (اشتباهِ رایجِ ۸). اگر سند عددی نگفته باشد، فالبکِ محافظه‌کارانهٔ ۲۰۰۰
به کار می‌رود که به نفعِ REJECT خطا می‌کند.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RES = ROOT / 'results'
AUD = RES / '_audit_rename'
CAP = AUD / 'captures'
VER = AUD / 'verdicts'
LOG = AUD / 'AUDIT_LEDGER.json'
N_TRIALS_FALLBACK = 2000

VERDICT_TAG = {'ACCEPT': 'ACCEPT', 'POWER-LIMITED': 'POWER-LIMITED',
               'UNPROVEN': 'UNPROVEN', 'REJECT': 'REJECT',
               'INCOMPLETE': 'INCOMPLETE'}


def sh(cmd: str, timeout: int = 600):
    p = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def load_ledger() -> dict:
    if LOG.exists():
        try:
            return json.loads(LOG.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def save_ledger(d: dict):
    LOG.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                   encoding='utf-8')


def sort_key(fname: str):
    m = re.match(r'^S(\d+)([a-z]?)_', fname)
    return (0, int(m.group(1)), m.group(2)) if m else (1, 0, fname)


def pick_n_trials(rec: dict) -> int:
    v = rec.get('n_candidates')
    if isinstance(v, list) and v:
        try:
            return max(int(x) for x in v)
        except Exception:
            pass
    if isinstance(v, (int, float)) and v:
        return int(v)
    return N_TRIALS_FALLBACK


def clean_name(fname: str) -> tuple:
    """`(sid, StrategyName)` را از نامِ قدیمی درمی‌آورد."""
    stem = fname[:-3] if fname.endswith('.md') else fname
    m = re.match(r'^(S\d+[a-z]?)_(.*)$', stem)
    if not m:
        return None, stem
    sid, rest = m.group(1), m.group(2)
    # دمِ نامِ قدیمی (NetProfit_123 / _82 / _REJECTED / ...) حذف می‌شود
    rest = re.sub(r'_?NetProfit_-?\+?\d+', '', rest)
    rest = re.sub(r'_(REJECTED|ACCEPTED|DEAD|PL|UNPROVEN)$', '', rest, flags=re.I)
    rest = re.sub(r'_-?\d+(_-?\d+)*$', '', rest)
    rest = re.sub(r'_rqs2?-?\S*$', '', rest, flags=re.I)
    parts = [p for p in re.split(r'[_\s]+', rest) if p]
    name = ''.join(w[:1].upper() + w[1:] for w in parts) or 'Layer'
    return sid, name


PAIR_TAG = {'XAUUSD': 'Xauusd', 'EURUSD': 'Eurusd', 'AUDUSD': 'Audusd',
            'GBPUSD': 'Gbpusd', 'USDJPY': 'Usdjpy', 'DXY': 'Dxy'}
TF_ORDER = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1']


def build_new_name(old: str, verdict_json: dict) -> str:
    """
    نامِ نو طبقِ فرمتِ صریحِ User Note:
        استراتژی_جفت‌ارز_تایم‌فریم(ها)_rqs2_score_status.md
    """
    sid, name = clean_name(old)
    cards = verdict_json.get('cards') or []
    pairs, tfs = [], []
    for c in cards:
        cd = c.get('card', '')
        if '-' not in cd:
            continue
        p, t = cd.split('-', 1)
        if p not in pairs:
            pairs.append(p)
        if t not in tfs:
            tfs.append(t)
    pair_tag = ''.join(PAIR_TAG.get(p, p.capitalize()) for p in pairs) or 'NA'
    tfs.sort(key=lambda t: TF_ORDER.index(t) if t in TF_ORDER else 99)
    tf_tag = ''.join(tfs) or 'NA'
    v = verdict_json.get('headline_verdict', 'INCOMPLETE')
    s = int(round(float(verdict_json.get('headline_score') or 0)))
    tag = VERDICT_TAG.get(v, 'INCOMPLETE')
    return f'{sid}_{name}_{pair_tag}_{tf_tag}_rqs2_{s}_{tag}.md'


def find_current(old: str) -> Path | None:
    """فایل را پیدا می‌کند (ممکن است قبلاً تغییرِ نام یافته باشد)."""
    p = RES / old
    if p.exists():
        return p
    sid, _ = clean_name(old)
    if sid:
        hits = sorted(RES.glob(f'{sid}_*.md'))
        if len(hits) == 1:
            return hits[0]
    return None


def process(rec: dict, ledger: dict) -> str:
    old = rec['file']
    sid, _ = clean_name(old)
    if sid in ledger and ledger[sid].get('done'):
        return 'skip'

    cur = find_current(old)
    if cur is None:
        ledger[sid] = {'done': True, 'status': 'FILE_MISSING', 'old': old}
        return 'missing'

    scripts = [s for s in (rec.get('scripts') or [])
               if (ROOT / 'strategies' / s).exists()]
    n_trials = pick_n_trials(rec)
    print(f'\n════ {sid}  {cur.name[:60]}', flush=True)
    print(f'  scripts={scripts[:2]} n_trials={n_trials}', flush=True)

    vj = None
    # ── ① capture ────────────────────────────────────────────────────────────
    cap_file = None
    for scr in scripts[:2]:
        dest = CAP / (scr.replace('/', '_') + '.capture.json')
        if not dest.exists():
            rc, so, se_ = sh(f'timeout 900 python tools/audit_capture.py {scr}',
                             timeout=960)
            print('  capture:', (so or se_).strip().splitlines()[-1][:120]
                  if (so or se_).strip() else 'no output', flush=True)
        if dest.exists():
            try:
                cd = json.loads(dest.read_text(encoding='utf-8'))
            except Exception:
                continue
            if cd.get('n_calls'):
                cap_file = dest
                break

    # ── ② judge ──────────────────────────────────────────────────────────────
    if cap_file is not None:
        rc, so, se_ = sh(f'timeout 1800 python tools/audit_judge_capture.py '
                         f'"{cap_file}" "{cur.name}" {n_trials}', timeout=1900)
        print((so or '').rstrip()[-900:], flush=True)
        vpath = VER / (cur.name.replace('.md', '') + '.json')
        if vpath.exists():
            try:
                vj = json.loads(vpath.read_text(encoding='utf-8'))
            except Exception:
                vj = None

    if vj is None or not (vj.get('cards')):
        vj = {'layer': cur.name, 'headline_verdict': 'INCOMPLETE',
              'headline_score': 0.0, 'cards': [],
              'reason': ('no engine call captured / script failed — not '
                         'reproducible with current harness'),
              'n_trials': n_trials}
        vpath = VER / (cur.name.replace('.md', '') + '.json')
        vpath.write_text(json.dumps(vj, ensure_ascii=False, indent=1),
                         encoding='utf-8')
        print('  -> INCOMPLETE (not reproducible)', flush=True)

    # ── ③ rename ─────────────────────────────────────────────────────────────
    new = build_new_name(cur.name, vj)
    verdict = vj.get('headline_verdict')
    score = vj.get('headline_score')
    if new != cur.name:
        rc, so, se_ = sh(f'git mv "{cur.relative_to(ROOT)}" "results/{new}"')
        if rc != 0:
            print('  git mv FAILED:', se_[:200], flush=True)

    # ── ④ commit + push (چرخهٔ اجباریِ checkpoint) ───────────────────────────
    ledger[sid] = {'done': True, 'old': old, 'new': new,
                   'verdict': verdict, 'score': score,
                   'cards': [{'card': c.get('card'), 'verdict': c.get('verdict'),
                              'score': c.get('rqs2_score'),
                              'n': (c.get('metrics') or {}).get('n_trades')}
                             for c in (vj.get('cards') or [])]}
    save_ledger(ledger)
    sh('git add -A results/')
    msg = (f'Audit {sid}: {verdict}/{score} — renamed to {new}')
    sh(f'git commit -q -m "{msg}"')
    rc, so, se_ = sh('git push -q origin main', timeout=180)
    if rc != 0:
        print('  ⚠️ PUSH FAILED — stopping per HARD-RULE:', se_[:300],
              flush=True)
        return 'push_failed'
    print(f'  ✅ {verdict}/{score} -> {new}', flush=True)
    return 'ok'


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    scan = json.loads((AUD / 'scan.json').read_text(encoding='utf-8'))
    scan.sort(key=lambda r: sort_key(r['file']))
    ledger = load_ledger()
    n = 0
    for rec in scan:
        if n >= limit:
            break
        sid, _ = clean_name(rec['file'])
        if sid in ledger and ledger[sid].get('done'):
            continue
        r = process(rec, ledger)
        if r == 'push_failed':
            print('STOPPING: push failure must be resolved first.')
            return 1
        if r in ('ok', 'missing'):
            n += 1
    print(f'\n══ batch finished: {n} layers processed ══')
    return 0


if __name__ == '__main__':
    sys.exit(main())
