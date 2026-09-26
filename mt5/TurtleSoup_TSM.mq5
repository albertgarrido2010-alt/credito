//+------------------------------------------------------------------+
//| TurtleSoup_TSM.mq5                                                |
//| Turtle Soup M5 en US100 / USTEC con las reglas del backtest:      |
//|  1) Régimen: cierre < SMA20 -> solo compras (TS alcista);          |
//|              cierre > SMA20 -> solo ventas (TS bajista).           |
//|  2) TS alcista: low < low anterior y close > low anterior.         |
//|     TS bajista: high > high anterior y close < high anterior.      |
//|  3) Gap: si open < low anterior u open > high anterior, no vale.   |
//|  4) Velas gatillo de 09:30 a 09:55 de NY (15:30-15:55 de Madrid), |
//|     máximo 1 operación al día (la primera válida).                 |
//|  5) Entrada al cierre de la gatillo; SL fijo en points de MT5;     |
//|     TP = RR x SL; cierre                                           |
//|     forzado al cierre de la vela de las 14:00 de NY (a las 14:05). |
//|  6) Riesgo fijo por operación en la divisa de la cuenta.           |
//| Horario: siempre en hora de Nueva York (09:30-09:55 gatillo,     |
//| cierre 14:00). El EA detecta solo el desfase del broker buscando  |
//| la pausa diaria del Nasdaq (17:00-18:00 NY) en sus velas M5, así  |
//| que se adapta a cualquier broker y a los cambios de horario.      |
//+------------------------------------------------------------------+
#property copyright "credito"
#property version   "1.00"

#include <Trade/Trade.mqh>

enum ENUM_MODO { MODO_COMBINADO = 0, MODO_SOLO_ALCISTAS = 1, MODO_SOLO_BAJISTAS = 2 };

input group "Estrategia"
input ENUM_MODO InpModo          = MODO_COMBINADO; // Combinado / solo alcistas / solo bajistas
input int       InpSLPoints      = 11250;          // SL en points de MT5 (11250 x 0,01 = 112,5 puntos de índice)
input double    InpRR            = 1.00;           // RR: TP = RR x SL
input int       InpSMA           = 20;             // Periodo de la SMA de régimen (cierre, M5)
input double    InpRiesgo        = 100.0;          // Riesgo por operación (divisa de la cuenta)

input group "Horario (hora de Nueva York)"
input string    InpVentanaIni    = "09:30";        // Primera vela gatillo (= 15:30 de Madrid)
input string    InpVentanaFin    = "09:55";        // Última vela gatillo
input string    InpCierre        = "14:00";        // Vela de cierre forzado (= 20:00 de Madrid; se cierra a su cierre)
input int       InpPausaNY       = 17;             // Hora de NY en que empieza la pausa diaria del índice

input group "Ejecución"
input ulong     InpMagic         = 20260926;
input int       InpDesviacion    = 30;             // Deslizamiento máximo (points)

CTrade  trade;
int     hSMA = INVALID_HANDLE;
datetime ultimaBarra = 0;
int     diaOperado = -1;   // día (hora de NY) en que ya se abrió la operación

//--- utilidades de fecha -------------------------------------------------
int MinutosDe(const string hhmm)
{
   string p[];
   if(StringSplit(hhmm, ':', p) != 2) return -1;
   return (int)StringToInteger(p[0]) * 60 + (int)StringToInteger(p[1]);
}

// Desfase servidor - Nueva York (horas), detectado con la pausa diaria del índice en las velas M5:
// la última vela antes de un hueco de 30-150 min cierra a la hora InpPausaNY de NY.
int  desfaseNY = 7;          // valor por defecto (servidor = NY + 7) hasta detectarlo
datetime ultimaDeteccion = 0;

