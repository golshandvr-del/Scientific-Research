// ============================================================================
// lpsb_state_s355.ts — لایهٔ S355: «دروازهٔ حالتِ ساختارِ لگ-متناسب» (LPSB State Gate)
// ----------------------------------------------------------------------------
// نخستین لایهٔ پروژه که **هر ۱۱ دروازهٔ RQS2 (v2.4)** را پاس کرد.
//
//   کارت:      XAUUSD-M5  (و فقط همین کارت — سه کارتِ دیگر در H3 ماندند)
//   نقش:       فیلترِ زمینه‌ای روی مولدِ S333، نه مولدِ ورودِ مستقل
//   قانون:     ورودِ لانگِ S333 پذیرفته می‌شود ⇐⇒ state_LPSB(L=8, f=0.33) === −1
//   نتیجه:     RQS2 = 83.9 · WR 72.34% · PF 3.951 · lift +25.27pp · z 3.47
//              p_perm = 0.000259 (K=500) · holdout 40% → WR 81.25% · maxDD 1.98%
//   سند:       results/S355_LPSBStateFilterRevival_Xauusd_M5_rqs2-84.md
//   مصنوعِ خام: results/_scan_S351/XAUUSD_M5_filter_rqs2.json
//
// ---------------------------------------------------------------------------
// ⭐ چرا این فیلتر کار می‌کند (و چرا جهتش ضدِ شهود است)
// ---------------------------------------------------------------------------
// منبعِ ایده: Market_Structure_Break_and_Order_Block_v3 (MT4/GPL) — تلگرام.
// هستهٔ ریاضیِ منبع: آستانهٔ «شکستِ ساختار» به **دامنهٔ خودِ لگِ ساختاری** نرمال
// می‌شود، نه به ATR ⇒ سنجهٔ **خود-متشابهِ فراکتالی** در برابرِ نرمال‌سازیِ آماریِ
// نوسان. نرمال‌کنندهٔ متفاوت ⇒ اطلاعاتِ متفاوت (و همین لبهٔ نو را ساخت).
//
// جهتِ فیلتر ضدِ شهود است: برای **خرید**، ساختارِ نزولی (`state = −1`) لازم است.
// دلیلِ اقتصادی: S333 یک لایهٔ pullback در روندِ صعودیِ کلان (EMA20>EMA100) است.
// وقتی ساختارِ خُردِ LPSB هم `+1` است، pullback «کم‌عمق در روندِ داغ» است و
// حرکتِ باقی‌مانده تا TP کم است؛ وقتی ساختارِ خُرد `−1` است، همان pullback یک
// **عقب‌نشینیِ واقعی درونِ روندِ صعودیِ سالم** است ⇒ نسبتِ پاداش/ریسکِ بهتر.
// هر دو شاخه در همان اجرا سنجیده شدند (‏`state=+1` ⇒ n=18, WR 50.0% ⇒ REJECT)
// تا انتخاب، پس‌از‌واقعیت (post-hoc) نباشد.
//
// ---------------------------------------------------------------------------
// ⛔ ضدِ repaint — تفاوتِ حیاتی با نسخهٔ MT4
// ---------------------------------------------------------------------------
// نسخهٔ MT4 پیوت را از `pos + zigzag_len` می‌خواند ⇒ **نگاه به آینده**. این پورت
// علّی است: پیوتِ کندلِ j تنها در کندلِ `j+L` قابلِ دانستن می‌شود و حالتِ ساختار
// در کندلِ i فقط از پیوت‌هایی ساخته می‌شود که `تأیید ≤ i` دارند.
//
// verbatim از strategies/s351_lpsb.py (تابعِ confirmed_pivots + lpsb_signals)
// پورت شده؛ شرطِ فیلتر verbatim از strategies/s351_filter_rqs2.py خطِ
// `filt = base & (state == -1)`.
//
// ⚠️ نکتهٔ ظریفِ برابریِ پورت: در پایتون، ماشینِ حالت روی آرایه‌های **پیش از**
// اعمالِ warmup-mask اجرا می‌شود (mask فقط روی cross_up/cross_dn برگشتی است، نه
// روی state). این‌جا هم عیناً همان رفتار پیاده شده — هیچ warmup روی state نیست.
// ============================================================================

import { type Candle } from './indicators'
import { type RouterDecision } from './router'

// عضوِ مرکزیِ خانوادهٔ پیش‌ثبت‌شده (s351_verdict.CENTRAL) — جست‌وجو نشده.
export const LPSB_CENTRAL = { L: 8, f: 0.33 } as const

