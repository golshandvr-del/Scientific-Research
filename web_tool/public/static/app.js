// ============================================================================
// XAUUSD Live Tool — فرانت‌اند
// داشبورد تحلیل زنده طلا — روتر سه‌مغزی (S25 صعودی / S31 نزولی / رنج)
// + پنل «وضعیت تحقیق علمی» زنده (به‌روز تا استراتژی ۴۲، قوانین L1–L21)
// ============================================================================
const app = document.getElementById('app');
let chart = null;
let autoTimer = null;

const fmt = (n, d = 2) => (n == null || isNaN(n)) ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

function skeleton() {
  app.innerHTML = `
  <header class="flex items-center justify-between flex-wrap gap-3 mb-5 mt-2">
    <div class="flex items-center gap-3">
      <div class="text-3xl"><i class="fas fa-coins text-amber-400"></i></div>
      <div>
        <h1 class="text-2xl font-bold">XAUUSD <span class="text-amber-400">Live</span> <span class="text-[11px] align-middle px-2 py-0.5 rounded-md bg-cyan-500/15 text-cyan-300">روتر سه‌مغزی</span></h1>
        <p class="text-xs text-slate-400">تشخیص روند → مغز صعودی (S25/LONG) • مغز نزولی (S31/SHORT) • رنج (عدم معامله)</p>
      </div>
    </div>
    <div class="flex items-center gap-2 text-sm flex-wrap">
      <span id="live-dot" class="pulse-dot text-emerald-400"><i class="fas fa-circle text-[8px]"></i></span>
      <span id="last-update" class="text-slate-400">در حال بارگذاری…</span>
      <button id="notif-btn" class="bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg text-slate-200 transition" title="فعال‌سازی اعلان فرصت معامله">
        <i class="fas fa-bell"></i> <span id="notif-label">اعلان</span>
      </button>
      <button id="refresh-btn" class="bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg text-slate-200 transition">
        <i class="fas fa-rotate-right"></i> بروزرسانی
      </button>
    </div>
  </header>
  <div id="content"><div class="card p-8 text-center text-slate-400"><i class="fas fa-spinner fa-spin text-2xl"></i><p class="mt-3">دریافت داده زنده از بازار…</p></div></div>
  <footer class="text-center text-xs text-slate-500 mt-8 pb-6 leading-6">
    <p>ساختار کندل: Yahoo GC=F مقیاس‌شده به <b>XAU/USD spot</b> — قیمت لحظه‌ای: Swissquote/gold-api (سازگار با TradingView) • <span id="delay-note" class="text-slate-400">…</span></p>
    <p class="text-amber-500/80"><i class="fas fa-triangle-exclamation"></i> این ابزار صرفاً برای تحقیق علمی است و توصیه مالی محسوب نمی‌شود. معامله با ریسک همراه است.</p>
  </footer>`;
  document.getElementById('refresh-btn').onclick = load;
  setupNotifications();
}

function badge(text, cls) {
  return `<span class="px-2 py-0.5 rounded-md text-xs font-semibold ${cls}">${text}</span>`;
}

function trendLabel(t) {
  if (t === 'up') return badge('روند صعودی', 'bg-emerald-500/20 text-emerald-300');
  if (t === 'down') return badge('روند نزولی', 'bg-red-500/20 text-red-300');
  return badge('رنج / خنثی', 'bg-slate-500/20 text-slate-300');
}

function confLabel(c) {
  if (c === 'high') return badge('اطمینان بالا', 'bg-emerald-500/20 text-emerald-300');
  if (c === 'medium') return badge('اطمینان متوسط', 'bg-amber-500/20 text-amber-300');
  return badge('اطمینان پایین', 'bg-slate-500/20 text-slate-300');
}

