//+------------------------------------------------------------------+
//|                                          XAUUSD_S14_Robot.mq5     |
//|         Expert Advisor مبتنی بر استراتژی ۱۴ (VWAP-Regime ML)      |
//|                                                                  |
//|  پروژه تحقیقاتی الگویابی ریاضی XAUUSD M15                          |
//|  استراتژی: LONG-only، فیلتر ML (LightGBM ensemble → ONNX)          |
//|  نتایج بک‌تست OOS: WR=61.58% | exp=+0.35$/trade | 5.28 trade/day   |
//|                                                                  |
//|  منطق:                                                            |
//|   1. کاندید پایه: close > EMA50 > EMA200 (روند صعودی)             |
//|   2. ساخت ۵۷ feature دقیقاً مطابق engine/features.py             |
//|   3. اجرای مدل ONNX (میانگین ۳ seed) → احتمال موفقیت              |
//|   4. اگر proba >= 0.68 → ورود LONG                               |
//|   5. TP = 1.0*ATR14 ، SL = 1.5*ATR14 ، حداکثر نگهداری ۴۸ کندل    |
//+------------------------------------------------------------------+
#property copyright "Scientific-Research XAUUSD Project"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

//====================== ورودی‌های کاربر ============================
input double  InpLotSize        = 0.01;    // حجم ثابت هر معامله (لات)
input double  InpThreshold      = 0.68;    // آستانه احتمال مدل (THR)
input double  InpTP_ATR         = 1.0;     // ضریب TP بر حسب ATR
input double  InpSL_ATR         = 1.5;     // ضریب SL بر حسب ATR
input int     InpMaxHoldBars    = 48;      // حداکثر نگهداری (کندل M15)
input int     InpMaxPositions   = 3;       // حداکثر معاملات همزمان
input double  InpSpreadLimit    = 40;      // حداکثر اسپرد مجاز (point)
input ulong   InpMagic          = 141414;  // شماره جادویی (Magic)
input bool    InpUseEnsemble    = true;    // استفاده از میانگین ۳ مدل (ensemble)
input bool    InpVerbose        = true;    // چاپ لاگ تشخیصی

//====================== ثابت‌ها =====================================
#define NUM_FEATURES 57

// نام فایل‌های مدل ONNX (باید در MQL5/Files قرار گیرند)
#define MODEL_FILE_0 "xauusd_s14_model_0.onnx"
#define MODEL_FILE_1 "xauusd_s14_model_1.onnx"
#define MODEL_FILE_2 "xauusd_s14_model_2.onnx"

//====================== متغیرهای سراسری =============================
CTrade         trade;
CPositionInfo  posinfo;

long   g_model[3] = {INVALID_HANDLE, INVALID_HANDLE, INVALID_HANDLE};
int    g_num_models = 0;

// هندل اندیکاتورها
int    h_ema20, h_ema50, h_ema100, h_ema200;
int    h_ema12, h_ema26;      // برای MACD
int    h_atr14;
int    h_adx14;
int    h_rsi7, h_rsi14, h_rsi21;
int    h_stoch;
int    h_bb20;
int    h_macd;

datetime g_last_bar_time = 0;

// EMAهای چند-تایم‌فریمی (روی همین M15 با دوره‌های بزرگ‌تر، مطابق features.py)
// features.py: ema_htf = ema(close, htf*3)  → h1:12, h4:48, d1:288
int    h_ema_h1, h_ema_h4, h_ema_d1;

