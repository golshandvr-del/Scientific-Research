//+------------------------------------------------------------------+
//|                                                  CStockClock.mqh |
//|                        Copyright 2015, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2015, MetaQuotes Software Corp."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict
#include "StockClockEnums.mqh"
#include "CGTrendline.mqh"
#include "CGBitmapLabel.mqh"
#include "CGLabel.mqh"
#include "CGButton.mqh"
//+------------------------------------------------------------------+
//| Shows stock 24-hour clock                                        |
//+------------------------------------------------------------------+
class CStockClock
  {
private:
   DST_EVENT         m_dst_event;                                          // DST time event (stock open or close)
   string            m_folder;                                             // folder with bmp files
   string            m_name_back;                                          // object name for back/forward button
   string            m_name_move;                                          // object name for move button
   string            m_name_hide;                                          // object name for hide button
   STOCK_SCHEME      m_scheme;                                             // color scheme
   int               m_x;                                                  // x left-top position of the clock-skin
   int               m_y;                                                  // y left-top position of the clock-skin
   int               m_width;                                              // width of the clock-skin
   int               m_height;                                             // height of the clock-skin
   int               m_x0;                                                 // x central point in pixels
   int               m_y0;                                                 // y central point in pixels
   int               m_x0_rel;                                             // relativaly to x central point in pixels
   int               m_y0_rel;                                             // relativaly to y central point in pixels
   int               m_radius_hh;                                          // radius (width)  of hour hand
   int               m_radius_mh;                                          // radius (width) of minute hand
   int               m_radius_sh;                                          // radius (width) of second hand
   int               m_xmove;                                              // x move button position
   int               m_ymove;                                              // y move button position
   int               m_xback;                                              // x back/forward button position
   int               m_yback;                                              // y back/forward button position
   int               m_xhide;                                              // x hide button position
   int               m_yhide;                                              // y hide button position
   int               m_x_label;                                            // x header position
   int               m_y_label;                                            // y header position
   int               m_xmove_rel;                                          // relativaly to x move button position
   int               m_ymove_rel;                                          // relativaly to y move button position
   int               m_xback_rel;                                          // relativaly to x back/forward button position
   int               m_yback_rel;                                          // relativaly to y back/forward button position
   int               m_xhide_rel;                                          // relativaly to x hide button position
   int               m_yhide_rel;                                          // relativaly to y hide button position
   int               m_x_label_rel;                                        // relativaly to x header position
   int               m_y_label_rel;                                        // relativaly to y header position
   int               m_xcpt_rel;                                           // relativaly to x central point
   int               m_ycpt_rel;                                           // relativaly to y central point
   int               m_xhidden;                                            // x hidden position
   int               m_yhidden;                                            // y hidden position
   int               m_button_width;                                       // button width
   int               m_button_height;                                      // button height
   int               m_header_height;                                      // header height
   int               m_xboundary;                                          // right x boundary position
   int               m_yboundary;                                          // bottom y boundary position
   datetime          m_dt0;                                                // datetime for central point
   datetime          m_dt_hh;                                              // datetime for the 2-nd hour hand point 
   datetime          m_dt_mh;                                              // datetime for the 2-nd minute hand point
   datetime          m_dt_sh;                                              // datetime for the  2-nd second hand point
   double            m_pr0;                                                // price for central point
   double            m_pr_hh;                                              // price for the 2-nd hour hand point
   double            m_pr_mh;                                              // price for the 2-nd minute hand point
   double            m_pr_sh;                                              // price for the 2-nd second hand point
   datetime          m_tmd;                                                // debugging datetime
   bool              m_show_second_hand;                                   // show second hand
   bool              m_clock_hidden;                                       // clock hidden
   bool              m_error_position;                                     // clock error position
   bool              m_debug_on;                                           // use debug time              
   color             m_bcolor;
   color             m_wcolor;
   ENUM_LINE_STYLE   m_secstyle;
   CGBitmapLabel     *m_clock_skin;                                        // clock skin
   CGBitmapLabel     *m_header;                                            // header panel
   CGTrendline       *m_hand_second;                                       // second hand
   CGTrendline       *m_hand_minute;                                       // minute hand
   CGTrendline       *m_hand_hour;                                         // hour hand
   CGLabel           *m_clockname;                                         // clock header name
   CGButton          *m_button_move;                                       // move button
   CGButton          *m_button_back;                                       // back/forward button
   CGButton          *m_button_hide;                                       // hide button
   string            DstEventFileBlack(void);                              // return bmp file name corresponding to DST event          
   string            DstEventFileWhite(void);                              // return bmp file name corresponding to DST event          
   void              DSTime(void);                                         // Setting Day Saving Time event.     
public:
   CStockClock(int x,int y,string folder,bool show_second_hand=false,STOCK_SCHEME scheme=black); // top-left position, etc.
   ~CStockClock();
   void              DefaultsSkin(void);                                   // setting defaults for clock skip
   void              DefaultsHeader(void);                                 // setting defaults for header panel
   void              SetExtSecond(color bColor,
                                  color wColor,
                                  ENUM_LINE_STYLE style)
                                 {m_bcolor=bColor;
                                  m_wcolor=wColor;
                                  m_secstyle=style;};                                  
   void              DefaultsHours(void);                                  // setting defaults for second hand
   void              DefaultsMinute(void);                                 // setting defaults for second hand
   void              DefaultsSecond(void);                                 // setting defaults for second hand
   void              DefaultsMove(void);                                   // setting defaults for move button
   void              DefaultsBack(void);                                   // setting defaults for back/forward button
   void              DefaultsHide(void);                                   // setting defaults for hide button
   void              DefaultsHeaderLabel(void);                            // setting defaults for head label
   void              HandSecondMove(void);                                 // new position of second hand 
   void              HandMinuteMove(void);                                 // new position of minute hand 
   void              HandHourMove(void);                                   // new position of hour hand 
   void              ProcessingDstEvent(void);                             // Processing DST events
   bool              ShowSecondHand(void) {return(m_show_second_hand);};       
   void              SetPositions(int x,int y);                             // Setting positions for the objects                 
   void              SetStateBack(bool aValue=false);                      // Setting back/forward state for the objects
   void              SetStateMove(bool aValue=false);                      // Setting on/off state of move-button
   void              SetBackOn(void) {m_button_back.SetState(true);}       // Setting button state
   void              SetMoveOff(void) {m_button_move.SetState(false);}     // Setting button state
   void              ClockShow(void);                                      // Show clock
   void              SetDebugDate(int yy,int mn,int dd);
   void              ClockHide(void);                                      // Hide clock
   bool              ClockHidden(void) {return(m_clock_hidden);}           // Clock hidden or not
   // events
   bool   StateBack(void) {return(m_button_back.State());}                 // Getting back/forward button state
   bool   StateMove(void) {return(m_button_move.State());}                 // Getting move button state
   bool   StateHide(void) {return(m_button_hide.State());}                 // Getting hide button state
   void   EventBack(const int id,const long& lparam,const double& dparam,const string& sparam); // back/forward
   void   EventMove(const int id,const long& lparam,const double& dparam,const string& sparam); // new position
   void   EventHide(const int id,const long& lparam,const double& dparam,const string& sparam); // hide/show clock

  };
