//+------------------------------------------------------------------+
//|                                                CGBitmapLabel.mqh |
//|                        Copyright 2015, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2015, MetaQuotes Software Corp."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict
#include "CGraphBase.mqh"
//+------------------------------------------------------------------+
//| Class for creating Bitmap Label object                           |
//+------------------------------------------------------------------+
class CGBitmapLabel
  {
private:
   string            m_name;                                               // object name
   long              m_id;                                                 // chart ID
   int               m_subwin;                                             // subwindow index
   bool              m_created;                                            // true if object created
   //
   string            m_file_on;                                            // on-state picture
   string            m_file_off;                                           // off-state picture
   int               m_xdist;                                              // x-distance from the corner
   int               m_ydist;                                              // y-distance from the corner
   int               m_xsize;                                              // object width
   int               m_ysize;                                              // object height
   int               m_xoffset;                                            // range of visibility
   int               m_yoffset;                                            // range of visibility
   bool              m_state;                                              // pressed (on/off)
   ENUM_BASE_CORNER  m_corner;                                             // corner of connection
   ENUM_ANCHOR_POINT m_anchor;                                             // anchor point
   color             m_colorBD;                                            // border color
   ENUM_LINE_STYLE   m_style;                                              // border style
   int               m_point_width;                                        // anchor point size
   bool              m_back;                                               // fore/background
   bool              m_selected;                                           // to select the object
   bool              m_selectable;                                         // to be selectable
   long              m_zorder;                                             // click priority
   bool              m_hidden;                                             // not to show in the object list
   // pointer to the used class
   CGraphBase        *m_graph_base;                                        // pointer to CGraphBase

public:
   CGBitmapLabel(string aName="BitmapLabel_",string file_on="",string file_off="",long aID=0,int aSubWin=0);
   ~CGBitmapLabel();
   void              Create(void);                                         // creating object
   // Settings
   void              SetFileOn(string value);                              // on-state picture
   void              SetFileOff(string value);                             // off-state picture
   void              SetXDist(int value);                                  // x-distance from the corner
   void              SetYDist(int value);                                  // y-distance from the corner
   void              SetXSize(int value);                                  // object width
   void              SetYSize(int value);                                  // object height
   void              SetXOffset(int value);                                // range of visibility
   void              SetYOffset(int value);                                // range of visibility
   void              SetState(bool value);                                 // pressed (on/off)
   void              SetCorner(ENUM_BASE_CORNER value);                    // corner of connection
   void              SetAnchor(ENUM_ANCHOR_POINT value);                   // anchor point
   void              SetColor(color value);                              // border color
   void              SetStyle(ENUM_LINE_STYLE value);                      // border style
   void              SetPointWidth(int value);                             // anchor point size
   void              SetBack(bool value);                                  // fore/background
   void              SetSelected(bool value);                              // to select the object
   void              SetSelectable(bool value);                            // to be selectable
   void              SetZOrder(long value);                                // z-order
   void              SetHidden(bool value);                                // not to show in the object list
   // Gettings
   string            GetFileOn(void);                                      // get on-state picture
   string            GetFileOff(void);                                     // get off-state picture
  };
//+------------------------------------------------------------------+
//| Constructor                                                      |
//+------------------------------------------------------------------+
CGBitmapLabel::CGBitmapLabel(string aName="BitmapLabel_",string file_on="",string file_off="",long aID=0,int aSubWin=0)
  {
   m_created=false;
   m_file_on=file_on;
   m_file_off=file_off;
   m_name=aName;
   m_id=aID;
   m_subwin=aSubWin;
   m_graph_base=new CGraphBase(m_name,m_id,m_subwin);
  }
//+------------------------------------------------------------------+
//| Destructor                                                       |
//+------------------------------------------------------------------+
CGBitmapLabel::~CGBitmapLabel()
  {
   delete m_graph_base;
  }
//+------------------------------------------------------------------+
//| Creating object                                                  |
//+------------------------------------------------------------------+
void CGBitmapLabel::Create(void)
  {
   m_created=false;
   if(m_graph_base.CreateBitmapLabel())
      m_created=true;
  }
//+------------------------------------------------------------------+
//| set on-state picture                                             |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetFileOn(string value)
  {
   if(m_created)
     {
      m_file_on=value;
      m_graph_base.SetBmpFileOn(m_file_on);
     }
  }
//+------------------------------------------------------------------+
//| set off-state picture                                            |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetFileOff(string value)
  {
   if(m_created)
     {
      m_file_off=value;
      m_graph_base.SetBmpFileOff(m_file_on);
     }
  }
