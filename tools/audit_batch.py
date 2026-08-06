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

import gc
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RES = ROOT / 'results'
AUD = RES / '_audit_rename'
CAP = AUD / 'captures'
VER = AUD / 'verdicts'
LOG = AUD / 'AUDIT_LEDGER.json'
N_TRIALS_FALLBACK = 2000

# بودجهٔ زمانیِ ضبط (ثانیه). از محیط قابلِ تنظیم است تا پاسِ دومِ صف
# بتواند لایه‌های `DEFERRED` را با بودجهٔ بزرگ‌تر دوباره بیازماید:
#     AUDIT_CAP_BUDGET=1800 python tools/audit_batch.py 200
CAP_BUDGET = int(os.environ.get('AUDIT_CAP_BUDGET', '300'))

VERDICT_TAG = {'ACCEPT': 'ACCEPT', 'POWER-LIMITED': 'POWER-LIMITED',
               'UNPROVEN': 'UNPROVEN', 'REJECT': 'REJECT',
               'INCOMPLETE': 'INCOMPLETE'}


def sh(cmd: str, timeout: int = 600):
    p = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def free_mb() -> int:
    """رمِ آزادِ فعلی (MB). صفر یعنی نامعلوم."""
    try:
        with open('/proc/meminfo') as fh:
            info = {}
            for line in fh:
                k, _, v = line.partition(':')
                info[k.strip()] = v.strip()
        return int(info.get('MemAvailable', '0 kB').split()[0]) // 1024
    except Exception:
        return 0


def wait_for_memory(need_mb: int = 320, tries: int = 30) -> bool:
    """
    قبل از شروعِ لایهٔ بعد، منتظرِ آزاد شدنِ رم می‌ماند.

    ⚠️ چرا لازم است: سندباکس فقط ~۹۸۵MB رم دارد. اندازه‌گیری‌شده: راننده
    بلافاصله بعد از یک ضبطِ سنگین `Killed` شد چون پروسهٔ قبلی هنوز رم را
    آزاد نکرده بود. بدونِ این محافظ، **کلِ صف** با یک لایهٔ سنگین می‌مُرد و
    پیشرفت از دست می‌رفت (همان چیزی که قانونِ «اندک اندک» علیه‌اش هست).
    """
    for _ in range(tries):
        if free_mb() >= need_mb:
            return True
        gc.collect()
        time.sleep(4)
    return free_mb() >= need_mb // 2


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

    # ── ابتدا دمِ فرمتِ **جدید** حذف می‌شود ─────────────────────────────────
    # ⚠️ چرا لازم شد (اندازه‌گیری‌شده): وقتی لایه‌ای برای ممیزیِ مجدد به صف
    # برمی‌گردد، نامش **قبلاً** فرمتِ جدید را دارد
    # (`..._NA_NA_rqs2_0_INCOMPLETE`). اگر این دم شناسایی نشود، `NA`ها به
    # اسمِ استراتژی می‌چسبند و در هر پاس تکرار می‌شوند:
    #     BrooksTwoLegs → BrooksTwoLegsNANA → BrooksTwoLegsNANANANA
    # این یک فسادِ تجمعیِ نام است و باید **قبل** از هر پاک‌سازیِ دیگری
    # خنثی شود.
    rest = re.sub(
        r'_(?:[A-Za-z]+|NA)_(?:[A-Z0-9]+|NA)_rqs2_-?\d+_'
        r'(?:ACCEPT|POWER-LIMITED|UNPROVEN|REJECT|INCOMPLETE)$',
        '', rest, flags=re.I)

    # دمِ نامِ قدیمی (NetProfit_123 / _82 / _REJECTED / ...) حذف می‌شود
    rest = re.sub(r'_?NetProfit_-?\+?\d+', '', rest)
    rest = re.sub(r'_(REJECTED|ACCEPTED|DEAD|PL|UNPROVEN)$', '', rest, flags=re.I)
    rest = re.sub(r'_-?\d+(_-?\d+)*$', '', rest)
    rest = re.sub(r'_rqs2?-?\S*$', '', rest, flags=re.I)
    parts = [p for p in re.split(r'[_\s]+', rest) if p]
    name = ''.join(w[:1].upper() + w[1:] for w in parts) or 'Layer'

    # ترمیمِ فسادِ تجمعیِ پاس‌های قبلی: دنبالهٔ `NA` که به انتهای اسم چسبیده
    # (`BrooksTwoLegsNANA`) معنایی ندارد و باید پاک شود. فقط دنبالهٔ **آخر**
    # حذف می‌شود تا اسم‌های واقعیِ حاوی `NA` (مثلِ `Nasdaq`) آسیب نبینند.
    name = re.sub(r'(?:NA){2,}$', '', name) or 'Layer'
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

    # قبل از هر لایه منتظرِ رمِ کافی می‌مانیم (سندباکسِ ۹۸۵MB)
    if not wait_for_memory():
        print(f'  ⚠️ low memory ({free_mb()}MB) — proceeding cautiously',
              flush=True)

    vj = None
    # ── ① capture ────────────────────────────────────────────────────────────
    # ⚠️ بودجهٔ زمانیِ کوتاه‌ترِ عمدی (`CAP_BUDGET`): لایه‌هایی مثلِ
    # `s166_mtf_rescue` یک جاروبِ MTF با صدها فراخوانی‌اند و به‌تنهایی
    # می‌توانند کلِ صفِ ۱۶۴ لایه‌ای را بخوابانند. اگر لایه‌ای در این بودجه
    # ضبط نشود، **رد نمی‌شود**؛ به `DEFERRED` می‌رود تا در پاسِ دومِ صف با
    # بودجهٔ بزرگ‌تر آزموده شود. این مستقیماً در خدمتِ قانونِ «اندک اندک»
    # است: پیشرفتِ قطعیِ بسیاری از لایه‌ها بر پیشرفتِ نامعلومِ یک لایه اولویت
    # دارد، چون سندباکس هر لحظه ممکن است ریست شود.
    cap_file = None
    timed_out = False
    for scr in scripts[:2]:
        dest = CAP / (scr.replace('/', '_') + '.capture.json')
        if not dest.exists():
            rc, so, se_ = sh(f'timeout {CAP_BUDGET} python '
                             f'tools/audit_capture.py {scr}',
                             timeout=CAP_BUDGET + 60)
            if rc == 124:                      # کدِ خروجِ `timeout`
                timed_out = True
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

    # ── تفکیکِ «کندِ قابلِ تلاشِ مجدد» از «واقعاً بازتولیدناپذیر» ─────────────
    # اگر ضبط فقط به‌خاطرِ بودجهٔ زمانی نیمه‌کاره ماند، این **یافتهٔ علمی
    # نیست** و نباید حکمِ نهایی بگیرد. لایه `DEFERRED` می‌شود، نامش دست
    # نمی‌خورد، و در پاسِ بعدی با بودجهٔ بزرگ‌تر دوباره می‌آید.
    if vj is None or not (vj.get('cards')):
        if cap_file is None and timed_out:
            print(f'  ⏳ DEFERRED (capture exceeded {CAP_BUDGET}s budget) — '
                  f'name unchanged, will retry with larger budget', flush=True)
            ledger[sid] = {'done': False, 'status': 'DEFERRED', 'old': old,
                           'reason': f'capture > {CAP_BUDGET}s'}
            save_ledger(ledger)
            sh('git add -A results/')
            sh(f'git commit -q -m "Audit {sid}: DEFERRED — capture exceeded '
               f'{CAP_BUDGET}s budget, queued for a larger-budget pass"')
            sh('git push -q origin main', timeout=180)
            return

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
