// ============================================================================
// bus/event_bus.ts — EventBus سبکِ pub/sub  [webplan P1 · ایدهٔ #۱]
// ----------------------------------------------------------------------------
// ستونِ فقراتِ معماریِ ROS2-گونه. گره‌ها به‌جای فراخوانیِ خطیِ توابع، رویداد منتشر
// (publish) و مصرف (subscribe) می‌کنند. رویدادِ کلیدی: "bar.closed@ASSET.TF".
//
// چرا مهم است (پلِ شبیه‌ساز↔سایت): همان رویدادهایی که سایتِ زنده منتشر می‌کند،
// شبیه‌سازِ backtest هم با bar-replay منتشر می‌کند ⇒ زمینه‌سازِ کدِ Isomorphic
// (ایدهٔ #۹) و «هر لایه‌ای که در شبیه‌ساز RQS+≥۸۰ گرفت، بدونِ تغییر در سایت زنده شود».
//
// طراحی: بدونِ هیچ وابستگی، سازگار با Cloudflare Workers و Node/Termux. هم‌زمان
// (synchronous) تا رفتار قطعی و قابلِ‌تست بماند (مهم برای تستِ برابری).
//
// ⚠️ P1 افزودنی است: این باس هنوز در مسیرِ تصمیمِ فعلی تزریق نشده؛ فقط زیرساخت است.
// ============================================================================

export type BusHandler<T = unknown> = (payload: T, topic: string) => void

export interface Subscription {
  /** لغوِ اشتراک. */
  unsubscribe(): void
}

/**
 * EventBus مینیمالِ topic-محور.
 * - topic یک رشتهٔ آزاد است؛ قرارداد پروژه: "<event>@<ASSET>.<TF>" مثلِ "bar.closed@XAUUSD.M5".
 * - انتشار هم‌زمان است؛ خطای یک مشترک بقیه را متوقف نمی‌کند (ایزوله می‌شود).
 */
export class EventBus {
  private handlers = new Map<string, Set<BusHandler<any>>>()
  private wildcards = new Set<BusHandler<any>>()   // مشترکِ همهٔ topicها ('*')

  subscribe<T = unknown>(topic: string, handler: BusHandler<T>): Subscription {
    if (topic === '*') {
      this.wildcards.add(handler as BusHandler<any>)
      return { unsubscribe: () => this.wildcards.delete(handler as BusHandler<any>) }
    }
    let set = this.handlers.get(topic)
    if (!set) { set = new Set(); this.handlers.set(topic, set) }
    set.add(handler as BusHandler<any>)
    return { unsubscribe: () => set!.delete(handler as BusHandler<any>) }
  }

  publish<T = unknown>(topic: string, payload: T): void {
    const set = this.handlers.get(topic)
    if (set) for (const h of set) safeCall(h, payload, topic)
    if (this.wildcards.size) for (const h of this.wildcards) safeCall(h, payload, topic)
  }

  /** پاک‌سازیِ کامل (برای تست/ری‌ست). */
  clear(): void { this.handlers.clear(); this.wildcards.clear() }

  /** تعدادِ مشترکانِ یک topic (برای دیباگ/تست). */
  subscriberCount(topic: string): number {
    return (this.handlers.get(topic)?.size ?? 0) + this.wildcards.size
  }
}

function safeCall(h: BusHandler<any>, payload: unknown, topic: string): void {
  try { h(payload, topic) } catch (e) { /* ایزوله: یک مشترکِ خراب بقیه را نمی‌شکند */ }
}

// ---------------------------------------------------------------------------
// کمکی‌های ساختِ نامِ topic (قرارداد یکنواخت در کلِ پروژه)
// ---------------------------------------------------------------------------
export const Topics = {
  barClosed: (asset: string, tf: string) => `bar.closed@${asset}.${tf}`,
  priceTick: (asset: string, tf: string) => `price.tick@${asset}.${tf}`,
  priceStale: (asset: string, tf: string) => `price.stale@${asset}.${tf}`,
}

/** باسِ سراسریِ پیش‌فرضِ فرآیند (اختیاری برای استفادهٔ ساده). */
export const globalBus = new EventBus()