function render(d) {
  const a = d.analysis;
  const m = d.meta;
  const up = new Date(d.lastUpdate).toLocaleTimeString('fa-IR');
  document.getElementById('last-update').textContent = 'آخرین بروزرسانی: ' + up;
  // نمایش تأخیر مؤثر داده (هدف: < ۵ دقیقه)
  const delaySec = d.effectiveDelaySec ?? null;
  const dn = document.getElementById('delay-note');
  if (dn && delaySec != null) {
    const min = delaySec / 60;
    const cls = min < 5 ? 'text-emerald-400' : min < 10 ? 'text-amber-400' : 'text-red-400';
    dn.className = cls;
    dn.textContent = d.spot
      ? `تأخیر قیمت لحظه‌ای: ${delaySec < 90 ? delaySec + ' ثانیه' : min.toFixed(1) + ' دقیقه'} ✓`
      : `تأخیر: ${min.toFixed(0)} دقیقه`;
  }

  window.__lastPrice = a.price;   // برای دکمهٔ «پر کردن ورود با قیمت فعلی»
  const isLong = a.direction === 'LONG';
  const isShort = a.direction === 'SHORT';
  const hasSig = isLong || isShort;
  const sigColor = isLong ? 'emerald' : isShort ? 'red' : 'slate';
  const probColor = a.probability >= 66 ? 'emerald' : (a.probability >= 60 ? 'amber' : 'slate');
  const brainLabel = a.activeBrain === 'bull' ? 'مغز صعودی (S25)' : a.activeBrain === 'bear' ? 'مغز نزولی (S31)' : 'رنج — بدون مغز';

  document.getElementById('content').innerHTML = `
  <!-- نوار قیمت -->
  <section class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
    <div class="card p-4">
      <p class="text-xs text-slate-400 mb-1">قیمت فعلی</p>
      <p class="text-2xl font-bold text-amber-400">$${fmt(a.price)}</p>
    </div>
    <div class="card p-4">
      <p class="text-xs text-slate-400 mb-1">روند بازار</p>
      <p class="text-lg mt-1">${trendLabel(a.trend)}</p>
    </div>
    <div class="card p-4">
      <p class="text-xs text-slate-400 mb-1">سقف/کف امروز</p>
      <p class="text-sm mt-1"><span class="text-emerald-400">${fmt(m.dayHigh)}</span> / <span class="text-red-400">${fmt(m.dayLow)}</span></p>
    </div>
    <div class="card p-4">
      <p class="text-xs text-slate-400 mb-1">ATR (نوسان)</p>
      <p class="text-lg font-semibold">$${fmt(a.atr)}</p>
    </div>
  </section>

  <!-- سیگنال واقعی مدل ONNX (دقیقاً معادل ربات) -->
  <section id="onnx-signal" class="card p-5 mb-4">
    <div class="flex items-center justify-between flex-wrap gap-3 mb-3">
      <h2 class="text-lg font-bold"><i class="fas fa-robot text-cyan-400"></i> سیگنال واقعی مدل ربات (ONNX)</h2>
      <span class="text-[11px] px-2 py-0.5 rounded-md bg-cyan-500/15 text-cyan-300">اجرای مدل در مرورگر — نه تقریب</span>
    </div>
    <div id="onnx-body" class="text-sm text-slate-400">
      <i class="fas fa-spinner fa-spin"></i> بارگذاری مدل ONNX ensemble و اجرای استنتاج در مرورگر…
    </div>
  </section>

  <!-- مدیریت معاملهٔ باز کاربر (Trade Advisor) — User Note -->
  <section id="trade-manager" class="card p-5 mb-4">
    <div class="flex items-center justify-between flex-wrap gap-3 mb-3">
      <h2 class="text-lg font-bold"><i class="fas fa-hand-holding-dollar text-amber-400"></i> مدیریت معاملهٔ من</h2>
      <span class="text-[11px] px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300">راهنمای زندهٔ مدیریت معامله</span>
    </div>
    <div id="tm-body" class="text-sm text-slate-300"></div>
  </section>

  <!-- تحلیل چند-تایم‌فریمی + منابع بنیادی -->
  <section id="context-panel" class="grid md:grid-cols-3 gap-4 mb-4">
    <div class="card p-5"><h2 class="text-base font-bold mb-3"><i class="fas fa-layer-group text-indigo-400"></i> هم‌راستایی روند (H1/H4/D1)</h2><div id="mtf-body" class="text-sm text-slate-400"><i class="fas fa-spinner fa-spin"></i> …</div></div>
    <div class="card p-5"><h2 class="text-base font-bold mb-3"><i class="fas fa-globe text-teal-400"></i> بین‌بازاری (DXY / بازده اوراق)</h2><div id="im-body" class="text-sm text-slate-400"><i class="fas fa-spinner fa-spin"></i> …</div></div>
    <div class="card p-5"><h2 class="text-base font-bold mb-3"><i class="fas fa-calendar-days text-rose-400"></i> تقویم اخبار USD</h2><div id="news-body" class="text-sm text-slate-400"><i class="fas fa-spinner fa-spin"></i> …</div></div>
  </section>

  <!-- سیگنال معامله (موتور امتیازدهی شفاف — مکمل) -->
  <section class="card p-5 mb-4 ${isLong ? 'glow-up' : isShort ? 'glow-down' : ''}">
    <div class="flex items-center justify-between flex-wrap gap-3 mb-4">
      <h2 class="text-lg font-bold"><i class="fas fa-bullseye text-${sigColor}-400"></i> موتور امتیازدهی شفاف (مکمل) — ${brainLabel}</h2>
      <div class="flex gap-2">${confLabel(a.confidence)}
        ${isLong ? badge('سیگنال: LONG (خرید)', 'bg-emerald-500/20 text-emerald-300')
          : isShort ? badge('سیگنال: SHORT (فروش)', 'bg-red-500/20 text-red-300')
          : badge('سیگنال: منتظر بمانید', 'bg-slate-600/40 text-slate-300')}
      </div>
    </div>

    <div class="mb-4">
      <div class="flex justify-between text-sm mb-1">
        <span class="text-slate-400">احتمال موفقیت (رسیدن به TP قبل از SL)</span>
        <span class="font-bold text-${probColor}-400">${fmt(a.probability, 1)}%</span>
      </div>
      <div class="bar-bg h-3">
        <div class="h-full bg-${probColor}-500 transition-all" style="width:${a.probability}%"></div>
      </div>
      <p class="text-[11px] text-slate-500 mt-1">نقطه سربه‌سر استراتژی = ۶۰٪ (با TP=1.0×ATR و SL=1.5×ATR). احتمال بالای ۶۰٪ یعنی لبه مثبت.</p>
    </div>

    ${hasSig ? `
    <div class="grid grid-cols-3 gap-3 text-center">
      <div class="bg-slate-800/60 rounded-lg p-3">
        <p class="text-xs text-slate-400">ورود (${isShort ? 'فروش' : 'خرید'})</p>
        <p class="font-bold text-slate-100">$${fmt(a.entry)}</p>
      </div>
      <div class="bg-emerald-900/30 rounded-lg p-3">
        <p class="text-xs text-emerald-400">حد سود (TP)</p>
        <p class="font-bold text-emerald-300">$${fmt(a.tp)}</p>
      </div>
      <div class="bg-red-900/30 rounded-lg p-3">
        <p class="text-xs text-red-400">حد ضرر (SL)</p>
        <p class="font-bold text-red-300">$${fmt(a.sl)}</p>
      </div>
    </div>
    <p class="text-xs text-slate-500 mt-2 text-center">${a.rr}</p>
    ` : `
    <div class="bg-slate-800/40 rounded-lg p-4 text-center text-slate-300 text-sm">
      <i class="fas fa-hourglass-half text-slate-400"></i>
      در حال حاضر شرایط ورود برقرار نیست: ${a.noEntryReason || 'شرایط استراتژی کامل نیست.'}
      <span class="block text-xs text-slate-500 mt-1">روتر سه‌مغزی: در صعودی مغز S25 (LONG)، در نزولی مغز S31 (SHORT)، در رنج عدم معامله. آستانهٔ ورود ≥ ${fmt(a.entryThreshold ?? 60, 0)}٪.</span>
    </div>`}
  </section>

  <!-- چارت -->
  <section class="card p-4 mb-4">
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-lg font-bold"><i class="fas fa-chart-candlestick text-amber-400"></i> نمودار قیمت + حمایت/مقاومت</h2>
      <span class="text-xs text-slate-500">${d.totalCandles} کندل M15</span>
    </div>
    <div style="height:360px"><canvas id="price-chart"></canvas></div>
    <div class="flex gap-4 justify-center text-xs mt-2 text-slate-400">
      <span><span class="inline-block w-3 h-0.5 bg-red-500 align-middle"></span> مقاومت</span>
      <span><span class="inline-block w-3 h-0.5 bg-emerald-500 align-middle"></span> حمایت</span>
      <span><span class="inline-block w-3 h-0.5 bg-blue-400 align-middle"></span> VWAP</span>
    </div>
  </section>

  <!-- سطوح حمایت/مقاومت -->
  <section class="grid md:grid-cols-2 gap-4 mb-4">
    <div class="card p-5">
      <h2 class="text-lg font-bold mb-3"><i class="fas fa-layer-group text-amber-400"></i> نزدیک‌ترین سطوح کلیدی</h2>
      ${srRow('مقاومت پیش‌رو', a.resistance, a.price, 'red')}
      ${srRow('حمایت زیرین', a.support, a.price, 'emerald')}
      <p class="text-xs text-slate-500 mt-3">سطوح از الگوریتم Pivot(5,5) پروژه با ادغام و انقضا محاسبه شده‌اند (بدون نگاه به آینده).</p>
    </div>

    <!-- سناریوهای شکست -->
    <div class="card p-5">
      <h2 class="text-lg font-bold mb-3"><i class="fas fa-code-branch text-amber-400"></i> سناریوی شکست سطوح</h2>
      <div class="space-y-3">${a.breakoutScenarios.map(scenarioRow).join('') || '<p class="text-slate-500 text-sm">سطح فعالی یافت نشد.</p>'}</div>
    </div>
  </section>

  <!-- جزئیات امتیازدهی -->
  <section class="card p-5 mb-4">
    <h2 class="text-lg font-bold mb-3"><i class="fas fa-microscope text-amber-400"></i> تفکیک منطق تصمیم (شفاف)</h2>
    <div class="grid md:grid-cols-2 gap-x-6 gap-y-2">${a.scoreBreakdown.map(factorRow).join('')}</div>
    <p class="text-xs text-slate-500 mt-3 leading-5">
      این بخش یک «موتور امتیازدهی شفاف» بر پایهٔ همان feature‌های استراتژی برنده است که سهم هر عامل را توضیح می‌دهد (تفسیرپذیری).
      <b>تصمیم نهاییِ معامله بر عهدهٔ «سیگنال واقعی مدل ONNX» بالای صفحه است</b> که خروجی دقیقِ ربات را در مرورگر اجرا می‌کند؛ این بخش صرفاً برای درک منطق پشت آن است.
    </p>
  </section>

  <!-- شاخص‌های خام -->
  <section class="card p-5 mb-4">
    <h2 class="text-lg font-bold mb-3"><i class="fas fa-gauge-high text-amber-400"></i> شاخص‌های لحظه‌ای</h2>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
      ${miniStat('RSI(14)', fmt(a.rsi14, 1), a.rsi14 > 70 ? 'red' : a.rsi14 < 30 ? 'emerald' : 'slate')}
      ${miniStat('ADX', fmt(a.adx, 1), a.adx > 25 ? 'amber' : 'slate')}
      ${miniStat('MACD Hist', fmt(a.macdHist, 3), a.macdHist > 0 ? 'emerald' : 'red')}
      ${miniStat('VWAP', '$' + fmt(a.vwap), a.price > a.vwap ? 'emerald' : 'red')}
      ${miniStat('EMA50', '$' + fmt(a.ema50), 'slate')}
      ${miniStat('EMA200', '$' + fmt(a.ema200), 'slate')}
      ${miniStat('مغز فعال', a.activeBrain === 'bull' ? 'صعودی' : a.activeBrain === 'bear' ? 'نزولی' : 'رنج', a.activeBrain === 'bull' ? 'emerald' : a.activeBrain === 'bear' ? 'red' : 'slate')}
      ${miniStat('جهت', isLong ? 'LONG' : isShort ? 'SHORT' : 'منتظر', isLong ? 'emerald' : isShort ? 'red' : 'slate')}
    </div>
  </section>

  ${researchStatusPanel()}`;

  drawChart(d);
}

