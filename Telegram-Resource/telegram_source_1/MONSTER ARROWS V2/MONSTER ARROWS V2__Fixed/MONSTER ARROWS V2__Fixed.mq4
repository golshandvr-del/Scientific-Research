#property copyright "Copyright © 2025, MEOW PURR";
#property link "https://t.me/MeowForex1";
#property version "2.0";
#property strict
#property description "I dedicate this Indicator to the Innocent Children of Palestine";

#property indicator_chart_window
#property indicator_buffers 2

#property indicator_color1 Lime
#property indicator_width1 4

#property indicator_color2 Red
#property indicator_width2 4


extern string __FILTERS__ = "=== FILTERS & CONFIRMATION ===";
extern bool EnableHTF_Filter = true; // Enable Higher Timeframe Confluence Filter
extern bool RequireBothHTF = true; // Require BOTH HTF confirmations (Strict Mode)
extern int ConfirmationDelay = 2; // Bars to wait to confirm signal (Non-Repaint)
extern string __SMC__ = "=== SMART MONEY CONCEPTS (SMC) ===";
extern bool EnableHunt = true; // Liquidity Sweep (Stop Hunt)
extern bool EnableFVG = true; // Fair Value Gap (Displacement)
extern bool ShowSMCVisuals = true; // Show SMC Lines & Boxes
extern color FVG_Buy_Color = DarkGreen; // FVG Box color for Buy
extern color FVG_Sell_Color = 139; // FVG Box color for Sell
extern color Hunt_Buy_Color = Aqua; // Hunt line color for Buy
extern color Hunt_Sell_Color = Magenta; // Hunt line color for Sell
extern string __ZIGZAG__ = "=== ZIGZAG SETTINGS ===";
extern int ZigZagDepth = 30; // ZigZag Depth
extern int ZigZagDeviation = 5; // ZigZag Deviation
extern int ZigZagBackstep = 3; // ZigZag Backstep
extern double FibLevel = 0.618; // Fibonacci Retracement Level
extern int BarsToAnalyze = 1000; // Number of historical bars to analyze
extern string __ATR__ = "=== DAILY ATR TARGETS ===";
extern bool Show_ATR_Targets = true; // Show Daily ATR Lines
extern int ATR_Period = 14; // ATR Period (Daily)
extern color ATR_High_Color = Aqua;
extern color ATR_Low_Color = Magenta;
extern int ATR_Style = 1;
extern string __TP__ = "=== AUTO TP SETTINGS ===";
extern bool Auto_Draw_TP = true; // Draw TP Lines for signal
extern color TP_Color = DodgerBlue;
extern color TP_Entry_Color = Yellow; // Entry line color
extern color TP1_Color = Lime; // TP1 line color
extern color TP2_Color = Orange; // TP2 line color
extern color TP3_Color = Red; // TP3 line color
extern int TP_Width = 1;
extern int TP_Style;
extern string __DASHBOARD__ = "=== DASHBOARD & ALERTS ===";
extern bool Show_Dashboard = true; // Show Info Panel on Left Side
extern int Dash_X_Offset = 20; // Horizontal position
extern int Dash_Y_Offset = 20; // Vertical position
extern color Dash_Title_Color = Gold;
extern color Dash_Text_Color = White;
extern bool Enable_Alerts = true; // Master Alert Switch
extern bool Alert_Popup = true; // Popup Alert
extern bool Alert_Sound = true; // Sound Alert
extern bool Alert_Email; // Email Alert
extern bool Alert_Push = true; // Mobile Push Notification
extern string Sound_File = "alert2.wav"; // Sound file
extern int Alert_Cooldown = 60; // Seconds between alerts
extern string __VISUAL__ = "=== ARROW VISUALS ===";
extern int Arrow_Size = 4; // Arrow size (1-5)
extern color Buy_Arrow_Color = Lime;
extern color Sell_Arrow_Color = Red;
extern int Arrow_Distance = 15; // Arrow distance from candle (points)
extern int BuyArrowCode = 233; // Buy arrow symbol code
extern int SellArrowCode = 234; // Sell arrow symbol code
extern bool Show_Confirmation_Dots = true; // Show confirmation indicator dots
extern string __MISC__ = "=== MISC SETTINGS ===";
extern int RefreshInterval = 1; // Check for signals every X seconds (1-60)
extern int DeepScanBars = 50; // Number of recent bars to scan for missed signals

long returned_l;
long Il_001E8;
bool Ib_001F0;
int Gi_00000;
string Is_00068;
double Id_00078;
int Ii_00080;
double Ind_000;
int Ii_00084;
long Gl_00000;
bool returned_b;
int returned_i;
int Ii_0017C;
int Gi_00001;
long Gl_00002;
int Gi_00003;
long Gl_00003;
int Gi_00002;
double Gd_00002;
int Ii_00180;
int Gi_00004;
long Gl_00005;
int Gi_00006;
long Gl_00006;
int Gi_00005;
double Gd_00005;
bool Ib_00184;
int Ii_000A8;
long Il_000A0;
string Gs_00001;
string Gs_00002;
string Gs_00003;
long Gl_00004;
long Il_001F8;
double Gd_00004;
int Gi_00007;
int Gi_00008;
long Gl_00009;
long Gl_00008;
int Gi_00009;
int Gi_0000A;
double Gd_0000A;
double Gd_00009;
int Gi_0000B;
int Gi_0000C;
long Gl_0000D;
long Gl_0000C;
int Gi_0000D;
int Gi_0000E;
double Gd_0000E;
double Gd_0000D;
double Gd_0000F;
bool Gb_00010;
double Gd_00010;
double Gd_00011;
double Gd_00012;
double Ind_003;
int Gi_00010;
int Gi_00013;
int Gi_00014;
long Gl_00015;
long Gl_00014;
int Gi_00015;
int Gi_00016;
double Gd_00016;
double Gd_00015;
int Gi_00017;
int Gi_00018;
long Gl_00019;
long Gl_00018;
int Gi_00019;
int Gi_0001A;
double Gd_0001A;
double Gd_00019;
int Gi_0001B;
long Gl_0001C;
long Gl_0001B;
int Gi_0001D;
long Gl_0001D;
int Gi_0001E;
int Gi_0001F;
long Gl_00020;
long Gl_0001F;
int Gi_00021;
int Gi_00022;
long Gl_00022;
bool Gb_00023;
int Gi_00026;
long Gl_00027;
long Gl_00026;
int Gi_0002B;
int Gi_0002C;
long Gl_0002C;
bool Gb_0002A;
int Gi_0002D;
bool Gb_0002E;
double Gd_0002D;
int Gi_0002E;
bool Gb_0002F;
double Gd_0002E;
bool Gb_00031;
int Gi_00031;
double Gd_00032;
double Gd_00031;
int Gi_00032;
long Gl_00033;
long Gl_00032;
int Gi_00034;
int Gi_00035;
int Gi_00036;
int Gi_0003B;
long Gl_0003C;
long Gl_0003B;
int Gi_0003D;
int Gi_0003E;
int Gi_0003F;
bool Gb_00044;
int Gi_00044;
double Gd_00044;
int Gi_00045;
bool Gb_00046;
double Id_001A0;
int Ii_001A8;
int Gi_00049;
int Gi_0004A;
int Gi_0004B;
int Gi_0004C;
int Gi_0004D;
int Gi_0004E;
int Gi_0004F;
int Gi_00050;
bool Gb_00051;
double Gd_0004E;
double Gd_00050;
int Gi_00051;
double Gd_00048;
double Gd_00051;
int Gi_00052;
double Gd_00047;
double Gd_00052;
int Gi_00053;
int Gi_00046;
bool Gb_00053;
bool Gb_00054;
double Gd_00055;
double Gd_00056;
bool Gb_00057;
int Gi_00057;
int Ii_001B8;
long Gl_00057;
long Gl_00058;
int Gi_00059;
long Gl_0005A;
long Gl_00059;
int Gi_0005B;
long Gl_0005B;
double Gd_0005B;
int Gi_0005C;
double Gd_0005C;
bool Gb_0005D;
double Gd_0005D;
int Gi_0005D;
double Ind_004;
double Gd_0005E;
int Gi_0005E;
int Gi_0005F;
long Gl_00060;
long Gl_0005F;
int Gi_00060;
double Gd_00061;
double Gd_00060;
int Gi_00062;
int Gi_00063;
int Ii_001C0;
long Gl_00063;
double Gd_00063;
int Gi_00064;
long Gl_00065;
long Gl_00064;
int Ii_001C4;
int Ii_001C8;
int Gi_00065;
double Id_001E0;
double Gd_00065;
int Gi_00066;
double Id_001D8;
double Gd_00066;
int Gi_00067;
double Id_001D0;
double Gd_00067;
int Gi_00069;
long Gl_0006A;
long Gl_00069;
int Gi_0006B;
double Gd_0006C;
double Gd_0006B;
long Il_00088;
double Id_001B0;
bool Gb_00093;
int Gi_00093;
long Gl_00094;
long Gl_00093;
bool Gb_00094;
int Gi_00094;
long Gl_00095;
int Gi_00068;
double Gd_00068;
bool Gb_0006D;
double Id_00188;
int Ii_00190;
int Gi_00070;
int Gi_00071;
int Gi_00072;
int Gi_00073;
int Gi_00074;
int Gi_00075;
int Gi_00076;
bool Gb_00077;
double Gd_00075;
double Gd_00076;
int Gi_00077;
double Gd_0006F;
double Gd_00077;
int Gi_00078;
double Gd_0006E;
double Gd_00078;
int Gi_00079;
int Gi_0006D;
bool Gb_00079;
bool Gb_0007A;
double Gd_0007B;
double Gd_0007C;
bool Gb_0007D;
int Gi_0007D;
long Gl_0007D;
long Gl_0007E;
int Gi_0007F;
long Gl_00080;
long Gl_0007F;
int Gi_00081;
long Gl_00081;
double Gd_00081;
int Gi_00082;
double Gd_00082;
bool Gb_00083;
int Gi_00083;
double Gd_00083;
int Gi_00084;
double Gd_00084;
int Gi_00085;
long Gl_00086;
long Gl_00085;
int Gi_00086;
double Gd_00087;
double Gd_00086;
int Gi_00088;
int Gi_00089;
long Gl_00089;
double Gd_00089;
int Gi_0008A;
long Gl_0008B;
long Gl_0008A;
int Gi_0008B;
double Gd_0008B;
int Gi_0008C;
double Gd_0008C;
int Gi_0008D;
double Gd_0008D;
int Gi_0008F;
long Gl_00090;
long Gl_0008F;
int Gi_00091;
double Gd_00092;
double Gd_00091;
long Il_00090;
double Id_00198;
int Gi_0008E;
double Gd_0008E;
int Gi_00040;
int Gi_00041;
int Gi_00042;
double Gd_00040;
bool Gb_00043;
double Gd_00043;
int Gi_00037;
int Gi_00038;
int Gi_00039;
double Gd_00037;
bool Gb_0003A;
double Gd_0003A;
double Gd_0003B;
bool Gb_0003B;
int Gi_0002F;
bool Gb_00030;
double Gd_0002F;
int Gi_00030;
double Gd_00030;
long Il_00098;
int Ii_001BC;
bool Gb_00001;
double Gd_00000;
bool Gb_00002;
double Gd_00001;
double Gd_00003;
bool Gb_00005;
bool Gb_00006;
bool Gb_00007;
double Gd_00006;
double Gd_00007;
double Gd_00008;
bool Gb_0000A;
long Gl_00001;
bool Gb_00000;
long Gl_0000A;
long Gl_0000F;
bool Gb_0000F;
int Gi_00011;
int Gi_00012;
bool Gb_00014;
bool Gb_00019;
int Gi_0001C;
long Gl_0001E;
bool Gb_0001E;
int Gi_00020;
long Gl_00023;
int Gi_00024;
int Gi_00025;
int Gi_00027;
long Gl_00028;
bool Gb_00004;
bool Gb_0000C;
double Gd_00018;
bool Gb_0001C;
double Gd_00020;
double Gd_00021;
int Gi_00023;
bool Gb_00024;
long Gl_00024;
double Gd_00028;
double Gd_00029;
int Gi_0002A;
bool Gb_0002C;
int Gi_00033;
bool Gb_00034;
long Gl_00034;
long Gl_00038;
double Gd_00034;
double Gd_00035;
bool Gb_00038;
double Gd_0002C;
long Gl_00030;
double Gd_00024;
double Gd_00025;
bool Gb_00028;
double Gd_0001C;
double Gd_0001D;
bool Gb_00020;
double Gd_00014;
bool Gb_00018;
double Gd_0000C;
int Gi_0000F;
long Gl_00010;
bool Gb_00008;
bool Gb_00003;
long Gl_0000B;
double Gd_0000B;
long Gl_0000E;
bool Gb_00012;
long Gl_00017;
long Gl_0001A;
double Gd_0001B;
double Gd_0001E;

double Id_00000[];
double Id_00034[];
long Il_000AC[];
double Id_000E0[];
long Il_00114[];
double Id_00148[];
double returned_double;

