/*
   G e n e r a t e d  by ex4-to-mq4 decompiler FREEWARE 4.0.509.5
   Website:  h t TP :// ww W.m E ta q uotes .n eT
   E-mail :  sUP P o rt@m E t Aq UoT es . N E t
*/
#property link      "http://www.forexter.land.ru/indicators.htm"

#property indicator_chart_window
#property indicator_buffers 8
#property indicator_color1 MediumBlue
#property indicator_color2 RoyalBlue
#property indicator_color3 Blue
#property indicator_color4 Blue
#property indicator_color5 DarkGreen
#property indicator_color6 Red
#property indicator_color7 DarkGreen
#property indicator_color8 Red

extern int SR = 3;
extern int SRZZ = 12;
extern int MainRZZ = 20;
extern int FP = 21;
extern int SMF = 3;
extern bool DrawZZ = FALSE;
extern int PriceConst = 0;
double G_ibuf_104[];
double G_ibuf_108[];
double Gda_112[];
double Gda_116[];
double G_ibuf_120[];
double G_ibuf_124[];
double G_ibuf_128[];
double G_ibuf_132[];
int Gia_136[6] = {0, 0, 0, 0, 0, 0};
int Gia_140[5] = {0, 0, 0, 0, 0};
int Gi_144;
int Gi_148;
int Gi_152;
int Gi_156;
int Gi_160;
bool Gi_164 = TRUE;
int G_bars_168 = 0;

void MainCalculation(int Ai_0) {
   if (Bars - Ai_0 > SR + 1) SACalc(Ai_0);
   else Gda_112[Ai_0] = 0;
   if (Bars - Ai_0 > FP + SR + 2) {
      SMCalc(Ai_0);
      return;
   }
   Gda_116[Ai_0] = 0;
}

void SACalc(int Ai_0) {
   int Li_4;
   int count_8;
   int Li_12;
   int Li_16;
   double Ld_24;
   switch (PriceConst) {
   case 0:
      Gda_112[Ai_0] = iMA(NULL, 0, SR + 1, 0, MODE_LWMA, PRICE_CLOSE, Ai_0);
      break;
   case 1:
      Gda_112[Ai_0] = iMA(NULL, 0, SR + 1, 0, MODE_LWMA, PRICE_OPEN, Ai_0);
      break;
   case 4:
      Gda_112[Ai_0] = iMA(NULL, 0, SR + 1, 0, MODE_LWMA, PRICE_MEDIAN, Ai_0);
      break;
   case 5:
      Gda_112[Ai_0] = iMA(NULL, 0, SR + 1, 0, MODE_LWMA, PRICE_TYPICAL, Ai_0);
      break;
   case 6:
      Gda_112[Ai_0] = iMA(NULL, 0, SR + 1, 0, MODE_LWMA, PRICE_WEIGHTED, Ai_0);
      break;
   default:
      Gda_112[Ai_0] = iMA(NULL, 0, SR + 1, 0, MODE_LWMA, PRICE_OPEN, Ai_0);
   }
   for (int Li_20 = Ai_0 + SR + 2; Li_20 > Ai_0; Li_20--) {
      Ld_24 = 0.0;
      Li_4 = 0;
      count_8 = 0;
      Li_12 = Li_20 + SR;
      Li_16 = Li_20 - SR;
      if (Li_16 < Ai_0) Li_16 = Ai_0;
      while (Li_12 >= Li_20) {
         count_8++;
         Ld_24 += count_8 * SnakePrice(Li_12);
         Li_4 += count_8;
         Li_12--;
      }
      while (Li_12 >= Li_16) {
         count_8--;
         Ld_24 += count_8 * SnakePrice(Li_12);
         Li_4 += count_8;
         Li_12--;
      }
      Gda_112[Li_20] = Ld_24 / Li_4;
   }
}

double SnakePrice(int Ai_0) {
   switch (PriceConst) {
   case 0:
      return (Close[Ai_0]);
   case 1:
      return (Open[Ai_0]);
   case 4:
      return ((High[Ai_0] + Low[Ai_0]) / 2.0);
   case 5:
      return ((Close[Ai_0] + High[Ai_0] + Low[Ai_0]) / 3.0);
   case 6:
      return ((2.0 * Close[Ai_0] + High[Ai_0] + Low[Ai_0]) / 4.0);
   }
   return (Open[Ai_0]);
}

void SMCalc(int Ai_0) {
   double Ld_4;
   double Ld_12;
   for (int Li_20 = Ai_0 + SR + 2; Li_20 >= Ai_0; Li_20--) {
      Ld_4 = Gda_112[ArrayMaximum(Gda_112, FP, Li_20)];
      Ld_12 = Gda_112[ArrayMinimum(Gda_112, FP, Li_20)];
      Gda_116[Li_20] = ((SMF + 2) * 2 * Gda_112[Li_20] - (Ld_4 + Ld_12)) / 2.0 / (SMF + 1);
   }
}

