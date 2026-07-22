//+------------------------------------------------------------------+
//|                                                  CGTrendline.mqh |
//|                        Copyright 2015, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2015, MetaQuotes Software Corp."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict
#include "CGraphBase.mqh"
//+------------------------------------------------------------------+
//|  Класс для работы с трендовой линией (Trendline)                 |
//+------------------------------------------------------------------+
class CGTrendline
  {
private:
   string            m_name;                                               // object name
   long              m_id;                                                 // chart ID
   int               m_subwin;                                             // subwindow index
   bool              m_created;                                            // true if object created
   //
   datetime          m_time1;                                              // первая (левая) координата времени
   double            m_price1;                                             // первая (левая) координата цены
   datetime          m_time2;                                              // вторая (правая) координата времени
   double            m_price2;                                             // вторая (правая) координата цены
   color             m_color;                                              // цвет трендовой линии
   ENUM_LINE_STYLE   m_style;                                              // стиль трендовой линии
   int               m_width;                                              // толщина трендовой линии
   bool              m_back;                                               // на заднем плане
   bool              m_selected;                                           // выделить для перемещений
   bool              m_selectable;                                         // возможность выделения
   bool              m_ray_right;                                          // продолжение линии вправо
   bool              m_hidden;                                             // скрыт в списке объектов
   long              m_zorder;                                             // приоритет на нажатие мышью
   CGraphBase        *m_graph_base;                                        // pointer to CGraphPrimitives
public:
   CGTrendline(string aName,long aID=0,int aSubWin=0);
   ~CGTrendline();
   // сеттеры
   void              Create(void);                                         // создание трендовой линии
   void              DeleteTrend(void);                                    // удаление трендовой линии                                             
   void              SetLeftPos(datetime aTime,double aPrice);             // установка левых координат
   void              SetRightPos(datetime aTime,double aPrice);            // установка правых координат
   void              SetPositions(datetime aTime1,double aPrice1,datetime aTime2,double aPrice2);
   void              SetColor(color aColor=clrRed);                        // установка цвета
   void              SetStyle(ENUM_LINE_STYLE aStyle=STYLE_SOLID);         // установка стиля
   void              SetWidth(int aWidth=1);                               // установка толщины линии
   void              SetBack(bool aValue=false);                           // передний план по умолчанию
   void              SetSelected(bool aValue=false);                       // выделение объекта
   void              SetSelectable(bool aValue=true);                      // установка возможности выделения
   void              SetRay(bool aValue=false);                            // setting rays right/left
   void              SetHidden(bool aValue=false);                         // наличие в списке объектов
   void              SetZOrder(long aValue=0);                             // уставка приоритета нажатия мышью
   // геттеры
   string            Name(void) {return(m_name);}                          // получить имя
   bool              Selected(void);                                       // получить признак выбранности
   double            PriceByTime(datetime aTime);                          // получить значение цены по времени
  };
//+------------------------------c------------------------------------+
//| Конструктор                                                      |
//+------------------------------------------------------------------+
CGTrendline::CGTrendline(string aName,long aID=0,int aSubWin=0)
  {
   m_created=false;
   m_name=aName;
   m_id=aID;
   m_subwin=aSubWin;
   m_graph_base=new CGraphBase(m_name,m_id,m_subwin,true);
  }
//+------------------------------------------------------------------+
//| Создание объекта TrendLine                                       |
//+------------------------------------------------------------------+
void CGTrendline::Create(void)
  {
   m_created=false;
   if(m_graph_base.CreateTrend())
      m_created=true;
  }
//+------------------------------------------------------------------+
//| Деструктор                                                       |
//+------------------------------------------------------------------+
CGTrendline::~CGTrendline()
  {
   delete m_graph_base;
  }
//+------------------------------------------------------------------+
//| Установка левых координат                                        |
//+------------------------------------------------------------------+
void CGTrendline::SetLeftPos(datetime aTime,double aPrice)
  {
   if(m_created)
     {
      m_time1=aTime;
      m_price1=aPrice;
      m_graph_base.SetTimePrice(0,m_time1,m_price1);
     }
  }