int init()
{
   string tmp_str00000;
   string tmp_str00001;
   int Li_FFFF8;
   int Li_FFFFC;
   Id_00078 = 0;
   Ii_00080 = 0;
   Ii_00084 = 0;
   Il_00088 = 0;
   Il_00090 = 0;
   Il_00098 = 0;
   Il_000A0 = 0;
   Ii_000A8 = 0;
   Ii_0017C = 0;
   Ii_00180 = 0;
   Ib_00184 = true;
   Id_00188 = 0;
   Ii_00190 = 0;
   Id_00198 = 0;
   Id_001A0 = 0;
   Ii_001A8 = 0;
   Id_001B0 = 0;
   Ii_001B8 = 0;
   Ii_001BC = 0;
   Ii_001C0 = 0;
   Ii_001C4 = 0;
   Ii_001C8 = -1;
   Id_001D0 = 0;
   Id_001D8 = 0;
   Id_001E0 = 0;
   Il_001E8 = 9779321599;
   Ib_001F0 = true;
   Il_001F8 = 0;
   /*
   if (TimeCurrent() > Il_001E8) { 
   Ib_001F0 = false;
   Alert("TRIAL EXPIRED! Please buy full version from @MeowForex1");
   } 
   else { 
   Ib_001F0 = true;
   } 
   */
   IndicatorShortName("Monster Arrows v2.0 (Ultimate SMC)");
   if (Arrow_Size <= 5) { 
   Gi_00000 = Arrow_Size;
   } 
   else { 
   Gi_00000 = 5;
   } 
   if (Gi_00000 >= 1) { 
   } 
   else { 
   Gi_00000 = 1;
   } 
   Li_FFFF8 = Gi_00000;
   SetIndexBuffer(0, Id_00000);
   SetIndexStyle(0, DRAW_ARROW, -1, Gi_00000, Buy_Arrow_Color);
   SetIndexArrow(0, BuyArrowCode);
   SetIndexLabel(0, "Monster Buy");
   SetIndexEmptyValue(0, 2147483647);
   SetIndexBuffer(1, Id_00034);
   SetIndexStyle(1, DRAW_ARROW, -1, Gi_00000, Sell_Arrow_Color);
   SetIndexArrow(1, SellArrowCode);
   SetIndexLabel(1, "Monster Sell");
   SetIndexEmptyValue(1, 2147483647);
   Is_00068 = _Symbol;
   Id_00078 = _Point;
   Ii_00080 = _Digits;
   if (Ii_00080 == 3 || _Digits == 5) { 
   
   Id_00078 = (Id_00078 * 10);
   } 
   Ii_00084 = _Period;
   ArrayResize(Il_000AC, 10000, 0);
   ArrayResize(Id_000E0, 10000, 0);
   ArrayResize(Il_00114, 10000, 0);
   ArrayResize(Id_00148, 10000, 0);
   if (Ib_001F0) { 
   tmp_str00001 = _Symbol + "_";
   tmp_str00001 = tmp_str00001 + IntegerToString(_Period, 0, 32);
   tmp_str00001 = tmp_str00001 + "_MonsterV2.bin";
   tmp_str00000 = tmp_str00001;
   if (FileIsExist(tmp_str00000, 0)) { 
   Gi_00000 = FileOpen(tmp_str00000, 5);
   if (Gi_00000 != -1) { 
   if (FileSize(Gi_00000) > 0) { 
   Ii_0017C = FileReadInteger(Gi_00000, 4);
   if (Ii_0017C > 10000) { 
   Ii_0017C = 10000;
   } 
   Gi_00001 = 0;
   if (Ii_0017C > 0) { 
   do { 
   Gl_00002 = FileReadLong(Gi_00000);
   Il_000AC[Gi_00001] = Gl_00002;
   Id_000E0[Gi_00001] = FileReadDouble(Gi_00000, 0);
   Gi_00001 = Gi_00001 + 1;
   } while (Gi_00001 < Ii_0017C); 
   } 
   Ii_00180 = FileReadInteger(Gi_00000, 4);
   if (Ii_00180 > 10000) { 
   Ii_00180 = 10000;
   } 
   Gi_00004 = 0;
   if (Ii_00180 > 0) { 
   do { 
   Gl_00005 = FileReadLong(Gi_00000);
   Il_00114[Gi_00004] = Gl_00005;
   Id_00148[Gi_00004] = FileReadDouble(Gi_00000, 0);
   Gi_00004 = Gi_00004 + 1;
   } while (Gi_00004 < Ii_00180); 
   }} 
   FileClose(Gi_00000);
   }}} 
   if (Show_Dashboard && Ib_001F0) { 
   func_1021();
   } 
   Ib_00184 = true;
   Ii_000A8 = Bars;
   Il_000A0 = TimeCurrent();
   Li_FFFFC = 0;
   return 0;
}

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[], const double &open[], const double &high[], const double &low[], const double &close[], const long &tick_volume[], const long &volume[], const int &spread[])
{
   string tmp_str00000;
   string tmp_str00001;
   string tmp_str00002;
   string tmp_str00003;
   string tmp_str00004;
   string tmp_str00005;
   string tmp_str00006;
   string tmp_str00007;
   string tmp_str00008;
   string tmp_str00009;
   string tmp_str0000A;
   string tmp_str0000B;
   string tmp_str0000C;
   string tmp_str0000D;
   string tmp_str0000E;
   string tmp_str0000F;
   string tmp_str00010;
   string tmp_str00011;
   string tmp_str00012;
   string tmp_str00013;
   string tmp_str00014;
   string tmp_str00015;
   int Li_FFFFC;
   int Li_FFFF8;
   string Ls_FFDD4;
   bool Lb_FFFF3;
   int Li_FFFEC;
   long Ll_FFFE0;
   int Li_FFFDC;
   int Li_FFFD8;
   int Li_FFFD4;
   int Li_FFFD0;
   int Li_FFFCC;
   int Li_FFFC8;
   int Li_FFFC4;
   double Ld_FFFB8;
   bool Lb_FFFB7;
   bool Lb_FFFB6;
   bool Lb_FFFB5;
   int Li_FFFB0;
   int Li_FFFAC;
   int Li_FFF28;
   int Li_FFF24;
   double Ld_FFF18;
   bool Lb_FFF17;
   bool Lb_FFF16;
   bool Lb_FFF15;
   double Ld_FFF08;
   double Ld_FFF00;
   int Li_FFEFC;
   double Ld_FFEF0;
   double Ld_FFEE8;
   double Ld_FFEE0;
   double Ld_FFED8;
   double Ld_FFED0;
   bool Lb_FFECF;
   bool Lb_FFECE;
   bool Lb_FFECD;
   double Ld_FFEC0;
   double Ld_FFEB8;
   int Li_FFEB4;
   double Ld_FFEA8;
   double Ld_FFEA0;
   double Ld_FFE98;
   double Ld_FFE90;
   double Ld_FFE88;

   if (rates_total < 100) { 
   Li_FFFFC = 0;
   return Li_FFFFC;
   } 
   Li_FFFF8 = 1;
   /*
   if (TimeCurrent() > Il_001E8) { 
   Li_FFFF8 = 0;
   Ib_001F0 = false;
   if (ObjectFind("M_Title") >= 0) { 
   string Ls_FFDD4[15] = { "M_Title", "M_License", "M_HTF", "M_SMC", "M_State", "M_Ov_Head", "M_Ov_Val", "M_Tr_Head", "M_Tr_M1", "M_Tr_M5", "M_Tr_M15", "M_Tr_M30", "M_Tr_H1", "M_Tr_H4", "M_Tr_D1" };
   Gi_00000 = 0;
   if (ArraySize(Li_FFDD4) > 0) { 
   do { 
   ObjectDelete(Ls_FFDD4[Gi_00000]);
   if (Gi_00000 >= 8) { 
   tmp_str00000 = Ls_FFDD4[Gi_00000] + "_Lbl";
   ObjectDelete(tmp_str00000);
   tmp_str00001 = Ls_FFDD4[Gi_00000] + "_Val";
   ObjectDelete(tmp_str00001);
   } 
   Gi_00000 = Gi_00000 + 1;
   } while (Gi_00000 < ArraySize(Li_FFDD4)); 
   } 
   ArrayFree(Ls_FFDD4);
   } 
   Comment("\n\n\n   TRIAL EXPIRED.\n   Please buy full version from @MeowForex1");
   Gl_00004 = TimeCurrent() - Il_001F8;
   if (Gl_00004 > 300) { 
   Alert("TRIAL EXPIRED! Please buy full version from @MeowForex1");
   Il_001F8 = TimeCurrent();
   } 
   Li_FFFF4 = 0;
   if (Fa_i_00 > 0) { 
   do { 
   Id_00000[Li_FFFF4] = 2147483647;
   Id_00034[Li_FFFF4] = 2147483647;
   Li_FFFF4 = Li_FFFF4 + 1;
   } while (Li_FFFF4 < Fa_i_00); 
   } 
   Li_FFFFC = 0;
   return Li_FFFFC;
   } 
   */
   if (Ib_00184) { 
   Gi_00006 = 0;
   Gi_00007 = 0;
   if (Ii_0017C > 0) { 
   do { 
   Gi_00006 = iBarShift(NULL, 0, Il_000AC[Gi_00007], false);
   if (Gi_00006 >= 0 && Gi_00006 < Bars) { 
   Id_00000[Gi_00006] = Id_000E0[Gi_00007];
   } 
   Gi_00007 = Gi_00007 + 1;
   } while (Gi_00007 < Ii_0017C); 
   } 
   Gi_0000B = 0;
   if (Ii_00180 > 0) { 
   do { 
   Gi_00006 = iBarShift(NULL, 0, Il_00114[Gi_0000B], false);
   if (Gi_00006 >= 0 && Gi_00006 < Bars) { 
   Id_00034[Gi_00006] = Id_00148[Gi_0000B];
   } 
   Gi_0000B = Gi_0000B + 1;
   } while (Gi_0000B < Ii_00180); 
   } 
   func_1009();
   Ib_00184 = false;
   } 
   if (Show_ATR_Targets) { 
   Gd_0000F = iATR(NULL, 1440, ATR_Period, 0);
   returned_double = iOpen(NULL, 1440, 0);
   if ((Gd_0000F <= 0) == false && (returned_double <= 0) == false) { 
   Gd_00010 = (returned_double + Gd_0000F);
   Gd_00012 = (returned_double - Gd_0000F);
   if (ObjectFind("Monster_ATR_High") < 0) { 
   ObjectCreate(0, "Monster_ATR_High", OBJ_HLINE, 0, 0, Gd_00010, 0, 0, 0, 0);
   ObjectSet("Monster_ATR_High", OBJPROP_COLOR, ATR_High_Color);
   ObjectSet("Monster_ATR_High", OBJPROP_STYLE, ATR_Style);
   ObjectSet("Monster_ATR_High", OBJPROP_WIDTH, 1);
   ObjectSetString(0, "Monster_ATR_High", 206, "Daily ATR High Target");
   } 
   else { 
   ObjectSet("Monster_ATR_High", OBJPROP_PRICE1, Gd_00010);
   } 
   if (ObjectFind("Monster_ATR_Low") < 0) { 
   ObjectCreate(0, "Monster_ATR_Low", OBJ_HLINE, 0, 0, Gd_00012, 0, 0, 0, 0);
   ObjectSet("Monster_ATR_Low", OBJPROP_COLOR, ATR_Low_Color);
   ObjectSet("Monster_ATR_Low", OBJPROP_STYLE, ATR_Style);
   ObjectSet("Monster_ATR_Low", OBJPROP_WIDTH, 1);
   ObjectSetString(0, "Monster_ATR_Low", 206, "Daily ATR Low Target");
   } 
   else { 
   ObjectSet("Monster_ATR_Low", OBJPROP_PRICE1, Gd_00012);
   }}} 
   Lb_FFFF3 = false;
   if (Bars != Ii_000A8) { 
   Lb_FFFF3 = true;
   Ii_000A8 = Bars;
   } 
   Li_FFFEC = 0;
   if (prev_calculated == 0) { 
   Li_FFFEC = rates_total;
   Gi_00010 = 0;
   Gi_00013 = 0;
   if (Ii_0017C > 0) { 
   do { 
   Gi_00010 = iBarShift(NULL, 0, Il_000AC[Gi_00013], false);
   if (Gi_00010 >= 0 && Gi_00010 < Bars) { 
   Id_00000[Gi_00010] = Id_000E0[Gi_00013];
   } 
   Gi_00013 = Gi_00013 + 1;
   } while (Gi_00013 < Ii_0017C); 
   } 
   Gi_00017 = 0;
   if (Ii_00180 > 0) { 
   do { 
   Gi_00010 = iBarShift(NULL, 0, Il_00114[Gi_00017], false);
   if (Gi_00010 >= 0 && Gi_00010 < Bars) { 
   Id_00034[Gi_00010] = Id_00148[Gi_00017];
   } 
   Gi_00017 = Gi_00017 + 1;
   } while (Gi_00017 < Ii_00180); 
   } 
   func_1009();
   } 
   else { 
   Li_FFFEC = rates_total - prev_calculated;
   } 
   Ll_FFFE0 = TimeCurrent();
   if (RefreshInterval <= 60) { 
   Gi_0001B = RefreshInterval;
   } 
   else { 
   Gi_0001B = 60;
   } 
   if (Gi_0001B >= 1) { 
   } 
   else { 
   Gi_0001B = 1;
   } 
   Li_FFFDC = Gi_0001B;
   Gl_0001C = Ll_FFFE0 - Il_000A0;
   Gl_0001B = Gi_0001B;
   if (Gl_0001C >= Gl_0001B) { 
   Il_000A0 = Ll_FFFE0;
   RefreshRates();
   WindowRedraw();
   } 
   Gl_0001B = Ll_FFFE0 - Il_000A0;
   Gi_0001D = Li_FFFDC + 1;
   Gl_0001D = Gi_0001D;
   if (Lb_FFFF3 || Gl_0001B < Gl_0001D) {
   
   Gi_0001D = DeepScanBars;
   if (DeepScanBars >= BarsToAnalyze) { 
   Gi_0001E = BarsToAnalyze;
   } 
   else { 
   Gi_0001E = Gi_0001D;
   } 
   Gi_0001D = Li_FFFEC;
   if (Li_FFFEC <= Gi_0001E) { 
   } 
   else { 
   Gi_0001E = Gi_0001D;
   } 
   Li_FFFEC = Gi_0001E;
   }
   Gi_0001E = Li_FFFEC;
   if (Li_FFFEC >= BarsToAnalyze) { 
   Gi_0001F = BarsToAnalyze;
   } 
   else { 
   Gi_0001F = Gi_0001E;
   } 
   Li_FFFEC = Gi_0001F;
   Li_FFFEC = Gi_0001F * Li_FFFF8;
   Li_FFFD8 = Li_FFFEC;
   if (Li_FFFEC >= rates_total) { 
   Li_FFFD8 = rates_total - 1;
   } 
   Li_FFFD4 = func_1017(_Period);
   Li_FFFD0 = func_1018(_Period);
   Li_FFFCC = Li_FFFD8;
   if (Li_FFFD8 >= ConfirmationDelay) { 
   do { 
   Gl_00020 = Time[Li_FFFCC];
   Gi_00021 = 0;
   Gb_00023 = false;
   if (Ii_0017C > 0) {
   do { 
   if (Il_000AC[Gi_00021] == Gl_00020) {
   Gb_00023 = true;
   break;
   }
   Gi_00021 = Gi_00021 + 1;
   } while (Gi_00021 < Ii_0017C); 
   } 
   
   if (Gb_00023 != true) { 
   Gl_00027 = Time[Li_FFFCC];
   Gi_0002B = 0;
   Gb_0002A = false;
   if (Ii_00180 > 0) {
   do { 
   if (Il_00114[Gi_0002B] == Gl_00027) {
   Gb_0002A = true;
   break;
   }
   Gi_0002B = Gi_0002B + 1;
   } while (Gi_0002B < Ii_00180); 
   }
   
   if (Gb_0002A != true) { 
   Li_FFFC8 = 0;
   Li_FFFC4 = Li_FFFCC + 1;
   Gi_0002D = Li_FFFCC + 200;
   if (Li_FFFC4 < Gi_0002D && Li_FFFC4 < rates_total) { 
   do { 
   if ((Id_00000[Li_FFFC4] != 2147483647) && (Id_00000[Li_FFFC4] != 0)) { 
   Li_FFFC8 = 1;
   break; 
   } 
   if ((Id_00034[Li_FFFC4] != 2147483647) && (Id_00034[Li_FFFC4] != 0)) { 
   Li_FFFC8 = -1;
   break; 
   } 
   Li_FFFC4 = Li_FFFC4 + 1;
   Gi_00031 = Li_FFFCC + 200;
   if (Li_FFFC4 >= Gi_00031) break; 
   } while (Li_FFFC4 < rates_total); 
   } 
   returned_double = iCustom(NULL, 0, "ZigZag", ZigZagDepth, ZigZagDeviation, ZigZagBackstep, 0, Li_FFFCC);
   Ld_FFFB8 = returned_double;
   if ((Ld_FFFB8 <= 0) != true) { 
   Gd_00032 = (_Point * 2);
   Lb_FFFB7 = (returned_double >= (High[Li_FFFCC] - Gd_00032));
   Lb_FFFB6 = !Lb_FFFB7;
   Lb_FFFB5 = true;
   if (EnableHTF_Filter && Li_FFFD4 != _Period) { 
   Gi_00034 = Li_FFFD4;
   Gi_00035 = iBarShift(NULL, Li_FFFD4, Time[Li_FFFCC], false);
   if (Gi_00035 < 0) { 
   Gi_00036 = 0;
   } 
   else { 
   Gi_00037 = iBars(NULL, Gi_00034) - 1;
   Gi_00038 = Gi_00035 + 100;
   if (Gi_00038 >= Gi_00037) { 
   } 
   else { 
   Gi_00037 = Gi_00038;
   } 
   Gi_00038 = Gi_00037;
   Gi_00039 = Gi_00035;
   Gi_00036 = 0;
   if (Gi_00035 < Gi_00037) {
   do { 
   Gd_00037 = iCustom(NULL, Gi_00034, "ZigZag", ZigZagDepth, ZigZagDeviation, ZigZagBackstep, 0, Gi_00039);
   if ((Gd_00037 > 0)) {
   Gd_0003A = iHigh(NULL, Gi_00034, Gi_00039);
   Gd_0003B = (MarketInfo(_Symbol, MODE_POINT) * 2);
   if ((Gd_00037 >= (Gd_0003A - Gd_0003B))) {
   Gi_00036 = -1;
   break;
   }
   Gi_00036 = 1;
   break;
   }
   Gi_00039 = Gi_00039 + 1;
   } while (Gi_00039 < Gi_00038); 
   }
   } 
   Li_FFFB0 = Gi_00036;
   Gi_0003D = Li_FFFD0;
   Gi_0003E = iBarShift(NULL, Li_FFFD0, Time[Li_FFFCC], false);
   if (Gi_0003E < 0) { 
   Gi_0003F = 0;
   } 
   else { 
   Gi_00040 = iBars(NULL, Gi_0003D) - 1;
   Gi_00041 = Gi_0003E + 100;
   if (Gi_00041 >= Gi_00040) { 
   } 
   else { 
   Gi_00040 = Gi_00041;
   } 
   Gi_00041 = Gi_00040;
   Gi_00042 = Gi_0003E;
   Gi_0003F = 0;
   if (Gi_0003E < Gi_00040) {
   do { 
   Gd_00040 = iCustom(NULL, Gi_0003D, "ZigZag", ZigZagDepth, ZigZagDeviation, ZigZagBackstep, 0, Gi_00042);
   if ((Gd_00040 > 0)) {
   Gd_00043 = iHigh(NULL, Gi_0003D, Gi_00042);
   Gd_00044 = (MarketInfo(_Symbol, MODE_POINT) * 2);
   if ((Gd_00040 >= (Gd_00043 - Gd_00044))) {
   Gi_0003F = -1;
   break;
   }
   Gi_0003F = 1;
   break;
   }
   Gi_00042 = Gi_00042 + 1;
   } while (Gi_00042 < Gi_00041); 
   }
   } 
   Li_FFFAC = Gi_0003F;
   if (RequireBothHTF != false) {
   if (Lb_FFFB6 != false) {
   Gb_00044 = (Li_FFFB0 == 1);
   if (Gb_00044) { 
   Gb_00044 = (Gi_0003F == 1);
   } 
   Lb_FFFB5 = Gb_00044;
   }
   else{
   if (Lb_FFFB7 != false) {
   Gb_00044 = (Li_FFFB0 == -1);
   if (Gb_00044) { 
   Gb_00044 = (Li_FFFAC == -1);
   } 
   Lb_FFFB5 = Gb_00044;
   }}}
   else{
   if (Lb_FFFB6) { 
   Gb_00044 = (Li_FFFB0 == 1);
   if (Gb_00044 != true) { 
   Gb_00044 = (Li_FFFAC == 1);
   } 
   Lb_FFFB5 = Gb_00044;
   } 
   else { 
   if (Lb_FFFB7) { 
   Gb_00044 = (Li_FFFB0 == -1);
   if (Gb_00044 != true) { 
   Gb_00044 = (Li_FFFAC == -1);
   } 
   Lb_FFFB5 = Gb_00044;
   }}}} 
   double Ld_FFF9C[2];
   ArrayInitialize(Ld_FFF9C, 0);
   int Li_FFF60[2];
   Li_FFF28 = 0;
   Li_FFF24 = Li_FFFCC + 1;
   if (Li_FFF24 < rates_total) { 
   do { 
   returned_double = iCustom(NULL, 0, "ZigZag", ZigZagDepth, ZigZagDeviation, ZigZagBackstep, 0, Li_FFF24);
   Ld_FFF18 = returned_double;
   if ((Ld_FFF18 > 0)) { 
   Ld_FFF9C[Li_FFF28] = returned_double;
   Li_FFF60[Li_FFF28] = Li_FFF24;
   Li_FFF28 = Li_FFF28 + 1;
   } 
   Li_FFF24 = Li_FFF24 + 1;
   if (Li_FFF24 >= rates_total) break; 
   } while (Li_FFF28 < 2); 
   } 
   if (Lb_FFFB6 && Li_FFFC8 != 1 && Lb_FFFB5) { 
   Lb_FFF17 = false;
   Lb_FFF16 = true;
   Lb_FFF15 = true;
   Ld_FFF08 = 0;
   Ld_FFF00 = 0;
   Li_FFEFC = 0;
   if (EnableHunt) { 
   if ((Id_001A0 > 0)) {
   Lb_FFF16 = (Ld_FFFB8 < Id_001A0);
   if (Lb_FFF16 && ShowSMCVisuals) {
   func_1014(Ii_001A8, Li_FFFCC, Id_001A0, true);
   }}
   else{
   Lb_FFF16 = false;
   }} 
   if (EnableFVG) { 
   Gi_00049 = Li_FFFCC;
   Gi_0004A = Bars - 3;
   Gi_0004B = Li_FFFCC + ZigZagDepth;
   if (Gi_0004B >= Gi_0004A) { 
   } 
   else { 
   Gi_0004A = Gi_0004B;
   } 
   Gi_0004B = Gi_0004A;
   Gi_0004C = Gi_00049 + 2;
   Gi_0004D = Gi_0004C;
   Gb_00053 = false;
   if (Gi_0004C < Gi_0004A) {
   do { 
   Gi_0004C = Gi_0004D + 2;
   if (Gi_0004C < Bars) {
   Gi_0004E = Gi_0004C;
   Gi_0004F = Gi_0004C;
   if ((High[Gi_0004C] < Low[Gi_0004D])) {
   Ld_FFF08 = Low[Gi_0004D];
   Gi_00052 = Gi_0004F;
   Ld_FFF00 = High[Gi_0004F];
   Gi_00053 = Gi_0004D + 1;
   Li_FFEFC = Gi_00053;
   Gb_00053 = true;
   break;
   }}
   Gi_0004D = Gi_0004D + 1;
   } while (Gi_0004D < Gi_0004B); 
   }
   
   Lb_FFF15 = Gb_00053;
   if (Gb_00053 && ShowSMCVisuals) { 
   Gb_00054 = true;
   if (Li_FFEFC >= 0 && Li_FFEFC < Bars && Li_FFFCC >= 0 
   && Li_FFFCC < Bars && (Ld_FFF08 <= Ld_FFF00) == false) { 
   Gi_00057 = Ii_001B8 % 50;
   tmp_str00003 = "MonsterFVG_" + IntegerToString(Gi_00057, 0, 32);
   tmp_str00002 = tmp_str00003;
   ObjectDelete(tmp_str00002);
   Gi_00057 = Li_FFEFC + 1;
   Gi_00059 = Li_FFFCC - 1;
   if (Gi_00059 >= 0) { 
   } 
   else { 
   Gi_00059 = 0;
   } 
   ObjectCreate(0, tmp_str00002, OBJ_RECTANGLE, 0, Time[Gi_00057], Ld_FFF08, Time[Gi_00059], Ld_FFF00);
   if (Gb_00054) { 
   Gi_0005B = FVG_Buy_Color;
   } 
   else { 
   Gi_0005B = FVG_Sell_Color;
   } 
   ObjectSetInteger(0, tmp_str00002, 6, Gi_0005B);
   ObjectSetInteger(0, tmp_str00002, 7, 0);
   ObjectSetInteger(0, tmp_str00002, 8, 1);
   ObjectSetInteger(0, tmp_str00002, 9, 1);
   ObjectSetInteger(0, tmp_str00002, 1031, 1);
   ObjectSetInteger(0, tmp_str00002, 1000, 0);
   if (Gb_00054) { 
   tmp_str00003 = "Bullish FVG Zone";
   } 
   else { 
   tmp_str00003 = "Bearish FVG Zone";
   } 
   ObjectSetString(0, tmp_str00002, 206, tmp_str00003);
   Ii_001B8 = Ii_001B8 + 1;
   }}} 
   if (Li_FFF28 >= 2) {
   Ld_FFEF0 = Ld_FFF9C[0];
   Ld_FFEE8 = Ld_FFF9C[1];
   Gb_0005D = (Ld_FFEF0 > Ld_FFEE8);
   if ((Ld_FFEF0 > Ld_FFEE8)) {
   Ld_FFEE0 = (Ld_FFEF0 - Ld_FFEE8);
   Gd_0005D = (Ld_FFEE0 * FibLevel);
   Ld_FFED8 = (Ld_FFEF0 - Gd_0005D);
   Gb_0005D = (Ld_FFFB8 <= Ld_FFED8);
   if (Gb_0005D) { 
   Gb_0005D = Lb_FFF16;
   } 
   if (Gb_0005D) { 
   Gb_0005D = Lb_FFF15;
   } 
   Lb_FFF17 = Gb_0005D;
   }
   else{
   Gb_0005D = Lb_FFF16;
   if (Lb_FFF16) { 
   Gb_0005D = Lb_FFF15;
   } 
   Lb_FFF17 = Gb_0005D;
   }}
   else{
   Gb_0005D = Lb_FFF16;
   if (Lb_FFF16) { 
   Gb_0005D = Lb_FFF15;
   } 
   Lb_FFF17 = Gb_0005D;
   }
   if (Lb_FFF17) { 
   Gd_0005E = (Arrow_Distance * _Point);
   Ld_FFED0 = (Low[Li_FFFCC] - Gd_0005E);
   Id_00000[Li_FFFCC] = Ld_FFED0;
   func_1032(Time[Li_FFFCC], Ld_FFED0, true);
   if (Show_Confirmation_Dots) { 
   Gd_00061 = Low[Li_FFFCC];
   Gi_00062 = Li_FFFCC;
   if (Li_FFFCC >= 0 && Li_FFFCC < Bars) { 
   Gi_00063 = Ii_001C0 % 50;
   tmp_str00005 = "MonsterDot_" + IntegerToString(Gi_00063, 0, 32);
   tmp_str00004 = tmp_str00005;
   ObjectDelete(tmp_str00004);
   Gd_00063 = ((Arrow_Distance * 0.5) * _Point);
   ObjectCreate(0, tmp_str00004, OBJ_ARROW, 0, Time[Li_FFFCC], (Gd_00061 - Gd_00063));
   ObjectSetInteger(0, tmp_str00004, 14, 159);
   ObjectSetInteger(0, tmp_str00004, 6, 16776960);
   ObjectSetInteger(0, tmp_str00004, 8, 2);
   ObjectSetInteger(0, tmp_str00004, 9, 0);
   ObjectSetInteger(0, tmp_str00004, 1000, 0);
   ObjectSetString(0, tmp_str00004, 206, "SMC Confirmation");
   Ii_001C0 = Ii_001C0 + 1;
   }} 
   Ii_001C4 = 1;
   Ii_001C8 = Li_FFFCC;
   Id_001E0 = Close[Li_FFFCC];
   Id_001D8 = Low[Li_FFFCC];
   if (Li_FFF28 >= 1) { 
   Id_001D0 = Ld_FFF9C[0];
   } 
   else { 
   Gi_00068 = iHighest(NULL, 0, 2, 30, Li_FFFCC);
   Id_001D0 = High[Gi_00068];
   } 
   if (Li_FFFCC == ConfirmationDelay) { 
   Gl_0006A = Time[Li_FFFCC];
   tmp_str00005 = "BUY";
   if (Gl_0006A > Il_00088) { 
   Il_00088 = Gl_0006A;
   if (Enable_Alerts) { 
   tmp_str00006 = func_1020(_Period);
   tmp_str00007 = TimeToString(Gl_0006A, 3);
   tmp_str00008 = DoubleToString(Close[Li_FFFCC], Ii_00080);
   tmp_str00009 = StringFormat("?? MONSTER ARROWS V2 ??\n\n%s SIGNAL!\n\nPair: %s\nTimeframe: %s\nPrice: %s\nTime: %s\n\n? HTF Confirmed\n? SMC Confirmed", tmp_str00005, _Symbol, tmp_str00006, tmp_str00008, tmp_str00007);
   tmp_str0000A = StringFormat("Monster V2: %s %s %s @ %s", tmp_str00005, _Symbol, tmp_str00006, tmp_str00008);
   if (Alert_Sound) { 
   PlaySound(Sound_File);
   } 
   if (Alert_Popup) { 
   Alert(tmp_str00009);
   } 
   if (Alert_Push) { 
   SendNotification(tmp_str0000A);
   } 
   if (Alert_Email) { 
   tmp_str0000B = StringFormat("Monster V2 %s - %s %s", tmp_str00005, _Symbol, tmp_str00006);
   SendMail(tmp_str0000B, tmp_str00009);
   } 
   Print("?? MONSTER V2: ", tmp_str0000A);
   }}}} 
   Id_001B0 = Id_001A0;
   Id_001A0 = Ld_FFFB8;
   Ii_001A8 = Li_FFFCC;
   } 
   else { 
   Print("######## ", Lb_FFFB7, " : ", Li_FFFC8);
   if (Lb_FFFB7 && Li_FFFC8 != -1 && Lb_FFFB5) { 
   Lb_FFECF = false;
   Lb_FFECE = true;
   Lb_FFECD = true;
   Ld_FFEC0 = 0;
   Ld_FFEB8 = 0;
   Li_FFEB4 = 0;
   if (EnableHunt) { 
   if ((Id_00188 > 0)) {
   Lb_FFECE = (Ld_FFFB8 > Id_00188);
   if (Lb_FFECE && ShowSMCVisuals) {
   func_1014(Ii_00190, Li_FFFCC, Id_00188, false);
   }}
   else{
   Lb_FFECE = false;
   }} 
   if (EnableFVG) { 
   Gi_00070 = Li_FFFCC;
   Gi_00071 = Bars - 3;
   Gi_00072 = Li_FFFCC + ZigZagDepth;
   if (Gi_00072 >= Gi_00071) { 
   } 
   else { 
   Gi_00071 = Gi_00072;
   } 
   Gi_00072 = Gi_00071;
   Gi_00073 = Gi_00070 + 2;
   Gi_00074 = Gi_00073;
   Gb_00079 = false;
   if (Gi_00073 < Gi_00071) {
   do { 
   Gi_00073 = Gi_00074 + 2;
   if (Gi_00073 < Bars) {
   Gi_00075 = Gi_00073;
   if ((Low[Gi_00073] > High[Gi_00074])) {
   Gi_00077 = Gi_00073;
   Ld_FFEC0 = Low[Gi_00073];
   Ld_FFEB8 = High[Gi_00074];
   Gi_00079 = Gi_00074 + 1;
   Li_FFEB4 = Gi_00079;
   Gb_00079 = true;
   break;
   }}
   Gi_00074 = Gi_00074 + 1;
   } while (Gi_00074 < Gi_00072); 
   }
   
   Lb_FFECD = Gb_00079;
   if (Gb_00079 && ShowSMCVisuals) { 
   Gb_0007A = false;
   if (Li_FFEB4 >= 0 && Li_FFEB4 < Bars && Li_FFFCC >= 0 
   && Li_FFFCC < Bars && (Ld_FFEC0 <= Ld_FFEB8) == false) { 
   Gi_0007D = Ii_001B8 % 50;
   tmp_str0000D = "MonsterFVG_" + IntegerToString(Gi_0007D, 0, 32);
   tmp_str0000C = tmp_str0000D;
   ObjectDelete(tmp_str0000C);
   Gi_0007D = Li_FFEB4 + 1;
   Gi_0007F = Li_FFFCC - 1;
   if (Gi_0007F >= 0) { 
   } 
   else { 
   Gi_0007F = 0;
   } 
   ObjectCreate(0, tmp_str0000C, OBJ_RECTANGLE, 0, Time[Gi_0007D], Ld_FFEC0, Time[Gi_0007F], Ld_FFEB8);
   if (Gb_0007A) { 
   Gi_00081 = FVG_Buy_Color;
   } 
   else { 
   Gi_00081 = FVG_Sell_Color;
   } 
   ObjectSetInteger(0, tmp_str0000C, 6, Gi_00081);
   ObjectSetInteger(0, tmp_str0000C, 7, 0);
   ObjectSetInteger(0, tmp_str0000C, 8, 1);
   ObjectSetInteger(0, tmp_str0000C, 9, 1);
   ObjectSetInteger(0, tmp_str0000C, 1031, 1);
   ObjectSetInteger(0, tmp_str0000C, 1000, 0);
   if (Gb_0007A) { 
   tmp_str0000D = "Bullish FVG Zone";
   } 
   else { 
   tmp_str0000D = "Bearish FVG Zone";
   } 
   ObjectSetString(0, tmp_str0000C, 206, tmp_str0000D);
   Ii_001B8 = Ii_001B8 + 1;
   }}} 
   
   if (Li_FFF28 >= 2) {
   Ld_FFEA8 = Ld_FFF9C[0];
   Ld_FFEA0 = Ld_FFF9C[1];
   Gb_00083 = Ld_FFEA8 < Ld_FFEA0;
   if ((Ld_FFEA8 < Ld_FFEA0)) {
   Ld_FFE98 = (Ld_FFEA0 - Ld_FFEA8);
   Ld_FFE90 = ((Ld_FFE98 * FibLevel) + Ld_FFEA8);
   Gb_00083 = (Ld_FFFB8 >= Ld_FFE90);
   if (Gb_00083) { 
   Gb_00083 = Lb_FFECE;
   } 
   if (Gb_00083) { 
   Gb_00083 = Lb_FFECD;
   } 
   Lb_FFECF = Gb_00083;
   }
   else{
   Gb_00083 = Lb_FFECE;
   if (Lb_FFECE) { 
   Gb_00083 = Lb_FFECD;
   } 
   Lb_FFECF = Gb_00083;
   }}
   else{
   Gb_00083 = Lb_FFECE;
   if (Lb_FFECE) { 
   Gb_00083 = Lb_FFECD;
   } 
   Lb_FFECF = Gb_00083;
   }
   
   if (Lb_FFECF) { 
   Ld_FFE88 = ((Arrow_Distance * _Point) + High[Li_FFFCC]);
   Id_00034[Li_FFFCC] = Ld_FFE88;
   func_1032(Time[Li_FFFCC], Ld_FFE88, false);
   if (Show_Confirmation_Dots) { 
   Gd_00087 = High[Li_FFFCC];
   Gi_00088 = Li_FFFCC;
   if (Li_FFFCC >= 0 && Li_FFFCC < Bars) { 
   Gi_00089 = Ii_001C0 % 50;
   tmp_str0000F = "MonsterDot_" + IntegerToString(Gi_00089, 0, 32);
   tmp_str0000E = tmp_str0000F;
   ObjectDelete(tmp_str0000E);
   ObjectCreate(0, tmp_str0000E, OBJ_ARROW, 0, Time[Li_FFFCC], (((Arrow_Distance * 0.5) * _Point) + Gd_00087));
   ObjectSetInteger(0, tmp_str0000E, 14, 159);
   ObjectSetInteger(0, tmp_str0000E, 6, 16711935);
   ObjectSetInteger(0, tmp_str0000E, 8, 2);
   ObjectSetInteger(0, tmp_str0000E, 9, 0);
   ObjectSetInteger(0, tmp_str0000E, 1000, 0);
   ObjectSetString(0, tmp_str0000E, 206, "SMC Confirmation");
   Ii_001C0 = Ii_001C0 + 1;
   }} 
   Ii_001C4 = -1;
   Ii_001C8 = Li_FFFCC;
   Id_001E0 = Close[Li_FFFCC];
   Id_001D0 = High[Li_FFFCC];
   if (Li_FFF28 >= 1) { 
   Id_001D8 = Ld_FFF9C[0];
   } 
   else { 
   Gi_0008E = iLowest(NULL, 0, 1, 30, Li_FFFCC);
   Id_001D8 = Low[Gi_0008E];
   } 
   if (Li_FFFCC == ConfirmationDelay) { 
   Gl_00090 = Time[Li_FFFCC];
   tmp_str0000F = "SELL";
   if (Gl_00090 > Il_00090) { 
   Il_00090 = Gl_00090;
   if (Enable_Alerts) { 
   tmp_str00010 = func_1020(_Period);
   tmp_str00011 = TimeToString(Gl_00090, 3);
   tmp_str00012 = DoubleToString(Close[Li_FFFCC], Ii_00080);
   tmp_str00013 = StringFormat("?? MONSTER ARROWS V2 ??\n\n%s SIGNAL!\n\nPair: %s\nTimeframe: %s\nPrice: %s\nTime: %s\n\n? HTF Confirmed\n? SMC Confirmed", tmp_str0000F, _Symbol, tmp_str00010, tmp_str00012, tmp_str00011);
   tmp_str00014 = StringFormat("Monster V2: %s %s %s @ %s", tmp_str0000F, _Symbol, tmp_str00010, tmp_str00012);
   if (Alert_Sound) { 
   PlaySound(Sound_File);
   } 
   if (Alert_Popup) { 
   Alert(tmp_str00013);
   } 
   if (Alert_Push) { 
   SendNotification(tmp_str00014);
   } 
   if (Alert_Email) { 
   tmp_str00015 = StringFormat("Monster V2 %s - %s %s", tmp_str0000F, _Symbol, tmp_str00010);
   SendMail(tmp_str00015, tmp_str00013);
   } 
   Print("?? MONSTER V2: ", tmp_str00014);
   }}}} 
   Id_00198 = Id_00188;
   Id_00188 = Ld_FFFB8;
   Ii_00190 = Li_FFFCC;
   }} 
   ArrayFree(Li_FFF60);
   ArrayFree(Ld_FFF9C);
   }}} 
   Li_FFFCC = Li_FFFCC - 1;
   } while (Li_FFFCC >= ConfirmationDelay); 
   } 
   if (Auto_Draw_TP && Ii_001C8 >= 0 && Ii_001C8 < Bars) { 
   if (Ii_001C4 == 1 && (Id_001D0 > 0) && (Id_001D8 > 0)) { 
   func_1016(Id_001D8, Id_001D0, Time[Ii_001C8], true);
   } 
   else { 
   if (Ii_001C4 == -1 && (Id_001D0 > 0) && (Id_001D8 > 0)) { 
   func_1016(Id_001D0, Id_001D8, Time[Ii_001C8], false);
   }}} 
   if (Show_Dashboard == false) return rates_total; 
   func_1022(Ii_001C4);
   
   Li_FFFFC = rates_total;
   
   return Li_FFFFC;
}