//+------------------------------------------------------------------+
//| بارگذاری یک مدل ONNX از فایل                                      |
//+------------------------------------------------------------------+
long LoadModel(string fname)
{
   long handle = OnnxCreate(fname, ONNX_DEFAULT);
   if(handle == INVALID_HANDLE)
   {
      Print("خطا در بارگذاری مدل ONNX: ", fname, "  err=", GetLastError());
      return INVALID_HANDLE;
   }
   // تعیین شکل ورودی: [1, 57]
   const long input_shape[] = {1, NUM_FEATURES};
   if(!OnnxSetInputShape(handle, 0, input_shape))
   {
      Print("خطا در OnnxSetInputShape برای ", fname, "  err=", GetLastError());
      OnnxRelease(handle);
      return INVALID_HANDLE;
   }
   // خروجی مدل LightGBM→ONNX: دو خروجی (label و probabilities)
   // شکل احتمال: [1, 2]
   const long out_shape[] = {1, 2};
   if(!OnnxSetOutputShape(handle, 1, out_shape))
   {
      // ممکن است opset متفاوت باشد؛ هشدار غیرمهلک
      if(InpVerbose) Print("هشدار: OnnxSetOutputShape(idx=1) ناموفق برای ", fname);
   }
   return handle;
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
   h_ema_h1 = iMA(sym, tf, 12,  0, MODE_EMA, PRICE_CLOSE);   // h1: htf*3=12
   h_ema_h4 = iMA(sym, tf, 48,  0, MODE_EMA, PRICE_CLOSE);   // h4: htf*3=48
   h_ema_d1 = iMA(sym, tf, 288, 0, MODE_EMA, PRICE_CLOSE);   // d1: htf*3=288
   h_atr14  = iATR(sym, tf, 14);
   h_adx14  = iADX(sym, tf, 14);
   h_rsi7   = iRSI(sym, tf, 7,  PRICE_CLOSE);
   h_rsi14  = iRSI(sym, tf, 14, PRICE_CLOSE);
   h_rsi21  = iRSI(sym, tf, 21, PRICE_CLOSE);
   h_stoch  = iStochastic(sym, tf, 14, 3, 3, MODE_SMA, STO_LOWHIGH);
   h_bb20   = iBands(sym, tf, 20, 0, 2.0, PRICE_CLOSE);
   h_macd   = iMACD(sym, tf, 12, 26, 9, PRICE_CLOSE);

   if(h_ema20==INVALID_HANDLE || h_ema50==INVALID_HANDLE || h_ema200==INVALID_HANDLE ||
      h_atr14==INVALID_HANDLE || h_adx14==INVALID_HANDLE || h_rsi14==INVALID_HANDLE ||
      h_stoch==INVALID_HANDLE || h_bb20==INVALID_HANDLE || h_macd==INVALID_HANDLE)
   {
      Print("خطا در ساخت اندیکاتورها. err=", GetLastError());
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);

   if(!InitIndicators())
      return INIT_FAILED;

   // بارگذاری مدل‌ها
   g_num_models = 0;
   if(InpUseEnsemble)
   {
      string files[3] = {MODEL_FILE_0, MODEL_FILE_1, MODEL_FILE_2};
      for(int i=0; i<3; i++)
      {
         g_model[i] = LoadModel(files[i]);
         if(g_model[i] != INVALID_HANDLE) g_num_models++;
      }
   }
   if(g_num_models == 0)
   {
      // fallback: مدل تکی
      g_model[0] = LoadModel("xauusd_s14_model.onnx");
      if(g_model[0] != INVALID_HANDLE) g_num_models = 1;
   }
   if(g_num_models == 0)
   {
      Print("هیچ مدلی بارگذاری نشد. فایل ONNX را در پوشه MQL5/Files قرار دهید.");
      return INIT_FAILED;
   }
   PrintFormat("ربات XAUUSD-S14 آماده شد. تعداد مدل بارگذاری‌شده: %d | THR=%.2f",
               g_num_models, InpThreshold);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   for(int i=0; i<3; i++)
      if(g_model[i] != INVALID_HANDLE) OnnxRelease(g_model[i]);
   IndicatorRelease(h_ema20); IndicatorRelease(h_ema50);
   IndicatorRelease(h_ema100); IndicatorRelease(h_ema200);
   IndicatorRelease(h_ema_h1); IndicatorRelease(h_ema_h4); IndicatorRelease(h_ema_d1);
   IndicatorRelease(h_atr14); IndicatorRelease(h_adx14);
   IndicatorRelease(h_rsi7); IndicatorRelease(h_rsi14); IndicatorRelease(h_rsi21);
   IndicatorRelease(h_stoch); IndicatorRelease(h_bb20); IndicatorRelease(h_macd);
}

