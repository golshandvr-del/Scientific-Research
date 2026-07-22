//+------------------------------------------------------------------+
//|                                                      CGLabel.mqh |
//|                        Copyright 2014, MetaQuotes Software Corp. |
//|                                              http://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2014, MetaQuotes Software Corp."
#property link      "http://www.mql5.com"
#property version   "1.00"
#property strict
#include "CGraphBase.mqh"
//+------------------------------------------------------------------+
//| Class CGLabel can be used in the tester                          |
//+------------------------------------------------------------------+
class CGLabel
  {
private:
   string   m_name;                                                        // object name
   long     m_id;                                                          // chart ID
   int      m_subwin;                                                      // subwindow index
   bool     m_created;                                                     // true if object created
   //
   int      m_xdist;                                                       // x-distance from the corner
   int      m_ydist;                                                       // y-distance from the corner
   color    m_color_fg;                                                    // text color
   string   m_text;                                                        // label text
   ENUM_BASE_CORNER m_corner;                                              // corner of connection
   ENUM_ANCHOR_POINT m_anchor;                                             // anchor point
   double   m_angle;                                                       // angle of the label
   string   m_fontname;                                                    // font name
   int      m_fontsize;                                                    // font size
   bool     m_selected;                                                    // to select the object
   bool     m_selectable;                                                  // to be selectable
   bool     m_back;                                                        // fore/background
   long     m_zorder;                                                      // click priority
   bool     m_hidden;                                                      // not to show in the object list
   // pointer to the used class
   CGraphBase  *m_graph_base;                                              // pointer to CGraphBase
public:
   CGLabel(string aName="Label_",long aID=0,int aSubWin=0);
   ~CGLabel(void);
   void  Create(void);                                                     // creating object
   // Settings and movings
   void  SetXDist(int aDist=10);                                           // x-distance from the corner
   void  SetYDist(int aDist=15);                                           // y-distance from the corner
   void  SetColorText(color aColor=clrYellow);                             // text color
   void  SetText(string aText="LABEL_");                                   // text property
   void  SetCorner(ENUM_BASE_CORNER aCorner=CORNER_LEFT_UPPER);            // corner
   void  SetAnchor(ENUM_ANCHOR_POINT anAnchor=ANCHOR_LEFT_UPPER);          // anchor point
   void  SetAngle(double anAngle=0);                                       // angle of the label
   void  SetFontName(string aFont="Calibri");                              // font name
   void  SetFontSize(int aSize=8);                                         // font size
   void  SetSelected(bool aValue=false);                                   // to select the object
   void  SetSelectable(bool aValue=false);                                 // to be selectable
   void  SetBack(bool aBack=false);                                        // fore/background
   void  SetZOrder(long aOrder=0);                                         // click priority
   void  SetHidden(bool aHidden=true);                                     // not to show in the object list
   //
   bool  MoveXY(int aPosX=0,int aPosY=0);                                  // moving the object 
   bool  MoveX(int aPosX=0);                                               // moving the object 
   bool  MoveY(int aPosY=0);                                               // moving the object 
   // Gettings
   string Name(void)                   {return(m_name);}                   // getting object name
   int    XDist(void)                  {return(m_xdist);}                  // x-distance from the corner
   int    YDist(void)                  {return(m_ydist);}                  // y-distance from the corner
   color  ColorText(void)              {return(m_color_fg);}               // text color
   string Text(void)                   {return(m_text);}                   // text property
   ENUM_BASE_CORNER Corner(void)       {return(m_corner);}                 // corner
   ENUM_ANCHOR_POINT Anchor(void)      {return(m_anchor);}                 // anchor point
   double Angle(void)                  {return(m_angle);}                  // angle of the label
   string FontName(void)               {return(m_fontname);}               // font name
   int    FontSize(void)               {return(m_fontsize);}               // font size
   bool   Selected(void)               {return(m_selected);}               // to select the object
   bool   Selectable(void)             {return(m_selectable);}             // to be selectable
   bool   Back(void)                   {return(m_back);}                   // fore/background
   long   ZOrder(void)                 {return(m_zorder);}                 // click priority
   bool   Hidden(bool aHidden=true)    {return(m_hidden);}                 // not to show in the object list
   // Other methods
   CGraphBase *PtrGraphBase(void)      {return(m_graph_base);}             // get the pointer to CGraphBase
   bool  Created(void)                 {return(m_created);}                // checking creating of the object
   void  ReDraw(void) {m_graph_base.Redraw();}                             // redraw graph
  };
//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CGLabel::CGLabel(string aName="Label_",long aID=0,int aSubWin=0)
  {
   m_created=false;
   m_name=aName;
   m_id=aID;
   m_subwin=aSubWin;
   m_graph_base=new CGraphBase(m_name,m_id,m_subwin);
  }
//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CGLabel::~CGLabel(void)
  {
   delete(m_graph_base);
  }
//+------------------------------------------------------------------+
//| Creating object                                                  |
//+------------------------------------------------------------------+
void CGLabel::Create(void)
  {
   m_created=false;
   if(m_graph_base.CreateLabel())
      m_created=true;
  }
