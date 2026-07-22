//+------------------------------------------------------------------+
//|                                              StockClockEnums.mqh |
//|                        Copyright 2015, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2015, MetaQuotes Software Corp."
#property link      "https://www.mql5.com"
#property strict
//+------------------------------------------------------------------+
//| Stock color scheme enum                                          |
//+------------------------------------------------------------------+
enum STOCK_SCHEME
  {
   black,
   white
  };
//+------------------------------------------------------------------+
//| Day Saving Time events enum                                      |
//+------------------------------------------------------------------+
enum DST_EVENT
  {
   dst_203,                                                                // USA, Canada. Change to summer. Second Sunday of March.
   dst_403,                                                                // Europa. Change to Summer. Last Sunday of March.
   dst_104,                                                                // Wellington, Sidney. Change to Winter. First Sunday of April.
                                                                           // Summer in north GMT zone.
   dst_409,                                                                // Wellington. Change to Summer. Last Sunday of September.
   dst_110,                                                                // Sidney. Change to Summer. First Summer of Octember.
   dst_410,                                                                // Europa. Change to Winter. Last Sunday of Octember.
   dst_111,                                                                // USA, Canada. Change to Winter. First Sunday of November.
                                                                           // Winter in north GMT zone.
   dst_999                                                                 // Error
  };
//+------------------------------------------------------------------+
