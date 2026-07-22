//+------------------------------------------------------------------+
//|                                                     CGButton.mqh |
//|                        Copyright 2014, MetaQuotes Software Corp. |
//|                                              http://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2014, MetaQuotes Software Corp."
#property link      "http://www.mql5.com"
#property version   "1.00"
#property strict
#include "CGraphBase.mqh"
//+------------------------------------------------------------------+
//| Class CGButton                                                   |
//+------------------------------------------------------------------+
class CGButton
  {
private:
   string   m_name;                                                        // object name
   long     m_id;                                                          // chart ID
   int      m_subwin;                                                      // subwindow index
   bool     m_created;                                                     // true if object created
   //
   int      m_xdist;                                                       // x-distance from the corner
   int      m_ydist;                                                       // y-distance from the corner
   int      m_xsize;                                                       // button width
   int      m_ysize;                                                       // button hight
   color    m_color_fg;                                                    // foreground color
   color    m_color_bg;                                                    // background color
   color    m_color_bd;                                                    // border color
   string   m_text;                                                        // button text
   uchar    m_char;                                                        // button char
   ENUM_BASE_CORNER m_corner;                                              // corner of connection
   string   m_fontname;                                                    // font name
   bool     m_state;                                                       // button state
   int      m_fontsize;                                                    // font size
   bool     m_selected;                                                    // to select the object
   bool     m_selectable;                                                  // to be selectable
   bool     m_back;                                                        // fore/background
   bool     m_readonly;                                                    // read only state
   long     m_zorder;                                                      // click priority
   bool     m_hidden;                                                      // not to show in the object list
   // pointer to the used class
   CGraphBase  *m_graph_base;                                              // pointer to CGraphBase
public:
   CGButton(string aName="Button_",long aID=0,int aSubWin=0);
   ~CGButton(void);
   void  Create(void);                                                     // creating object
   // settings
   void  SetXDist(int aDist=10);                                           // setting DistanceX
   void  SetYDist(int aDist=15);                                           // setting DistanceY
   void  SetXSize(int aSize=10);                                           // setting width
   void  SetYSize(int aSize=10);                                           // setting height
   void  SetBack(bool aBack=false);                                        // setting for/background
   void  SetState(bool aState=true);                                       // setting "on/off" state
   void  SetChar(uchar aChar=73);                                          // setting Windings symbol
   void  SetText(string aText="");                                         // setting button text
   void  SetColorFG(color aColor=clrWhite);                                // setting foreground color
   void  SetColorBG(color aColor=clrFireBrick);                            // setting background color
   void  SetColorBD(color aColor=clrSnow);                                 // setting border color
   void  SetCorner(ENUM_BASE_CORNER aCorner=CORNER_LEFT_UPPER);            // setting corner of connection
   void  SetFontName(string aFont="Windings");                             // setting font name
   void  SetFontSize(int aSize=8);                                         // setting font size
   void  SetSelected(bool aValue=false);                                   // setting selected state
   void  SetSelectable(bool aValue=false);                                 // setting selectable state
   void  SetHidden(bool aValue=true);                                      // setting headen in the object list state
   // getting
   string NameObj(void) {return(m_name);}                                  // getting object name
   bool State(void) {return(m_graph_base.State());}                                     // getting button state
   int  XDistance(void) {return(m_xdist);}                                 // getting x_distance
   int  YDistance(void) {return(m_ydist);}                                 // getting y_distance
   // pointer
   CGraphBase  *PtrGraphBase(void) {return(m_graph_base);}                  
  };
//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CGButton::CGButton(string aName="Button_",long aID=0,int aSubWin=0)
  {
   m_name=aName;
   m_id=aID;
   m_subwin=aSubWin;
   m_graph_base=new CGraphBase(m_name,m_id,m_subwin);
  }
//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CGButton::~CGButton(void)
  {
   //m_graph_base.Delete();
   delete(m_graph_base);
  }