void func_1009()
{
   int Li_FFFFC;
   int Li_FFFF8;
   int Li_FFFF4;
   int Li_FFFF0;
   int Li_FFFEC;
   int Li_FFFE8;

   Ii_001C4 = 0;
   Ii_001C8 = -1;
   Id_001D0 = 0;
   Id_001D8 = 0;
   Id_001E0 = 0;
   if (Bars < 100) return; 
   Gi_00000 = Bars - 50;
   if (Gi_00000 <= 500) { 
   } 
   else { 
   Gi_00000 = 500;
   } 
   Li_FFFFC = Gi_00000;
   Li_FFFF8 = ConfirmationDelay;
   if (ConfirmationDelay >= Gi_00000) return; 
   do { 
   if ((Id_00000[Li_FFFF8] != 2147483647) && (Id_00000[Li_FFFF8] != 0)) { 
   Ii_001C4 = 1;
   Ii_001C8 = Li_FFFF8;
   Id_001E0 = Close[Li_FFFF8];
   Id_001D8 = Low[Li_FFFF8];
   Gi_00004 = Bars - Li_FFFF8;
   Gi_00004 = Gi_00004 - 1;
   if (Gi_00004 <= 50) { 
   } 
   else { 
   Gi_00004 = 50;
   } 
   Li_FFFF4 = Gi_00004;
   if (Gi_00004 > 0) { 
   Li_FFFF0 = iHighest(NULL, 0, 2, Gi_00004, Li_FFFF8);
   if (Li_FFFF0 >= 0 && Li_FFFF0 < Bars) { 
   Id_001D0 = High[Li_FFFF0];
   }} 
   if ((Id_001D0 > Id_001D8)) return; 
   Id_001D0 = ((_Point * 100) + Id_001D8);
   return ;
   } 
   if ((Id_00034[Li_FFFF8] != 2147483647) && (Id_00034[Li_FFFF8] != 0)) { 
   Ii_001C4 = -1;
   Ii_001C8 = Li_FFFF8;
   Id_001E0 = Close[Li_FFFF8];
   Id_001D0 = High[Li_FFFF8];
   Gi_00009 = Bars - Li_FFFF8;
   Gi_00009 = Gi_00009 - 1;
   if (Gi_00009 <= 50) { 
   } 
   else { 
   Gi_00009 = 50;
   } 
   Li_FFFEC = Gi_00009;
   if (Gi_00009 > 0) { 
   Li_FFFE8 = iLowest(NULL, 0, 1, Gi_00009, Li_FFFF8);
   if (Li_FFFE8 >= 0 && Li_FFFE8 < Bars) { 
   Id_001D8 = Low[Li_FFFE8];
   }} 
   if ((Id_001D8 < Id_001D0)) return; 
   Gd_0000A = (_Point * 100);
   Id_001D8 = (Id_001D0 - Gd_0000A);
   return ;
   } 
   Li_FFFF8 = Li_FFFF8 + 1;
   } while (Li_FFFF8 < Li_FFFFC); 
   
}