//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CStockClock::CStockClock(int x,int y,string folder,bool show_second_hand=false,STOCK_SCHEME scheme=black)
  {
   m_x=x;
   m_y=y;
   //--- setting relative positions and sizes
   m_width=401;
   m_height=400;
   m_x0_rel=200;
   m_y0_rel=220;
   m_xmove_rel=1;
   m_ymove_rel=1;
   m_xback_rel=382;
   m_yback_rel=1;
   m_xhide_rel=364;
   m_yhide_rel=1;
   m_x_label_rel=200;
   m_y_label_rel=10;
   m_x0=x+m_x0_rel;
   m_y0=y+m_y0_rel;
   m_radius_hh=119;
   m_radius_mh=159;
   m_radius_sh=159;
   m_button_height=17;
   m_button_width=17;
   m_header_height=20;
   m_xcpt_rel=6;
   m_ycpt_rel=6;
   m_clock_hidden=false;
   m_xhidden=0;
   m_bcolor=clrGreenYellow;
   m_wcolor=clrDarkOrange;
   m_secstyle=STYLE_SOLID;
   long result=-1;
   ResetLastError();
   if(!ChartGetInteger(0,CHART_HEIGHT_IN_PIXELS,0,result)) Print(__FUNCTION__,": CHART_HEIGHT_IN_PIXELS. Error Code = ",GetLastError());
   m_yboundary=(int)result;
   m_yhidden = -500;
   result=-1;
   ResetLastError();
   if(!ChartGetInteger(0,CHART_WIDTH_IN_PIXELS,0,result)) Print(__FUNCTION__,": CHART_WIDTH_IN_PIXELS. Error Code = ",GetLastError());
   m_xboundary=(int)result;
   //--- subfolder in Image-folder
   m_folder="//Images//"+folder+"//";
   //--- show second hand or not
   m_show_second_hand=show_second_hand;
   m_scheme=scheme;
   //--- creating objects
   m_clock_skin=new CGBitmapLabel("ClockStockSkin");
   m_header=new CGBitmapLabel("ClockHeader");
   m_hand_second=new CGTrendline("ClockHandSecond");
   m_hand_minute=new CGTrendline("ClockHandMinute");
   m_hand_hour=new CGTrendline("ClockHandHour");
   m_clockname=new CGLabel("ClockNameLabel");
   //--- button names will be used when events are checking
   m_name_move="ClockButtonMove";
   m_name_back="ClockButtonBack";
   m_name_hide="ClockButtonHide";
   m_button_move=new CGButton(m_name_move);
   m_button_back=new CGButton(m_name_back);
   m_button_hide=new CGButton(m_name_hide);
   m_debug_on=false;
  }
//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CStockClock::~CStockClock()
  {
   delete m_clock_skin;
   delete m_header;
   delete m_hand_second;
   delete m_hand_minute;
   delete m_hand_hour;
   delete m_button_move;
   delete m_button_back;
   delete m_button_hide;
   delete m_clockname;
  }
//+------------------------------------------------------------------+
//| Back/forward event                                               |
//+------------------------------------------------------------------+
void CStockClock::EventBack(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK)
     {
      //--- button m_name_back was clicked
      if(sparam==m_name_back)                      
        {
         //--- if button is on
         if(StateBack())
           {
            SetStateBack(true);
            return; 
           }
         //--- if button is off
         if(!StateBack())
           {
            SetStateBack(false);
            return;
           }   
        }
     }
  }
//+------------------------------------------------------------------+
//| New position event                                               |
//+------------------------------------------------------------------+
void CStockClock::EventMove(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   int left=(int)lparam;
   int top=(int)dparam;
   int left_icon,top_icon,right_icon,bottom_icon;
   if(id==CHARTEVENT_CLICK)
     {
      //--- calculate button rectangle
      left_icon=m_button_move.XDistance();
      top_icon=m_button_move.YDistance(); 
      right_icon=left_icon+m_button_width;
      bottom_icon=top_icon+m_button_height;
      //--- if button is pressed and clicked inside the rectangle
      if(StateMove())       
        {
         if(left>right_icon || left<left_icon || top<top_icon || top>bottom_icon)
           {
            //--- set new positions
            SetPositions(left,top);
            //--- set button on-state
            SetStateMove(false);     
            return;
           }
         }
     }
  }
//+------------------------------------------------------------------+
//| Hide/Show clock event                                            |
//+------------------------------------------------------------------+
void CStockClock::EventHide(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK)
     {
      //--- button m_name_back was clicked
      if(sparam==m_name_hide)                      
        {
         //--- if button is on
         if(m_clock_hidden)
           {
            ClockShow();
            return; 
           }
         //--- if button is off
         if(!m_clock_hidden)
           {
            ClockHide();
            return;
           }   
        }
     }
  }
//+------------------------------------------------------------------+
//| Setting on/off state of move button                              |
//+------------------------------------------------------------------+
void CStockClock::SetStateMove(bool aValue=false)
  {
   m_button_move.SetState(aValue);
  }
//+------------------------------------------------------------------+
//| Hide clock down                                                  |
//+------------------------------------------------------------------+
void CStockClock::ClockHide(void)
  {   
   int center_x,center_y;                 
   //--- bool variable to block events for "move" and "back/forward" buttons
   m_clock_hidden=true;
   //--- setting new positions for bitmap label objects when they are hided
   m_clock_skin.SetXDist(m_xhidden);                                             
   m_clock_skin.SetYDist(m_yhidden+m_header_height);                                             
   center_x=m_xhidden+m_x0_rel;
   center_y=m_yhidden+m_y0_rel;
   m_hand_hour.SetColor(clrNONE);
   m_hand_minute.SetColor(clrNONE);
   m_hand_second.SetColor(clrNONE);               
  }
//+------------------------------------------------------------------+
//| Show clock up                                                    |
//+------------------------------------------------------------------+
void CStockClock::ClockShow(void)
  {
   //--- bool variable to unblock events for "move" and "back/forward" buttons
   m_clock_hidden=false;
   //--- setting old positions for bitmap label objects when they are hided
   m_clock_skin.SetXDist(m_x);                                             
   m_clock_skin.SetYDist(m_y+m_header_height);                                             
   m_x0=m_x+m_x0_rel;
   m_y0=m_y+m_y0_rel;
   switch (m_scheme)
     {
      //--- setting colors
      case black:
         m_hand_hour.SetColor(C'100,100,100');                             
         m_hand_minute.SetColor(C'100,100,100');                             
         m_hand_second.SetColor(clrGreenYellow);      
         break;
      case white:
         m_hand_hour.SetColor(C'155,155,155');                             
         m_hand_minute.SetColor(C'155,155,155');                             
         m_hand_second.SetColor(clrDarkOrange);       
         break;
      default:
         m_hand_hour.SetColor(C'100,100,100');            
         m_hand_minute.SetColor(C'100,100,100');                             
         m_hand_second.SetColor(clrGreenYellow);      
     };
  }
