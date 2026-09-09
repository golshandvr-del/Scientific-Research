// integ_s1911_council.mjs — آزمونِ گاردِ «شاهدِ کاذب» در مسیرِ شورا.
//
// چرا این آزمون **جدا** از integ_s1911_card.mjs لازم است:
//   integ_s1911_card ثابت کرد مکانیزمِ نمایشِ کارت درست کار می‌کند: S1911 هرگز
//   primary نمی‌شود و در otherLayers می‌نشیند (چون زیرِ S965 وصل شده). ولی شورا
//   یک مسیرِ **دیگر** است که فقط آرا را **می‌شمارد** و اولویت برایش بی‌معناست.
//   آنجا اندازه‌گیری شد که S1911 در هر ۷ رویدادِ آزمون شمارشِ فعال را +۱ می‌کند
//   (بدترین حالت: SHORT از ۲ به ۳) ⇒ شورا می‌گفت «اجماعِ کامل … لایهٔ دوم هم
//   تأیید کرد ⇒ لاتِ ×۱.۵» در حالی که شاهدِ دومی وجود ندارد. این عیناً همان
//   «شاهدِ کاذب» است: ریسکِ دوبرابر بدونِ اطلاعِ تازه.
//
// این اسکریپت روی خودِ convene() واقعی (نه کپی) می‌سنجد که:
//   ① تلاقیِ S965+S1911 دیگر «تأییدِ دوم» اعلام نمی‌شود، و «۱ شاهدِ مستقل» را
//      صریح می‌گوید + دستور «لاتِ ×۱.۵ را نادیده بگیر».
//   ② همان تلاقی با یک لایهٔ **واقعاً مستقل** (S950) درست ۲ شاهد می‌شمارد.
//   ③ زوجِ منتشرشدهٔ S966⊂S965 هم گرفته می‌شود (رگرسیونِ سابقهٔ ریپو).
//   ④ تلاقیِ لایه‌های مستقل هیچ هشدارِ کاذبی نمی‌گیرد (بی‌اثر بودن روی حالتِ سالم).
//   ⑤ عددِ lotMultiplier **دست‌نخورده** مانده (۱.۵) — گارد فقط متن را صادق کرد،
//      و تغییرِ یک قانونِ سنجیده‌شده بدونِ اندازه‌گیریِ تازه مجاز نیست.
//   ⑥ حالتِ SINGLE و CONFLICT دست‌نخورده‌اند (گارد فقط شاخهٔ UNANIMOUS را لمس کرد).

import fs from 'node:fs'
import { convene } from './dist_parity/council.js'

const CARD = 'XAUUSD-H8'
const L = (code, dir, state = 'ENTRY') => ({ code, name: `layer ${code}`, state, direction: dir })

// CardDecisionِ ساختگی: primary + otherLayers، عینِ شکلی که runCard می‌سازد.
const mk = (primary, others) => ({
  state: primary.state, direction: primary.direction,
  headline: `head ${primary.code}`, reason: 'x',
  sourceLayer: { code: primary.code, name: primary.name },
  otherLayers: others,
})

const cases = [
  {
    id: 'A) S965 + S1911 هم‌جهت — زیرمجموعهٔ ۱۰۰٪ ⇒ باید فقط ۱ شاهدِ مستقل',
    dec: mk(L('S965', 'LONG'), [L('S1911', 'LONG')]),
    want: { consensus: 'UNANIMOUS', independent: 1, mentionsDup: 'S1911⊂S965', tellsIgnoreLot: true },
  },
  {
    id: 'B) S965 + S1911 + S950 — یکی زیرمجموعه، یکی مستقل ⇒ ۲ شاهدِ مستقل',
    dec: mk(L('S950', 'LONG'), [L('S965', 'LONG'), L('S1911', 'LONG')]),
    want: { consensus: 'UNANIMOUS', independent: 2, mentionsDup: 'S1911⊂S965', tellsIgnoreLot: false },
  },
  {
    id: 'C) S965 + S966 — زوجِ منتشرشدهٔ ریپو ⇒ رگرسیون: باید گرفته شود',
    dec: mk(L('S965', 'SHORT'), [L('S966', 'SHORT')]),
    want: { consensus: 'UNANIMOUS', independent: 1, mentionsDup: 'S966⊂S965', tellsIgnoreLot: true },
  },
  // ⚠️ در D و E هیچ زوجِ زیرمجموعه‌ای حاضر نیست، پس گارد **عمداً** متن را لمس
  //    نمی‌کند و همان متنِ تاریخیِ «اجماعِ کامل» می‌آید. اجرای اولِ این اسکریپت
  //    این دو را قرمز کرد، ولی خطا در **انتظارِ من** بود نه در گارد: انتظار داشتم
  //    عبارتِ «N شاهدِ مستقل» همیشه چاپ شود، در حالی که طرحِ درست این است که مسیرِ
  //    سالم دست‌نخورده بماند (کم‌ترین تغییر در رفتارِ موجود). پس معیارِ درست برای
  //    این دو مورد «نبودِ هرگونه هشدار» است، نه «بودنِ شمارشِ مستقل».
  {
    id: 'D) S1911 بدونِ S965 (ابرمجموعه غایب) + S950 ⇒ نباید هشدار بدهد',
    dec: mk(L('S950', 'LONG'), [L('S1911', 'LONG')]),
    want: { consensus: 'UNANIMOUS', independent: null, mentionsDup: null, tellsIgnoreLot: false },
  },
  {
    id: 'E) دو لایهٔ مستقل (S950 + S770) ⇒ هیچ هشدارِ کاذبی نباید بدهد',
    dec: mk(L('S950', 'LONG'), [L('S770', 'LONG')]),
    want: { consensus: 'UNANIMOUS', independent: null, mentionsDup: null, tellsIgnoreLot: false },
  },
  {
    id: 'F) تک‌لایه ⇒ SINGLE دست‌نخورده',
    dec: mk(L('S1911', 'LONG'), []),
    want: { consensus: 'SINGLE', independent: null, mentionsDup: null, tellsIgnoreLot: false },
  },
  {
    id: 'G) تضاد ⇒ CONFLICT دست‌نخورده',
    dec: mk(L('S965', 'LONG'), [L('S950', 'SHORT')]),
    want: { consensus: 'CONFLICT', independent: null, mentionsDup: null, tellsIgnoreLot: false },
  },
]

