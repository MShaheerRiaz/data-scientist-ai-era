# Bot Setup — click-by-click (GJ Bossman project)

Save this file, `GJ-Bossman.md`, and `GbpJpyMondayEA.mq5` into
`C:\Users\Microsoft\.claude\GJ Bossman\` on your laptop. That folder is the
project's home: memory file + EA + this guide. Any Claude session you start
later — point it at that folder and it knows everything.

---

## Step 1 — Get a demo account (free, 10 minutes)

Two options; A is better because it simulates FTMO's exact rules.

**Option A — FTMO Free Trial (recommended)**
1. Go to **ftmo.com** → top right **Client Area** → register (email + password).
2. In the Client Area click **Free Trial** → choose account size **$100,000**,
   platform **MT5** → confirm.
3. Within minutes you get an email + Client Area entry with three things:
   **Login number**, **Password**, **Server name** (e.g. `FTMO-Demo2`).
   Keep these — you'll type them into MT5 in Step 3.

**Option B — any MT5 demo** (fallback): inside MT5, File → Open an Account →
pick "MetaQuotes Ltd" or any broker → Demo. Works, but no FTMO rule simulation.

## Step 2 — Install MT5 (10 minutes)

1. If you took the FTMO trial: in the FTMO Client Area, click your trial
   account → **Download MT5** (this gets FTMO's branded MT5). Otherwise
   download from metatrader5.com.
2. Run the installer → Next → Finish. MT5 opens.

## Step 3 — Log in

1. In MT5: **File → Login to Trade Account**.
2. Type the **Login**, **Password**, and pick the **Server** from Step 1.
3. Bottom-right corner of MT5 should show connection bars + numbers
   (e.g. "3245/1 kb"). Red "No connection" = wrong server picked, try again.

## Step 4 — Install and compile the EA (15 minutes)

1. In MT5 press **F4** (opens MetaEditor).
2. In MetaEditor: **File → Open Data Folder** — a Windows Explorer window
   opens. Go into **MQL5 → Experts**.
3. Copy `GbpJpyMondayEA.mq5` from your `GJ Bossman` folder into that
   **Experts** folder.
4. Back in MetaEditor: **File → Open** → pick the file you just copied.
5. Press **F7** (Compile). Watch the bottom "Errors" tab.
   - Goal: **0 errors** (warnings are OK).
   - If there ARE errors: screenshot or copy the error lines and paste them
     to Claude — fixes are usually one-liners. This is the expected
     first-compile step, don't panic.
6. Close MetaEditor. In MT5, open the **Navigator** panel (Ctrl+N) →
   under **Expert Advisors** you should now see **GbpJpyMondayEA**.

## Step 5 — Verify in the Strategy Tester (30 minutes, optional but smart)

1. In MT5: **View → Strategy Tester** (Ctrl+R).
2. Settings tab: Expert = GbpJpyMondayEA, Symbol = **GBPJPY**, Period = **H1**,
   Model = "Every tick based on real ticks", Date = last 2 years,
   Deposit = 100,000.
3. Click **Start**. When done, check the Graph/Backtest tabs — you want a
   result in the same ballpark as the README table (+8–16 pips per Monday
   trade, ~4–5% of trades stopped out). Wildly different = tell Claude.

## Step 6 — Attach to live charts (10 minutes)

Do this twice — once per pair.

**Chart 1 — GBPJPY**
1. **File → New Chart → GBPJPY**. Set timeframe to **H1** (toolbar).
2. Drag **GbpJpyMondayEA** from Navigator onto the chart.
3. A dialog opens. **Common tab**: tick **Allow Algo Trading**.
4. **Inputs tab** — set exactly:
   - `InpRiskPercent` = **0.35**
   - `InpFridayShort` = **true**
   - everything else: leave default.
5. Click OK. Top-right of the chart should show **GbpJpyMondayEA** with a
   little blue/green hat icon (not grey/sad = good).

**Chart 2 — AUDJPY**
1. **File → New Chart → AUDJPY**, timeframe **H1**.
2. Drag the same EA on. Common tab: Allow Algo Trading.
3. **Inputs tab**:
   - `InpRiskPercent` = **0.35**
   - `InpFridayShort` = **false**  ← important, Friday short is GJ-only
   - everything else: default.
4. OK.

**Master switch:** the toolbar **Algo Trading** button (a robot icon) must be
green/ON. If it's red, click it once. Both EAs are dead while it's red.

## Step 7 — Phone alerts (5 minutes)

1. Install the **MetaTrader 5 app** on your phone (Play Store).
2. Phone app: Settings → **Chat and Messages** → your **MetaQuotes ID** is
   shown (8 characters, e.g. `A1B2C3D4`).
3. Laptop MT5: **Tools → Options → Notifications** tab → tick
   **Enable push notifications** → paste your MetaQuotes ID → click **Test**.
   Your phone should buzz. Now every entry/exit/FTMO-status event pings you.

## Step 8 — What running looks like

- The bot trades: **Monday 00:00** server open (both pairs, + gap-fill when
  there's a weekend gap down), exits Monday **23:00**; **Friday** GJ short
  00:00 → 22:00. Rest of the week: silence. That's correct behavior.
- **Laptop rule for paper month:** laptop ON + MT5 open from Sunday ~11pm
  server time through Tuesday 1am, and Fridays. If the laptop sleeps
  mid-trade the SL/TP still sit on the broker's server — you're protected;
  the EA closes any leftover position when it reconnects.
- Journal: MT5 → **File → Open Data Folder → up one level → Common → Files →
  `GbpJpyMondayEA_journal.jsonl`**. After ~4 Mondays, paste that file to
  Claude for the review.

## Step 9 — The month, then the decision

- Weeks 1–4: demo at the settings above. Zero cost.
- After 4 Mondays: journal review with Claude — compare fills/slippage/
  spread vs backtest. If it matches → buy the FTMO Challenge ($100k ≈ $540,
  refunded on pass) and switch risk inputs to challenge sizing (Claude will
  give the exact numbers then).
- VPS decision also happens then (MT5 built-in Virtual Hosting, ~$12–15/mo)
  — not needed for the demo month.

---

## TradingView / MCP — current status

- TradingView desktop has **no official MCP** — nothing to connect there.
  Screenshots pasted into Claude remain the way we do chart reviews, and
  they work fine.
- An MT5 MCP server (Claude reading your MT5 directly) is possible later on
  your laptop with a locally-running Claude Code session — parked until
  after the paper month, it adds nothing to the demo test.
- What actually matters for "further progress": the **journal file** —
  that's the bot's full memory, and pasting it beats any live connection.

## If something breaks

| Symptom | Fix |
|---|---|
| Compile errors at F7 | Paste errors to Claude |
| Grey/sad icon on chart | Algo Trading button is OFF, or "Allow Algo Trading" unticked in EA settings |
| "Not enough money" in Journal tab | Wrong account size / lots — tell Claude |
| No trade on Monday | Check MT5 Experts tab logs + journal file for `skip_entry` reason — this may be correct behavior (spread/news filter) |
| No phone alert | Redo Step 7, press Test again |
