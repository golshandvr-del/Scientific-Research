//+------------------------------------------------------------------+
//|                                    XAUUSD_ThreeBrain_Robot.mq5    |
//|      Expert Advisor — معماری «روتر سه‌مغزی» (هم‌گام با پروژه/سایت) |
//|                                                                  |
//|  پروژه تحقیقاتی الگویابی ریاضی XAUUSD M15                          |
//|  این ربات دقیقاً همان تصمیم‌گیری سایت تحلیل زنده را بازتولید می‌کند: |
//|                                                                  |
//|   ┌─ رژیم صعودی (close>EMA50>EMA200) → مغز S25 (LONG)             |
//|   ├─ رژیم نزولی (close<EMA50<EMA200) → مغز Bear/S31 (SHORT)       |
//|   └─ رنج (هیچ‌کدام)                   → بدون معامله               |
//|                                                                  |
//|  هر مغز یک ensemble ۳-seed از LightGBM صادرشده به ONNX است که     |
//|  روی ۵۹ feature (۵۷ پایه + early_atr + weekly_rev) کار می‌کند.    |
//|                                                                  |
//|  نتایج بک‌تست OOS (Walk-Forward، ورود open بعدی، اسپرد ۰.۲$):      |
//|    • مغز صعودی S25 : WR=62.3% | exp=+0.54$ | p=0.015 (معنادار)    |
//|    • مغز نزولی Bear: WR=58.4% | PF=1.49  | exp=+1.71$ | p=0.015   |
//+------------------------------------------------------------------+
#property copyright "Scientific-Research XAUUSD Project"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

//====================== ورودی‌های کاربر ============================
input double  InpLotSize        = 0.01;    // حجم ثابت هر معامله (لات)

input group   "مغز صعودی (S25 — LONG)"
input bool    InpEnableBull     = true;    // فعال‌سازی مغز صعودی
input double  InpBullThreshold  = 0.68;    // آستانه احتمال مغز صعودی
input double  InpBullTP_ATR     = 1.0;     // ضریب TP (صعودی)
input double  InpBullSL_ATR     = 1.5;     // ضریب SL (صعودی)

input group   "مغز نزولی (Bear/S31 — SHORT)"
input bool    InpEnableBear     = true;    // فعال‌سازی مغز نزولی
input double  InpBearThreshold  = 0.66;    // آستانه احتمال مغز نزولی
input double  InpBearTP_ATR     = 1.4;     // ضریب TP (نزولی)
input double  InpBearSL_ATR     = 1.7;     // ضریب SL (نزولی)

input group   "مدیریت معامله"
input int     InpMaxHoldBars    = 48;      // حداکثر نگهداری (کندل M15)
input int     InpMaxPositions   = 3;       // حداکثر معاملات همزمان
input double  InpSpreadLimit    = 40;      // حداکثر اسپرد مجاز (point)
input ulong   InpMagic          = 253131;  // شماره جادویی (Magic)
input bool    InpVerbose        = true;    // چاپ لاگ تشخیصی

//====================== ثابت‌ها =====================================
#define NUM_FEATURES 59   // ۵۷ پایه + early_atr + weekly_rev

// مدل مغز صعودی (S25) — ensemble ۳ seed
#define BULL_MODEL_0 "xauusd_s25_model_0.onnx"
#define BULL_MODEL_1 "xauusd_s25_model_1.onnx"
#define BULL_MODEL_2 "xauusd_s25_model_2.onnx"
// مدل مغز نزولی (Bear/S31) — ensemble ۳ seed
#define BEAR_MODEL_0 "xauusd_bear_model_0.onnx"
#define BEAR_MODEL_1 "xauusd_bear_model_1.onnx"
#define BEAR_MODEL_2 "xauusd_bear_model_2.onnx"

//====================== متغیرهای سراسری =============================
CTrade         trade;
CPositionInfo  posinfo;

long   g_bull[3] = {INVALID_HANDLE, INVALID_HANDLE, INVALID_HANDLE};
long   g_bear[3] = {INVALID_HANDLE, INVALID_HANDLE, INVALID_HANDLE};
int    g_num_bull = 0, g_num_bear = 0;

