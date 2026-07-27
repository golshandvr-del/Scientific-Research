// ============================================================================
// council/council.ts — گرهِ شورای لایه‌ها (رأی‌گیریِ سایه‌ای)  [webplan P4.5 · گره ۶]
// ----------------------------------------------------------------------------
// ورودی: CardDecision (شاملِ primary + otherLayers = همهٔ لایه‌های فعالِ کارت)
// خروجی: CouncilVerdict@v1
//
// منطقِ رأی‌گیری (webplan §۳ گره ۶):
//   • اجماعِ کامل (همه هم‌جهت)  ⇒ UNANIMOUS، لاتِ ×۱.۵.
//   • اکثریت (مثلاً ۲ از ۳)      ⇒ MAJORITY، لاتِ ×۱، «لایهٔ دوم هم تأیید کرد».
//   • تضاد (یکی LONG یکی SHORT)  ⇒ CONFLICT، خنثی + «بازارِ دوقطبی» (فیلترِ محافظ).
//   • یک لایه                    ⇒ SINGLE (اجماع بی‌معنا، رأیِ همان لایه).
//
// ⚠️ سایه‌ای: این گره فقط حکم می‌سازد و لاگ می‌کند. wouldAllowEntry صرفاً *پیشنهاد*
//    است؛ تصمیمِ نهاییِ کارت هنوز از runCard می‌آید. فعال‌سازیِ فیلترِ اجماع پس از
//    سنجشِ اثرش روی RQS+ (شبیه‌سازِ رویدادمحور) انجام می‌شود.
// ============================================================================

import type { CardDecision } from '../runtime/contracts'
import {
  COUNCIL_VERDICT_VERSION,
  type CouncilVerdict,
  type Consensus,
  type LayerVote,
} from './contracts'

/** استخراجِ رأیِ همهٔ لایه‌های *فعالِ* (ENTRY/APPROACHING) یک کارت از CardDecision. */
function collectVotes(cardId: string, dec: CardDecision): LayerVote[] {
  const votes: LayerVote[] = []
  // ۱) خودِ primary اگر فعال باشد.
  if (dec.state === 'ENTRY' || dec.state === 'APPROACHING') {
    votes.push({
      code: dec.sourceLayer?.code || '—',
      name: dec.sourceLayer?.name || dec.headline,
      state: dec.state,
      direction: dec.direction,
      probability: dec.probability,
    })
  }
  // ۲) لایه‌های ثانویهٔ فعال (otherLayers فقط ENTRY/APPROACHING دارد).
  for (const o of dec.otherLayers || []) {
    votes.push({
      code: o.code, name: o.name, state: o.state,
      direction: o.direction, probability: o.probability,
    })
  }
  return votes
}

/**
 * ساختِ حکمِ شورا از CardDecision یک کارت.
 * تنها آرای ENTRY در شمارشِ جهت لحاظ می‌شوند (APPROACHING هنوز جهتِ قطعی ندارد،
 * اما در فهرستِ votes برای شفافیت می‌ماند).
 */
export function convene(cardId: string, dec: CardDecision): CouncilVerdict {
  const votes = collectVotes(cardId, dec)
  const entryVotes = votes.filter(v => v.state === 'ENTRY' && (v.direction === 'LONG' || v.direction === 'SHORT'))
  const longVotes = entryVotes.filter(v => v.direction === 'LONG').length
  const shortVotes = entryVotes.filter(v => v.direction === 'SHORT').length

  let consensus: Consensus
  let direction: 'LONG' | 'SHORT' | undefined
  let lotMultiplier = 1
  let wouldAllowEntry = false
  let note: string

  const activeCount = entryVotes.length

  if (votes.length === 0) {
    consensus = 'NONE'
    lotMultiplier = 0
    note = 'هیچ لایهٔ فعالی رأی نداده است.'
  } else if (activeCount === 0) {
    // فقط APPROACHINGها فعال‌اند — اجماعِ ورود بی‌معناست، ولی رأیِ آماده‌باش هست.
    consensus = votes.length === 1 ? 'SINGLE' : 'MAJORITY'
    lotMultiplier = 0
    note = `${votes.length} لایه در آماده‌باش (APPROACHING)؛ هنوز ورودِ قطعی نیست.`
  } else if (longVotes > 0 && shortVotes > 0) {
    // تضادِ جهت ⇒ فیلترِ محافظ.
    consensus = 'CONFLICT'
    lotMultiplier = 0
    wouldAllowEntry = false
    note = `تضادِ جهت: ${longVotes} لایه LONG و ${shortVotes} لایه SHORT ⇒ بازارِ دوقطبی. شورا ورود را وتو می‌کند (فیلترِ محافظ).`
  } else {
    // همه هم‌جهت.
    direction = longVotes > 0 ? 'LONG' : 'SHORT'
    wouldAllowEntry = true
    if (activeCount === 1) {
      consensus = 'SINGLE'
      lotMultiplier = 1
      note = `تنها یک لایهٔ فعال (${direction}). اجماع بی‌معناست؛ رأیِ همان لایه ملاک است.`
    } else {
      // چند لایهٔ هم‌جهت. آیا *همهٔ* آرای ENTRY هم‌جهت‌اند؟ (اینجا بله، چون تضاد رد شد.)
      consensus = 'UNANIMOUS'
      lotMultiplier = 1.5
      note = `اجماعِ کامل: ${activeCount} لایه هم‌جهت (${direction}). اطمینانِ بالا؛ پیشنهادِ لاتِ ×۱.۵. «لایهٔ دوم هم همین سیگنال را تأیید کرد.»`
    }
  }

  return {
    v: COUNCIL_VERDICT_VERSION,
    cardId, consensus, direction, lotMultiplier, wouldAllowEntry,
    longVotes, shortVotes, votes, note,
  }
}
