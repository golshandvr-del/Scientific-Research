// ============================================================================
// XAUUSD Live Tool — فرانت‌اند
// داشبورد تحلیل زنده طلا بر پایه استراتژی برنده پروژه (S14 VWAP-Regime)
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
        <h1 class="text-2xl font-bold">XAUUSD <span class="text-amber-400">Live</span></h1>
        <p class="text-xs text-slate-400">ابزار تحلیل زنده طلا — مبتنی بر استراتژی تحقیقاتی S14 (VWAP-Regime)</p>
      </div>
    </div>
    <div class="flex items-center gap-2 text-sm">
      <span id="live-dot" class="pulse-dot text-emerald-400"><i class="fas fa-circle text-[8px]"></i></span>
      <span id="last-update" class="text-slate-400">در حال بارگذاری…</span>
      <button id="refresh-btn" class="bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg text-slate-200 transition">
        <i class="fas fa-rotate-right"></i> بروزرسانی
      </button>
    </div>
  </header>
  <div id="content"><div class="card p-8 text-center text-slate-400"><i class="fas fa-spinner fa-spin text-2xl"></i><p class="mt-3">دریافت داده زنده از بازار…</p></div></div>
  <footer class="text-center text-xs text-slate-500 mt-8 pb-6 leading-6">
    <p>منبع داده: Yahoo Finance (GC=F طلای آتی COMEX) — تأخیر حدود ۱۵ دقیقه</p>
    <p class="text-amber-500/80"><i class="fas fa-triangle-exclamation"></i> این ابزار صرفاً برای تحقیق علمی است و توصیه مالی محسوب نمی‌شود. معامله با ریسک همراه است.</p>
  </footer>`;
  document.getElementById('refresh-btn').onclick = load;
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

  const isLong = a.direction === 'LONG';
  const sigColor = isLong ? 'emerald' : 'slate';
  const probColor = a.probability >= 66 ? 'emerald' : (a.probability >= 60 ? 'amber' : 'slate');

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

  <!-- تحلیل چند-تایم‌فریمی + منابع بنیادی -->
  <section id="context-panel" class="grid md:grid-cols-3 gap-4 mb-4">
    <div class="card p-5"><h2 class="text-base font-bold mb-3"><i class="fas fa-layer-group text-indigo-400"></i> هم‌راستایی روند (H1/H4/D1)</h2><div id="mtf-body" class="text-sm text-slate-400"><i class="fas fa-spinner fa-spin"></i> …</div></div>
    <div class="card p-5"><h2 class="text-base font-bold mb-3"><i class="fas fa-globe text-teal-400"></i> بین‌بازاری (DXY / بازده اوراق)</h2><div id="im-body" class="text-sm text-slate-400"><i class="fas fa-spinner fa-spin"></i> …</div></div>
    <div class="card p-5"><h2 class="text-base font-bold mb-3"><i class="fas fa-calendar-days text-rose-400"></i> تقویم اخبار USD</h2><div id="news-body" class="text-sm text-slate-400"><i class="fas fa-spinner fa-spin"></i> …</div></div>
  </section>

  <!-- سیگنال معامله (موتور امتیازدهی شفاف — مکمل) -->
  <section class="card p-5 mb-4 ${isLong ? 'glow-up' : ''}">
    <div class="flex items-center justify-between flex-wrap gap-3 mb-4">
      <h2 class="text-lg font-bold"><i class="fas fa-bullseye text-${sigColor}-400"></i> موتور امتیازدهی شفاف (مکمل)</h2>
      <div class="flex gap-2">${confLabel(a.confidence)}
        ${isLong ? badge('سیگنال: LONG (خرید)', 'bg-emerald-500/20 text-emerald-300') : badge('سیگنال: منتظر بمانید', 'bg-slate-600/40 text-slate-300')}
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

    ${isLong ? `
    <div class="grid grid-cols-3 gap-3 text-center">
      <div class="bg-slate-800/60 rounded-lg p-3">
        <p class="text-xs text-slate-400">ورود</p>
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
      <span class="block text-xs text-slate-500 mt-1">استراتژی S14 فقط در روند صعودی و با احتمال ≥ ${fmt(a.entryThreshold ?? 60, 0)}٪ وارد می‌شود.</span>
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
      ${miniStat('رژیم صعودی', a.regimeOk ? 'بله' : 'خیر', a.regimeOk ? 'emerald' : 'slate')}
      ${miniStat('جهت', isLong ? 'LONG' : 'منتظر', isLong ? 'emerald' : 'slate')}
    </div>
  </section>`;

  drawChart(d);
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
    console.log('[ONNX] signal:', JSON.stringify({dir:sig.direction, prob:sig.probabilityPct, regime:sig.regimeOk, n:j.candles.length}));
    renderOnnx(sig, j.candles.length);
  } catch (e) {
    body.innerHTML = `<span class="text-amber-400"><i class="fas fa-triangle-exclamation"></i> اجرای مدل ONNX ناموفق: ${e.message}</span>`;
  }
}

function renderOnnx(s, nCandles) {
  const body = document.getElementById('onnx-body');
  const sec = document.getElementById('onnx-signal');
  const isLong = s.direction === 'LONG';
  sec.classList.toggle('glow-up', isLong);
  const pColor = s.probability >= 0.75 ? 'emerald' : s.probability >= s.threshold ? 'amber' : 'slate';
  const pct = s.probabilityPct;
  const thrPct = (s.threshold * 100).toFixed(0);
  body.innerHTML = `
    <div class="flex flex-wrap items-center gap-2 mb-3">
      ${isLong
        ? badge('سیگنال مدل: LONG (خرید)', 'bg-emerald-500/25 text-emerald-300')
        : badge('سیگنال مدل: بدون ورود', 'bg-slate-600/40 text-slate-300')}
      ${confLabel(s.confidence)}
      ${badge(s.regimeOk ? 'رژیم صعودی ✓' : 'خارج از رژیم', s.regimeOk ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-600/40 text-slate-300')}
    </div>
    <div class="mb-3">
      <div class="flex justify-between text-sm mb-1">
        <span class="text-slate-400">احتمال مدل (ensemble ۳ مدل) — کلاس «برد»</span>
        <span class="font-bold text-${pColor}-400">${fmt(pct,2)}%</span>
      </div>
      <div class="bar-bg h-3 relative">
        <div class="h-full bg-${pColor}-500 transition-all" style="width:${pct}%"></div>
        <div class="absolute top-0 bottom-0" style="left:${thrPct}%; width:2px; background:#f1f5f9" title="آستانه ${thrPct}%"></div>
      </div>
      <p class="text-[11px] text-slate-500 mt-1">آستانهٔ تصمیم مدل = ${thrPct}٪ (خط سفید). ورود فقط وقتی احتمال ≥ آستانه و رژیم صعودی باشد.</p>
    </div>
    ${isLong ? `
    <div class="grid grid-cols-3 gap-3 text-center">
      <div class="bg-slate-800/60 rounded-lg p-3"><p class="text-xs text-slate-400">ورود</p><p class="font-bold">$${fmt(s.entry)}</p></div>
      <div class="bg-emerald-900/30 rounded-lg p-3"><p class="text-xs text-emerald-400">TP</p><p class="font-bold text-emerald-300">$${fmt(s.tp)}</p></div>
      <div class="bg-red-900/30 rounded-lg p-3"><p class="text-xs text-red-400">SL</p><p class="font-bold text-red-300">$${fmt(s.sl)}</p></div>
    </div>
    <p class="text-xs text-slate-500 mt-2 text-center">${s.rr}</p>
    ` : `
    <div class="bg-slate-800/40 rounded-lg p-3 text-center text-slate-300 text-sm">
      <i class="fas fa-hourglass-half"></i> مدل سیگنال ورود نمی‌دهد ${s.regimeOk ? `(احتمال مدل ${fmt(pct,1)}٪ < آستانهٔ ${thrPct}٪)` : '(بازار خارج از رژیم صعودی)'}.
    </div>`}
    <p class="text-[11px] text-slate-500 mt-3 leading-5">
      <i class="fas fa-circle-check text-cyan-400"></i> این خروجی از اجرای مستقیم فایل‌های <code>xauusd_s14_model_{0,1,2}.onnx</code>
      با <code>onnxruntime-web</code> روی ${nCandles} کندل M15 محاسبه شده و <b>دقیقاً معادل منطق ربات MT5</b> است (parity ~۹۹.۶٪).
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

skeleton();
load();
// بروزرسانی خودکار هر ۶۰ ثانیه
autoTimer = setInterval(load, 60000);
