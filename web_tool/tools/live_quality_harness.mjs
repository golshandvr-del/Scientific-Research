// ============================================================================
// ابزارِ تست کیفیتِ سایت با قیمتِ لحظه‌ای (Live Quality Harness)
// ----------------------------------------------------------------------------
// پاسخِ مستقیم به User Note:
//   «ما منطق را تست کردیم اما سایت را نه. برای تستِ کیفیتِ سایت چیزی بسازیم که
//    مشابهِ سایت قیمت را لحظه‌ای بگیرد (نه دادهٔ قدیمی) و پیشنهادِ معامله بدهد.
//    همزمان یک ماژول باشد که طبقِ دستورِ آن معاملاتی را باز کند. هر دو از قیمتِ
//    لحظه‌ای استفاده کنند. چند دقیقه منتظر بمانیم ببینیم رفتارِ منطقی دارند یا
//    سایت دستورِ اشتباه می‌دهد.»
//
// این ابزار «همان endpointهای واقعیِ سایت» را صدا می‌زند (نه یک شبیه‌ساز جدا):
//   • /api/decision  → همان موتور/Router زندهٔ سایت (سیگنال ۴-حالته + TP/SL + لات)
//   • /api/spots     → قیمتِ لحظه‌ایِ همان منابعِ سایت (Swissquote/gold-api/Yahoo)
//   • /api/trade/advice → همان منطقِ مدیریتِ معاملهٔ سایت
// بنابراین آنچه اینجا می‌بینیم «دقیقاً همان چیزی است که کاربر در مرورگر می‌بیند».
//
// ماژولِ PaperBroker: نقشِ «کاربری که طبقِ دستورِ سایت در دمو معامله می‌کند» را
// بازی می‌کند. وقتی سایت ENTRY بدهد، با قیمتِ لحظه‌ای وارد می‌شود، سپس با قیمتِ
// spotِ زنده TP/SL/بستنِ توصیه‌شده را دنبال می‌کند و سود/زیانِ واقعیِ دلاری را ثبت.
//
// خروجی: یک گزارشِ رفتاری که نشان می‌دهد سایت «منطقی» رفتار می‌کند یا «flicker/
// دستورِ متناقض» می‌دهد. این همان چیزی است که تا الان نداشتیم.
//
// اجرا:
//   node tools/live_quality_harness.mjs --minutes 6 --interval 8 --asset XAUUSD
//   (پیش‌فرض: ۵ دقیقه، پُلینگِ هر ۸ ثانیه، همهٔ دارایی‌ها)
// ============================================================================

const BASE = process.env.HARNESS_BASE || 'http://localhost:3000'

// ---------------------- پارس آرگومان‌ها ----------------------
function argVal(name, def) {
  const i = process.argv.indexOf('--' + name)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def
}
const MINUTES = parseFloat(argVal('minutes', '5'))
const INTERVAL_SEC = parseFloat(argVal('interval', '8'))
const ASSET_FILTER = argVal('asset', '')          // '' = همه
const CAPITAL = parseFloat(argVal('capital', '10000'))
const RISK = parseFloat(argVal('risk', '1'))
const AUTO_TRADE = argVal('autotrade', 'on') !== 'off'   // paper-broker فعال؟

const nowIso = () => new Date().toISOString().replace('T', ' ').slice(0, 19)
const sleep = (ms) => new Promise(r => setTimeout(r, ms))

async function jget(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}
async function jpost(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json()
}

// ============================================================================
// PaperBroker — «کاربرِ دمو». برای هر دارایی حداکثر یک معاملهٔ باز نگه می‌دارد.
// از قیمتِ spotِ لحظه‌ای برای TP/SL و ثبتِ سود/زیانِ دلاریِ واقعی استفاده می‌کند.
// ============================================================================
class PaperBroker {
  constructor() { this.open = {} /* asset → trade */; this.closed = [] }

  hasOpen(asset) { return !!this.open[asset] }

  // باز کردنِ معامله دقیقاً با دستورِ سایت (side/entry/tp/sl/lots)
  openTrade(asset, dec, decimals) {
    const t = {
      asset, side: dec.direction === 'LONG' ? 'long' : 'short',
      entry: dec.entry, tp: dec.tp, sl: dec.sl,
      lots: dec.sizing?.lots ?? null,
      valuePerPricePerLot: asset.startsWith('XAUUSD') ? 100 : 100000,
      openedAt: Math.floor(Date.now() / 1000),
      openedPrice: dec.entry, decimals,
      prob: dec.probability,
      maxFavorable: 0, maxAdverse: 0,
    }
    this.open[asset] = t
    return t
  }