//+------------------------------------------------------------------+
//| x-distance from the corner                                       |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetXDist(int value)
  {
   if(m_created)
     {
      m_xdist=value;
      m_graph_base.SetXDistance(m_xdist);
     }
  }
//+------------------------------------------------------------------+
//| y-distance from the corner                                       |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetYDist(int value)                                  
  {
   if(m_created)
     {
      m_ydist=value;
      m_graph_base.SetYDistance(m_ydist);
     }
  }
//+------------------------------------------------------------------+
//|  object width                                                    |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetXSize(int value)
  {
   if(m_created)
     {
      m_xsize=value;
      m_graph_base.SetXSize(m_xsize);
     }
  }
//+------------------------------------------------------------------+
//|  object height                                                   |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetYSize(int value)
  {
   if(m_created)
     {
      m_ysize=value;
      m_graph_base.SetYSize(m_ysize);
     }
  }
//+------------------------------------------------------------------+
//| range of visibility                                              |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetXOffset(int value)
  {
   if(m_created)
     {
      m_xoffset=value;
      m_graph_base.SetXOffset(m_xoffset);
     }
  }
//+------------------------------------------------------------------+
//| range of visibility                                              |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetYOffset(int value)
  {
   if(m_created)
     {
      m_yoffset=value;
      m_graph_base.SetYOffset(m_yoffset);
     }
  }
//+------------------------------------------------------------------+
//| pressed (on/off)                                                 |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetState(bool value)
  {
   if(m_created)
     {
      m_state=value;
      m_graph_base.SetState(m_state);
     }
  }
//+------------------------------------------------------------------+
//| corner of connection                                             |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetCorner(ENUM_BASE_CORNER value)
  {
   if(m_created)
     {
      m_corner=value;
      m_graph_base.SetColor(m_corner);
     }
  }
//+------------------------------------------------------------------+
//| anchor point                                                     |
//+------------------------------------------------------------------+
void  CGBitmapLabel::SetAnchor(ENUM_ANCHOR_POINT value)
  {
   if(m_created)
     {
      m_anchor=value;
      m_graph_base.SetAnchor(m_anchor);
     }
  }
//+------------------------------------------------------------------+
//| border color                                                     |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetColor(color value)
  {
   if(m_created)
     {
      m_colorBD=value;
      m_graph_base.SetColor(m_colorBD);
     }
  }
//+------------------------------------------------------------------+
//| border style                                                     |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetStyle(ENUM_LINE_STYLE value)
  {
   if(m_created)
     {
      m_style=value;
      m_graph_base.SetStyle(m_style);
     }
  }
//+------------------------------------------------------------------+
//| anchor point size                                                |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetPointWidth(int value)
  {
   if(m_created)
     {
      m_point_width=value;
      m_graph_base.SetWidth(m_point_width);
     }
  }
//+------------------------------------------------------------------+
//| fore/background                                                  |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetBack(bool value)
  {
   if(m_created)
     {
      m_back=value;
      m_graph_base.SetBack(m_back);
     }
  }
//+------------------------------------------------------------------+
//|  to select the object                                            |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetSelected(bool value)
  {
   if(m_created)
     {
      m_selected=value;
      m_graph_base.SetSelected(m_selected);
     }
  }
//+------------------------------------------------------------------+
//| to be selectable                                                 |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetSelectable(bool value)
  {
   if(m_created)
     {
      m_selected=value;
      m_graph_base.SetSelected(m_selected);
     }
  }
//+------------------------------------------------------------------+
//| z-order                                                          |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetZOrder(long value)
  {
   if(m_created)
     {
      m_zorder=value;
      m_graph_base.SetZOrder(m_zorder);
     }
  }
//+------------------------------------------------------------------+
//| not to show in the object list                                   |
//+------------------------------------------------------------------+
void CGBitmapLabel::SetHidden(bool value)
  {
   if(m_created)
     {
      m_hidden=value;
      m_graph_base.SetHidden(m_hidden);
     }
  }
//+------------------------------------------------------------------+
//| Get on-state picture name                                        |
//+------------------------------------------------------------------+
string CGBitmapLabel::GetFileOn(void)
  {
   return(m_graph_base.BmpFileOn());
  }
//+------------------------------------------------------------------+
//| Get off-state picture name                                       |
//+------------------------------------------------------------------+
string CGBitmapLabel::GetFileOff(void)
  {
   return(m_graph_base.BmpFileOff());
  }
//+------------------------------------------------------------------+