//+------------------------------------------------------------------+
//| Setting debug date                                               |
//+------------------------------------------------------------------+
void CStockClock::SetDebugDate(int yy,int mn,int dd)
  {
   string error_str;
   datetime tm;
   //tm=StringToTime(" 1955.13.35 00:00 ");
   tm=StringToTime(" "+IntegerToString((int)yy)+"."+IntegerToString((int)mn,2,'0')+"."+IntegerToString((int)dd,2,'0')+" 00:00 ");
   MqlDateTime stm;
   TimeToStruct(tm,stm);
   if(yy!=stm.year||mn!=stm.mon||dd!=stm.day) 
     {
      error_str="Input Date error. New debuging date is assigned:"+TimeToString(tm,TIME_DATE);
      Print(__FUNCTION__,error_str);
     }
   m_debug_on=true;
   m_tmd=StructToTime(stm);
  }
//+------------------------------------------------------------------+
//| Setting back/forward state of the objects                        |
//+------------------------------------------------------------------+
void CStockClock::SetStateBack(bool aValue=false)
  {
   //--- setting on/off state for all objects
   m_clock_skin.SetBack(aValue);
   m_header.SetBack(aValue);
   m_hand_second.SetBack(aValue);
   m_hand_minute.SetBack(aValue);
   m_hand_hour.SetBack(aValue);
   m_button_back.SetBack(aValue);
   m_button_move.SetBack(aValue);
   m_button_hide.SetBack(aValue);
   m_clockname.SetBack(aValue);
   
  }
//+------------------------------------------------------------------+
//| Calculate X-Y positions for the objects                          |
//+------------------------------------------------------------------+
void CStockClock::SetPositions(int x,int y)
  {
   //--- setting sizes and x- y-positions for all objects
   m_x=x;
   m_y=y;
   m_xmove=m_x+m_xmove_rel;
   m_ymove=m_y+m_ymove_rel;
   m_xback=m_x+m_xback_rel;
   m_yback=m_y+m_yback_rel;
   m_xhide=m_x+m_xhide_rel;
   m_yhide=m_y+m_yhide_rel;
   m_x_label=m_x+m_x_label_rel;
   m_y_label=m_y+m_y_label_rel;
   m_button_move.SetXDist(m_xmove);
   m_button_move.SetYDist(m_ymove);
   m_button_back.SetXDist(m_xback);
   m_button_back.SetYDist(m_yback);
   m_button_hide.SetXDist(m_xhide);
   m_button_hide.SetYDist(m_yhide);
   m_header.SetXDist(m_x);
   m_header.SetYDist(m_y);
   m_clock_skin.SetXDist(m_x);                                             
   m_clock_skin.SetYDist(m_y+m_header_height);                                             
   m_clockname.SetXDist(m_x_label);
   m_clockname.SetYDist(m_y_label);
   m_x0=x+m_x0_rel;
   m_y0=y+m_y0_rel;
   HandSecondMove();
   HandHourMove();
   HandMinuteMove();
  }
//+------------------------------------------------------------------+
//| Processing DST events                                            |
//+------------------------------------------------------------------+
void CStockClock::ProcessingDstEvent(void)
  {   
   //--- store current image file
   string image_old=m_clock_skin.GetFileOn();
   string image_new;
   //--- setting current "Day Saving Time" event
   DSTime();
   switch(m_scheme)
     {
      case black:
         image_new=DstEventFileBlack();
         break;
      case white:
         image_new=DstEventFileWhite();
         break;
      default:
         image_new=DstEventFileBlack();
     };
   if(image_old!=image_new)
      m_clock_skin.SetFileOn(image_new);
  }
//+------------------------------------------------------------------+
//| Setting defaults for move button                                 |
//+------------------------------------------------------------------+
void CStockClock::DefaultsMove(void)
  {
   m_xmove=m_x+m_xmove_rel;
   m_ymove=m_y+m_ymove_rel;
   color cFG,cBG,cBD;
   //--- creating  object
   m_button_move.Create();
   switch(m_scheme)
     {
      case black:
         cFG=C'0,0,0';
         cBG=C'100,100,100';
         cBD=clrNONE;
         break;
      case white:
         cFG=C'255,255,255';
         cBG=C'155,155,155';
         cBD=clrNONE;
         break;
      default:
         cFG=C'0,0,0';
         cBG=C'100,100,100';
         cBD=clrNONE;
     };
   //--- setting properties
   m_button_move.SetXDist(m_xmove);
   m_button_move.SetYDist(m_ymove);
   m_button_move.SetXSize(m_button_height);
   m_button_move.SetYSize(m_button_width);
   m_button_move.SetBack(true);
   m_button_move.SetState(false);
   m_button_move.SetChar(78);
   m_button_move.SetColorFG(cFG);     
   m_button_move.SetColorBG(cBG);
   m_button_move.SetColorBD(cBD);
   m_button_move.SetCorner(CORNER_LEFT_UPPER);
   m_button_move.SetFontName("Wingdings 2");
   m_button_move.SetFontSize(14);
   m_button_move.SetSelected(false);
   m_button_move.SetSelectable(false);
   m_button_move.SetHidden(true);
     
  }
//+------------------------------------------------------------------+
//| Setting defaults for hide button                                 |
//+------------------------------------------------------------------+
void CStockClock::DefaultsHide(void)
  {
   m_xhide=m_x+m_xhide_rel;
   m_yhide=m_y+m_yhide_rel;
   color cFG,cBG,cBD;
   //--- creating  object
   m_button_hide.Create();
   switch(m_scheme)
     {
      case black:
         cFG=C'0,0,0';
         cBG=C'100,100,100';
         cBD=clrNONE;
         break;
      case white:
         cFG=C'255,255,255';
         cBG=C'155,155,155';
         cBD=clrNONE;
         break;
      default:
         cFG=C'0,0,0';
         cBG=C'100,100,100';
         cBD=clrNONE;
     };
   //--- setting properties
   m_button_hide.SetXDist(m_xhide);
   m_button_hide.SetYDist(m_yhide);
   m_button_hide.SetXSize(m_button_width);
   m_button_hide.SetYSize(m_button_height);
   m_button_hide.SetBack(true);
   m_button_hide.SetState(false);
   m_button_hide.SetChar(244);
   m_button_hide.SetColorFG(cFG);     
   m_button_hide.SetColorBG(cBG);
   m_button_hide.SetColorBD(cBD);
   m_button_hide.SetCorner(CORNER_LEFT_UPPER);
   m_button_hide.SetFontName("Wingdings");
   m_button_hide.SetFontSize(10);
   m_button_hide.SetSelected(false);
   m_button_hide.SetSelectable(false);
   m_button_hide.SetHidden(true);
  }