void func_1014(int Fa_i_00, int Fa_i_01, double Fa_d_02, bool FuncArg_Boolean_00000003)
{
   string tmp_str00000;
   string tmp_str00001;
   string Ls_FFFF0;
   string Ls_FFFE0;

   if (ShowSMCVisuals == false) return; 
   if (Fa_i_00 < 0) return; 
   if (Fa_i_00 >= Bars) return; 
   if (Fa_i_01 < 0) return; 
   if (Fa_i_01 >= Bars) return; 
   Ls_FFFF0 = "MonsterHunt_" + IntegerToString(Ii_001BC % 50, 0, 32);
   ObjectDelete(Ls_FFFF0);
   ObjectCreate(0, Ls_FFFF0, OBJ_TREND, 0, Time[Fa_i_00], Fa_d_02, Time[Fa_i_01], Fa_d_02);
   if (FuncArg_Boolean_00000003) { 
   Gi_00003 = Hunt_Buy_Color;
   } 
   else { 
   Gi_00003 = Hunt_Sell_Color;
   } 
   ObjectSetInteger(0, Ls_FFFF0, 6, Gi_00003);
   ObjectSetInteger(0, Ls_FFFF0, 7, 1);
   ObjectSetInteger(0, Ls_FFFF0, 8, 2);
   ObjectSetInteger(0, Ls_FFFF0, 10, 0);
   ObjectSetInteger(0, Ls_FFFF0, 9, 0);
   ObjectSetInteger(0, Ls_FFFF0, 1000, 0);
   if (FuncArg_Boolean_00000003) { 
   tmp_str00000 = "Liquidity Sweep (Buy)";
   } 
   else { 
   tmp_str00000 = "Liquidity Sweep (Sell)";
   } 
   ObjectSetString(0, Ls_FFFF0, 206, tmp_str00000);
   Ls_FFFE0 = Ls_FFFF0 + "_Lbl";
   ObjectDelete(Ls_FFFE0);
   ObjectCreate(0, Ls_FFFE0, OBJ_TEXT, 0, Time[Fa_i_00], Fa_d_02);
   if (FuncArg_Boolean_00000003) { 
   tmp_str00001 = "? HUNT";
   } 
   else { 
   tmp_str00001 = "? HUNT";
   } 
   ObjectSetString(0, Ls_FFFE0, 999, tmp_str00001);
   if (FuncArg_Boolean_00000003) { 
   Gi_00004 = Hunt_Buy_Color;
   } 
   else { 
   Gi_00004 = Hunt_Sell_Color;
   } 
   ObjectSetInteger(0, Ls_FFFE0, 6, Gi_00004);
   ObjectSetInteger(0, Ls_FFFE0, 100, 7);
   ObjectSetString(0, Ls_FFFE0, 1001, "Arial Bold");
   Ii_001BC = Ii_001BC + 1;
   
}