export interface LpsbGateConfig {
  L: number                 // نیم‌پنجرهٔ پیوتِ فراکتال (۸ = عضوِ مرکزی)
  f: number                 // فاکتورِ فیبِ تأییدِ شکست (۰.۳۳ = سازندهٔ منبع)
  requiredState: -1 | 1     // حالتِ لازم برای عبورِ سیگنال (−۱ برای S333/M5)
  code: string              // کدِ لایهٔ ترکیبی (S355)
  name: string              // نامِ فارسیِ لایه (برای نمایش به کاربر)
}

// پیکربندیِ کارتِ پذیرفته‌شده — تنها کارتی که ۱۱/۱۱ شد.
export const S355_CFG: Record<string, LpsbGateConfig> = {
  'XAUUSD-M5': {
    L: LPSB_CENTRAL.L, f: LPSB_CENTRAL.f, requiredState: -1,
    code: 'S355',
    name: 'S333 + دروازهٔ حالتِ ساختارِ لگ-متناسب (LPSB)',
  },
}

// ===========================================================================
// S431 — گسترشِ **همین** دروازه به سه کارتِ دیگر (M15/M30/H1)
// ---------------------------------------------------------------------------
// سند: results/S431_LpsbMulticardPool_Xauusd_M5M15M30H1_rqs2_93_ACCEPT.md
// مدرکِ خام: results/_scan_S431/pool_verdict.json
// دفترچه: docs/handoff/reports/MISSION_4_REPORT.md (ورودیِ E-05)
//
// ⭐ چه چیزی نو است و چه چیزی **نو نیست** (تفکیکِ صریح برای جلوگیری از ادعای بیش‌ازواقع):
//   نو نیست: خودِ قانون. عیناً همان `state === requiredState` با همان عضوِ
//            مرکزیِ `L=8, f=0.33`. **هیچ پارامترِ نویی جست‌وجو نشد.**
//   نو نیست: هندسه. `TP/SL/maxHold` هر کارت از `S333_CFG` همان کارت ارث می‌رسد
//            (تأیید شد که با `BEST_CFG`ِ پایتون کاراکتر-به-کاراکتر یکی است).
//   نو هست:  **اتصال**. این سازوکار پیش‌تر تنها به `XAUUSD-M5` وصل بود؛ سه کارتِ
//            `M15/M30/H1` لایه‌های کاملاً متفاوتی می‌راندند (S344/S312/S356).
//
// ⭐ چرا این سه کارت **قبلاً** رد شده بودند و الان مجازند:
//   در حکمِ v2.4ِ S355 هر سه در `H3` (توان) مانده بودند: n = ۳۸/۲۸/۶۶ — و
//   `n_required_h3` برای این اندازهٔ اثر ۷۲.۴ است. یعنی شکستشان **ریاضیاً از
//   کمبودِ نمونه** بود، نه از نبودِ لبه (`lift` هر سه مثبت و بزرگ: +۱۷.۴/+۱۹.۵/+۱۶.۲).
//   `S431` نشان داد وقتی چهار کارت در **یک جمعیتِ تقویمیِ واحد** تجمیع شوند،
//   `n=۱۶۸` و `z=۴.۷۰۶` (سد ۳.۰۹) و هر ۱۱ دروازه پاس ⇒ `RQS2 = 93.9`.
//
// ⚠️ صداقتِ آماری — این «چهار کارتِ مستقلاً پاس‌شده» **نیست**:
//   حکمِ `ACCEPT` روی **جمعیتِ تجمیعی** صادر شده. هر عضو به‌تنهایی هنوز
//   کم‌نمونه است. پس اتصالِ سایت هم باید به همین شکل تفسیر شود: چهار کارت
//   **یک لایهٔ آماریِ واحد** را می‌رانند که با هم اعتبار یافته‌اند.
//
// ⚠️ محدودیتِ افشا‌شده: لایه **فقط لانگ** است (`side_n = {long:168, short:0}`).
//   هیچ سیگنالِ شورتی تولید نمی‌کند ⇒ در رونِدِ نزولیِ بلندمدت ساکت می‌ماند
//   (که ایمن است) ولی از آن سود هم نمی‌برد.
// ===========================================================================
export const S431_CFG: Record<string, LpsbGateConfig> = {
  'XAUUSD-M15': {
    L: LPSB_CENTRAL.L, f: LPSB_CENTRAL.f, requiredState: -1,
    code: 'S431',
    name: 'S333 + دروازهٔ ساختارِ LPSB (استخرِ چند-کارتی)',
  },
  'XAUUSD-M30': {
    L: LPSB_CENTRAL.L, f: LPSB_CENTRAL.f, requiredState: -1,
    code: 'S431',
    name: 'S333 + دروازهٔ ساختارِ LPSB (استخرِ چند-کارتی)',
  },
  'XAUUSD-H1': {
    L: LPSB_CENTRAL.L, f: LPSB_CENTRAL.f, requiredState: -1,
    code: 'S431',
    name: 'S333 + دروازهٔ ساختارِ LPSB (استخرِ چند-کارتی)',
  },
}

