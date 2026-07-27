// ============================================================================
// ui/badges.js — گرهِ ظاهر (UI) · نشان‌های افزودنی  [webplan P5 · گره ۴]
// ----------------------------------------------------------------------------
// این ماژول «فقط مصرف‌کنندهٔ CardDecision» است — هیچ منطقِ تصمیمی این‌جا نیست
// (طبقِ webplan §گره ۴). دو نشانِ افزودنیِ خالص:
//
//   ۱) heartbeatBar(ageSec)  — نوارِ قرمزِ «دادهٔ زنده قطع — سیگنال منجمد»
//       اگر سنِّ قیمتِ زنده از آستانه بگذرد (ایدهٔ #۷، ایمنی). آستانه = ۹۰ ثانیه
//       (طبقِ webplan §گره ۴ و §Heartbeat).
//
//   ۲) councilBadge(council) — نشانِ «لایهٔ دوم هم همین سیگنال را تأیید کرد»
//       از خروجیِ گرهِ شورا (P4.5). فقط وقتی اجماع/اکثریتِ چندلایه وجود دارد.
//
// اصلِ Strangler-Fig: هر دو تابع اگر داده نبود رشتهٔ خالی برمی‌گردانند، پس
// رفتارِ فعلیِ کارت‌ها بیت‌به‌بیت حفظ می‌شود (افزودنیِ محض).
//
// قانونِ طراحی (User Note): هیچ اطلاعاتِ اضافه (RQS، سودِ خالص، نتایجِ تحقیق) به
// کاربر نشان داده نمی‌شود — این نشان‌ها فقط «ایمنی» و «اطمینانِ اجماع» را می‌گویند.
// ============================================================================

/** آستانهٔ کهنگیِ قیمتِ زنده (ثانیه) — پس از این، سیگنال «منجمد» اعلام می‌شود. */
export const HEARTBEAT_STALE_SEC = 90

/**
 * نوارِ Heartbeat: اگر `ageSec > 90` نوارِ قرمزِ هشدار برمی‌گرداند؛ وگرنه خالی.
 * @param {number|null|undefined} ageSec سنِّ آخرین قیمتِ زنده به ثانیه.
 * @returns {string} HTML (یا رشتهٔ خالی).
 */
export function heartbeatBar(ageSec) {
  if (ageSec == null || !Number.isFinite(ageSec) || ageSec <= HEARTBEAT_STALE_SEC) return ''
  const mins = ageSec >= 120 ? ` (${Math.round(ageSec / 60)} دقیقه)` : ` (${Math.round(ageSec)} ثانیه)`
  return `
    <div class="mb-2 rounded-md bg-rose-600/20 border border-rose-500/50 px-2.5 py-1.5 flex items-center gap-2"
         role="alert" data-heartbeat="stale">
      <i class="fas fa-heart-crack text-rose-300 animate-pulse"></i>
      <span class="text-[11px] font-bold text-rose-200">دادهٔ زنده قطع — سیگنال منجمد${mins}</span>
    </div>`
}

/**
 * نشانِ شورا: وقتی چند لایهٔ هم‌جهت اجماع/اکثریت دارند، «تأییدِ لایهٔ دوم» را نشان می‌دهد.
 * تضاد (CONFLICT) را هم به‌شکلِ هشدارِ «بازارِ دوقطبی» نمایش می‌دهد.
 * @param {object|null} council خروجیِ گرهِ شورا (CouncilVerdict@v1) یا null.
 * @returns {string} HTML (یا رشتهٔ خالی).
 */
export function councilBadge(council) {
  if (!council || typeof council !== 'object') return ''
  const c = council.consensus
  // فقط وقتی چیزِ معناداری برای گفتن هست نشان می‌دهیم (SINGLE/NONE ⇒ خالی).
  if (c === 'UNANIMOUS' || c === 'MAJORITY') {
    const n = c === 'UNANIMOUS' ? council.longVotes + council.shortVotes : Math.max(council.longVotes, council.shortVotes)
    const dirFa = council.direction === 'LONG' ? 'خرید' : council.direction === 'SHORT' ? 'فروش' : ''
    const label = c === 'UNANIMOUS'
      ? `اجماعِ کامل: ${toFa(n)} لایه هم‌جهت (${dirFa}) تأیید کردند`
      : `اکثریت: لایهٔ دوم هم ${dirFa} را تأیید کرد`
    const color = c === 'UNANIMOUS'
      ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200'
      : 'bg-teal-500/15 border-teal-500/40 text-teal-200'
    return `
      <div class="mb-2 rounded-md border px-2.5 py-1.5 flex items-center gap-2 ${color}" data-council="${c}">
        <i class="fas fa-people-group text-[11px]"></i>
        <span class="text-[11px] font-bold">${label}</span>
      </div>`
  }
  if (c === 'CONFLICT') {
    return `
      <div class="mb-2 rounded-md bg-amber-500/15 border border-amber-500/40 px-2.5 py-1.5 flex items-center gap-2"
           role="alert" data-council="CONFLICT">
        <i class="fas fa-scale-unbalanced text-amber-300 text-[11px]"></i>
        <span class="text-[11px] font-bold text-amber-200">بازارِ دوقطبی: لایه‌ها تضاد دارند — احتیاط</span>
      </div>`
  }
  return ''
}

/** تبدیلِ عددِ لاتین به رقمِ فارسی (هماهنگ با بقیهٔ ظاهر). */
function toFa(n) {
  const fa = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
  return String(n).replace(/[0-9]/g, d => fa[+d])
}

// --- پلِ global: app.js یک اسکریپتِ کلاسیک است (نه ماژول). برای مصرفِ بی‌ریسک،
//     همین توابع را روی window.UIBadges هم می‌گذاریم تا نوعِ اسکریپتِ app.js را
//     تغییر ندهیم (Strangler-Fig: صفر تغییر در بارگذاریِ فعلی).
if (typeof window !== 'undefined') {
  window.UIBadges = { heartbeatBar, councilBadge, HEARTBEAT_STALE_SEC }
}