//+------------------------------------------------------------------+
//| Setting defaults for back/forward button                         |
//+------------------------------------------------------------------+
void CStockClock::DefaultsBack(void)
  {
   m_xback=m_x+m_xback_rel;
   m_yback=m_y+m_yback_rel;
   color cFG,cBG,cBD;
   //--- creating  object
   m_button_back.Create();
   switch(m_scheme)
     {
      case black:
         cFG=C'0,0,0';
         cBG=C'100,100,100';
         cBD=clrNONE;
         break;
      case white:
         cFG=C'255,255,255';
         cBG=C'155,155,155';
         cBD=clrNONE;
         break;
      default:
         cFG=C'0,0,0';
         cBG=C'100,100,100';
         cBD=clrNONE;
     };
   //--- setting properties
   m_button_back.SetXDist(m_xback);
   m_button_back.SetYDist(m_yback);
   m_button_back.SetXSize(m_button_width);
   m_button_back.SetYSize(m_button_height);
   m_button_back.SetBack(true);
   m_button_back.SetState(true);
   m_button_back.SetChar(181);
   m_button_back.SetColorFG(cFG);     
   m_button_back.SetColorBG(cBG);
   m_button_back.SetColorBD(cBD);
   m_button_back.SetCorner(CORNER_LEFT_UPPER);
   m_button_back.SetFontName("Wingdings");
   m_button_back.SetFontSize(14);
   m_button_back.SetSelected(false);
   m_button_back.SetSelectable(false);
   m_button_back.SetHidden(true);
  }
//+------------------------------------------------------------------+
//| Setting defaults for header label                                |
//+------------------------------------------------------------------+
void CStockClock::DefaultsHeaderLabel(void)
  {
   m_x_label=m_x+m_x_label_rel;
   m_y_label=m_y+m_y_label_rel;
   //--- creating  object
   m_clockname.Create();
   color cFG;
   switch(m_scheme)
     {
      case black:
         cFG=C'0,0,0';
         break;
      case white:
         cFG=C'255,255,255';
         break;
      default:
         cFG=C'0,0,0';
     };
   //--- setting properties
   m_clockname.SetXDist(m_x_label);
   m_clockname.SetYDist(m_y_label);
   m_clockname.SetBack(true);
   m_clockname.SetText("market 24-hours GMT clock");
   m_clockname.SetColorText(cFG);     
   m_clockname.SetCorner(CORNER_LEFT_UPPER);
   m_clockname.SetAnchor(ANCHOR_CENTER);
   m_clockname.SetFontName("Arial");
   m_clockname.SetFontSize(12);
   m_clockname.SetSelected(false);
   m_clockname.SetSelectable(false);
   m_clockname.SetHidden(true);
  }
//+------------------------------------------------------------------+
//| Setting defaults for header                                      |
//+------------------------------------------------------------------+
void CStockClock::DefaultsHeader(void)
  {
   //--- creating object
   m_header.Create();                                                      
   //--- setting properties
   switch(m_scheme)
     {
      case black:
         m_header.SetFileOn(m_folder+"clock_analog_header_black.bmp");    
         break;
      case white:
         m_header.SetFileOn(m_folder+"clock_analog_header_white.bmp");    
         break;
      default:
         m_header.SetFileOn(m_folder+"clock_analog_header_black.bmp");    
     }
   m_header.SetXDist(m_x);                                                
   m_header.SetYDist(m_y);                                                
   m_header.SetXSize(m_width);                                                
   m_header.SetYSize(m_header_height);                                    
   m_header.SetXOffset(0);                                          
   m_header.SetYOffset(0);                                          
   m_header.SetState(true);                                         
   m_header.SetCorner(CORNER_LEFT_UPPER);                           
   m_header.SetAnchor(ANCHOR_LEFT_UPPER);                           
   m_header.SetColor(clrNONE);                                    
   m_header.SetStyle(STYLE_SOLID);                                  
   m_header.SetPointWidth(1);                                       
   m_header.SetBack(true);                                          
   m_header.SetSelected(false);                                     
   m_header.SetSelectable(false);                                   
   m_header.SetZOrder(0);                                           
   m_header.SetHidden(true);                                        
  }
//+------------------------------------------------------------------+
//| Setting defaults for clock skin                                  |
//+------------------------------------------------------------------+
void CStockClock::DefaultsSkin(void)
  {
   //--- creating  object
   m_clock_skin.Create();       
   //--- setting properties
   switch(m_scheme)
     {
      case black:
         m_clock_skin.SetFileOn(m_folder+"clock_analog_black_start.bmp"); 
         break;
      case white:
         m_clock_skin.SetFileOn(m_folder+"clock_analog_white_start.bmp"); 
         break;
      default:
         m_clock_skin.SetFileOn(m_folder+"clock_analog_black_start.bmp"); 
     }
   m_clock_skin.SetXDist(m_x);                                           
   m_clock_skin.SetYDist(m_y+m_header_height);                           
   m_clock_skin.SetXSize(m_width);                                       
   m_clock_skin.SetYSize(m_height);                                      
   m_clock_skin.SetXOffset(0);                                           
   m_clock_skin.SetYOffset(0);                                           
   m_clock_skin.SetState(true);                                          
   m_clock_skin.SetCorner(CORNER_LEFT_UPPER);                            
   m_clock_skin.SetAnchor(ANCHOR_LEFT_UPPER);                            
   m_clock_skin.SetColor(clrNONE);                                     
   m_clock_skin.SetStyle(STYLE_SOLID);                                   
   m_clock_skin.SetPointWidth(1);                                        
   m_clock_skin.SetBack(true);                                           
   m_clock_skin.SetSelected(false);                                      
   m_clock_skin.SetSelectable(false);                                    
   m_clock_skin.SetZOrder(0);                                            
   m_clock_skin.SetHidden(true);                                         
  }
//+------------------------------------------------------------------+
//| Setting defaults for hour hand                                   |
//+------------------------------------------------------------------+
void CStockClock::DefaultsHours(void)
  {
   //--- creating  object
   m_hand_hour.Create();        
   //--- setting properies
   switch (m_scheme)
     {
      case black:
         m_hand_hour.SetColor(C'100,100,100');                             
         break;
      case white:
         m_hand_hour.SetColor(C'155,155,155');                             
         break;
      default:
         m_hand_hour.SetColor(C'100,100,100');            
     };
   m_hand_hour.SetStyle(STYLE_SOLID);                                      
   m_hand_hour.SetWidth(5);          
   m_hand_hour.SetRay(false);                                      
   m_hand_hour.SetBack(true);                                              
   m_hand_hour.SetSelected(false);                                         
   m_hand_hour.SetSelectable(false);                                       
   m_hand_hour.SetHidden(true);                                            
   m_hand_hour.SetZOrder(0);                                               
  }
//+------------------------------------------------------------------+
//| Setting defaults for minute hand                                 |
//+------------------------------------------------------------------+
void CStockClock::DefaultsMinute(void)
  {
   //--- creating  object
   m_hand_minute.Create();                                  
   //--- setting properies
   switch (m_scheme)
     {
      case black:
         m_hand_minute.SetColor(C'100,100,100');            
         break;
      case white:
         m_hand_minute.SetColor(C'155,155,155');            
         break;
      default:
         m_hand_minute.SetColor(C'100,100,100');            
     };
   m_hand_minute.SetStyle(STYLE_SOLID);               
   m_hand_minute.SetWidth(3);   
   m_hand_minute.SetRay(false);                      
   m_hand_minute.SetBack(true);                       
   m_hand_minute.SetSelected(false);                  
   m_hand_minute.SetSelectable(false);                
   m_hand_minute.SetHidden(true);                     
   m_hand_minute.SetZOrder(0);                        
  }
