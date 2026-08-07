//+------------------------------------------------------------------+
//| GbpJpyMondayEA.mq5                                               |
//| Custom Monday-long seasonality EA for GBPJPY, built for FTMO use |
//|                                                                  |
//| Strategy (from the day-of-week study in ../REPORT.md):           |
//|   Buy GBPJPY on Monday's first bar (server 00:00, i.e. the week  |
//|   open on EET-style broker time), hold through Monday, close at  |
//|   the configured exit hour. ATR-based stop. One trade per week.  |
//|                                                                  |
//| FTMO compliance by construction:                                 |
//|   - one order per week, closed same day: no HFT, no tick         |
//|     scalping, no latency/feed arbitrage, trivial server load     |
//|   - no weekend holding (works on regular, non-Swing accounts)    |
//|   - daily-loss and total-drawdown guards halt trading well       |
//|     before FTMO's 5% daily / 10% overall limits                  |
//|   - optional news filter blocks entries near high-impact events  |
//|     (FTMO restricts news trading during Challenge/Verification)  |
//| This EA implements the account owner's own strategy; it is not   |
//| a commercial/third-party EA.                                     |
//+------------------------------------------------------------------+
#property copyright "Private strategy - not for distribution"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//--- inputs
input double InpRiskPercent      = 0.5;   // Risk per trade, % of balance
input double InpATRMult          = 1.5;   // Stop = ATR(D1) x this
input int    InpATRPeriod        = 14;    // ATR period (D1)
input double InpFixedStopPips    = 0;     // Fixed stop in pips (0 = use ATR)
input int    InpEntryHour        = 0;     // Entry hour, server time, Monday
input int    InpExitHour         = 23;    // Exit hour, server time, Monday
input double InpMaxDailyLossPct  = 3.0;   // Halt day if equity falls this % from day start
input double InpMaxTotalDDPct    = 8.0;   // Halt EA if equity falls this % from baseline
input double InpMaxSpreadPips    = 6.0;   // Skip entry if spread wider than this
input int    InpNewsBlockMinutes = 3;     // Skip entry within +/- minutes of high-impact news (0 = off)
input long   InpMagic            = 20260807;

CTrade  trade;
double  g_baselineEquity = 0;     // equity when EA first attached (challenge baseline)
double  g_dayStartEquity = 0;
int     g_dayOfEquity    = -1;
bool    g_totalHalt      = false;
datetime g_lastEntryDay  = 0;

double PipSize()   { return _Point * 10; }  // 3-digit JPY quotes: 1 pip = 0.01
double PipsToPrice(double pips) { return pips * PipSize(); }

//+------------------------------------------------------------------+
int OnInit()
{
   if(StringFind(_Symbol, "GBPJPY") < 0)
      Print("Warning: EA designed for GBPJPY, attached to ", _Symbol);
   trade.SetExpertMagicNumber(InpMagic);
   g_baselineEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   ResetDay();
   return INIT_SUCCEEDED;
}

void ResetDay()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   g_dayOfEquity    = t.day_of_year;
   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
}

//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
   }
   return false;
}

void CloseAll(const string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         trade.PositionClose(ticket);
         Print("Closed position: ", reason);
      }
   }
}

//+------------------------------------------------------------------+
//| Risk guards: return false if trading must stop                   |
//+------------------------------------------------------------------+
bool GuardsOK()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   if(g_totalHalt) return false;
   if(g_baselineEquity > 0 &&
      eq <= g_baselineEquity * (1.0 - InpMaxTotalDDPct / 100.0))
   {
      g_totalHalt = true;
      CloseAll("total drawdown guard hit - EA halted, detach or review");
      Print("TOTAL DRAWDOWN GUARD: equity ", eq, " vs baseline ", g_baselineEquity);
      return false;
   }
   if(eq <= g_dayStartEquity * (1.0 - InpMaxDailyLossPct / 100.0))
   {
      CloseAll("daily loss guard hit - no more trades today");
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Optional: block entries near high-impact calendar events         |
//+------------------------------------------------------------------+
bool NewsClear()
{
   if(InpNewsBlockMinutes <= 0) return true;
   MqlCalendarValue values[];
   datetime from = TimeCurrent() - InpNewsBlockMinutes * 60;
   datetime to   = TimeCurrent() + InpNewsBlockMinutes * 60;
   if(CalendarValueHistory(values, from, to) <= 0)
      return true;                       // calendar unavailable (e.g. tester) - do not block
   for(int i = 0; i < ArraySize(values); i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev)) continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;
      MqlCalendarCountry c;
      if(!CalendarCountryById(ev.country_id, c)) continue;
      if(c.currency == "GBP" || c.currency == "JPY" || c.currency == "USD")
      {
         Print("Entry blocked: high-impact ", c.currency, " event near now (", ev.name, ")");
         return false;
      }
   }
   return true;
}

//+------------------------------------------------------------------+
double StopDistancePrice()
{
   if(InpFixedStopPips > 0) return PipsToPrice(InpFixedStopPips);
   int h = iATR(_Symbol, PERIOD_D1, InpATRPeriod);
   double buf[];
   if(h == INVALID_HANDLE || CopyBuffer(h, 0, 1, 1, buf) < 1)
      return PipsToPrice(150);           // conservative fallback
   return buf[0] * InpATRMult;
}

double LotForRisk(double stopPrice)
{
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0 || stopPrice <= 0) return 0;
   double lossPerLot = stopPrice / tickSize * tickValue;
   double lots = riskMoney / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / step) * step;
   lots = MathMax(lots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
   lots = MathMin(lots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
   return lots;
}

//+------------------------------------------------------------------+
void OnTick()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day_of_year != g_dayOfEquity) ResetDay();

   bool inPos = HasOpenPosition();

   if(!GuardsOK()) return;

   // exit: at/after exit hour on Monday, or any bar that is no longer Monday
   if(inPos && (t.day_of_week != 1 || t.hour >= InpExitHour))
   {
      CloseAll("scheduled Monday exit");
      return;
   }

   // entry: Monday, entry hour, once per week
   if(inPos || t.day_of_week != 1 || t.hour != InpEntryHour) return;

   datetime today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   if(today == g_lastEntryDay) return;   // already traded this Monday

   double spreadPips = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) -
                        SymbolInfoDouble(_Symbol, SYMBOL_BID)) / PipSize();
   if(spreadPips > InpMaxSpreadPips)
   {
      Print("Entry skipped: spread ", DoubleToString(spreadPips, 1), " pips");
      return;
   }
   if(!NewsClear()) return;

   double stopDist = StopDistancePrice();
   double lots     = LotForRisk(stopDist);
   if(lots <= 0) { Print("Entry skipped: lot calc failed"); return; }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = NormalizeDouble(ask - stopDist, _Digits);
   if(trade.Buy(lots, _Symbol, 0.0, sl, 0.0, "Monday seasonality long"))
   {
      g_lastEntryDay = today;
      Print("Monday long opened: ", lots, " lots, SL ", sl,
            " (", DoubleToString(stopDist / PipSize(), 0), " pips)");
   }
   else
      Print("Buy failed: ", trade.ResultRetcodeDescription());
}
//+------------------------------------------------------------------+
