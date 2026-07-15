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
