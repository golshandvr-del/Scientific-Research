// ============================================================================
// secondary_layers.ts — «کاوشِ همهٔ لایه‌های نزدیک به فعال‌سازی» (پاسخِ User Note)
// ----------------------------------------------------------------------------
// مشکلی که کاربر دید (و درست حدس زد): تابعِ decide()ِ router یک آبشارِ early-return
// است؛ به‌محضِ اینکه «اولین» لایه به APPROACHING/ENTRY می‌رسد return می‌کند و بقیهٔ
// لایه‌ها — حتی اگر آن‌ها هم نزدیکِ فعال‌شدن باشند — اصلاً نمایش داده نمی‌شوند.
//
// این ماژول منطقِ برندهٔ decide() را دست نمی‌زند (ریسکِ صفر روی سیگنالِ اصلی).
// در عوض، «همان توابعِ compute*» را که خودِ decide() استفاده می‌کند، مستقل و فقط
// برای «کاوش» صدا می‌زند و فهرستی سبک از لایه‌هایی که در وضعیتِ ENTRY/APPROACHING
// هستند برمی‌گرداند. فرانت‌اند این‌ها را به‌صورتِ collapsed زیرِ سیگنالِ اصلی نشان
// می‌دهد؛ کاربر با یک کلیک بازشان می‌کند و دلیل/تأییدهای هر کدام را می‌بیند.
//
// نکته: خروجی «خلاصه» است (state + دلیل + تأییدها)، نه یک RouterDecisionِ کاملِ
// قابلِ‌ورود. سیگنالِ قابلِ‌ورود همان لایهٔ اصلی است (decide). لایه‌های ثانویه فقط
// «شفافیت» می‌دهند: «این‌ها هم دارند نزدیک می‌شوند».
// ============================================================================
import type { AnalysisResult } from './signal'
import { computeShortMA, DEFAULT_SHORT_MA } from './short_ma_confluence'
import { computeSqueeze, DEFAULT_SQUEEZE } from './squeeze_breakout'
import { computeOvernight } from './overnight_drift'
import { computeMonday, MONDAY_ENTRY_HOURS } from './monday_drift'
import { computeTurnOfMonth } from './turn_of_month_drift'
import { trendLineDecision, TREND_LINE_CFG } from './gold_trend_line'
import { channelDecision, CHANNEL_CFG } from './gold_channel'
import { toIranHM } from './router'

// خلاصهٔ سبکِ یک لایهٔ ثانویه برای نمایشِ collapsed در UI.
export interface SecondaryLayer {
  code: string
  name: string
  kind: string
  state: 'ENTRY' | 'APPROACHING'
  direction?: 'LONG' | 'SHORT'
  reason: string
  confirmations?: { label: string; met: boolean; detail: string }[]
}

// پارامترهای موردِنیاز برای کاوش — همان چیزهایی که decideAsset در دست دارد.
export interface ProbeCtx {
  assetId: string          // 'XAUUSD' | 'XAUUSD-M5' | ... | 'EURUSD' ...
  result: AnalysisResult
  open: number[]
  high: number[]
  low: number[]
  close: number[]
  capital: number
  riskPct: number
  utcHour?: number
  utcDay?: number
  times?: number[]
  // کدِ لایهٔ اصلی (تصمیمِ برنده) تا از فهرستِ ثانویه حذف شود (تکراری نشود).
  primaryCode?: string
}

// آیا این تایم‌فریمِ طلا لایهٔ trend-line/channel دارد؟ (CFGها همین کلیدها را دارند)
const TL_KEY: Record<string, string> = {
  'XAUUSD': 'XAUUSD-M15', 'XAUUSD-M5': 'XAUUSD-M5',
  'XAUUSD-M30': 'XAUUSD-M30', 'XAUUSD-H4': 'XAUUSD-H4',
}