void LZZCalc(int Ai_0) {
   int Li_8;
   int Li_12;
   int Li_16;
   int index_20;
   int Li_4 = Ai_0 - 1;
   int Li_24 = 0;
   int Li_28 = 0;
   while (Li_4 < Gi_144 && Li_16 == 0) {
      Li_4++;
      G_ibuf_108[Li_4] = 0;
      Li_8 = Li_4 - MainRZZ;
      if (Li_8 < Ai_0) Li_8 = Ai_0;
      Li_12 = Li_4 + MainRZZ;
      if (Li_4 == ArrayMinimum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
         Li_16 = -1;
         Li_24 = Li_4;
      }
      if (Li_4 == ArrayMaximum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
         Li_16 = 1;
         Li_28 = Li_4;
      }
   }
   if (Li_16 != 0) {
      index_20 = 0;
      if (Li_4 > Ai_0) {
         if (Gda_116[Li_4] > Gda_116[Ai_0]) {
            if (Li_16 == 1) {
               if (Li_4 >= Ai_0 + MainRZZ && index_20 < 5) {
                  index_20++;
                  Gia_136[index_20] = Li_4;
               }
               Li_28 = Li_4;
               G_ibuf_108[Li_4] = Gda_116[Li_4];
            }
         } else {
            if (Li_16 == -1) {
               if (Li_4 >= Ai_0 + MainRZZ && index_20 < 5) {
                  index_20++;
                  Gia_136[index_20] = Li_4;
               }
               Li_24 = Li_4;
               G_ibuf_108[Li_4] = Gda_116[Li_4];
            }
         }
      }
      if (Li_4 < Gi_160 || index_20 < 5) {
         while (true) {
            G_ibuf_108[Li_4] = 0;
            Li_8 = Li_4 - MainRZZ;
            if (Li_8 < Ai_0) Li_8 = Ai_0;
            Li_12 = Li_4 + MainRZZ;
            if (Li_4 == ArrayMinimum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
               if (Li_16 == -1 && Gda_116[Li_4] < Gda_116[Li_24]) {
                  if (Li_4 >= Ai_0 + MainRZZ && index_20 < 5) Gia_136[index_20] = Li_4;
                  G_ibuf_108[Li_24] = 0;
                  G_ibuf_108[Li_4] = Gda_116[Li_4];
                  Li_24 = Li_4;
               }
               if (Li_16 == 1) {
                  if (Li_4 >= Ai_0 + MainRZZ && index_20 < 5) {
                     index_20++;
                     Gia_136[index_20] = Li_4;
                  }
                  G_ibuf_108[Li_4] = Gda_116[Li_4];
                  Li_16 = -1;
                  Li_24 = Li_4;
               }
            }
            if (Li_4 == ArrayMaximum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
               if (Li_16 == 1 && Gda_116[Li_4] > Gda_116[Li_28]) {
                  if (Li_4 >= Ai_0 + MainRZZ && index_20 < 5) Gia_136[index_20] = Li_4;
                  G_ibuf_108[Li_28] = 0;
                  G_ibuf_108[Li_4] = Gda_116[Li_4];
                  Li_28 = Li_4;
               }
               if (Li_16 == -1) {
                  if (Li_4 >= Ai_0 + MainRZZ && index_20 < 5) {
                     index_20++;
                     Gia_136[index_20] = Li_4;
                  }
                  G_ibuf_108[Li_4] = Gda_116[Li_4];
                  Li_16 = 1;
                  Li_28 = Li_4;
               }
            }
            Li_4++;
            if (Li_4 > Gi_144) return;
            if (Li_4 < Gi_160 || index_20 < 5) continue;
            break;
         }
      }
      Gi_152 = Bars - Gia_136[5];
      G_ibuf_108[Ai_0] = Gda_116[Ai_0];
      return;
   }
}

