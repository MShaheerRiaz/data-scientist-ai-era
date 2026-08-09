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
input bool   InpJournal          = true;  // Write JSONL journal (Common\Files)
input double InpFtmoTargetPct    = 10.0;  // FTMO profit target % (10 = Challenge, 5 = Verification, 0 = off)
input double InpFtmoDailyLossPct = 5.0;   // FTMO max daily loss %
input double InpFtmoMaxLossPct   = 10.0;  // FTMO max overall loss %
input bool   InpPushAlerts       = true;  // Also push to phone (needs MetaQuotes ID in MT5 options)

CTrade  trade;
bool    g_ftmoPassed    = false;
bool    g_ftmoFailed    = false;
datetime g_lastDailyBreachDay = 0;
double  g_baselineEquity = 0;     // equity when EA first attached (challenge baseline)
double  g_dayStartEquity = 0;
int     g_dayOfEquity    = -1;
bool    g_totalHalt      = false;
datetime g_lastEntryDay  = 0;

double PipSize()   { return _Point * 10; }  // 3-digit JPY quotes: 1 pip = 0.01
double PipsToPrice(double pips) { return pips * PipSize(); }

//+------------------------------------------------------------------+
//| Append-only JSONL journal, same shape as the Binance bot's:      |
//| every decision is logged, including skipped entries and why —    |
//| skips tell you whether the filters are saving you or muzzling    |
//| you. File: Common\Files\GbpJpyMondayEA_journal.jsonl             |
//+------------------------------------------------------------------+
const string JOURNAL_FILE = "GbpJpyMondayEA_journal.jsonl";

void Journal(const string event, const string kvJson)
{
   if(!InpJournal) return;
   int fh = FileOpen(JOURNAL_FILE, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(fh == INVALID_HANDLE) { Print("journal open failed: ", GetLastError()); return; }
   FileSeek(fh, 0, SEEK_END);
   string line = StringFormat(
      "{\"ts\":\"%s\",\"event\":\"%s\",\"symbol\":\"%s\",\"equity\":%.2f,\"balance\":%.2f%s%s}",
      TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), event, _Symbol,
      AccountInfoDouble(ACCOUNT_EQUITY), AccountInfoDouble(ACCOUNT_BALANCE),
      StringLen(kvJson) > 0 ? "," : "", kvJson);
   FileWriteString(fh, line + "\n");
   FileClose(fh);
}

string J(const string k, const double v)  { return StringFormat("\"%s\":%.3f", k, v); }
string Js(const string k, const string v) { return StringFormat("\"%s\":\"%s\"", k, v); }

//+------------------------------------------------------------------+
int OnInit()
{
   if(StringFind(_Symbol, "GBPJPY") < 0)
      Print("Warning: EA designed for GBPJPY, attached to ", _Symbol);
   trade.SetExpertMagicNumber(InpMagic);
   g_baselineEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   ResetDay();
   Journal("attach", J("baseline_equity", g_baselineEquity) + "," +
                     J("risk_pct", InpRiskPercent) + "," + J("atr_mult", InpATRMult));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   Journal("detach", StringFormat("\"reason_code\":%d", reason));
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
         double openPx  = PositionGetDouble(POSITION_PRICE_OPEN);
         double curPx   = PositionGetDouble(POSITION_PRICE_CURRENT);
         double profit  = PositionGetDouble(POSITION_PROFIT);
         double lots    = PositionGetDouble(POSITION_VOLUME);
         long   openTs  = PositionGetInteger(POSITION_TIME);
         trade.PositionClose(ticket);
         Print("Closed position: ", reason);
         Journal("exit", Js("reason", reason) + "," +
                 J("entry_price", openPx) + "," + J("exit_price", curPx) + "," +
                 J("pips", (curPx - openPx) / PipSize()) + "," +
                 J("profit", profit) + "," + J("lots", lots) + "," +
                 StringFormat("\"held_hours\":%.1f",
                              (double)(TimeCurrent() - openTs) / 3600.0));
      }
   }
}

