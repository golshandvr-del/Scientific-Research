// آزمونِ واحدِ دفترِ سیگنال: ثبت، حذفِ تکرار، حلِ TP/SL/انقضا، شاهدِ کاذب، بدیلِ بین‌کارتی.
import { observeDecision, getJournal, journalStats, resolveRecord, _resetForTest } from '../src/journal/signal_journal'

let fail = 0
const ok = (c: boolean, m: string) => { console.log(`  ${c ? '✓' : '❌'} ${m}`); if (!c) fail++ }
const bar = (t: number, o: number, h: number, l: number, c: number) => ({ time: t, open: o, high: h, low: l, close: c })
_resetForTest()

const base = [bar(0, 100, 101, 99, 100), bar(100, 100, 101, 99, 100)]
const dec = {
  state: 'ENTRY', direction: 'LONG', entry: 100, tp: 102, sl: 99, rr: 2,
  sourceLayer: { code: 'S382', name: 'W%R' }, slPlan: { maxHoldBars: 3 },
  falseWitness: [{ code: 'S1581', inFavorOf: 'S382', jaccard: 0.635 }],
  otherLayers: [{ code: 'S572', state: 'ENTRY', direction: 'LONG', entry: 100, tp: 101, sl: 99.5,
    sameEventFamily: { code: 'S572', isPrimary: false, primaryCard: 'XAUUSD-M30' } }],
}
const a1 = await observeDecision({ card: 'XAUUSD-H4', asset: 'XAUUSD-H4', tf: 'H4', gapSec: 100, dec, price: 100, bars: base })
ok(a1.length === 2, `ثبتِ primary + other (${a1.length})`)
ok(!a1.some(r => r.layer === 'S1581'), 'شاهدِ کاذبِ حذف‌شده رکوردِ جدا نمی‌گیرد')
ok(a1[0].notes.some(n => n.includes('S1581')), 'شاهدِ کاذب در یادداشتِ برنده آمده')
ok(a1[1].independent === false, 'بدیلِ بین‌کارتی ⇒ independent=false')

const a2 = await observeDecision({ card: 'XAUUSD-H4', asset: 'XAUUSD-H4', tf: 'H4', gapSec: 100, dec, price: 100, bars: [...base, bar(200, 100, 100.5, 99.8, 100.2)] })
ok(a2.length === 0, 'ENTRYِ تکراریِ همان اپیزود ثبت نمی‌شود')

await observeDecision({ card: 'XAUUSD-H4', asset: 'XAUUSD-H4', tf: 'H4', gapSec: 100, dec: { state: 'NEUTRAL' }, price: 102, bars: [...base, bar(200, 100, 100.5, 99.8, 100.2), bar(300, 100.2, 102.5, 100, 102)] })
const j = await getJournal()
const p = j.find(r => r.layer === 'S382')!, o = j.find(r => r.layer === 'S572')!
ok(p.status === 'TP' && p.pips === 20 && p.rMultiple === 2, `primary ⇒ TP +20pip 2R (${p.status} ${p.pips} ${p.rMultiple})`)
ok(o.status === 'TP', `other ⇒ TP (${o.status})`)

// TP و SL در یک کندل ⇒ SL (محافظه‌کار)
const r: any = { status: 'OPEN', direction: 'SHORT', entry: 100, tp: 98, sl: 101, barTime: 0 }
resolveRecord(r, [bar(10, 100, 101.5, 97, 99)])
ok(r.status === 'SL' && r.pips === -10, `کندلِ دوطرفه ⇒ SL (${r.status} ${r.pips})`)
// انقضای hold
const e: any = { status: 'OPEN', direction: 'LONG', entry: 100, tp: 110, sl: 90, barTime: 0, maxHoldBars: 2 }
resolveRecord(e, [bar(1, 100, 101, 99, 100.5), bar(2, 100.5, 101, 99, 101)])
ok(e.status === 'EXPIRED' && e.pips === 10, `انقضا روی closeِ کندلِ آخرِ hold (${e.status} ${e.pips})`)

const s = await journalStats()
const row = s.rows.find((x: any) => x.layer === 'S572')
ok(row.alternates === 1 && row.closed === 0, 'آمار: بدیل در WR شمرده نمی‌شود')

const n = await observeDecision({ card: 'XAUUSD-H4', asset: 'XAUUSD-H4', tf: 'H4', gapSec: 100, dec, price: 102, bars: [...base, bar(200, 1, 1, 1, 1), bar(300, 1, 1, 1, 1), bar(400, 102, 103, 101, 102)] })
ok(n.length >= 1, 'پس از بسته‌شدنِ اپیزود، سیگنالِ تازهٔ همان لایه دوباره ثبت می‌شود')

console.log(fail ? `\n❌ ${fail} شکست` : '\n✅ همه سبز')
process.exit(fail ? 1 : 0)