//+------------------------------------------------------------------+
//| Setting defaults for second hand                                 |
//+------------------------------------------------------------------+
void CStockClock::DefaultsSecond(void)
  {
   color a_color=clrNONE;
   //--- creating  object
   m_hand_second.Create();
   //--- setting properies
   switch (m_scheme)
     {
      case black:
         a_color=m_bcolor; 
         break;
      case white:
         a_color=m_wcolor;  
         break;
      default:
         a_color=m_bcolor; 
     };
   if(!m_show_second_hand) a_color=clrNONE;
   m_hand_second.SetColor(a_color); 
   m_hand_second.SetStyle(m_secstyle);          
   m_hand_second.SetWidth(1);         
   m_hand_second.SetRay(false);           
   m_hand_second.SetBack(true);                  
   m_hand_second.SetSelected(false);             
   m_hand_second.SetSelectable(false);           
   m_hand_second.SetHidden(true);                
   m_hand_second.SetZOrder(0);                   
  }
//+------------------------------------------------------------------+
//| New position of second hand                                      |
//+------------------------------------------------------------------+
void CStockClock::HandSecondMove(void)
  {
   double angle;
   int x,y;
   int subwin=0;
   MqlDateTime stm;
   TimeToStruct(TimeGMT(),stm);
   int error_code=0;
   ResetLastError();
   //--- getting central position in datetime-price coordinates
   if(!ChartXYToTimePrice(0,m_x0,m_y0,subwin,m_dt0,m_pr0)) error_code=GetLastError();
   //--- calculating x-y position for moving hand-end along circule
   angle=stm.sec*(2*M_PI)/60;
   x=(int)(m_x0+NormalizeDouble(m_radius_sh*MathSin(angle),0));
   y=(int)(m_y0-NormalizeDouble(m_radius_sh*MathCos(angle),0));
   ResetLastError();
   //--- getting circule position in datetime-price coordinates
   if(!ChartXYToTimePrice(0,x,y,subwin,m_dt_sh,m_pr_sh)) error_code=GetLastError();
   if(error_code==0)
      m_hand_second.SetPositions(m_dt0,m_pr0,m_dt_sh,m_pr_sh);
   else
      m_hand_second.SetPositions(0,0,0,0);
  }
//+------------------------------------------------------------------+
//| New position of minute hand                                      |
//+------------------------------------------------------------------+
void CStockClock::HandMinuteMove(void)
  {
   double angle;
   int x,y;
   int subwin=0;
   MqlDateTime stm;
   TimeToStruct(TimeGMT(),stm);
   int error_code=0;
   ResetLastError();
   //--- getting central position in datetime-price coordinates
   if(!ChartXYToTimePrice(0,m_x0,m_y0,subwin,m_dt0,m_pr0)) error_code=GetLastError();
   //--- calculating x-y position for moving hand-end along circule
   angle=stm.min*(2*M_PI)/60;
   x=(int)(m_x0+NormalizeDouble(m_radius_mh*MathSin(angle),0));
   y=(int)(m_y0-NormalizeDouble(m_radius_mh*MathCos(angle),0));
   ResetLastError();
   //--- getting circule position in datetime-price coordinates
   if(!ChartXYToTimePrice(0,x,y,subwin,m_dt_mh,m_pr_mh)) error_code=GetLastError();
   if(error_code==0)
      m_hand_minute.SetPositions(m_dt0,m_pr0,m_dt_mh,m_pr_mh);
   else
      m_hand_minute.SetPositions(0,0,0,0);
  }
//+------------------------------------------------------------------+
//| New position of hour hand                                        |
//+------------------------------------------------------------------+
void CStockClock::HandHourMove(void)
  {
   double angle;
   int x,y;
   int subwin=0;
   MqlDateTime stm;
   TimeToStruct(TimeGMT(),stm);
   int error_code=0;
   ResetLastError();
   //--- getting central position in datetime-price coordinates
   if(!ChartXYToTimePrice(0,m_x0,m_y0,subwin,m_dt0,m_pr0)) error_code=GetLastError();
   //--- calculating x-y position for moving hand-end along circule
   angle=stm.hour*(2*M_PI)/24 + stm.min*(2*M_PI)/1440;
   x=(int)(m_x0+NormalizeDouble(m_radius_hh*MathSin(angle),0));
   y=(int)(m_y0-NormalizeDouble(m_radius_hh*MathCos(angle),0));
   ResetLastError();
   //--- getting circule position in datetime-price coordinates
   if(!ChartXYToTimePrice(0,x,y,subwin,m_dt_hh,m_pr_hh)) error_code=GetLastError();
   if(error_code==0)
      m_hand_hour.SetPositions(m_dt0,m_pr0,m_dt_hh,m_pr_hh);
   else
      m_hand_hour.SetPositions(0,0,0,0);
  }