  // به‌روزرسانی با قیمتِ لحظه‌ای؛ اگر TP/SL بخورد معامله را می‌بندد.
  markPrice(asset, price) {
    const t = this.open[asset]
    if (!t || price == null || !isFinite(price)) return null
    const dir = t.side === 'long' ? 1 : -1
    const move = (price - t.entry) * dir           // به واحدِ قیمت
    t.maxFavorable = Math.max(t.maxFavorable, move)
    t.maxAdverse = Math.min(t.maxAdverse, move)
    let hit = null
    if (t.side === 'long') {
      if (price >= t.tp) hit = 'TP'
      else if (price <= t.sl) hit = 'SL'
    } else {
      if (price <= t.tp) hit = 'TP'
      else if (price >= t.sl) hit = 'SL'
    }
    if (hit) return this.closeTrade(asset, price, hit)
    return null
  }

  // بستنِ معامله (توسطِ TP/SL یا دستورِ مدیریتیِ سایت)
  closeTrade(asset, price, reason) {
    const t = this.open[asset]
    if (!t) return null
    const dir = t.side === 'long' ? 1 : -1
    const priceMove = (price - t.entry) * dir
    const lots = t.lots ?? 0.01
    const pnl = priceMove * t.valuePerPricePerLot * lots
    const rec = { ...t, closedPrice: price, closeReason: reason,
      closedAt: Math.floor(Date.now() / 1000), priceMove, pnl,
      heldSec: Math.floor(Date.now() / 1000) - t.openedAt }
    this.closed.push(rec)
    delete this.open[asset]
    return rec
  }

  netPnl() { return this.closed.reduce((s, r) => s + r.pnl, 0) }
}

// ============================================================================
// تحلیلگرِ رفتار — هر رویداد را ثبت و «flicker/تناقض» را تشخیص می‌دهد.
// ============================================================================
class BehaviorAudit {
  constructor() {
    this.perAsset = {}   // asset → { states:[], entrySignals:0, transitions:[], entryPrices:[] }
  }
  ensure(asset) {
    if (!this.perAsset[asset]) this.perAsset[asset] = {
      states: [], prevState: null, entrySignals: 0, neutralAfterEntry: 0,
      entryPrices: [], entryTpSl: [], transitions: [], flickers: 0,
      distinctEntryOffers: 0, lastEntryOffer: null,
    }
    return this.perAsset[asset]
  }
  record(asset, dec, tick) {
    const a = this.ensure(asset)
    const st = dec.state
    a.states.push({ tick, st, price: dec.price })
    // شمارشِ گذارها
    if (a.prevState && a.prevState !== st) {
      a.transitions.push(`${a.prevState}→${st}`)
      // flicker = ENTRY→NEUTRAL یا برعکس در گذارهای متوالی (سیگنالِ ناپایدار)
      if ((a.prevState === 'ENTRY' && st === 'NEUTRAL') ||
          (a.prevState === 'NEUTRAL' && st === 'ENTRY')) a.flickers++
    }
    if (st === 'ENTRY') {
      a.entrySignals++
      // آیا offerِ ورود (entry/tp/sl) بین دو tick عوض می‌شود؟ (باگِ «TP/SL متغیر»)
      const offer = `${dec.direction}|${round(dec.entry)}|${round(dec.tp)}|${round(dec.sl)}`
      if (offer !== a.lastEntryOffer) { a.distinctEntryOffers++; a.lastEntryOffer = offer }
      a.entryPrices.push(dec.entry)
    }
    a.prevState = st
  }
}
const round = (x) => x == null ? '-' : Number(x).toFixed(4)