void SZZCalc(int Ai_0) {
   int Li_8;
   int Li_12;
   int Li_16;
   int index_20;
   int Li_4 = Ai_0 - 1;
   int Li_24 = 0;
   int Li_28 = 0;
   while (Li_4 <= Gi_160 && Li_16 == 0) {
      Li_4++;
      G_ibuf_132[Li_4] = 0;
      G_ibuf_128[Li_4] = 0;
      G_ibuf_124[Li_4] = 0;
      G_ibuf_120[Li_4] = 0;
      G_ibuf_104[Li_4] = 0;
      Li_8 = Li_4 - SRZZ;
      if (Li_8 < Ai_0) Li_8 = Ai_0;
      Li_12 = Li_4 + SRZZ;
      if (Li_4 == ArrayMinimum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
         Li_16 = -1;
         Li_24 = Li_4;
      }
      if (Li_4 == ArrayMaximum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
         Li_16 = 1;
         Li_28 = Li_4;
      }
   }
   if (Li_16 != 0) {
      index_20 = 0;
      if (Li_4 > Ai_0) {
         if (Gda_116[Li_4] > Gda_116[Ai_0]) {
            if (Li_16 == 1) {
               if (Li_4 >= Ai_0 + SRZZ && index_20 < 4) {
                  index_20++;
                  Gia_140[index_20] = Li_4;
               }
               Li_28 = Li_4;
               G_ibuf_124[Li_4 - 1] = Open[Li_4 - 1];
            }
         } else {
            if (Li_16 == -1) {
               if (Li_4 >= Ai_0 + SRZZ && index_20 < 4) {
                  index_20++;
                  Gia_140[index_20] = Li_4;
               }
               Li_24 = Li_4;
               G_ibuf_120[Li_4 - 1] = Open[Li_4 - 1];
            }
         }
      }
      if (Li_4 <= Gi_160 || index_20 < 4) {
         while (true) {
            G_ibuf_132[Li_4] = 0;
            G_ibuf_128[Li_4] = 0;
            G_ibuf_124[Li_4] = 0;
            G_ibuf_120[Li_4] = 0;
            G_ibuf_104[Li_4] = 0;
            Li_8 = Li_4 - SRZZ;
            if (Li_8 < Ai_0) Li_8 = Ai_0;
            Li_12 = Li_4 + SRZZ;
            if (Li_4 == ArrayMinimum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
               if (Li_16 == -1 && Gda_116[Li_4] < Gda_116[Li_24]) {
                  if (Li_4 >= Ai_0 + SRZZ && index_20 < 4) Gia_140[index_20] = Li_4;
                  G_ibuf_120[Li_24 - 1] = 0;
                  G_ibuf_120[Li_4 - 1] = Open[Li_4 - 1];
                  Li_24 = Li_4;
               }
               if (Li_16 == 1) {
                  if (Li_4 >= Ai_0 + SRZZ && index_20 < 4) {
                     index_20++;
                     Gia_140[index_20] = Li_4;
                  }
                  G_ibuf_120[Li_4 - 1] = Open[Li_4 - 1];
                  Li_16 = -1;
                  Li_24 = Li_4;
               }
            }
            if (Li_4 == ArrayMaximum(Gda_116, Li_12 - Li_8 + 1, Li_8)) {
               if (Li_16 == 1 && Gda_116[Li_4] > Gda_116[Li_28]) {
                  if (Li_4 >= Ai_0 + SRZZ && index_20 < 4) Gia_140[index_20] = Li_4;
                  G_ibuf_124[Li_28 - 1] = 0;
                  G_ibuf_124[Li_4 - 1] = Open[Li_4 - 1];
                  Li_28 = Li_4;
               }
               if (Li_16 == -1) {
                  if (Li_4 >= Ai_0 + SRZZ && index_20 < 4) {
                     index_20++;
                     Gia_140[index_20] = Li_4;
                  }
                  G_ibuf_124[Li_4 - 1] = Open[Li_4 - 1];
                  Li_16 = 1;
                  Li_28 = Li_4;
               }
            }
            Li_4++;
            if (Li_4 > Gi_160) return;
            if (Li_4 <= Gi_160 || index_20 < 4) continue;
            break;
         }
      }
      Gi_148 = Bars - Gia_140[4];
      return;
   }
}

