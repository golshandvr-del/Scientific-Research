
#define INDICATOR_NAME       "123PatternsV7WithAlerts"
#property indicator_chart_window
#property indicator_buffers 6
#property indicator_color1  DodgerBlue   // UpperLine
#property indicator_color2  OrangeRed    // LowerLine
#property indicator_color3  Goldenrod    // BullDot
#property indicator_color4  CornflowerBlue    // BearDot
#property indicator_color5  DodgerBlue   // BuyArrow
#property indicator_color6  OrangeRed    // SellArrow
#property indicator_width1  1
#property indicator_width2  1
#property indicator_width3  3  // BullDot
#property indicator_width4  3  // BearDot
#property indicator_width5  3  // BuyArrow
#property indicator_width6  3  // SellArrow

extern string generalSettings=" ================== 1-2-3 settings =======================";
extern string strMaxNoOfCandles= " ***** Number of candles which will be back calculated;0=all on chart";
extern int    maxNoOfCandles    = 1000;
extern string OneTwoThreeSettings=" ================== 1-2-3 settings =======================";
extern int    ZigZagDepth     = 6;
extern double RetraceDepthMin = 0.4;
extern double RetraceDepthMax = 1.0;
extern bool   ShowAllLines    = True;
extern bool   ShowAllBullBearDots = false;
extern bool   ShowAllBreaks   = True;
//alerts
extern string alertSettings=" ================== ALERT settings =======================";
extern bool Point2BreakAlerts = true;//123 setup
extern bool BreakUpperLineAlerts = true;//not 123 setup
extern bool BreakLowerLineAlerts = true;//not 123 setup
//
extern bool PopupAlerts         = true;
extern bool EmailAlerts         = false;
extern bool PushNotificationAlerts = false;
int lastP2BreakAlert=3;
int lastLineBreakAlert=3;
string msg;
//end alerts

// indicator buffers
double UpperLine[];
double LowerLine[];

double BuyArrow[];
double SellArrow[];
double BullDot[1000];
double BearDot[1000];

double   firsthigh, firstlow, lasthigh, lastlow, prevhigh, prevlow, signalprice, brokenline;
datetime firsthightime, firstlowtime, lasthightime, lastlowtime, prevhightime, prevlowtime, signaltime;
datetime redrawtime;  // remember when the indicator was redrawn

int     signal;
#define NOSIG   0
#define BUYSIG  1
#define SELLSIG 2

void initIndex(bool doInit,int indexNo,int drawStyle,double &Arr[],int arrSym){
   if (!doInit)
      return;
   SetIndexStyle(indexNo,drawStyle);
   SetIndexBuffer(indexNo,Arr);
   SetIndexArrow(indexNo,arrSym);
}


//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int init() {
   int i;
   for(i=0; i<=5; i++) {
      initIndex(ShowAllLines,0,DRAW_LINE,UpperLine,0);
      initIndex(ShowAllLines,1,DRAW_LINE,LowerLine,0);
      initIndex(ShowAllBullBearDots,2,DRAW_ARROW,BullDot,159);
      initIndex(ShowAllBullBearDots,3,DRAW_ARROW,BearDot,159);
      initIndex(true,4,DRAW_ARROW,BuyArrow,SYMBOL_ARROWUP);
      initIndex(true,5,DRAW_ARROW,SellArrow,SYMBOL_ARROWDOWN);
    }
   IndicatorShortName(INDICATOR_NAME);
   IndicatorDigits(Digits);
   return(0);
} // end of init()