// ============================================================================
// حلقهٔ اصلی
// ============================================================================
async function main() {
  console.log('='.repeat(78))
  console.log(`  ابزارِ تست کیفیتِ سایت با قیمتِ لحظه‌ای  —  ${nowIso()}`)
  console.log(`  BASE=${BASE}  مدت=${MINUTES}دقیقه  پُلینگ=هر${INTERVAL_SEC}ثانیه  paper-broker=${AUTO_TRADE ? 'روشن' : 'خاموش'}`)
  console.log('='.repeat(78))

  // چک سلامت
  await jget('/api/health')

  const broker = new PaperBroker()
  const audit = new BehaviorAudit()
  const decMap = {}   // asset → decimals

  const endAt = Date.now() + MINUTES * 60 * 1000
  let tick = 0

  while (Date.now() < endAt) {
    tick++
    const tStr = nowIso().slice(11)
    let dResp
    try {
      dResp = await jget(`/api/decision?capital=${CAPITAL}&risk=${RISK}`)
    } catch (e) {
      console.log(`[${tStr}] tick#${tick} ❌ خطا در /api/decision: ${e.message}`)
      await sleep(INTERVAL_SEC * 1000); continue
    }

    // قیمتِ لحظه‌ای (مثلِ خودِ سایت) — موازی
    let spotResp = { spots: [] }
    try { spotResp = await jget('/api/spots') } catch {}
    const spotOf = {}
    for (const s of spotResp.spots || []) if (s.ok) spotOf[s.asset] = s.price

    for (const a of dResp.assets) {
      if (ASSET_FILTER && a.asset !== ASSET_FILTER) continue
      if (!a.ok) { console.log(`[${tStr}] ${a.asset} ❌ ${a.error}`); continue }
      const dec = a.decision
      dec.price = a.price
      decMap[a.asset] = a.decimals || 2
      const live = spotOf[a.asset] ?? a.price

      // اگر معاملهٔ باز داریم → این معامله را با قیمتِ لحظه‌ای مدیریت کن
      if (broker.hasOpen(a.asset)) {
        // ۱) TP/SL با قیمتِ spot
        const hit = broker.markPrice(a.asset, live)
        if (hit) {
          console.log(`[${tStr}] ${a.asset} 🔚 معامله بسته شد (${hit.closeReason}) @ ${round(hit.closedPrice)} | PnL=${hit.pnl.toFixed(2)}$ | نگه‌داری=${hit.heldSec}s`)
          continue
        }
        // ۲) توصیهٔ مدیریتیِ سایت (همان endpoint واقعی)
        const t = broker.open[a.asset]
        try {
          const adv = await jpost('/api/trade/advice', {
            asset: a.asset, trade: { side: t.side, entry: t.entry, tp: t.tp, sl: t.sl, openedAt: t.openedAt },
            modelProbPct: t.prob,
          })
          if (adv.ok && adv.status) {
            const crit = (adv.status.advices || []).filter(x => x.severity === 'critical')
            if (crit.length) {
              // سایت می‌گوید ببند → مثلِ کاربر عمل کن
              const rec = broker.closeTrade(a.asset, live, 'SITE_CLOSE:' + crit[0].title)
              console.log(`[${tStr}] ${a.asset} ⚠️ سایت دستورِ بستن داد: «${crit[0].title}» → بسته شد | PnL=${rec.pnl.toFixed(2)}$`)
            } else {
              console.log(`[${tStr}] ${a.asset} 🟦 MANAGE | pnlR=${adv.status.pnlR?.toFixed(2)} | ${adv.status.overallNote?.slice(0, 60) || ''}`)
            }
          }
        } catch (e) { /* ادامه */ }
        continue
      }

      // معاملهٔ باز نداریم → رفتارِ سیگنال را ثبت کن
      audit.record(a.asset, dec, tick)
      let extra = ''
      const prob = dec.probability ?? (dec.indicators?.find(i => i.name === 'احتمالِ مدل')?.value) ?? '?'
      if (dec.state === 'ENTRY') {
        extra = `DIR=${dec.direction} entry=${round(dec.entry)} tp=${round(dec.tp)} sl=${round(dec.sl)} lots=${dec.sizing?.lots ?? '-'} prob=${dec.probability}`
      } else {
        const er = dec.indicators?.find(i => i.name === 'کاراییِ روند (ER)')?.value || ''
        extra = `prob=${typeof prob === 'number' ? prob : prob} ER=${er}`
      }
      console.log(`[${tStr}] ${a.asset} state=${dec.state.padEnd(11)} live=${round(live)} ${extra}`)

      // paper-broker: اگر سایت ENTRY داد و ما معامله‌ای نداریم → مثلِ کاربر باز کن
      if (AUTO_TRADE && dec.state === 'ENTRY') {
        const t = broker.openTrade(a.asset, dec, a.decimals || 2)
        console.log(`   ➕ [کاربرِ دمو] معامله باز شد: ${t.side.toUpperCase()} ${a.asset} @ ${round(t.entry)} lots=${t.lots} (طبقِ دستورِ سایت)`)
      }
    }

    await sleep(INTERVAL_SEC * 1000)
  }

  // ---------------------- گزارشِ نهایی ----------------------
  printReport(audit, broker)
}