//+------------------------------------------------------------------+
//| کمک‌تابع: خواندن یک بافر اندیکاتور در اندیس معین                  |
//| shift=1 یعنی آخرین کندل بسته‌شده (کندل جاری در حال شکل‌گیری=0)     |
//+------------------------------------------------------------------+
double IndVal(int handle, int buffer, int shift)
{
   double buf[];
   if(CopyBuffer(handle, buffer, shift, 1, buf) < 1)
      return EMPTY_VALUE;
   return buf[0];
}

//+------------------------------------------------------------------+
//| شیب رگرسیون خطی روی پنجره متحرک (مطابق rolling_slope در پایتون)   |
//| price[] با اندیس ۰=قدیمی‌ترین ... n-1=جدیدترین                    |
//+------------------------------------------------------------------+
double RollingSlope(const double &price[], int end_idx, int period)
{
   if(end_idx - period + 1 < 0) return 0.0;
   double x_mean = (period - 1) / 2.0;
   double denom = 0.0;
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

//+------------------------------------------------------------------+
//| z-score روی پنجره (mean/std نمونه‌ای مطابق pandas .std())         |
//+------------------------------------------------------------------+
double ZScore(const double &arr[], int end_idx, int period)
{
   if(end_idx - period + 1 < 0) return 0.0;
   double m = 0.0;
   for(int k=0; k<period; k++) m += arr[end_idx - period + 1 + k];
   m /= period;
   double s = 0.0;
   for(int k=0; k<period; k++)
   {
      double d = arr[end_idx - period + 1 + k] - m;
      s += d * d;
   }
   s = MathSqrt(s / (period - 1)); // ddof=1 مطابق pandas
   if(s == 0.0) return 0.0;
   return (arr[end_idx] - m) / s;
}

//+------------------------------------------------------------------+
//| میانگین متحرک ساده روی آرایه                                     |
//+------------------------------------------------------------------+
double RollingMean(const double &arr[], int end_idx, int period)
{
   if(end_idx - period + 1 < 0) return 0.0;
   double m = 0.0;
   for(int k=0; k<period; k++) m += arr[end_idx - period + 1 + k];
   return m / period;
}

//+------------------------------------------------------------------+
//| ساخت ۵۷ feature برای کندل بسته‌شدهٔ j" (shift از کندل جاری)       |
//| ترتیب دقیقاً مطابق mt5_robot/feature_order.txt و features.py     |
//| خروجی در feat[] (طول NUM_FEATURES). true اگر موفق.               |
//+------------------------------------------------------------------+
bool BuildFeatures(int sig_shift, float &feat[])
{
   // برای محاسبهٔ VWAP لنگرشده و شیب/zscore به تاریخچهٔ کافی نیاز داریم.
   // NEED کندل تاریخی می‌گیریم (اندیس صعودی زمانی می‌سازیم).
   int NEED = 400;  // برای ema288 و vwap روزانه کافی است
   MqlRates rates[];
   ArraySetAsSeries(rates, false); // اندیس ۰=قدیمی‌ترین
   int copied = CopyRates(_Symbol, PERIOD_M15, sig_shift, NEED, rates);
   if(copied < NEED)
   {
      if(InpVerbose) Print("داده کافی برای feature نیست: ", copied);
      return false;
   }
   int cur = copied - 1;  // اندیس کندل سیگنال (جدیدترین در این آرایه)

   // سری‌های قیمت با اندیس صعودی
   double closeA[], highA[], lowA[], openA[], volA[], tpA[];
   ArrayResize(closeA, copied); ArrayResize(highA, copied);
   ArrayResize(lowA, copied);   ArrayResize(openA, copied);
   ArrayResize(volA, copied);   ArrayResize(tpA, copied);
   for(int i=0; i<copied; i++)
   {
      closeA[i] = rates[i].close;
      highA[i]  = rates[i].high;
      lowA[i]   = rates[i].low;
      openA[i]  = rates[i].open;
      volA[i]   = (double)rates[i].tick_volume;
      tpA[i]    = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
   }

   double c  = closeA[cur];
   double h  = highA[cur];
   double l  = lowA[cur];
   double o  = openA[cur];

   // مقادیر اندیکاتورهای MT5 (shift=sig_shift یعنی همان کندل سیگنال)
   double ema20  = IndVal(h_ema20, 0, sig_shift);
   double ema50  = IndVal(h_ema50, 0, sig_shift);
   double ema100 = IndVal(h_ema100,0, sig_shift);
   double ema200 = IndVal(h_ema200,0, sig_shift);
   double emaH1  = IndVal(h_ema_h1,0, sig_shift);
   double emaH4  = IndVal(h_ema_h4,0, sig_shift);
   double emaD1  = IndVal(h_ema_d1,0, sig_shift);
   double atr14  = IndVal(h_atr14, 0, sig_shift);
   double rsi7   = IndVal(h_rsi7,  0, sig_shift);
   double rsi14  = IndVal(h_rsi14, 0, sig_shift);
   double rsi21  = IndVal(h_rsi21, 0, sig_shift);
   double adx    = IndVal(h_adx14, 0, sig_shift);
   double pdi    = IndVal(h_adx14, 1, sig_shift);
   double mdi    = IndVal(h_adx14, 2, sig_shift);
   double macd_main = IndVal(h_macd, 0, sig_shift);
   double macd_sig  = IndVal(h_macd, 1, sig_shift);
   double stoch_k   = IndVal(h_stoch, 0, sig_shift);
   double stoch_d   = IndVal(h_stoch, 1, sig_shift);
   double bb_up  = IndVal(h_bb20, 1, sig_shift); // UPPER_BAND
   double bb_lo  = IndVal(h_bb20, 2, sig_shift); // LOWER_BAND

   if(atr14==EMPTY_VALUE || ema200==EMPTY_VALUE || bb_up==EMPTY_VALUE)
      return false;

   // MACD hist مطابق features.py = macd_main - signal (خود MT5 signal را می‌دهد)
   double macd_hist = macd_main - macd_sig;

   // ---- VWAP لنگرشدهٔ روزانه (از ابتدای همان روز تا کندل سیگنال) ----
   MqlDateTime dt_cur; TimeToStruct(rates[cur].time, dt_cur);
   double cum_pv = 0.0, cum_v = 0.0;
   for(int i=cur; i>=0; i--)
   {
      MqlDateTime dti; TimeToStruct(rates[i].time, dti);
      if(dti.day != dt_cur.day || dti.mon != dt_cur.mon || dti.year != dt_cur.year)
         break;
      cum_pv += tpA[i] * volA[i];
      cum_v  += volA[i];
   }
   double vwap = (cum_v > 0.0) ? cum_pv / cum_v : c;

   // ---- open روزانه (اولین کندل همان روز) ----
   double daily_open = o;
   for(int i=cur; i>=0; i--)
   {
      MqlDateTime dti; TimeToStruct(rates[i].time, dti);
      if(dti.day != dt_cur.day || dti.mon != dt_cur.mon || dti.year != dt_cur.year)
         break;
      daily_open = openA[i];
   }

   // ---- streak: تعداد کندل هم‌جهت اخیر (علامت‌دار) مطابق features.py ----
   double streak = 0.0;
   {
      double prev_sign = 0.0;
      int count = 0;
      for(int i=cur; i>0; i--)
      {
         double diff = closeA[i] - closeA[i-1];
         double sgn = (diff>0)?1.0:((diff<0)?-1.0:0.0);
         if(i==cur){ prev_sign = sgn; count = 1; }
         else { if(sgn==prev_sign && sgn!=0.0) count++; else break; }
      }
      streak = count * prev_sign;
   }

   // ---- range/body helpers ----
   double rng = (h - l); if(rng==0.0) rng = 1e-9;

   // ---- ATR moving-average ratio (atr_ratio) ----
   // atr_ma = میانگین ۵۰ کندل ATR؛ ATR را برای ۵۰ کندل اخیر می‌خوانیم
   double atr_ma = 0.0;
   {
      double atrbuf[];
      if(CopyBuffer(h_atr14, 0, sig_shift, 50, atrbuf) == 50)
      {
         double sm=0; for(int i=0;i<50;i++) sm+=atrbuf[i];
         atr_ma = sm/50.0;
      }
   }
   double atr_ratio = (atr_ma>0.0)? atr14/atr_ma : 1.0;

   // ---- ساخت آرایهٔ feature به ترتیب دقیق ----
   int p = 0;
   // ret_1..ret_21 (pct_change)
   feat[p++] = (float)((c/closeA[cur-1]) - 1.0);
   feat[p++] = (float)((c/closeA[cur-2]) - 1.0);
   feat[p++] = (float)((c/closeA[cur-3]) - 1.0);
   feat[p++] = (float)((c/closeA[cur-5]) - 1.0);
   feat[p++] = (float)((c/closeA[cur-8]) - 1.0);
   feat[p++] = (float)((c/closeA[cur-13]) - 1.0);
   feat[p++] = (float)((c/closeA[cur-21]) - 1.0);
   // rsi
   feat[p++] = (float)rsi7;
   feat[p++] = (float)rsi14;
   feat[p++] = (float)rsi21;
   // macd
   feat[p++] = (float)macd_main;
   feat[p++] = (float)macd_sig;
   feat[p++] = (float)macd_hist;
   // atr, atr_pct, atr_ratio, range_pct, body_pct
   feat[p++] = (float)atr14;
   feat[p++] = (float)(atr14 / c);
   feat[p++] = (float)atr_ratio;
   feat[p++] = (float)((h - l) / c);
   feat[p++] = (float)(MathAbs(c - o) / c);
   // adx, di_diff
   feat[p++] = (float)adx;
   feat[p++] = (float)(pdi - mdi);
   // bb_pos, bb_width
   double bb_w = (bb_up - bb_lo); if(bb_w==0.0) bb_w=1e-9;
   feat[p++] = (float)((c - bb_lo) / bb_w);
   feat[p++] = (float)(bb_w / c);
   // stoch
   feat[p++] = (float)stoch_k;
   feat[p++] = (float)stoch_d;
   // dist_ema20/50/100 (نسبی)
   feat[p++] = (float)((c - ema20) / ema20);
   feat[p++] = (float)((c - ema50) / ema50);
   feat[p++] = (float)((c - ema100) / ema100);
   // slope_20, slope_50 (نرمال‌شده با close)
   feat[p++] = (float)(RollingSlope(closeA, cur, 20) / c);
   feat[p++] = (float)(RollingSlope(closeA, cur, 50) / c);
   // zscore_20, zscore_50
   feat[p++] = (float)ZScore(closeA, cur, 20);
   feat[p++] = (float)ZScore(closeA, cur, 50);
   // vol_ratio = vol / rolling_mean(vol,20)
   double vol_ma20 = RollingMean(volA, cur, 20);
   feat[p++] = (float)((vol_ma20>0.0)? volA[cur]/vol_ma20 : 1.0);
   // upper_wick, lower_wick
   feat[p++] = (float)((h - MathMax(o,c)) / rng);
   feat[p++] = (float)((MathMin(o,c) - l) / rng);
   // streak
   feat[p++] = (float)streak;
   // hour_sin, hour_cos, dow, hour
   int hour = dt_cur.hour;
   int dow  = dt_cur.day_of_week; // 0=یکشنبه در MT5
   // pandas dayofweek: دوشنبه=0..یکشنبه=6 ؛ MT5: یکشنبه=0..شنبه=6
   int pandas_dow = (dow==0)?6:(dow-1);
   feat[p++] = (float)MathSin(2.0*M_PI*hour/24.0);
   feat[p++] = (float)MathCos(2.0*M_PI*hour/24.0);
   feat[p++] = (float)pandas_dow;
   feat[p++] = (float)hour;
   // dist_daily_open
   feat[p++] = (float)((c - daily_open) / daily_open);
   // MTF: trend_h1/slope_h1/ret_h1 ، h4 ، d1
   feat[p++] = (float)((c - emaH1) / emaH1);              // trend_h1
   feat[p++] = (float)(RollingSlope(closeA, cur, 4) / c); // slope_h1 (htf=4)
   feat[p++] = (float)((c/closeA[cur-4]) - 1.0);          // ret_h1
   feat[p++] = (float)((c - emaH4) / emaH4);              // trend_h4
   feat[p++] = (float)(RollingSlope(closeA, cur, 16) / c);// slope_h4 (htf=16)
   feat[p++] = (float)((c/closeA[cur-16]) - 1.0);         // ret_h4
   feat[p++] = (float)((c - emaD1) / emaD1);              // trend_d1
   feat[p++] = (float)(RollingSlope(closeA, cur, 96) / c);// slope_d1 (htf=96)
   feat[p++] = (float)((c/closeA[cur-96]) - 1.0);         // ret_d1
   // above_ema200, dist_ema200
   feat[p++] = (float)((c > ema200)?1.0:0.0);
   feat[p++] = (float)((c - ema200) / ema200);
   // vwap_dist, vwap_dist_atr, above_vwap
   feat[p++] = (float)((c - vwap) / c);
   feat[p++] = (float)((c - vwap) / atr14);
   feat[p++] = (float)((c > vwap)?1.0:0.0);
   // ema50_dist_atr, vol_z20, close_pos_in_range
   feat[p++] = (float)((c - ema50) / atr14);
   feat[p++] = (float)ZScore(volA, cur, 20);
   feat[p++] = (float)((c - l) / rng);

   if(p != NUM_FEATURES)
   {
      Print("خطای تعداد feature: ", p, " != ", NUM_FEATURES);
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| اجرای یک مدل ONNX روی feature و برگرداندن احتمال کلاس ۱          |
//+------------------------------------------------------------------+
double RunModel(long handle, const float &feat[])
{
   float in_data[];
   ArrayResize(in_data, NUM_FEATURES);
   for(int i=0; i<NUM_FEATURES; i++) in_data[i] = feat[i];

   // خروجی‌ها: 0=label (long) ، 1=probabilities (float[1,2])
   long   out_label[];
   float  out_proba[];
   ArrayResize(out_label, 1);
   ArrayResize(out_proba, 2);

   if(!OnnxRun(handle, ONNX_NO_CONVERSION, in_data, out_label, out_proba))
   {
      // تلاش دوم با حالت پیش‌فرض
      if(!OnnxRun(handle, ONNX_DEFAULT, in_data, out_label, out_proba))
      {
         if(InpVerbose) Print("OnnxRun ناموفق. err=", GetLastError());
         return -1.0;
      }
   }
   return (double)out_proba[1]; // احتمال کلاس ۱ (موفقیت TP)
}

//+------------------------------------------------------------------+
//| احتمال ensemble (میانگین مدل‌های بارگذاری‌شده)                    |
//+------------------------------------------------------------------+
double EnsembleProba(const float &feat[])
{
   double sum = 0.0; int cnt = 0;
   for(int i=0; i<3; i++)
   {
      if(g_model[i]==INVALID_HANDLE) continue;
      double pr = RunModel(g_model[i], feat);
      if(pr >= 0.0){ sum += pr; cnt++; }
   }
   if(cnt==0) return -1.0;
   return sum / cnt;
}

//+------------------------------------------------------------------+
//| شمارش معاملات باز این ربات                                       |
//+------------------------------------------------------------------+
int CountMyPositions()
{
   int cnt = 0;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)==(long)InpMagic &&
         PositionGetString(POSITION_SYMBOL)==_Symbol)
         cnt++;
   }
   return cnt;
}