const rows = []
let pass = 0
for (const c of cases) {
  const v = convene(CARD, c.dec)
  const note = v.note || ''
  const okConsensus = v.consensus === c.want.consensus
  // «۱ شاهدِ مستقل» به‌صورتِ عدد در متن است (فارسی، داخلِ **N شاهدِ مستقل**)
  const okIndep = c.want.independent == null
    ? !note.includes('شاهدِ مستقل')
    : note.includes(`**${c.want.independent} شاهدِ مستقل**`)
  const okDup = c.want.mentionsDup == null
    ? !note.includes('⊂')
    : note.includes(c.want.mentionsDup)
  const okIgnore = c.want.tellsIgnoreLot
    ? note.includes('نادیده بگیرید')
    : !note.includes('نادیده بگیرید')
  const ok = okConsensus && okIndep && okDup && okIgnore
  if (ok) pass++
  rows.push({
    case: c.id, consensus: v.consensus, lotMultiplier: v.lotMultiplier,
    longVotes: v.longVotes, shortVotes: v.shortVotes,
    note, ok, detail: { okConsensus, okIndep, okDup, okIgnore },
  })
  console.log(`${ok ? '✅' : '❌'} ${c.id}\n    consensus=${v.consensus} lot=${v.lotMultiplier}\n    note: ${note}\n`)
}

// ⑤ قانونِ لات باید دست‌نخورده باشد: در هر تلاقیِ UNANIMOUS همان ۱.۵ بماند.
const unan = rows.filter(r => r.consensus === 'UNANIMOUS')
const lotUntouched = unan.length > 0 && unan.every(r => r.lotMultiplier === 1.5)

const checks = {
  // گاردِ آزمونِ پوچ (درسِ integ_s1911_card: صفر موردِ آزمون ⇒ GREENِ دروغین)
  someCasesTested: cases.length > 0 && rows.length === cases.length,
  allCasesPass: pass === cases.length,
  lot_rule_untouched: lotUntouched,
}
const green = Object.values(checks).every(Boolean)

const out = {
  what: 'آزمونِ گاردِ شاهدِ کاذب در مسیرِ شورا (convene واقعی) · XAUUSD-H8',
  why: ('مکانیزمِ نمایشِ کارت همپوشانی را با اولویت حل می‌کند، ولی شورا مسیرِ جدایی '
      + 'است که فقط آرا را می‌شمارد؛ زیرمجموعهٔ ۱۰۰٪ آنجا شمارش را متورم می‌کند و '
      + '«تأییدِ دومِ» کاذب می‌سازد ⇒ ریسکِ دوبرابر بدونِ اطلاعِ تازه.'),
  measured_basis: {
    's1911_subset_of_s965': 'results/_s1911_ckpt/false_witness_h8.json (۸۲ از ۸۲ · jaccard ۰.۵۶۹)',
    'live_path_confirm': 'results/_s1911_ckpt/integ_card_s1911.json (۷ از ۷ رویداد · S965 همیشه حاضر)',
    's966_subset_of_s965': 'عددِ منتشرشدهٔ ریپو، بازتولیدشده به‌عنوانِ کنترلِ ابزار (share ۱۰۰٪ · jaccard ۰.۵۰)',
  },
  passed: `${pass}/${cases.length}`,
  checks, rows,
  lot_rule_untouched: lotUntouched,
  note_on_scope: ('گارد فقط **متنِ** شاخهٔ UNANIMOUS را صادق کرد. عددِ lotMultiplier '
                + 'عمداً دست‌نخورده ماند: آن یک قانونِ سنجیده است و تغییرش نیازمندِ '
                + 'اندازه‌گیریِ مستقل است، نه استنتاج.'),
  verdict: green ? 'GREEN' : 'RED',
}
fs.writeFileSync('../results/_s1911_ckpt/integ_council_s1911.json', JSON.stringify(out, null, 1))
console.log(JSON.stringify({ passed: out.passed, checks, verdict: out.verdict }, null, 1))
if (!green) process.exit(1)