//+------------------------------------------------------------------+
//| Getting the file name corresponding to "DaySavingTime-event":    |
//| Winter, Summer, when Winter time must be changed to Summer time  |
//| and so on                                                        |
//| black color scheme                                               |
//+------------------------------------------------------------------+
string CStockClock::DstEventFileBlack(void)
  {
   string file_name=m_folder+"clock_analog_error_999.bmp";
   int h60m;
   datetime time;
   MqlDateTime stmG,stm;
   if(!m_debug_on) 
     {
      time=TimeGMT();
      TimeToStruct(time,stm);
     }
   else 
     {
      time=m_tmd;   
      TimeToStruct(TimeGMT(),stmG);
      TimeToStruct(m_tmd,stm);
      stm.hour=stmG.hour;
      stm.min=stmG.min;
      stm.sec=stmG.sec;
     }
   h60m=stm.hour*60+stm.min;
   switch (m_dst_event)
     {
      //--- Winter
      case dst_111:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"111//"+"clock_analog_black_111_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"111//"+"clock_analog_black_111_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"111//"+"clock_analog_black_111_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"111//"+"clock_analog_black_111_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"111//"+"clock_analog_black_111_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"111//"+"clock_analog_black_111_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"111//"+"clock_analog_black_111_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"111//"+"clock_analog_black_111_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"111//"+"clock_analog_black_111_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"111//"+"clock_analog_black_111_1000.bmp";
         // 12:30 till 14:30
         if(h60m>=750&&h60m<870)
            file_name=m_folder+"111//"+"clock_analog_black_111_1230.bmp";
         // 14:30 till 15:00
         if(h60m>=870&&h60m<900)
            file_name=m_folder+"111//"+"clock_analog_black_111_1430.bmp";
         // 15:00 till 15:45
         if(h60m>=900&&h60m<945)
            file_name=m_folder+"111//"+"clock_analog_black_111_1500.bmp";
         // 15:45 till 16:30
         if(h60m>=945&&h60m<990)
            file_name=m_folder+"111//"+"clock_analog_black_111_1545.bmp";
         // 16:30 till 21:00
         if(h60m>=990&&h60m<1260)
            file_name=m_folder+"111//"+"clock_analog_black_111_1630.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"111//"+"clock_analog_black_111_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"111//"+"clock_analog_black_111_2300.bmp";
         break;
      //--- North America
      case dst_203:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"203//"+"clock_analog_black_203_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"203//"+"clock_analog_black_203_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"203//"+"clock_analog_black_203_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"203//"+"clock_analog_black_203_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"203//"+"clock_analog_black_203_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"203//"+"clock_analog_black_203_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"203//"+"clock_analog_black_203_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"203//"+"clock_analog_black_203_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"203//"+"clock_analog_black_203_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"203//"+"clock_analog_black_203_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"203//"+"clock_analog_black_203_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"203//"+"clock_analog_black_203_1330.bmp";
         // 15:00 till 15:45
         if(h60m>=900&&h60m<945)
            file_name=m_folder+"203//"+"clock_analog_black_203_1500.bmp";
         // 15:45 till 16:30
         if(h60m>=945&&h60m<990)
            file_name=m_folder+"203//"+"clock_analog_black_203_1545.bmp";
         // 16:30 till 20:00
         if(h60m>=990&&h60m<1200)
            file_name=m_folder+"203//"+"clock_analog_black_203_1630.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"203//"+"clock_analog_black_203_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"203//"+"clock_analog_black_203_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"203//"+"clock_analog_black_203_2300.bmp";
         break;
      //--- Europe
      case dst_403:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"403//"+"clock_analog_black_403_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"403//"+"clock_analog_black_403_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"403//"+"clock_analog_black_403_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"403//"+"clock_analog_black_403_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"403//"+"clock_analog_black_403_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"403//"+"clock_analog_black_403_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"403//"+"clock_analog_black_403_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"403//"+"clock_analog_black_403_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"403//"+"clock_analog_black_403_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"403//"+"clock_analog_black_403_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"403//"+"clock_analog_black_403_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"403//"+"clock_analog_black_403_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"403//"+"clock_analog_black_403_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"403//"+"clock_analog_black_403_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"403//"+"clock_analog_black_403_1545.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"403//"+"clock_analog_black_403_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"403//"+"clock_analog_black_403_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"403//"+"clock_analog_black_403_2300.bmp";
         break;
      //--- Summer
      case dst_104:
         // 0 till 1
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"104//"+"clock_analog_black_104_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"104//"+"clock_analog_black_104_0100.bmp";
         // 1:30 till 4:45
         if(h60m>=90&&h60m<285)
            file_name=m_folder+"104//"+"clock_analog_black_104_0130.bmp";
         // 4:45 till 6:00
         if(h60m>=285&&h60m<360)
            file_name=m_folder+"104//"+"clock_analog_black_104_0445.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"104//"+"clock_analog_black_104_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"104//"+"clock_analog_black_104_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"104//"+"clock_analog_black_104_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"104//"+"clock_analog_black_104_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"104//"+"clock_analog_black_104_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"104//"+"clock_analog_black_104_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"104//"+"clock_analog_black_104_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"104//"+"clock_analog_black_104_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"104//"+"clock_analog_black_104_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"104//"+"clock_analog_black_104_1545.bmp";
         // 20:00 till 22:00
         if(h60m>=1200&&h60m<1320)
            file_name=m_folder+"104//"+"clock_analog_black_104_2000.bmp";
         // 22:00 till 0:00
         if(h60m>=1320&&h60m<1440)
            file_name=m_folder+"104//"+"clock_analog_black_104_2200.bmp";
         break;
      //--- Wellington
      case dst_409:
         // 0 till 1
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"409//"+"clock_analog_black_409_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"409//"+"clock_analog_black_409_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"409//"+"clock_analog_black_409_0130.bmp";
         // 3:45 till 6:00
         if(h60m>=225&&h60m<360)
            file_name=m_folder+"409//"+"clock_analog_black_409_0345.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"409//"+"clock_analog_black_409_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"409//"+"clock_analog_black_409_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"409//"+"clock_analog_black_409_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"409//"+"clock_analog_black_409_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"409//"+"clock_analog_black_409_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"409//"+"clock_analog_black_409_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"409//"+"clock_analog_black_409_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"409//"+"clock_analog_black_409_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"409//"+"clock_analog_black_409_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"409//"+"clock_analog_black_409_1545.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"409//"+"clock_analog_black_409_2000.bmp";
         // 21:00 till 0:00
         if(h60m>=1260&&h60m<1440)
            file_name=m_folder+"409//"+"clock_analog_black_409_2100.bmp";
         break;
      //--- Sidney
      case dst_110:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"110//"+"clock_analog_black_110_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"110//"+"clock_analog_black_110_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"110//"+"clock_analog_black_110_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"110//"+"clock_analog_black_110_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"110//"+"clock_analog_black_110_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"110//"+"clock_analog_black_110_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"110//"+"clock_analog_black_110_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"110//"+"clock_analog_black_110_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"110//"+"clock_analog_black_110_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"110//"+"clock_analog_black_110_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"110//"+"clock_analog_black_110_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"110//"+"clock_analog_black_110_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"110//"+"clock_analog_black_110_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"110//"+"clock_analog_black_110_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"110//"+"clock_analog_black_110_1545.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"110//"+"clock_analog_black_110_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"110//"+"clock_analog_black_110_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"110//"+"clock_analog_black_110_2300.bmp";
         break;
      //--- Europe
      case dst_410:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"203//"+"clock_analog_black_203_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"203//"+"clock_analog_black_203_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"203//"+"clock_analog_black_203_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"203//"+"clock_analog_black_203_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"203//"+"clock_analog_black_203_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"203//"+"clock_analog_black_203_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"203//"+"clock_analog_black_203_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"203//"+"clock_analog_black_203_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"203//"+"clock_analog_black_203_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"203//"+"clock_analog_black_203_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"203//"+"clock_analog_black_203_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"203//"+"clock_analog_black_203_1330.bmp";
         // 15:00 till 15:45
         if(h60m>=900&&h60m<945)
            file_name=m_folder+"203//"+"clock_analog_black_203_1500.bmp";
         // 15:45 till 16:30
         if(h60m>=945&&h60m<990)
            file_name=m_folder+"203//"+"clock_analog_black_203_1545.bmp";
         // 16:30 till 20:00
         if(h60m>=990&&h60m<1200)
            file_name=m_folder+"203//"+"clock_analog_black_203_1630.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"203//"+"clock_analog_black_203_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"203//"+"clock_analog_black_203_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"203//"+"clock_analog_black_203_2300.bmp";
         break;
      case dst_999:
         file_name=m_folder+"clock_analog_error_999.bmp";
         break;
      default:
         file_name=m_folder+"clock_analog_error_999.bmp";
     };
   return(file_name);
  }
