// ============================================================================
// indicators/bank/_aggregate.ts — تجمیعِ همهٔ دسته‌های بانک در یک آرایهٔ واحد.
// ----------------------------------------------------------------------------
// این ماژول ۹ فایلِ دسته‌بندی‌شده را import و به ترتیبِ اصلیِ bank.ts concat می‌کند،
// تا خروجی با نسخهٔ یکپارچهٔ قبلی بیت‌به‌بیت یکسان بماند (همان ترتیبِ ثبت).
// ترتیب: trend → momentum → volatility/volume → statistical → cycle →
//        structure → composite → pattern → variants.
// ============================================================================

import type { IndicatorDef } from '../contracts'
import { TREND_ITEMS } from './trend'
import { MOMENTUM_ITEMS } from './momentum'
import { VOLATILITY_ITEMS } from './volatility'
import { STATISTICAL_ITEMS } from './statistical'
import { CYCLE_ITEMS } from './cycle'
import { STRUCTURE_ITEMS } from './structure'
import { COMPOSITE_ITEMS } from './composite'
import { PATTERN_ITEMS } from './pattern'
import { VARIANTS_ITEMS } from './variants'

export const BANK_ALL: IndicatorDef<any>[] = [
  ...TREND_ITEMS,
  ...MOMENTUM_ITEMS,
  ...VOLATILITY_ITEMS,
  ...STATISTICAL_ITEMS,
  ...CYCLE_ITEMS,
  ...STRUCTURE_ITEMS,
  ...COMPOSITE_ITEMS,
  ...PATTERN_ITEMS,
  ...VARIANTS_ITEMS,
]
