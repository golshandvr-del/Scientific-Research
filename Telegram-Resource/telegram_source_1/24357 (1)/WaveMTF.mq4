//+------------------------------------------------------------------+
//|                                                      WaveMTF.mq4 |
//|                           Copyright 2019, Roberto Jacobs (3rjfx) |
//|                              https://www.mql5.com/en/users/3rjfx |
//+------------------------------------------------------------------+
#property copyright "Copyright 2019, Roberto Jacobs (3rjfx) ~ By 3rjfx ~ Created: 2019/01/26"
#property link      "https://www.mql5.com/en/users/3rjfx"
#property description "Indicator WaveMTF Bull and Bear System with Signal and Alert"
#property description "for MetaTrader 4 with options to display signal on the chart."
/* Update_01: 2019/02/23 ~ Remove any of bugs and error, and the not used code. */
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 2
//--
//--
enum YN
 {
   No,
   Yes
 };
//--
enum corner
 {  
   NotShow=-1,     // Not Show Arrow
   topchart=0,     // On Top Chart
   bottomchart=1   // On Bottom Chart
 };
//--
//--
input corner                 cor = topchart; // Arrow Move Position
input YN                  alerts = Yes;        // Display Alerts / Messages (Yes) or (No)
input YN              EmailAlert = No;         // Email Alert (Yes) or (No)
input YN              sendnotify = No;         // Send Notification (Yes) or (No)
input YN             displayinfo = Yes;        // Display Trade Info
input color            textcolor = clrSnow;    // Text Color
input color              ArrowUp = clrLime;    // Arrow Up Color
input color              ArrowDn = clrRed;     // Arrow Down Color
input color              NTArrow = clrYellow;  // Arrow No Signal
//---
//---- indicator buffers
double BufferUp[];
double BufferDn[];
//--
//--- spacing
int scaleX=35,scaleY=40,scaleYt=18,offsetX=250,offsetY=3,fontSize=7; // coordinate
int txttf,
    arrtf;
color arclr;
ENUM_BASE_CORNER bcor;
//--- arrays for various things
int BBTF[]={1,5,15,30,60,240,1440,10080,43200};
int XBB[10];
string periodStr[]={"M1","M5","M15","M30","H1","H4","D1","W1","MN","MOVE"}; // Text Timeframes
//--
double 
   pricepos;
datetime 
   cbartime;
int cur,prv;
int imnn,imnp;
int cmnt,pmnt;
int arr;
long CI;
static int fbar;
string posisi,
       sigpos,
       iname,
       msgText;
string frtext="wave";
//---------//
//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
//--- indicator buffers mapping
    IndicatorBuffers(2);
    //--
    SetIndexBuffer(0,BufferUp);
    SetIndexBuffer(1,BufferDn);
    //--
    SetIndexStyle(0,DRAW_NONE);
    SetIndexStyle(1,DRAW_NONE);
    //--
//----
    //-- name for DataWindow
    SetIndexLabel(0,"Bullish");
    SetIndexLabel(1,"Bearish");
    //--
    SetIndexEmptyValue(0,0.0);
    SetIndexEmptyValue(1,0.0);
//---- indicator short name
    IndicatorDigits(_Digits);
    iname=WindowExpertName();
    IndicatorShortName(iname);
    CI=ChartID();
    arr=ArraySize(XBB);
    //--
    if(cor>=0)
      {
        if(cor==topchart) {bcor=CORNER_LEFT_UPPER; txttf=45; arrtf=-20;}
        if(cor==bottomchart) {bcor=CORNER_LEFT_LOWER; txttf=45; arrtf=-12;}
      }
    else
     {
       string name;
       for(int i=ObjectsTotal()-1; i>=0; i--)
         {
           name=ObjectName(i);
           if(StringFind(name,frtext,0)>-1) ObjectDelete(0,name);
         }
     }
    //--
//---
   return(INIT_SUCCEEDED);
  }
