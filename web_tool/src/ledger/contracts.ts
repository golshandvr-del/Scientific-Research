// ============================================================================
// ledger/contracts.ts — قراردادِ نسخه‌دارِ دفترِ RQS زنده  [webplan P7 · ایدهٔ #۳]
// ----------------------------------------------------------------------------
// «دفترِ RQS زنده» نتیجهٔ واقعیِ معاملاتِ کاربر را ذخیره می‌کند و RQS+ زندهٔ هر
// لایه را از همان نتایجِ واقعی (نه بک‌تست) محاسبه می‌کند. اگر RQS+ زندهٔ یک لایه
// افت کرد، دفتر آن را برای «بایگانیِ موقت» پرچم می‌زند ⇒ سایتِ *یادگیرنده*.
//
// این گره کاملاً افزودنی/سایه‌ای است: هیچ تصمیمی را تغییر نمی‌دهد و صرفاً از طریقِ
// endpointهای جدیدِ /api/ledger/* مصرف می‌شود (مسیرِ /api/decision دست‌نخورده).
// ============================================================================

/** نسخهٔ قراردادِ دفتر — هر تغییرِ ناسازگار این عدد را بالا می‌برد. */
export const LEDGER_CONTRACT_VERSION = 1 as const

/** جهتِ معامله. */
export type TradeDir = 'LONG' | 'SHORT'

// ----------------------------------------------------------------------------
// TradeOutcome@v1 — یک رکوردِ نتیجهٔ واقعیِ معاملهٔ کاربر (پس از بسته‌شدن).
// ----------------------------------------------------------------------------
export interface TradeOutcome {
  readonly v: typeof LEDGER_CONTRACT_VERSION
  /** کارت (مثلاً 'XAUUSD-M15'). */
  readonly cardId: string
  /** کدِ لایه‌ای که سیگنال را داد (مثلاً 'S324'). منبعِ نسبت‌دادنِ نتیجه به لایه. */
  readonly layerCode: string
  readonly dir: TradeDir
  /** قیمتِ ورود و خروجِ واقعی (که کاربر ثبت کرده). */
  readonly entry: number
  readonly exit: number
  /** حد سود/ضررِ اعلام‌شده هنگامِ سیگنال (برای WR_breakeven = SL/(SL+TP)). */
  readonly tpDist: number   // فاصلهٔ TP از ورود (به دلار/اونس)
  readonly slDist: number   // فاصلهٔ SL از ورود
  /** سود/زیانِ خالصِ این معامله به دلار (پس از اسپرد، طبقِ CONTRACT_SIZE=100). */
  readonly pnl: number
  /** آیا برنده بود؟ (pnl > 0) */
  readonly win: boolean
  /** زمانِ بسته‌شدن (ms). */
  readonly closedAt: number
}

// ----------------------------------------------------------------------------
// LiveRqs@v1 — خروجیِ محاسبهٔ RQS+ زنده برای یک لایه.
// ----------------------------------------------------------------------------
export interface GateResult {
  readonly id: 'G0' | 'G1' | 'G2' | 'G3' | 'G4' | 'G5'
  readonly name: string
  readonly pass: boolean
  readonly detail: string
}

export interface LiveRqs {
  readonly v: typeof LEDGER_CONTRACT_VERSION
  readonly layerCode: string
  readonly cardId: string
  /** تعدادِ معاملهٔ واقعیِ ثبت‌شده برای این لایه. */
  readonly n: number
  /** نرخِ برد (۰..۱). */
  readonly wr: number
  /** Profit Factor. */
  readonly pf: number
  /** میانگینِ سودِ هر معامله (expectancy) به دلار. */
  readonly expectancy: number
  /** بیشترین رشتهٔ باختِ متوالی. */
  readonly maxConsecLoss: number
  /** بیشترین افتِ سرمایه (٪ نسبت به اوجِ منحنیِ اکوییتی). */
  readonly maxDDPct: number
  /** p-value آزمونِ دوجمله‌ای (لبه بر رندوم). */
  readonly pValue: number
  /** نمرهٔ نهاییِ RQS+ (۰..۱۰۰). */
  readonly rqs: number
  /** آیا از همهٔ ۶ گیت پاس شد؟ */
  readonly passedAllGates: boolean
  /** نتیجهٔ تک‌تکِ گیت‌ها (برای شفافیتِ گزارش). */
  readonly gates: GateResult[]
  /** آیا لایه باید موقتاً بایگانی شود؟ (RQS زنده < آستانه با نمونهٔ کافی) */
  readonly shouldArchive: boolean
  /** توضیحِ فارسیِ وضعیت (برای گزارش/UI آینده). */
  readonly note: string
}

/** آستانهٔ رسمیِ پروژه: RQS+ ≥ ۸۰ برای زنده‌ماندنِ لایه. */
export const RQS_LIVE_THRESHOLD = 80 as const
/** کفِ نمونه برای اینکه محاسبهٔ زنده «معتبر» تلقی شود (کمتر از این = داده ناکافی). */
export const RQS_LIVE_MIN_SAMPLES = 30 as const