// ----------------------------------------------------------------------------
// کاوشِ همهٔ لایه‌های ثانویهٔ فعال برای یک دارایی/تایم‌فریم.
// خروجی فقط شاملِ لایه‌هایی است که ENTRY یا APPROACHING‌اند و کدشان با لایهٔ اصلی
// یکی نیست (تا زیرِ سیگنالِ اصلی، تکراری نمایش داده نشود).
// ----------------------------------------------------------------------------
export function probeSecondaryLayers(ctx: ProbeCtx): SecondaryLayer[] {
  const out: SecondaryLayer[] = []
  const { assetId, result, open, high, low, close, capital, riskPct } = ctx
  const isGoldM15 = assetId === 'XAUUSD'

  const push = (l: SecondaryLayer) => {
    if (ctx.primaryCode && l.code === ctx.primaryCode) return   // تکراری با لایهٔ اصلی
    out.push(l)
  }

  // ---- لایه‌های زمان-محورِ طلا M15 (فقط روی کارتِ XAUUSD اصلی) ----
  if (isGoldM15 && typeof ctx.utcHour === 'number') {
    const ov = computeOvernight(ctx.utcHour)
    if (ov.state === 'ENTRY' || ov.state === 'APPROACHING') {
      push({
        code: 'S139', name: 'درایوِ شبانه (Overnight Drift)', kind: 'time',
        state: ov.state, direction: 'LONG', reason: ov.reason,
        confirmations: ov.state === 'APPROACHING' ? [
          { label: `رسیدنِ ساعت به ${toIranHM(22)} به وقتِ ایران`, met: false,
            detail: 'با بسته‌شدنِ کندلِ ساعتِ ورود، سیگنالِ خرید صادر می‌شود.' },
        ] : undefined,
      })
    }
  }
  if (isGoldM15 && typeof ctx.utcHour === 'number' && typeof ctx.utcDay === 'number') {
    const mo = computeMonday(ctx.utcDay, ctx.utcHour)
    if (mo.state === 'ENTRY' || mo.state === 'APPROACHING') {
      push({
        code: 'S140', name: 'درایوِ ابتدای هفته (Monday Drift)', kind: 'time',
        state: mo.state, direction: 'LONG', reason: mo.reason,
        confirmations: mo.state === 'APPROACHING' ? [
          { label: `رسیدنِ ساعت به ${toIranHM(MONDAY_ENTRY_HOURS[0])} در دوشنبه`, met: false,
            detail: 'با ورود به پنجرهٔ درایوِ ابتدای هفته، سیگنالِ خرید صادر می‌شود.' },
        ] : undefined,
      })
    }
  }
  if (isGoldM15 && Array.isArray(ctx.times) && typeof ctx.utcHour === 'number') {
    const tom = computeTurnOfMonth(ctx.times, ctx.utcHour)
    if (tom.state === 'ENTRY' || tom.state === 'APPROACHING') {
      push({
        code: 'S141', name: 'درایوِ چرخشِ ماه (Turn-of-Month)', kind: 'time',
        state: tom.state, direction: 'LONG', reason: tom.reason,
        confirmations: tom.state === 'APPROACHING' ? [
          { label: 'رسیدنِ اولین روزِ معاملاتیِ ماه در ساعتِ ورود', met: false,
            detail: 'با ورود به پنجرهٔ درایوِ اولِ ماه، سیگنالِ خرید صادر می‌شود.' },
        ] : undefined,
      })
    }
  }

  // ---- لایهٔ SHORT-MA-Confluence (طلا M15) ----
  if (isGoldM15) {
    const sm = computeShortMA(close, DEFAULT_SHORT_MA)
    if (sm.active) {
      push({ code: 'SHORT-MA', name: 'هم‌گراییِ میانگین‌ها (SHORT)', kind: 'ma-confluence',
        state: 'ENTRY', direction: 'SHORT', reason: sm.reason })
    } else if (sm.approaching) {
      push({ code: 'SHORT-MA', name: 'هم‌گراییِ میانگین‌ها (SHORT)', kind: 'ma-confluence',
        state: 'APPROACHING', direction: 'SHORT', reason: sm.reason,
        confirmations: [
          { label: 'قیمت از خطِ میانهٔ MA رو به پایین عبور کند', met: false,
            detail: `اکنون ${sm.distPct.toFixed(2)}% بالای میانه و رو به کاهش است.` },
          { label: 'چیدمانِ نزولیِ میانگین‌ها (EMA50<EMA100<SMA200)', met: sm.dnStack,
            detail: sm.dnStack ? 'برقرار است ✓' : 'هنوز کامل نیست.' },
        ] })
    }
  }

  // ---- لایهٔ Squeeze→Breakout (طلا M15) ----
  if (isGoldM15) {
    const sq = computeSqueeze(close, high, DEFAULT_SQUEEZE, low)
    if (sq.active) {
      push({ code: 'S132', name: 'فشردگی→شکست (Squeeze Breakout)', kind: 'squeeze',
        state: 'ENTRY', direction: 'LONG', reason: sq.reason })
    } else if (sq.approaching) {
      push({ code: 'S132', name: 'فشردگی→شکست (Squeeze Breakout)', kind: 'squeeze',
        state: 'APPROACHING', direction: 'LONG', reason: sq.reason,
        confirmations: [
          { label: 'شکستِ سقفِ اخیر با کندلِ قوی', met: false,
            detail: 'پس از فشردگیِ نوسان، شکستِ رو به بالا ماشه را شلیک می‌کند.' },
        ] })
    }
  }

  // ---- لایه‌های Al Brooks (trend-line S215 + channel S219) روی تایم‌فریم‌های طلا ----
  const tlKey = TL_KEY[assetId]
  if (tlKey && TREND_LINE_CFG[tlKey]) {
    try {
      const tl = trendLineDecision(TREND_LINE_CFG[tlKey], result, open, high, low, close, capital, riskPct)
      if (tl.state === 'ENTRY' || tl.state === 'APPROACHING') {
        push({ code: 'S215', name: 'خطِ روندِ Al Brooks (Trend-Line)', kind: 'price-action',
          state: tl.state, direction: tl.direction,
          reason: tl.reason, confirmations: tl.confirmations })
      }
    } catch { /* لایهٔ اختیاری؛ اگر داده کم بود ردش کن */ }
  }
  if (tlKey && CHANNEL_CFG[tlKey]) {
    try {
      const chn = channelDecision(CHANNEL_CFG[tlKey], result, open, high, low, close, capital, riskPct)
      if (chn.state === 'ENTRY' || chn.state === 'APPROACHING') {
        push({ code: 'S219', name: 'کانالِ Al Brooks (Channel)', kind: 'price-action',
          state: chn.state, direction: chn.direction,
          reason: chn.reason, confirmations: chn.confirmations })
      }
    } catch { /* اختیاری */ }
  }

  return out
}