//+------------------------------------------------------------------+
//| Getting the file name corresponding to "DaySavingTime-event":    |
//| Winter, Summer, when Winter time must be changed to Summer time  |
//| and so on                                                        |
//| white color scheme                                               |
//+------------------------------------------------------------------+
string CStockClock::DstEventFileWhite(void)
  {
   string file_name=m_folder+"clock_analog_error_999.bmp";
   int h60m;
   datetime time;
   MqlDateTime stmG,stm;
   if(!m_debug_on) 
     {
      time=TimeGMT();
      TimeToStruct(time,stm);
     }
   else 
     {
      time=m_tmd;   
      TimeToStruct(TimeGMT(),stmG);
      TimeToStruct(m_tmd,stm);
      stm.hour=stmG.hour;
      stm.min=stmG.min;
      stm.sec=stmG.sec;
     }
   h60m=stm.hour*60+stm.min;
   switch (m_dst_event)
     {
      //--- Winter
      case dst_111:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"111//"+"clock_analog_white_111_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"111//"+"clock_analog_white_111_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"111//"+"clock_analog_white_111_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"111//"+"clock_analog_white_111_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"111//"+"clock_analog_white_111_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"111//"+"clock_analog_white_111_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"111//"+"clock_analog_white_111_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"111//"+"clock_analog_white_111_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"111//"+"clock_analog_white_111_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"111//"+"clock_analog_white_111_1000.bmp";
         // 12:30 till 14:30
         if(h60m>=750&&h60m<870)
            file_name=m_folder+"111//"+"clock_analog_white_111_1230.bmp";
         // 14:30 till 15:00
         if(h60m>=870&&h60m<900)
            file_name=m_folder+"111//"+"clock_analog_white_111_1430.bmp";
         // 15:00 till 15:45
         if(h60m>=900&&h60m<945)
            file_name=m_folder+"111//"+"clock_analog_white_111_1500.bmp";
         // 15:45 till 16:30
         if(h60m>=945&&h60m<990)
            file_name=m_folder+"111//"+"clock_analog_white_111_1545.bmp";
         // 16:30 till 21:00
         if(h60m>=990&&h60m<1260)
            file_name=m_folder+"111//"+"clock_analog_white_111_1630.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"111//"+"clock_analog_white_111_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"111//"+"clock_analog_white_111_2300.bmp";
         break;
      //--- North America
      case dst_203:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"203//"+"clock_analog_white_203_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"203//"+"clock_analog_white_203_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"203//"+"clock_analog_white_203_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"203//"+"clock_analog_white_203_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"203//"+"clock_analog_white_203_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"203//"+"clock_analog_white_203_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"203//"+"clock_analog_white_203_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"203//"+"clock_analog_white_203_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"203//"+"clock_analog_white_203_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"203//"+"clock_analog_white_203_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"203//"+"clock_analog_white_203_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"203//"+"clock_analog_white_203_1330.bmp";
         // 15:00 till 15:45
         if(h60m>=900&&h60m<945)
            file_name=m_folder+"203//"+"clock_analog_white_203_1500.bmp";
         // 15:45 till 16:30
         if(h60m>=945&&h60m<990)
            file_name=m_folder+"203//"+"clock_analog_white_203_1545.bmp";
         // 16:30 till 20:00
         if(h60m>=990&&h60m<1200)
            file_name=m_folder+"203//"+"clock_analog_white_203_1630.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"203//"+"clock_analog_white_203_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"203//"+"clock_analog_white_203_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"203//"+"clock_analog_white_203_2300.bmp";
         break;
      //--- Europe
      case dst_403:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"403//"+"clock_analog_white_403_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"403//"+"clock_analog_white_403_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"403//"+"clock_analog_white_403_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"403//"+"clock_analog_white_403_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"403//"+"clock_analog_white_403_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"403//"+"clock_analog_white_403_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"403//"+"clock_analog_white_403_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"403//"+"clock_analog_white_403_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"403//"+"clock_analog_white_403_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"403//"+"clock_analog_white_403_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"403//"+"clock_analog_white_403_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"403//"+"clock_analog_white_403_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"403//"+"clock_analog_white_403_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"403//"+"clock_analog_white_403_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"403//"+"clock_analog_white_403_1545.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"403//"+"clock_analog_white_403_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"403//"+"clock_analog_white_403_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"403//"+"clock_analog_white_403_2300.bmp";
         break;
      //--- Summer
      case dst_104:
         // 0 till 1
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"104//"+"clock_analog_white_104_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"104//"+"clock_analog_white_104_0100.bmp";
         // 1:30 till 4:45
         if(h60m>=90&&h60m<285)
            file_name=m_folder+"104//"+"clock_analog_white_104_0130.bmp";
         // 4:45 till 6:00
         if(h60m>=285&&h60m<360)
            file_name=m_folder+"104//"+"clock_analog_white_104_0445.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"104//"+"clock_analog_white_104_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"104//"+"clock_analog_white_104_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"104//"+"clock_analog_white_104_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"104//"+"clock_analog_white_104_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"104//"+"clock_analog_white_104_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"104//"+"clock_analog_white_104_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"104//"+"clock_analog_white_104_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"104//"+"clock_analog_white_104_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"104//"+"clock_analog_white_104_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"104//"+"clock_analog_white_104_1545.bmp";
         // 20:00 till 22:00
         if(h60m>=1200&&h60m<1320)
            file_name=m_folder+"104//"+"clock_analog_white_104_2000.bmp";
         // 22:00 till 0:00
         if(h60m>=1320&&h60m<1440)
            file_name=m_folder+"104//"+"clock_analog_white_104_2200.bmp";
         break;
      //--- Wellington
      case dst_409:
         // 0 till 1
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"409//"+"clock_analog_white_409_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"409//"+"clock_analog_white_409_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"409//"+"clock_analog_white_409_0130.bmp";
         // 3:45 till 6:00
         if(h60m>=225&&h60m<360)
            file_name=m_folder+"409//"+"clock_analog_white_409_0345.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"409//"+"clock_analog_white_409_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"409//"+"clock_analog_white_409_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"409//"+"clock_analog_white_409_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"409//"+"clock_analog_white_409_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"409//"+"clock_analog_white_409_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"409//"+"clock_analog_white_409_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"409//"+"clock_analog_white_409_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"409//"+"clock_analog_white_409_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"409//"+"clock_analog_white_409_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"409//"+"clock_analog_white_409_1545.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"409//"+"clock_analog_white_409_2000.bmp";
         // 21:00 till 0:00
         if(h60m>=1260&&h60m<1440)
            file_name=m_folder+"409//"+"clock_analog_white_409_2100.bmp";
         break;
      //--- Sidney
      case dst_110:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"110//"+"clock_analog_white_110_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"110//"+"clock_analog_white_110_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"110//"+"clock_analog_white_110_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"110//"+"clock_analog_white_110_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"110//"+"clock_analog_white_110_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"110//"+"clock_analog_white_110_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"110//"+"clock_analog_white_110_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"110//"+"clock_analog_white_110_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"110//"+"clock_analog_white_110_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"110//"+"clock_analog_white_110_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"110//"+"clock_analog_white_110_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"110//"+"clock_analog_white_110_1330.bmp";
         // 15:00 till 15:30
         if(h60m>=900&&h60m<930)
            file_name=m_folder+"110//"+"clock_analog_white_110_1500.bmp";
         // 15:30 till 15:45
         if(h60m>=930&&h60m<945)
            file_name=m_folder+"110//"+"clock_analog_white_110_1530.bmp";
         // 15:45 till 20:00
         if(h60m>=945&&h60m<1200)
            file_name=m_folder+"110//"+"clock_analog_white_110_1545.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"110//"+"clock_analog_white_110_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"110//"+"clock_analog_white_110_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"110//"+"clock_analog_white_110_2300.bmp";
         break;
      //--- Europe
      case dst_410:
         // 0:00 till 1:00
         if(h60m>=0&&h60m<60)
            file_name=m_folder+"203//"+"clock_analog_white_203_0000.bmp";
         // 1:00 till 1:30
         if(h60m>=60&&h60m<90)
            file_name=m_folder+"203//"+"clock_analog_white_203_0100.bmp";
         // 1:30 till 3:45
         if(h60m>=90&&h60m<225)
            file_name=m_folder+"203//"+"clock_analog_white_203_0130.bmp";
         // 3:45 till 5:00
         if(h60m>=225&&h60m<300)
            file_name=m_folder+"203//"+"clock_analog_white_203_0345.bmp";
         // 5:00 till 6:00
         if(h60m>=300&&h60m<360)
            file_name=m_folder+"203//"+"clock_analog_white_203_0500.bmp";
         // 6:00 till 7:00
         if(h60m>=360&&h60m<420)
            file_name=m_folder+"203//"+"clock_analog_white_203_0600.bmp";
         // 7:00 till 8:00
         if(h60m>=420&&h60m<480)
            file_name=m_folder+"203//"+"clock_analog_white_203_0700.bmp";
         // 8:00 till 9:00
         if(h60m>=480&&h60m<540)
            file_name=m_folder+"203//"+"clock_analog_white_203_0800.bmp";
         // 9:00 till 10:00
         if(h60m>=540&&h60m<600)
            file_name=m_folder+"203//"+"clock_analog_white_203_0900.bmp";
         // 10:00 till 12:30
         if(h60m>=600&&h60m<750)
            file_name=m_folder+"203//"+"clock_analog_white_203_1000.bmp";
         // 12:30 till 13:30
         if(h60m>=750&&h60m<810)
            file_name=m_folder+"203//"+"clock_analog_white_203_1230.bmp";
         // 13:30 till 15:00
         if(h60m>=810&&h60m<900)
            file_name=m_folder+"203//"+"clock_analog_white_203_1330.bmp";
         // 15:00 till 15:45
         if(h60m>=900&&h60m<945)
            file_name=m_folder+"203//"+"clock_analog_white_203_1500.bmp";
         // 15:45 till 16:30
         if(h60m>=945&&h60m<990)
            file_name=m_folder+"203//"+"clock_analog_white_203_1545.bmp";
         // 16:30 till 20:00
         if(h60m>=990&&h60m<1200)
            file_name=m_folder+"203//"+"clock_analog_white_203_1630.bmp";
         // 20:00 till 21:00
         if(h60m>=1200&&h60m<1260)
            file_name=m_folder+"203//"+"clock_analog_white_203_2000.bmp";
         // 21:00 till 23:00
         if(h60m>=1260&&h60m<1380)
            file_name=m_folder+"203//"+"clock_analog_white_203_2100.bmp";
         // 23:00 till 0:00
         if(h60m>=1380&&h60m<1440)
            file_name=m_folder+"203//"+"clock_analog_white_203_2300.bmp";
         break;
      case dst_999:
         file_name=m_folder+"clock_analog_error_999.bmp";
         break;
      default:
         file_name=m_folder+"clock_analog_error_999.bmp";
     };
   return(file_name);
  }