//---------//
//+------------------------------------------------------------------+
//| Custor indicator deinitialization function                       |
//+------------------------------------------------------------------+
int deinit()
  {
//----
    Comment("");
    string name;
    for(int i=ObjectsTotal()-1; i>=0; i--)
      {
        name=ObjectName(i);
        if(StringFind(name,frtext,0)>-1) ObjectDelete(0,name);
      }
    //--
    GlobalVariablesDeleteAll();
//----
   return(0);
  }
//---------//
//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
//---
    ArraySetAsSeries(high,true);
    ArraySetAsSeries(low,true);
    ArraySetAsSeries(close,true);
    ArraySetAsSeries(time,true);
    int tr=0,xbup=0,xbdn=0,i;
    cbartime=time[0];
    arclr=NTArrow;
    //--
    imnn=Minute();
    if(imnn!=imnp)
      {
        ResetLastError();
        RefreshRates();
        if(cor>=0)
          {
            for(int x=0; x<arr; x++)
              {
                CreateArrowLabel(CI,frtext+"_tfx_arrow_"+string(x),periodStr[x],"Bodoni MT Black",fontSize,textcolor,bcor,
                                 txttf+x*scaleX+offsetX,scaleY+offsetY+7,true); //"Georgia" "Bodoni MT Black" "Verdana" "Arial Black"
              }
          }
        //--
        for(i=0; i<arr-1; i++)
          {
            XBB[i]=GetDirection(BBTF[i]);
            if(cor>=0)
              {
                if(XBB[i]>0) arclr=ArrowUp;
                if(XBB[i]<0) arclr=ArrowDn;
                CreateArrowLabel(CI,frtext+"_win_arrow_"+string(i),CharToString(108),"Wingdings",14,arclr,bcor,
                                 txttf+i*scaleX+offsetX,arrtf+scaleY+offsetY+7,true);
              }
            if(i>0 && i<7)
              {
                if(XBB[i]>0) xbup++; 
                if(XBB[i]<0) xbdn++;
              }
          }
        if(i==9)
          {
            if(xbup>=5) 
              {
                tr=1;
                XBB[i]=xbup; arclr=ArrowUp; BufferUp[0]=GetPrice(_Period,tr); 
                pricepos=BufferUp[0]; 
                cur=1;
                fbar=iBarShift(_Symbol,0,cbartime,false);
              }
            else
            if(xbdn>=5) 
              {
                tr=-1;
                XBB[i]=xbdn; arclr=ArrowDn; BufferDn[0]=GetPrice(_Period,tr); 
                pricepos=BufferDn[0]; 
                cur=-1;
                fbar=iBarShift(_Symbol,0,cbartime,false);
              }
            else 
              {
                XBB[i]=0; 
                arclr=NTArrow; 
                BufferDn[0]=0.0; 
                BufferUp[0]=0.0; 
                pricepos=close[0];
                cur=0;
                fbar=iBarShift(_Symbol,0,time[0],false);
              }
            //--
            if(cor>=0) CreateArrowLabel(CI,frtext+"_win_arrow_"+string(i),CharToString(108),"Wingdings",14,arclr,bcor,
                                         txttf+i*scaleX+offsetX+8,arrtf+scaleY+offsetY+7,true);
          }
        //--
        imnp=imnn;
      }
    //--   
    if(alerts==Yes||EmailAlert==Yes||sendnotify==Yes) Do_Alerts(cur,fbar);
    if(displayinfo==Yes) ChartComm();
    //--
//--- return value of prev_calculated for next call
   return(rates_total);
  }
//---------//

