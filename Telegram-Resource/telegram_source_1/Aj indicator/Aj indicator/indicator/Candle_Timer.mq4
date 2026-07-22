#property copyright "Copyright © 2009, Condor FX"
#property link      "support@buyload.ru"

#property indicator_chart_window

extern string Font = "Tahoma";
extern int Font_Size = 10;
extern color Font_Color = Silver;
double gda_unused_76[];

int init()
   {
   return (0);
   }
int deinit()
   {
   ObjectDelete("time");
   }
int start() {
   int li_8 = Time[0] + 60 * Period() - TimeCurrent();
   double ld_0 = li_8 / 60.0;
   int li_12 = li_8 % 60;
   int li_16 = (li_8 - li_12) / 3600;
   li_8 = (li_8 - li_12) / 60 - li_16*60;
   //Comment(li_8 + " minutes " + li_12 + " seconds left to bar end");
   if (ObjectFind("time") != 0) 
      {
      ObjectCreate("time", OBJ_TEXT, 0, Time[0], Bid - Font_Size*Point);
      ObjectSet("time",OBJPROP_BACK, false);
      ObjectSetText("time", "                  « " + li_16 +":" + li_8 + ":" + li_12, Font_Size, Font, Font_Color);
      } 
   else 
      {
      ObjectSetText("time", "                  « " + li_16 +":" + li_8 + ":" + li_12, Font_Size, Font, Font_Color);
      ObjectMove("time", 0, Time[0], Bid - Font_Size*Point);
      }
   return (0);
}