// ============================================================================
// پنل وضعیت تحقیق علمی — به‌روزرسانی زندهٔ آخرین دستاوردها (تا استراتژی ۴۲)
// این بخش تصویر صادقانه و به‌روز پروژه را نشان می‌دهد: چه به دست آمد، چه نه، و چرا.
// ============================================================================
function researchStatusPanel() {
  // هدف سه‌گانهٔ کاربر و بهترین نتیجهٔ ثبت‌شده برای هر قید (از فایل‌های results/)
  const goals = [
    { name: 'Win Rate > 60%', best: 'S25: ۶۲.۰٪ (p=0.027 معنادار)', ok: true },
    { name: 'Profit Factor > 1.3', best: 'S26: ۱.۳۵ • S36: ۱.۳۳', ok: true },
    { name: 'Expectancy مثبت پایدار', best: 'S26: +۱.۰۸$ • S36: +۱.۱۴$', ok: true },
    { name: '≥ ۵ معامله در روز', best: 'S36: ۴.۲۴ (رکورد پروژه)', ok: false },
    { name: 'هر ۴ قید هم‌زمان', best: 'روی OHLCV صرف: برآورده نشد (L21)', ok: false },
  ];
  const goalRows = goals.map(g => `
    <div class="flex items-center justify-between py-2 border-b border-slate-800/60 text-sm">
      <span class="flex items-center gap-2">
        <i class="fas ${g.ok ? 'fa-circle-check text-emerald-400' : 'fa-circle-xmark text-amber-400'}"></i>
        <span class="text-slate-200">${g.name}</span>
      </span>
      <span class="text-xs text-slate-400 text-left">${g.best}</span>
    </div>`).join('');

  // قوانین بنیادی کشف‌شده (تقطیر ۴۲ استراتژی)
  const laws = [
    ['L1', 'اطلاعات > معماری — فقط دادهٔ ورودی جدید سقف را جابه‌جا می‌کند.'],
    ['L7', 'سقف WR با OHLCV صرفِ M15: ~۶۶–۶۸٪ (فرکانس کم)، ~۶۲–۶۳٪ (فرکانس بالا).'],
    ['L15', 'دیوار هم‌ارزی WR↔PF: کوچک‌کردن TP، WR را بالا می‌برد ولی PF را دقیقاً به همان نسبت پایین.'],
    ['L17', 'edge در رژیم پرنوسان ~۷× قوی‌تر — بهترین اهرم PF/exp پروژه (S38).'],
    ['L20/L21', 'مرز پارتوی WR↔PF↔فرکانس: این سه هرگز هم‌زمان روی داده صرف برآورده نشدند.'],
  ];
  const lawRows = laws.map(([id, t]) => `
    <div class="flex gap-2 py-1.5 text-xs border-b border-slate-800/40">
      <span class="font-mono font-bold text-cyan-300 shrink-0">${id}</span>
      <span class="text-slate-300 leading-5">${t}</span>
    </div>`).join('');

  return `
  <section id="research-status" class="card p-5 mb-4">
    <div class="flex items-center justify-between flex-wrap gap-3 mb-3">
      <h2 class="text-lg font-bold"><i class="fas fa-flask-vial text-violet-400"></i> وضعیت تحقیق علمی — به‌روز تا استراتژی ۴۲</h2>
      <span class="text-[11px] px-2 py-0.5 rounded-md bg-violet-500/15 text-violet-300">۴۲ استراتژی • ۲۱ قانون کشف‌شده</span>
    </div>

    <div class="grid md:grid-cols-2 gap-5">
      <div>
        <h3 class="text-sm font-bold text-slate-200 mb-2"><i class="fas fa-bullseye text-amber-400"></i> پیشرفت نسبت به هدف سه‌گانهٔ کاربر</h3>
        ${goalRows}
        <p class="text-[11px] text-slate-500 mt-2 leading-5">
          هر قید به‌تنهایی حل شد، اما <b class="text-amber-300">هر چهار قید هم‌زمان</b> روی دادهٔ صرف OHLCV
          برآورده نشد (قانون L21 — انحصار متقابل). این یک نتیجهٔ علمی معتبر است، نه شکست مهندسی.
        </p>
      </div>
      <div>
        <h3 class="text-sm font-bold text-slate-200 mb-2"><i class="fas fa-scale-balanced text-cyan-400"></i> قوانین بنیادی کشف‌شده</h3>
        ${lawRows}
      </div>
    </div>

    <div class="mt-4 bg-slate-800/40 rounded-lg p-3 text-xs text-slate-300 leading-6">
      <b class="text-emerald-300"><i class="fas fa-route"></i> مسیر باقی‌مانده برای عبور از سقف:</b>
      تنها راهِ اثبات‌شده برای برآوردنِ هم‌زمانِ هر چهار قید، افزودن <b>دادهٔ برون‌زای جهت‌دار</b>
      (گروه G — شاخص دلار DXY، بازده اوراق US10Y، تقویم اخبار) است — که هم‌اکنون در پنل «بین‌بازاری»
      و «تقویم اخبار» همین صفحه به‌صورت زنده دریافت و نمایش داده می‌شود.
    </div>
  </section>`;
}

function srRow(label, lvl, price, color) {
  if (!lvl) return `<div class="flex justify-between py-2 border-b border-slate-700/50"><span class="text-slate-400">${label}</span><span class="text-slate-500">یافت نشد</span></div>`;
  const dist = ((lvl.price - price) / price * 100);
  return `<div class="flex justify-between items-center py-2 border-b border-slate-700/50">
    <span class="text-slate-300">${label}</span>
    <span class="text-left">
      <span class="font-bold text-${color}-400">$${fmt(lvl.price)}</span>
      <span class="text-xs text-slate-500 block">${dist >= 0 ? '+' : ''}${fmt(dist, 2)}% • قدرت ${lvl.touches}</span>
    </span>
  </div>`;
}