function printReport(audit, broker) {
  console.log('\n' + '='.repeat(78))
  console.log('  گزارشِ رفتاریِ سایت (کیفیت)')
  console.log('='.repeat(78))
  for (const [asset, a] of Object.entries(audit.perAsset)) {
    const total = a.states.length
    const counts = {}
    for (const s of a.states) counts[s.st] = (counts[s.st] || 0) + 1
    console.log(`\n▶ ${asset}  (تعدادِ نمونه: ${total})`)
    console.log(`   توزیعِ حالت: ${Object.entries(counts).map(([k, v]) => `${k}=${v}`).join('  ')}`)
    console.log(`   گذارها: ${a.transitions.length ? a.transitions.join(', ') : '—(پایدار، بدونِ گذار)'}`)
    console.log(`   🚨 flickerِ ENTRY↔NEUTRAL: ${a.flickers}`)
    if (a.entrySignals > 0) {
      console.log(`   سیگنال‌های ENTRY: ${a.entrySignals}  |  offerهای متمایز (entry/tp/sl عوض شد): ${a.distinctEntryOffers}`)
      if (a.entryPrices.length > 1) {
        const mn = Math.min(...a.entryPrices), mx = Math.max(...a.entryPrices)
        console.log(`   بازهٔ قیمتِ ورودِ پیشنهادی: ${mn.toFixed(4)} .. ${mx.toFixed(4)}  (اختلاف=${(mx - mn).toFixed(4)})`)
      }
    }
    // قضاوتِ کیفیت
    const verdicts = []
    if (a.flickers > 0) verdicts.push(`❌ ناپایدار: ${a.flickers} بار بینِ ورود/خنثی پرید (باگِ «پیشنهاد داد، خنثی شد»)`)
    if (a.distinctEntryOffers > 1) verdicts.push(`⚠️ offerِ ورود ناپایدار: ${a.distinctEntryOffers} پیشنهادِ متفاوتِ TP/SL (کاربر نمی‌داند کدام درست است)`)
    if (!verdicts.length) verdicts.push('✅ رفتارِ پایدار در این پنجره')
    verdicts.forEach(v => console.log('   ' + v))
  }

  console.log('\n' + '-'.repeat(78))
  console.log('  نتیجهٔ paper-broker (کاربرِ دمو که طبقِ دستورِ سایت معامله کرد)')
  console.log('-'.repeat(78))
  const closed = broker.closed
  if (!closed.length && !Object.keys(broker.open).length) {
    console.log('   هیچ معامله‌ای باز نشد (سایت در این پنجره ENTRY نداد یا فیلتر شد).')
  } else {
    for (const r of closed) {
      console.log(`   ${r.asset} ${r.side.toUpperCase()} entry=${r.entry.toFixed(4)} → close=${r.closedPrice.toFixed(4)} (${r.closeReason}) | حرکت=${r.priceMove.toFixed(4)} | PnL=${r.pnl.toFixed(2)}$ | ${r.heldSec}s`)
    }
    for (const [asset, t] of Object.entries(broker.open)) {
      console.log(`   ${asset} ${t.side.toUpperCase()} entry=${t.entry.toFixed(4)} → هنوز باز | MFE=${t.maxFavorable.toFixed(4)} MAE=${t.maxAdverse.toFixed(4)}`)
    }
    console.log(`\n   💰 سودِ خالصِ paper (بسته‌شده‌ها): ${broker.netPnl().toFixed(2)}$  |  تعدادِ بسته‌شده: ${closed.length}  |  باز: ${Object.keys(broker.open).length}`)
  }
  console.log('='.repeat(78))
}

main().catch(e => { console.error('FATAL:', e); process.exit(1) })