void func_1016(double Fa_d_00, double Fa_d_01, long Fa_l_02, bool FuncArg_Boolean_00000003)
{
   string tmp_str00000;
   string tmp_str00001;
   string tmp_str00002;
   string tmp_str00003;
   double Ld_FFFF8;
   double Ld_FFFF0;
   double Ld_FFFE8;
   double Ld_FFFE0;
   long Ll_FFFD8;

   if (Fa_d_00 <= 0) return; 
   if (Fa_d_01 <= 0) return; 
   if (Fa_l_02 <= 0) return; 
   Ld_FFFF8 = fabs((Fa_d_01 - Fa_d_00));
   if (Ld_FFFF8 < (_Point * 10)) return; 
   Ld_FFFF0 = 0;
   Ld_FFFE8 = 0;
   Ld_FFFE0 = 0;
   if (FuncArg_Boolean_00000003) { 
   Ld_FFFF0 = ((Ld_FFFF8 * 0.5) + Fa_d_00);
   Ld_FFFE8 = (Fa_d_00 + Ld_FFFF8);
   Ld_FFFE0 = ((Ld_FFFF8 * 1.618) + Fa_d_00);
   } 
   else { 
   Gd_00000 = (Ld_FFFF8 * 0.5);
   Ld_FFFF0 = (Fa_d_00 - Gd_00000);
   Ld_FFFE8 = (Fa_d_00 - Ld_FFFF8);
   Gd_00000 = (Ld_FFFF8 * 1.618);
   Ld_FFFE0 = (Fa_d_00 - Gd_00000);
   } 
   Gi_00000 = _Period * 60;
   Gi_00000 = Gi_00000 * 100;
   Gl_00000 = Gi_00000;
   Ll_FFFD8 = Fa_l_02 + Gl_00000;
   ObjectDelete("Monster_TP_Entry");
   ObjectDelete("Monster_TP1");
   ObjectDelete("Monster_TP2");
   ObjectDelete("Monster_TP3");
   ObjectDelete("Monster_TP_Entry_Label");
   ObjectDelete("Monster_TP1_Label");
   ObjectDelete("Monster_TP2_Label");
   ObjectDelete("Monster_TP3_Label");
   ObjectCreate(0, "Monster_TP_Entry", OBJ_TREND, 0, Fa_l_02, Fa_d_00, Ll_FFFD8, Fa_d_00);
   ObjectSetInteger(0, "Monster_TP_Entry", 6, TP_Entry_Color);
   ObjectSetInteger(0, "Monster_TP_Entry", 7, 0);
   ObjectSetInteger(0, "Monster_TP_Entry", 8, 2);
   ObjectSetInteger(0, "Monster_TP_Entry", 1004, 1);
   ObjectSetInteger(0, "Monster_TP_Entry", 9, 1);
   ObjectCreate(0, "Monster_TP_Entry_Label", OBJ_TEXT, 0, Ll_FFFD8, Fa_d_00);
   tmp_str00000 = "? ENTRY - " + DoubleToString(Fa_d_00, Ii_00080);
   ObjectSetString(0, "Monster_TP_Entry_Label", 999, tmp_str00000);
   ObjectSetInteger(0, "Monster_TP_Entry_Label", 6, TP_Entry_Color);
   ObjectSetInteger(0, "Monster_TP_Entry_Label", 100, 9);
   ObjectSetString(0, "Monster_TP_Entry_Label", 1001, "Arial Bold");
   ObjectCreate(0, "Monster_TP1", OBJ_TREND, 0, Fa_l_02, Ld_FFFF0, Ll_FFFD8, Ld_FFFF0);
   ObjectSetInteger(0, "Monster_TP1", 6, TP1_Color);
   ObjectSetInteger(0, "Monster_TP1", 7, 1);
   ObjectSetInteger(0, "Monster_TP1", 8, 1);
   ObjectSetInteger(0, "Monster_TP1", 1004, 1);
   ObjectSetInteger(0, "Monster_TP1", 9, 1);
   ObjectCreate(0, "Monster_TP1_Label", OBJ_TEXT, 0, Ll_FFFD8, Ld_FFFF0);
   tmp_str00001 = "TP1 (50%) - " + DoubleToString(Ld_FFFF0, Ii_00080);
   ObjectSetString(0, "Monster_TP1_Label", 999, tmp_str00001);
   ObjectSetInteger(0, "Monster_TP1_Label", 6, TP1_Color);
   ObjectSetInteger(0, "Monster_TP1_Label", 100, 8);
   ObjectSetString(0, "Monster_TP1_Label", 1001, "Arial");
   ObjectCreate(0, "Monster_TP2", OBJ_TREND, 0, Fa_l_02, Ld_FFFE8, Ll_FFFD8, Ld_FFFE8);
   ObjectSetInteger(0, "Monster_TP2", 6, TP2_Color);
   ObjectSetInteger(0, "Monster_TP2", 7, 1);
   ObjectSetInteger(0, "Monster_TP2", 8, 1);
   ObjectSetInteger(0, "Monster_TP2", 1004, 1);
   ObjectSetInteger(0, "Monster_TP2", 9, 1);
   ObjectCreate(0, "Monster_TP2_Label", OBJ_TEXT, 0, Ll_FFFD8, Ld_FFFE8);
   tmp_str00002 = "TP2 (100%) - " + DoubleToString(Ld_FFFE8, Ii_00080);
   ObjectSetString(0, "Monster_TP2_Label", 999, tmp_str00002);
   ObjectSetInteger(0, "Monster_TP2_Label", 6, TP2_Color);
   ObjectSetInteger(0, "Monster_TP2_Label", 100, 8);
   ObjectSetString(0, "Monster_TP2_Label", 1001, "Arial");
   ObjectCreate(0, "Monster_TP3", OBJ_TREND, 0, Fa_l_02, Ld_FFFE0, Ll_FFFD8, Ld_FFFE0);
   ObjectSetInteger(0, "Monster_TP3", 6, TP3_Color);
   ObjectSetInteger(0, "Monster_TP3", 7, 1);
   ObjectSetInteger(0, "Monster_TP3", 8, 1);
   ObjectSetInteger(0, "Monster_TP3", 1004, 1);
   ObjectSetInteger(0, "Monster_TP3", 9, 1);
   ObjectCreate(0, "Monster_TP3_Label", OBJ_TEXT, 0, Ll_FFFD8, Ld_FFFE0);
   tmp_str00003 = "TP3 (161.8%) - " + DoubleToString(Ld_FFFE0, Ii_00080);
   ObjectSetString(0, "Monster_TP3_Label", 999, tmp_str00003);
   ObjectSetInteger(0, "Monster_TP3_Label", 6, TP3_Color);
   ObjectSetInteger(0, "Monster_TP3_Label", 100, 8);
   ObjectSetString(0, "Monster_TP3_Label", 1001, "Arial");
   WindowRedraw();
   
}

int func_1017(int Fa_i_00)
{
   int Li_FFFFC = Fa_i_00;

   returned_i = Fa_i_00;
   if (returned_i < 1) return Fa_i_00; 
   if (returned_i > 10080) return Fa_i_00; 
   if (returned_i == 1) Li_FFFFC = 5;
   if (returned_i == 5) Li_FFFFC = 15;
   if (returned_i == 15) Li_FFFFC = 30;
   if (returned_i == 30) Li_FFFFC = 60;
   if (returned_i == 60) Li_FFFFC = 240;
   if (returned_i == 240) Li_FFFFC = 1440;
   if (returned_i == 1440) Li_FFFFC = 10080;
   if (returned_i == 10080) Li_FFFFC = 43200;
   return Li_FFFFC;
   
   Li_FFFFC = Fa_i_00;
   
   return Li_FFFFC;
}

int func_1018(int Fa_i_00)
{
   int Li_FFFFC = Fa_i_00;

   returned_i = Fa_i_00;
   if (returned_i < 1) return Fa_i_00; 
   if (returned_i > 10080) return Fa_i_00; 
   if (returned_i == 1) Li_FFFFC = 15;
   if (returned_i == 5) Li_FFFFC = 30;
   if (returned_i == 15) Li_FFFFC = 60;
   if (returned_i == 30) Li_FFFFC = 240;
   if (returned_i == 60) Li_FFFFC = 1440;
   if (returned_i == 240) Li_FFFFC = 10080;
   if (returned_i == 1440) Li_FFFFC = 43200;
   if (returned_i == 10080) Li_FFFFC = 43200;
   return Li_FFFFC;
   
   Li_FFFFC = Fa_i_00;
   
   return Li_FFFFC;
}