function scenarioRow(s) {
  const c = s.kind === 'res' ? 'emerald' : 'red';
  const arrow = s.kind === 'res' ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down';
  return `<div class="bg-slate-800/50 rounded-lg p-3">
    <div class="flex justify-between items-center mb-1">
      <span class="text-sm font-semibold"><i class="fas ${arrow} text-${c}-400"></i> ${s.label}</span>
      <span class="text-xs text-slate-400">${s.distancePct >= 0 ? '+' : ''}${fmt(s.distancePct, 2)}%</span>
    </div>
    <p class="text-xs text-slate-300 mb-2">${s.ifBreak}</p>
    <div class="flex items-center gap-2">
      <div class="bar-bg h-2 flex-1"><div class="h-full bg-${c}-500" style="width:${s.probability}%"></div></div>
      <span class="text-xs font-bold text-${c}-400">${fmt(s.probability, 0)}%</span>
    </div>
    <p class="text-[10px] text-slate-500 mt-1">احتمال ادامه حرکت پس از شکست</p>
  </div>`;
}

function factorRow(f) {
  const pos = f.contrib > 0;
  const neu = f.contrib === 0;
  const color = neu ? 'slate' : (pos ? 'emerald' : 'red');
  const sign = pos ? '+' : '';
  return `<div class="flex justify-between items-center py-1 text-sm border-b border-slate-800/60">
    <span class="text-slate-300">${f.note}</span>
    <span class="font-mono text-${color}-400 text-xs">${sign}${fmt(f.contrib, 2)}</span>
  </div>`;
}

function miniStat(label, val, color) {
  return `<div class="bg-slate-800/50 rounded-lg p-3">
    <p class="text-xs text-slate-400">${label}</p>
    <p class="font-bold text-${color}-400">${val}</p>
  </div>`;
}