//+------------------------------------------------------------------+
//| FTMO status monitor: alerts + journals PASSED / DAILY BREACH /   |
//| FAILED against the account baseline (attach-time equity).        |
//| Note: FTMO measures the daily loss from balance/equity at        |
//| midnight CE(S)T; this check uses the server-day start equity —   |
//| close enough for monitoring, and the EA's own tighter guards     |
//| (-3% day / -8% total) halt trading well before a real breach.    |
//+------------------------------------------------------------------+
void Notify(const string msg)
{
   Print(msg);
   Alert(msg);
   if(InpPushAlerts) SendNotification(msg);
}

void CheckFtmoStatus()
{
   if(g_baselineEquity <= 0) return;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   if(InpFtmoTargetPct > 0 && !g_ftmoPassed &&
      eq >= g_baselineEquity * (1.0 + InpFtmoTargetPct / 100.0))
   {
      g_ftmoPassed = true;
      Notify(StringFormat("FTMO TARGET REACHED: +%.1f%% (equity %.2f). Phase passed - stop or continue manually.",
             InpFtmoTargetPct, eq));
      Journal("ftmo_passed", J("target_pct", InpFtmoTargetPct));
   }
   if(!g_ftmoFailed && eq <= g_baselineEquity * (1.0 - InpFtmoMaxLossPct / 100.0))
   {
      g_ftmoFailed = true;
      Notify(StringFormat("FTMO MAX LOSS BREACHED: -%.1f%% from baseline (equity %.2f). Challenge FAILED.",
             InpFtmoMaxLossPct, eq));
      Journal("ftmo_failed", J("max_loss_pct", InpFtmoMaxLossPct));
      g_totalHalt = true;
      CloseAll("FTMO max loss breached");
   }
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   datetime today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   if(today != g_lastDailyBreachDay &&
      eq <= g_dayStartEquity * (1.0 - InpFtmoDailyLossPct / 100.0))
   {
      g_lastDailyBreachDay = today;
      Notify(StringFormat("FTMO DAILY LOSS BREACHED: -%.1f%% today (equity %.2f). Rule violated.",
             InpFtmoDailyLossPct, eq));
      Journal("ftmo_daily_breach", J("daily_loss_pct", InpFtmoDailyLossPct));
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
      Journal("guard_total_drawdown", J("baseline", g_baselineEquity));
      CloseAll("total drawdown guard hit - EA halted, detach or review");
      Print("TOTAL DRAWDOWN GUARD: equity ", eq, " vs baseline ", g_baselineEquity);
      return false;
   }
   if(eq <= g_dayStartEquity * (1.0 - InpMaxDailyLossPct / 100.0))
   {
      Journal("guard_daily_loss", J("day_start_equity", g_dayStartEquity));
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

   CheckFtmoStatus();

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
      Journal("skip_entry", Js("reason", "spread") + "," + J("spread_pips", spreadPips));
      return;
   }
   if(!NewsClear())
   {
      Journal("skip_entry", Js("reason", "news_blackout"));
      return;
   }

   double stopDist = StopDistancePrice();
   double lots     = LotForRisk(stopDist);
   if(lots <= 0)
   {
      Print("Entry skipped: lot calc failed");
      Journal("skip_entry", Js("reason", "lot_calc_failed"));
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = NormalizeDouble(ask - stopDist, _Digits);
   if(trade.Buy(lots, _Symbol, 0.0, sl, 0.0, "Monday seasonality long"))
   {
      g_lastEntryDay = today;
      Print("Monday long opened: ", lots, " lots, SL ", sl,
            " (", DoubleToString(stopDist / PipSize(), 0), " pips)");
      Journal("entry", J("price", trade.ResultPrice()) + "," + J("lots", lots) + "," +
              J("sl", sl) + "," + J("sl_pips", stopDist / PipSize()) + "," +
              J("spread_pips", spreadPips) + "," + J("risk_pct", InpRiskPercent));
   }
   else
   {
      Print("Buy failed: ", trade.ResultRetcodeDescription());
      Journal("error", Js("where", "buy") + "," + Js("message", trade.ResultRetcodeDescription()));
   }
}
//+------------------------------------------------------------------+