//+------------------------------------------------------------------+
//| Установка правых координат                                       |
//+------------------------------------------------------------------+
void CGTrendline::SetRightPos(datetime aTime,double aPrice)
  {
   if(m_created)
     {
      m_time2=aTime;
      m_price2=aPrice;
      m_graph_base.SetTimePrice(1,m_time2,m_price2);
     }
  }
//+------------------------------------------------------------------+
//| Установка всех координат                                         |
//+------------------------------------------------------------------+
void CGTrendline::SetPositions(datetime aTime1,double aPrice1,datetime aTime2,double aPrice2)
  {
   SetLeftPos(aTime1,aPrice1);
   SetRightPos(aTime2,aPrice2);
  }
//+------------------------------------------------------------------+
//| Удаление трендовой линии                                         |
//+------------------------------------------------------------------+
void CGTrendline::DeleteTrend(void)
  {
   if(m_created)
      m_graph_base.Delete();
  }
//+------------------------------------------------------------------+
//| Установка цвета                                                  |
//+------------------------------------------------------------------+
void CGTrendline::SetColor(color aColor=255)
  {
   if(m_created)
     {
      //Print("Установка цвета.");
      m_color=aColor;
      m_graph_base.SetColor(m_color);
     }
  }
//+------------------------------------------------------------------+
//| Setting Rays right/left                                          |
//+------------------------------------------------------------------+
void CGTrendline::SetRay(bool aValue=false)
  {
   if(m_created)
     {
      m_ray_right=aValue;
      m_graph_base.SetRayRight(m_ray_right);
     }
  }
//+------------------------------------------------------------------+
//| Установка стиля                                                  |
//+------------------------------------------------------------------+
void CGTrendline::SetStyle(ENUM_LINE_STYLE aStyle=0)
  {
   if(m_created)
     {
      //Print("Установка стиля.");
      m_style=aStyle;
      m_graph_base.SetStyle(m_style);
     }
  }
//+------------------------------------------------------------------+
//| Установка ширины                                                 |
//+------------------------------------------------------------------+
void CGTrendline::SetWidth(int aWidth=1)
  {
   if(m_created)
     {
      m_width=aWidth;
      m_graph_base.SetWidth(m_width);
     }
  }
//+------------------------------------------------------------------+
//| Установка на передний/задний план                                |
//+------------------------------------------------------------------+
void CGTrendline::SetBack(bool aValue=false)
  {
   if(m_created)
     {
      m_back=aValue;
      m_graph_base.SetBack(m_back);
     }
  }
//+------------------------------------------------------------------+
//| Установка выделения                                              |
//+------------------------------------------------------------------+
void CGTrendline::SetSelected(bool aValue=false)
  {
   if(m_created)
     {
      m_selected=aValue;
      m_graph_base.SetSelected(m_selected);
     }
  }
//+------------------------------------------------------------------+
//| Установка возможности выделения                                  |
//+------------------------------------------------------------------+
void CGTrendline::SetSelectable(bool aValue=true)
  {
   if(m_created)
     {
      m_selectable=aValue;
      m_graph_base.SetSelectable(m_selectable);
     }
  }
//+------------------------------------------------------------------+
//| Установка наличия в списке объектов                              |
//+------------------------------------------------------------------+
void CGTrendline::SetHidden(bool aValue=false)
  {
   if(m_created)
     {
      m_hidden=aValue;
      m_graph_base.SetHidden(m_hidden);
     }
  }
//+------------------------------------------------------------------+
//| Установка приоритета на щелчок мыши                              |
//+------------------------------------------------------------------+
void CGTrendline::SetZOrder(long aValue=0)
  {
   if(m_created)
     {
      m_zorder=aValue;
      m_graph_base.SetZOrder(m_zorder);
     }
  }
//+------------------------------------------------------------------+