bool DetectarDesfase()
{
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int n = CopyRates(_Symbol, PERIOD_M5, 1, 12 * 24 * 8, r);   // ~8 días de velas
   if(n < 50) return false;
   int votos[25];
   ArrayInitialize(votos, 0);
   int encontrados = 0;
   for(int i = 0; i < n - 1 && encontrados < 5; i++)
   {
      long hueco = (long)(r[i].time - r[i + 1].time);
      if(hueco < 30 * 60 || hueco > 150 * 60) continue;          // solo la pausa diaria (no fin de semana)
      datetime inicioPausa = r[i + 1].time + 5 * 60;            // cierre de la última vela antes del hueco
      MqlDateTime d; TimeToStruct(inicioPausa, d);
      int horaServ = d.hour + (d.min >= 30 ? 1 : 0);
      int off = ((horaServ - InpPausaNY) % 24 + 24) % 24;
      if(off > 12) off -= 24;
      votos[off + 12]++;
      encontrados++;
   }
   if(encontrados == 0) return false;
   // la hora que más se repite en las últimas pausas (un festivo con cierre temprano no la cambia)
   int mejor = ArrayMaximum(votos);
   int nuevo = mejor - 12;
   if(nuevo != desfaseNY)
      PrintFormat("Desfase servidor - Nueva York: %+d h (detectado en %d pausas diarias)", nuevo, votos[mejor]);
   desfaseNY = nuevo;
   return true;
}

// hora del servidor -> hora de Nueva York
datetime ANY(const datetime tServidor)
{
   return tServidor - desfaseNY * 3600;
}

int MinutoDelDia(const datetime t)
{
   MqlDateTime d; TimeToStruct(t, d);
   return d.hour * 60 + d.min;
}

int ClaveDia(const datetime t)
{
   MqlDateTime d; TimeToStruct(t, d);
   return d.year * 1000 + d.day_of_year;
}

//--- posición --------------------------------------------------------------
bool TengoPosicion()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
         return true;
   }
   return false;
}

void CerrarPosiciones()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
         trade.PositionClose(tk);
   }
}

// Lotes para arriesgar InpRiesgo (divisa de la cuenta) entre la entrada y el SL.
// OrderCalcProfit hace la conversión de la divisa del símbolo (USD) a la de la cuenta (p. ej. EUR).
double Lotes(const ENUM_ORDER_TYPE tipo, const double entrada, const double sl)
{
   double paso = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double perdida1Lote = 0;
   if(!OrderCalcProfit(tipo, _Symbol, 1.0, entrada, sl, perdida1Lote) || perdida1Lote == 0)
   {
      // alternativa: valor del tick (puede venir sin convertir en el probador)
      double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickVal <= 0 || tickSize <= 0) return 0;
      perdida1Lote = MathAbs(entrada - sl) / tickSize * tickVal;
      Print("OrderCalcProfit no disponible; se usa el valor del tick");
   }
   perdida1Lote = MathAbs(perdida1Lote);
   double lotes = MathRound(InpRiesgo / perdida1Lote / paso) * paso;   // al paso más cercano
   if(lotes < vmin)
   {
      PrintFormat("Riesgo %.2f insuficiente: el lote mínimo (%.2f) arriesga %.2f", InpRiesgo, vmin, vmin * perdida1Lote);
      return 0;
   }
   lotes = MathMin(lotes, vmax);
   PrintFormat("Lotes %.2f -> riesgo real hasta el SL %.2f %s (objetivo %.2f)", lotes, lotes * perdida1Lote,
               AccountInfoString(ACCOUNT_CURRENCY), InpRiesgo);
   return lotes;
}

//--- ciclo -----------------------------------------------------------------
int OnInit()
{
   hSMA = iMA(_Symbol, PERIOD_M5, InpSMA, 0, MODE_SMA, PRICE_CLOSE);
   if(hSMA == INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDesviacion);
   if(MinutosDe(InpVentanaIni) < 0 || MinutosDe(InpVentanaFin) < 0 || MinutosDe(InpCierre) < 0)
      return INIT_PARAMETERS_INCORRECT;
   if(InpSLPoints <= 0) return INIT_PARAMETERS_INCORRECT;
   PrintFormat("SL = %d points x %s = %.2f de precio", InpSLPoints, DoubleToString(_Point, _Digits), InpSLPoints * _Point);
   if(!DetectarDesfase()) Print("Aún no hay velas para detectar el desfase; se usa servidor = NY + 7 hasta detectarlo");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hSMA != INVALID_HANDLE) IndicatorRelease(hSMA);
}