//+------------------------------------------------------------------+
//| Setting Day Saving Time event                                    |
//+------------------------------------------------------------------+
void CStockClock::DSTime(void)
  {
   datetime time;
   MqlDateTime stm,stm_first,stm_last;
   if(!m_debug_on) time=TimeGMT();
   else time=m_tmd;   
   TimeToStruct(time,stm);
   datetime tm_first,tm_last;
   int day_of_week,day_of_week_first,day_of_week_last,day_of_change1,day_of_change2,day_of_change_last;
   m_dst_event=dst_999;
   //--- setting first day of current month
   tm_first=time-(stm.day-1)*86400;
   tm_last=tm_first+2592000;
   if(stm.mon==4||stm.mon==9||stm.mon==11)
      tm_last=tm_first+2505600;
   TimeToStruct(tm_first,stm_first);
   TimeToStruct(tm_last,stm_last);
   //--- setting the name of the first day (Monday-1,...Sunday-7)
   if(stm_first.day_of_week!=0) day_of_week_first=stm_first.day_of_week;
   else day_of_week_first=7;
   if(stm_last.day_of_week!=0) day_of_week_last=stm_last.day_of_week;
   else day_of_week_last=7;
   if(stm.day_of_week!=0) day_of_week=stm.day_of_week;
   else day_of_week=7;

   day_of_change1=8-day_of_week_first;                                          
   day_of_change2=15-day_of_week_first;                                         
   //--- Winter in GMT Zone.
   if((stm.mon>=1 && stm.mon<=2)||stm.mon==12)      
      m_dst_event=dst_111;  
   //--- the month of changing time                              
   if(stm.mon==3)                                                          
     {     
      //--- previous event before changing
      m_dst_event=dst_111;  
      //--- America. The second Sunday of March.
      if(stm.day>=day_of_change2)            
         m_dst_event=dst_203;
      //--- Europe. The last Sunday of March.
      day_of_change_last=31-stm_last.day_of_week;
      if(stm.day>=day_of_change_last)
         m_dst_event=dst_403;
     }   
   //--- the month of changing time                              
   if(stm.mon==4)                                                 
     {   
      //--- previous event before changing
      m_dst_event=dst_403;
      //--- Wellington, Sidney. The first Sunday of April.
      if(stm.day>=day_of_change1)                           
         m_dst_event=dst_104;
     }   
   //--- Summer in GMT zone
   if(stm.mon>4 && stm.mon<9)                                              
      m_dst_event=dst_104;
   //--- The month of changing to Summer time. Wellington
   if(stm.mon==9)                                                          
     {
      //--- previous event before changing
      m_dst_event=dst_104;
      // the last Sunday of September
      day_of_change_last=30-stm_last.day_of_week;
      if(stm.day>=day_of_change_last)
         m_dst_event=dst_409;
     }
   //--- the month of changing time                              
   if(stm.mon==10)                                                         
     {
      //--- previous event before changing
      m_dst_event=dst_409;
      // The first Sunday of October. Sidnay.
      if(stm.day>=day_of_change1)
         m_dst_event=dst_110;
      // The last Sunday of October when changing to Winter time for Europe.
      day_of_change_last=31-stm_last.day_of_week;
      if(stm.day>=day_of_change_last) 
         m_dst_event=dst_410;
     }
   //--- the month of changing time                              
   if(stm.mon==11)     
     {
      //--- previous event before changing
      m_dst_event=dst_410;
      // The first Sunday of November. America.
      if(stm.day>=day_of_change1)
         m_dst_event=dst_111;
     }                                                    
  }
//+------------------------------------------------------------------+