// getting the price direction
int GetDirection(int xtf) 
  {
//---
    int ret=0;
    RefreshRates();
    //--
    double ptpc1=(iHigh(_Symbol,xtf,1)+iLow(_Symbol,xtf,1)+iClose(_Symbol,xtf,1))/3;
    double ptpc0=(iHigh(_Symbol,xtf,0)+iLow(_Symbol,xtf,0)+iClose(_Symbol,xtf,0))/3;
    //--
    double mapw1=iMA(_Symbol,xtf,13,0,MODE_SMMA,PRICE_WEIGHTED,1);
    double mapw0=iMA(_Symbol,xtf,13,0,MODE_SMMA,PRICE_WEIGHTED,0);
    //--
    double bb1=ptpc1-mapw1;
    double bb0=ptpc0-mapw0;
    //--
    if(bb0>bb1) ret=1;
    if(bb0<bb1) ret=-1;
    //--
    return(ret);
//---
  }
//---------//

// getting the price position
double GetPrice(int xtf,int bb)
  {
//---
    int bar=(int)480/xtf < 5 ? 5 : (int)480/xtf;
    if(bar>120) bar=120;
    double ppos=0;
    double hih[],
           lol[];
    ArrayResize(hih,bar);
    ArrayResize(lol,bar);
    ArraySetAsSeries(hih,true);
    ArraySetAsSeries(lol,true);
    //--
    for(int x=bar-1; x>=0; x--)
      {
        hih[x]=iHigh(_Symbol,xtf,x);
        lol[x]=iLow(_Symbol,xtf,x);
      }
    if(bb>0) {ppos=iLow(_Symbol,xtf,ArrayMinimum(lol,bar,0)); cbartime=iTime(_Symbol,xtf,ArrayMinimum(lol,bar,0));}
    if(bb<0) {ppos=iHigh(_Symbol,xtf,ArrayMaximum(hih,bar,0)); cbartime=iTime(_Symbol,xtf,ArrayMaximum(hih,bar,0));}
    //--
    return(ppos);
//---
  }
//---------//

void Do_Alerts(int fcur,int fb)
  {
    //--
    cmnt=Minute();
    if(cmnt!=pmnt)
      {
        //--
        if(fcur==1)
          {
            msgText="Wave Price Up Start"+" at bars: "+string(fb);
            posisi="Bullish"; 
            sigpos="Open BUY Order";
          }
        else
        if(fcur==-1)
          {
            msgText="Wave Price Down Start"+" at bars: "+string(fb);
            posisi="Bearish"; 
            sigpos="Open SELL Order";
          }
        else
          {
            msgText="Wave Price Not Found!";
            posisi="Not Found!"; 
            sigpos="Wait for Confirmation!";
          }
        //--
        if(fcur!=prv)
          {
            Print(iname,"--- "+_Symbol+" "+TF2Str(_Period)+": "+msgText+
                  "\n--- at: ",TimeToString(iTime(_Symbol,0,0),TIME_DATE|TIME_MINUTES)+" - "+sigpos);
            //--
            if(alerts==Yes)
              Alert(iname,"--- "+_Symbol+" "+TF2Str(_Period)+": "+msgText+
                    "--- at: ",TimeToString(iTime(_Symbol,0,0),TIME_DATE|TIME_MINUTES)+" - "+sigpos);
            //--
            if(EmailAlert==Yes) 
              SendMail(iname,"--- "+_Symbol+" "+TF2Str(_Period)+": "+msgText+
                               "\n--- at: "+TimeToString(iTime(_Symbol,0,0),TIME_DATE|TIME_MINUTES)+" - "+sigpos);
            //--
            if(sendnotify==Yes) 
              SendNotification(iname+"--- "+_Symbol+" "+TF2Str(_Period)+": "+msgText+
                               "\n--- at: "+TimeToString(iTime(_Symbol,0,0),TIME_DATE|TIME_MINUTES)+" - "+sigpos);                
            //--
            prv=fcur;
            //pbartime=fbartime;
          }
        //--
        pmnt=cmnt;
      }
    //--
    return;
    //---
  }
//---------//

string TF2Str(int period)
  {
   switch(period)
     {
       //--
       case PERIOD_M1: return("M1");
       case PERIOD_M5: return("M5");
       case PERIOD_M15: return("M15");
       case PERIOD_M30: return("M30");
       case PERIOD_H1: return("H1");
       case PERIOD_H4: return("H4");
       case PERIOD_D1: return("D1");
       case PERIOD_W1: return("W1");
       case PERIOD_MN1: return("MN");
       //--
     }
   return(string(period));
  }  