void OnTick()
{
   datetime barra = iTime(_Symbol, PERIOD_M5, 0);
   if(barra == 0 || barra == ultimaBarra) return;   // solo al abrir cada vela M5
   ultimaBarra = barra;
   if(barra - ultimaDeteccion >= 3600) { DetectarDesfase(); ultimaDeteccion = barra; }

   // una vez al día: en qué hora del servidor cae la apertura de NY
   static int diaAviso = -1;
   if(ClaveDia(ANY(barra)) != diaAviso)
   {
      diaAviso = ClaveDia(ANY(barra));
      int ini = MinutosDe(InpVentanaIni) + desfaseNY * 60, fin = MinutosDe(InpCierre) + desfaseNY * 60;
      PrintFormat("Apertura NY %s = %02d:%02d del servidor (servidor = NY %+d h); cierre forzado %02d:%02d del servidor",
                  InpVentanaIni, (ini / 60 + 24) % 24, ini % 60, desfaseNY, (fin / 60 + 24) % 24, fin % 60);
   }

   // cierre forzado: al abrir una vela posterior a la de InpCierre (= cierre de esa vela)
   datetime refAhora = ANY(barra);
   if(TengoPosicion() && MinutoDelDia(refAhora) > MinutosDe(InpCierre))
      CerrarPosiciones();

   // vela gatillo = la última cerrada (shift 1); vela anterior = shift 2
   datetime tGat = iTime(_Symbol, PERIOD_M5, 1);
   datetime refGat = ANY(tGat);
   int m = MinutoDelDia(refGat);
   if(m < MinutosDe(InpVentanaIni) || m > MinutosDe(InpVentanaFin)) return;
   if(diaOperado == ClaveDia(refGat) || TengoPosicion()) return;

   double o1 = iOpen(_Symbol, PERIOD_M5, 1), h1 = iHigh(_Symbol, PERIOD_M5, 1);
   double l1 = iLow(_Symbol, PERIOD_M5, 1),  c1 = iClose(_Symbol, PERIOD_M5, 1);
   double h2 = iHigh(_Symbol, PERIOD_M5, 2), l2 = iLow(_Symbol, PERIOD_M5, 2);
   double sma[1];
   if(CopyBuffer(hSMA, 0, 1, 1, sma) != 1) return;

   if(o1 < l2 || o1 > h2) return;                              // gap: TS inválido
   bool compra = (l1 < l2 && c1 > l2 && c1 < sma[0]) && InpModo != MODO_SOLO_BAJISTAS;
   bool venta  = (h1 > h2 && c1 < h2 && c1 > sma[0]) && InpModo != MODO_SOLO_ALCISTAS;
   if(!compra && !venta) return;

   double dist = InpSLPoints * _Point;               // points de MT5 -> distancia en precio
   int dig = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   bool ok;
   if(compra)
   {
      double px = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = NormalizeDouble(px - dist, dig), tp = NormalizeDouble(px + InpRR * dist, dig);
      double lotes = Lotes(ORDER_TYPE_BUY, px, sl);
      if(lotes <= 0) return;
      ok = trade.Buy(lotes, _Symbol, 0, sl, tp, "TSM compra");
   }
   else
   {
      double px = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = NormalizeDouble(px + dist, dig), tp = NormalizeDouble(px - InpRR * dist, dig);
      double lotes = Lotes(ORDER_TYPE_SELL, px, sl);
      if(lotes <= 0) return;
      ok = trade.Sell(lotes, _Symbol, 0, sl, tp, "TSM venta");
   }
   if(ok) diaOperado = ClaveDia(refGat);   // máximo 1 operación al día, aunque salte enseguida
}
//+------------------------------------------------------------------+