// ---------------------------------------------------------------------------
// confirmedPivots — هستهٔ ضدِ repaint.
//   سوئینگ‌بالا در j  ⇐ high[j] >= max(high[j−L .. j+L])   → در j+L تأیید می‌شود
//   سوئینگ‌پایین در j ⇐ low[j]  <= min(low[j−L .. j+L])    → در j+L تأیید می‌شود
// خروجی: hRef[i]/lRef[i] = آخرین پیوتِ **تأییدشده تا کندلِ i** (NaN اگر نبود).
// ---------------------------------------------------------------------------
export function confirmedPivots(candles: Candle[], L: number): { hRef: number[]; lRef: number[] } {
  const n = candles.length
  const hRef = new Array<number>(n).fill(NaN)
  const lRef = new Array<number>(n).fill(NaN)
  const w = 2 * L + 1
  if (n < w + 2) return { hRef, lRef }   // برابریِ پورت: پایتون هم این‌جا NaN برمی‌گرداند

  const h = new Array<number>(n)
  const l = new Array<number>(n)
  for (let i = 0; i < n; i++) { h[i] = candles[i].high; l[i] = candles[i].low }

  // پیوت‌بودنِ مرکزِ پنجرهٔ متقارنِ 2L+1 (centers = L .. n−L−1)
  const isPh = new Array<boolean>(n).fill(false)
  const isPl = new Array<boolean>(n).fill(false)
  for (let j = L; j < n - L; j++) {
    let mx = -Infinity, mn = Infinity
    for (let k = j - L; k <= j + L; k++) {
      if (h[k] > mx) mx = h[k]
      if (l[k] < mn) mn = l[k]
    }
    isPh[j] = h[j] >= mx
    isPl[j] = l[j] <= mn
  }

  // forward-fill با تأخیرِ تأیید: پیوتِ j در کندلِ j+L در دسترس می‌آید
  let curH = NaN, curL = NaN
  for (let i = 0; i < n; i++) {
    const j = i - L
    if (j >= 0) {
      if (isPh[j]) curH = h[j]
      if (isPl[j]) curL = l[j]
    }
    hRef[i] = curH
    lRef[i] = curL
  }
  return { hRef, lRef }
}

// ---------------------------------------------------------------------------
// lpsbStateSeries — ماشینِ حالتِ ساختار (+1 صعودی / −1 نزولی / 0 نامعلوم).
//   leg      = hRef − lRef                       (باید > 0 باشد)
//   upLvl    = hRef + f·leg   ،  dnLvl = lRef − f·leg
//   crossUp  در i ⇐ close[i] > upLvl[i]  و  close[i−1] ≤ upLvl[i]   (گذارِ تازه)
//   crossDn  در i ⇐ close[i] < dnLvl[i]  و  close[i−1] ≥ dnLvl[i]
// شرطِ «گذارِ تازه» معادلِ سپرِ `last_l0==l0 || last_h0==h0`ِ سورسِ MT4 است:
// از شمارشِ چندبارهٔ یک شکستِ واحد جلوگیری می‌کند.
// ---------------------------------------------------------------------------
export function lpsbStateSeries(candles: Candle[], L: number, f: number): Int8Array {
  const n = candles.length
  const state = new Int8Array(n)
  if (n === 0) return state
  const { hRef, lRef } = confirmedPivots(candles, L)

  let cur = 0
  let prevClose = candles[0].close
  for (let i = 0; i < n; i++) {
    const c = candles[i].close
    const leg = hRef[i] - lRef[i]
    if (Number.isFinite(leg) && leg > 0 && i >= 1) {
      const upLvl = hRef[i] + f * leg
      const dnLvl = lRef[i] - f * leg
      // ⚠️ verbatim: سطحِ کندلِ جاری با **کلوزِ کندلِ قبلی** مقایسه می‌شود
      //    (پایتون: ~(c[:-1] > up_lvl[1:]))
      const crossUp = c > upLvl && !(prevClose > upLvl)
      const crossDn = c < dnLvl && !(prevClose < dnLvl)
      if (crossUp) cur = 1
      else if (crossDn) cur = -1
    }
    state[i] = cur as -1 | 0 | 1
    prevClose = c
  }
  return state
}