// هندل اندیکاتورها
int    h_ema20, h_ema50, h_ema100, h_ema200;
int    h_atr14, h_adx14;
int    h_rsi7, h_rsi14, h_rsi21;
int    h_stoch, h_bb20, h_macd;
int    h_ema_h1, h_ema_h4, h_ema_d1;   // MTF: ema(close, htf*3) → 12/48/288

datetime g_last_bar_time = 0;

//+------------------------------------------------------------------+
//| بارگذاری یک مدل ONNX از فایل                                      |
//+------------------------------------------------------------------+
long LoadModel(string fname)
{
   long handle = OnnxCreate(fname, ONNX_DEFAULT);
   if(handle == INVALID_HANDLE)
   {
      if(InpVerbose) Print("خطا در بارگذاری مدل ONNX: ", fname, "  err=", GetLastError());
      return INVALID_HANDLE;
   }
   const long input_shape[] = {1, NUM_FEATURES};
   if(!OnnxSetInputShape(handle, 0, input_shape))
   {
      Print("خطا در OnnxSetInputShape برای ", fname, "  err=", GetLastError());
      OnnxRelease(handle);
      return INVALID_HANDLE;
   }
   const long out_shape[] = {1, 2};
   if(!OnnxSetOutputShape(handle, 1, out_shape))
      if(InpVerbose) Print("هشدار: OnnxSetOutputShape(idx=1) ناموفق برای ", fname);
   return handle;
}

//+------------------------------------------------------------------+
//| بارگذاری یک گروه مدل ensemble                                     |
//+------------------------------------------------------------------+
int LoadEnsemble(long &arr[], string f0, string f1, string f2)
{
   string files[3]; files[0]=f0; files[1]=f1; files[2]=f2;
   int cnt = 0;
   for(int i=0; i<3; i++)
   {
      arr[i] = LoadModel(files[i]);
      if(arr[i] != INVALID_HANDLE) cnt++;
   }
   return cnt;
}

