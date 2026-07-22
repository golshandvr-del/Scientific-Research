//+------------------------------------------------------------------+
//|                                                   CGraphBase.mqh |
//|                                                  English vertion |
//|                        Copyright 2014, MetaQuotes Software Corp. |
//|                                              http://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2014, MetaQuotes Software Corp."
#property link      "http://www.mql5.com"
#property version   "1.00"
#property strict
//+------------------------------------------------------------------+
//| CGraphBase for creating unique object in a subwindow of the chart|
//+------------------------------------------------------------------+
class CGraphBase
  {
protected:
   string m_name;                                                    // object name
   long m_id;                                                        // chart ID
   int m_subwin;                                                     // subwindow index
   bool m_delete;                                                    // удалить объект после выхода
public:
   //--- Constuctor & Destructor
   CGraphBase(string aName="",long aID=0,int aSubWin=0,bool a_delete=true);
   ~CGraphBase(void);                                  
   //--- special methods
   void Deinit(void);
   //--- Methods of creating some objects       
   bool CreateLabel(void);                                           // Creating label-object 
   bool CreateBitmap(void);                                          // Creating bitmap-object
   bool CreateBitmapLabel(void);                                     // Creating bitmap-label-object
   bool CreateBitmap(datetime aTime=0,double aPrice=0);              // Creating bitmap-object with datetime and price anchor points
   bool CreateText(datetime aTime=0,double aPrice=0);                // Creating text-object with datetime and price anchor points
   bool CreateButton(void);                                          // Creating button-object
   bool CreateEdit(void);                                            // Creating edit-object
   bool CreateVLine(void);                                           // Creating vertical_line-object
   bool CreateHLine(void);                                           // Creating horizontal line-object
   bool CreateTrend(void);                                           // Creating trend line-object
   bool CreateTrendByAngle(void);                                    // Creating trend by angle
   bool CreateEvent(void);                                           // Creating event-object
   bool CreateRectangle(void);                                       // Creating rectangle-object
   bool CreateRectangle(datetime aTime1=0,double aPrice1=0,datetime aTime2=0,double aPrice2=0);
   bool CreateRectangleLabel(void);                                  // Creating rectangle-label with using XDIST and YDIST later
   //--- Getting class variables       
   string   Name(void)               {return(m_name);}   
   long     Chart_ID(void)           {m_id=ChartID();return(m_id);}
   int      SubWindow(void)          {return(m_subwin);}
   //--- Setting object properties 
   bool SetText         (string aValue);                             // Setiing OBJPROP_TEXT
   bool SetFont         (string aValue);                             // Setiing OBJPROP_FONT
   bool SetCorner       (ENUM_BASE_CORNER aValue);                   // Setiing OBJPROP_CORNER
   bool SetFontSize     (int aValue);                                // Setiing OBJPROP_FONTSIZE
   bool SetColor        (color aValue);                              // Setiing OBJPROP_COLOR
   bool SetBgColor      (color aValue);                              // Setiing OBJPROP_BGCOLOR
   bool SetBorderColor  (color aValue);                              // Setiing OBJPROP_BORDER_COLOR
   bool SetXSize        (int aValue);                                // Setiing OBJPROP_XSIZE
   bool SetYSize        (int aValue);                                // Setiing OBJPROP_YSIZE
   bool SetXDistance    (int aValue);                                // Setiing OBJPROP_XDISTANCE
   bool SetYDistance    (int aValue);                                // Setiing OBJPROP_YDISTANCE
   bool SetSelected     (bool aValue);                               // Setiing OBJPROP_SELECTED
   bool SetSelectable   (bool aValue);                               // Setiing OBJPROP_SELECTABLE
   bool SetZOrder       (long aValue);                               // Setiing OBJPROP_ZORDER 		
   bool SetReadOnly     (bool aValue);                               // Setiing OBJPROP_READONLY           		
   bool SetAligh        (ENUM_ALIGN_MODE aValue);                    // Setiing OBJPROP_ALIGN              		
   bool SetNoTip        (string aValue);                             // Setiing OBJPROP_TOOLTIP             		
   bool SetTimeFrames   (long aValue);                               // Setiing OBJPROP_TIMEFRAMES        
   bool SetStyle        (ENUM_LINE_STYLE aValue);                    // Setiing OBJPROP_STYLE             
   bool SetWidth        (int aValue);                                // Setiing OBJPROP_WIDTH              
   bool SetAnchor       (ENUM_ANCHOR_POINT aValue);                  // Setiing OBJPROP_ANCHOR            
   bool SetBorderType   (ENUM_BORDER_TYPE aValue);                   // Setiing OBJPROP_BORDER_TYPE             
   bool SetBack         (bool aValue);                               // Setiing OBJPROP_BACK               	
   bool SetState        (bool aValue);                               // Setiing OBJPROP_STATE              
   bool SetFill         (bool aValue);                               // Setiing OBJPROP_FILL               		
   bool SetTime         (int aIndex,datetime aValue);                // Setiing OBJPROP_TIME	
   bool SetLevels       (int aValue);                                // Setiing OBJPROP_LEVELS            	
   bool SetLevelColor   (int aIndex,color aValue);                   // Setiing OBJPROP_LEVELCOLOR
   bool SetLevelStyle   (int aIndex,ENUM_LINE_STYLE aValue);         // Setiing OBJPROP_LEVELSTYLE
   bool SetLevelWidth   (int aIndex,int aValue);                     // Setiing OBJPROP_LEVELWIDTH
   bool SetRayRight     (bool aValue);                               // Setiing OBJPROP_RAY_RIGHT          		
   bool SetRay          (bool aValue);                               // Setiing OBJPROP_RAY                		
   bool SetEllipse      (bool aValue);                               // Setiing OBJPROP_ELLIPSE            			   
   bool SetArrowCode    (char aValue);                               // Setiing OBJPROP_ARROWCODE         
   bool SetDirection    (ENUM_GANN_DIRECTION aValue);                // Setiing OBJPROP_DIRECTION         
   bool SetDrawLines    (bool aValue);                               // Setiing OBJPROP_DRAWLINES          
   bool SetXOffset      (int aValue);                                // Setiing OBJPROP_XOFFSET           	
   bool SetYOffset      (int aValue);                                // Setiing OBJPROP_YOFFSET           	
   bool SetPeriod       (ENUM_TIMEFRAMES aValue);                    // Setiing OBJPROP_PERIOD            
   bool SetDateScale    (bool aValue);                               // Setiing OBJPROP_DATE_SCALE         
   bool SetPriceScale   (bool aValue);                               // Setiing OBJPROP_PRICE_SCALE        
   bool SetChartScale   (int aValue);                                // Setiing OBJPROP_CHART_SCALE       		
   bool SetPrice        (int aIndex,double aValue);                  // Setiing OBJPROP_PRICE
   bool SetLevelValue   (int aIndex,double aValue);                  // Setiing OBJPROP_LEVELVALUE
   bool SetScale        (double aValue);                             // Setiing OBJPROP_SCALE                  
   bool SetAngle        (double aValue);                             // Setiing OBJPROP_ANGLE              
   bool SetDeviation    (double aValue);                             // Setiing OBJPROP_DEVIATION          
   bool SetToolTip      (string aValue);                             // Setiing OBJPROP_TOOLTIP            
   bool SetLevelText    (int aIndex,string aValue);                  // Setiing OBJPROP_LEVELTEXT
   bool SetBmpFile      (string aValue);                             // Setiing OBJPROP_BMPFILE
   bool SetBmpFileOn    (string aValue);                             // Setiing OBJPROP_BMPFILE
   bool SetBmpFileOff   (string aValue);                             // Setiing OBJPROP_BMPFILE
   bool SetSymbol       (string aValue);                             // Setiing OBJPROP_SYMBOL 
   bool SetHidden       (bool aValue);                               // Setting OBJPROP_HIDDEN   
   bool SetTimePrice    (int aIndex,datetime aTime,double aPrice);   // Setting new Time and Price by index to point (ObjectMove)         
   //--- Getting object properties     
   color                   Color       (void)         {return( (color)                    ObjectGetInteger(m_id,m_name,OBJPROP_COLOR));}
   ENUM_LINE_STYLE         Style       (void)         {return( (ENUM_LINE_STYLE)          ObjectGetInteger(m_id,m_name,OBJPROP_STYLE));}
   int                     Width       (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_WIDTH));} 
   bool                    Back        (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_BACK));} 	
   bool                    Fill        (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_FILL));} 		
   bool                    Selected    (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_SELECTED));} 		
   bool                    ReadOnly    (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_READONLY));} 		
   ENUM_OBJECT             Type        (void)         {return( (ENUM_OBJECT)              ObjectGetInteger(m_id,m_name,OBJPROP_TYPE));}
   datetime                Time        (int aIndex)   {return( (datetime)                 ObjectGetInteger(m_id,m_name,OBJPROP_TIME,aIndex));}	
   bool                    Selectable  (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_SELECTABLE));} 		
   datetime                CreateTime  (void)         {return( (datetime)                 ObjectGetInteger(m_id,m_name,OBJPROP_CREATETIME));}	
   int                     Levels      (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_LEVELS));}	
   color                   LevelColor  (int aIndex)   {return( (color)                    ObjectGetInteger(m_id,m_name,OBJPROP_LEVELCOLOR,aIndex));}		
   ENUM_LINE_STYLE         LevelStyle  (int aIndex)   {return( (ENUM_LINE_STYLE)          ObjectGetInteger(m_id,m_name,OBJPROP_LEVELSTYLE,aIndex));}	
   int                     LevelWidth  (int aIndex)   {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_LEVELWIDTH,aIndex));}		
   int                     FontSize    (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_FONTSIZE));}		   
   bool                    RayLeft     (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_RAY_LEFT));} 	
   bool                    RayRight    (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_RAY_RIGHT));} 		
   bool                    Ray         (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_RAY));} 		
   bool                    Ellipse     (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_ELLIPSE));} 			   
   char                    ArrowCode   (void)         {return( (char)                     ObjectGetInteger(m_id,m_name,OBJPROP_ARROWCODE));}
   long                    TimeFrames  (void)         {return(                            ObjectGetInteger(m_id,m_name,OBJPROP_TIMEFRAMES));}
   long                    Anchor      (void)         {return(                            ObjectGetInteger(m_id,m_name,OBJPROP_ANCHOR));}
   int                     XDistance   (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_XDISTANCE));}	
   int                     YDistance   (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_YDISTANCE));}	
   ENUM_GANN_DIRECTION     Direction   (void)         {return( (ENUM_GANN_DIRECTION)      ObjectGetInteger(m_id,m_name,OBJPROP_DIRECTION));}
   bool                    State       (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_STATE));} 
   long                    ChartChartID(void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_CHART_ID));}
   int                     XSize       (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_XSIZE));}	
   int                     YSize       (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_YSIZE));}		
   int                     XOffset     (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_XOFFSET));}	
   int                     YOffset     (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_YOFFSET));}	
   ENUM_TIMEFRAMES         Period      (void)         {return( (ENUM_TIMEFRAMES)          ObjectGetInteger(m_id,m_name,OBJPROP_PERIOD));}
   bool                    DateScale   (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_DATE_SCALE));} 
   bool                    PriceScale  (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_PRICE_SCALE));} 
   int                     ChartScale  (void)         {return( (int)                      ObjectGetInteger(m_id,m_name,OBJPROP_CHART_SCALE));}		
   color                   BgColor     (void)         {return( (color)                    ObjectGetInteger(m_id,m_name,OBJPROP_BGCOLOR));}
   ENUM_BASE_CORNER        Corner      (void)         {return( (ENUM_BASE_CORNER)         ObjectGetInteger(m_id,m_name,OBJPROP_CORNER));}
   ENUM_BORDER_TYPE        BorderType  (void)         {return( (ENUM_BORDER_TYPE)         ObjectGetInteger(m_id,m_name,OBJPROP_BORDER_TYPE));}
   double                  Price       (int aIndex)   {return(                            ObjectGetDouble(m_id,m_name,OBJPROP_PRICE,aIndex));} 
   double                  LevelValue  (int aIndex)   {return(                            ObjectGetDouble(m_id,m_name,OBJPROP_LEVELVALUE,aIndex));}  
   double                  Scale       (void)         {return(                            ObjectGetDouble(m_id,m_name,OBJPROP_SCALE));}
   double                  Angle       (void)         {return(                            ObjectGetDouble(m_id,m_name,OBJPROP_ANGLE));}
   double                  Deviation   (void)         {return(                            ObjectGetDouble(m_id,m_name,OBJPROP_DEVIATION));}
   string                  Text        (void)         {return(                            ObjectGetString(m_id,m_name,OBJPROP_TEXT));}
   string                  ToolTip     (void)         {return(                            ObjectGetString(m_id,m_name,OBJPROP_TOOLTIP));}
   string                  LevelText   (int aIndex)   {return(                            ObjectGetString(m_id,m_name,OBJPROP_LEVELTEXT,aIndex));} 
   string                  Font        (void)         {return(                            ObjectGetString(m_id,m_name,OBJPROP_FONT));}
   string                  BmpFile     (void)         {return(                            ObjectGetString(m_id,m_name,OBJPROP_BMPFILE));}
   string                  BmpFileOn   (void)         {return(                            ObjectGetString(m_id,m_name,OBJPROP_BMPFILE,0));}
   string                  BmpFileOff  (void)         {return(                            ObjectGetString(m_id,m_name,OBJPROP_BMPFILE,1));}       
   string                  GraphSymbol (void)         {return(                            ObjectGetString(m_id,m_name,OBJPROP_SYMBOL));}  
   bool                    Hidden      (void)         {return( (bool)                     ObjectGetInteger(m_id,m_name,OBJPROP_HIDDEN));} 