//---------//

string AccountMode() // function: to known account trade mode
   {
//----
//--- Demo, Contest or Real account 
   ENUM_ACCOUNT_TRADE_MODE account_type=(ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
 //---
   string trade_mode;
   //--
   switch(account_type) 
     { 
      case  ACCOUNT_TRADE_MODE_DEMO: 
         trade_mode="Demo"; 
         break; 
      case  ACCOUNT_TRADE_MODE_CONTEST: 
         trade_mode="Contest"; 
         break; 
      default: 
         trade_mode="Real"; 
         break; 
     }
   //--
   return(trade_mode);
//----
   } //-end AccountMode()
//---------//

void ChartComm() // function: write comments on the chart
  {
//----
   //--
   Comment("\n     :: Server Date Time : ",(string)Year(),".",(string)Month(),".",(string)Day(), "   ",TimeToString(TimeCurrent(),TIME_SECONDS), 
      "\n     ------------------------------------------------------------", 
      "\n      :: Broker             :  ",TerminalCompany(), 
      "\n      :: Acc. Name       :  ",AccountName(), 
      "\n      :: Acc, Number    :  ",(string)AccountNumber(),
      "\n      :: Acc,TradeMode :  ",AccountMode(),
      "\n      :: Acc. Leverage   :  1 : ",(string)AccountLeverage(), 
      "\n      :: Acc. Balance     :  ",DoubleToString(AccountBalance(),2),
      "\n      :: Acc. Equity       :  ",DoubleToString(AccountEquity(),2), 
      "\n      --------------------------------------------",
      "\n      :: Indicator Name  :  ",iname,
      "\n      :: Currency Pair    :  ",_Symbol,
      "\n      :: Current Spread  :  ",IntegerToString(SymbolInfoInteger(_Symbol,SYMBOL_SPREAD),0),
      "\n      :: Signal Start       : at bar ",string(iBarShift(_Symbol,0,cbartime,false)),
      "\n      :: Wave Start       :  ",DoubleToString(pricepos,_Digits), 
      "\n      :: Indicator Signal :  ",posisi,
      "\n      :: Suggested        :  ",sigpos);
   //---
   ChartRedraw();
   return;
//----
  } //-end ChartComm()  
//---------//

bool CreateArrowLabel(long   chart_id, 
                      string lable_name, 
                      string label_text,
                      string font_model,
                      int    font_size,
                      color  label_color,
                      int    chart_corner,
                      int    x_cor, 
                      int    y_cor,
                      bool   price_hidden)
  { 
//--- 
    //--
    ObjectDelete(chart_id,lable_name);
    //--
    if(!ObjectCreate(chart_id,lable_name,OBJ_LABEL,0,0,0,0,0)) 
      { 
        Print(__FUNCTION__, 
            ": failed to create \"Arrow Label\" sign! Error code = ",GetLastError());
        return(false); 
      } 
    //--
    ObjectSetString(chart_id,lable_name,OBJPROP_TEXT,label_text);
    ObjectSetString(chart_id,lable_name,OBJPROP_FONT,font_model); 
    ObjectSetInteger(chart_id,lable_name,OBJPROP_FONTSIZE,font_size);
    ObjectSetInteger(chart_id,lable_name,OBJPROP_COLOR,label_color);
    ObjectSetInteger(chart_id,lable_name,OBJPROP_CORNER,chart_corner);
    ObjectSetInteger(chart_id,lable_name,OBJPROP_XDISTANCE,x_cor);
    ObjectSetInteger(chart_id,lable_name,OBJPROP_YDISTANCE,y_cor);
    ObjectSetInteger(chart_id,lable_name,OBJPROP_HIDDEN,price_hidden);
    //--- successful execution 
    return(true);
    //--
  }
//---------//  
//+------------------------------------------------------------------+