//+------------------------------------------------------------------+
//| Creating object                                                  |
//+------------------------------------------------------------------+
void CGButton::Create(void)
  {
   m_created=false;
   if(m_graph_base.CreateButton())
      m_created=true;
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_XDISTANCE                               |
//+------------------------------------------------------------------+
void CGButton::SetXDist(int aDist=10)
  {
   if(m_created)
     {
      m_xdist=aDist;
      m_graph_base.SetXDistance(m_xdist);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_YDISTANCE                               |
//+------------------------------------------------------------------+
void CGButton::SetYDist(int aDist=15)
  {
   if(m_created)
     {
      m_ydist=aDist;
      m_graph_base.SetYDistance(m_ydist);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_XSIZE                                   |
//+------------------------------------------------------------------+
void CGButton::SetXSize(int aSize=10)
  {
   if(m_created)
     {
      m_xsize=aSize;
      m_graph_base.SetXSize(m_xsize);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_YSIZE                                   |
//+------------------------------------------------------------------+
void CGButton::SetYSize(int aSize=10)
  {
   if(m_created)
     {
      m_ysize=aSize;
      m_graph_base.SetYSize(m_ysize);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_BACK                                    |
//+------------------------------------------------------------------+
void CGButton::SetBack(bool aBack=false)
  {
   if(m_created)
     {
      m_back=aBack;
      m_graph_base.SetBack(m_back);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_TEXT                                    |
//+------------------------------------------------------------------+
void CGButton::SetText(string aText="")
  {
   if(m_created)
     {
      m_text=aText;
      m_graph_base.SetText(m_text);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_TEXT                                    |
//+------------------------------------------------------------------+
void CGButton::SetChar(uchar aChar=73)
  {
   if(m_created)
     {
      m_char=aChar;
      m_graph_base.SetText(CharToString(m_char));
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_STATE                                   |
//+------------------------------------------------------------------+
void CGButton::SetState(bool aState=true)
  {
   if(m_created)
     {
      m_state=aState;
      m_graph_base.SetState(m_state);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_COLOR                                   |
//+------------------------------------------------------------------+
void CGButton::SetColorFG(color aColor=clrWhite)
  {
   if(m_created)
     {
      m_color_fg=aColor;
      m_graph_base.SetColor(m_color_fg);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_BGCOLOR                                 |
//+------------------------------------------------------------------+
void CGButton::SetColorBG(color aColor=clrFireBrick)
  {
   if(m_created)
     {
      m_color_bg=aColor;
      m_graph_base.SetBgColor(m_color_bg);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_BORDER_COLOR                            |
//+------------------------------------------------------------------+
void CGButton::SetColorBD(color aColor=clrSnow)
  {
   if(m_created)
     {
      m_color_bd=aColor;
      m_graph_base.SetBorderColor(m_color_bd);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_CORNER                                  |
//+------------------------------------------------------------------+
void CGButton::SetCorner(ENUM_BASE_CORNER aCorner=0)
  {
   if(m_created)
     {
      m_corner=aCorner;
      m_graph_base.SetCorner(m_corner);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_FONT                                    |
//+------------------------------------------------------------------+
void CGButton::SetFontName(string aFont="Windings")
  {
   if(m_created)
     {
      m_fontname=aFont;
      m_graph_base.SetFont(m_fontname);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_FONTSIZE                                |
//+------------------------------------------------------------------+
void CGButton::SetFontSize(int aSize=8)
  {
   if(m_created)
     {
      m_fontsize=aSize;
      m_graph_base.SetFontSize(m_fontsize);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_SELECTED                                |
//+------------------------------------------------------------------+
void CGButton::SetSelected(bool aValue=false)
  {
   if(m_created)
     {
      m_selected=aValue;
      m_graph_base.SetSelected(m_selected);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_SELECTABLE                              |
//+------------------------------------------------------------------+
void CGButton::SetSelectable(bool aValue=false)
  {
   if(m_created)
     {
      m_selectable=aValue;
      m_graph_base.SetSelectable(m_selectable);
     }
  }
//+------------------------------------------------------------------+
//| Setting property OBJPROP_HIDDEN                                  |
//+------------------------------------------------------------------+
void CGButton::SetHidden(bool aValue=true)
  {
   if(m_created)
     {
      m_hidden=aValue;
      m_graph_base.SetHidden(m_hidden);
     }
  }
//+------------------------------------------------------------------+