//+------------------------------------------------------------------+
//| Setting OBJPROP_XDISTANCE                                        |
//+------------------------------------------------------------------+
void CGLabel::SetXDist(int aDist=10)
  {
   if(m_created)
     {
      m_xdist=aDist;
      m_graph_base.SetXDistance(m_xdist);
     }
  }
//+------------------------------------------------------------------+
//| Setting OBJPROP_YDISTANCE                                        |
//+------------------------------------------------------------------+
void CGLabel::SetYDist(int aDist=15)
  {
   if(m_created)
     {
      m_ydist=aDist;
      m_graph_base.SetYDistance(m_ydist);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_BACK                                            |
//+------------------------------------------------------------------+
void CGLabel::SetBack(bool aBack=false)
  {
   if(m_created)
     {
      m_back=aBack;
      m_graph_base.SetBack(m_back);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_ZORDER                                          |
//+------------------------------------------------------------------+
void CGLabel::SetZOrder(long aOrder=0)
  {
   if(m_created)
     {
      m_zorder=aOrder;
      m_graph_base.SetZOrder(m_zorder);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_COLOR                                           |
//+------------------------------------------------------------------+
void CGLabel::SetColorText(color aColor=65535)
  {
   if(m_created)
     {
      m_color_fg=aColor;
      m_graph_base.SetColor(m_color_fg);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_TEXT                                            |
//+------------------------------------------------------------------+
void CGLabel::SetText(string aText="LABEL_")
  {
   if(m_created)
     {
      m_text=aText;
      m_graph_base.SetText(m_text);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_CORNER                                          |
//+------------------------------------------------------------------+
void CGLabel::SetCorner(ENUM_BASE_CORNER aCorner=0)
  {
   if(m_created)
     {
      m_corner=aCorner;
      m_graph_base.SetCorner(m_corner);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_ANCHOR                                          |
//+------------------------------------------------------------------+
void CGLabel::SetAnchor(ENUM_ANCHOR_POINT anAnchor=0)
  {
   if(m_created)
     {
      m_anchor=anAnchor;
      m_graph_base.SetAnchor(m_anchor);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_ANGLE                                           |
//+------------------------------------------------------------------+
void CGLabel::SetAngle(double anAngle=0.000000)
  {
   if(m_created)
     {
      m_angle=anAngle;
      m_graph_base.SetAngle(m_angle);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_FONT                                            |
//+------------------------------------------------------------------+
void CGLabel::SetFontName(string aFont="Calibri")
  {
   if(m_created)
     {
      m_fontname=aFont;
      m_graph_base.SetFont(m_fontname);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_FONTSIZE                                        |
//+------------------------------------------------------------------+
void CGLabel::SetFontSize(int aSize=8)
  {
   if(m_created)
     {
      m_fontsize=aSize;
      m_graph_base.SetFontSize(m_fontsize);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_SELECTED                                        |
//+------------------------------------------------------------------+
void CGLabel::SetSelected(bool aValue=false)
  {
   if(m_created)
     {
      m_selected=aValue;
      m_graph_base.SetSelected(m_selected);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_SELECTABLE                                      |
//+------------------------------------------------------------------+
void CGLabel::SetSelectable(bool aValue=false)
  {
   if(m_created)
     {
      m_selectable=aValue;
      m_graph_base.SetSelectable(m_selectable);
     }
  }
//+------------------------------------------------------------------+
//| Setting  OBJPROP_HIDDEN                                          |
//+------------------------------------------------------------------+
void CGLabel::SetHidden(bool aHidden=true)
  {   
   if(m_created)
     {
      m_hidden=aHidden;
      m_graph_base.SetHidden(m_hidden);
     }
  }
//+------------------------------------------------------------------+
//| Moving the Object to the new X Y position                        |
//+------------------------------------------------------------------+
bool CGLabel::MoveXY(int aPosX=0,int aPosY=0)
  {
   ResetLastError();
   if(!m_graph_base.SetXDistance(aPosX))
     {
      Print(__FUNCTION__,": Cannot move to X! Error code:",GetLastError());
      return(false);
     }
   if(!m_graph_base.SetYDistance(aPosY))
     {
      Print(__FUNCTION__,": Cannot move to Y! Error code:",GetLastError());
      return(false);
     }
   m_xdist=aPosX;
   m_ydist=aPosY;
   return(true);
  }
//+------------------------------------------------------------------+
//| Moving the Object to the new X position                          |
//+------------------------------------------------------------------+
bool CGLabel::MoveX(int aPosX=0)
  {
   ResetLastError();
   if(!m_graph_base.SetXDistance(aPosX))
     {
      Print(__FUNCTION__,": Cannot move to X! Error code:",GetLastError());
      return(false);
     }
   m_xdist=aPosX;
   return(true);
  }
//+------------------------------------------------------------------+
//| Moving the Object to the new Y position                          |
//+------------------------------------------------------------------+
bool CGLabel::MoveY(int aPosY=0)
  {
   ResetLastError();
   if(!m_graph_base.SetYDistance(aPosY))
     {
      Print(__FUNCTION__,": Cannot move to Y! Error code:",GetLastError());
      return(false);
     }
   m_ydist=aPosY;
   return(true);
  }
//+------------------------------------------------------------------+


