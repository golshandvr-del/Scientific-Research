// تستِ واحدِ منطقِ زندهٔ S214 (Late-Entry) — بررسیِ ENTRY/APPROACHING/خارج‌از‌پنجره.
// اجرا:  cd web_tool && npx tsx tools/test_s214_late_entry.mts
import { evalGoldM5LateEntry } from '../src/gold_m5_late_entry.ts'

// --- ساختِ سریِ کندلِ مصنوعیِ M5 که به یک تاریخِ هدف ختم می‌شود ---------------
// pre-EOM day → روزِ ~۲۴ اُمِ ماه (۶–۸ روزِ کاری مانده)، ساعتِ ۱۴ UTC (روز، نه شب).
function buildSeries(lastTs: number, n = 400, withMomentum = true) {
  const o: number[] = [], h: number[] = [], l: number[] = [], c: number[] = [], t: number[] = []
  let px = 4000
  for (let i = 0; i < n; i++) {
    t.push(lastTs - (n - 1 - i) * 300) // هر کندل ۵ دقیقه
    const open = px
    // روندِ صعودیِ ملایمِ زمینه (تا EMA20>EMA50 شود و regimeUp=true) + نوسانِ کوچک
    let close = px + 0.15 + (Math.sin(i / 7) * 0.6)
    // ۶ کندلِ آخر: رشتهٔ صعودیِ قویِ غیر-climactic (برای فعال‌کردنِ مومنتوم)
    if (withMomentum && i >= n - 6) close = open + 1.2 // بدنهٔ صعودیِ متوسط
    const hi = Math.max(open, close) + 0.3
    const lo = Math.min(open, close) - 0.3
    o.push(open); c.push(close); h.push(hi); l.push(lo)
    px = close
  }
  return { o, h, l, c, t }
}

function dayTs(year: number, month0: number, day: number, hourUtc: number) {
  return Math.floor(Date.UTC(year, month0, day, hourUtc, 0, 0) / 1000)
}

// سناریو ۱: pre-EOM day + مومنتوم → انتظار: entry=true
{
  const ts = dayTs(2025, 0, 24, 14) // ۲۴ ژانویه ۲۰۲۵ (~۶ روزِ کاری مانده)، ۱۴ UTC (روز)
  const s = buildSeries(ts, 400, true)
  const r = evalGoldM5LateEntry(s.o, s.h, s.l, s.c, s.t, s.c[s.c.length - 1])
  console.log('سناریو ۱ (pre-EOM day + momentum):', JSON.stringify(r))
  console.log('  → inWindow=%s entry=%s regimeUp=%s hadRecentRun=%s fromEnd=%d hour=%d',
    r.inWindow, r.entry, r.regimeUp, r.hadRecentRun, r.fromEnd, r.utcHour)
}

// سناریو ۲: pre-EOM اما شب (۲۱ UTC) → انتظار: inWindow=false (به M5-scalp می‌افتد)
{
  const ts = dayTs(2025, 0, 24, 21)
  const s = buildSeries(ts, 400, true)
  const r = evalGoldM5LateEntry(s.o, s.h, s.l, s.c, s.t, s.c[s.c.length - 1])
  console.log('سناریو ۲ (pre-EOM NIGHT 21utc):', 'inWindow=' + r.inWindow, '(باید false باشد)')
}

// سناریو ۳: وسطِ ماه (نه pre-EOM) → انتظار: inWindow=false
{
  const ts = dayTs(2025, 0, 15, 14)
  const s = buildSeries(ts, 400, true)
  const r = evalGoldM5LateEntry(s.o, s.h, s.l, s.c, s.t, s.c[s.c.length - 1])
  console.log('سناریو ۳ (mid-month day):', 'inWindow=' + r.inWindow, '(باید false باشد)')
}

// سناریو ۴: pre-EOM day اما بدونِ مومنتوم → انتظار: inWindow=true, entry=false (APPROACHING)
{
  const ts = dayTs(2025, 0, 24, 14)
  const s = buildSeries(ts, 400, false)
  const r = evalGoldM5LateEntry(s.o, s.h, s.l, s.c, s.t, s.c[s.c.length - 1])
  console.log('سناریو ۴ (pre-EOM day, NO momentum):', 'inWindow=' + r.inWindow, 'entry=' + r.entry, '(باید inWindow=true, entry=false)')
}

console.log('\n✅ تستِ منطقِ S214 بدونِ خطا اجرا شد.')