//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int start()
{
   double   zigzag, range, retracedepth, one, two, three;
   datetime onetime, twotime, threetime;
   int      shift = Bars-1;

   bool isBrokenUpperLine=false;
   bool isBrokenLowerLine=false;
   if (maxNoOfCandles >0) 
      shift=maxNoOfCandles ;
   while(shift >= 0)
      {
      Print(shift);
      // UPPERLINES and LOWERLINES based on ZIGZAG
      UpperLine[shift] = UpperLine[shift+1];
      LowerLine[shift] = LowerLine[shift+1];
   
      //BuyArrow[shift] = EMPTY_VALUE;
      //SellArrow[shift] = EMPTY_VALUE;
      BullDot[shift] = EMPTY_VALUE;
      BearDot[shift] = EMPTY_VALUE;
      zigzag = iCustom(NULL,0,"ZigZag",ZigZagDepth,5,3,0,shift);
      if(zigzag == High[shift])
         {
         UpperLine[shift] = High[shift];
         firsthigh = prevhigh; firsthightime = prevhightime;
         prevhigh = lasthigh;  prevhightime = lasthightime;
         lasthigh = zigzag;    lasthightime = Time[shift];
         }
      if(zigzag == Low[shift])
         {
         LowerLine[shift] = Low[shift];
         firstlow = prevlow; firstlowtime = prevlowtime;
         prevlow = lastlow;  prevlowtime = lastlowtime;
         lastlow = zigzag;   lastlowtime = Time[shift];
         }
   
   ///////////////////////////
   // BULLISH BREAK ABOVE #2
   one = prevlow; onetime = prevlowtime;
   two = lasthigh; twotime = lasthightime; if(twotime == Time[shift]){two = prevhigh; twotime = prevhightime;}
   three = lastlow; threetime = lastlowtime;
   if(one - two != 0) retracedepth = (three - two) / (one - two);  // retrace depth
   // signal rules
   if(shift > 0 && retracedepth > RetraceDepthMin && retracedepth < RetraceDepthMax && brokenline != UpperLine[shift] && Low[shift] < UpperLine[shift] && Close[shift] > UpperLine[shift])                
      {
      range = MathAbs(two - three);                    // range is the distance between two and three
      BuyArrow[shift] = Low[shift]-(High[shift]-Low[shift])/2;
      BullDot[iBarShift(NULL,0,onetime)] = one;        // ONE
      BullDot[iBarShift(NULL,0,twotime)] = two;        // TWO
      BullDot[iBarShift(NULL,0,threetime)] = three;    // THREE
      signal = BUYSIG;
      signaltime = Time[shift];
      signalprice = BuyArrow[shift];
      brokenline = UpperLine[shift];
      isBrokenUpperLine=true;
      //alerts added
      if (shift<=1 && Point2BreakAlerts && signal==BUYSIG && lastP2BreakAlert!=1) {
          doAlerts(true);
          lastP2BreakAlert=1;
          }
      //end alerts      
   }
   /////////////////////////////////////////////
   // BULLISH BREAK OF UPPERLINE (NOT 123 SETUP)
   // signal rules
   if(shift > 0 && ShowAllBreaks && brokenline != UpperLine[shift] && Low[shift] < UpperLine[shift] && Close[shift] > UpperLine[shift])
      {
      range = UpperLine[shift]-LowerLine[shift];
      BuyArrow[shift] = Low[shift]-(High[shift]-Low[shift])/2;
      signal = BUYSIG;
      signaltime = Time[shift];
      signalprice = BuyArrow[shift];
      brokenline = UpperLine[shift];  
      isBrokenUpperLine=true;
      //not 123 setup alerts:
      if (shift<=1 && BreakUpperLineAlerts && lastLineBreakAlert!=2) {
         doAlerts(true);
         lastLineBreakAlert=2;
         }//end alerts
      }

   ///////////////////////////
   // BEARISH BREAK BELOW #2
   one = prevhigh; onetime = prevhightime;
   two = lastlow; twotime = lastlowtime; if(twotime == Time[shift]){two = prevlow; twotime = prevlowtime;}
   three = lasthigh; threetime = lasthightime;
   if(one - two != 0) retracedepth = (three - two) / (one - two);  // retrace depth
   // signal rules
   if(shift > 0 && retracedepth > RetraceDepthMin && retracedepth < RetraceDepthMax && brokenline != LowerLine[shift] && High[shift] > LowerLine[shift] && Close[shift] < LowerLine[shift])                 
      {
      range = MathAbs(two - three);                    // range is the distance between two and three
      SellArrow[shift] = High[shift]+(High[shift]-Low[shift])/2;
      BearDot[iBarShift(NULL,0,onetime)] = one;        // ONE
      BearDot[iBarShift(NULL,0,twotime)] = two;        // TWO
      BearDot[iBarShift(NULL,0,threetime)] = three;    // THREE
      signal = SELLSIG;
      signaltime = Time[shift];
      signalprice = SellArrow[shift];
      brokenline = LowerLine[shift];
      isBrokenLowerLine=true;
      //alerts added
      if (shift<=1 && Point2BreakAlerts && signal==SELLSIG && lastP2BreakAlert!=2) {
       doAlerts(false);
       lastP2BreakAlert=2;
      }
      //end alerts      
   }

   /////////////////////////////////////////////
   // BEARISH BREAK OF LOWERLINE (NOT 123 SETUP)
   // signal rules
   if (shift > 0 && ShowAllBreaks && brokenline != LowerLine[shift] && High[shift] > LowerLine[shift] && Close[shift] < LowerLine[shift])
      {
      range = UpperLine[shift]-LowerLine[shift];
      SellArrow[shift] = High[shift]+(High[shift]-Low[shift])/3; 
      signal = SELLSIG;
      signaltime = Time[shift];
      signalprice = SellArrow[shift];
      brokenline = LowerLine[shift];
      isBrokenLowerLine=true;
      //not 123 setup alerts:
      if (shift<=1 && BreakLowerLineAlerts && lastLineBreakAlert!=1) {
         doAlerts(false);
         lastLineBreakAlert=1;
         }//end alerts
      }
      if (LowerLine[shift] != LowerLine[shift+1] && SellArrow[shift]==EMPTY_VALUE)
         isBrokenLowerLine=false;
      if (UpperLine[shift] != UpperLine[shift+1] && BuyArrow[shift]==EMPTY_VALUE)
         isBrokenLowerLine=false;
      
      //if(UpperLine[shift] != UpperLine[shift+1]) UpperLine[shift+1] = EMPTY_VALUE;
      //if(LowerLine[shift] != LowerLine[shift+1]) LowerLine[shift+1] = EMPTY_VALUE;
      
   //if (brokenline && shift <20) 
   //   Alert(shift+" broken line");
      // UpperLine[shift] = EMPTY_VALUE;
   shift--; // move ahead one candle
   }
   
   // Set Zero Values to EMPTY;
   ChangeZero2EmptyArray();
   
   // Delete red unneccessary lines!
   deleteRedLines();
   deleteBlueLines();
   return(0);
}// end of start()

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
int deinit() 
{
return(0);}