void ArrCalc() {
   int Li_8;
   int Li_16 = 0;
   for (int Li_0 = Gi_160; G_ibuf_108[Li_0] == 0.0; Li_0--) {
   }
   int Li_4 = Li_0;
   double Ld_20 = G_ibuf_108[Li_0];
   for (Li_0--; G_ibuf_108[Li_0] == 0.0; Li_0--) {
   }
   if (G_ibuf_108[Li_0] > Ld_20) Li_16 = 1;
   if (G_ibuf_108[Li_0] > 0.0 && G_ibuf_108[Li_0] < Ld_20) Li_16 = -1;
   Ld_20 = G_ibuf_108[Li_4];
   for (Li_0 = Li_4 - 1; Li_0 > 0; Li_0--) {
      if (G_ibuf_108[Li_0] > Ld_20) {
         Li_16 = -1;
         Ld_20 = G_ibuf_108[Li_0];
      }
      if (G_ibuf_108[Li_0] > 0.0 && G_ibuf_108[Li_0] < Ld_20) {
         Li_16 = 1;
         Ld_20 = G_ibuf_108[Li_0];
      }
      if (Li_16 > 0 && G_ibuf_124[Li_0] > 0.0) {
         G_ibuf_104[Li_0] = Open[Li_0];
         G_ibuf_124[Li_0] = 0;
      }
      if (Li_16 < 0 && G_ibuf_120[Li_0] > 0.0) {
         G_ibuf_104[Li_0] = Open[Li_0];
         G_ibuf_120[Li_0] = 0;
      }
      if (Li_16 > 0 && G_ibuf_120[Li_0] > 0.0) {
         if (Li_0 > 1) {
            Li_4 = Li_0 - 1;
            Li_8 = Li_4 - SRZZ + 1;
            if (Li_8 < 0) Li_8 = 0;
            for (int Li_12 = Li_4; Li_12 >= Li_8 && G_ibuf_124[Li_12] == 0.0; Li_12--) {
               G_ibuf_128[Li_12] = G_ibuf_120[Li_0];
               G_ibuf_132[Li_12] = 0;
            }
         }
         if (Li_0 == 1) G_ibuf_128[0] = G_ibuf_120[Li_0];
      }
      if (Li_16 < 0 && G_ibuf_124[Li_0] > 0.0) {
         if (Li_0 > 1) {
            Li_4 = Li_0 - 1;
            Li_8 = Li_4 - SRZZ + 1;
            if (Li_8 < 0) Li_8 = 0;
            for (Li_12 = Li_4; Li_12 >= Li_8 && G_ibuf_120[Li_12] == 0.0; Li_12--) {
               G_ibuf_132[Li_12] = G_ibuf_124[Li_0];
               G_ibuf_128[Li_12] = 0;
            }
         }
         if (Li_0 == 1) G_ibuf_132[0] = G_ibuf_124[Li_0];
      }
   }
}

void deinit() {
}

int init() {
   IndicatorBuffers(8);
   SetIndexBuffer(0, G_ibuf_104);
   SetIndexStyle(0, DRAW_ARROW, EMPTY, 2);
   SetIndexArrow(0, SYMBOL_STOPSIGN);
   SetIndexEmptyValue(0, 0.0);
   SetIndexBuffer(1, G_ibuf_108);
   if (DrawZZ) {
      SetIndexStyle(1, DRAW_SECTION, EMPTY, 2);
      SetIndexEmptyValue(1, 0.0);
   } else SetIndexStyle(1, DRAW_NONE);
   SetIndexBuffer(2, Gda_112);
   SetIndexStyle(2, DRAW_NONE);
   SetIndexBuffer(3, Gda_116);
   SetIndexStyle(3, DRAW_NONE);
   SetIndexBuffer(4, G_ibuf_120);
   SetIndexStyle(4, DRAW_ARROW, EMPTY, 1);
   SetIndexArrow(4, 233);
   SetIndexEmptyValue(4, 0.0);
   SetIndexBuffer(5, G_ibuf_124);
   SetIndexStyle(5, DRAW_ARROW, EMPTY, 1);
   SetIndexArrow(5, 234);
   SetIndexEmptyValue(5, 0.0);
   SetIndexBuffer(6, G_ibuf_128);
   SetIndexStyle(6, DRAW_ARROW);
   SetIndexArrow(6, 217);
   SetIndexEmptyValue(6, 0.0);
   SetIndexBuffer(7, G_ibuf_132);
   SetIndexStyle(7, DRAW_ARROW);
   SetIndexArrow(7, 218);
   SetIndexEmptyValue(7, 0.0);
   return (0);
}

int start() {
   int Li_0 = IndicatorCounted();
   if (Li_0 < 0) return (-1);
   if (Li_0 > 0) Li_0--;
   if (Gi_164 == TRUE) {
      if (SR < 2) SR = 2;
      if (Bars <= (MainRZZ + FP + SR + 2) * 2) return (-1);
      if (SRZZ <= SR) SRZZ = SR + 1;
      Gi_144 = Bars - (MainRZZ + FP + SR + 2);
      Gi_160 = Gi_144;
      Gi_156 = Gi_160;
      G_bars_168 = Bars;
      Gi_164 = FALSE;
   }
   int Li_4 = Bars - Li_0;
   for (int Li_8 = Li_4; Li_8 >= 0; Li_8--) MainCalculation(Li_8);
   if (G_bars_168 != Bars) {
      Gi_156 = Bars - Gi_148;
      Gi_160 = Bars - Gi_152;
      G_bars_168 = Bars;
   }
   SZZCalc(0);
   LZZCalc(0);
   ArrCalc();
   return (0);
}