//--- Getting dimentions of the chart
   int ChartWidth (void) {return((int)ChartGetInteger(m_id,CHART_WIDTH_IN_PIXELS,m_subwin));}
   int ChartHeight(void) {return((int)ChartGetInteger(m_id,CHART_HEIGHT_IN_PIXELS,m_subwin));}
   int ChartWidthWithError(void);
   int ChartHeightWithError(void);
//--- Other methods
   bool Delete(void);                                                      // Deleting Object  
   void Redraw(void){ChartRedraw(m_id);}  
  };
//+------------------------------------------------------------------+
//| Constuctor fills only main variables                             |
//+------------------------------------------------------------------+
CGraphBase::CGraphBase(string aName="",long aID=0,int aSubWin=0,bool a_delete=true)
  {
   m_name=aName;
   m_id=aID;
   m_subwin=aSubWin;
   m_delete=a_delete;
  }
//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CGraphBase::~CGraphBase(void)
  {
   if(m_delete) Deinit();
  }
//+------------------------------------------------------------------+         
//| Deinit                                                           |
//+------------------------------------------------------------------+    
void CGraphBase::Deinit(void)
  {
   if(!Delete())
      Print(__FUNCTION__,": ATTENTION! CAN NOT DELETE ",m_name);
  }     
//+------------------------------------------------------------------+         
//| Deleting object                                                  |
//+------------------------------------------------------------------+         
bool CGraphBase::Delete(void)   //{ObjectDelete(m_id,m_name);} 
  {
   ResetLastError();
   if(!ObjectDelete(m_id,m_name))
     {
      Print(__FUNCTION__,": Object Delete Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+
//| Getting width of the chart                                       |
//+------------------------------------------------------------------+         
int CGraphBase::ChartWidthWithError(void)
  {
   long result=-1;
   ResetLastError();
   if(!ChartGetInteger(m_id,CHART_WIDTH_IN_PIXELS,m_subwin,result))
      Alert(__FUNCTION__+", Error Code = ",GetLastError());
   return((int)result);
  }   
//+------------------------------------------------------------------+
//| Getting the width of the chart wth error code if error           |
//+------------------------------------------------------------------+         
int CGraphBase::ChartHeightWithError(void)
  {
   long result=-1;
   ResetLastError();
   if(!ChartGetInteger(m_id,CHART_HEIGHT_IN_PIXELS,m_subwin,result))
      Print(__FUNCTION__,": CHART_HEIGHT_IN_PIXELS. Error Code = ",GetLastError());
   return((int)result);
  }
//+------------------------------------------------------------------+         
//| Creating objects                                                 |       
//+------------------------------------------------------------------+         
bool CGraphBase::CreateLabel(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_LABEL,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_LABEL. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateButton(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_BUTTON,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_BUTTON. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateEdit(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_EDIT,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_EDIT. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateVLine(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_VLINE,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_VLINE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateHLine(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_HLINE,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_HLINE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateTrend(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_TREND,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_TREND. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateTrendByAngle(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_TRENDBYANGLE,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_TRENDBYANGLE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateEvent(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_EVENT,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_EVENT. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateRectangle(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_RECTANGLE,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_RECTANGLE(void). Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateRectangle(datetime aTime1=0,double aPrice1=0.000000,datetime aTime2=0,double aPrice2=0.000000)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_RECTANGLE,m_subwin,aTime1,aPrice1,aTime2,aPrice2))
     {
      Print(__FUNCTION__,": OBJ_RECTANGLE(times&prices). Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateRectangleLabel(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_RECTANGLE_LABEL,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_RECTANGLE_LABEL. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateBitmapLabel(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_BITMAP_LABEL,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_BITMAP_LABEL. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateBitmap(void)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_BITMAP,m_subwin,0,0))
     {
      Print(__FUNCTION__,": OBJ_BITMAP. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateBitmap(datetime aTime=0,double aPrice=0.000000)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_BITMAP,m_subwin,aTime,aPrice))
     {
      Print(__FUNCTION__,": OBJ_BITMAP. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::CreateText(datetime aTime=0,double aPrice=0.000000)
  {
   ResetLastError();
   if(!ObjectCreate(m_id,m_name,OBJ_TEXT,m_subwin,aTime,aPrice))
     {
      Print(__FUNCTION__,": OBJ_TEXT. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  } 
//+------------------------------------------------------------------+         
//| Setting properties                                               |       
//+------------------------------------------------------------------+         
bool CGraphBase::SetAligh(ENUM_ALIGN_MODE aValue)
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_ALIGN,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_ALIGN. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetAnchor(ENUM_ANCHOR_POINT aValue)
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_ANCHOR,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_ANCHOR. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetAngle(double aValue)
  {
   ResetLastError();
   if(!ObjectSetDouble(m_id,m_name,OBJPROP_ANGLE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_ANGLE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetText(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_TEXT,               aValue);}
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_TEXT,aValue))
     {
      Print(__FUNCTION__,": . Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetFont(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_FONT,               aValue);} 
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_FONT,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_TEXT. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetCorner(ENUM_BASE_CORNER aValue)//           {ObjectSetInteger(m_id,m_name,OBJPROP_CORNER,            aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_CORNER,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_CORNER. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetFontSize(int aValue)//                        {;}		   
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_FONTSIZE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_FONTSIZE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetColor(color aValue)//                      {;}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_COLOR,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_COLOR. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetBgColor(color aValue)//                      {ObjectSetInteger(m_id,m_name,OBJPROP_BGCOLOR,           aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_BGCOLOR,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_BGCOLOR. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetBorderColor(color aValue)//                      {ObjectSetInteger(m_id,m_name,OBJPROP_BORDER_COLOR,      aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_BORDER_COLOR,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_BORDER_COLOR. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetXSize(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_XSIZE,             aValue);}	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_XSIZE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_XSIZE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetYSize(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_YSIZE,             aValue);}		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_YSIZE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_YSIZE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetXDistance(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_XDISTANCE,         aValue);}	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_XDISTANCE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_XDISTANCE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetYDistance(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_YDISTANCE,         aValue);}	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_YDISTANCE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_YDISTANCE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetSelected(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_SELECTED,          aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_SELECTED,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_SELECTED. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetSelectable(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_SELECTABLE,        aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_SELECTABLE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_SELECTABLE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetZOrder(long aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_ZORDER,            aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_ZORDER,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_ZORDER. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetReadOnly(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_READONLY,          aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_READONLY,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_READONLY. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetNoTip(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_TOOLTIP,            aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_TOOLTIP,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_TOOLTIP. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetTimeFrames(long aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_TIMEFRAMES,        aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_TIMEFRAMES,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_TIMEFRAMES. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetStyle(ENUM_LINE_STYLE aValue)//            {ObjectSetInteger(m_id,m_name,OBJPROP_STYLE,             aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_STYLE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_STYLE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetWidth(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_WIDTH,             aValue);} 
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_WIDTH,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_WIDTH. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetBorderType(ENUM_BORDER_TYPE aValue)//           {ObjectSetInteger(m_id,m_name,OBJPROP_BORDER_TYPE,       aValue);}      
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_BORDER_TYPE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_BORDER_TYPE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetBack(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_BACK,              aValue);} 	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_BACK,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_BACK. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetState(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_STATE,             aValue);} 
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_STATE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_STATE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetFill(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_FILL,              aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_FILL,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_FILL. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetTime(int aIndex,datetime aValue)//        {ObjectSetInteger(m_id,m_name,OBJPROP_TIME,              aIndex,aValue);}	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_TIME,aIndex,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_TIME. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetLevels(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_LEVELS,            aValue);}	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_LEVELS,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_LEVELS. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetLevelColor(int aIndex,color aValue)//           {ObjectSetInteger(m_id,m_name,OBJPROP_LEVELCOLOR,        aIndex,aValue);}		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_LEVELCOLOR,aIndex,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_LEVELCOLOR. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetLevelStyle(int aIndex,ENUM_LINE_STYLE aValue)// {ObjectSetInteger(m_id,m_name,OBJPROP_LEVELSTYLE,        aIndex,aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_LEVELSTYLE,aIndex,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_LEVELSTYLE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetLevelWidth(int aIndex,int aValue)//             {ObjectSetInteger(m_id,m_name,OBJPROP_LEVELWIDTH,        aIndex,aValue);}		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_LEVELWIDTH,aIndex,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_LEVELWIDTH. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetRayRight(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_RAY_RIGHT,         aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_RAY_RIGHT,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_RAY_RIGHT. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetRay(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_RAY,               aValue);} 		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_RAY,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_RAY. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetEllipse(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_ELLIPSE,           aValue);} 			   
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_ELLIPSE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_ELLIPSE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetArrowCode(char aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_ARROWCODE,         aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_ARROWCODE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_ARROWCODE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetDirection(ENUM_GANN_DIRECTION aValue)//        {ObjectSetInteger(m_id,m_name,OBJPROP_DIRECTION,         aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_DIRECTION,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_DIRECTION. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetXOffset(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_XOFFSET,           aValue);}	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_XOFFSET,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_XOFFSET. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetYOffset(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_YOFFSET,aValue);}	
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_YOFFSET,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_YOFFSET. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetPeriod(ENUM_TIMEFRAMES aValue)//            {ObjectSetInteger(m_id,m_name,OBJPROP_PERIOD,aValue);}
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_PERIOD,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_PERIOD. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetDateScale(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_DATE_SCALE,aValue);} 
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_DATE_SCALE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_DATE_SCALE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetPriceScale(bool aValue)//                       {ObjectSetInteger(m_id,m_name,OBJPROP_PRICE_SCALE,aValue);} 
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_PRICE_SCALE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_PRICE_SCALE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetChartScale(int aValue)//                        {ObjectSetInteger(m_id,m_name,OBJPROP_CHART_SCALE,aValue);}		
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_CHART_SCALE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_CHART_SCALE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetPrice(int aIndex,double aValue)//          {ObjectSetDouble(m_id,m_name,OBJPROP_PRICE,aIndex,aValue);} 
  {
   ResetLastError();
   if(!ObjectSetDouble(m_id,m_name,OBJPROP_PRICE,aIndex,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_PRICE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetLevelValue(int aIndex,double aValue)//          {ObjectSetDouble(m_id,m_name,OBJPROP_LEVELVALUE,aIndex,aValue);}  
  {
   ResetLastError();
   if(!ObjectSetDouble(m_id,m_name,OBJPROP_LEVELVALUE,aIndex,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_LEVELVALUE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetScale(double aValue)//                     {ObjectSetDouble(m_id,m_name,OBJPROP_SCALE,aValue);}     
  {
   ResetLastError();
   if(!ObjectSetDouble(m_id,m_name,OBJPROP_SCALE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_SCALE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetDeviation(double aValue)//                     {ObjectSetDouble(m_id,m_name,OBJPROP_DEVIATION,aValue);}
  {
   ResetLastError();
   if(!ObjectSetDouble(m_id,m_name,OBJPROP_DEVIATION,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_DEVIATION. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetToolTip(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_TOOLTIP,aValue);}
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_TOOLTIP,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_TOOLTIP. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetLevelText(int aIndex,string aValue)//          {ObjectSetString(m_id,m_name,OBJPROP_LEVELTEXT,aIndex,aValue);} 
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_LEVELTEXT,aIndex,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_LEVELTEXT. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetBmpFile(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_BMPFILE,0,aValue);}       
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_BMPFILE,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_BMPFILE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetBmpFileOn(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_BMPFILE,0,aValue);}       
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_BMPFILE,0,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_BMPFILE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetBmpFileOff(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_BMPFILE,1,aValue);}       
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_BMPFILE,1,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_BMPFILE. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetSymbol(string aValue)//                     {ObjectSetString(m_id,m_name,OBJPROP_SYMBOL,aValue);}  
  {
   ResetLastError();
   if(!ObjectSetString(m_id,m_name,OBJPROP_SYMBOL,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_SYMBOL. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetHidden(bool aValue)
  {
   ResetLastError();
   if(!ObjectSetInteger(m_id,m_name,OBJPROP_HIDDEN,aValue))
     {
      Print(__FUNCTION__,": OBJPROP_HIDDEN. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         
bool CGraphBase::SetTimePrice(int aIndex,datetime aTime,double aPrice)
  {
   ResetLastError();
   if(!ObjectMove(m_id,m_name,aIndex,aTime,aPrice))
     {
      Print(__FUNCTION__,": ObjectMove. Error Code = ",GetLastError());
      return(false);
     }
   return(true);
  }
//+------------------------------------------------------------------+         