string func_1020(int Fa_i_00)
{
   string tmp_str00000;

   returned_i = Fa_i_00;
   if (returned_i < 1) return "?"; 
   if (returned_i > 43200) return "?"; 
   if (returned_i == 1) tmp_str00000 = "M1";
   if (returned_i == 5) tmp_str00000 = "M5";
   if (returned_i == 15) tmp_str00000 = "M15";
   if (returned_i == 30) tmp_str00000 = "M30";
   if (returned_i == 60) tmp_str00000 = "H1";
   if (returned_i == 240) tmp_str00000 = "H4";
   if (returned_i == 1440) tmp_str00000 = "D1";
   if (returned_i == 10080) tmp_str00000 = "W1";
   if (returned_i == 43200) tmp_str00000 = "MN1";
   return tmp_str00000;
   
   tmp_str00000 = "?";
   
   return tmp_str00000;
}

void func_1021()
{
   string tmp_str00000;
   string tmp_str00001;
   string tmp_str00002;
   string tmp_str00003;
   string tmp_str00006;
   string tmp_str00007;
   string tmp_str00008;
   string tmp_str00009;
   string tmp_str0000A;
   string tmp_str0000B;
   string tmp_str0000C;
   string tmp_str0000D;
   string tmp_str0000E;
   string tmp_str0000F;
   string tmp_str00010;
   string tmp_str00011;
   string tmp_str00012;
   string tmp_str00013;
   string tmp_str00014;
   string tmp_str00015;
   string tmp_str00016;
   string tmp_str00017;
   string tmp_str00018;
   string tmp_str00019;
   string tmp_str0001A;
   string tmp_str0001B;
   string tmp_str0001C;
   string tmp_str0001D;
   string tmp_str0001E;
   string tmp_str0001F;
   string tmp_str00020;
   string tmp_str00021;
   string tmp_str00022;
   string tmp_str00023;
   string tmp_str00024;
   string tmp_str00025;
   int Li_FFFFC;
   int Li_FFFF8;
   int Li_FFFF4;

   Li_FFFFC = Dash_X_Offset;
   Li_FFFF8 = Dash_Y_Offset;
   Li_FFFF4 = 18;
   Gb_00000 = true;
   Gi_00001 = Dash_Title_Color;
   Gi_00002 = Dash_Y_Offset;
   Gi_00003 = Dash_X_Offset;
   Gi_00004 = 12;
   tmp_str00000 = "MONSTER ARROWS v2.0";
   tmp_str00001 = "M_Title";
   if (ObjectFind(tmp_str00001) < 0) { 
   ObjectCreate(0, tmp_str00001, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00001, 101, 0);
   ObjectSetInteger(0, tmp_str00001, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00001, 999, tmp_str00000);
   if (Gb_00000) { 
   tmp_str00002 = "Arial Bold";
   } 
   else { 
   tmp_str00002 = "Arial";
   } 
   ObjectSetString(0, tmp_str00001, 1001, tmp_str00002);
   ObjectSetInteger(0, tmp_str00001, 100, Gi_00004);
   ObjectSetInteger(0, tmp_str00001, 102, Gi_00003);
   ObjectSetInteger(0, tmp_str00001, 103, Gi_00002);
   ObjectSetInteger(0, tmp_str00001, 6, Gi_00001);
   Li_FFFF8 = Li_FFFF8 + 25;
   Gb_00005 = true;
   Gi_00006 = 16777215;
   Gi_00007 = Li_FFFF8;
   Gi_00008 = Li_FFFFC;
   Gi_00009 = 10;
   tmp_str00003 = "Checking License...";
   /*
   tmp_str00004 = "M_License";
   if (ObjectFind(tmp_str00004) < 0) { 
   ObjectCreate(0, tmp_str00004, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00004, 101, 0);
   ObjectSetInteger(0, tmp_str00004, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00004, 999, tmp_str00003);
   if (Gb_00005) { 
   tmp_str00005 = "Arial Bold";
   } 
   else { 
   tmp_str00005 = "Arial";
   } 
   ObjectSetString(0, tmp_str00004, 1001, tmp_str00005);
   ObjectSetInteger(0, tmp_str00004, 100, Gi_00009);
   ObjectSetInteger(0, tmp_str00004, 102, Gi_00008);
   ObjectSetInteger(0, tmp_str00004, 103, Gi_00007);
   ObjectSetInteger(0, tmp_str00004, 6, Gi_00006);
   */
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   Gb_0000A = false;
   Gi_0000B = Dash_Text_Color;
   Gi_0000C = Li_FFFF8;
   Gi_0000D = Li_FFFFC;
   Gi_0000E = 9;
   tmp_str00006 = "";
   tmp_str00007 = "M_HTF";
   if (ObjectFind(tmp_str00007) < 0) { 
   ObjectCreate(0, tmp_str00007, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00007, 101, 0);
   ObjectSetInteger(0, tmp_str00007, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00007, 999, tmp_str00006);
   if (Gb_0000A) { 
   tmp_str00008 = "Arial Bold";
   } 
   else { 
   tmp_str00008 = "Arial";
   } 
   ObjectSetString(0, tmp_str00007, 1001, tmp_str00008);
   ObjectSetInteger(0, tmp_str00007, 100, Gi_0000E);
   ObjectSetInteger(0, tmp_str00007, 102, Gi_0000D);
   ObjectSetInteger(0, tmp_str00007, 103, Gi_0000C);
   ObjectSetInteger(0, tmp_str00007, 6, Gi_0000B);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   Gb_0000F = false;
   Gi_00010 = Dash_Text_Color;
   Gi_00011 = Li_FFFF8;
   Gi_00012 = Li_FFFFC;
   Gi_00013 = 9;
   tmp_str00009 = "";
   tmp_str0000A = "M_SMC";
   if (ObjectFind(tmp_str0000A) < 0) { 
   ObjectCreate(0, tmp_str0000A, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str0000A, 101, 0);
   ObjectSetInteger(0, tmp_str0000A, 1011, 0);
   } 
   ObjectSetString(0, tmp_str0000A, 999, tmp_str00009);
   if (Gb_0000F) { 
   tmp_str0000B = "Arial Bold";
   } 
   else { 
   tmp_str0000B = "Arial";
   } 
   ObjectSetString(0, tmp_str0000A, 1001, tmp_str0000B);
   ObjectSetInteger(0, tmp_str0000A, 100, Gi_00013);
   ObjectSetInteger(0, tmp_str0000A, 102, Gi_00012);
   ObjectSetInteger(0, tmp_str0000A, 103, Gi_00011);
   ObjectSetInteger(0, tmp_str0000A, 6, Gi_00010);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   Gb_00014 = false;
   Gi_00015 = Dash_Text_Color;
   Gi_00016 = Li_FFFF8;
   Gi_00017 = Li_FFFFC;
   Gi_00018 = 9;
   tmp_str0000C = "";
   tmp_str0000D = "M_State";
   if (ObjectFind(tmp_str0000D) < 0) { 
   ObjectCreate(0, tmp_str0000D, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str0000D, 101, 0);
   ObjectSetInteger(0, tmp_str0000D, 1011, 0);
   } 
   ObjectSetString(0, tmp_str0000D, 999, tmp_str0000C);
   if (Gb_00014) { 
   tmp_str0000E = "Arial Bold";
   } 
   else { 
   tmp_str0000E = "Arial";
   } 
   ObjectSetString(0, tmp_str0000D, 1001, tmp_str0000E);
   ObjectSetInteger(0, tmp_str0000D, 100, Gi_00018);
   ObjectSetInteger(0, tmp_str0000D, 102, Gi_00017);
   ObjectSetInteger(0, tmp_str0000D, 103, Gi_00016);
   ObjectSetInteger(0, tmp_str0000D, 6, Gi_00015);
   Li_FFFF8 = Li_FFFF8 + 25;
   Gb_00019 = true;
   Gi_0001A = Dash_Title_Color;
   Gi_0001B = Li_FFFF8;
   Gi_0001C = Li_FFFFC;
   Gi_0001D = 10;
   tmp_str0000F = "-- OVERALL DIRECTION --";
   tmp_str00010 = "M_Ov_Head";
   if (ObjectFind(tmp_str00010) < 0) { 
   ObjectCreate(0, tmp_str00010, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00010, 101, 0);
   ObjectSetInteger(0, tmp_str00010, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00010, 999, tmp_str0000F);
   if (Gb_00019) { 
   tmp_str00011 = "Arial Bold";
   } 
   else { 
   tmp_str00011 = "Arial";
   } 
   ObjectSetString(0, tmp_str00010, 1001, tmp_str00011);
   ObjectSetInteger(0, tmp_str00010, 100, Gi_0001D);
   ObjectSetInteger(0, tmp_str00010, 102, Gi_0001C);
   ObjectSetInteger(0, tmp_str00010, 103, Gi_0001B);
   ObjectSetInteger(0, tmp_str00010, 6, Gi_0001A);
   Li_FFFF8 = Li_FFFF8 + 20;
   Gb_0001E = true;
   Gi_0001F = 8421504;
   Gi_00020 = Li_FFFF8;
   Gi_00021 = Li_FFFFC + 10;
   Gi_00022 = 12;
   tmp_str00012 = "CALCULATING...";
   tmp_str00013 = "M_Ov_Val";
   if (ObjectFind(tmp_str00013) < 0) { 
   ObjectCreate(0, tmp_str00013, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00013, 101, 0);
   ObjectSetInteger(0, tmp_str00013, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00013, 999, tmp_str00012);
   if (Gb_0001E) { 
   tmp_str00014 = "Arial Bold";
   } 
   else { 
   tmp_str00014 = "Arial";
   } 
   ObjectSetString(0, tmp_str00013, 1001, tmp_str00014);
   ObjectSetInteger(0, tmp_str00013, 100, Gi_00022);
   ObjectSetInteger(0, tmp_str00013, 102, Gi_00021);
   ObjectSetInteger(0, tmp_str00013, 103, Gi_00020);
   ObjectSetInteger(0, tmp_str00013, 6, Gi_0001F);
   Li_FFFF8 = Li_FFFF8 + 25;
   Gb_00023 = true;
   Gi_00024 = Dash_Title_Color;
   Gi_00025 = Li_FFFF8;
   Gi_00026 = Li_FFFFC;
   Gi_00027 = 9;
   tmp_str00015 = "-- TIMEFRAME TRENDS --";
   tmp_str00016 = "M_Tr_Head";
   if (ObjectFind(tmp_str00016) < 0) { 
   ObjectCreate(0, tmp_str00016, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00016, 101, 0);
   ObjectSetInteger(0, tmp_str00016, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00016, 999, tmp_str00015);
   if (Gb_00023) { 
   tmp_str00017 = "Arial Bold";
   } 
   else { 
   tmp_str00017 = "Arial";
   } 
   ObjectSetString(0, tmp_str00016, 1001, tmp_str00017);
   ObjectSetInteger(0, tmp_str00016, 100, Gi_00027);
   ObjectSetInteger(0, tmp_str00016, 102, Gi_00026);
   ObjectSetInteger(0, tmp_str00016, 103, Gi_00025);
   ObjectSetInteger(0, tmp_str00016, 6, Gi_00024);
   Li_FFFF8 = Li_FFFF8 + 20;
   tmp_str00018 = "M1: ";
   tmp_str00019 = "M_Tr_M1";
   func_1024(tmp_str00019, tmp_str00018, Li_FFFFC, Li_FFFF8);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   tmp_str0001A = "M5: ";
   tmp_str0001B = "M_Tr_M5";
   func_1024(tmp_str0001B, tmp_str0001A, Li_FFFFC, Li_FFFF8);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   tmp_str0001C = "M15: ";
   tmp_str0001D = "M_Tr_M15";
   func_1024(tmp_str0001D, tmp_str0001C, Li_FFFFC, Li_FFFF8);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   tmp_str0001E = "M30: ";
   tmp_str0001F = "M_Tr_M30";
   func_1024(tmp_str0001F, tmp_str0001E, Li_FFFFC, Li_FFFF8);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   tmp_str00020 = "H1: ";
   tmp_str00021 = "M_Tr_H1";
   func_1024(tmp_str00021, tmp_str00020, Li_FFFFC, Li_FFFF8);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   tmp_str00022 = "H4: ";
   tmp_str00023 = "M_Tr_H4";
   func_1024(tmp_str00023, tmp_str00022, Li_FFFFC, Li_FFFF8);
   Li_FFFF8 = Li_FFFF8 + Li_FFFF4;
   tmp_str00024 = "D1: ";
   tmp_str00025 = "M_Tr_D1";
   func_1024(tmp_str00025, tmp_str00024, Li_FFFFC, Li_FFFF8);
}

void func_1022(int Fa_i_00)
{
   string tmp_str00000;
   string tmp_str00001;
   string tmp_str00002;
   string tmp_str00003;
   string tmp_str00004;
   string tmp_str00005;
   string tmp_str00006;
   string tmp_str00007;
   string tmp_str00008;
   string tmp_str00009;
   string tmp_str0000A;
   string tmp_str0000B;
   string tmp_str0000C;
   string tmp_str0000D;
   string tmp_str0000E;
   string tmp_str0000F;
   string tmp_str00010;
   string tmp_str00011;
   string tmp_str00012;
   string tmp_str00013;
   string tmp_str00014;
   string tmp_str00015;
   string tmp_str00016;
   string tmp_str00017;
   string tmp_str00018;
   string tmp_str00019;
   string tmp_str0001A;
   string tmp_str0001B;
   string tmp_str0001C;
   string tmp_str0001D;
   string tmp_str0001E;
   string tmp_str0001F;
   string tmp_str00020;
   string tmp_str00021;
   string tmp_str00022;
   string tmp_str00023;
   string tmp_str00024;
   string tmp_str00025;
   string tmp_str00026;
   string tmp_str00027;
   string tmp_str00028;
   string tmp_str00029;
   string tmp_str0002A;
   string tmp_str0002B;
   string tmp_str0002C;
   string tmp_str0002D;
   string tmp_str0002E;
   string tmp_str0002F;
   string tmp_str00030;
   string tmp_str00031;
   string tmp_str00032;
   string tmp_str00033;
   string tmp_str00034;
   string tmp_str00035;
   string tmp_str00036;
   string tmp_str00037;
   string tmp_str00038;
   int Li_FFFE0;
   int Li_FFFDC;
   string Ls_FFFD0;
   string Ls_FFFC0;
   string Ls_FFFB0;
   int Li_FFFAC;
   int Li_FFFA8;
   int Li_FFFA4;
   string Ls_FFF98;
   int Li_FFF94;

   /*
   Ll_FFFF8 = Il_001E8 - TimeCurrent();
   Gl_00000 = Ll_FFFF8 / 86400;
   Li_FFFF4 = (int)Gl_00000;
   tmp_str00000 = "Trial: " + IntegerToString(Li_FFFF4, 0, 32);
   tmp_str00000 = tmp_str00000 + " Days Left";
   Ls_FFFE8 = tmp_str00000;
   Li_FFFE4 = 65280;
   if (Li_FFFF4 < 5) { 
   Li_FFFE4 = 42495;
   } 
   if (Li_FFFF4 <= 0) { 
   Ls_FFFE8 = "EXPIRED - Contact @MeowForex1";
   Li_FFFE4 = 255;
   } 
   ObjectSetString(0, "M_License", 999, Ls_FFFE8);
   ObjectSetInteger(0, "M_License", 6, Li_FFFE4);
   */
   Li_FFFE0 = func_1017(_Period);
   Li_FFFDC = func_1018(_Period);
   tmp_str00000 = "HTF: " + func_1020(Li_FFFE0);
   tmp_str00000 = tmp_str00000 + " + ";
   tmp_str00000 = tmp_str00000 + func_1020(Li_FFFDC);
   if (RequireBothHTF) { 
   tmp_str00001 = " (BOTH)";
   } 
   else { 
   tmp_str00001 = " (ANY)";
   } 
   tmp_str00000 = tmp_str00000 + tmp_str00001;
   Ls_FFFD0 = tmp_str00000;
   ObjectSetString(0, "M_HTF", 999, Ls_FFFD0);
   Ls_FFFC0 = "SMC: ";
   if (EnableHunt) { 
   tmp_str00001 = "Hunt ? | ";
   } 
   else { 
   tmp_str00001 = "Hunt ? | ";
   } 
   Ls_FFFC0 = Ls_FFFC0 + tmp_str00001;
   if (EnableFVG) { 
   tmp_str00001 = "FVG ?";
   } 
   else { 
   tmp_str00001 = "FVG ?";
   } 
   Ls_FFFC0 = Ls_FFFC0 + tmp_str00001;
   ObjectSetString(0, "M_SMC", 999, Ls_FFFC0);
   Ls_FFFB0 = "Signal: Waiting...";
   Li_FFFAC = 12632256;
   if (Fa_i_00 == 1) { 
   Ls_FFFB0 = "? ACTIVE: BUY";
   Li_FFFAC = 65280;
   } 
   else { 
   if (Fa_i_00 == -1) { 
   Ls_FFFB0 = "? ACTIVE: SELL";
   Li_FFFAC = 255;
   }} 
   ObjectSetString(0, "M_State", 999, Ls_FFFB0);
   ObjectSetInteger(0, "M_State", 6, Li_FFFAC);
   Li_FFFA8 = 0;
   Li_FFFA4 = 0;
   tmp_str00001 = "M_Tr_M1";
   Gd_00000 = iMA(NULL, 1, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 1, 0);
   Gd_00001 = returned_double;
   tmp_str00002 = "—";
   Gi_00002 = 8421504;
   Gi_00003 = 0;
   if ((returned_double > 0) && (Gd_00000 > 0)) { 
   if ((returned_double > Gd_00000)) { 
   tmp_str00002 = "? UP";
   Gi_00002 = 65280;
   Gi_00003 = 1;
   } 
   else { 
   if ((Gd_00001 < Gd_00000)) { 
   tmp_str00002 = "? DN";
   Gi_00002 = 255;
   Gi_00003 = -1;
   }}} 
   tmp_str00003 = tmp_str00001 + "_Val";
   ObjectSetString(0, tmp_str00003, 999, tmp_str00002);
   tmp_str00004 = tmp_str00001 + "_Val";
   ObjectSetInteger(0, tmp_str00004, 6, Gi_00002);
   if (Gi_00003 == 1) { 
   Li_FFFA8 = Li_FFFA8 + 1;
   } 
   else { 
   tmp_str00005 = "M_Tr_M1";
   Gd_00004 = iMA(NULL, 1, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 1, 0);
   Gd_00005 = returned_double;
   tmp_str00006 = "—";
   Gi_00006 = 8421504;
   Gi_00007 = 0;
   if ((returned_double > 0) && (Gd_00004 > 0)) { 
   if ((returned_double > Gd_00004)) { 
   tmp_str00006 = "? UP";
   Gi_00006 = 65280;
   Gi_00007 = 1;
   } 
   else { 
   if ((Gd_00005 < Gd_00004)) { 
   tmp_str00006 = "? DN";
   Gi_00006 = 255;
   Gi_00007 = -1;
   }}} 
   tmp_str00007 = tmp_str00005 + "_Val";
   ObjectSetString(0, tmp_str00007, 999, tmp_str00006);
   tmp_str00008 = tmp_str00005 + "_Val";
   ObjectSetInteger(0, tmp_str00008, 6, Gi_00006);
   if (Gi_00007 == -1) { 
   Li_FFFA4 = Li_FFFA4 + 1;
   }} 
   tmp_str00009 = "M_Tr_M5";
   Gd_00008 = iMA(NULL, 5, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 5, 0);
   Gd_00009 = returned_double;
   tmp_str0000A = "—";
   Gi_0000A = 8421504;
   Gi_0000B = 0;
   if ((returned_double > 0) && (Gd_00008 > 0)) { 
   if ((returned_double > Gd_00008)) { 
   tmp_str0000A = "? UP";
   Gi_0000A = 65280;
   Gi_0000B = 1;
   } 
   else { 
   if ((Gd_00009 < Gd_00008)) { 
   tmp_str0000A = "? DN";
   Gi_0000A = 255;
   Gi_0000B = -1;
   }}} 
   tmp_str0000B = tmp_str00009 + "_Val";
   ObjectSetString(0, tmp_str0000B, 999, tmp_str0000A);
   tmp_str0000C = tmp_str00009 + "_Val";
   ObjectSetInteger(0, tmp_str0000C, 6, Gi_0000A);
   if (Gi_0000B == 1) { 
   Li_FFFA8 = Li_FFFA8 + 1;
   } 
   else { 
   tmp_str0000D = "M_Tr_M5";
   Gd_0000C = iMA(NULL, 5, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 5, 0);
   Gd_0000D = returned_double;
   tmp_str0000E = "—";
   Gi_0000E = 8421504;
   Gi_0000F = 0;
   if ((returned_double > 0) && (Gd_0000C > 0)) { 
   if ((returned_double > Gd_0000C)) { 
   tmp_str0000E = "? UP";
   Gi_0000E = 65280;
   Gi_0000F = 1;
   } 
   else { 
   if ((Gd_0000D < Gd_0000C)) { 
   tmp_str0000E = "? DN";
   Gi_0000E = 255;
   Gi_0000F = -1;
   }}} 
   tmp_str0000F = tmp_str0000D + "_Val";
   ObjectSetString(0, tmp_str0000F, 999, tmp_str0000E);
   tmp_str00010 = tmp_str0000D + "_Val";
   ObjectSetInteger(0, tmp_str00010, 6, Gi_0000E);
   if (Gi_0000F == -1) { 
   Li_FFFA4 = Li_FFFA4 + 1;
   }} 
   tmp_str00011 = "M_Tr_M15";
   Gd_00010 = iMA(NULL, 15, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 15, 0);
   Gd_00011 = returned_double;
   tmp_str00012 = "—";
   Gi_00012 = 8421504;
   Gi_00013 = 0;
   if ((returned_double > 0) && (Gd_00010 > 0)) { 
   if ((returned_double > Gd_00010)) { 
   tmp_str00012 = "? UP";
   Gi_00012 = 65280;
   Gi_00013 = 1;
   } 
   else { 
   if ((Gd_00011 < Gd_00010)) { 
   tmp_str00012 = "? DN";
   Gi_00012 = 255;
   Gi_00013 = -1;
   }}} 
   tmp_str00013 = tmp_str00011 + "_Val";
   ObjectSetString(0, tmp_str00013, 999, tmp_str00012);
   tmp_str00014 = tmp_str00011 + "_Val";
   ObjectSetInteger(0, tmp_str00014, 6, Gi_00012);
   if (Gi_00013 == 1) { 
   Li_FFFA8 = Li_FFFA8 + 1;
   } 
   else { 
   tmp_str00015 = "M_Tr_M15";
   Gd_00014 = iMA(NULL, 15, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 15, 0);
   Gd_00015 = returned_double;
   tmp_str00016 = "—";
   Gi_00016 = 8421504;
   Gi_00017 = 0;
   if ((returned_double > 0) && (Gd_00014 > 0)) { 
   if ((returned_double > Gd_00014)) { 
   tmp_str00016 = "? UP";
   Gi_00016 = 65280;
   Gi_00017 = 1;
   } 
   else { 
   if ((Gd_00015 < Gd_00014)) { 
   tmp_str00016 = "? DN";
   Gi_00016 = 255;
   Gi_00017 = -1;
   }}} 
   tmp_str00017 = tmp_str00015 + "_Val";
   ObjectSetString(0, tmp_str00017, 999, tmp_str00016);
   tmp_str00018 = tmp_str00015 + "_Val";
   ObjectSetInteger(0, tmp_str00018, 6, Gi_00016);
   if (Gi_00017 == -1) { 
   Li_FFFA4 = Li_FFFA4 + 1;
   }} 
   tmp_str00019 = "M_Tr_M30";
   Gd_00018 = iMA(NULL, 30, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 30, 0);
   Gd_00019 = returned_double;
   tmp_str0001A = "—";
   Gi_0001A = 8421504;
   Gi_0001B = 0;
   if ((returned_double > 0) && (Gd_00018 > 0)) { 
   if ((returned_double > Gd_00018)) { 
   tmp_str0001A = "? UP";
   Gi_0001A = 65280;
   Gi_0001B = 1;
   } 
   else { 
   if ((Gd_00019 < Gd_00018)) { 
   tmp_str0001A = "? DN";
   Gi_0001A = 255;
   Gi_0001B = -1;
   }}} 
   tmp_str0001B = tmp_str00019 + "_Val";
   ObjectSetString(0, tmp_str0001B, 999, tmp_str0001A);
   tmp_str0001C = tmp_str00019 + "_Val";
   ObjectSetInteger(0, tmp_str0001C, 6, Gi_0001A);
   if (Gi_0001B == 1) { 
   Li_FFFA8 = Li_FFFA8 + 1;
   } 
   else { 
   tmp_str0001D = "M_Tr_M30";
   Gd_0001C = iMA(NULL, 30, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 30, 0);
   Gd_0001D = returned_double;
   tmp_str0001E = "—";
   Gi_0001E = 8421504;
   Gi_0001F = 0;
   if ((returned_double > 0) && (Gd_0001C > 0)) { 
   if ((returned_double > Gd_0001C)) { 
   tmp_str0001E = "? UP";
   Gi_0001E = 65280;
   Gi_0001F = 1;
   } 
   else { 
   if ((Gd_0001D < Gd_0001C)) { 
   tmp_str0001E = "? DN";
   Gi_0001E = 255;
   Gi_0001F = -1;
   }}} 
   tmp_str0001F = tmp_str0001D + "_Val";
   ObjectSetString(0, tmp_str0001F, 999, tmp_str0001E);
   tmp_str00020 = tmp_str0001D + "_Val";
   ObjectSetInteger(0, tmp_str00020, 6, Gi_0001E);
   if (Gi_0001F == -1) { 
   Li_FFFA4 = Li_FFFA4 + 1;
   }} 
   tmp_str00021 = "M_Tr_H1";
   Gd_00020 = iMA(NULL, 60, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 60, 0);
   Gd_00021 = returned_double;
   tmp_str00022 = "—";
   Gi_00022 = 8421504;
   Gi_00023 = 0;
   if ((returned_double > 0) && (Gd_00020 > 0)) { 
   if ((returned_double > Gd_00020)) { 
   tmp_str00022 = "? UP";
   Gi_00022 = 65280;
   Gi_00023 = 1;
   } 
   else { 
   if ((Gd_00021 < Gd_00020)) { 
   tmp_str00022 = "? DN";
   Gi_00022 = 255;
   Gi_00023 = -1;
   }}} 
   tmp_str00023 = tmp_str00021 + "_Val";
   ObjectSetString(0, tmp_str00023, 999, tmp_str00022);
   tmp_str00024 = tmp_str00021 + "_Val";
   ObjectSetInteger(0, tmp_str00024, 6, Gi_00022);
   if (Gi_00023 == 1) { 
   Li_FFFA8 = Li_FFFA8 + 1;
   } 
   else { 
   tmp_str00025 = "M_Tr_H1";
   Gd_00024 = iMA(NULL, 60, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 60, 0);
   Gd_00025 = returned_double;
   tmp_str00026 = "—";
   Gi_00026 = 8421504;
   Gi_00027 = 0;
   if ((returned_double > 0) && (Gd_00024 > 0)) { 
   if ((returned_double > Gd_00024)) { 
   tmp_str00026 = "? UP";
   Gi_00026 = 65280;
   Gi_00027 = 1;
   } 
   else { 
   if ((Gd_00025 < Gd_00024)) { 
   tmp_str00026 = "? DN";
   Gi_00026 = 255;
   Gi_00027 = -1;
   }}} 
   tmp_str00027 = tmp_str00025 + "_Val";
   ObjectSetString(0, tmp_str00027, 999, tmp_str00026);
   tmp_str00028 = tmp_str00025 + "_Val";
   ObjectSetInteger(0, tmp_str00028, 6, Gi_00026);
   if (Gi_00027 == -1) { 
   Li_FFFA4 = Li_FFFA4 + 1;
   }} 
   tmp_str00029 = "M_Tr_H4";
   Gd_00028 = iMA(NULL, 240, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 240, 0);
   Gd_00029 = returned_double;
   tmp_str0002A = "—";
   Gi_0002A = 8421504;
   Gi_0002B = 0;
   if ((returned_double > 0) && (Gd_00028 > 0)) { 
   if ((returned_double > Gd_00028)) { 
   tmp_str0002A = "? UP";
   Gi_0002A = 65280;
   Gi_0002B = 1;
   } 
   else { 
   if ((Gd_00029 < Gd_00028)) { 
   tmp_str0002A = "? DN";
   Gi_0002A = 255;
   Gi_0002B = -1;
   }}} 
   tmp_str0002B = tmp_str00029 + "_Val";
   ObjectSetString(0, tmp_str0002B, 999, tmp_str0002A);
   tmp_str0002C = tmp_str00029 + "_Val";
   ObjectSetInteger(0, tmp_str0002C, 6, Gi_0002A);
   if (Gi_0002B == 1) { 
   Li_FFFA8 = Li_FFFA8 + 1;
   } 
   else { 
   tmp_str0002D = "M_Tr_H4";
   Gd_0002C = iMA(NULL, 240, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 240, 0);
   Gd_0002D = returned_double;
   tmp_str0002E = "—";
   Gi_0002E = 8421504;
   Gi_0002F = 0;
   if ((returned_double > 0) && (Gd_0002C > 0)) { 
   if ((returned_double > Gd_0002C)) { 
   tmp_str0002E = "? UP";
   Gi_0002E = 65280;
   Gi_0002F = 1;
   } 
   else { 
   if ((Gd_0002D < Gd_0002C)) { 
   tmp_str0002E = "? DN";
   Gi_0002E = 255;
   Gi_0002F = -1;
   }}} 
   tmp_str0002F = tmp_str0002D + "_Val";
   ObjectSetString(0, tmp_str0002F, 999, tmp_str0002E);
   tmp_str00030 = tmp_str0002D + "_Val";
   ObjectSetInteger(0, tmp_str00030, 6, Gi_0002E);
   if (Gi_0002F == -1) { 
   Li_FFFA4 = Li_FFFA4 + 1;
   }} 
   tmp_str00031 = "M_Tr_D1";
   Gd_00030 = iMA(NULL, 1440, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 1440, 0);
   Gd_00031 = returned_double;
   tmp_str00032 = "—";
   Gi_00032 = 8421504;
   Gi_00033 = 0;
   if ((returned_double > 0) && (Gd_00030 > 0)) { 
   if ((returned_double > Gd_00030)) { 
   tmp_str00032 = "? UP";
   Gi_00032 = 65280;
   Gi_00033 = 1;
   } 
   else { 
   if ((Gd_00031 < Gd_00030)) { 
   tmp_str00032 = "? DN";
   Gi_00032 = 255;
   Gi_00033 = -1;
   }}} 
   tmp_str00033 = tmp_str00031 + "_Val";
   ObjectSetString(0, tmp_str00033, 999, tmp_str00032);
   tmp_str00034 = tmp_str00031 + "_Val";
   ObjectSetInteger(0, tmp_str00034, 6, Gi_00032);
   if (Gi_00033 == 1) { 
   Li_FFFA8 = Li_FFFA8 + 1;
   } 
   else { 
   tmp_str00035 = "M_Tr_D1";
   Gd_00034 = iMA(NULL, 1440, 200, 0, 1, 0, 0);
   returned_double = iClose(NULL, 1440, 0);
   Gd_00035 = returned_double;
   tmp_str00036 = "—";
   Gi_00036 = 8421504;
   Gi_00037 = 0;
   if ((returned_double > 0) && (Gd_00034 > 0)) { 
   if ((returned_double > Gd_00034)) { 
   tmp_str00036 = "? UP";
   Gi_00036 = 65280;
   Gi_00037 = 1;
   } 
   else { 
   if ((Gd_00035 < Gd_00034)) { 
   tmp_str00036 = "? DN";
   Gi_00036 = 255;
   Gi_00037 = -1;
   }}} 
   tmp_str00037 = tmp_str00035 + "_Val";
   ObjectSetString(0, tmp_str00037, 999, tmp_str00036);
   tmp_str00038 = tmp_str00035 + "_Val";
   ObjectSetInteger(0, tmp_str00038, 6, Gi_00036);
   if (Gi_00037 == -1) { 
   Li_FFFA4 = Li_FFFA4 + 1;
   }} 
   Ls_FFF98 = "RANGING / MIXED";
   Li_FFF94 = 8421504;
   if (Li_FFFA8 >= 5) { 
   Ls_FFF98 = "? STRONG BUY";
   Li_FFF94 = 65280;
   } 
   else { 
   if (Li_FFFA8 >= 4) { 
   Ls_FFF98 = "? BUY BIAS";
   Li_FFF94 = 32768;
   } 
   else { 
   if (Li_FFFA4 >= 5) { 
   Ls_FFF98 = "? STRONG SELL";
   Li_FFF94 = 255;
   } 
   else { 
   if (Li_FFFA4 >= 4) { 
   Ls_FFF98 = "? SELL BIAS";
   Li_FFF94 = 17919;
   }}}} 
   ObjectSetString(0, "M_Ov_Val", 999, Ls_FFF98);
   ObjectSetInteger(0, "M_Ov_Val", 6, Li_FFF94);
}

void func_1024(string Fa_s_00, string Fa_s_01, int Fa_i_02, int Fa_i_03)
{
   string tmp_str00000;
   string tmp_str00001;
   string tmp_str00002;
   string tmp_str00003;
   string tmp_str00004;
   string tmp_str00005;

   Gb_00000 = false;
   Gi_00001 = Dash_Text_Color;
   Gi_00002 = Fa_i_03;
   Gi_00003 = Fa_i_02;
   Gi_00004 = 9;
   tmp_str00000 = Fa_s_01;
   tmp_str00001 = Fa_s_00 + "_Lbl";
   if (ObjectFind(tmp_str00001) < 0) { 
   ObjectCreate(0, tmp_str00001, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00001, 101, 0);
   ObjectSetInteger(0, tmp_str00001, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00001, 999, tmp_str00000);
   if (Gb_00000) { 
   tmp_str00002 = "Arial Bold";
   } 
   else { 
   tmp_str00002 = "Arial";
   } 
   ObjectSetString(0, tmp_str00001, 1001, tmp_str00002);
   ObjectSetInteger(0, tmp_str00001, 100, Gi_00004);
   ObjectSetInteger(0, tmp_str00001, 102, Gi_00003);
   ObjectSetInteger(0, tmp_str00001, 103, Gi_00002);
   ObjectSetInteger(0, tmp_str00001, 6, Gi_00001);
   Gb_00005 = true;
   Gi_00006 = 8421504;
   Gi_00007 = Fa_i_03;
   Gi_00008 = Fa_i_02 + 35;
   Gi_00009 = 9;
   tmp_str00003 = "...";
   tmp_str00004 = Fa_s_00 + "_Val";
   if (ObjectFind(tmp_str00004) < 0) { 
   ObjectCreate(0, tmp_str00004, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tmp_str00004, 101, 0);
   ObjectSetInteger(0, tmp_str00004, 1011, 0);
   } 
   ObjectSetString(0, tmp_str00004, 999, tmp_str00003);
   if (Gb_00005) { 
   tmp_str00005 = "Arial Bold";
   } 
   else { 
   tmp_str00005 = "Arial";
   } 
   ObjectSetString(0, tmp_str00004, 1001, tmp_str00005);
   ObjectSetInteger(0, tmp_str00004, 100, Gi_00009);
   ObjectSetInteger(0, tmp_str00004, 102, Gi_00008);
   ObjectSetInteger(0, tmp_str00004, 103, Gi_00007);
   ObjectSetInteger(0, tmp_str00004, 6, Gi_00006);
}

void func_1032(long Fa_l_00, double Fa_d_01, bool FuncArg_Boolean_00000002)
{
   string tmp_str00000;
   string tmp_str00001;
   string tmp_str00002;

   if (FuncArg_Boolean_00000002) { 
   if (Ii_0017C >= 10000) return; 
   Gl_00000 = Fa_l_00;
   Gi_00001 = 0;
   Gb_00003 = false;
   if (Ii_0017C > 0) {
   do { 
   if (Il_000AC[Gi_00001] == Gl_00000) {
   Gb_00003 = true;
   break;
   }
   Gi_00001 = Gi_00001 + 1;
   } while (Gi_00001 < Ii_0017C); 
   } 
   
   if (Gb_00003) return; 
   Il_000AC[Ii_0017C] = Fa_l_00;
   Id_000E0[Ii_0017C] = Fa_d_01;
   Ii_0017C = Ii_0017C + 1;
   tmp_str00001 = _Symbol + "_";
   tmp_str00001 = tmp_str00001 + IntegerToString(_Period, 0, 32);
   tmp_str00001 = tmp_str00001 + "_MonsterV2.bin";
   tmp_str00000 = tmp_str00001;
   Gi_00008 = FileOpen(tmp_str00000, 6);
   if (Gi_00008 == -1) return; 
   FileWriteInteger(Gi_00008, Ii_0017C, 4);
   Gi_00009 = 0;
   if (Ii_0017C > 0) { 
   do { 
   FileWriteLong(Gi_00008, Il_000AC[Gi_00009]);
   FileWriteDouble(Gi_00008, Id_000E0[Gi_00009], 0);
   Gi_00009 = Gi_00009 + 1;
   } while (Gi_00009 < Ii_0017C); 
   } 
   FileWriteInteger(Gi_00008, Ii_00180, 4);
   Gi_0000C = 0;
   if (Ii_00180 > 0) { 
   do { 
   FileWriteLong(Gi_00008, Il_00114[Gi_0000C]);
   FileWriteDouble(Gi_00008, Id_00148[Gi_0000C], 0);
   Gi_0000C = Gi_0000C + 1;
   } while (Gi_0000C < Ii_00180); 
   } 
   FileClose(Gi_00008);
   return ;
   } 
   if (Ii_00180 >= 10000) return; 
   Gl_0000F = Fa_l_00;

   Gi_00013 = 0;
   Gb_00012 = false;
   if (Ii_00180 > 0) {
   do { 
   if (Il_00114[Gi_00013] == Gl_0000F) {
   Gb_00012 = true;
   break;
   }
   Gi_00013 = Gi_00013 + 1;
   } while (Gi_00013 < Ii_00180); 
   }
   
   if (Gb_00012) return; 
   Il_00114[Ii_00180] = Fa_l_00;
   Id_00148[Ii_00180] = Fa_d_01;
   Ii_00180 = Ii_00180 + 1;
   tmp_str00002 = _Symbol + "_";
   tmp_str00002 = tmp_str00002 + IntegerToString(_Period, 0, 32);
   tmp_str00002 = tmp_str00002 + "_MonsterV2.bin";
   tmp_str00001 = tmp_str00002;
   Gi_00017 = FileOpen(tmp_str00001, 6);
   if (Gi_00017 == -1) return; 
   FileWriteInteger(Gi_00017, Ii_0017C, 4);
   Gi_00018 = 0;
   if (Ii_0017C > 0) { 
   do { 
   FileWriteLong(Gi_00017, Il_000AC[Gi_00018]);
   FileWriteDouble(Gi_00017, Id_000E0[Gi_00018], 0);
   Gi_00018 = Gi_00018 + 1;
   } while (Gi_00018 < Ii_0017C); 
   } 
   FileWriteInteger(Gi_00017, Ii_00180, 4);
   Gi_0001B = 0;
   if (Ii_00180 > 0) { 
   do { 
   FileWriteLong(Gi_00017, Il_00114[Gi_0001B]);
   FileWriteDouble(Gi_00017, Id_00148[Gi_0001B], 0);
   Gi_0001B = Gi_0001B + 1;
   } while (Gi_0001B < Ii_00180); 
   } 
   FileClose(Gi_00017);
   
}