//+------------------------------------------------------------------+
//| مدیریت خروج زمانی (max-hold): بستن معاملاتی که ۴۸ کندل باز مانده‌اند|
//+------------------------------------------------------------------+
void ManageTimeExit()
{
   datetime now = iTime(_Symbol, PERIOD_M15, 0);
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=(long)InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
      int bars_held = iBarShift(_Symbol, PERIOD_M15, open_time);
      if(bars_held >= InpMaxHoldBars)
      {
         trade.PositionClose(ticket);
         if(InpVerbose) PrintFormat("خروج زمانی: تیکت %I64u پس از %d کندل بسته شد",
                                     ticket, bars_held);
      }
   }
}

//+------------------------------------------------------------------+
//| باز کردن معاملهٔ LONG با TP/SL مبتنی بر ATR                       |
//+------------------------------------------------------------------+
void OpenLong(double atr14)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tp  = ask + InpTP_ATR * atr14;
   double sl  = ask - InpSL_ATR * atr14;

   // نرمال‌سازی به تعداد رقم اعشار نماد
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   tp = NormalizeDouble(tp, digits);
   sl = NormalizeDouble(sl, digits);

   if(trade.Buy(InpLotSize, _Symbol, ask, sl, tp, "S14-ML"))
   {
      if(InpVerbose)
         PrintFormat("ورود LONG @ %.2f | SL=%.2f TP=%.2f (ATR=%.2f)", ask, sl, tp, atr14);
   }
   else
   {
      if(InpVerbose) Print("خطا در باز کردن معامله: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| OnTick — منطق اصلی (فقط روی کندل جدید ارزیابی می‌شود)             |
//+------------------------------------------------------------------+
void OnTick()
{
   // مدیریت خروج زمانی در هر تیک
   ManageTimeExit();

   // فقط یک‌بار در هر کندل جدید ارزیابی کن
   datetime cur_bar = iTime(_Symbol, PERIOD_M15, 0);
   if(cur_bar == g_last_bar_time) return;
   g_last_bar_time = cur_bar;

   // فیلتر اسپرد
   double spread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpSpreadLimit)
   {
      if(InpVerbose) Print("اسپرد بالا، رد سیگنال: ", spread);
      return;
   }

   // محدودیت تعداد معاملات همزمان
   if(CountMyPositions() >= InpMaxPositions) return;

   // سیگنال روی کندل بسته‌شده (shift=1) ارزیابی می‌شود؛ ورود در open کندل جاری
   int sig_shift = 1;

   // ---- فیلتر کاندید پایه: close > EMA50 > EMA200 ----
   double c      = iClose(_Symbol, PERIOD_M15, sig_shift);
   double ema50  = IndVal(h_ema50, 0, sig_shift);
   double ema200 = IndVal(h_ema200,0, sig_shift);
   double atr14  = IndVal(h_atr14, 0, sig_shift);
   if(ema50==EMPTY_VALUE || ema200==EMPTY_VALUE || atr14==EMPTY_VALUE) return;
   if(!(c > ema50 && ema50 > ema200)) return;  // فقط روند صعودی

   // ---- ساخت feature و اجرای مدل ----
   float feat[];
   ArrayResize(feat, NUM_FEATURES);
   if(!BuildFeatures(sig_shift, feat)) return;

   double proba;
   if(InpUseEnsemble && g_num_models > 1)
      proba = EnsembleProba(feat);
   else
      proba = RunModel(g_model[0], feat);

   if(proba < 0.0) return; // خطای مدل

   if(InpVerbose)
      PrintFormat("proba=%.4f (THR=%.2f) %s", proba, InpThreshold,
                  (proba>=InpThreshold)?"→ ورود":"");

   // ---- تصمیم ورود ----
   if(proba >= InpThreshold)
      OpenLong(atr14);
}
//+------------------------------------------------------------------+