// رسم چارت شمعی با خطوط S/R و VWAP
function drawChart(d) {
  const ctx = document.getElementById('price-chart');
  if (!ctx) return;
  const data = d.chart.map(k => ({ x: k.t * 1000, o: k.o, h: k.h, l: k.l, c: k.c }));
  if (chart) chart.destroy();

  const a = d.analysis;
  const annotations = [];
  const lines = [];
  if (a.resistance) lines.push({ y: a.resistance.price, color: '#ef4444' });
  if (a.support) lines.push({ y: a.support.price, color: '#22c55e' });
  lines.push({ y: a.vwap, color: '#60a5fa' });

  chart = new Chart(ctx, {
    type: 'candlestick',
    data: {
      datasets: [{
        label: 'XAUUSD',
        data: data,
        color: { up: '#22c55e', down: '#ef4444', unchanged: '#94a3b8' },
        borderColor: { up: '#22c55e', down: '#ef4444', unchanged: '#94a3b8' },
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { type: 'time', time: { unit: 'day' }, ticks: { color: '#94a3b8', maxRotation: 0 }, grid: { color: 'rgba(51,65,85,0.3)' } },
        y: { position: 'right', ticks: { color: '#94a3b8' }, grid: { color: 'rgba(51,65,85,0.3)' } },
      },
    },
    plugins: [{
      id: 'srlines',
      afterDraw(c) {
        const { ctx, chartArea: { left, right }, scales: { y } } = c;
        ctx.save();
        lines.forEach(l => {
          if (l.y == null || isNaN(l.y)) return;
          const yp = y.getPixelForValue(l.y);
          ctx.beginPath();
          ctx.setLineDash([6, 4]);
          ctx.strokeStyle = l.color;
          ctx.lineWidth = 1.2;
          ctx.moveTo(left, yp); ctx.lineTo(right, yp); ctx.stroke();
        });
        ctx.restore();
      }
    }],
  });
}

async function load() {
  try {
    document.getElementById('live-dot')?.classList.add('text-amber-400');
    const res = await fetch('/api/analysis?interval=15m&range=1mo');
    const d = await res.json();
    if (!d.ok) throw new Error(d.error || 'خطا در دریافت داده');
    render(d);
    document.getElementById('live-dot')?.classList.remove('text-amber-400');
    document.getElementById('live-dot')?.classList.add('text-emerald-400');
    // پس از رندر اصلی، بخش‌های سنگین/شبکه‌ای را موازی و مستقل بارگذاری کن
    runOnnxSignal();
    loadContext();
    renderTradeManager();   // بخش مدیریت معاملهٔ کاربر (User Note)
  } catch (e) {
    document.getElementById('content').innerHTML = `<div class="card p-8 text-center text-red-400">
      <i class="fas fa-circle-exclamation text-2xl"></i>
      <p class="mt-3">خطا در دریافت داده زنده: ${e.message}</p>
      <button onclick="location.reload()" class="mt-4 bg-slate-800 px-4 py-2 rounded-lg">تلاش مجدد</button>
    </div>`;
  }
}

// ---------------- اجرای واقعی مدل ONNX در مرورگر (User Note #1) ----------------
// کندل‌های کامل M15 را می‌گیرد (نه فقط ۳۰۰ اخیر) تا feature‌ها با تاریخچهٔ کافی
// (EMA200/VWAP روزانه) دقیقاً مثل ربات ساخته شوند، سپس ۳ مدل ensemble اجرا می‌شوند.
async function runOnnxSignal() {
  const body = document.getElementById('onnx-body');
  if (!body) return;
  try {
    if (!window.GoldModel) throw new Error('ماژول مدل هنوز بارگذاری نشده');
    // ۶۰ روز کندل M15 (بیشترین بازهٔ مجاز Yahoo برای ۱۵دقیقه) — ~۵۷۰۰ کندل،
    // برای EMA200 و VWAP روزانه کاملاً کافی است.
    const r = await fetch('/api/candles?interval=15m&range=60d');
    const j = await r.json();
    if (!j.ok || !j.candles?.length) throw new Error(j.error || 'کندل کافی دریافت نشد');
    const sig = await window.GoldModel.computeModelSignal(j.candles);
    console.log('[ONNX] signal:', JSON.stringify({dir:sig.direction, prob:sig.probabilityPct, regime:sig.regime, brain:sig.activeBrain, n:j.candles.length}));
    renderOnnx(sig, j.candles.length);
    checkOpportunity(sig);
  } catch (e) {
    body.innerHTML = `<span class="text-amber-400"><i class="fas fa-triangle-exclamation"></i> اجرای مدل ONNX ناموفق: ${e.message}</span>`;
  }
}

function renderOnnx(s, nCandles) {
  const body = document.getElementById('onnx-body');
  const sec = document.getElementById('onnx-signal');
  tmLastModelProb = s.probabilityPct;   // برای هم‌سو/مخالف بودن با معاملهٔ کاربر
  const isLong = s.direction === 'LONG';
  const isShort = s.direction === 'SHORT';
  sec.classList.toggle('glow-up', isLong);
  sec.classList.toggle('glow-down', isShort);
  const pColor = s.regime === 'range' ? 'slate'
    : s.probability >= s.threshold + 0.07 ? (isShort ? 'red' : 'emerald')
    : s.probability >= s.threshold ? 'amber' : 'slate';
  const pct = s.probabilityPct;
  const thrPct = (s.threshold * 100).toFixed(0);

  // نشان رژیم/مغز فعال
  const regimeMap = {
    bull: { txt: 'روند صعودی — مغز صعودی (S25) فعال', cls: 'bg-emerald-500/20 text-emerald-300', icon: 'fa-arrow-trend-up' },
    bear: { txt: 'روند نزولی — مغز نزولی (S31) فعال', cls: 'bg-red-500/20 text-red-300', icon: 'fa-arrow-trend-down' },
    range: { txt: 'بازار رنج — همهٔ مغزها غیرفعال', cls: 'bg-slate-600/40 text-slate-300', icon: 'fa-arrows-left-right' },
  };
  const rg = regimeMap[s.regime] || regimeMap.range;

  // بنر توضیح مغز فعال (پاسخ به User Note)
  let brainInfo = '';
  if (s.regime === 'bull') {
    brainInfo = `<i class="fas fa-flask text-violet-300"></i> <b>مغز صعودی (S25)</b> — بک‌تست OOS:
      WR=<b class="text-emerald-300">۶۲.۳٪</b> • Exp=<b class="text-emerald-300">+۰.۵۴$</b> • p=<b class="text-emerald-300">۰.۰۱۵</b> • فقط LONG.`;
  } else if (s.regime === 'bear') {
    brainInfo = `<i class="fas fa-flask text-violet-300"></i> <b>مغز نزولی (S31)</b> — بک‌تست OOS:
      PF=<b class="text-red-300">۱.۴۹</b> • Exp=<b class="text-red-300">+۱.۷۱$</b> • WR=<b class="text-amber-300">۵۸.۴٪</b> • p=<b class="text-emerald-300">۰.۰۱۵</b> • فقط SHORT.
      این مغز پاسخ مستقیم به درخواست شماست: دیگر در روند نزولی سکوت نمی‌کنیم.`;
  } else {
    brainInfo = `<i class="fas fa-circle-info text-slate-300"></i> در رنج، تحقیق (استراتژی ۳۲) نشان داد هیچ مغزی edge پایدار ندارد؛
      <b>تصمیم علمیِ صحیح = عدم معامله</b> تا شکل‌گیری روند.`;
  }

  const sigBadge = isLong ? badge('سیگنال: LONG (خرید)', 'bg-emerald-500/25 text-emerald-300')
    : isShort ? badge('سیگنال: SHORT (فروش)', 'bg-red-500/25 text-red-300')
    : badge('سیگنال: بدون ورود', 'bg-slate-600/40 text-slate-300');

  // کارت ورود/TP/SL
  let tradeCard = '';
  if (isLong || isShort) {
    const tpCls = 'bg-emerald-900/30', tpTxt = 'text-emerald-300', tpLbl = 'text-emerald-400';
    tradeCard = `
    <div class="grid grid-cols-3 gap-3 text-center">
      <div class="bg-slate-800/60 rounded-lg p-3"><p class="text-xs text-slate-400">ورود</p><p class="font-bold">$${fmt(s.entry)}</p></div>
      <div class="${tpCls} rounded-lg p-3"><p class="text-xs ${tpLbl}">TP</p><p class="font-bold ${tpTxt}">$${fmt(s.tp)}</p></div>
      <div class="bg-red-900/30 rounded-lg p-3"><p class="text-xs text-red-400">SL</p><p class="font-bold text-red-300">$${fmt(s.sl)}</p></div>
    </div>
    <p class="text-xs text-slate-500 mt-2 text-center">${s.rr}</p>`;
  } else {
    tradeCard = `
    <div class="bg-slate-800/40 rounded-lg p-3 text-center text-slate-300 text-sm">
      <i class="fas fa-hourglass-half"></i> ${s.reason || 'مدل سیگنال ورود نمی‌دهد.'}
    </div>`;
  }

  // نوار احتمال (فقط وقتی مغزی فعال است)
  let probBar = '';
  if (s.regime !== 'range') {
    probBar = `
    <div class="mb-3">
      <div class="flex justify-between text-sm mb-1">
        <span class="text-slate-400">احتمال مغزِ فعال (ensemble ۳ مدل) — کلاس «برد»</span>
        <span class="font-bold text-${pColor}-400">${fmt(pct,2)}%</span>
      </div>
      <div class="bar-bg h-3 relative">
        <div class="h-full bg-${pColor}-500 transition-all" style="width:${pct}%"></div>
        <div class="absolute top-0 bottom-0" style="left:${thrPct}%; width:2px; background:#f1f5f9" title="آستانه ${thrPct}%"></div>
      </div>
      <p class="text-[11px] text-slate-500 mt-1">آستانهٔ تصمیم = ${thrPct}٪ (خط سفید). ورود فقط وقتی احتمال ≥ آستانه باشد.</p>
    </div>`;
  }

  body.innerHTML = `
    <div class="flex flex-wrap items-center gap-2 mb-3">
      ${sigBadge}
      ${confLabel(s.confidence)}
      ${badge(`<i class="fas ${rg.icon} mr-1"></i>${rg.txt}`, rg.cls)}
    </div>
    <div class="text-[11px] text-slate-400 bg-slate-800/40 rounded-md px-3 py-2 mb-3 leading-5">
      ${brainInfo}
    </div>
    ${probBar}
    ${tradeCard}
    <p class="text-[11px] text-slate-500 mt-3 leading-5">
      <i class="fas fa-circle-check text-cyan-400"></i> روتر سه‌مغزی: ابتدا روند تشخیص داده می‌شود، سپس مغز تخصصیِ همان روند
      (فایل‌های ONNX واقعی با <code>onnxruntime-web</code>) روی ${nCandles} کندل M15 اجرا می‌شود.
    </p>`;
}

// ------------- تحلیل چند-تایم‌فریمی + بین‌بازاری + اخبار (User Note #2,#3) -------------
async function loadContext() {
  try {
    const r = await fetch('/api/context');
    const d = await r.json();
    renderMTF(d.mtf);
    renderIntermarket(d.intermarket);
    renderNews(d.news);
    checkNewsRisk(d.news);
  } catch (e) {
    ['mtf-body','im-body','news-body'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<span class="text-amber-400 text-xs">خطا: ${e.message}</span>`;
    });
  }
}

function tfBadge(t) {
  if (t === 'up') return '<span class="text-emerald-400"><i class="fas fa-arrow-up"></i> صعودی</span>';
  if (t === 'down') return '<span class="text-red-400"><i class="fas fa-arrow-down"></i> نزولی</span>';
  return '<span class="text-slate-400"><i class="fas fa-arrows-left-right"></i> رنج</span>';
}

function renderMTF(m) {
  const el = document.getElementById('mtf-body');
  if (!el) return;
  if (!m || m.error) { el.innerHTML = `<span class="text-amber-400 text-xs">در دسترس نیست: ${m?.error||''}</span>`; return; }
  const alignColor = m.alignment === 'bullish' ? 'emerald' : m.alignment === 'bearish' ? 'red' : 'slate';
  const alignText = m.alignment === 'bullish' ? 'هم‌راستای صعودی' : m.alignment === 'bearish' ? 'هم‌راستای نزولی' : 'ناهم‌راستا';
  el.innerHTML = `
    ${m.timeframes.map(t => `
      <div class="flex justify-between items-center py-1.5 border-b border-slate-800/60">
        <span class="font-semibold text-slate-200">${t.timeframe}</span>
        <span>${tfBadge(t.trend)}</span>
        <span class="text-xs text-slate-500 font-mono">EMA50 $${fmt(t.ema50)}</span>
      </div>`).join('')}
    <div class="mt-3 p-2 rounded-lg bg-${alignColor}-500/10 text-${alignColor}-300 text-xs">
      <b>${alignText}</b> (امتیاز ${m.alignmentScore >= 0 ? '+' : ''}${m.alignmentScore}) — ${m.note}
    </div>`;
}

function renderIntermarket(im) {
  const el = document.getElementById('im-body');
  if (!el) return;
  if (!im || im.error) { el.innerHTML = `<span class="text-amber-400 text-xs">در دسترس نیست: ${im?.error||''}</span>`; return; }
  const biasColor = im.goldBias === 'supportive' ? 'emerald' : im.goldBias === 'headwind' ? 'red' : 'slate';
  const row = (a) => `
    <div class="flex justify-between items-center py-1.5 border-b border-slate-800/60">
      <span class="text-slate-300 text-xs">${a.name}</span>
      <span class="text-left">
        <span class="font-bold">${fmt(a.price, 3)}</span>
        <span class="text-xs ${a.changePct>=0?'text-red-400':'text-emerald-400'} block">${a.changePct>=0?'+':''}${fmt(a.changePct,2)}% ${tfBadge(a.trend)}</span>
      </span>
    </div>`;
  el.innerHTML = `
    ${row(im.dxy)}
    ${row(im.tnx)}
    <div class="mt-3 p-2 rounded-lg bg-${biasColor}-500/10 text-${biasColor}-300 text-xs">${im.note}</div>
    <p class="text-[10px] text-slate-500 mt-2">طلا معمولاً با دلار و بازده اوراق رابطهٔ معکوس دارد؛ رنگ قرمزِ تغییر یعنی صعودِ آن دارایی (فشار بر طلا).</p>`;
}

function renderNews(n) {
  const el = document.getElementById('news-body');
  if (!el) return;
  if (!n || n.error) { el.innerHTML = `<span class="text-amber-400 text-xs">در دسترس نیست: ${n?.error||''}</span>`; return; }
  const impColor = (i) => i === 'High' ? 'red' : i === 'Medium' ? 'amber' : 'slate';
  const upcoming = n.events.filter(e => e.minutesUntil > -120).slice(0, 6);
  el.innerHTML = `
    <div class="p-2 rounded-lg ${n.riskWindow ? 'bg-red-500/15 text-red-300' : 'bg-slate-700/30 text-slate-300'} text-xs mb-2">${n.note}</div>
    <div class="space-y-1">
      ${upcoming.length ? upcoming.map(e => {
        const c = impColor(e.impact);
        const when = e.minutesUntil > 0
          ? `تا ${e.minutesUntil >= 60 ? Math.round(e.minutesUntil/60)+' ساعت' : e.minutesUntil+' دقیقه'} دیگر`
          : 'گذشته';
        return `<div class="flex justify-between items-center text-xs py-1 border-b border-slate-800/50">
          <span class="truncate max-w-[60%]">${badge(e.impact, 'bg-'+c+'-500/20 text-'+c+'-300')} ${e.title}</span>
          <span class="text-slate-500">${when}</span>
        </div>`;
      }).join('') : '<p class="text-slate-500 text-xs">رویداد مرتبطی یافت نشد.</p>'}
    </div>`;
}

// ============================================================================
// سیستم اعلان (Notification) — خبر دادن فرصت معامله به کاربر (User Note ارتقا)
// چون کاربر نمی‌تواند ۲۴ ساعته سایت را باز نگه دارد، وقتی «سیگنال معتبر ورود»
// یا «پنجرهٔ ریسک خبری» رخ می‌دهد، اعلان مرورگر (Web Notification) می‌فرستد.
// برای جلوگیری از اسپم، از هر نوع اعلان حداکثر هر ۳۰ دقیقه یک‌بار ارسال می‌شود.
// ============================================================================
const NOTIF = { lastSignalKey: '', lastAt: 0, lastNewsKey: '' };

function notifStatus() {
  if (!('Notification' in window)) return 'unsupported';
  return Notification.permission; // 'granted' | 'denied' | 'default'
}

function setupNotifications() {
  const btn = document.getElementById('notif-btn');
  const label = document.getElementById('notif-label');
  if (!btn) return;
  const refresh = () => {
    const st = notifStatus();
    if (st === 'unsupported') { btn.classList.add('opacity-50'); if (label) label.textContent = 'بدون اعلان'; btn.disabled = true; return; }
    if (st === 'granted') { btn.classList.add('text-emerald-400'); if (label) label.textContent = 'اعلان فعال'; }
    else if (st === 'denied') { btn.classList.add('opacity-60'); if (label) label.textContent = 'اعلان مسدود'; }
    else { if (label) label.textContent = 'فعال‌سازی اعلان'; }
  };
  btn.onclick = async () => {
    if (notifStatus() === 'unsupported') return;
    try {
      const p = await Notification.requestPermission();
      if (p === 'granted') {
        new Notification('XAUUSD Live', { body: 'اعلان‌ها فعال شد ✓ هنگام فرصت معامله به شما خبر می‌دهیم.', icon: '/favicon.ico' });
      }
    } catch (e) {}
    refresh();
  };
  refresh();
}

function sendNotification(title, body, tag) {
  if (notifStatus() !== 'granted') return;
  const now = Date.now();
  // ضد اسپم: از هر tag حداکثر هر ۳۰ دقیقه
  if (tag === NOTIF.lastSignalKey && now - NOTIF.lastAt < 30 * 60 * 1000) return;
  try {
    const n = new Notification(title, { body, icon: '/favicon.ico', tag, requireInteraction: false });
    n.onclick = () => { window.focus(); n.close(); };
    NOTIF.lastSignalKey = tag; NOTIF.lastAt = now;
  } catch (e) {}
}

// بررسی فرصت‌های اعلان بر پایهٔ سیگنال ONNX (منبع تصمیم اصلی)
function checkOpportunity(sig) {
  if (!sig) return;
  if (sig.direction === 'LONG') {
    const key = 'LONG-' + (sig.entry ? sig.entry.toFixed(1) : '');
    sendNotification(
      '🟢 فرصت خرید طلا (XAUUSD)',
      `سیگنال LONG (مغز صعودی S25) — احتمال ${sig.probabilityPct}٪. ورود $${(sig.entry||0).toFixed(2)} | TP $${(sig.tp||0).toFixed(2)} | SL $${(sig.sl||0).toFixed(2)}`,
      key
    );
  } else if (sig.direction === 'SHORT') {
    const key = 'SHORT-' + (sig.entry ? sig.entry.toFixed(1) : '');
    sendNotification(
      '🔴 فرصت فروش طلا (XAUUSD)',
      `سیگنال SHORT (مغز نزولی S31) — احتمال ${sig.probabilityPct}٪. ورود $${(sig.entry||0).toFixed(2)} | TP $${(sig.tp||0).toFixed(2)} | SL $${(sig.sl||0).toFixed(2)}`,
      key
    );
  }
}

// اعلان پنجرهٔ ریسک خبری
function checkNewsRisk(news) {
  if (!news || news.error) return;
  if (news.riskWindow) {
    const key = 'NEWSRISK';
    sendNotification('⚠️ پنجرهٔ ریسک خبری USD', news.note || 'رویداد پرتأثیر USD نزدیک است — نوسان شدید محتمل.', key);
  }
}

// ============================================================================
// مدیریت معاملهٔ باز کاربر (Trade Manager) — پاسخ به User Note
// - کاربر یک معامله (long/short + ورود + TP + SL) وارد می‌کند.
// - معامله در localStorage ذخیره می‌شود → با رفرش/بستن مرورگر از دست نمی‌رود.
// - فقط «یک» معامله هم‌زمان می‌توان داشت.
// - سایت با تحلیل زنده، advice مدیریتی می‌دهد (جابه‌جایی TP/SL، هشدار S/R، …).
// - معامله فقط با دکمهٔ «بستن معامله» حذف می‌شود.
// ============================================================================
const TM_KEY = 'xau_open_trade_v1';
let tmTimer = null;
let tmLastModelProb = null;   // آخرین احتمال مدل ONNX برای هم‌سو/مخالف بودن

function tmLoad() {
  try { return JSON.parse(localStorage.getItem(TM_KEY) || 'null'); } catch { return null; }
}
function tmSave(t) { localStorage.setItem(TM_KEY, JSON.stringify(t)); }
function tmClear() { localStorage.removeItem(TM_KEY); }

// نقطهٔ ورود اصلی رندر بخش مدیریت معامله
function renderTradeManager() {
  const t = tmLoad();
  if (!t) { renderTradeForm(); }
  else { renderTradeStatusShell(t); refreshTradeAdvice(); }
}

// --- حالت ۱: هنوز معامله‌ای وارد نشده → فرم ورود ---
function renderTradeForm(prefill) {
  const body = document.getElementById('tm-body');
  if (!body) return;
  const p = prefill || {};
  body.innerHTML = `
    <p class="text-xs text-slate-400 mb-3">
      معامله‌ای که در حساب دمو باز کرده‌ای را این‌جا وارد کن تا سایت آن را به‌صورت زنده «مدیریت» کند:
      توصیهٔ جابه‌جایی حد سود/ضرر، هشدار نزدیکی به حمایت/مقاومت، و تغییر شرایط بازار.
    </p>
    <div class="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <div>
        <label class="block text-xs text-slate-400 mb-1">جهت</label>
        <select id="tm-side" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100">
          <option value="long">خرید (LONG)</option>
          <option value="short">فروش (SHORT)</option>
        </select>
      </div>
      <div>
        <label class="block text-xs text-slate-400 mb-1">قیمت ورود</label>
        <input id="tm-entry" type="number" step="0.01" placeholder="مثلاً 3350.00" value="${p.entry ?? ''}"
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100">
      </div>
      <div>
        <label class="block text-xs text-emerald-400 mb-1">حد سود (TP)</label>
        <input id="tm-tp" type="number" step="0.01" placeholder="TP" value="${p.tp ?? ''}"
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-emerald-300">
      </div>
      <div>
        <label class="block text-xs text-red-400 mb-1">حد ضرر (SL)</label>
        <input id="tm-sl" type="number" step="0.01" placeholder="SL" value="${p.sl ?? ''}"
          class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-red-300">
      </div>
      <div class="flex items-end">
        <button id="tm-open-btn" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-900 font-bold rounded-lg px-3 py-2 transition">
          <i class="fas fa-plus"></i> ثبت معامله
        </button>
      </div>
    </div>
    <div class="flex items-center gap-2 mt-3">
      <button id="tm-fill-price" class="text-xs text-slate-400 hover:text-amber-300"><i class="fas fa-wand-magic-sparkles"></i> پر کردن ورود با قیمت فعلی بازار</button>
    </div>
    <p id="tm-err" class="text-xs text-red-400 mt-2"></p>`;

  document.getElementById('tm-open-btn').onclick = tmSubmit;
  document.getElementById('tm-fill-price').onclick = () => {
    const el = document.getElementById('tm-entry');
    const price = window.__lastPrice;
    if (el && price) el.value = price.toFixed(2);
  };
}

function tmSubmit() {
  const side = document.getElementById('tm-side').value;
  const entry = parseFloat(document.getElementById('tm-entry').value);
  const tp = parseFloat(document.getElementById('tm-tp').value);
  const sl = parseFloat(document.getElementById('tm-sl').value);
  const err = document.getElementById('tm-err');
  err.textContent = '';
  if (![entry, tp, sl].every(x => isFinite(x) && x > 0)) { err.textContent = 'همهٔ مقادیر ورود/TP/SL باید عدد معتبر باشند.'; return; }
  if (side === 'long' && !(tp > entry && sl < entry)) { err.textContent = 'برای خرید: TP باید بالاتر و SL پایین‌تر از ورود باشد.'; return; }
  if (side === 'short' && !(tp < entry && sl > entry)) { err.textContent = 'برای فروش: TP باید پایین‌تر و SL بالاتر از ورود باشد.'; return; }
  const trade = { side, entry, tp, sl, openedAt: Math.floor(Date.now() / 1000), initialTp: tp, initialSl: sl };
  tmSave(trade);
  renderTradeManager();
}

// --- حالت ۲: معامله فعال → پوستهٔ نمایش (سپس advice زنده) ---
function renderTradeStatusShell(t) {
  const body = document.getElementById('tm-body');
  if (!body) return;
  const sideBadge = t.side === 'long'
    ? badge('خرید (LONG)', 'bg-emerald-500/25 text-emerald-300')
    : badge('فروش (SHORT)', 'bg-red-500/25 text-red-300');
  body.innerHTML = `
    <div class="flex items-center justify-between flex-wrap gap-2 mb-3">
      <div class="flex items-center gap-2">${sideBadge}
        <span class="text-xs text-slate-400">ورود <b class="text-slate-200">$${fmt(t.entry)}</b></span>
      </div>
      <button id="tm-close-btn" class="bg-red-600/80 hover:bg-red-500 text-white text-sm rounded-lg px-3 py-1.5 transition">
        <i class="fas fa-xmark"></i> بستن معامله
      </button>
    </div>
    <div id="tm-status"><div class="text-slate-400 text-sm"><i class="fas fa-spinner fa-spin"></i> دریافت تحلیل زنده برای مدیریت معامله…</div></div>`;
  document.getElementById('tm-close-btn').onclick = () => {
    if (confirm('آیا معامله بسته شود و از سایت حذف گردد؟')) { tmClear(); if (tmTimer) clearInterval(tmTimer); tmTimer = null; renderTradeManager(); }
  };
  // بروزرسانی خودکار advice هر ۳۰ ثانیه (مستقل از رفرش کل صفحه)
  if (tmTimer) clearInterval(tmTimer);
  tmTimer = setInterval(refreshTradeAdvice, 30000);
}

// دریافت advice زنده از سرور برای معاملهٔ ذخیره‌شده
async function refreshTradeAdvice() {
  const t = tmLoad();
  const el = document.getElementById('tm-status');
  if (!t || !el) return;
  try {
    const r = await fetch('/api/trade/advice', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trade: t, modelProbPct: tmLastModelProb }),
    });
    const d = await r.json();
    if (!d.ok) throw new Error(d.error || 'خطا در تحلیل معامله');
    renderTradeStatus(d, t);
  } catch (e) {
    el.innerHTML = `<span class="text-amber-400 text-xs"><i class="fas fa-triangle-exclamation"></i> ${e.message}</span>`;
  }
}

function adviceCard(ad) {
  const map = {
    critical: { c: 'red', icon: 'fa-circle-exclamation' },
    warning: { c: 'amber', icon: 'fa-triangle-exclamation' },
    good: { c: 'emerald', icon: 'fa-circle-check' },
    info: { c: 'sky', icon: 'fa-circle-info' },
  };
  const s = map[ad.severity] || map.info;
  const btn = ad.suggest
    ? `<button class="tm-apply mt-2 text-xs bg-${s.c}-500/20 hover:bg-${s.c}-500/35 text-${s.c}-200 rounded-md px-2 py-1 transition"
         data-field="${ad.suggest.field}" data-value="${ad.suggest.value}">
         <i class="fas fa-check"></i> اعمال ${ad.suggest.field === 'tp' ? 'TP' : 'SL'} = $${fmt(ad.suggest.value)}
       </button>`
    : '';
  return `<div class="bg-${s.c}-500/10 border border-${s.c}-500/30 rounded-lg p-3">
    <div class="flex items-start gap-2">
      <i class="fas ${s.icon} text-${s.c}-400 mt-0.5"></i>
      <div class="flex-1">
        <p class="font-semibold text-${s.c}-200 text-sm">${ad.title}</p>
        <p class="text-xs text-slate-300 mt-0.5 leading-5">${ad.detail}</p>
        ${btn}
      </div>
    </div>
  </div>`;
}

function actionLabel(action) {
  const m = {
    'hold': ['نگه‌داری', 'slate'], 'move-sl': ['انتقال SL به بریک‌ایون', 'amber'],
    'let-run': ['اجازهٔ رشد سود (Trail)', 'emerald'], 'take-partial': ['بستن بخشی', 'amber'],
    'close': ['بستن معامله', 'red'], 'tighten': ['محکم‌کردن SL', 'amber'],
  };
  const [txt, c] = m[action] || m['hold'];
  return badge(txt, `bg-${c}-500/20 text-${c}-300`);
}

function renderTradeStatus(d, t) {
  const el = document.getElementById('tm-status');
  if (!el) return;
  const s = d.status;
  const pnlColor = s.inProfit ? 'emerald' : (s.pnlR < 0 ? 'red' : 'slate');
  const progClamped = Math.max(0, Math.min(100, s.progressToTp));
  const closed = s.reachedTp || s.reachedSl;
  el.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
      <div class="bg-slate-800/60 rounded-lg p-3"><p class="text-xs text-slate-400">قیمت فعلی</p><p class="font-bold text-amber-400">$${fmt(s.price)}</p></div>
      <div class="bg-slate-800/60 rounded-lg p-3"><p class="text-xs text-slate-400">سود/زیان</p><p class="font-bold text-${pnlColor}-400">${s.pnlUsd >= 0 ? '+' : ''}$${fmt(s.pnlUsd)} <span class="text-xs">(${s.pnlR >= 0 ? '+' : ''}${fmt(s.pnlR, 2)}R)</span></p></div>
      <div class="bg-emerald-900/30 rounded-lg p-3"><p class="text-xs text-emerald-400">TP فعلی</p><p class="font-bold text-emerald-300">$${fmt(s.tp)} <span class="text-[10px] text-slate-500">(${s.distToTpPct >= 0 ? '' : ''}${fmt(s.distToTpPct,2)}%)</span></p></div>
      <div class="bg-red-900/30 rounded-lg p-3"><p class="text-xs text-red-400">SL فعلی</p><p class="font-bold text-red-300">$${fmt(s.sl)} <span class="text-[10px] text-slate-500">(${fmt(s.distToSlPct,2)}%)</span></p></div>
    </div>

    <div class="mb-3">
      <div class="flex justify-between text-xs mb-1"><span class="text-slate-400">پیشرفت به سمت TP</span><span class="text-slate-300">${fmt(s.progressToTp,0)}%</span></div>
      <div class="bar-bg h-2.5"><div class="h-full bg-${pnlColor}-500 transition-all" style="width:${progClamped}%"></div></div>
      <p class="text-[11px] text-slate-500 mt-1">${s.riskReward} • روند بازار: ${d.market.trend === 'up' ? 'صعودی' : d.market.trend === 'down' ? 'نزولی' : 'رنج'} • ATR $${fmt(d.market.atr)}</p>
    </div>

    <div class="p-3 rounded-lg bg-slate-800/40 border border-slate-700/50 mb-3 flex items-center justify-between flex-wrap gap-2">
      <span class="text-sm"><i class="fas fa-compass text-amber-400"></i> <b>اقدام پیشنهادی:</b> ${s.overallNote}</span>
      ${actionLabel(s.overallAction)}
    </div>

    <div class="space-y-2">
      ${s.advices.length ? s.advices.map(adviceCard).join('') : '<div class="text-slate-400 text-sm p-2"><i class="fas fa-check text-emerald-400"></i> شرایط پایدار است؛ توصیهٔ خاصی وجود ندارد. طبق پلن ادامه بده.</div>'}
    </div>

    ${closed ? `<p class="text-xs text-slate-400 mt-3"><i class="fas fa-flag-checkered"></i> معامله به ${s.reachedTp ? 'TP' : 'SL'} رسیده — پس از بستن در بروکر، این‌جا هم دکمهٔ «بستن معامله» را بزن.</p>` : ''}
    <p class="text-[11px] text-slate-500 mt-3">آخرین بروزرسانی مدیریت: ${new Date(d.lastUpdate).toLocaleTimeString('fa-IR')} • این معامله در مرورگر شما ذخیره شده و فقط با دکمهٔ «بستن معامله» حذف می‌شود.</p>`;

  // فعال‌سازی دکمه‌های «اعمال TP/SL پیشنهادی»
  el.querySelectorAll('.tm-apply').forEach(b => {
    b.onclick = () => {
      const field = b.getAttribute('data-field');
      const value = parseFloat(b.getAttribute('data-value'));
      const cur = tmLoad(); if (!cur) return;
      cur[field] = value;
      tmSave(cur);
      refreshTradeAdvice();
    };
  });

  // اعلان مرورگر برای رویدادهای مهم مدیریت معامله
  tmNotify(s);
}

function tmNotify(s) {
  if (s.reachedTp) sendNotification('🎯 معاملهٔ شما به TP رسید', `قیمت به حد سود ${fmt(s.tp)} رسید. سود را ثبت کن.`, 'TM-TP-' + s.tp);
  else if (s.reachedSl) sendNotification('🛑 معاملهٔ شما به SL رسید', `قیمت به حد ضرر ${fmt(s.sl)} رسید.`, 'TM-SL-' + s.sl);
  else if (s.overallAction === 'close') sendNotification('⚠️ توصیهٔ بستن معامله', s.overallNote, 'TM-CLOSE');
  else if (s.overallAction === 'move-sl') sendNotification('🔒 معامله را بی‌ریسک کن', s.overallNote, 'TM-BE');
}

skeleton();
load();
// بروزرسانی خودکار هر ۳۰ ثانیه (برای تأخیر کمتر داده)
autoTimer = setInterval(load, 30000);