// حالتِ ساختار در «کندلِ جاری» (آخرین کندلِ بسته‌شده) — همان ایندکسی که
// سیگنالِ S333 روی آن ارزیابی می‌شود.
export function lpsbStateNow(candles: Candle[], L: number, f: number): number {
  const s = lpsbStateSeries(candles, L, f)
  return s.length ? s[s.length - 1] : 0
}

const stateLabel = (s: number) => (s === 1 ? 'صعودی (+۱)' : s === -1 ? 'نزولی (−۱)' : 'نامعلوم (۰)')

// ===========================================================================
// withLpsbGate — دکوراتورِ **عمومی** لایه (تابعِ مرتبهٔ بالا)
// ---------------------------------------------------------------------------
// هر لایه‌ای با امضای `(ctx) => RouterDecision | null` را می‌گیرد و نسخهٔ
// «دروازه‌دار» آن را برمی‌گرداند. هیچ چیزی در لایهٔ درونی تغییر نمی‌کند ⇒
// اصلِ ماژولار/ROS2-مانند و توسعه‌پذیریِ پروژه حفظ می‌شود و همین دکوراتور
// می‌تواند فردا روی لایهٔ دیگری هم آزموده شود (بدونِ کپیِ کد).
//
// رفتار (سه شاخه، هم‌راستا با چهار حالتِ کارت):
//   • ENTRY  + دروازه باز  ⇒ عبور، با افزودنِ برچسبِ فیلتر به sourceLayer.filters
//                            (کاربر می‌بیند سیگنال از کدام لایه/فیلتر آمده)
//   • ENTRY  + دروازه بسته ⇒ تنزل به APPROACHING با ذکرِ صریحِ «منتظرِ چه تأییدی
//                            باش» — این دقیقاً حالتِ دومِ کارت است، نه سکوت.
//   • APPROACHING/NEUTRAL  ⇒ عبور، با پیوستِ مقدارِ عددیِ حالتِ ساختار به دلیل
//                            (قانونِ سایت: در حالتِ خنثی مقادیرِ شاخص‌ها گفته شود)
// ===========================================================================
export function withLpsbGate<C extends { candles: Candle[] }>(
  inner: (ctx: C) => RouterDecision | null,
  cfg: LpsbGateConfig,
): (ctx: C) => RouterDecision | null {
  return (ctx: C) => {
    const d = inner(ctx)
    if (!d) return null

    const st = lpsbStateNow(ctx.candles, cfg.L, cfg.f)
    const need = cfg.requiredState
    const open = st === need

    const gateTxt = `دروازهٔ ساختارِ LPSB (L=${cfg.L}, f=${cfg.f}): حالت = ${stateLabel(st)}`

    if (d.state === 'ENTRY') {
      if (open) {
        const filters = [...(d.sourceLayer?.filters ?? []), `${gateTxt} ✓ (لازم: ${stateLabel(need)})`]
        return {
          ...d,
          reason: `${d.reason} | ${gateTxt} ✓ — دروازهٔ ${cfg.code} باز است.`,
          sourceLayer: d.sourceLayer
            ? { ...d.sourceLayer, code: cfg.code, name: cfg.name, filters }
            : undefined,
        }
      }
      // دروازه بسته ⇒ سیگنالِ خام هست ولی تأییدِ ساختاری نیست ⇒ «نزدیکِ سیگنال»
      return {
        ...d,
        state: 'APPROACHING',
        headline: 'نزدیکِ سیگنال — منتظرِ تأییدِ ساختار',
        reason: `مولدِ پایه (pullbackِ S333) شرایطِ ورود را دارد، اما ${gateTxt} ` +
                `و برای ورود حالتِ ${stateLabel(need)} لازم است. ` +
                `منتظر باش تا ساختارِ لگ-متناسب به سمتِ ${stateLabel(need)} شکسته شود؛ ` +
                `تا آن لحظه ورود نمی‌کنیم (دروازهٔ ${cfg.code}).`,
        sourceLayer: d.sourceLayer
          ? { ...d.sourceLayer, code: cfg.code, name: cfg.name,
              filters: [...(d.sourceLayer.filters ?? []), `${gateTxt} ✗ (لازم: ${stateLabel(need)})`] }
          : undefined,
        // هندسهٔ معامله در حالتِ APPROACHING نباید نمایش داده شود
        direction: undefined, entry: undefined, tp: undefined, sl: undefined,
        rr: undefined, probability: undefined, sizing: undefined,
      }
    }

    return { ...d, reason: `${d.reason} | ${gateTxt}` }
  }
}