//+------------------------------------------------------------------+
//| راه‌اندازی اندیکاتورها                                            |
//+------------------------------------------------------------------+
bool InitIndicators()
{
   string sym = _Symbol;
   ENUM_TIMEFRAMES tf = PERIOD_M15;
   h_ema20  = iMA(sym, tf, 20,  0, MODE_EMA, PRICE_CLOSE);
   h_ema50  = iMA(sym, tf, 50,  0, MODE_EMA, PRICE_CLOSE);
   h_ema100 = iMA(sym, tf, 100, 0, MODE_EMA, PRICE_CLOSE);
   h_ema200 = iMA(sym, tf, 200, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_h1 = iMA(sym, tf, 12,  0, MODE_EMA, PRICE_CLOSE);
   h_ema_h4 = iMA(sym, tf, 48,  0, MODE_EMA, PRICE_CLOSE);
   h_ema_d1 = iMA(sym, tf, 288, 0, MODE_EMA, PRICE_CLOSE);
   h_atr14  = iATR(sym, tf, 14);
   h_adx14  = iADX(sym, tf, 14);
   h_rsi7   = iRSI(sym, tf, 7,  PRICE_CLOSE);
   h_rsi14  = iRSI(sym, tf, 14, PRICE_CLOSE);
   h_rsi21  = iRSI(sym, tf, 21, PRICE_CLOSE);
   h_stoch  = iStochastic(sym, tf, 14, 3, 3, MODE_SMA, STO_LOWHIGH);
   h_bb20   = iBands(sym, tf, 20, 0, 2.0, PRICE_CLOSE);
   h_macd   = iMACD(sym, tf, 12, 26, 9, PRICE_CLOSE);
   if(h_ema50==INVALID_HANDLE || h_ema200==INVALID_HANDLE || h_atr14==INVALID_HANDLE ||
      h_adx14==INVALID_HANDLE || h_rsi14==INVALID_HANDLE || h_stoch==INVALID_HANDLE ||
      h_bb20==INVALID_HANDLE  || h_macd==INVALID_HANDLE)
   {
      Print("خطا در ساخت اندیکاتورها. err=", GetLastError());
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   if(!InitIndicators())
      return INIT_FAILED;

   if(InpEnableBull)
      g_num_bull = LoadEnsemble(g_bull, BULL_MODEL_0, BULL_MODEL_1, BULL_MODEL_2);
   if(InpEnableBear)
      g_num_bear = LoadEnsemble(g_bear, BEAR_MODEL_0, BEAR_MODEL_1, BEAR_MODEL_2);

   if(g_num_bull == 0 && g_num_bear == 0)
   {
      Print("هیچ مدلی بارگذاری نشد. فایل‌های ONNX را در MQL5/Files قرار دهید.");
      return INIT_FAILED;
   }
   PrintFormat("ربات سه‌مغزی آماده شد. مغز صعودی=%d مدل | مغز نزولی=%d مدل",
               g_num_bull, g_num_bear);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   for(int i=0; i<3; i++)
   {
      if(g_bull[i] != INVALID_HANDLE) OnnxRelease(g_bull[i]);
      if(g_bear[i] != INVALID_HANDLE) OnnxRelease(g_bear[i]);
   }
   IndicatorRelease(h_ema20); IndicatorRelease(h_ema50);
   IndicatorRelease(h_ema100); IndicatorRelease(h_ema200);
   IndicatorRelease(h_ema_h1); IndicatorRelease(h_ema_h4); IndicatorRelease(h_ema_d1);
   IndicatorRelease(h_atr14); IndicatorRelease(h_adx14);
   IndicatorRelease(h_rsi7); IndicatorRelease(h_rsi14); IndicatorRelease(h_rsi21);
   IndicatorRelease(h_stoch); IndicatorRelease(h_bb20); IndicatorRelease(h_macd);
}

//====================== کمک‌توابع محاسباتی =========================
double IndVal(int handle, int buffer, int shift)
{
   double buf[];
   if(CopyBuffer(handle, buffer, shift, 1, buf) < 1) return EMPTY_VALUE;
   return buf[0];
}

double RollingSlope(const double &price[], int end_idx, int period)
{
   if(end_idx - period + 1 < 0) return 0.0;
   double x_mean = (period - 1) / 2.0, denom = 0.0;
   for(int k=0; k<period; k++) denom += (k - x_mean) * (k - x_mean);
   if(denom == 0.0) return 0.0;
   double y_mean = 0.0;
   for(int k=0; k<period; k++) y_mean += price[end_idx - period + 1 + k];
   y_mean /= period;
   double num = 0.0;
   for(int k=0; k<period; k++)
      num += (k - x_mean) * (price[end_idx - period + 1 + k] - y_mean);
   return num / denom;
}

double ZScore(const double &arr[], int end_idx, int period)
{
   if(end_idx - period + 1 < 0) return 0.0;
   double m = 0.0;
   for(int k=0; k<period; k++) m += arr[end_idx - period + 1 + k];
   m /= period;
   double s = 0.0;
   for(int k=0; k<period; k++){ double d = arr[end_idx - period + 1 + k] - m; s += d*d; }
   s = MathSqrt(s / (period - 1));
   if(s == 0.0) return 0.0;
   return (arr[end_idx] - m) / s;
}

double RollingMean(const double &arr[], int end_idx, int period)
{
   if(end_idx - period + 1 < 0) return 0.0;
   double m = 0.0;
   for(int k=0; k<period; k++) m += arr[end_idx - period + 1 + k];
   return m / period;
}

//+------------------------------------------------------------------+
//| ساخت ۵۹ feature برای کندل سیگنال (sig_shift)                     |
//| ترتیب دقیقاً مطابق mt5_robot/feature_order_s25.txt              |
//| (۵۷ feature پایهٔ S14 + early_atr + weekly_rev)                  |
//+------------------------------------------------------------------+
bool BuildFeatures(int sig_shift, float &feat[])
{
   int NEED = 700;   // برای early_atr هفتگی + ema288 کافی
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(_Symbol, PERIOD_M15, sig_shift, NEED, rates);
   if(copied < 400)
   {
      if(InpVerbose) Print("داده کافی برای feature نیست: ", copied);
      return false;
   }
   int cur = copied - 1;

   double closeA[], highA[], lowA[], openA[], volA[], tpA[];
   ArrayResize(closeA, copied); ArrayResize(highA, copied);
   ArrayResize(lowA, copied);   ArrayResize(openA, copied);
   ArrayResize(volA, copied);   ArrayResize(tpA, copied);
   for(int i=0; i<copied; i++)
   {
      closeA[i]=rates[i].close; highA[i]=rates[i].high; lowA[i]=rates[i].low;
      openA[i]=rates[i].open;   volA[i]=(double)rates[i].tick_volume;
      tpA[i]=(rates[i].high+rates[i].low+rates[i].close)/3.0;
   }
   double c=closeA[cur], h=highA[cur], l=lowA[cur], o=openA[cur];

   double ema20=IndVal(h_ema20,0,sig_shift), ema50=IndVal(h_ema50,0,sig_shift);
   double ema100=IndVal(h_ema100,0,sig_shift), ema200=IndVal(h_ema200,0,sig_shift);
   double emaH1=IndVal(h_ema_h1,0,sig_shift), emaH4=IndVal(h_ema_h4,0,sig_shift);
   double emaD1=IndVal(h_ema_d1,0,sig_shift);
   double atr14=IndVal(h_atr14,0,sig_shift);
   double rsi7=IndVal(h_rsi7,0,sig_shift), rsi14=IndVal(h_rsi14,0,sig_shift);
   double rsi21=IndVal(h_rsi21,0,sig_shift);
   double adx=IndVal(h_adx14,0,sig_shift), pdi=IndVal(h_adx14,1,sig_shift), mdi=IndVal(h_adx14,2,sig_shift);
   double macd_main=IndVal(h_macd,0,sig_shift), macd_sig=IndVal(h_macd,1,sig_shift);
   double stoch_k=IndVal(h_stoch,0,sig_shift), stoch_d=IndVal(h_stoch,1,sig_shift);
   double bb_up=IndVal(h_bb20,1,sig_shift), bb_lo=IndVal(h_bb20,2,sig_shift);
   if(atr14==EMPTY_VALUE || ema200==EMPTY_VALUE || bb_up==EMPTY_VALUE) return false;
   double macd_hist = macd_main - macd_sig;

   // ---- VWAP لنگرشدهٔ روزانه ----
   MqlDateTime dt_cur; TimeToStruct(rates[cur].time, dt_cur);
   double cum_pv=0.0, cum_v=0.0;
   for(int i=cur; i>=0; i--)
   {
      MqlDateTime dti; TimeToStruct(rates[i].time, dti);
      if(dti.day!=dt_cur.day || dti.mon!=dt_cur.mon || dti.year!=dt_cur.year) break;
      cum_pv += tpA[i]*volA[i]; cum_v += volA[i];
   }
   double vwap = (cum_v>0.0)? cum_pv/cum_v : c;

   // ---- open روزانه ----
   double daily_open=o;
   for(int i=cur; i>=0; i--)
   {
      MqlDateTime dti; TimeToStruct(rates[i].time, dti);
      if(dti.day!=dt_cur.day || dti.mon!=dt_cur.mon || dti.year!=dt_cur.year) break;
      daily_open = openA[i];
   }

   // ---- streak ----
   double streak=0.0;
   {
      double prev_sign=0.0; int count=0;
      for(int i=cur; i>0; i--)
      {
         double diff=closeA[i]-closeA[i-1];
         double sgn=(diff>0)?1.0:((diff<0)?-1.0:0.0);
         if(i==cur){ prev_sign=sgn; count=1; }
         else { if(sgn==prev_sign && sgn!=0.0) count++; else break; }
      }
      streak = count*prev_sign;
   }

   double rng=(h-l); if(rng==0.0) rng=1e-9;

   double atr_ma=0.0;
   {
      double atrbuf[];
      if(CopyBuffer(h_atr14,0,sig_shift,50,atrbuf)==50)
      { double sm=0; for(int i=0;i<50;i++) sm+=atrbuf[i]; atr_ma=sm/50.0; }
   }
   double atr_ratio=(atr_ma>0.0)? atr14/atr_ma : 1.0;

   // ================= ۵۷ feature پایه =================
   int p=0;
   feat[p++]=(float)((c/closeA[cur-1])-1.0);
   feat[p++]=(float)((c/closeA[cur-2])-1.0);
   feat[p++]=(float)((c/closeA[cur-3])-1.0);
   feat[p++]=(float)((c/closeA[cur-5])-1.0);
   feat[p++]=(float)((c/closeA[cur-8])-1.0);
   feat[p++]=(float)((c/closeA[cur-13])-1.0);
   feat[p++]=(float)((c/closeA[cur-21])-1.0);
   feat[p++]=(float)rsi7; feat[p++]=(float)rsi14; feat[p++]=(float)rsi21;
   feat[p++]=(float)macd_main; feat[p++]=(float)macd_sig; feat[p++]=(float)macd_hist;
   feat[p++]=(float)atr14; feat[p++]=(float)(atr14/c); feat[p++]=(float)atr_ratio;
   feat[p++]=(float)((h-l)/c); feat[p++]=(float)(MathAbs(c-o)/c);
   feat[p++]=(float)adx; feat[p++]=(float)(pdi-mdi);
   double bb_w=(bb_up-bb_lo); if(bb_w==0.0) bb_w=1e-9;
   feat[p++]=(float)((c-bb_lo)/bb_w); feat[p++]=(float)(bb_w/c);
   feat[p++]=(float)stoch_k; feat[p++]=(float)stoch_d;
   feat[p++]=(float)((c-ema20)/ema20);
   feat[p++]=(float)((c-ema50)/ema50);
   feat[p++]=(float)((c-ema100)/ema100);
   feat[p++]=(float)(RollingSlope(closeA,cur,20)/c);
   feat[p++]=(float)(RollingSlope(closeA,cur,50)/c);
   feat[p++]=(float)ZScore(closeA,cur,20);
   feat[p++]=(float)ZScore(closeA,cur,50);
   double vol_ma20=RollingMean(volA,cur,20);
   feat[p++]=(float)((vol_ma20>0.0)? volA[cur]/vol_ma20 : 1.0);
   feat[p++]=(float)((h-MathMax(o,c))/rng);
   feat[p++]=(float)((MathMin(o,c)-l)/rng);
   feat[p++]=(float)streak;
   int hour=dt_cur.hour, dow=dt_cur.day_of_week;
   int pandas_dow=(dow==0)?6:(dow-1);
   feat[p++]=(float)MathSin(2.0*M_PI*hour/24.0);
   feat[p++]=(float)MathCos(2.0*M_PI*hour/24.0);
   feat[p++]=(float)pandas_dow; feat[p++]=(float)hour;
   feat[p++]=(float)((c-daily_open)/daily_open);
   feat[p++]=(float)((c-emaH1)/emaH1);
   feat[p++]=(float)(RollingSlope(closeA,cur,4)/c);
   feat[p++]=(float)((c/closeA[cur-4])-1.0);
   feat[p++]=(float)((c-emaH4)/emaH4);
   feat[p++]=(float)(RollingSlope(closeA,cur,16)/c);
   feat[p++]=(float)((c/closeA[cur-16])-1.0);
   feat[p++]=(float)((c-emaD1)/emaD1);
   feat[p++]=(float)(RollingSlope(closeA,cur,96)/c);
   feat[p++]=(float)((c/closeA[cur-96])-1.0);
   feat[p++]=(float)((c>ema200)?1.0:0.0);
   feat[p++]=(float)((c-ema200)/ema200);
   feat[p++]=(float)((c-vwap)/c);
   feat[p++]=(float)((c-vwap)/atr14);
   feat[p++]=(float)((c>vwap)?1.0:0.0);
   feat[p++]=(float)((c-ema50)/atr14);
   feat[p++]=(float)ZScore(volA,cur,20);
   feat[p++]=(float)((c-l)/rng);

   // ================= ۲ feature زمانی هفتگی =================
   // early_atr  = (close چهارشنبه − open دوشنبه) / میانگین ATR روزانه
   // weekly_rev = -sign(early) * clip(|early_atr|,0,3) * day_weight
   //   day_weight: Mon .2 Tue .3 Wed .5 Thu 1.0 Fri .9  (Sat/Sun صفر)
   double early_atr=0.0, weekly_rev=0.0;
   {
      // early_move: از open اولین کندلِ دوشنبه تا close آخرین کندلِ چهارشنبه
      // در همان هفتهٔ تقویمی کندل سیگنال.
      // pandas_dow: Mon=0 Tue=1 Wed=2 Thu=3 Fri=4
      double mon_open = EMPTY_VALUE, wed_close = EMPTY_VALUE;
      int    wed_seen_idx = -1;
      // پیدا کردن مرز شروع هفته: به عقب می‌رویم تا اولین دوشنبه‌ای که
      // pandas_dow==0 و کندل قبلی‌اش dow>0 (یا جهش روز) باشد.
      // ساده‌سازی مطمئن: از cur به عقب، تا وقتی به یک دوشنبه برسیم و open آن را بگیریم؛
      // در همین مسیر آخرین close چهارشنبه را نگه می‌داریم.
      int limit = MathMax(0, cur-600);
      // ابتدا close آخرین چهارشنبهٔ ≤ cur را بیاب
      for(int i=cur; i>=limit; i--)
      {
         MqlDateTime d; TimeToStruct(rates[i].time, d);
         int pdow=(d.day_of_week==0)?6:(d.day_of_week-1);
         if(pdow==2){ wed_close = closeA[i]; wed_seen_idx=i; break; }
         if(pdow>2) continue;         // Thu/Fri بعد از Wed → ادامه به عقب
      }
      // open اولین دوشنبهٔ همان هفته (قبل از آن چهارشنبه)
      if(wed_seen_idx>=0)
      {
         for(int i=wed_seen_idx; i>=limit; i--)
         {
            MqlDateTime d; TimeToStruct(rates[i].time, d);
            int pdow=(d.day_of_week==0)?6:(d.day_of_week-1);
            if(pdow==0) mon_open = openA[i];      // آخرین‌بار که Mon دیده شد = اولین کندل دوشنبه (چون به عقب می‌رویم)
            if(pdow>2) break;                     // به هفتهٔ قبل رسیدیم
         }
      }
      double atr_daily = RollingMean_ATR(sig_shift); // میانگین ۹۶ کندل ATR
      if(mon_open!=EMPTY_VALUE && wed_close!=EMPTY_VALUE && atr_daily>0.0)
      {
         double early = wed_close - mon_open;
         early_atr = early / (atr_daily + 1e-9);
         double aw = 0.0;
         switch(pandas_dow){
            case 0: aw=0.2; break; case 1: aw=0.3; break; case 2: aw=0.5; break;
            case 3: aw=1.0; break; case 4: aw=0.9; break; default: aw=0.0; }
         double clipped = MathMin(MathAbs(early_atr), 3.0);
         double sgn = (early>0)?1.0:((early<0)?-1.0:0.0);
         weekly_rev = -sgn * clipped * aw;
      }
   }
   feat[p++]=(float)early_atr;   // index 57
   feat[p++]=(float)weekly_rev;  // index 58

   if(p != NUM_FEATURES)
   {
      Print("خطای تعداد feature: ", p, " != ", NUM_FEATURES);
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| میانگین ۹۶ کندل ATR (atr_daily برای نرمال‌سازی early_atr)         |
//+------------------------------------------------------------------+
double RollingMean_ATR(int sig_shift)
{
   double atrbuf[];
   if(CopyBuffer(h_atr14, 0, sig_shift, 96, atrbuf) == 96)
   {
      double sm=0; for(int i=0;i<96;i++) sm+=atrbuf[i];
      return sm/96.0;
   }
   return 0.0;
}

//+------------------------------------------------------------------+
//| اجرای یک مدل ONNX → احتمال کلاس ۱                                |
//+------------------------------------------------------------------+
double RunModel(long handle, const float &feat[])
{
   float in_data[];
   ArrayResize(in_data, NUM_FEATURES);
   for(int i=0; i<NUM_FEATURES; i++) in_data[i] = feat[i];
   long out_label[]; float out_proba[];
   ArrayResize(out_label,1); ArrayResize(out_proba,2);
   if(!OnnxRun(handle, ONNX_NO_CONVERSION, in_data, out_label, out_proba))
      if(!OnnxRun(handle, ONNX_DEFAULT, in_data, out_label, out_proba))
      {
         if(InpVerbose) Print("OnnxRun ناموفق. err=", GetLastError());
         return -1.0;
      }
   return (double)out_proba[1];
}

double EnsembleProba(long &arr[], const float &feat[])
{
   double sum=0.0; int cnt=0;
   for(int i=0; i<3; i++)
   {
      if(arr[i]==INVALID_HANDLE) continue;
      double pr=RunModel(arr[i], feat);
      if(pr>=0.0){ sum+=pr; cnt++; }
   }
   if(cnt==0) return -1.0;
   return sum/cnt;
}

//+------------------------------------------------------------------+
int CountMyPositions()
{
   int cnt=0;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong t=PositionGetTicket(i);
      if(t==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)==(long)InpMagic &&
         PositionGetString(POSITION_SYMBOL)==_Symbol) cnt++;
   }
   return cnt;
}

void ManageTimeExit()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong t=PositionGetTicket(i);
      if(t==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=(long)InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      datetime open_time=(datetime)PositionGetInteger(POSITION_TIME);
      int bars_held=iBarShift(_Symbol, PERIOD_M15, open_time);
      if(bars_held >= InpMaxHoldBars)
      {
         trade.PositionClose(t);
         if(InpVerbose) PrintFormat("خروج زمانی: تیکت %I64u پس از %d کندل", t, bars_held);
      }
   }
}

//+------------------------------------------------------------------+
void OpenTrade(bool is_long, double atr14, double tp_atr, double sl_atr, string tag)
{
   int digits=(int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(is_long)
   {
      double ask=SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double tp=NormalizeDouble(ask+tp_atr*atr14, digits);
      double sl=NormalizeDouble(ask-sl_atr*atr14, digits);
      if(trade.Buy(InpLotSize,_Symbol,ask,sl,tp,tag))
      { if(InpVerbose) PrintFormat("ورود LONG @ %.2f SL=%.2f TP=%.2f", ask,sl,tp); }
      else if(InpVerbose) Print("خطا در Buy: ", trade.ResultRetcodeDescription());
   }
   else
   {
      double bid=SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double tp=NormalizeDouble(bid-tp_atr*atr14, digits);
      double sl=NormalizeDouble(bid+sl_atr*atr14, digits);
      if(trade.Sell(InpLotSize,_Symbol,bid,sl,tp,tag))
      { if(InpVerbose) PrintFormat("ورود SHORT @ %.2f SL=%.2f TP=%.2f", bid,sl,tp); }
      else if(InpVerbose) Print("خطا در Sell: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| OnTick — روتر سه‌مغزی (فقط روی کندل جدید)                         |
//+------------------------------------------------------------------+
void OnTick()
{
   ManageTimeExit();

   datetime cur_bar = iTime(_Symbol, PERIOD_M15, 0);
   if(cur_bar == g_last_bar_time) return;
   g_last_bar_time = cur_bar;

   double spread=(double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpSpreadLimit)
   { if(InpVerbose) Print("اسپرد بالا، رد سیگنال: ", spread); return; }

   if(CountMyPositions() >= InpMaxPositions) return;

   int sig_shift=1;
   double c=iClose(_Symbol, PERIOD_M15, sig_shift);
   double ema50=IndVal(h_ema50,0,sig_shift);
   double ema200=IndVal(h_ema200,0,sig_shift);
   double atr14=IndVal(h_atr14,0,sig_shift);
   if(ema50==EMPTY_VALUE || ema200==EMPTY_VALUE || atr14==EMPTY_VALUE) return;

   // ---- تشخیص رژیم (روتر) ----
   bool uptrend   = (c > ema50 && ema50 > ema200);
   bool downtrend = (c < ema50 && ema50 < ema200);
   if(!uptrend && !downtrend) return;   // رنج → بدون معامله

   float feat[]; ArrayResize(feat, NUM_FEATURES);
   if(!BuildFeatures(sig_shift, feat)) return;

   // ---- مغز صعودی ----
   if(uptrend && InpEnableBull && g_num_bull>0)
   {
      double proba = EnsembleProba(g_bull, feat);
      if(proba<0.0) return;
      if(InpVerbose) PrintFormat("[BULL] proba=%.4f THR=%.2f %s", proba, InpBullThreshold,
                                 (proba>=InpBullThreshold)?"→ LONG":"");
      if(proba >= InpBullThreshold)
         OpenTrade(true, atr14, InpBullTP_ATR, InpBullSL_ATR, "S25-Bull");
      return;
   }

   // ---- مغز نزولی ----
   if(downtrend && InpEnableBear && g_num_bear>0)
   {
      double proba = EnsembleProba(g_bear, feat);
      if(proba<0.0) return;
      if(InpVerbose) PrintFormat("[BEAR] proba=%.4f THR=%.2f %s", proba, InpBearThreshold,
                                 (proba>=InpBearThreshold)?"→ SHORT":"");
      if(proba >= InpBearThreshold)
         OpenTrade(false, atr14, InpBearTP_ATR, InpBearSL_ATR, "Bear-S31");
      return;
   }
}
//+------------------------------------------------------------------+