//+------------------------------------------------------------------+
//| Alert function
//+------------------------------------------------------------------+

void doAlerts(bool buy) {
   string Msg;
   if (buy)
      Msg="buy";
   else
      Msg="sell";
   Msg=" "+Symbol()+" M"+ Period() + " "+Msg+"!";
   string emailsubject=WindowExpertName()+ Msg;
   if (PopupAlerts) Alert(Msg);
   if (EmailAlerts) SendMail(Msg,Msg);
   if (PushNotificationAlerts) SendNotification(Msg);
   }


//+------------------------------------------------------------------+
//| Set Zero Values to Empty
//+------------------------------------------------------------------+

void ChangeZero2EmptyArray(){
   // Get number of Bars
   int shift=Bars-1;
   // Loop through Arrays
   while(shift>= 0)
      {
         // Set Arrays to Empty if Zero
         if (LowerLine[shift]==0)
            LowerLine[shift]=EMPTY_VALUE;
         if (UpperLine[shift]==0)
            UpperLine[shift]=EMPTY_VALUE;
      shift--;
      }
}

//+------------------------------------------------------------------+
//| Delete unneccessary red lines
//+------------------------------------------------------------------+
void deleteRedLines(){
   int brokenlevelno,i,j;
   int shift = Bars-1;
   while(shift>= 0)
      {
      while (LowerLine[shift]==EMPTY_VALUE) 
         shift--;
      i=shift;
      brokenlevelno=shift;
      do {
         if (SellArrow[i]!=EMPTY_VALUE)
            brokenlevelno=i-3;
         i--;
      } while (LowerLine[i]==LowerLine[i+1]); 

      for (j=i;j<=brokenlevelno;j++)
         LowerLine[j]=EMPTY_VALUE;
      shift=i-1;
      }
}

//+------------------------------------------------------------------+
//| Delete unneccessary blue lines
//+------------------------------------------------------------------+
void deleteBlueLines(){
   int brokenlevelno,i,j;
   int shift = Bars-1;
   while(shift>= 0)
      {
      while (UpperLine[shift]==EMPTY_VALUE) 
         shift--;
      i=shift;
      brokenlevelno=shift;
      do {
         if (BuyArrow[i]!=EMPTY_VALUE)
            brokenlevelno=i-3;
         i--;
      } while (UpperLine[i]==UpperLine[i+1]); 

      for (j=i;j<=brokenlevelno;j++)
         UpperLine[j]=EMPTY_VALUE;
      shift=i-1;
      }
}